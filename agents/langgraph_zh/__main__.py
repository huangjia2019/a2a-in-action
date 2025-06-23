import logging
import os

import click

from agents.langgraph.agent import CurrencyAgent
from agents.langgraph.task_manager import AgentTaskManager
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
@click.option('--port', 'port', default=10000)
def main(host, port):
    """启动货币Agent服务器。"""
    try:
        if not os.getenv('GOOGLE_API_KEY'):
            raise MissingAPIKeyError(
                '未设置GOOGLE_API_KEY环境变量。'
            )

        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        skill = AgentSkill(
            id='convert_currency',
            name='货币汇率转换工具',
            description='帮助在各种货币之间进行汇率转换',
            tags=['货币转换', '汇率查询'],
            examples=['USD和GBP之间的汇率是多少？'],
        )
        agent_card = AgentCard(
            name='货币Agent',
            description='帮助查询各种货币的汇率',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            defaultInputModes=CurrencyAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=CurrencyAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        notification_sender_auth = PushNotificationSenderAuth()
        notification_sender_auth.generate_jwk()
        server = A2AServer(
            agent_card=agent_card,
            task_manager=AgentTaskManager(
                agent=CurrencyAgent(),
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
