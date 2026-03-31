"""
构思智能体模块 (IdeationAgent)

本模块实现"阶段一：意图捕获与双轨分类机制"。

核心功能：
- 接收用户的初始科研想法
- 利用模型的结构化输出能力，强制返回 JSON 数据
- 二元分类：区分研究论文 (RESEARCH_PAPER) 和综述论文 (SURVEY_PAPER)
- 提供基于思维链 (CoT) 的分类依据

设计原则：
- 使用 Pydantic 定义严格的输出模型
- 通过 response_format 强制模型返回符合格式的 JSON
- 分类结果直接影响后续工作流的路径选择
"""

from typing import Any, Dict, Optional
import json
import time

from agent_framework import ChatResponse, Message, Content, Role

from agents.base import (
    BaseResearchAgent,
    ModelClientFactory,
    SessionManager,
    ResearchContextProvider,
)
from agents.schemas import (
    IdeationOutput,
    PaperType,
    ClassificationReasoning,
    get_ideation_response_format,
    parse_ideation_output,
)
from core.config import LLMConfig


# ============================================================================
# 构思智能体
# ============================================================================

class IdeationAgent(BaseResearchAgent[IdeationOutput]):
    """
    构思智能体

    负责理解用户的科研意图，并进行双轨分类：
    - 研究论文轨道：用户希望提出新方法、新理论或进行实验研究
    - 综述论文轨道：用户希望系统梳理某一领域的研究现状

    这是整个科研工作流的入口点，分类结果决定后续路径。

    使用示例：
        ```python
        from agents.ideation import IdeationAgent
        from core.config import settings

        # 创建智能体
        llm_config = settings.get_llm_config()
        agent = IdeationAgent(llm_config=llm_config)

        # 分析用户意图
        result = await agent.analyze(
            "我想研究一种新的基于图神经网络的分子性质预测方法"
        )

        print(f"分类结果: {result.paper_type}")
        print(f"研究主题: {result.research_topic}")
        print(f"关键词: {result.keywords}")
        ```
    """

    def _default_instructions(self) -> str:
        """
        获取默认系统指令

        定义智能体的角色、能力和输出规范。
        """
        return """你是一位资深的科研顾问，专门帮助研究者明确和细化他们的研究意图。

你的核心任务是：
1. 理解用户的研究想法或问题
2. 判断这是原创研究（research_paper）还是综述研究（survey_paper）
3. 提取研究主题和关键词
4. 提供清晰的分类依据

分类标准：
- RESEARCH_PAPER（原创研究）：用户希望提出新方法、新理论、新算法，或进行实验验证
  关键词：提出、设计、开发、改进、优化、实验、验证、新方法、新算法

- SURVEY_PAPER（综述研究）：用户希望系统梳理、总结、分析某一领域的研究现状
  关键词：综述、调研、梳理、总结、分析现状、比较、对比

输出要求：
- 必须返回严格的 JSON 格式
- reasoning 字段必须包含完整的思维链推理过程
- confidence 反映分类的确定程度
- keywords 应包含 3-8 个核心关键词

请始终以专业、严谨的态度分析用户的研究意图。"""

    async def analyze(
        self,
        user_input: str,
        include_context: bool = True,
    ) -> IdeationOutput:
        """
        分析用户的研究意图

        这是 IdeationAgent 的核心方法，执行双轨分类。

        Args:
            user_input: 用户的研究想法或问题描述
            include_context: 是否包含上下文信息

        Returns:
            IdeationOutput 对象，包含分类结果和详细信息

        Raises:
            ValueError: 如果模型返回的内容无法解析为有效 JSON
        """
        # 构建分析提示
        analysis_prompt = self._build_analysis_prompt(user_input)

        # 注意：DeepSeek 不支持 response_format，通过提示词要求 JSON 输出
        # 不使用 response_format 参数

        # 发送消息并获取响应
        response = await self.send_message(
            user_input=analysis_prompt,
            response_format=None,  # 不使用结构化输出，通过提示词控制
            include_context=include_context,
        )

        # 解析响应
        return self._parse_response(response)

    def _build_analysis_prompt(self, user_input: str) -> str:
        """
        构建分析提示

        将用户输入包装为明确的分析任务。

        Args:
            user_input: 用户输入

        Returns:
            完整的分析提示
        """
        return f"""请分析以下研究意图，并进行分类：

用户输入：
"{user_input}"

请按照以下步骤进行分析：
1. 识别用户的核心研究意图
2. 判断这是原创研究还是综述研究
3. 提取研究主题和关键词
4. 给出分类置信度和推理依据

请严格按照以下 JSON 格式返回结果（不要包含任何其他文字说明）：

{{
  "paper_type": "research_paper" 或 "survey_paper",
  "confidence": 0.0-1.0之间的数字,
  "reasoning": {{
    "key_indicators": ["关键指标1", "关键指标2"],
    "reasoning_steps": ["推理步骤1", "推理步骤2"],
    "confidence_factors": ["置信度因素1", "置信度因素2"]
  }},
  "research_topic": "研究主题",
  "keywords": ["关键词1", "关键词2", "关键词3"]
}}

注意：
- paper_type 只能是 "research_paper" 或 "survey_paper"
- confidence 是 0.0 到 1.0 之间的浮点数
- keywords 应包含 3-8 个核心关键词
- 必须返回纯 JSON 格式，不要包含 markdown 代码块标记"""

    def _parse_response(self, response: ChatResponse) -> IdeationOutput:
        """
        解析模型响应

        从 ChatResponse 中提取 JSON 内容并解析为 IdeationOutput。

        Args:
            response: 模型响应

        Returns:
            解析后的 IdeationOutput 对象

        Raises:
            ValueError: 如果解析失败
        """
        # 提取响应文本
        if not response.messages:
            raise ValueError("模型返回空响应")

        # 获取第一条消息的文本内容
        message = response.messages[0]
        text_content = message.text if hasattr(message, 'text') else ""

        if not text_content:
            # 尝试从 contents 中提取
            if message.contents:
                for content in message.contents:
                    if hasattr(content, 'text') and content.text:
                        text_content = content.text
                        break

        if not text_content:
            raise ValueError("无法从响应中提取文本内容")

        # 尝试解析 JSON
        try:
            # 清理可能的 markdown 代码块标记
            cleaned_text = self._clean_json_text(text_content)
            return parse_ideation_output(cleaned_text)
        except Exception as e:
            raise ValueError(f"解析模型响应失败: {e}\n原始内容: {text_content}")

    def _clean_json_text(self, text: str) -> str:
        """
        清理 JSON 文本

        移除可能的 markdown 代码块标记。

        Args:
            text: 原始文本

        Returns:
            清理后的 JSON 文本
        """
        text = text.strip()

        # 移除 markdown 代码块标记
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        return text.strip()

    async def classify_only(
        self,
        user_input: str,
    ) -> PaperType:
        """
        仅执行分类（不返回完整分析）

        用于快速判断用户意图类型。

        Args:
            user_input: 用户输入

        Returns:
            论文类型枚举值
        """
        result = await self.analyze(user_input)
        return result.paper_type

    async def get_research_topic(
        self,
        user_input: str,
    ) -> str:
        """
        仅获取研究主题

        Args:
            user_input: 用户输入

        Returns:
            研究主题字符串
        """
        result = await self.analyze(user_input)
        return result.research_topic

    async def get_keywords(
        self,
        user_input: str,
    ) -> list:
        """
        仅获取关键词

        Args:
            user_input: 用户输入

        Returns:
            关键词列表
        """
        result = await self.analyze(user_input)
        return result.keywords


# ============================================================================
# 批量分析支持
# ============================================================================

class IdeationBatchProcessor:
    """
    构思批量处理器

    支持批量分析多个研究想法，适用于：
    - 处理用户提供的多个研究问题
    - 并行分析多个研究主题
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        max_concurrent: int = 5,
    ):
        """
        初始化批量处理器

        Args:
            llm_config: LLM 配置
            max_concurrent: 最大并发数
        """
        self._llm_config = llm_config
        self._max_concurrent = max_concurrent

    async def analyze_batch(
        self,
        inputs: list[str],
    ) -> list[IdeationOutput]:
        """
        批量分析研究意图

        使用信号量控制并发数量。

        Args:
            inputs: 用户输入列表

        Returns:
            分析结果列表（与输入顺序对应）
        """
        import asyncio

        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def analyze_with_semaphore(
            agent: IdeationAgent,
            input_text: str,
        ) -> IdeationOutput:
            async with semaphore:
                try:
                    return await agent.analyze(input_text)
                finally:
                    await agent.close()

        # 为每个输入创建独立的智能体实例
        agents = [
            IdeationAgent(
                name=f"ideation_batch_{i}",
                llm_config=self._llm_config,
            )
            for i in range(len(inputs))
        ]

        # 并行执行分析
        tasks = [
            analyze_with_semaphore(agent, input_text)
            for agent, input_text in zip(agents, inputs)
        ]

        return await asyncio.gather(*tasks)


# ============================================================================
# 工厂函数
# ============================================================================

def create_ideation_agent(
    llm_config: LLMConfig,
    session_manager: Optional[SessionManager] = None,
    context_provider: Optional[ResearchContextProvider] = None,
    custom_instructions: Optional[str] = None,
) -> IdeationAgent:
    """
    创建构思智能体实例

    便捷工厂函数，简化智能体创建过程。

    Args:
        llm_config: LLM 配置
        session_manager: 会话管理器（可选）
        context_provider: 上下文提供者（可选）
        custom_instructions: 自定义系统指令（可选）

    Returns:
        初始化完成的 IdeationAgent 实例
    """
    return IdeationAgent(
        name="ideation_agent",
        llm_config=llm_config,
        session_manager=session_manager,
        context_provider=context_provider,
        instructions=custom_instructions,
    )
