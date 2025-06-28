# 极简版LlamaIndex文件聊天Agent

这是一个简化版的LlamaIndex文件聊天Agent，专门用于教学演示。

## 主要特点

### 1. 极简架构
- **核心组件**：文档加载 → 向量索引 → 智能问答
- **简单流程**：易于理解的工作流
- **最小依赖**：只使用LlamaIndex核心功能

### 2. 核心组件

#### Agent类
```python
class SimpleFileChatAgent:
    def __init__(self):
        # 配置LLM和嵌入模型
        # 初始化文档存储和索引
```

#### 主要方法
- `load_document()`: 加载本地文档
- `load_document_from_base64()`: 从base64加载文档
- `chat()`: 与文档进行对话
- `get_chat_history()`: 获取对话历史
- `clear_history()`: 清空对话历史

### 3. 教学要点

#### LlamaIndex基础概念
- **Document**: 文档对象
- **VectorStoreIndex**: 向量索引
- **QueryEngine**: 查询引擎
- **NodeParser**: 节点分割器

#### 工作流程
```python
# 1. 创建文档
doc = Document(text=content, metadata={"file_name": "example.txt"})

# 2. 构建索引
index = VectorStoreIndex.from_documents(documents, transformations=[splitter])

# 3. 创建查询引擎
query_engine = index.as_query_engine(similarity_top_k=3)

# 4. 执行查询
response = query_engine.query("用户问题")
```

## 使用方法

### 1. 安装依赖
```bash
pip install llama-index llama-index-llms-google-genai llama-index-embeddings-google python-dotenv
```

### 2. 设置环境变量
```bash
export GOOGLE_API_KEY="your_google_api_key"
```

### 3. 运行演示
```bash
python 01_LlamaIndex_Simple.py
```

### 4. 基本使用
```python
from llama_index_file_chat_zh.01_LlamaIndex_Simple import SimpleFileChatAgent

# 创建Agent
agent = SimpleFileChatAgent()

# 加载文档
agent.load_document('your_document.txt', "文档名称")

# 进行对话
result = agent.chat("你的问题")
print(result['response'])

# 查看引用
for citation_num, citation_info in result['citations'].items():
    print(f"[{citation_num}] {citation_info['content']}")
```

## 与原版对比

| 特性 | 原版 | 简化版 |
|------|------|--------|
| 代码行数 | ~244行 | ~200行 |
| 架构复杂度 | 事件驱动工作流 | 简单类设计 |
| 文档格式支持 | PDF、复杂格式 | 文本文件 |
| 引用系统 | 结构化引用 | 基本引用 |
| 学习曲线 | 陡峭 | 平缓 |
| 教学适用性 | 中等 | 优秀 |

## 核心功能

### 1. 文档加载
- 支持本地文本文件
- 支持base64编码内容
- 自动构建向量索引

### 2. 智能问答
- 基于向量相似度搜索
- 提供引用信息
- 支持上下文理解

### 3. 对话管理
- 维护对话历史
- 支持历史查询
- 可清空历史记录

### 4. 错误处理
- 文档加载失败处理
- 查询错误处理
- 友好的错误提示

## 扩展建议

1. **添加更多文档格式支持**
   - PDF文档
   - Word文档
   - Markdown文件

2. **增强引用功能**
   - 更精确的行号引用
   - 可视化引用显示

3. **改进搜索策略**
   - 混合搜索（关键词+语义）
   - 多轮对话优化

4. **添加文档管理**
   - 文档分类
   - 文档删除
   - 批量处理

## 学习路径

1. **基础概念学习**
   - 理解向量索引原理
   - 学习文档分割策略
   - 掌握查询引擎使用

2. **功能扩展**
   - 添加新的文档格式支持
   - 实现更复杂的搜索逻辑
   - 优化响应质量

3. **高级特性**
   - 学习原版的工作流设计
   - 理解事件驱动架构
   - 掌握结构化输出

4. **实际应用**
   - 构建文档问答系统
   - 集成到Web应用
   - 部署到生产环境

## 技术栈

- **LlamaIndex**: 核心框架
- **Google GenAI**: LLM和嵌入模型
- **SentenceSplitter**: 文档分割
- **VectorStoreIndex**: 向量存储

## 注意事项

1. **API密钥**: 需要有效的Google API密钥
2. **文档格式**: 目前主要支持文本文件
3. **内存使用**: 大文档会占用较多内存
4. **响应时间**: 首次索引构建需要时间

## 故障排除

### 常见问题

1. **API密钥错误**
   ```
   解决方案: 检查GOOGLE_API_KEY环境变量
   ```

2. **文档加载失败**
   ```
   解决方案: 检查文件路径和编码格式
   ```

3. **索引构建失败**
   ```
   解决方案: 检查文档内容和大小
   ```

4. **查询无结果**
   ```
   解决方案: 调整similarity_top_k参数
   ``` 