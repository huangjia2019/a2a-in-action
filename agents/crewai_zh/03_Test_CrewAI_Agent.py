"""
测试CrewAI Agent的图像生成功能
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from demo.crewai_agent import SimpleCrewAIAgent


def test_agent_initialization():
    """测试Agent初始化"""
    print("=== 测试Agent初始化 ===")
    
    try:
        agent = SimpleCrewAIAgent()
        print("✅ Agent初始化成功")
        print(f"  Agent角色: {agent.image_creator_agent.role}")
        print(f"  Agent目标: {agent.image_creator_agent.goal}")
        print(f"  可用工具数量: {len(agent.image_creator_agent.tools)}")
        return agent
    except Exception as e:
        print(f"❌ Agent初始化失败: {e}")
        return None


def test_image_generation(agent):
    """测试图像生成功能"""
    print("\n=== 测试图像生成 ===")
    
    if not agent:
        print("❌ Agent未初始化，跳过测试")
        return
    
    # 测试提示词
    test_prompts = [
        "一只可爱的小猫坐在花园里，阳光明媚",
        "一个现代化的城市夜景，霓虹灯闪烁",
        "一朵红色的玫瑰在雨中绽放"
    ]
    
    session_id = "test_session_456"
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n--- 测试 {i}: {prompt} ---")
        
        try:
            # 生成图像
            result = agent.generate_image(prompt, session_id)
            print(f"生成结果: {result}")
            
            # 检查结果
            if result and not result.startswith("错误"):
                print("✅ 图像生成成功")
                
                # 获取图像数据
                image_data = agent.get_image_data(session_id, result)
                if image_data.error:
                    print(f"❌ 获取图像数据失败: {image_data.error}")
                else:
                    print("✅ 图像数据获取成功")
                    print(f"  图像ID: {image_data.id}")
                    print(f"  图像名称: {image_data.name}")
                    print(f"  MIME类型: {image_data.mime_type}")
                    print(f"  数据大小: {len(image_data.bytes) if image_data.bytes else 0} 字节")
            else:
                print(f"❌ 图像生成失败: {result}")
                
        except Exception as e:
            print(f"❌ 测试过程中出错: {e}")


def test_artifact_file_id_extraction(agent):
    """测试artifact_file_id提取功能"""
    print("\n=== 测试artifact_file_id提取 ===")
    
    if not agent:
        print("❌ Agent未初始化，跳过测试")
        return
    
    test_queries = [
        "修改这个图像 id abc123456789012345678901234567890",
        "基于这个图片 artifact-file-id def123456789012345678901234567890 生成新版本",
        "简单的图像生成请求",
        "id 12345678901234567890123456789012 修改为蓝色",
    ]
    
    for query in test_queries:
        artifact_id = agent.extract_artifact_file_id(query)
        print(f"查询: {query}")
        print(f"提取的ID: {artifact_id}")
        print()


def test_error_handling(agent):
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    if not agent:
        print("❌ Agent未初始化，跳过测试")
        return
    
    # 测试空提示词
    print("测试空提示词...")
    try:
        result = agent.generate_image("", "error_test_session")
        print(f"空提示词结果: {result}")
    except Exception as e:
        print(f"空提示词错误: {e}")
    
    # 测试获取不存在的图像
    print("\n测试获取不存在的图像...")
    try:
        image_data = agent.get_image_data("nonexistent_session", "nonexistent_id")
        print(f"不存在图像结果: {image_data.error}")
    except Exception as e:
        print(f"获取不存在图像错误: {e}")


def main():
    """主测试函数"""
    print("开始测试CrewAI图像生成Agent...\n")
    
    # 检查环境变量
    print("检查环境变量...")
    api_key = os.getenv('GOOGLE_API_KEY')
    if api_key:
        print("✅ GOOGLE_API_KEY 已设置")
    else:
        print("⚠️  GOOGLE_API_KEY 未设置，将使用默认配置")
    
    vertex_ai = os.getenv('GOOGLE_GENAI_USE_VERTEXAI')
    if vertex_ai:
        print("✅ GOOGLE_GENAI_USE_VERTEXAI 已设置")
    else:
        print("ℹ️  GOOGLE_GENAI_USE_VERTEXAI 未设置")
    
    print()
    
    try:
        # 初始化Agent
        agent = test_agent_initialization()
        
        # 测试各种功能
        test_artifact_file_id_extraction(agent)
        test_error_handling(agent)
        
        # 注意：实际的图像生成需要API密钥，这里只做基本测试
        if api_key:
            test_image_generation(agent)
        else:
            print("\n⚠️  跳过图像生成测试（需要GOOGLE_API_KEY）")
            print("要测试图像生成，请设置GOOGLE_API_KEY环境变量")
        
        print("\n✅ 所有测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 