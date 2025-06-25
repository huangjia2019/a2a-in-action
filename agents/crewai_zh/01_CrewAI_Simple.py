from crewai import Agent, Crew, Task, LLM
from dotenv import load_dotenv
import os

# 设置 DeepSeek API 密钥
load_dotenv()

# 配置 DeepSeek LLM
deepseek_llm = LLM(
    model="deepseek/deepseek-chat",  # 或使用 "deepseek-r1" 等具体模型
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# 定义一个简单的 Agent
researcher = Agent(
    role="研究员",
    goal="搜索并总结最新 AI 趋势",
    backstory="你是一位热衷于探索 AI 技术的专家",
    llm=deepseek_llm,  # 使用 DeepSeek 模型
    verbose=True
)

# 定义任务
task = Task(
    description="查找并总结 2025 年 AI 领域的最新发展",
    agent=researcher,
    expected_output="一份简短的 AI 趋势总结"
)

# 创建 Crew 并执行
crew = Crew(
    agents=[researcher],
    tasks=[task],
    verbose=True
)

# 运行任务
result = crew.kickoff()
print(result)
print('')