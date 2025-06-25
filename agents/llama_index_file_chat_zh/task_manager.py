import asyncio
import logging
import traceback

from collections.abc import AsyncIterable
from typing import Any

from agents.llama_index_file_chat.agent import (
    ChatResponseEvent,
    InputEvent,
    LogEvent,
    ParseAndChat,
)
from common.server import utils
from common.server.task_manager import InMemoryTaskManager
from common.types import (
    Artifact,
    FilePart,
    InternalError,
    InvalidParamsError,
    JSONRPCResponse,
    Message,
    PushNotificationConfig,
    SendTaskRequest,
    SendTaskResponse,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskSendParams,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from common.utils.push_notification_auth import PushNotificationSenderAuth
from llama_index.core.workflow import Context


logger = logging.getLogger(__name__)


class LlamaIndexTaskManager(InMemoryTaskManager):
    # 技术上支持几乎所有类型，但我们将限制为一些常见类型
    SUPPORTED_INPUT_TYPES = [
        'text/plain',
        'application/pdf',
        'application/msword',
        'image/png',
        'image/jpeg',
    ]
    SUPPORTED_OUTPUT_TYPES = ['text', 'text/plain']

    def __init__(
        self,
        agent: ParseAndChat,
        notification_sender_auth: PushNotificationSenderAuth,
    ):
        super().__init__()
        self.agent = agent
        self.notification_sender_auth = notification_sender_auth
        # 按会话ID存储上下文状态
        # 理想情况下，您应该使用数据库或其他kv存储来存储上下文状态
        self.ctx_states: dict[str, dict[str, Any]] = {}

    async def _run_streaming_agent(self, request: SendTaskStreamingRequest):
        task_send_params: TaskSendParams = request.params
        task_id = task_send_params.id
        session_id = task_send_params.sessionId
        input_event = self._get_input_event(task_send_params)

        try:
            ctx = None
            handler = None

            # 检查我们是否有此会话的保存上下文状态
            print(f'任务数量: {len(self.tasks)}', flush=True)
            print(f'上下文状态数量: {len(self.ctx_states)}', flush=True)
            saved_ctx_state = self.ctx_states.get(session_id, None)

            if saved_ctx_state is not None:
                # 使用现有上下文恢复
                logger.info(f'使用保存的上下文恢复会话 {session_id}')
                ctx = Context.from_dict(self.agent, saved_ctx_state)
                handler = self.agent.run(
                    start_event=input_event,
                    ctx=ctx,
                )
            else:
                # 新会话！
                logger.info(f'启动新会话 {session_id}')
                handler = self.agent.run(
                    start_event=input_event,
                )

            # 流式传输更新
            async for event in handler.stream_events():
                if isinstance(event, LogEvent):
                    # 将日志事件作为中间消息发送
                    content = event.msg
                    parts = [{'type': 'text', 'text': content}]
                    task_status = TaskStatus(
                        state=TaskState.WORKING,
                        message=Message(role='agent', parts=parts),
                    )
                    latest_task = await self.update_store(
                        task_id, task_status, None
                    )
                    await self.send_task_notification(latest_task)

                    # 发送状态更新事件
                    task_update_event = TaskStatusUpdateEvent(
                        id=task_id, status=task_status, final=False
                    )
                    await self.enqueue_events_for_sse(
                        task_id, task_update_event
                    )

            # 如果我们到达这里而没有遇到返回，等待最终响应
            final_response = await handler
            if isinstance(final_response, ChatResponseEvent):
                content = final_response.response
                parts = [{'type': 'text', 'text': content}]
                metadata = (
                    final_response.citations
                    if hasattr(final_response, 'citations')
                    else None
                )
                if metadata is not None:
                    # 确保元数据是字符串键的字典
                    metadata = {str(k): v for k, v in metadata.items()}

                # 保存上下文状态以恢复当前会话
                self.ctx_states[session_id] = handler.ctx.to_dict()

                artifact = Artifact(
                    parts=parts, index=0, append=False, metadata=metadata
                )
                task_status = TaskStatus(state=TaskState.COMPLETED)
                latest_task = await self.update_store(
                    task_id, task_status, [artifact]
                )
                await self.send_task_notification(latest_task)

                # 发送工件更新
                task_artifact_update_event = TaskArtifactUpdateEvent(
                    id=task_id, artifact=artifact
                )
                await self.enqueue_events_for_sse(
                    task_id, task_artifact_update_event
                )

                # 发送最终状态更新
                task_update_event = TaskStatusUpdateEvent(
                    id=task_id, status=task_status, final=True
                )
                await self.enqueue_events_for_sse(task_id, task_update_event)

        except Exception as e:
            logger.error(f'流式响应时发生错误: {e}')
            logger.error(traceback.format_exc())

            # 向客户端报告错误
            await self.enqueue_events_for_sse(
                task_id,
                InternalError(
                    message=f'流式响应时发生错误: {e}'
                ),
            )

            # 在错误情况下清理上下文
            if session_id in self.ctx_states:
                del self.ctx_states[session_id]

    def _validate_request(
        self, request: SendTaskRequest | SendTaskStreamingRequest
    ) -> JSONRPCResponse | None:
        task_send_params: TaskSendParams = request.params
        if not utils.are_modalities_compatible(
            task_send_params.acceptedOutputModes, self.SUPPORTED_OUTPUT_TYPES
        ):
            logger.warning(
                '不支持的输出模式。收到 %s，支持 %s',
                task_send_params.acceptedOutputModes,
                self.SUPPORTED_OUTPUT_TYPES,
            )
            return utils.new_incompatible_types_error(request.id)

        if (
            task_send_params.pushNotification
            and not task_send_params.pushNotification.url
        ):
            logger.warning('推送通知URL缺失')
            return JSONRPCResponse(
                id=request.id,
                error=InvalidParamsError(
                    message='推送通知URL缺失'
                ),
            )

        return None

    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
        """Handles the 'send task' request."""
        validation_error = self._validate_request(request)
        if validation_error:
            return SendTaskResponse(id=request.id, error=validation_error.error)

        if request.params.pushNotification:
            if not await self.set_push_notification_info(
                request.params.id, request.params.pushNotification
            ):
                return SendTaskResponse(
                    id=request.id,
                    error=InvalidParamsError(
                        message='Push notification URL is invalid'
                    ),
                )

        await self.upsert_task(request.params)

        # Check if this is a continuation of an existing task that needs input
        task_id = request.params.id
        session_id = request.params.sessionId
        task = await self.update_store(
            request.params.id, TaskStatus(state=TaskState.WORKING), None
        )

        await self.send_task_notification(task)

        task_send_params: TaskSendParams = request.params
        input_event = self._get_input_event(task_send_params)

        try:
            # Check if we have a saved context for this session
            ctx = None
            saved_ctx_state = self.ctx_states.get(session_id, None)

            if saved_ctx_state:
                # Resume existing conversation
                logger.info(
                    f'Resuming existing conversation for session {session_id}'
                )
                ctx = Context.from_dict(self.agent, saved_ctx_state)
                handler = self.agent.run(
                    start_event=input_event,
                    ctx=ctx,
                )
            else:
                # New conversation
                logger.info(
                    f'Starting new conversation for session {session_id}'
                )
                handler = self.agent.run(
                    start_event=input_event,
                )

            final_response: ChatResponseEvent = await handler

            # Create artifact with response
            content = final_response.response
            parts = [{'type': 'text', 'text': content}]
            metadata = (
                final_response.citations
                if hasattr(final_response, 'citations')
                else None
            )
            if metadata is not None:
                metadata = {str(k): v for k, v in metadata.items()}

            task_status = TaskStatus(state=TaskState.COMPLETED)
            artifact = Artifact(
                parts=parts, index=0, append=False, metadata=metadata
            )
            task = await self.update_store(task_id, task_status, [artifact])
            task_result = self.append_task_history(
                task, task_send_params.historyLength
            )
            await self.send_task_notification(task)
            return SendTaskResponse(id=request.id, result=task_result)
        except Exception as e:
            logger.error(f'Error invoking agent: {e}')
            logger.error(traceback.format_exc())

            # Clean up context in case of error
            if session_id in self.ctx_states:
                del self.ctx_states[session_id]

            # Return error response
            parts = [{'type': 'text', 'text': f'Error: {e!s}'}]
            task_status = TaskStatus(
                state=TaskState.FAILED,
                message=Message(role='agent', parts=parts),
            )
            task = await self.update_store(task_id, task_status, None)
            task_result = self.append_task_history(
                task, task_send_params.historyLength
            )
            await self.send_task_notification(task)
            return SendTaskResponse(id=request.id, result=task_result)

    async def on_send_task_subscribe(
        self, request: SendTaskStreamingRequest
    ) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:
        try:
            error = self._validate_request(request)
            if error:
                return error

            await self.upsert_task(request.params)

            if request.params.pushNotification:
                if not await self.set_push_notification_info(
                    request.params.id, request.params.pushNotification
                ):
                    return JSONRPCResponse(
                        id=request.id,
                        error=InvalidParamsError(
                            message='Push notification URL is invalid'
                        ),
                    )

            task_send_params: TaskSendParams = request.params
            sse_event_queue = await self.setup_sse_consumer(
                task_send_params.id, False
            )

            asyncio.create_task(self._run_streaming_agent(request))

            return self.dequeue_events_for_sse(
                request.id, task_send_params.id, sse_event_queue
            )
        except Exception as e:
            logger.error(f'Error in SSE stream: {e}')
            logger.error(traceback.format_exc())
            return JSONRPCResponse(
                id=request.id,
                error=InternalError(
                    message='An error occurred while streaming the response'
                ),
            )

    def _get_input_event(self, task_send_params: TaskSendParams) -> InputEvent:
        """Extract file attachment if present in the message parts."""
        file_data = None
        file_name = None
        text_parts = []
        for part in task_send_params.message.parts:
            if isinstance(part, FilePart):
                file_data = part.file.bytes
                file_name = part.file.name
                if file_data is None:
                    raise ValueError('File data is missing!')
            elif isinstance(part, TextPart):
                text_parts.append(part.text)
            else:
                raise ValueError(f'Unsupported part type: {type(part)}')

        return InputEvent(
            msg='\n'.join(text_parts),
            attachment=file_data,
            file_name=file_name,
        )

    async def send_task_notification(self, task: Task):
        if not await self.has_push_notification_info(task.id):
            logger.info(f'No push notification info found for task {task.id}')
            return
        push_info = await self.get_push_notification_info(task.id)

        logger.info(f'Notifying for task {task.id} => {task.status.state}')
        await self.notification_sender_auth.send_push_notification(
            push_info.url, data=task.model_dump(exclude_none=True)
        )

    async def on_resubscribe_to_task(
        self, request
    ) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:
        task_id_params: TaskIdParams = request.params
        try:
            sse_event_queue = await self.setup_sse_consumer(
                task_id_params.id, True
            )
            return self.dequeue_events_for_sse(
                request.id, task_id_params.id, sse_event_queue
            )
        except Exception as e:
            logger.error(f'Error while reconnecting to SSE stream: {e}')
            return JSONRPCResponse(
                id=request.id,
                error=InternalError(
                    message=f'An error occurred while reconnecting to stream: {e}'
                ),
            )

    async def set_push_notification_info(
        self, task_id: str, push_notification_config: PushNotificationConfig
    ):
        # Verify the ownership of notification URL by issuing a challenge request.
        is_verified = (
            await self.notification_sender_auth.verify_push_notification_url(
                push_notification_config.url
            )
        )
        if not is_verified:
            return False

        await super().set_push_notification_info(
            task_id, push_notification_config
        )
        return True
