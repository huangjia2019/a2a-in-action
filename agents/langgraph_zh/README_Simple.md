# 极简版LangGraph汇率Agent

这是一个简化版的LangGraph汇率转换Agent，专门用于教学演示。

## 主要特点

### 1. 极简架构
- **3个节点**：处理查询 → 获取汇率 → 生成响应
- **线性流程**：简单易懂的工作流
- **最小依赖**：只使用核心LangGraph功能

### 2. 核心组件

#### 状态定义
```python
class CurrencyState(TypedDict):
    messages: Annotated[list, "对话消息列表"]
    exchange_data: Annotated[dict, "汇率数据"]
```

#### 工具函数
```python
@tool
def get_exchange_rate(currency_from: str = 'USD', currency_to: str = 'CNY') -> dict:
    # 调用汇率API
```

#### 工作流节点
1. **process_query**: 解析用户查询，识别货币对
2. **get_rate**: 调用API获取汇率数据
3. **respond**: 格式化并返回结果

### 3. 教学要点

#### LangGraph基础概念
- **StateGraph**: 状态图定义
- **节点 (Node)**: 工作流中的处理步骤
- **边 (Edge)**: 节点之间的连接关系
- **检查点 (Checkpoint)**: 状态持久化

#### 工作流创建步骤
```python
# 1. 创建状态图
workflow = StateGraph(CurrencyState)

# 2. 添加节点
workflow.add_node("process_query", self._process_query)
workflow.add_node("get_rate", self._get_rate)
workflow.add_node("respond", self._respond)

# 3. 设置入口点
workflow.set_entry_point("process_query")

# 4. 添加边
workflow.add_edge("process_query", "get_rate")
workflow.add_edge("get_rate", "respond")
workflow.add_edge("respond", END)

# 5. 编译图
return workflow.compile(checkpointer=memory)
```

## 使用方法

### 1. 安装依赖
```bash
pip install langgraph langchain-google-genai httpx python-dotenv
```

### 2. 设置环境变量
```bash
export GOOGLE_API_KEY="your_google_api_key"
```

### 3. 运行演示
```bash
python 02_LangGraph_Currency_Agent_Simple.py
```

### 4. 测试查询
```python
agent = SimpleCurrencyAgent()
result = agent.process_query("美元兑人民币的汇率是多少？")
print(result['content'])
```

## 与原版对比

| 特性 | 原版 | 极简版 |
|------|------|--------|
| 代码行数 | ~400行 | ~150行 |
| 节点数量 | 3个 | 3个 |
| LLM分析 | 复杂智能分析 | 简单关键词匹配 |
| 错误处理 | 详细 | 基础 |
| 状态管理 | 复杂 | 简单 |
| 教学适用性 | 中等 | 优秀 |

## 扩展建议

1. **添加更多货币支持**
2. **实现更智能的查询解析**
3. **添加汇率历史查询**
4. **实现多轮对话支持**
5. **添加汇率计算功能**

## 学习路径

1. 先理解极简版的核心概念
2. 尝试修改和扩展功能
3. 学习原版的复杂特性
4. 应用到自己的项目中 