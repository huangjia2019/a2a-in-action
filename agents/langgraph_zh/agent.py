from collections.abc import AsyncIterable
from typing import Any, Literal

import httpx

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent


memory = MemorySaver()


@tool
def get_exchange_rate(
    currency_from: str = 'USD',
    currency_to: str = 'EUR',
    currency_date: str = 'latest',
):
    """使用此工具获取当前汇率。

    参数:
        currency_from: 要转换的货币（例如，"USD"）。
        currency_to: 要转换到的货币（例如，"EUR"）。
        currency_date: 汇率的日期或"latest"。默认为"latest"。

    返回:
        包含汇率数据的字典，如果请求失败则返回错误消息。
    """
    try:
        response = httpx.get(
            f'https://api.frankfurter.app/{currency_date}',
            params={'from': currency_from, 'to': currency_to},
        )
        response.raise_for_status()

        data = response.json()
        if 'rates' not in data:
            return {'error': 'API响应格式无效。'}
        return data
    except httpx.HTTPError as e:
        return {'error': f'API请求失败: {e}'}
    except ValueError:
        return {'error': 'API返回的JSON响应无效。'}


class ResponseFormat(BaseModel):
    """以这种格式响应用户。"""

    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    message: str


class CurrencyAgent:
    SYSTEM_INSTRUCTION = (
        '你是专门进行货币转换的助手。'
        "你的唯一目的是使用'get_exchange_rate'工具来回答有关汇率的问题。"
        '如果用户询问除货币转换或汇率之外的任何内容，'
        '请礼貌地说明你无法帮助该主题，只能协助货币相关的查询。'
        '不要尝试回答不相关的问题或将工具用于其他目的。'
        '如果用户需要提供更多信息，请将响应状态设置为input_required。'
        '如果在处理请求时出现错误，请将响应状态设置为error。'
        '如果请求完成，请将响应状态设置为completed。'
    )

    def __init__(self):
        self.model = ChatGoogleGenerativeAI(model='gemini-2.0-flash')
        self.tools = [get_exchange_rate]

        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat,
        )

    def invoke(self, query, sessionId) -> str:
        config = {'configurable': {'thread_id': sessionId}}
        self.graph.invoke({'messages': [('user', query)]}, config)
        return self.get_agent_response(config)

    async def stream(self, query, sessionId) -> AsyncIterable[dict[str, Any]]:
        inputs = {'messages': [('user', query)]}
        config = {'configurable': {'thread_id': sessionId}}

        for item in self.graph.stream(inputs, config, stream_mode='values'):
            message = item['messages'][-1]
            if (
                isinstance(message, AIMessage)
                and message.tool_calls
                and len(message.tool_calls) > 0
            ):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': '正在查询汇率...',
                }
            elif isinstance(message, ToolMessage):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': '正在处理汇率数据...',
                }

        yield self.get_agent_response(config)

    def get_agent_response(self, config):
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get('structured_response')
        if structured_response and isinstance(
            structured_response, ResponseFormat
        ):
            if (
                structured_response.status == 'input_required'
                or structured_response.status == 'error'
            ):
                return {
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': structured_response.message,
                }
            if structured_response.status == 'completed':
                return {
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': structured_response.message,
                }

        return {
            'is_task_complete': False,
            'require_user_input': True,
            'content': '我们目前无法处理您的请求。请重试。',
        }

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']
