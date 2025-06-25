import base64
import os

from typing import Any

from llama_cloud_services.parse import LlamaParse
from llama_index.core.llms import ChatMessage
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.llms.google_genai import GoogleGenAI
from pydantic import BaseModel, Field


## 工作流事件


class LogEvent(Event):
    msg: str


class InputEvent(StartEvent):
    msg: str
    attachment: str | None = None
    file_name: str | None = None


class ParseEvent(Event):
    attachment: str
    file_name: str
    msg: str


class ChatEvent(Event):
    msg: str


class ChatResponseEvent(StopEvent):
    response: str
    citations: dict[int, list[str]]


## 结构化输出


class Citation(BaseModel):
    """对文档中特定行的引用。"""

    citation_number: int = Field(
        description='响应文本中使用的特定内联引用编号。'
    )
    line_numbers: list[int] = Field(
        description='被引用的文档中的行号。'
    )


class ChatResponse(BaseModel):
    """对用户的响应，包含内联引用（如果有的话）。"""

    response: str = Field(
        description='对用户的响应，包括内联引用（如果有的话）。'
    )
    citations: list[Citation] = Field(
        default=list,
        description='引用列表，其中每个引用都是一个对象，用于将引用编号映射到被引用的文档中的行号。',
    )


class ParseAndChat(Workflow):
    def __init__(
        self,
        timeout: float | None = None,
        verbose: bool = False,
        **workflow_kwargs: Any,
    ):
        super().__init__(timeout=timeout, verbose=verbose, **workflow_kwargs)
        self._sllm = GoogleGenAI(
            model='gemini-2.0-flash', api_key=os.getenv('GOOGLE_API_KEY')
        ).as_structured_llm(ChatResponse)
        self._parser = LlamaParse(api_key=os.getenv('LLAMA_CLOUD_API_KEY'))
        self._system_prompt_template = """\
你是一个有用的助手，可以回答关于文档的问题，提供引用，并进行对话。

这是带有行号的文档：
<document_text>
{document_text}
</document_text>

当引用文档内容时：
1. 你的内联引用应该从[1]开始，每个额外的内联引用递增1
2. 每个引用编号应该对应文档中的特定行
3. 如果一个内联引用覆盖多个连续行，请尽量优先使用单个内联引用来覆盖所需的行号
4. 如果一个引用需要覆盖多个不连续的行，可以使用[2, 3, 4]这样的引用格式
5. 例如，如果响应包含"The transformer architecture... [1]."和"Attention mechanisms... [2]."，这些分别来自第10-12行和第45-46行，那么：citations = [[10, 11, 12], [45, 46]]
6. 始终从[1]开始你的引用，每个额外的内联引用递增1。不要使用行号作为内联引用编号，否则我会失去工作。
"""

    @step
    def route(self, ev: InputEvent) -> ParseEvent | ChatEvent:
        if ev.attachment:
            return ParseEvent(
                attachment=ev.attachment, file_name=ev.file_name, msg=ev.msg
            )
        return ChatEvent(msg=ev.msg)

    @step
    async def parse(self, ctx: Context, ev: ParseEvent) -> ChatEvent:
        ctx.write_event_to_stream(LogEvent(msg='正在解析文档...'))
        results = await self._parser.aparse(
            base64.b64decode(ev.attachment),
            extra_info={'file_name': ev.file_name},
        )
        ctx.write_event_to_stream(LogEvent(msg='文档解析成功。'))

        documents = await results.aget_markdown_documents(split_by_page=False)

        # 由于我们只有一个文档且不按页分割，我们可以直接使用第一个
        document = documents[0]

        # 将文档分割成行并添加行号
        # 这将用于引用
        document_text = ''
        for idx, line in enumerate(document.text.split('\n')):
            document_text += f"<line idx='{idx}'>{line}</line>\n"

        await ctx.set('document_text', document_text)
        return ChatEvent(msg=ev.msg)

    @step
    async def chat(self, ctx: Context, event: ChatEvent) -> ChatResponseEvent:
        current_messages = await ctx.get('messages', default=[])
        current_messages.append(ChatMessage(role='user', content=event.msg))
        ctx.write_event_to_stream(
            LogEvent(
                msg=f'正在与{len(current_messages)}条初始消息进行对话。'
            )
        )

        document_text = await ctx.get('document_text', default='')
        if document_text:
            ctx.write_event_to_stream(
                LogEvent(msg='正在插入系统提示...')
            )
            input_messages = [
                ChatMessage(
                    role='system',
                    content=self._system_prompt_template.format(
                        document_text=document_text
                    ),
                ),
                *current_messages,
            ]
        else:
            input_messages = current_messages

        response = await self._sllm.achat(input_messages)
        response_obj: ChatResponse = response.raw
        ctx.write_event_to_stream(
            LogEvent(msg='收到LLM响应，正在解析引用...')
        )

        current_messages.append(
            ChatMessage(role='assistant', content=response_obj.response)
        )
        await ctx.set('messages', current_messages)

        # 从文档文本中解析引用
        citations = {}
        if document_text:
            for citation in response_obj.citations:
                line_numbers = citation.line_numbers
                for line_number in line_numbers:
                    start_idx = document_text.find(
                        f"<line idx='{line_number}'>"
                    )
                    end_idx = document_text.find(
                        f"<line idx='{line_number + 1}'>"
                    )
                    citation_text = (
                        document_text[
                            start_idx
                            + len(f"<line idx='{line_number}'>") : end_idx
                        ]
                        .replace('</line>', '')
                        .strip()
                    )

                    if citation.citation_number not in citations:
                        citations[citation.citation_number] = []
                    citations[citation.citation_number].append(citation_text)

        return ChatResponseEvent(
            response=response_obj.response, citations=citations
        )


async def main():
    """ParseAndChat Agent的测试脚本。"""
    agent = ParseAndChat()
    ctx = Context(agent)

    # 运行 `wget https://arxiv.org/pdf/1706.03762 -O attention.pdf` 获取文件
    # 或使用你自己的文件
    with open('attention.pdf', 'rb') as f:
        attachment = f.read()

    handler = agent.run(
        start_event=InputEvent(
            msg='你好！你能告诉我关于这个文档的什么信息？',
            attachment=attachment,
            file_name='test.pdf',
        ),
        ctx=ctx,
    )

    async for event in handler:
        if not isinstance(event, StopEvent):
            print(event)

    response: ChatResponseEvent = await handler

    print(response.response)
    for citation_number, citation_texts in response.citations.items():
        print(f'引用 {citation_number}: {citation_texts}')

    # 测试上下文持久性
    handler = agent.run(
        '我上次问你什么了？',
        ctx=ctx,
    )
    response: ChatResponseEvent = await handler
    print(response.response)


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
