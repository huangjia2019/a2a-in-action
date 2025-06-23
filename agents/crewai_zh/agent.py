"""基于CrewAI的A2A协议示例。

处理Agent并提供所需的工具。
"""

import base64
import logging
import os
import re

from collections.abc import AsyncIterable
from io import BytesIO
from typing import Any
from uuid import uuid4

from PIL import Image
from common.utils.in_memory_cache import InMemoryCache
from crewai import LLM, Agent, Crew, Task
from crewai.process import Process
from crewai.tools import tool
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel


load_dotenv()

logger = logging.getLogger(__name__)


class Imagedata(BaseModel):
    """表示图像数据。

    属性:
      id: 图像的唯一标识符。
      name: 图像名称。
      mime_type: 图像的MIME类型。
      bytes: Base64编码的图像数据。
      error: 如果图像处理出现问题时的错误消息。
    """

    id: str | None = None
    name: str | None = None
    mime_type: str | None = None
    bytes: str | None = None
    error: str | None = None


@tool('ImageGenerationTool')
def generate_image_tool(
    prompt: str, session_id: str, artifact_file_id: str = None
) -> str:
    """基于提示词生成图像或修改给定图像的图像生成工具。"""
    if not prompt:
        raise ValueError('提示词不能为空')

    client = genai.Client()
    cache = InMemoryCache()

    text_input = (
        prompt,
        '如果输入图像与请求不匹配，请忽略任何输入图像。',
    )

    ref_image = None
    logger.info(f'会话ID {session_id}')
    print(f'会话ID {session_id}')

    # TODO (rvelicheti) - 将复杂的内存处理逻辑改为更好的版本。
    # 从缓存中获取图像并将其发送回模型。
    # 假设生成的图像的最后一个版本是适用的。
    # 转换为PIL图像，这样发送给LLM的上下文不会过载
    try:
        ref_image_data = None
        # image_id = session_cache[session_id][-1]
        session_image_data = cache.get(session_id)
        if artifact_file_id:
            try:
                ref_image_data = session_image_data[artifact_file_id]
                logger.info('在提示输入中找到参考图像')
            except Exception:
                ref_image_data = None
        if not ref_image_data:
            # 从python 3.7开始保持插入顺序
            latest_image_key = list(session_image_data.keys())[-1]
            ref_image_data = session_image_data[latest_image_key]

        ref_bytes = base64.b64decode(ref_image_data.bytes)
        ref_image = Image.open(BytesIO(ref_bytes))
    except Exception:
        ref_image = None

    if ref_image:
        contents = [text_input, ref_image]
    else:
        contents = text_input

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=['Text', 'Image']
            ),
        )
    except Exception as e:
        logger.error(f'生成图像时出错 {e}')
        print(f'异常 {e}')
        return -999999999

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            try:
                data = Imagedata(
                    bytes=base64.b64encode(part.inline_data.data).decode(
                        'utf-8'
                    ),
                    mime_type=part.inline_data.mime_type,
                    name='generated_image.png',
                    id=uuid4().hex,
                )
                session_data = cache.get(session_id)
                if session_data is None:
                    # 会话不存在，创建新项目
                    cache.set(session_id, {data.id: data})
                else:
                    # 会话存在，直接更新现有字典
                    session_data[data.id] = data

                return data.id
            except Exception as e:
                logger.error(f'解包图像时出错 {e}')
                print(f'异常 {e}')
    return -999999999


class ImageGenerationAgent:
    """基于用户提示词生成图像的Agent。"""

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain', 'image/png']

    def __init__(self):
        if os.getenv('GOOGLE_GENAI_USE_VERTEXAI'):
            self.model = LLM(model='vertex_ai/gemini-2.0-flash')
        elif os.getenv('GOOGLE_API_KEY'):
            self.model = LLM(
                model='gemini/gemini-2.0-flash',
                api_key=os.getenv('GOOGLE_API_KEY'),
            )

        self.image_creator_agent = Agent(
            role='图像创作专家',
            goal=(
                "基于用户的文本提示词生成图像。如果提示词模糊，请询问澄清问题"
                "（虽然工具目前在一次运行中不支持来回对话）。专注于"
                "解释用户的请求并有效使用图像生成器工具。"
            ),
            backstory=(
                '你是一个由AI驱动的数字艺术家。你专门从事将文本描述'
                '转换为视觉表示，使用强大的图像生成工具。你的目标'
                '是基于提供的提示词实现准确性和创造性。'
            ),
            verbose=False,
            allow_delegation=False,
            tools=[generate_image_tool],
            llm=self.model,
        )

        self.image_creation_task = Task(
            description=(
                "接收用户提示词：'{user_prompt}'。\n分析提示词并"
                '识别是否需要创建新图像或编辑现有图像。在提示词中查找'
                '代词如这个、那个等，它们可能提供上下文，重写提示词'
                '以包含上下文。如果创建新图像，忽略作为输入上下文'
                '提供的任何图像。使用"图像生成器"工具进行图像'
                '创建或修改。工具将期望一个提示词，即{user_prompt}，'
                '以及session_id，即{session_id}。'
                '可选地，工具还将期望一个artifact_file_id，'
                '即发送给你的{artifact_file_id}'
            ),
            expected_output='生成图像的ID',
            agent=self.image_creator_agent,
        )

        self.image_crew = Crew(
            agents=[self.image_creator_agent],
            tasks=[self.image_creation_task],
            process=Process.sequential,
            verbose=False,
        )

    def extract_artifact_file_id(self, query):
        try:
            pattern = r'(?:id|artifact-file-id)\s+([0-9a-f]{32})'
            match = re.search(pattern, query)

            if match:
                return match.group(1)
            return None
        except Exception:
            return None

    def invoke(self, query, session_id) -> str:
        """启动CrewAI并返回响应。"""
        artifact_file_id = self.extract_artifact_file_id(query)

        inputs = {
            'user_prompt': query,
            'session_id': session_id,
            'artifact_file_id': artifact_file_id,
        }
        logger.info(f'输入 {inputs}')
        print(f'输入 {inputs}')
        response = self.image_crew.kickoff(inputs)
        return response

    async def stream(self, query: str) -> AsyncIterable[dict[str, Any]]:
        """CrewAI不支持流式传输。"""
        raise NotImplementedError('CrewAI不支持流式传输。')

    def get_image_data(self, session_id: str, image_key: str) -> Imagedata:
        """给定键返回Imagedata。这是来自Agent的辅助方法。"""
        cache = InMemoryCache()
        session_data = cache.get(session_id)
        try:
            cache.get(session_id)
            return session_data[image_key]
        except KeyError:
            logger.error('生成图像时出错')
            return Imagedata(error='生成图像时出错，请重试。')
