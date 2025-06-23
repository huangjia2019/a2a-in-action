"""
基于CrewAI的简化Agent - 图像生成功能
"""

import base64
import logging
import os
import re
from io import BytesIO
from typing import Any
from uuid import uuid4

from PIL import Image
from crewai import LLM, Agent, Crew, Task
from crewai.process import Process
from crewai.tools import tool
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageData(BaseModel):
    """图像数据模型"""
    id: str | None = None
    name: str | None = None
    mime_type: str | None = None
    bytes: str | None = None
    error: str | None = None


class SimpleImageCache:
    """简单的内存缓存"""
    def __init__(self):
        self._cache = {}
    
    def get(self, session_id: str):
        return self._cache.get(session_id, {})
    
    def set(self, session_id: str, data: dict):
        self._cache[session_id] = data


# 全局缓存实例
image_cache = SimpleImageCache()


@tool('ImageGenerationTool')
def generate_image_tool(
    prompt: str, 
    session_id: str, 
    artifact_file_id: str = ""
) -> str:
    """基于提示词生成图像的工具"""
    
    if not prompt:
        raise ValueError('提示词不能为空')

    try:
        # 初始化Google GenAI客户端
        client = genai.Client()
        
        # 准备文本输入
        text_input = (
            prompt,
            '如果输入图像与请求不匹配，请忽略任何输入图像。',
        )

        ref_image = None
        logger.info(f'会话ID: {session_id}')
        print(f'会话ID: {session_id}')

        # 尝试获取参考图像
        try:
            session_image_data = image_cache.get(session_id)
            if session_image_data:
                if artifact_file_id and artifact_file_id.strip() and artifact_file_id in session_image_data:
                    ref_image_data = session_image_data[artifact_file_id]
                    logger.info('找到参考图像')
                else:
                    # 获取最新的图像
                    latest_image_key = list(session_image_data.keys())[-1]
                    ref_image_data = session_image_data[latest_image_key]

                # 转换为PIL图像
                ref_bytes = base64.b64decode(ref_image_data.bytes)
                ref_image = Image.open(BytesIO(ref_bytes))
        except Exception as e:
            logger.info(f'没有找到参考图像: {e}')
            ref_image = None

        # 准备输入内容
        if ref_image:
            contents = [text_input, ref_image]
        else:
            contents = text_input

        # 调用Google GenAI生成图像
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=['Text', 'Image']
            ),
        )

        # 处理响应
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                # 创建图像数据
                image_data = ImageData(
                    bytes=base64.b64encode(part.inline_data.data).decode('utf-8'),
                    mime_type=part.inline_data.mime_type,
                    name='generated_image.png',
                    id=uuid4().hex,
                )
                
                # 保存到缓存
                session_data = image_cache.get(session_id)
                if session_data is None:
                    session_data = {}
                
                session_data[image_data.id] = image_data
                image_cache.set(session_id, session_data)

                logger.info(f'成功生成图像: {image_data.id}')
                return image_data.id

        logger.error('没有生成图像')
        return "生成失败"

    except Exception as e:
        logger.error(f'生成图像时出错: {e}')
        print(f'异常: {e}')
        return f"错误: {str(e)}"


class SimpleCrewAIAgent:
    """基于CrewAI的简化图像生成Agent"""
    
    def __init__(self):
        # 初始化LLM
        if os.getenv('GOOGLE_GENAI_USE_VERTEXAI'):
            self.model = LLM(model='vertex_ai/gemini-2.0-flash')
        elif os.getenv('GOOGLE_API_KEY'):
            self.model = LLM(
                model='gemini/gemini-2.0-flash',
                api_key=os.getenv('GOOGLE_API_KEY'),
            )
        else:
            # 如果没有API密钥，使用默认模型
            self.model = LLM(model='gemini/gemini-2.0-flash')
            logger.warning("未设置GOOGLE_API_KEY，使用默认配置")

        # 创建图像创作Agent
        self.image_creator_agent = Agent(
            role='图像创作专家',
            goal=(
                "基于用户的文本提示词生成图像。如果提示词模糊，请询问澄清问题。"
                "专注于解释用户的请求并有效使用图像生成器工具。"
            ),
            backstory=(
                '你是一个由AI驱动的数字艺术家。你专门从事将文本描述'
                '转换为视觉表示，使用强大的图像生成工具。你的目标'
                '是基于提供的提示词实现准确性和创造性。'
            ),
            verbose=True,  # 开启详细输出以便调试
            allow_delegation=False,
            tools=[generate_image_tool],
            llm=self.model,
        )

        # 创建图像生成任务
        self.image_creation_task = Task(
            description=(
                "接收用户提示词：'{user_prompt}'。\n"
                "分析提示词并识别是否需要创建新图像或编辑现有图像。"
                "在提示词中查找代词如这个、那个等，它们可能提供上下文。"
                "使用图像生成器工具进行图像创建或修改。"
                "工具需要提示词：{user_prompt}，会话ID：{session_id}。"
                "如果提供了artifact_file_id：{artifact_file_id}，请使用它。"
            ),
            expected_output='生成图像的ID',
            agent=self.image_creator_agent,
        )

        # 创建Crew
        self.image_crew = Crew(
            agents=[self.image_creator_agent],
            tasks=[self.image_creation_task],
            process=Process.sequential,
            verbose=True,  # 开启详细输出
        )

    def extract_artifact_file_id(self, query: str) -> str | None:
        """从查询中提取artifact_file_id"""
        try:
            pattern = r'(?:id|artifact-file-id)\s+([0-9a-f]{32})'
            match = re.search(pattern, query)
            return match.group(1) if match else None
        except Exception:
            return None

    def generate_image(self, prompt: str, session_id: str = None) -> str:
        """生成图像的主方法"""
        
        if not session_id:
            session_id = uuid4().hex
        
        # 提取artifact_file_id
        artifact_file_id = self.extract_artifact_file_id(prompt)
        
        # 准备输入
        inputs = {
            'user_prompt': prompt,
            'session_id': session_id,
            'artifact_file_id': artifact_file_id or '',
        }
        
        logger.info(f'开始生成图像，输入: {inputs}')
        print(f'开始生成图像，输入: {inputs}')
        
        try:
            # 启动CrewAI
            response = self.image_crew.kickoff(inputs)
            logger.info(f'图像生成完成，响应: {response}')
            return response
        except Exception as e:
            logger.error(f'生成图像时出错: {e}')
            return f"错误: {str(e)}"

    def get_image_data(self, session_id: str, image_id: str) -> ImageData:
        """获取图像数据"""
        try:
            session_data = image_cache.get(session_id)
            if session_data and image_id in session_data:
                return session_data[image_id]
            else:
                return ImageData(error='图像未找到')
        except Exception as e:
            logger.error(f'获取图像数据时出错: {e}')
            return ImageData(error=f'获取图像数据时出错: {str(e)}')

    def save_image_to_file(self, session_id: str, image_id: str, filepath: str = None) -> str:
        """将图像保存到文件"""
        try:
            image_data = self.get_image_data(session_id, image_id)
            if image_data.error:
                return f"错误: {image_data.error}"
            
            # 如果没有指定文件路径，使用默认路径
            if not filepath:
                import os
                os.makedirs("generated_images", exist_ok=True)
                filepath = f"generated_images/{image_id}.png"
            
            # 解码Base64数据并保存
            import base64
            image_bytes = base64.b64decode(image_data.bytes)
            
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            
            logger.info(f'图像已保存到: {filepath}')
            return f"图像已保存到: {filepath}"
            
        except Exception as e:
            logger.error(f'保存图像时出错: {e}')
            return f"保存图像时出错: {str(e)}"


# 使用示例
def main():
    """主函数示例"""
    print("=== CrewAI图像生成Agent示例 ===\n")
    
    # 创建Agent实例
    agent = SimpleCrewAIAgent()
    
    # 测试图像生成
    test_prompt = "一只可爱的小猫坐在花园里，阳光明媚"
    session_id = "test_session_123"
    
    print(f"提示词: {test_prompt}")
    print(f"会话ID: {session_id}")
    print("\n开始生成图像...")
    
    # 生成图像
    result = agent.generate_image(test_prompt, session_id)
    print(f"\n生成结果: {result}")
    
    # 处理CrewAI返回的结果
    # CrewAI返回的是CrewOutput对象，需要转换为字符串
    if hasattr(result, 'raw'):
        # 如果是CrewOutput对象，获取原始输出
        result_str = str(result.raw)
    else:
        # 如果是字符串，直接使用
        result_str = str(result)
    
    print(f"处理后的结果: {result_str}")
    
    # 如果成功生成，获取图像数据
    if result_str and not result_str.startswith("错误"):
        print(f"\n获取图像数据...")
        image_data = agent.get_image_data(session_id, result_str)
        if image_data.error:
            print(f"获取图像数据失败: {image_data.error}")
        else:
            print(f"图像数据获取成功:")
            print(f"  ID: {image_data.id}")
            print(f"  名称: {image_data.name}")
            print(f"  MIME类型: {image_data.mime_type}")
            print(f"  数据大小: {len(image_data.bytes) if image_data.bytes else 0} 字节")
            
            # 保存图片到文件
            print(f"\n保存图片到文件...")
            save_result = agent.save_image_to_file(session_id, result_str)
            print(f"保存结果: {save_result}")
    else:
        print(f"图像生成失败或返回错误: {result_str}")


if __name__ == "__main__":
    main() 