# mcp_server.py
from python_a2a.mcp import FastMCP, text_response, create_fastapi_app
import uvicorn
from datetime import datetime
import time # 用于 get_current_time
import requests
import os
import json
from typing import Any, AsyncGenerator, Callable, Dict, Generator, List, Optional, Union
import asyncio
import json
from fastapi import BackgroundTasks, Response
from dotenv import load_dotenv
# 加载 .env 文件中的环境变量
load_dotenv()

async def sse_response(generator: Union[Generator[str, None, None], AsyncGenerator[str, None]]) -> Response:
    """将生成器转换为SSE响应"""
    async def stream_generator():
        if asyncio.iscoroutinefunction(generator.__anext__):
            # 异步生成器
            async for data in generator:
                yield f"data: {data}\n\n"
        else:
            # 同步生成器
            for data in generator:
                yield f"data: {data}\n\n"
                await asyncio.sleep(0)

    return Response(
        content=stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        },
    )

# 1. 创建 FastMCP 服务实例
# FastMCP 是一个轻量级的 MCP 服务器实现
utility_mcp = FastMCP(
    name="My MCP Tools",
    description="一些常用的实用工具集合",
    version="1.0.0"
)

# 2. 定义第一个工具：计算器
@utility_mcp.tool(
    name="calculator", # 工具的唯一名称
    description="执行一个简单的数学表达式字符串，例如 '5 * 3 + 2'，也可以处理中文表达式如'从1加到100'" # 工具的描述，LLM 可以理解这个描述来决定何时使用它
)
def calculate(expression: str): # 类型提示很重要，MCP 会据此生成工具的 schema
    """
    安全地评估一个数学表达式字符串，包括中文表达式。
    Args:
        expression: 要评估的数学表达式，例如 "10 + 5*2" 或 "从1加到100"
    Returns:
        包含计算结果的文本响应。
    """
    try:
        # 处理中文表达式
        if "从" in expression and "加到" in expression:
            # 解析类似"从1加到100"的表达式
            parts = expression.split("加到")
            if len(parts) == 2:
                start_str = parts[0].replace("从", "").strip()
                end_str = parts[1].strip()
                try:
                    start = int(start_str)
                    end = int(end_str)
                    result = sum(range(start, end + 1))
                    return text_response(f"计算结果: 从{start}加到{end} = {result}")
                except ValueError:
                    return text_response(f"无法解析数字: '{start_str}' 或 '{end_str}'")
        
        # 处理标准数学表达式
        result = eval(expression, {"__builtins__": {}}, {"abs": abs, "max": max, "min": min, "pow": pow, "round": round, "sum": sum})
        return text_response(f"计算结果: {expression} = {result}")
    except Exception as e:
        return text_response(f"计算错误 '{expression}': {str(e)}")

# 3. 定义第二个工具：获取当前时间
@utility_mcp.tool(
    name="get_current_time",
    description="获取当前的日期和时间信息"
)
def get_current_time_tool(): # 注意：工具函数名可以和工具名不同
    """
    获取当前的日期和时间。
    Returns:
        包含当前日期和时间的文本响应。
    """
    now = datetime.now()
    response = (
        f"当前日期: {now.strftime('%Y-%m-%d')}\\n"
        f"当前时间: {now.strftime('%H:%M:%S')}\\n"
        f"星期几: {now.strftime('%A')}"
    )
    return text_response(response)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

@utility_mcp.tool(
    name="get_current_weather",
    description="获取当前的天气信息，需要提供城市名称"
)
def get_current_weather_tool(city: str):
    try:
        # 请求 OpenWeatherMap API
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "zh_cn"
        }
        response = requests.get(url, params=params)
        data = response.json()

        if response.status_code != 200:
            return text_response(f"获取{city}天气失败：{data.get('message', '未知错误')}")

        weather_desc = data['weather'][0]['description']
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        return text_response(f"{city}当前天气是 {weather_desc}，温度为 {temp}°C，体感温度为 {feels_like}°C")
    
    except Exception as e:
        return text_response(f"获取{city}天气时出错：{str(e)}")

# 高德地图API工具
AMAP_API_KEY = os.getenv("AMAP_API_KEY")



@utility_mcp.tool(
    name="amap_geocode",
    description="根据关键字搜索（如“苏州中心”）获取经纬度坐标，适用于后续中心点为圆心周边半径的推荐。"
)
def amap_geocode_tool(
    keywords: str,
):
    """
    使用高德地图place/text接口获取地名或地址的经纬度坐标。
    Args:
        keywords: 地点名称或地址（如“苏州中心”）
    Returns:
        经纬度坐标字符串，如 '120.677934,31.316626'
    """
    if not AMAP_API_KEY:
        return text_response("未配置高德地图API密钥")
    url = "https://restapi.amap.com/v5/place/text"
    params = {
        "key": AMAP_API_KEY,
        "keywords": keywords,
        "page_size": 1,
        "output": "JSON"
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data.get("status") != "1" or not data.get("pois"):
            return text_response(f"未找到地点，原因：{data.get('info', '未知错误')}")
        pois = data["pois"]
        location = pois[0].get("location", "")
        name = pois[0].get("name", "")
        address = pois[0].get("address", "")
        if location:
            return text_response(f"{name}（{address}）的坐标为：{location}")
        else:
            return text_response("未获取到坐标信息")
    except Exception as e:
        return text_response(f"获取经纬度坐标时出错：{str(e)}")

@utility_mcp.tool(
    name="amap_place_around",
    description="根据经纬度坐标获取周边推荐POI（如餐饮、景点、商场等），支持自定义类型和半径，可以返回https://www.amap.com/place/<id>的链接"
)
def amap_place_around_tool(
    location: str,  # 格式：'经度,纬度'
    types: str = "",
    radius: int = 1000,
    keywords: str = "",
    page_size: int = 10
):
    """
    使用高德地图place/around接口获取指定坐标周边的POI推荐。
    Args:
        location: 中心点坐标，格式'经度,纬度'
        types: POI类型（可选），如'餐饮服务;风景名胜;购物服务'，多个类型用分号分隔
        radius: 搜索半径（米），默认1000米
        keywords: 关键词（可选）
        page_size: 返回结果数量，最大25, 默认为10
    Returns:
        周边POI推荐列表
    """
    if not AMAP_API_KEY:
        return text_response("未配置高德地图API密钥")
    url = "https://restapi.amap.com/v5/place/around"
    params = {
        "key": AMAP_API_KEY,
        "location": location,
        "types": types,
        "radius": radius,
        "keywords": keywords,
        "page_size": page_size,
        "output": "JSON"
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data.get("status") != "1" or not data.get("pois"):
            return text_response(f"未找到周边推荐，原因：{data.get('info', '未知错误')}")
        pois = data["pois"]
        result = []
        for poi in pois:
            name = poi.get("name", "")
            address = poi.get("address", "")
            poi_type = poi.get("type", "")
            distance = poi.get("distance", "")
            poi_id = poi.get("id", "")
            amap_url = f"https://www.amap.com/place/{poi_id}" if poi_id else ""
            result.append(f"{name}（类型：{poi_type}，地址：{address}，距离：{distance}米，id：{poi_id}{'，链接：' + amap_url if amap_url else ''}）")
        return text_response("\n".join(result))
    except Exception as e:
        return text_response(f"获取周边推荐时出错：{str(e)}")


@utility_mcp.tool(
    name="amap_adcode_search",
    description="根据地名或地址获取高德地图adcode城市/区县代码，适用于后续天气预报等场景。"
)
def amap_adcode_search_tool(
    keywords: str,
):
    """
    使用高德地图place/text接口获取地名或地址的adcode。
    Args:
        keywords: 地点名称或地址（如“西安”）
        city: 城市名称（可选）
    Returns:
        adcode字符串，如 '610112'
    """
    if not AMAP_API_KEY:
        return text_response("未配置高德地图API密钥")
    url = "https://restapi.amap.com/v5/place/text"
    params = {
        "key": AMAP_API_KEY,
        "keywords": keywords,
        "page_size": 1,
        "output": "JSON"
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data.get("status") != "1" or not data.get("pois"):
            return text_response(f"未找到地点，原因：{data.get('info', '未知错误')}")
        pois = data["pois"]
        adcode = pois[0].get("adcode", "")
        name = pois[0].get("name", "")
        address = pois[0].get("address", "")
        if adcode:
            return text_response(f"{name}（{address}）的adcode为：{adcode}")
        else:
            return text_response("未获取到adcode信息")
    except Exception as e:
        return text_response(f"获取adcode时出错：{str(e)}")

@utility_mcp.tool(
    name="amap_weather_forecast",
    description="根据adcode获取中国国内城市或区县的天气预报（含未来几天天气），需先通过amap_adcode_search获取adcode。"
)
def amap_weather_forecast_tool(
    adcode: str
):
    """
    使用高德地图weather/weatherInfo接口获取天气预报。
    Args:
        adcode: 城市或区县adcode代码
    Returns:
        天气预报信息
    """
    if not AMAP_API_KEY:
        return text_response("未配置高德地图API密钥")
    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": AMAP_API_KEY,
        "city": adcode,
        "extensions": "all",
        "output": "JSON"
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data.get("status") != "1" or not data.get("forecasts"):
            return text_response(f"未找到天气预报，原因：{data.get('info', '未知错误')}")
        forecast = data["forecasts"][0]
        city = forecast.get("city", "")
        province = forecast.get("province", "")
        reporttime = forecast.get("reporttime", "")
        casts = forecast.get("casts", [])
        result = [f"{province}{city}（adcode: {adcode}）天气预报，发布时间：{reporttime}"]
        for cast in casts:
            date = cast.get("date", "")
            week = cast.get("week", "")
            dayweather = cast.get("dayweather", "")
            nightweather = cast.get("nightweather", "")
            daytemp = cast.get("daytemp", "")
            nighttemp = cast.get("nighttemp", "")
            daywind = cast.get("daywind", "")
            nightwind = cast.get("nightwind", "")
            daypower = cast.get("daypower", "")
            nightpower = cast.get("nightpower", "")
            result.append(f"{date}（周{week}）：白天{dayweather}，夜间{nightweather}，最高{daytemp}℃，最低{nighttemp}℃，白天风向{daywind}{daypower}级，夜间风向{nightwind}{nightpower}级")
        return text_response("\n".join(result))
    except Exception as e:
        return text_response(f"获取天气预报时出错：{str(e)}")


# 运行 MCP 服务
if __name__ == "__main__":
    port = 7001 # 指定服务端口
    print(f"🚀 自定义 MCP 服务即将启动于 http://localhost:{port}")
    
    # create_fastapi_app 会将 FastMCP 实例转换为一个 FastAPI 应用
    app = create_fastapi_app(utility_mcp)
    
    # 使用 uvicorn 运行 FastAPI 应用
    # 这部分代码会阻塞，直到服务停止 (例如按 Ctrl+C)
    uvicorn.run(app, host="0.0.0.0", port=port)


