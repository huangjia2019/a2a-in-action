# a2a_agent_advanced.py
from python_a2a import A2AServer, run_server, TaskStatus, TaskState, AgentCard, AgentSkill
import requests
import re
import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# --- 配置 ---
AGENT_PORT = 7002
MCP_SERVER_URL = "http://localhost:7001" # 我们的 MCP 工具服务
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4" # 或者其他模型

# 初始化 OpenAI 客户端
openai_client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
)

class OpenAIEnhancedAgent(A2AServer):
    def __init__(self, agent_card, mcp_url):
        super().__init__(agent_card=agent_card)
        self.mcp_url = mcp_url
        # 初始化对话历史和工具调用历史
        self.conversation_history = []
        self.tool_call_history = []
        print(f"🤖 OpenAIEnhancedAgent 初始化，MCP 服务: {self.mcp_url}")

    def _call_mcp_tool(self, tool_name, params):
        """一个辅助方法，用于调用 MCP 工具"""
        if not self.mcp_url:
            return "错误：MCP 服务地址未配置。"
        
        tool_endpoint = f"{self.mcp_url}/tools/{tool_name}"
        try:
            print(f"📞 正在调用 MCP 工具: {tool_endpoint}，参数: {params}")
            response = requests.post(tool_endpoint, json=params, timeout=10)
            response.raise_for_status() # 如果 HTTP 状态码是 4xx 或 5xx，则抛出异常
            
            tool_response_json = response.json()
            print(f"工具响应JSON: {tool_response_json}")

            # 从 MCP 响应中提取文本内容
            # MCP 响应通常在 content -> parts -> text
            if tool_response_json.get("content"):
                parts = tool_response_json["content"]
                if isinstance(parts, list) and len(parts) > 0 and "text" in parts[0]:
                    return parts[0]["text"]
            return "工具成功执行，但未找到标准文本输出。"

        except requests.exceptions.RequestException as e:
            error_msg = f"调用 MCP 工具 {tool_name} 失败: {e}"
            print(f"❌ {error_msg}")
            return error_msg
        except Exception as e_json: # requests.post 成功，但响应不是期望的json或json结构不对
            error_msg = f"解析 MCP 工具 {tool_name} 响应失败: {e_json}"
            print(f"❌ {error_msg}")
            return error_msg


    def _get_openai_response(self, text_prompt, tools=None, max_iterations=5, use_history=False):
        """调用 OpenAI API 获取回复"""
        if use_history and self.conversation_history:
            # 使用完整对话历史
            messages = self.conversation_history.copy()
            # 如果最后一条不是当前提示，则添加当前提示
            if messages[-1].get("content") != text_prompt:
                messages.append({
                    "role": "user",
                    "content": text_prompt
                })
        else:
            # 不使用历史，只用当前提示
            messages = [{
                "role": "user",
                "content": text_prompt
            }]

        for i in range(max_iterations):
            try:
                response = openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    max_tokens=1500,
                    tools=tools if tools else [],
                    tool_choice='auto' if tools else None
                )
                
                tool_calls = response.choices[0].message.tool_calls
                return {
                    "message": response.choices[0].message.content,
                    "tool_calls": tool_calls,
                    "usage": response.usage
                }
            except Exception as e:
                print(f"❌ OpenAI API调用失败: {e}")
                time.sleep(0.1)
                if i == max_iterations - 1:
                    raise Exception("OpenAI API调用多次失败")

    def handle_task(self, task):
        message_data = task.message or {}
        content = message_data.get("content", {})
        user_text = content.get("text", "") 
        
        conversation_history = getattr(self, 'conversation_history', [])
        conversation_history.append({"role": "user", "content": user_text})
        print(f"📨 (OpenAI Agent) 收到任务: '{user_text}'")
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "执行数学计算",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "要计算的数学表达式"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "获取的当前本地的时间、日期、星期",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "获取指定城市的天气信息（请使用英文城市名）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "要查询天气的城市名称（必须使用英文，如：Beijing, Tokyo, New York）"
                            }
                        },
                        "required": ["city"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_city_poi",
                    "description": "获取指定城市的热门景点或餐饮推荐，用于生成旅游攻略时获取真实的当地景点和美食信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "城市英文名，如 Tokyo"
                            },
                            "category": {
                                "type": "string",
                                "description": "类别，景点：sightseeing，美食：food",
                                "enum": ["sightseeing", "food"]
                            }
                        },
                        "required": ["city", "category"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "amap_route_planning",
                    "description": "使用高德地图API规划从起点到终点的路线，支持驾车、步行、公交、骑行等出行方式",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origin": {
                                "type": "string",
                                "description": "起点地址或坐标（如：北京市海淀区清华大学）"
                            },
                            "destination": {
                                "type": "string",
                                "description": "终点地址或坐标（如：北京市朝阳区三里屯）"
                            },
                            "mode": {
                                "type": "string",
                                "description": "出行方式，可选值：driving(驾车)、walking(步行)、transit(公交)、riding(骑行)",
                                "enum": ["driving", "walking", "transit", "riding"],
                                "default": "driving"
                            },
                            "city": {
                                "type": "string",
                                "description": "城市名称，用于辅助地址解析，特别是公交路线规划时必须提供"
                            }
                        },
                        "required": ["origin", "destination"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "amap_geocode",
                    "description": "使用高德地图API的place/text接口，根据地名或地址获取经纬度坐标。适用于需要先获取地点坐标再进行周边推荐等场景。返回第一个匹配地点的经纬度信息。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "string",
                                "description": "地名、地址或POI名称，如：北京大学、东方明珠、上海迪士尼"
                            },
                            "city": {
                                "type": "string",
                                "description": "城市名称（可选），如：北京、上海"
                            }
                        },
                        "required": ["keywords"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "amap_place_around",
                    "description": "使用高德地图API的place/around接口，根据经纬度坐标获取周边兴趣点(POI)推荐，如餐厅、酒店、景点等。支持自定义类型、半径、关键词和返回数量。location参数为必填（格式：经度,纬度），可通过amap_geocode工具获取。返回POI的id、名称、类型、地址和距离等信息，可以用https://www.amap.com/place/<id>的链接查看详情。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "中心点坐标，格式：'经度,纬度'（必填），建议通过amap_geocode工具获取"
                            },
                            "keywords": {
                                "type": "string",
                                "description": "搜索关键词（如：火锅、博物馆、公园），可选"
                            },
                            "types": {
                                "type": "string",
                                "description": "POI类型编码，如'餐饮050000|生活服务070000|风景名胜110000'，可选"
                            },
                            "radius": {
                                "type": "integer",
                                "description": "搜索半径，单位：米，默认3000米，可选",
                                "default": 3000
                            },
                            "page_size": {
                                "type": "integer",
                                "description": "返回结果数量，最大25，默认10，可选",
                                "default": 10
                            }
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "amap_adcode_search",
                    "description": "根据地名或地址获取高德地图adcode城市/区县代码，适用于后续天气预报等场景。返回第一个匹配地点的adcode。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "string",
                                "description": "地名、地址或POI名称，如：西安、上海迪士尼"
                            },
                            "city": {
                                "type": "string",
                                "description": "城市名称（可选），如：西安、上海"
                            }
                        },
                        "required": ["keywords"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "amap_weather_forecast",
                    "description": "根据adcode获取中国国内城市或区县的天气预报（含未来几天天气），需先通过amap_adcode_search获取adcode。返回天气预报文本。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "adcode": {
                                "type": "string",
                                "description": "城市或区县adcode代码，如610112"
                            }
                        },
                        "required": ["adcode"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "amap_place_around",
                    "description": "使用高德地图API的place/around接口，根据经纬度坐标获取周边兴趣点(POI)推荐，如餐厅、酒店、景点等。支持自定义类型、半径、关键词和返回数量。location参数为必填（格式：经度,纬度），可通过amap_geocode工具获取。返回POI的id、名称、类型、地址和距离等信息，可以用https://www.amap.com/place/<id>的链接查看详情。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "中心点坐标，格式：'经度,纬度'（必填），建议通过amap_geocode工具获取"
                            },
                            "keywords": {
                                "type": "string",
                                "description": "搜索关键词（如：火锅、博物馆、公园），可选"
                            },
                            "types": {
                                "type": "string",
                                "description": "POI类型编码，如'餐饮050000|生活服务070000|风景名胜110000'，可选"
                            },
                            "radius": {
                                "type": "integer",
                                "description": "搜索半径，单位：米，默认3000米，可选",
                                "default": 3000
                            },
                            "page_size": {
                                "type": "integer",
                                "description": "返回结果数量，最大25，默认10，可选",
                                "default": 10
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ]

        # 让OpenAI选择工具和补全参数
        try:
            # 鼓励模型优先考虑使用工具
            enhanced_prompt = f"""
                你是一个智能助手，可以灵活运用多个工具来完成用户的需求。你可以：
                1. 组合使用多个工具，例如先获取天气信息，再推荐适合天气的景点
                2. 根据工具返回的结果决定是否需要调用其他工具
                3. 参考之前的工具调用历史，避免重复信息

                用户请求如下：{user_text}
                请分析需求并灵活调用工具来提供全面的回答。
                """
            if self.tool_call_history:
                tool_history_text = "\n\n以下是之前的工具调用历史，你可以参考这些信息：\n"
                for idx, tool_call in enumerate(self.tool_call_history):
                    tool_history_text += f"调用{idx+1}: 工具名称 {tool_call['name']}, 参数 {tool_call['args']}, 结果: {tool_call['result']}\n"
                enhanced_prompt += tool_history_text
            final_response = ""
            tool_result_for_openai = ""
            max_loops = 7
            for _ in range(max_loops):
                response = self._get_openai_response(
                    text_prompt=enhanced_prompt,
                    tools=tools,
                    use_history=True
                )
                tool_calls = response.get("tool_calls")
                if tool_calls:
                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        tool_result = self._call_mcp_tool(function_name, function_args)
                        self.tool_call_history.append({
                            "name": function_name,
                            "args": function_args,
                            "result": tool_result
                        })
                        tool_result_for_openai += f"使用{function_name}工具，参数是{function_args}，结果是：'{tool_result}'。\n"
                    enhanced_prompt = f"用户问：'{user_text}'。\n我已经调用了工具，结果如下：\n{tool_result_for_openai}\n请基于这些信息，以友好和清晰的方式回答用户。如果还需要调用工具请继续，否则直接给出最终答案。"
                else:
                    final_response = response.get("message")
                    break
            else:
                final_response = "很抱歉，未能在限定轮数内完成任务。"
            self.conversation_history.append({
                "role": "assistant",
                "content": final_response
            })
        except Exception as e:
            print(f"❌ OpenAI API调用失败: {e}")
            final_response = self._get_openai_response(user_text, tools=None).get("message")
        task.artifacts = [{"parts": [{"type": "text", "text": final_response}]}]
        task.status = TaskStatus(state=TaskState.COMPLETED)
        print(f"📤 (OpenAI Agent) 回复任务: '{final_response}'")
        return task

if __name__ == "__main__":
    # 替换您的 API Key
    agent_card = AgentCard(
        name="LLM Enhanced Assistant",
        description="一个由 LLM 驱动，并能使用外部工具的智能助手",
        url=f"http://localhost:{AGENT_PORT}",
        version="1.2.0",
        skills=[
            AgentSkill(name="Conversational AI", description="通过 OpenAI 大模型进行自然语言对话"),
            AgentSkill(name="Calculator", description="执行数学计算"),
            AgentSkill(name="Time Service", description="查询当前时间和日期"),
            AgentSkill(name="Weather Service", description="查询指定城市的天气"),
            AgentSkill(name="POI Service", description="查询指定城市的热门景点或餐饮"),
            AgentSkill(name="AMap Route Planning", description="使用高德地图API规划从起点到终点的路线"),
            AgentSkill(name="AMap POI Search", description="使用高德地图API搜索城市内的兴趣点"),
            AgentSkill(name="AMap Place Around", description="获取指定地点周边的推荐场所，如餐厅、商场、景点等")
        ]
    )

    openai_agent = OpenAIEnhancedAgent(agent_card, MCP_SERVER_URL)
    
    print(f"🚀 OpenAI Enhanced A2A Agent 即将启动于 http://localhost:{AGENT_PORT}")
    print(f"🔗 它将连接到 MCP 服务于 {MCP_SERVER_URL}")
    print(f"🧠 它将使用 OpenAI 模型: {OPENAI_MODEL}")
    
    # 启动服务，这会阻塞当前终端
    # 建议在实际部署时，MCP 服务和 A2A Agent 服务分别在不同的进程或服务器上运行
    run_server(openai_agent, host="0.0.0.0", port=AGENT_PORT)