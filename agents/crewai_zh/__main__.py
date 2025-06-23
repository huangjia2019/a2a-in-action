"""此文件作为应用程序的主入口点。

它初始化A2A服务器，定义代理的功能，
并启动服务器来处理传入的请求。
"""

import logging
import os

import click

from agent import ImageGenerationAgent
from common.server import A2AServer
from common.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    MissingAPIKeyError,
)
from dotenv import load_dotenv
from task_manager import AgentTaskManager


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10001)
def main(host, port):
    """A2A + CrewAI图像生成示例的入口点。"""
    try:
        if not os.getenv('GOOGLE_API_KEY') and not os.getenv(
            'GOOGLE_GENAI_USE_VERTEXAI'
        ):
            raise MissingAPIKeyError(
                '未设置GOOGLE_API_KEY或Vertex AI环境变量。'
            )

        capabilities = AgentCapabilities(streaming=False)
        skill = AgentSkill(
            id='image_generator',
            name='图像生成器',
            description=(
                '按需生成令人惊叹的高质量图像，并利用'
                '强大的编辑功能来修改、增强或完全'
                '转换视觉效果。'
            ),
            tags=['生成图像', '编辑图像'],
            examples=['生成一张树莓柠檬水的超写实图像'],
        )

        agent_card = AgentCard(
            name='图像生成器代理',
            description=(
                '按需生成令人惊叹的高质量图像，并利用'
                '强大的编辑功能来修改、增强或完全'
                '转换视觉效果。'
            ),
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=ImageGenerationAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=ImageGenerationAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        server = A2AServer(
            agent_card=agent_card,
            task_manager=AgentTaskManager(agent=ImageGenerationAgent()),
            host=host,
            port=port,
        )
        logger.info(f'在 {host}:{port} 上启动服务器')
        server.start()
    except MissingAPIKeyError as e:
        logger.error(f'错误: {e}')
        exit(1)
    except Exception as e:
        logger.error(f'服务器启动期间发生错误: {e}')
        exit(1)


if __name__ == '__main__':
    main()
