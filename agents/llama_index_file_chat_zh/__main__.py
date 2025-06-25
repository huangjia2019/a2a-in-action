import logging
import os

import click

from agents.llama_index_file_chat.agent import ParseAndChat
from agents.llama_index_file_chat.task_manager import LlamaIndexTaskManager
from common.server import A2AServer
from common.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    MissingAPIKeyError,
)
from common.utils.push_notification_auth import PushNotificationSenderAuth
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10010)
def main(host, port):
    """启动文档解析和聊天Agent服务器。"""
    try:
        if not os.getenv('GOOGLE_API_KEY'):
            raise MissingAPIKeyError(
                '未设置GOOGLE_API_KEY环境变量。'
            )
        if not os.getenv('LLAMA_CLOUD_API_KEY'):
            raise MissingAPIKeyError(
                '未设置LLAMA_CLOUD_API_KEY环境变量。'
            )

        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)

        skill = AgentSkill(
            id='parse_and_chat',
            name='文档解析和聊天',
            description='解析文件，然后使用解析的内容作为上下文与用户聊天。',
            tags=['解析', '聊天', '文件', 'llama_parse'],
            examples=['这个文件讲了什么？'],
        )

        agent_card = AgentCard(
            name='文档解析和聊天Agent',
            description='解析文件，然后使用解析的内容作为上下文与用户聊天。',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=LlamaIndexTaskManager.SUPPORTED_INPUT_TYPES,
            defaultOutputModes=LlamaIndexTaskManager.SUPPORTED_OUTPUT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        notification_sender_auth = PushNotificationSenderAuth()
        notification_sender_auth.generate_jwk()
        server = A2AServer(
            agent_card=agent_card,
            task_manager=LlamaIndexTaskManager(
                agent=ParseAndChat(),
                notification_sender_auth=notification_sender_auth,
            ),
            host=host,
            port=port,
        )

        server.app.add_route(
            '/.well-known/jwks.json',
            notification_sender_auth.handle_jwks_endpoint,
            methods=['GET'],
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
