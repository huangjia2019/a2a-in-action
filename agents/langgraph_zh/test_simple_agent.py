"""
测试极简LangGraph汇率Agent
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入必要的模块
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from typing import TypedDict, Annotated

# 直接导入我们的Agent类
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open('02_LangGraph_Currency.py').read())


def test_agent():
    """测试Agent功能"""
    print("=== 测试极简LangGraph汇率Agent ===\n")
    
    # 创建Agent
    agent = SimpleCurrencyAgent()
    
    # 测试用例
    test_cases = [
        {
            "query": "美元兑人民币的汇率是多少？",
            "expected": "应该返回USD到CNY的汇率"
        },
        {
            "query": "欧元兑日元",
            "expected": "应该返回EUR到JPY的汇率"
        },
        {
            "query": "今天天气怎么样",
            "expected": "应该拒绝非货币查询"
        },
        {
            "query": "港币兑韩元",
            "expected": "应该返回HKD到KRW的汇率"
        },
        {
            "query": "人民币兑人民币",
            "expected": "应该拒绝相同货币查询"
        }
    ]
    
    # 运行测试
    for i, test_case in enumerate(test_cases, 1):
        print(f"--- 测试 {i}: {test_case['query']} ---")
        print(f"期望: {test_case['expected']}")
        
        try:
            result = agent.process_query(test_case['query'], f"test_session_{i}")
            
            print(f"状态: {'✅ 完成' if result['is_task_complete'] else '❌ 需要输入'}")
            print(f"响应: {result['content']}")
            
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
        
        print()


def create_workflow_diagram():
    """创建并保存工作流图"""
    print("=== 生成工作流图 ===\n")
    
    try:
        # 创建Agent实例来获取图
        agent = SimpleCurrencyAgent()
        
        # 获取图的可视化
        print("正在生成工作流图...")
        
        try:
            from IPython.display import Image, display
            
            # 使用LangGraph内置的图形可视化
            graph_image = agent.graph.get_graph().draw_mermaid_png()
            display(Image(graph_image))
            
            # 保存图片
            with open('currency_agent_workflow.png', 'wb') as f:
                f.write(graph_image)
            
            print("✅ 工作流图已保存为: currency_agent_workflow.png")
            
        except ImportError:
            print("❌ 需要安装IPython: pip install ipython")
            print("或者需要安装额外的依赖")
            
        except Exception as e:
            print(f"❌ 生成图形时出错: {str(e)}")
            print("尝试使用备用方法...")
            
            # 备用方法：直接保存
            try:
                graph_image = agent.graph.get_graph().draw_mermaid_png()
                with open('currency_agent_workflow.png', 'wb') as f:
                    f.write(graph_image)
                print("✅ 工作流图已保存为: currency_agent_workflow.png")
            except Exception as e2:
                print(f"❌ 备用方法也失败: {str(e2)}")
            
    except Exception as e:
        print(f"❌ 创建Agent时出错: {str(e)}")


def show_agent_structure():
    """显示Agent结构信息"""
    print("=== Agent结构信息 ===\n")
    
    print("📋 核心组件:")
    print("  • StateGraph: 状态图管理")
    print("  • 3个节点: process_query → get_rate → respond")
    print("  • MemorySaver: 状态持久化")
    print("  • 工具函数: get_exchange_rate")
    
    print("\n🔄 工作流程:")
    print("  1. 用户输入查询")
    print("  2. process_query: 解析货币对")
    print("  3. get_rate: 调用汇率API")
    print("  4. respond: 格式化响应")
    print("  5. 返回结果")
    
    print("\n💡 教学要点:")
    print("  • LangGraph基础概念")
    print("  • 状态管理")
    print("  • 工具集成")
    print("  • 错误处理")


def main():
    """主函数"""
    print("🚀 极简LangGraph汇率Agent测试程序\n")
    
    # 检查环境变量
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  警告: 未设置GOOGLE_API_KEY环境变量")
        print("   请设置: export GOOGLE_API_KEY='your_api_key'")
        print()
    
    # 显示Agent结构
    show_agent_structure()
    print()
    
    # 测试Agent功能
    test_agent()
    
    # 生成工作流图
    create_workflow_diagram()
    
    print("\n🎉 测试完成!")


if __name__ == "__main__":
    main() 