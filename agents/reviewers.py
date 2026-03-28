"""
固定编排的同行评审委员会模块

本模块实现模拟顶级学术期刊审稿流程的固定多智能体编排。

核心设计：
- 独立角色：新颖性审稿人、方法论审稿人、影响力审稿人、主编/协调员
- 会话隔离：每个审稿人拥有独立的会话状态，防止观点污染
- 固定编排：按预定义的流程顺序执行，确保评审质量
- 聚合报告：主编汇总所有审稿意见，输出结构化的综合报告

参考期刊：Nature, Science, IEEE Transactions, ACM TOCHI
"""

from typing import Optional, Dict, Any, List, Sequence
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio

from pydantic import BaseModel, Field

from agents.base import (
    BaseResearchAgent,
    ModelClientFactory,
    LLMConfig,
    SessionManager,
    AgentSession,
)
from agents.schemas import DomainSurveyOutput
from agents.vlm_review import PolishedManuscript, FigureReviewOutput
from core.config import settings


# ============================================================================
# 枚举和常量定义
# ============================================================================

class ReviewerRole(str, Enum):
    """审稿人角色枚举"""
    NOVELTY_REVIEWER = "novelty_reviewer"           # 新颖性审稿人
    METHODOLOGY_REVIEWER = "methodology_reviewer"   # 方法论审稿人
    IMPACT_REVIEWER = "impact_reviewer"             # 影响力审稿人
    EDITOR_IN_CHIEF = "editor_in_chief"             # 主编/协调员


class ReviewDecision(str, Enum):
    """审稿决策枚举"""
    ACCEPT = "accept"                               # 接受发表
    MINOR_REVISION = "minor_revision"               # 小修后接受
    MAJOR_REVISION = "major_revision"               # 大修后重审
    REJECT_AND_RESUBMIT = "reject_and_resubmit"     # 拒稿但鼓励重投
    REJECT = "reject"                               # 拒稿


class ExpertiseLevel(str, Enum):
    """专业水平枚举"""
    EXPERT = "expert"           # 领域专家
    KNOWLEDGEABLE = "knowledgeable"  # 熟悉领域
    GENERAL = "general"         # 一般了解


# ============================================================================
# Pydantic 模型定义
# ============================================================================

class ReviewerProfile(BaseModel):
    """审稿人档案"""
    reviewer_id: str = Field(description="审稿人 ID")
    role: ReviewerRole = Field(description="审稿人角色")
    expertise_level: ExpertiseLevel = Field(
        default=ExpertiseLevel.EXPERT,
        description="专业水平",
    )
    specialization: List[str] = Field(
        default_factory=list,
        description="专业领域",
    )
    review_history_count: int = Field(
        default=0,
        description="历史审稿数量",
    )


class AspectScore(BaseModel):
    """单项评分"""
    aspect: str = Field(description="评分维度")
    score: float = Field(ge=1.0, le=10.0, description="评分（1-10）")
    weight: float = Field(ge=0.0, le=1.0, default=1.0, description="权重")
    rationale: str = Field(description="评分理由")


class ReviewerComment(BaseModel):
    """审稿人意见"""
    reviewer_id: str = Field(description="审稿人 ID")
    reviewer_role: ReviewerRole = Field(description="审稿人角色")

    # 评分
    aspect_scores: List[AspectScore] = Field(
        default_factory=list,
        description="各维度评分",
    )
    overall_score: float = Field(
        ge=1.0,
        le=10.0,
        description="综合评分",
    )

    # 决策
    decision: ReviewDecision = Field(description="审稿决策")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="决策置信度",
    )

    # 详细意见
    strengths: List[str] = Field(
        default_factory=list,
        description="优点",
    )
    weaknesses: List[str] = Field(
        default_factory=list,
        description="缺点",
    )
    specific_comments: List[str] = Field(
        default_factory=list,
        description="具体意见（针对特定章节或图表）",
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="改进建议",
    )

    # 机密意见（仅主编可见）
    confidential_comments: Optional[str] = Field(
        default=None,
        description="机密意见",
    )

    # 元数据
    review_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="审稿时间戳",
    )
    review_duration_seconds: Optional[float] = Field(
        default=None,
        description="审稿耗时（秒）",
    )


class PeerReviewReport(BaseModel):
    """同行评审综合报告"""
    manuscript_id: str = Field(description="手稿 ID")
    manuscript_title: str = Field(description="手稿标题")

    # 各审稿人意见
    novelty_review: Optional[ReviewerComment] = Field(
        default=None,
        description="新颖性审稿意见",
    )
    methodology_review: Optional[ReviewerComment] = Field(
        default=None,
        description="方法论审稿意见",
    )
    impact_review: Optional[ReviewerComment] = Field(
        default=None,
        description="影响力审稿意见",
    )

    # 主编综合意见
    editor_summary: Optional[str] = Field(
        default=None,
        description="主编总结",
    )
    editor_decision: Optional[ReviewDecision] = Field(
        default=None,
        description="主编最终决策",
    )
    editor_rationale: Optional[str] = Field(
        default=None,
        description="决策理由",
    )

    # 统计信息
    average_score: float = Field(
        default=0.0,
        description="平均评分",
    )
    score_variance: float = Field(
        default=0.0,
        description="评分方差",
    )
    consensus_level: float = Field(
        ge=0.0,
        le=1.0,
        description="共识程度",
    )

    # 时间戳
    review_start_timestamp: str = Field(
        description="评审开始时间",
    )
    review_end_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="评审结束时间",
    )
    total_duration_seconds: Optional[float] = Field(
        default=None,
        description="总耗时（秒）",
    )


# ============================================================================
# 基础审稿人智能体
# ============================================================================

class BaseReviewerAgent(BaseResearchAgent[ReviewerComment]):
    """
    基础审稿人智能体

    所有审稿人的基类，提供：
    - 独立的会话状态
    - 标准化的评审流程
    - 结构化的评审输出
    """

    def __init__(
        self,
        role: ReviewerRole,
        llm_config: LLMConfig,
        session_manager: SessionManager,
        expertise_level: ExpertiseLevel = ExpertiseLevel.EXPERT,
        specialization: Optional[List[str]] = None,
    ):
        """
        初始化审稿人

        Args:
            role: 审稿人角色
            llm_config: LLM 配置
            session_manager: 会话管理器（共享，但每个审稿人有独立会话）
            expertise_level: 专业水平
            specialization: 专业领域
        """
        super().__init__(
            name=role.value,
            llm_config=llm_config,
            session_manager=session_manager,
            instructions=self._get_role_instructions(role),
        )
        self._role = role
        self._expertise_level = expertise_level
        self._specialization = specialization or []

    def _get_role_instructions(self, role: ReviewerRole) -> str:
        """获取角色特定的系统指令"""
        base_instructions = """你是一位资深的学术审稿专家，负责对投稿的学术论文进行严格、公正的评审。

## 评审原则

1. **客观公正**：基于学术标准评判，不受个人偏好影响
2. **建设性**：提供具体的改进建议，帮助作者提升论文质量
3. **一致性**：评分标准前后一致，避免矛盾
4. **保密性**：评审意见保密，不得泄露给第三方

## 评分标准

- **1-3 分**：严重缺陷，不建议发表
- **4-5 分**：存在明显问题，需要大幅修改
- **6-7 分**：基本合格，但有小问题需要改进
- **8-9 分**：优秀，仅有微小瑕疵
- **10 分**：完美，无懈可击

## 输出要求

请以 JSON 格式输出评审意见，包含：
1. 各维度评分和理由
2. 综合评分和决策
3. 优点、缺点、具体意见、改进建议
4. 机密意见（仅主编可见）
"""

        role_specific = {
            ReviewerRole.NOVELTY_REVIEWER: """
## 新颖性审稿人职责

你专注于评估论文的**创新性和原创性**：

### 评估维度
1. **问题新颖性**：研究问题是否具有新意？
2. **方法创新性**：方法论是否有创新贡献？
3. **结果原创性**：结果和发现是否为首次报道？
4. **理论贡献**：是否有新的理论见解或框架？

### 重点关注
- 与现有文献的对比分析
- 创新点的明确性和重要性
- 是否有足够的原创贡献
- 是否存在重复发表或抄袭嫌疑
""",
            ReviewerRole.METHODOLOGY_REVIEWER: """
## 方法论审稿人职责

你专注于评估论文的**方法论严谨性**：

### 评估维度
1. **研究设计**：研究设计是否合理？
2. **数据收集**：数据收集方法是否科学？
3. **分析方法**：统计分析或计算方法是否正确？
4. **可重复性**：实验是否可重复？

### 重点关注
- 方法论的完整性和透明度
- 样本大小和代表性
- 统计方法的正确性
- 潜在的偏差和局限性
- 伦理合规性
""",
            ReviewerRole.IMPACT_REVIEWER: """
## 影响力审稿人职责

你专注于评估论文的**学术和实践影响力**：

### 评估维度
1. **理论影响**：对领域理论发展的贡献？
2. **实践价值**：对实际应用的指导意义？
3. **推广潜力**：结果是否可推广到其他场景？
4. **引用潜力**：论文的潜在引用价值？

### 重点关注
- 研究结果的重要性
- 对领域发展的推动作用
- 实际应用价值
- 对未来研究的启发
- 跨学科影响
""",
            ReviewerRole.EDITOR_IN_CHIEF: """
## 主编/协调员职责

你负责**汇总所有审稿意见并做出最终决策**：

### 职责范围
1. **意见综合**：整合各审稿人的意见
2. **冲突调解**：处理审稿人之间的分歧
3. **最终决策**：做出接受/修改/拒稿的决策
4. **作者反馈**：撰写给作者的反馈信

### 决策原则
- 综合考虑所有审稿人的意见
- 重视方法论审稿人的意见（方法论缺陷通常是致命的）
- 平衡新颖性和影响力
- 给予作者充分的改进机会
- 维护期刊的学术声誉
""",
        }

        return base_instructions + role_specific.get(role, "")

    async def review(
        self,
        manuscript: PolishedManuscript,
        figure_reviews: Optional[List[FigureReviewOutput]] = None,
        other_reviews: Optional[List[ReviewerComment]] = None,
    ) -> ReviewerComment:
        """
        执行评审

        Args:
            manuscript: 待审手稿
            figure_reviews: 图表审查结果
            other_reviews: 其他审稿人的意见（用于主编）

        Returns:
            评审意见
        """
        raise NotImplementedError("子类必须实现此方法")

    def _default_instructions(self) -> str:
        """
        获取默认系统指令

        由于 BaseReviewerAgent 在初始化时总是提供 instructions 参数,
        这个方法实际上不会被调用,但为了满足抽象方法的要求而实现。

        Returns:
            默认系统指令字符串
        """
        return "你是一位学术审稿专家。"


# ============================================================================
# 新颖性审稿人
# ============================================================================

class NoveltyReviewer(BaseReviewerAgent):
    """
    新颖性审稿人

    专注于评估论文的创新性和原创性。
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        session_manager: SessionManager,
        expertise_level: ExpertiseLevel = ExpertiseLevel.EXPERT,
        specialization: Optional[List[str]] = None,
    ):
        super().__init__(
            role=ReviewerRole.NOVELTY_REVIEWER,
            llm_config=llm_config,
            session_manager=session_manager,
            expertise_level=expertise_level,
            specialization=specialization,
        )

    async def review(
        self,
        manuscript: PolishedManuscript,
        figure_reviews: Optional[List[FigureReviewOutput]] = None,
        other_reviews: Optional[List[ReviewerComment]] = None,
    ) -> ReviewerComment:
        """执行新颖性评审"""
        from agent_framework import Message, Content

        # 确保会话已初始化
        if self._current_session is None:
            await self.initialize_session()

        # 构建评审提示词
        prompt = f"""请对以下学术论文进行新颖性评审。

## 论文信息

**标题**: {manuscript.title}

**摘要**: {manuscript.abstract}

**章节内容**:
"""
        for section in sorted(manuscript.sections, key=lambda s: s.order):
            prompt += f"\n### {section.title}\n{section.content[:500]}...\n"

        prompt += f"\n**结论**: {manuscript.conclusion}\n"

        prompt += """
## 评审要求

请从以下维度进行评分（1-10 分）：
1. 问题新颖性
2. 方法创新性
3. 结果原创性
4. 理论贡献

并给出综合评分、审稿决策、优点、缺点和改进建议。
"""

        # 构建消息
        messages = [Message(role="user", contents=[Content.from_text(prompt)])]

        # 获取聊天选项
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "reviewer_comment",
                "schema": ReviewerComment.model_json_schema(),
                "strict": True,
            }
        }
        options = ModelClientFactory.get_chat_options(
            self._llm_config,
            response_format=response_format,
        )

        # 调用模型
        start_time = datetime.now()
        response = await self._agent.client.get_response(
            messages=messages,
            options=options,
        )
        duration = (datetime.now() - start_time).total_seconds()

        # 解析输出
        if response.messages:
            content = response.messages[0].contents[0].text
            comment = ReviewerComment.model_validate_json(content)
            comment.reviewer_id = self._current_session.session_id
            comment.reviewer_role = self._role
            comment.review_duration_seconds = duration
            return comment

        # 返回默认值
        return ReviewerComment(
            reviewer_id=self._current_session.session_id,
            reviewer_role=self._role,
            decision=ReviewDecision.MAJOR_REVISION,
            review_duration_seconds=duration,
        )


# ============================================================================
# 方法论审稿人
# ============================================================================

class MethodologyReviewer(BaseReviewerAgent):
    """
    方法论审稿人

    专注于评估论文的方法论严谨性。
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        session_manager: SessionManager,
        expertise_level: ExpertiseLevel = ExpertiseLevel.EXPERT,
        specialization: Optional[List[str]] = None,
    ):
        super().__init__(
            role=ReviewerRole.METHODOLOGY_REVIEWER,
            llm_config=llm_config,
            session_manager=session_manager,
            expertise_level=expertise_level,
            specialization=specialization,
        )

    async def review(
        self,
        manuscript: PolishedManuscript,
        figure_reviews: Optional[List[FigureReviewOutput]] = None,
        other_reviews: Optional[List[ReviewerComment]] = None,
    ) -> ReviewerComment:
        """执行方法论评审"""
        from agent_framework import Message, Content

        if self._current_session is None:
            await self.initialize_session()

        prompt = f"""请对以下学术论文进行方法论评审。

## 论文信息

**标题**: {manuscript.title}

**摘要**: {manuscript.abstract}

**章节内容**:
"""
        for section in sorted(manuscript.sections, key=lambda s: s.order):
            prompt += f"\n### {section.title}\n{section.content[:500]}...\n"

        prompt += f"\n**结论**: {manuscript.conclusion}\n"

        # 添加图表审查信息
        if figure_reviews:
            prompt += "\n## 图表审查结果\n"
            for review in figure_reviews:
                prompt += f"- 图表 {review.figure_id}: 评分 {review.overall_score:.1f}, 结论 {review.verdict.value}\n"

        prompt += """
## 评审要求

请从以下维度进行评分（1-10 分）：
1. 研究设计
2. 数据收集
3. 分析方法
4. 可重复性

并给出综合评分、审稿决策、优点、缺点和改进建议。
"""

        messages = [Message(role="user", contents=[Content.from_text(prompt)])]

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "reviewer_comment",
                "schema": ReviewerComment.model_json_schema(),
                "strict": True,
            }
        }
        options = ModelClientFactory.get_chat_options(
            self._llm_config,
            response_format=response_format,
        )

        start_time = datetime.now()
        response = await self._agent.client.get_response(
            messages=messages,
            options=options,
        )
        duration = (datetime.now() - start_time).total_seconds()

        if response.messages:
            content = response.messages[0].contents[0].text
            comment = ReviewerComment.model_validate_json(content)
            comment.reviewer_id = self._current_session.session_id
            comment.reviewer_role = self._role
            comment.review_duration_seconds = duration
            return comment

        return ReviewerComment(
            reviewer_id=self._current_session.session_id,
            reviewer_role=self._role,
            decision=ReviewDecision.MAJOR_REVISION,
            review_duration_seconds=duration,
        )


# ============================================================================
# 影响力审稿人
# ============================================================================

class ImpactReviewer(BaseReviewerAgent):
    """
    影响力审稿人

    专注于评估论文的学术和实践影响力。
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        session_manager: SessionManager,
        expertise_level: ExpertiseLevel = ExpertiseLevel.EXPERT,
        specialization: Optional[List[str]] = None,
    ):
        super().__init__(
            role=ReviewerRole.IMPACT_REVIEWER,
            llm_config=llm_config,
            session_manager=session_manager,
            expertise_level=expertise_level,
            specialization=specialization,
        )

    async def review(
        self,
        manuscript: PolishedManuscript,
        figure_reviews: Optional[List[FigureReviewOutput]] = None,
        other_reviews: Optional[List[ReviewerComment]] = None,
    ) -> ReviewerComment:
        """执行影响力评审"""
        from agent_framework import Message, Content

        if self._current_session is None:
            await self.initialize_session()

        prompt = f"""请对以下学术论文进行影响力评审。

## 论文信息

**标题**: {manuscript.title}

**摘要**: {manuscript.abstract}

**章节内容**:
"""
        for section in sorted(manuscript.sections, key=lambda s: s.order):
            prompt += f"\n### {section.title}\n{section.content[:500]}...\n"

        prompt += f"\n**结论**: {manuscript.conclusion}\n"

        prompt += """
## 评审要求

请从以下维度进行评分（1-10 分）：
1. 理论影响
2. 实践价值
3. 推广潜力
4. 引用潜力

并给出综合评分、审稿决策、优点、缺点和改进建议。
"""

        messages = [Message(role="user", contents=[Content.from_text(prompt)])]

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "reviewer_comment",
                "schema": ReviewerComment.model_json_schema(),
                "strict": True,
            }
        }
        options = ModelClientFactory.get_chat_options(
            self._llm_config,
            response_format=response_format,
        )

        start_time = datetime.now()
        response = await self._agent.client.get_response(
            messages=messages,
            options=options,
        )
        duration = (datetime.now() - start_time).total_seconds()

        if response.messages:
            content = response.messages[0].contents[0].text
            comment = ReviewerComment.model_validate_json(content)
            comment.reviewer_id = self._current_session.session_id
            comment.reviewer_role = self._role
            comment.review_duration_seconds = duration
            return comment

        return ReviewerComment(
            reviewer_id=self._current_session.session_id,
            reviewer_role=self._role,
            decision=ReviewDecision.MAJOR_REVISION,
            review_duration_seconds=duration,
        )


# ============================================================================
# 主编/协调员
# ============================================================================

class EditorInChief(BaseReviewerAgent):
    """
    主编/协调员

    汇总所有审稿意见，做出最终决策。
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        session_manager: SessionManager,
    ):
        super().__init__(
            role=ReviewerRole.EDITOR_IN_CHIEF,
            llm_config=llm_config,
            session_manager=session_manager,
        )

    async def review(
        self,
        manuscript: PolishedManuscript,
        figure_reviews: Optional[List[FigureReviewOutput]] = None,
        other_reviews: Optional[List[ReviewerComment]] = None,
    ) -> ReviewerComment:
        """汇总审稿意见并做出决策"""
        from agent_framework import Message, Content

        if self._current_session is None:
            await self.initialize_session()

        if not other_reviews:
            return ReviewerComment(
                reviewer_id=self._current_session.session_id,
                reviewer_role=self._role,
                decision=ReviewDecision.MAJOR_REVISION,
            )

        prompt = f"""请汇总以下审稿意见并做出最终决策。

## 论文信息

**标题**: {manuscript.title}

**摘要**: {manuscript.abstract}

## 审稿意见汇总

"""
        for i, review in enumerate(other_reviews, 1):
            prompt += f"""
### 审稿人 {i} ({review.reviewer_role.value})

- **综合评分**: {review.overall_score:.1f}/10
- **决策**: {review.decision.value}
- **置信度**: {review.confidence:.2f}

**优点**:
{chr(10).join(f'- {s}' for s in review.strengths)}

**缺点**:
{chr(10).join(f'- {w}' for w in review.weaknesses)}

**改进建议**:
{chr(10).join(f'- {s}' for s in review.suggestions)}

"""
            if review.confidential_comments:
                prompt += f"**机密意见**: {review.confidential_comments}\n"

        prompt += """
## 决策要求

请综合考虑所有审稿人的意见，做出最终决策：
1. 计算平均评分和评分方差
2. 评估审稿人之间的共识程度
3. 权衡各维度的重要性
4. 给出最终决策和理由
5. 撰写给作者的反馈总结

决策选项：
- accept: 接受发表
- minor_revision: 小修后接受
- major_revision: 大修后重审
- reject_and_resubmit: 拒稿但鼓励重投
- reject: 拒稿
"""

        messages = [Message(role="user", contents=[Content.from_text(prompt)])]

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "reviewer_comment",
                "schema": ReviewerComment.model_json_schema(),
                "strict": True,
            }
        }
        options = ModelClientFactory.get_chat_options(
            self._llm_config,
            response_format=response_format,
        )

        start_time = datetime.now()
        response = await self._agent.client.get_response(
            messages=messages,
            options=options,
        )
        duration = (datetime.now() - start_time).total_seconds()

        if response.messages:
            content = response.messages[0].contents[0].text
            comment = ReviewerComment.model_validate_json(content)
            comment.reviewer_id = self._current_session.session_id
            comment.reviewer_role = self._role
            comment.review_duration_seconds = duration
            return comment

        return ReviewerComment(
            reviewer_id=self._current_session.session_id,
            reviewer_role=self._role,
            decision=ReviewDecision.MAJOR_REVISION,
            review_duration_seconds=duration,
        )


# ============================================================================
# 同行评审委员会（固定编排）
# ============================================================================

class PeerReviewCommittee:
    """
    同行评审委员会

    实现固定编排的多智能体审稿流程：
    1. 新颖性审稿人评审
    2. 方法论审稿人评审
    3. 影响力审稿人评审
    4. 主编汇总并决策

    关键特性：
    - 每个审稿人拥有独立的会话状态
    - 审稿意见互不干扰，防止观点污染
    - 固定的评审顺序，确保流程规范
    """

    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        parallel_review: bool = False,
    ):
        """
        初始化同行评审委员会

        Args:
            llm_config: LLM 配置
            parallel_review: 是否并行评审（默认顺序执行）
        """
        self._llm_config = llm_config or settings.get_llm_config()
        self._parallel_review = parallel_review

        # 共享的会话管理器（但每个审稿人有独立会话）
        self._session_manager = SessionManager()

        # 初始化审稿人
        self._novelty_reviewer = NoveltyReviewer(
            self._llm_config,
            self._session_manager,
        )
        self._methodology_reviewer = MethodologyReviewer(
            self._llm_config,
            self._session_manager,
        )
        self._impact_reviewer = ImpactReviewer(
            self._llm_config,
            self._session_manager,
        )
        self._editor = EditorInChief(
            self._llm_config,
            self._session_manager,
        )

    async def conduct_review(
        self,
        manuscript: PolishedManuscript,
        figure_reviews: Optional[List[FigureReviewOutput]] = None,
        manuscript_id: Optional[str] = None,
    ) -> PeerReviewReport:
        """
        执行同行评审

        Args:
            manuscript: 待审手稿
            figure_reviews: 图表审查结果
            manuscript_id: 手稿 ID

        Returns:
            同行评审综合报告
        """
        start_time = datetime.now()
        manuscript_id = manuscript_id or f"manuscript_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 初始化报告
        report = PeerReviewReport(
            manuscript_id=manuscript_id,
            manuscript_title=manuscript.title,
            review_start_timestamp=start_time.isoformat(),
            consensus_level=0.0,
        )

        # 执行评审
        if self._parallel_review:
            # 并行评审
            novelty_task = self._novelty_reviewer.review(manuscript, figure_reviews)
            methodology_task = self._methodology_reviewer.review(manuscript, figure_reviews)
            impact_task = self._impact_reviewer.review(manuscript, figure_reviews)

            novelty_review, methodology_review, impact_review = await asyncio.gather(
                novelty_task, methodology_task, impact_task
            )
        else:
            # 顺序评审
            novelty_review = await self._novelty_reviewer.review(manuscript, figure_reviews)
            methodology_review = await self._methodology_reviewer.review(manuscript, figure_reviews)
            impact_review = await self._impact_reviewer.review(manuscript, figure_reviews)

        # 记录评审意见
        report.novelty_review = novelty_review
        report.methodology_review = methodology_review
        report.impact_review = impact_review

        # 计算统计信息
        scores = [
            novelty_review.overall_score,
            methodology_review.overall_score,
            impact_review.overall_score,
        ]
        report.average_score = sum(scores) / len(scores)
        report.score_variance = sum((s - report.average_score) ** 2 for s in scores) / len(scores)

        # 计算共识程度（评分越接近，共识越高）
        max_score_diff = max(scores) - min(scores)
        report.consensus_level = 1.0 - (max_score_diff / 9.0)  # 归一化到 [0, 1]

        # 主编汇总
        all_reviews = [novelty_review, methodology_review, impact_review]
        editor_review = await self._editor.review(
            manuscript,
            figure_reviews,
            all_reviews,
        )

        report.editor_summary = "\n".join(editor_review.suggestions)
        report.editor_decision = editor_review.decision
        report.editor_rationale = "\n".join(editor_review.weaknesses + editor_review.strengths)

        # 记录结束时间
        end_time = datetime.now()
        report.review_end_timestamp = end_time.isoformat()
        report.total_duration_seconds = (end_time - start_time).total_seconds()

        return report

    async def close(self) -> None:
        """关闭所有审稿人"""
        await self._novelty_reviewer.close()
        await self._methodology_reviewer.close()
        await self._impact_reviewer.close()
        await self._editor.close()


# ============================================================================
# 便捷函数
# ============================================================================

async def conduct_peer_review(
    manuscript: PolishedManuscript,
    llm_config: Optional[LLMConfig] = None,
    figure_reviews: Optional[List[FigureReviewOutput]] = None,
) -> PeerReviewReport:
    """
    执行同行评审（便捷函数）

    Args:
        manuscript: 待审手稿
        llm_config: LLM 配置
        figure_reviews: 图表审查结果

    Returns:
        同行评审综合报告
    """
    committee = PeerReviewCommittee(llm_config)
    try:
        return await committee.conduct_review(manuscript, figure_reviews)
    finally:
        await committee.close()
