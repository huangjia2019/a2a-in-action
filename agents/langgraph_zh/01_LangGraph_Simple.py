"""
极简的LangGraph Agent示例
"""

import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated
import json

# 加载环境变量
load_dotenv()

# 定义状态类型
class AgentState(TypedDict):
    messages: Annotated[list, "对话消息列表"]
    current_step: Annotated[str, "当前步骤"]

# 配置LLM
def get_llm():
    """获取LLM实例"""
    if os.getenv('GOOGLE_API_KEY'):
        return ChatGoogleGenerativeAI(
            model='gemini-2.0-flash',
            api_key=os.getenv('GOOGLE_API_KEY')
        )
    else:
        # 如果没有API密钥，使用默认配置
        return ChatGoogleGenerativeAI(model='gemini-2.0-flash')

# 定义Agent节点
def research_agent(state: AgentState) -> AgentState:
    """研究Agent - 搜索并总结AI趋势"""
    llm = get_llm()
    
    # 获取用户消息
    messages = state["messages"]
    user_message = messages[-1].content if messages else "查找并总结2025年AI领域的最新发展"
    
    # 构建系统提示
    system_prompt = """你是一位热衷于探索AI技术的专家研究员。
    你的目标是搜索并总结最新AI趋势。
    请基于用户的问题提供详细、准确的分析。"""
    
    # 创建完整的消息列表
    full_messages = [
        HumanMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ]
    
    # 获取响应
    response = llm.invoke(full_messages)
    
    # 更新状态
    state["messages"].append(response)
    state["current_step"] = "completed"
    
    return state

# 创建图
def create_graph():
    """创建LangGraph工作流"""
    # 创建内存检查点
    memory = MemorySaver()
    
    # 创建工作流图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("researcher", research_agent)
    
    # 设置入口点
    workflow.set_entry_point("researcher")
    
    # 设置结束条件
    workflow.add_edge("researcher", END)
    
    # 编译图
    app = workflow.compile(checkpointer=memory)
    
    return app

def main():
    """主函数"""
    print("=== 极简LangGraph Agent示例 ===")
    
    # 创建图
    app = create_graph()
    
    # 初始化状态
    initial_state = {
        "messages": [HumanMessage(content="查找并总结2025年AI领域的最新发展")],
        "current_step": "start"
    }
    
    # 执行工作流
    print("正在执行研究任务...")
    result = app.invoke(initial_state)
    
    # 输出结果
    print("\n=== 研究结果 ===")
    if result["messages"]:
        last_message = result["messages"][-1]
        print(last_message.content)
    
    print("\n=== 工作流完成 ===")

if __name__ == "__main__":
    main() 