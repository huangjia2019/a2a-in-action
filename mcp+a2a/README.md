# AutoCityIntro - 智能城市助手

## 项目介绍

AutoCityIntro 是一个基于大语言模型和多种API的智能城市助手，能够提供城市信息、天气查询、景点推荐、路线规划等功能。项目使用A2A框架和MCP工具服务架构，支持多轮对话和多工具调用。

## 功能特点

- **基础工具**：
  - 计算器：执行数学计算
  - 时间服务：查询当前时间和日期
  - 天气服务：查询指定城市的天气信息
  - POI服务：查询指定城市的热门景点或餐饮推荐

- **高德地图工具**：
  - 路线规划：支持驾车、步行、公交、骑行等多种出行方式
  - POI搜索：搜索城市内的兴趣点，如餐厅、酒店、景点等

- **高级特性**：
  - 多轮对话：记住对话历史，实现连贯的交互体验
  - 多工具调用：能够组合使用多个工具解决复杂问题
  - SSE流式响应：高德地图工具支持流式输出，提供更好的用户体验

## 系统架构

系统由两部分组成：

1. **MCP工具服务**：提供各种工具API，包括计算器、时间、天气、POI查询和高德地图服务
2. **A2A智能助手**：基于OpenAI大模型，能够理解用户需求并调用适当的工具

## 环境配置

### 依赖安装

```bash
pip install -r requirements.txt
```

### 环境变量

创建`.env`文件，配置以下API密钥：

```
OPENAI_API_KEY=your_openai_api_key
OPENWEATHER_API_KEY=your_openweather_api_key
FOURSQUARE_API_KEY=your_foursquare_api_key
AMAP_API_KEY=your_amap_api_key
```

## 使用方法

### 启动服务

1. 启动MCP工具服务：

```bash
python mcp_server.py
```

2. 启动A2A智能助手：

```bash
python a2a_agent_advanced.py
```

### 测试工具

运行测试脚本：

```bash
python test_a2a_advanced.ipynb  # 测试基础功能
python test_amap_tools.py        # 测试高德地图工具
```

## 示例查询

- 「北京今天天气怎么样？」
- 「帮我计算3乘以100加20等于多少」
- 「现在几点了？」
- 「推荐东京的热门景点」
- 「帮我规划从北京清华大学到故宫博物院的驾车路线」
- 「我在上海外滩，附近有什么好吃的餐厅？」
- 「今天深圳天气怎么样？适合去哪些地方游玩？」

## 高德地图API参考

- [高德开放平台](https://lbs.amap.com/api/webservice/summary/)
- [路线规划API](https://lbs.amap.com/api/webservice/guide/api/direction)
- [POI搜索API](https://lbs.amap.com/api/webservice/guide/api/search)

## 许可证

MIT