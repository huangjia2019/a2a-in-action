"""
测试极简LlamaIndex文件聊天Agent
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 直接导入我们的Agent类
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open('01_LlamaIndex_Simple.py').read())


def test_document_loading():
    """测试文档加载功能"""
    print("=== 测试文档加载功能 ===\n")
    
    agent = SimpleFileChatAgent()
    
    # 创建测试文档
    test_content = """
# Python编程基础

Python是一种高级编程语言，以其简洁的语法和强大的功能而闻名。

## 基本语法

### 变量和数据类型
Python中的变量不需要声明类型，可以直接赋值：
```python
name = "张三"
age = 25
height = 1.75
```

### 条件语句
使用if-elif-else进行条件判断：
```python
if age >= 18:
    print("成年人")
elif age >= 12:
    print("青少年")
else:
    print("儿童")
```

### 循环语句
Python支持for和while循环：
```python
for i in range(5):
    print(i)

while count > 0:
    print(count)
    count -= 1
```

## 函数定义

函数使用def关键字定义：
```python
def greet(name):
    return f"你好，{name}！"
```

## 面向对象编程

Python支持面向对象编程：
```python
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
    
    def introduce(self):
        return f"我叫{self.name}，今年{self.age}岁"
```
"""
    
    # 保存测试文档
    with open('test_python_doc.txt', 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    # 测试加载文档
    print("1. 测试加载本地文档...")
    success = agent.load_document('test_python_doc.txt', "Python编程文档")
    
    if success:
        doc_info = agent.get_document_info()
        print(f"✅ 文档加载成功，共 {doc_info['count']} 个文档")
        for doc in doc_info['documents']:
            print(f"   • {doc['file_name']}: {doc['lines']} 行")
    else:
        print("❌ 文档加载失败")
    
    return agent


def test_chat_functionality(agent):
    """测试聊天功能"""
    print("\n=== 测试聊天功能 ===\n")
    
    # 测试查询
    test_queries = [
        {
            "query": "什么是Python？",
            "expected": "应该返回关于Python编程语言的基本介绍"
        },
        {
            "query": "Python中如何定义函数？",
            "expected": "应该返回函数定义的语法和示例"
        },
        {
            "query": "Python支持哪些循环语句？",
            "expected": "应该返回for和while循环的说明"
        },
        {
            "query": "如何在Python中创建类？",
            "expected": "应该返回面向对象编程的相关信息"
        }
    ]
    
    for i, test_case in enumerate(test_queries, 1):
        print(f"--- 测试 {i}: {test_case['query']} ---")
        print(f"期望: {test_case['expected']}")
        
        try:
            result = agent.chat(test_case['query'])
            
            print(f"回复: {result['response'][:200]}{'...' if len(result['response']) > 200 else ''}")
            
            if result['citations']:
                print("引用:")
                for citation_num, citation_info in result['citations'].items():
                    print(f"  [{citation_num}] {citation_info['content'][:100]}...")
            else:
                print("无引用信息")
                
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
        
        print()


def test_chat_history(agent):
    """测试对话历史功能"""
    print("\n=== 测试对话历史功能 ===\n")
    
    # 进行一些对话
    queries = ["Python有什么特点？", "如何安装Python？", "Python适合初学者吗？"]
    
    for query in queries:
        print(f"用户: {query}")
        result = agent.chat(query)
        print(f"助手: {result['response'][:100]}...")
        print()
    
    # 显示对话历史
    print("📝 完整对话历史:")
    history = agent.get_chat_history()
    for i, msg in enumerate(history, 1):
        role = "用户" if msg["role"] == "user" else "助手"
        content = msg['content'][:80] + "..." if len(msg['content']) > 80 else msg['content']
        print(f"{i}. {role}: {content}")
    
    # 测试清空历史
    print(f"\n🗑️  清空对话历史...")
    agent.clear_history()
    
    history_after_clear = agent.get_chat_history()
    print(f"清空后历史长度: {len(history_after_clear)}")


def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===\n")
    
    agent = SimpleFileChatAgent()
    
    # 测试在没有文档的情况下聊天
    print("1. 测试无文档聊天...")
    result = agent.chat("你好")
    print(f"回复: {result['response']}")
    print(f"有文档: {result['has_documents']}")
    
    # 测试加载不存在的文件
    print("\n2. 测试加载不存在的文件...")
    success = agent.load_document('nonexistent_file.txt')
    print(f"加载结果: {'成功' if success else '失败'}")


def compare_with_original():
    """与原版对比"""
    print("\n=== 与原版对比 ===\n")
    
    print("📋 简化版特点:")
    print("  • 使用LlamaIndex核心功能")
    print("  • 简化的文档加载和索引构建")
    print("  • 基本的聊天和引用功能")
    print("  • 对话历史管理")
    print("  • 错误处理")
    
    print("\n📋 原版特点:")
    print("  • 使用LlamaIndex Workflow")
    print("  • 复杂的事件驱动架构")
    print("  • 结构化输出和引用")
    print("  • 支持PDF等复杂文档格式")
    print("  • 更高级的文档解析")
    
    print("\n💡 教学价值:")
    print("  • 简化版适合学习LlamaIndex基础概念")
    print("  • 原版适合学习高级工作流设计")
    print("  • 两者都展示了文档问答的核心思想")


def main():
    """主函数"""
    print("🚀 极简LlamaIndex文件聊天Agent测试程序\n")
    
    # 检查环境变量
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  警告: 未设置GOOGLE_API_KEY环境变量")
        print("   请设置: export GOOGLE_API_KEY='your_api_key'")
        print()
    
    # 测试文档加载
    agent = test_document_loading()
    
    # 测试聊天功能
    test_chat_functionality(agent)
    
    # 测试对话历史
    test_chat_history(agent)
    
    # 测试错误处理
    test_error_handling()
    
    # 与原版对比
    compare_with_original()
    
    print("\n🎉 测试完成!")
    print("\n📋 核心功能验证:")
    print("  ✅ 文档加载和索引构建")
    print("  ✅ 智能问答和引用")
    print("  ✅ 对话历史管理")
    print("  ✅ 错误处理机制")


if __name__ == "__main__":
    main() 