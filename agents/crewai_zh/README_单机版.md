# CrewAI 图像生成 Agent

这是一个基于CrewAI框架的简化图像生成Agent，实现了与原始`crewai_ch/agent.py`相同的核心功能。

## 功能特性

- 🎨 基于文本提示词生成图像
- 🔧 使用Google GenAI (Gemini) 模型
- 💾 简单的内存缓存系统
- 🛠️ 支持图像编辑和修改
- 📝 详细的日志记录

## 文件结构

```
demo/
├── crewai_agent.py          # 主要的Agent实现
├── test_crewai_agent.py     # 测试脚本
└── README_crewai_agent.md   # 本文件
```

## 安装依赖

确保已安装以下Python包：

```bash
pip install crewai google-genai pillow python-dotenv pydantic
```

## 环境变量配置

在`.env`文件中设置以下环境变量：

```env
# Google GenAI API密钥
GOOGLE_API_KEY=your_google_api_key_here

# 可选：使用Vertex AI
GOOGLE_GENAI_USE_VERTEXAI=true
```

## 使用方法

### 基本使用

```python
from demo.crewai_agent import SimpleCrewAIAgent

# 创建Agent实例
agent = SimpleCrewAIAgent()

# 生成图像
prompt = "一只可爱的小猫坐在花园里，阳光明媚"
session_id = "my_session_123"
result = agent.generate_image(prompt, session_id)

print(f"生成的图像ID: {result}")

# 获取图像数据
if result and not result.startswith("错误"):
    image_data = agent.get_image_data(session_id, result)
    print(f"图像名称: {image_data.name}")
    print(f"MIME类型: {image_data.mime_type}")
    print(f"数据大小: {len(image_data.bytes)} 字节")
```

### 图像编辑

```python
# 基于现有图像进行编辑
prompt = "将这个图像修改为蓝色主题 id abc123456789012345678901234567890"
result = agent.generate_image(prompt, session_id)
```

### 运行测试

```bash
# 运行基本测试
python demo/test_crewai_agent.py

# 运行Agent示例
python demo/crewai_agent.py
```

## 核心组件

### SimpleCrewAIAgent

主要的Agent类，包含以下方法：

- `__init__()`: 初始化Agent和CrewAI组件
- `generate_image(prompt, session_id)`: 生成图像的主方法
- `get_image_data(session_id, image_id)`: 获取图像数据
- `extract_artifact_file_id(query)`: 从查询中提取图像ID

### generate_image_tool

CrewAI工具，负责实际的图像生成：

- 调用Google GenAI API
- 处理参考图像
- 管理图像缓存

### SimpleImageCache

简单的内存缓存系统，用于存储生成的图像数据。

## 与原始实现的区别

这个简化版本相比原始的`crewai_ch/agent.py`：

✅ **保留的功能**：
- 核心的图像生成逻辑
- CrewAI框架集成
- Google GenAI API调用
- 图像缓存机制
- artifact_file_id提取

❌ **简化的部分**：
- 移除了A2A协议相关的复杂结构
- 简化了错误处理
- 使用更简单的缓存实现
- 移除了流式处理（CrewAI不支持）

## 故障排除

### 常见问题

1. **API密钥错误**
   ```
   确保设置了正确的GOOGLE_API_KEY环境变量
   ```

2. **依赖包缺失**
   ```bash
   pip install crewai google-genai pillow python-dotenv pydantic
   ```

3. **图像生成失败**
   ```
   检查网络连接和API配额
   确保提示词不为空
   ```

### 调试模式

Agent默认开启了详细输出模式，可以通过修改以下参数来调整：

```python
# 在SimpleCrewAIAgent.__init__()中
verbose=False  # 关闭详细输出
```

## 扩展功能

可以基于这个基础实现添加更多功能：

- 支持更多图像格式
- 添加图像后处理
- 实现持久化存储
- 添加用户认证
- 支持批量生成

## 许可证

本项目遵循与主项目相同的许可证。 