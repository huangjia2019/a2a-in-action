"""
基于Workflow的LlamaIndex文件聊天Agent - 教学演示
"""

import os
import base64
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.llms import ChatMessage
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from pydantic import BaseModel, Field

# 加载环境变量
load_dotenv()


## 工作流事件定义

class LogEvent(Event):
    """日志事件"""
    msg: str


class InputEvent(StartEvent):
    """输入事件"""
    msg: str
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    base64_content: Optional[str] = None


class LoadDocumentEvent(Event):
    """文档加载事件"""
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    base64_content: Optional[str] = None
    msg: str


class ChatEvent(Event):
    """聊天事件"""
    msg: str


class ChatResponseEvent(StopEvent):
    """聊天响应事件"""
    response: str
    citations: Dict[int, Dict[str, Any]]
    has_documents: bool


## 结构化输出模型

class CitationInfo(BaseModel):
    """引用信息"""
    content: str = Field(description="引用的内容片段")
    metadata: Dict[str, Any] = Field(description="引用的元数据")


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str = Field(description="对用户的响应")
    citations: Dict[int, CitationInfo] = Field(
        default_factory=dict,
        description="引用信息，键为引用编号，值为引用详情"
    )
    has_documents: bool = Field(description="是否有加载的文档")


class VectorFileChatWorkflow(Workflow):
    """基于向量索引的文件聊天工作流"""
    
    def __init__(
        self,
        timeout: float | None = None,
        verbose: bool = False,
        **workflow_kwargs: Any,
    ):
        super().__init__(timeout=timeout, verbose=verbose, **workflow_kwargs)
        
        # 配置LLM
        self.llm = GoogleGenAI(
            model='gemini-2.0-flash',
            api_key=os.getenv('GOOGLE_API_KEY')
        )
        
        # 配置BGE嵌入模型
        self.embed_model = HuggingFaceEmbedding(
            model_name="BAAI/bge-small-zh-v1.5"
        )
        
        # 设置全局配置
        Settings.llm = self.llm
        Settings.embed_model = self.embed_model
        
        # 初始化文档存储
        self.documents = []
        self.index = None
        self.chat_history = []

    @step
    def route(self, ev: InputEvent) -> LoadDocumentEvent | ChatEvent:
        """路由步骤：判断是加载文档还是聊天"""
        if ev.file_path or ev.base64_content:
            return LoadDocumentEvent(
                file_path=ev.file_path,
                file_name=ev.file_name,
                base64_content=ev.base64_content,
                msg=ev.msg
            )
        return ChatEvent(msg=ev.msg)

    @step
    async def load_document(self, ctx: Context, ev: LoadDocumentEvent) -> ChatEvent:
        """文档加载步骤"""
        try:
            if ev.file_path:
                ctx.write_event_to_stream(LogEvent(msg=f"正在加载文档: {ev.file_path}"))
                
                # 读取文件内容
                with open(ev.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                file_name = ev.file_name or ev.file_path
                
            elif ev.base64_content:
                ctx.write_event_to_stream(LogEvent(msg=f"正在解析base64文档: {ev.file_name}"))
                
                # 解码base64内容
                content = base64.b64decode(ev.base64_content).decode('utf-8')
                file_name = ev.file_name
                
            else:
                raise ValueError("必须提供文件路径或base64内容")
            
            # 创建文档对象
            doc = Document(
                text=content,
                metadata={"file_name": file_name}
            )
            
            # 添加到文档列表
            self.documents.append(doc)
            
            # 重新构建索引
            await self._build_index(ctx)
            
            ctx.write_event_to_stream(LogEvent(msg=f"✅ 文档加载成功: {file_name}"))
            
        except Exception as e:
            ctx.write_event_to_stream(LogEvent(msg=f"❌ 文档加载失败: {str(e)}"))
        
        return ChatEvent(msg=ev.msg)

    async def _build_index(self, ctx: Context):
        """构建向量索引"""
        if not self.documents:
            ctx.write_event_to_stream(LogEvent(msg="⚠️  没有文档可索引"))
            return
        
        ctx.write_event_to_stream(LogEvent(msg="正在构建向量索引..."))
        
        # 使用句子分割器
        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
        
        # 创建向量索引
        self.index = VectorStoreIndex.from_documents(
            self.documents,
            transformations=[splitter]
        )
        
        ctx.write_event_to_stream(
            LogEvent(msg=f"✅ 索引构建完成，包含 {len(self.documents)} 个文档")
        )

    @step
    async def chat(self, ctx: Context, ev: ChatEvent) -> ChatResponseEvent:
        """聊天步骤"""
        try:
            # 添加用户消息到历史
            self.chat_history.append({"role": "user", "content": ev.msg})
            
            if not self.index:
                response_content = "抱歉，还没有加载任何文档。请先加载一个文档。"
                self.chat_history.append({"role": "assistant", "content": response_content})
                
                return ChatResponseEvent(
                    response=response_content,
                    citations={},
                    has_documents=False
                )
            
            # 创建查询引擎
            query_engine = self.index.as_query_engine(
                similarity_top_k=3,
                response_mode="compact"
            )
            
            # 执行查询
            ctx.write_event_to_stream(LogEvent(msg="正在查询文档..."))
            response = query_engine.query(ev.msg)
            
            # 提取引用信息
            citations = {}
            if hasattr(response, 'source_nodes') and response.source_nodes:
                for i, node in enumerate(response.source_nodes, 1):
                    citations[i] = {
                        "content": node.text[:200] + "..." if len(node.text) > 200 else node.text,
                        "metadata": node.metadata
                    }
            
            response_content = str(response)
            
            # 添加助手回复到历史
            self.chat_history.append({"role": "assistant", "content": response_content})
            
            return ChatResponseEvent(
                response=response_content,
                citations=citations,
                has_documents=True
            )
            
        except Exception as e:
            error_msg = f"查询过程中出现错误: {str(e)}"
            self.chat_history.append({"role": "assistant", "content": error_msg})
            
            return ChatResponseEvent(
                response=error_msg,
                citations={},
                has_documents=bool(self.index)
            )

    def get_chat_history(self) -> List[Dict]:
        """获取对话历史"""
        return self.chat_history

    def clear_history(self):
        """清空对话历史"""
        self.chat_history = []
        print("✅ 对话历史已清空")

    def get_document_info(self) -> Dict:
        """获取文档信息"""
        if not self.documents:
            return {"count": 0, "documents": []}
        
        doc_info = []
        for doc in self.documents:
            doc_info.append({
                "file_name": doc.metadata.get("file_name", "未知"),
                "text_length": len(doc.text),
                "lines": len(doc.text.split('\n'))
            })
        
        return {
            "count": len(self.documents),
            "documents": doc_info
        }


def create_sample_document():
    """创建示例文档用于测试"""
    sample_content = """
# 人工智能简介

人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，旨在创建能够执行通常需要人类智能的任务的系统。

## 主要分支

### 1. 机器学习
机器学习是AI的一个重要分支，它使计算机能够在没有明确编程的情况下学习和改进。

### 2. 深度学习
深度学习是机器学习的一个子集，使用神经网络来模拟人脑的工作方式。

### 3. 自然语言处理
自然语言处理（NLP）专注于使计算机能够理解、解释和生成人类语言。

## 应用领域

- 自动驾驶汽车
- 医疗诊断
- 推荐系统
- 语音识别
- 图像识别

## 未来展望

随着技术的不断发展，AI将在更多领域发挥重要作用，但同时也需要考虑伦理和安全问题。
"""
    
    with open('sample_ai_doc.txt', 'w', encoding='utf-8') as f:
        f.write(sample_content)
    
    return 'sample_ai_doc.txt'


async def main():
    """主函数 - 演示基于Workflow的文件聊天Agent"""
    print("=== 基于Workflow的LlamaIndex文件聊天Agent演示 ===\n")
    
    # 创建Workflow Agent
    agent = VectorFileChatWorkflow()
    ctx = Context(agent)
    
    # 创建示例文档
    sample_file = create_sample_document()
    
    # 加载文档
    handler = agent.run(
        start_event=InputEvent(
            msg="你好！请加载这个文档。",
            file_path=sample_file,
            file_name="AI介绍文档"
        ),
        ctx=ctx,
    )
    
    # 处理加载文档的事件流
    async for event in handler:
        if not isinstance(event, StopEvent):
            print(f"📝 {event.msg}")
    
    # 获取加载结果
    load_response = await handler
    
    print(f"\n📄 文档信息:")
    doc_info = agent.get_document_info()
    for doc in doc_info["documents"]:
        print(f"  • {doc['file_name']}: {doc['lines']} 行, {doc['text_length']} 字符")
    
    # 测试查询
    test_queries = [
        "什么是人工智能？",
        "机器学习的主要应用有哪些？",
        "深度学习和机器学习有什么关系？",
        "AI的未来发展如何？"
    ]
    
    print(f"\n💬 开始对话测试:")
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- 查询 {i}: {query} ---")
        
        # 创建聊天事件
        chat_handler = agent.run(
            start_event=InputEvent(msg=query),
            ctx=ctx,
        )
        
        # 处理聊天事件流
        async for event in chat_handler:
            if not isinstance(event, StopEvent):
                print(f"📝 {event.msg}")
        
        # 获取聊天响应
        result = await chat_handler
        
        print(f"回复: {result.response}")
        
        if result.citations:
            print("引用:")
            for citation_num, citation_info in result.citations.items():
                print(f"  [{citation_num}] {citation_info['content']}")
    
    # 显示对话历史
    print(f"\n📝 对话历史:")
    history = agent.get_chat_history()
    for msg in history:
        role = "用户" if msg["role"] == "user" else "助手"
        print(f"{role}: {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}")
    
    print("\n=== 演示完成 ===")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 