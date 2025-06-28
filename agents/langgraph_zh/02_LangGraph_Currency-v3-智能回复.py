"""
极简版LangGraph汇率Agent - 教学演示
"""

import os
import httpx
from typing import TypedDict, Annotated
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# 加载环境变量
load_dotenv()


class CurrencyState(TypedDict):
    """汇率转换状态"""
    messages: Annotated[list, "对话消息列表"]
    exchange_data: Annotated[dict, "汇率数据"]


@tool
def get_exchange_rate(currency_from: str = 'USD', currency_to: str = 'CNY') -> dict:
    """获取汇率信息
    
    参数:
        currency_from: 源货币代码 (例如: "USD", "CNY")
        currency_to: 目标货币代码 (例如: "EUR", "JPY") 
    
    返回:
        包含汇率数据的字典
    """
    try:
        response = httpx.get(
            f'https://api.frankfurter.app/latest',
            params={'from': currency_from, 'to': currency_to},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {'error': f'获取汇率失败: {e}'}


class SimpleCurrencyAgent:
    """极简汇率Agent"""
    
    def __init__(self):
        """初始化Agent"""
        # 配置LLM
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.0-flash',
            api_key=os.getenv('GOOGLE_API_KEY')
        )
        
        # 创建图
        self.graph = self._create_graph()
    
    def _create_graph(self):
        """创建LangGraph工作流"""
        # 创建内存检查点
        memory = MemorySaver()
        
        # 创建工作流图
        workflow = StateGraph(CurrencyState)
        
        # 添加节点
        workflow.add_node("process_query", self._process_query)
        workflow.add_node("get_rate", self._get_rate)
        workflow.add_node("respond", self._respond)
        workflow.add_node("respond_irrelevant", self._respond_irrelevant)
        
        # 设置入口点
        workflow.set_entry_point("process_query")
        
        # 添加条件边
        workflow.add_conditional_edges(
            "process_query",
            self._should_get_rate,
            {
                "get_rate": "get_rate",
                "respond_irrelevant": "respond_irrelevant"
            }
        )
        
        # 添加普通边
        workflow.add_edge("get_rate", "respond")
        workflow.add_edge("respond", END)
        workflow.add_edge("respond_irrelevant", END)
        
        # 编译图
        return workflow.compile(checkpointer=memory)
    
    def _should_get_rate(self, state: CurrencyState) -> str:
        """判断是否应该获取汇率"""
        exchange_data = state["exchange_data"]
        return "get_rate" if exchange_data.get("is_currency_query", False) else "respond_irrelevant"
    
    def _process_query(self, state: CurrencyState) -> CurrencyState:
        """处理用户查询 - 使用LLM判断相关性"""
        # 获取用户消息
        user_message = state["messages"][-1].content
        
        # 使用LLM判断查询是否与货币/汇率相关
        prompt = f"""
        请判断以下用户查询是否与货币转换、汇率查询相关。
        
        用户查询: "{user_message}"
        
        请只回答 "是" 或 "否"。
        
        相关查询示例:
        - 美元兑人民币汇率
        - 欧元换日元
        - 港币汇率
        - 人民币兑美元
        
        不相关查询示例:
        - 今天天气怎么样
        - 帮我写代码
        - 什么是人工智能
        - 推荐餐厅
        """
        
        try:
            # 调用LLM判断
            response = self.llm.invoke(prompt)
            is_currency_query = "是" in response.content.strip()
            
            if is_currency_query:
                # 货币查询处理
                currencies = {
                    '美元': 'USD', '人民币': 'CNY', '欧元': 'EUR', '日元': 'JPY',
                    '英镑': 'GBP', '澳元': 'AUD', '港币': 'HKD', '韩元': 'KRW'
                }
                
                found_currencies = []
                for cn_name, code in currencies.items():
                    if cn_name in user_message:
                        found_currencies.append(code)
                
                # 设置默认货币对
                if len(found_currencies) >= 2:
                    from_currency = found_currencies[0]
                    to_currency = found_currencies[1]
                elif len(found_currencies) == 1:
                    # 如果只找到一个货币，根据查询内容判断
                    if '兑人民币' in user_message or '换人民币' in user_message:
                        from_currency = found_currencies[0]
                        to_currency = 'CNY'
                    elif '人民币兑' in user_message or '人民币换' in user_message:
                        from_currency = 'CNY'
                        to_currency = found_currencies[0]
                    else:
                        # 默认查询该货币兑人民币
                        from_currency = found_currencies[0]
                        to_currency = 'CNY'
                else:
                    # 没有找到货币，使用默认
                    from_currency = 'USD'
                    to_currency = 'CNY'
                
                # 避免相同货币的API调用
                if from_currency == to_currency:
                    state["exchange_data"] = {
                        "is_currency_query": True,
                        "error": f"无法查询{from_currency}兑{to_currency}的汇率，因为它们是同一种货币。"
                    }
                else:
                    state["exchange_data"] = {
                        "is_currency_query": True,
                        "from_currency": from_currency,
                        "to_currency": to_currency,
                        "user_query": user_message
                    }
            else:
                # 非货币查询
                state["exchange_data"] = {
                    "is_currency_query": False,
                    "error": "抱歉，我只能协助货币转换和汇率查询。请询问汇率相关的问题。"
                }
                
        except Exception as e:
            # LLM调用失败时的备用逻辑
            print(f"LLM判断失败，使用备用逻辑: {e}")
            currency_keywords = ['汇率', '兑', '换', '美元', '人民币', '欧元', '日元', '英镑', '澳元', '港币', '韩元']
            is_currency_query = any(keyword in user_message for keyword in currency_keywords)
            
            if is_currency_query:
                state["exchange_data"] = {
                    "is_currency_query": True,
                    "from_currency": "USD",
                    "to_currency": "CNY",
                    "user_query": user_message
                }
            else:
                state["exchange_data"] = {
                    "is_currency_query": False,
                    "error": "抱歉，我只能协助货币转换和汇率查询。请询问汇率相关的问题。"
                }
        
        return state
    
    def _get_rate(self, state: CurrencyState) -> CurrencyState:
        """获取汇率数据"""
        exchange_data = state["exchange_data"]
        
        # 如果已经有错误信息，直接返回
        if "error" in exchange_data:
            return state
        
        # 调用汇率工具
        rate_data = get_exchange_rate.invoke({
            "currency_from": exchange_data["from_currency"],
            "currency_to": exchange_data["to_currency"]
        })
        
        exchange_data.update(rate_data)
        return state
    
    def _respond(self, state: CurrencyState) -> CurrencyState:
        """生成智能响应"""
        exchange_data = state["exchange_data"]
        
        if "error" in exchange_data:
            # 使用LLM生成错误响应
            error_prompt = f"""
            用户查询汇率时出现了错误。请生成一个友好、专业的错误回复。
            
            错误信息: {exchange_data['error']}
            用户查询: {exchange_data.get('user_query', '未知查询')}
            
            请用中文回复，要：
            1. 表达歉意
            2. 说明错误原因
            3. 提供建议或替代方案
            4. 保持友好和专业的语调
            """
            
            try:
                response = self.llm.invoke(error_prompt)
                response_content = response.content.strip()
            except Exception as e:
                response_content = f"抱歉，获取汇率时出现错误：{exchange_data['error']}"
        else:
            # 使用LLM生成汇率信息响应
            rates = exchange_data.get('rates', {})
            base = exchange_data.get('base', 'EUR')
            date = exchange_data.get('date', 'latest')
            from_currency = exchange_data.get('from_currency', '')
            to_currency = exchange_data.get('to_currency', '')
            
            if rates:
                # 构建汇率数据字符串
                rate_info = []
                for currency, rate in rates.items():
                    rate_info.append(f"{base} -> {currency}: {rate}")
                rate_data_str = "\n".join(rate_info)
                
                # 使用LLM生成智能回复
                rate_prompt = f"""
                请根据以下汇率数据，为用户生成一个友好、详细的汇率信息回复。
                
                汇率数据 ({date}):
                {rate_data_str}
                
                用户查询: {exchange_data.get('user_query', '')}
                查询的货币对: {from_currency} -> {to_currency}
                
                请用中文回复，要：
                1. 清晰展示汇率信息
                2. 解释汇率含义
                3. 提供有用的上下文信息
                4. 保持专业但友好的语调
                5. 可以添加一些汇率相关的建议或说明
                """
                
                try:
                    response = self.llm.invoke(rate_prompt)
                    response_content = response.content.strip()
                except Exception as e:
                    # LLM调用失败时的备用回复
                    response_content = f"汇率信息 ({date}):\n{rate_data_str}"
            else:
                response_content = "无法获取汇率信息"
        
        # 创建AI响应
        ai_message = AIMessage(content=response_content)
        state["messages"].append(ai_message)
        
        return state
    
    def _respond_irrelevant(self, state: CurrencyState) -> CurrencyState:
        """生成智能的不相关查询响应"""
        exchange_data = state["exchange_data"]
        user_query = state["messages"][-1].content
        
        # 使用LLM生成智能的不相关查询回复
        irrelevant_prompt = f"""
        用户询问了一个与货币转换、汇率查询不相关的问题。请生成一个友好、专业的回复。
        
        用户查询: "{user_query}"
        
        请用中文回复，要：
        1. 礼貌地说明你只能协助货币相关查询
        2. 解释你的专业领域
        3. 提供一些货币查询的示例
        4. 保持友好和帮助的态度
        5. 不要显得冷漠或拒绝
        """
        
        try:
            response = self.llm.invoke(irrelevant_prompt)
            response_content = response.content.strip()
        except Exception as e:
            # LLM调用失败时的备用回复
            response_content = exchange_data.get("error", "抱歉，我只能协助货币转换和汇率查询。请询问汇率相关的问题。")
        
        # 创建AI响应
        ai_message = AIMessage(content=response_content)
        state["messages"].append(ai_message)
        
        return state
    
    def process_query(self, query: str, session_id: str = "default") -> dict:
        """处理用户查询"""
        # 初始化状态
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "exchange_data": {}
        }
        
        # 配置会话
        config = {'configurable': {'thread_id': session_id}}
        
        try:
            # 执行工作流
            result = self.graph.invoke(initial_state, config)
            
            # 获取最终响应
            if result["messages"]:
                content = result["messages"][-1].content
            else:
                content = "无法处理请求"
            
            # 确定任务状态
            is_complete = "error" not in result["exchange_data"]
            
            return {
                'is_task_complete': is_complete,
                'require_user_input': not is_complete,
                'content': content,
                'session_id': session_id
            }
            
        except Exception as e:
            return {
                'is_task_complete': False,
                'require_user_input': True,
                'content': f"处理请求时出现错误: {str(e)}",
                'session_id': session_id
            }


def main():
    """主函数 - 演示极简汇率Agent"""
    print("=== 极简LangGraph汇率Agent演示 ===")
    
    # 创建Agent
    agent = SimpleCurrencyAgent()
    
    # 测试查询
    test_queries = [
        "美元兑人民币的汇率是多少？",
        "欧元兑日元",
        "今天天气怎么样",
        "港币兑韩元"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- 测试 {i}: {query} ---")
        
        result = agent.process_query(query, f"session_{i}")
        
        print(f"状态: {'完成' if result['is_task_complete'] else '需要输入'}")
        print(f"响应: {result['content']}")
    
    print("\n=== 演示完成 ===")


if __name__ == "__main__":
    main() 