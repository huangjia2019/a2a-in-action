"""
测试v3版本智能回复功能
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 直接导入我们的Agent类
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open('02_LangGraph_Currency-v3-智能回复.py').read())


def test_smart_responses():
    """测试智能回复功能"""
    print("=== 测试v3版本智能回复功能 ===\n")
    
    # 创建Agent
    agent = SimpleCurrencyAgent()
    
    # 测试用例 - 涵盖不同类型的查询
    test_cases = [
        {
            "query": "美元兑人民币的汇率是多少？",
            "type": "正常汇率查询",
            "expected": "应该返回智能格式化的汇率信息"
        },
        {
            "query": "欧元兑日元",
            "type": "简单汇率查询",
            "expected": "应该返回智能格式化的汇率信息"
        },
        {
            "query": "今天天气怎么样",
            "type": "不相关查询",
            "expected": "应该返回友好的拒绝回复"
        },
        {
            "query": "帮我写一个Python程序",
            "type": "编程相关查询",
            "expected": "应该返回友好的拒绝回复"
        },
        {
            "query": "人民币兑人民币",
            "type": "相同货币查询",
            "expected": "应该返回智能的错误回复"
        },
        {
            "query": "港币兑韩元",
            "type": "其他货币对查询",
            "expected": "应该返回智能格式化的汇率信息"
        }
    ]
    
    # 运行测试
    for i, test_case in enumerate(test_cases, 1):
        print(f"--- 测试 {i}: {test_case['type']} ---")
        print(f"查询: {test_case['query']}")
        print(f"期望: {test_case['expected']}")
        
        try:
            result = agent.process_query(test_case['query'], f"v3_test_session_{i}")
            
            print(f"状态: {'✅ 完成' if result['is_task_complete'] else '❌ 需要输入'}")
            print(f"智能回复:\n{result['content']}")
            
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
        
        print("-" * 60)


def compare_responses():
    """比较v2和v3版本的回复差异"""
    print("\n=== 比较v2和v3版本回复差异 ===\n")
    
    # 导入v2版本
    exec(open('02_LangGraph_Currency-v2-意图识别.py').read())
    agent_v2 = SimpleCurrencyAgent()
    
    # 导入v3版本
    exec(open('02_LangGraph_Currency-v3-智能回复.py').read())
    agent_v3 = SimpleCurrencyAgent()
    
    # 测试查询
    test_query = "美元兑人民币的汇率是多少？"
    
    print(f"测试查询: {test_query}\n")
    
    # v2版本回复
    print("--- v2版本回复 (模板化) ---")
    result_v2 = agent_v2.process_query(test_query, "v2_session")
    print(result_v2['content'])
    
    print("\n--- v3版本回复 (智能化) ---")
    result_v3 = agent_v3.process_query(test_query, "v3_session")
    print(result_v3['content'])
    
    print("\n--- 差异分析 ---")
    print("v2版本: 使用固定模板，回复简洁但缺乏个性化")
    print("v3版本: 使用LLM生成，回复更自然、详细、个性化")


def test_error_handling():
    """测试错误处理的智能回复"""
    print("\n=== 测试错误处理智能回复 ===\n")
    
    agent = SimpleCurrencyAgent()
    
    # 测试相同货币查询的错误处理
    error_cases = [
        {
            "query": "人民币兑人民币",
            "description": "相同货币查询"
        },
        {
            "query": "美元兑美元",
            "description": "相同货币查询"
        }
    ]
    
    for i, case in enumerate(error_cases, 1):
        print(f"--- 错误处理测试 {i}: {case['description']} ---")
        print(f"查询: {case['query']}")
        
        try:
            result = agent.process_query(case['query'], f"error_test_{i}")
            
            print(f"智能错误回复:\n{result['content']}")
            
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
        
        print("-" * 60)


def main():
    """主函数"""
    print("🚀 v3版本智能回复测试程序\n")
    
    # 检查环境变量
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  警告: 未设置GOOGLE_API_KEY环境变量")
        print("   请设置: export GOOGLE_API_KEY='your_api_key'")
        print()
    
    # 测试智能回复功能
    test_smart_responses()
    
    # 比较版本差异
    compare_responses()
    
    # 测试错误处理
    test_error_handling()
    
    print("\n🎉 v3版本测试完成!")
    print("\n📋 v3版本主要改进:")
    print("  • 使用LLM生成智能回复")
    print("  • 更自然、个性化的回复")
    print("  • 更好的错误处理和用户引导")
    print("  • 保持专业但友好的语调")


if __name__ == "__main__":
    main() 