"""
手稿润色与同行评审模块 (Integration, Polishing & Peer Review)

本模块实现 EpistemicFlow 的后期阶段：
- Stage 4: 手稿润色智能体 (Integration and Polishing Agent)
- Stage 5: 同行评审委员会 (Peer Review Board)

核心特性：
- 手稿润色：执行高阶推理与反思，输出 LaTeX 格式源码
- 评审委员会：使用 GroupChatOrchestrator 构建隔离的评审子图
- 固定编排：四个固定角色（Novelty, Methods, Impact, Leader）

设计原则：
- 完全隔离：评审委员会运行在独立的工作流中
- 结构化输出：评审报告严格遵循预定义格式
- 可追溯性：所有评审意见关联到具体章节
"""

from typing import Any, Dict, List, Optional, Sequence, Never
from dataclasses import dataclass, field
from enum import Enum
import json

from agent_framework import (
    Agent,
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    Workflow,
    handler,
    Message,
    Content,
)
from agent_framework.openai import OpenAIChatClient

from core.config import LLMConfig, settings


# ============================================================================
# 数据模型定义
# ============================================================================

class ReviewVerdict(str, Enum):
    """评审结论枚举"""
    ACCEPT = "accept"              # 接收
    MINOR_REVISION = "minor_revision"  # 小修
    MAJOR_REVISION = "major_revision"  # 大修
    REJECT = "reject"              # 拒稿


@dataclass
class ManuscriptSection:
    """手稿章节"""
    section_id: str
    """章节 ID"""
    title: str
    """章节标题"""
    content: str
    """章节内容（LaTeX 格式）"""
    figures: List[str] = field(default_factory=list)
    """图表引用列表"""


@dataclass
class Manuscript:
    """完整手稿"""
    title: str
    """标题"""
    abstract: str
    """摘要"""
    sections: List[ManuscriptSection]
    """章节列表"""
    references: List[str] = field(default_factory=list)
    """参考文献"""
    latex_source: str = ""
    """完整 LaTeX 源码"""


@dataclass
class ReviewComment:
    """评审意见"""
    reviewer_id: str
    """审稿人 ID"""
    reviewer_role: str
    """审稿人角色"""
    section_id: Optional[str]
    """关联章节 ID（None 表示整体意见）"""
    comment: str
    """意见内容"""
    severity: str = "normal"
    """严重程度：critical, major, minor, suggestion"""
    suggestion: Optional[str] = None
    """修改建议"""


@dataclass
class ReviewScore:
    """评审分数"""
    novelty: float = 0.0
    """新颖性 (0-10)"""
    methodology: float = 0.0
    """方法论 (0-10)"""
    impact: float = 0.0
    """影响力 (0-10)"""
    clarity: float = 0.0
    """清晰度 (0-10)"""
    overall: float = 0.0
    """总体评分 (0-10)"""


@dataclass
class IndividualReview:
    """单个审稿人的评审结果"""
    reviewer_id: str
    reviewer_role: str
    scores: ReviewScore
    comments: List[ReviewComment]
    verdict: ReviewVerdict
    confidence: float = 0.8


@dataclass
class ConsolidatedReview:
    """综合评审报告"""
    manuscript_title: str
    """手稿标题"""
    individual_reviews: List[IndividualReview]
    """各审稿人评审结果"""
    final_verdict: ReviewVerdict
    """最终结论"""
    final_scores: ReviewScore
    """平均分数"""
    consolidated_comments: List[ReviewComment]
    """聚合意见（去重、排序）"""
    revision_requirements: List[str]
    """修改要求"""
    editor_summary: str
    """主编总结"""


# ============================================================================
# 手稿润色智能体 (Integration and Polishing Agent)
# ============================================================================

class PolishingAgent:
    """
    手稿润色智能体
    
    负责接收所有实证结论和图表，执行高阶推理与反思，
    并严格输出高质量的 LaTeX 格式源码。
    
    核心能力：
    - 整合分散的研究结论
    - 执行反思推理（Reflection）
    - 生成结构化的 LaTeX 源码
    - 确保图表引用正确
    """
    
    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
    ):
        """
        初始化润色智能体
        
        Args:
            llm_config: LLM 配置
        """
        self._llm_config = llm_config or settings.get_llm_config()
        self._agent: Optional[Agent] = None
    
    def _get_agent(self) -> Agent:
        """获取或创建 Agent"""
        if self._agent is None:
            client = OpenAIChatClient(
                model_id=self._llm_config.model_name,
                api_key=self._llm_config.api_key,
                base_url=self._llm_config.base_url,
            )
            
            self._agent = Agent(
                client=client,
                name="polishing_agent",
                instructions=self._get_instructions(),
            )
        
        return self._agent
    
    def _get_instructions(self) -> str:
        """获取系统指令"""
        return """你是一位资深的学术写作专家，负责将研究成果整合为高质量的学术论文。

你的核心任务是：
1. 整合分散的研究结论和实证结果
2. 执行高阶反思推理，确保论证严密
3. 生成结构完整、格式规范的 LaTeX 源码
4. 确保图表引用正确、编号连续

写作要求：
- 标题：简洁、准确、吸引人
- 摘要：遵循 IMRAD 结构，不超过 250 词
- 引言：明确研究背景、动机和贡献
- 方法：详细、可复现
- 结果：客观、准确
- 讨论：深入、有洞见
- 结论：总结贡献、展望未来

LaTeX 格式要求：
- 使用标准 article 或 llncs 文档类
- 图表使用 figure/table 环境
- 公式使用 equation/align 环境
- 参考文献使用 biblatex

反思阶段要求：
在生成最终版本前，请：
1. 检查论证逻辑是否严密
2. 检查数据引用是否准确
3. 检查图表是否清晰
4. 检查语言是否学术规范
5. 检查格式是否符合期刊要求"""
    
    async def polish(
        self,
        research_results: Dict[str, Any],
        figures: List[Dict[str, Any]],
        tables: List[Dict[str, Any]],
        target_journal: Optional[str] = None,
    ) -> Manuscript:
        """
        执行手稿润色
        
        Args:
            research_results: 研究结果（来自前面的阶段）
            figures: 图表数据
            tables: 表格数据
            target_journal: 目标期刊（可选）
        
        Returns:
            润色后的完整手稿
        """
        agent = self._get_agent()
        
        # 构建润色提示
        prompt = self._build_polishing_prompt(
            research_results,
            figures,
            tables,
            target_journal,
        )
        
        # 第一轮：生成初稿
        response = await agent.run(prompt)
        draft = self._parse_manuscript(response)
        
        # 第二轮：反思与改进
        reflection_prompt = self._build_reflection_prompt(draft)
        reflection_response = await agent.run(reflection_prompt)
        
        # 第三轮：生成最终版本
        final_prompt = self._build_final_prompt(draft, reflection_response)
        final_response = await agent.run(final_prompt)
        
        return self._parse_manuscript(final_response)
    
    def _build_polishing_prompt(
        self,
        research_results: Dict[str, Any],
        figures: List[Dict[str, Any]],
        tables: List[Dict[str, Any]],
        target_journal: Optional[str],
    ) -> str:
        """构建润色提示"""
        journal_context = f"\n目标期刊: {target_journal}" if target_journal else ""
        
        figures_text = "\n".join(
            f"- 图 {i+1}: {f.get('title', '未命名')} ({f.get('type', 'figure')})"
            for i, f in enumerate(figures)
        )
        
        tables_text = "\n".join(
            f"- 表 {i+1}: {t.get('title', '未命名')}"
            for i, t in enumerate(tables)
        )
        
        return f"""请基于以下研究结果，撰写一篇完整的学术论文。

{journal_context}

研究结果：
{json.dumps(research_results, ensure_ascii=False, indent=2)}

图表：
{figures_text or '无'}

表格：
{tables_text or '无'}

请生成完整的 LaTeX 源码，包括：
1. 标题和摘要
2. 引言
3. 方法论
4. 实验结果
5. 讨论
6. 结论
7. 参考文献

请确保图表引用正确。"""
    
    def _build_reflection_prompt(self, draft: Manuscript) -> str:
        """构建反思提示"""
        return f"""请对以下论文初稿进行反思审查：

标题: {draft.title}
摘要: {draft.abstract[:200]}...

请从以下角度进行审查：
1. 论证逻辑是否严密？
2. 数据引用是否准确？
3. 图表是否清晰易懂？
4. 语言是否学术规范？
5. 格式是否符合要求？

请列出所有发现的问题，并提供修改建议。"""
    
    def _build_final_prompt(
        self,
        draft: Manuscript,
        reflection: Any,
    ) -> str:
        """构建最终版本提示"""
        reflection_text = reflection.text if hasattr(reflection, 'text') else str(reflection)
        
        return f"""请基于以下初稿和反思意见，生成最终版本的论文。

初稿 LaTeX 源码：
{draft.latex_source}

反思意见：
{reflection_text}

请修正所有问题，生成高质量的最终版本。"""
    
    def _parse_manuscript(self, response: Any) -> Manuscript:
        """解析手稿"""
        text = response.text if hasattr(response, 'text') else str(response)
        
        # 提取 LaTeX 源码
        latex_source = text
        if "```latex" in text:
            latex_source = text.split("```latex")[1].split("```")[0]
        elif "```" in text:
            latex_source = text.split("```")[1].split("```")[0]
        
        # 简化解析（实际应使用 LaTeX 解析器）
        return Manuscript(
            title="Generated Manuscript",
            abstract="",
            sections=[],
            latex_source=latex_source.strip(),
        )


# ============================================================================
# 同行评审委员会 (Peer Review Board)
# ============================================================================

class NoveltyReviewer(Executor):
    """
    新颖性审稿人
    
    负责评估论文的新颖性，硬性对比 SOTA。
    
    评审维度：
    - 与现有工作的差异化
    - 创新点的显著性
    - 对领域的贡献程度
    """
    
    def __init__(self, id: str = "novelty_reviewer"):
        super().__init__(id=id)
        self._agent: Optional[Agent] = None
    
    def _get_agent(self) -> Agent:
        if self._agent is None:
            client = OpenAIChatClient(
                model_id=settings.get_llm_config().model_name,
                api_key=settings.get_llm_config().api_key,
                base_url=settings.get_llm_config().base_url,
            )
            
            self._agent = Agent(
                client=client,
                name="novelty_reviewer",
                instructions="""你是一位专注于新颖性评估的审稿人。

你的评审重点：
1. 与现有 SOTA 的对比
2. 创新点的显著性
3. 技术贡献的原创性

评审标准：
- 8-10 分：重大创新，开辟新方向
- 6-7 分：有意义的改进
- 4-5 分：增量式贡献
- 0-3 分：缺乏新颖性

请严格对比现有工作，给出客观评价。""",
            )
        
        return self._agent
    
    @handler
    async def review(
        self,
        manuscript: Manuscript,
        ctx: WorkflowContext[IndividualReview],
    ) -> None:
        """执行新颖性评审"""
        agent = self._get_agent()
        
        prompt = f"""请评审以下论文的新颖性：

标题: {manuscript.title}
摘要: {manuscript.abstract}

请：
1. 识别论文的核心创新点
2. 对比现有 SOTA 工作
3. 评估创新显著性
4. 给出评分（0-10）和评审意见

请返回 JSON 格式的评审结果。"""
        
        response = await agent.run(prompt)
        review = self._parse_review(response, "novelty")
        
        await ctx.send_message(review)
    
    def _parse_review(self, response: Any, role: str) -> IndividualReview:
        """解析评审结果"""
        text = response.text if hasattr(response, 'text') else str(response)
        
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            
            data = json.loads(text.strip())
            
            return IndividualReview(
                reviewer_id=self.id,
                reviewer_role=role,
                scores=ReviewScore(
                    novelty=data.get("score", 5.0),
                ),
                comments=[
                    ReviewComment(
                        reviewer_id=self.id,
                        reviewer_role=role,
                        section_id=None,
                        comment=c.get("comment", ""),
                        severity=c.get("severity", "normal"),
                    )
                    for c in data.get("comments", [])
                ],
                verdict=ReviewVerdict(data.get("verdict", "minor_revision")),
            )
        except Exception:
            return IndividualReview(
                reviewer_id=self.id,
                reviewer_role=role,
                scores=ReviewScore(novelty=5.0),
                comments=[],
                verdict=ReviewVerdict.MINOR_REVISION,
            )


class MethodologyReviewer(Executor):
    """
    方法论审稿人
    
    负责审查统计严谨性和方法论正确性。
    
    评审维度：
    - 实验设计的合理性
    - 统计方法的正确性
    - 评估指标的全面性
    - 可复现性
    """
    
    def __init__(self, id: str = "methodology_reviewer"):
        super().__init__(id=id)
        self._agent: Optional[Agent] = None
    
    def _get_agent(self) -> Agent:
        if self._agent is None:
            client = OpenAIChatClient(
                model_id=settings.get_llm_config().model_name,
                api_key=settings.get_llm_config().api_key,
                base_url=settings.get_llm_config().base_url,
            )
            
            self._agent = Agent(
                client=client,
                name="methodology_reviewer",
                instructions="""你是一位专注于方法论审查的审稿人。

你的评审重点：
1. 实验设计是否合理
2. 统计方法是否正确
3. 评估指标是否全面
4. 结果是否可复现

常见问题：
- 样本量不足
- 统计检验误用
- 基线对比不公平
- 评估指标选择不当

请严格审查方法论，指出所有问题。""",
            )
        
        return self._agent
    
    @handler
    async def review(
        self,
        manuscript: Manuscript,
        ctx: WorkflowContext[IndividualReview],
    ) -> None:
        """执行方法论评审"""
        agent = self._get_agent()
        
        # 提取方法论章节
        method_section = next(
            (s for s in manuscript.sections if "method" in s.title.lower()),
            None,
        )
        
        prompt = f"""请审查以下论文的方法论：

标题: {manuscript.title}
方法论章节: {method_section.content if method_section else '未找到'}

请：
1. 检查实验设计
2. 审查统计方法
3. 评估指标选择
4. 检查可复现性
5. 给出评分（0-10）和修改建议

请返回 JSON 格式的评审结果。"""
        
        response = await agent.run(prompt)
        review = self._parse_review(response, "methodology")
        
        await ctx.send_message(review)
    
    def _parse_review(self, response: Any, role: str) -> IndividualReview:
        """解析评审结果"""
        text = response.text if hasattr(response, 'text') else str(response)
        
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            
            data = json.loads(text.strip())
            
            return IndividualReview(
                reviewer_id=self.id,
                reviewer_role=role,
                scores=ReviewScore(
                    methodology=data.get("score", 5.0),
                ),
                comments=[
                    ReviewComment(
                        reviewer_id=self.id,
                        reviewer_role=role,
                        section_id=c.get("section_id"),
                        comment=c.get("comment", ""),
                        severity=c.get("severity", "normal"),
                        suggestion=c.get("suggestion"),
                    )
                    for c in data.get("comments", [])
                ],
                verdict=ReviewVerdict(data.get("verdict", "minor_revision")),
            )
        except Exception:
            return IndividualReview(
                reviewer_id=self.id,
                reviewer_role=role,
                scores=ReviewScore(methodology=5.0),
                comments=[],
                verdict=ReviewVerdict.MINOR_REVISION,
            )


class ImpactReviewer(Executor):
    """
    影响力审稿人
    
    负责评估论文的潜在影响力。
    
    评审维度：
    - 对领域发展的推动作用
    - 实际应用价值
    - 对后续研究的启发
    """
    
    def __init__(self, id: str = "impact_reviewer"):
        super().__init__(id=id)
        self._agent: Optional[Agent] = None
    
    def _get_agent(self) -> Agent:
        if self._agent is None:
            client = OpenAIChatClient(
                model_id=settings.get_llm_config().model_name,
                api_key=settings.get_llm_config().api_key,
                base_url=settings.get_llm_config().base_url,
            )
            
            self._agent = Agent(
                client=client,
                name="impact_reviewer",
                instructions="""你是一位专注于影响力评估的审稿人。

你的评审重点：
1. 对领域发展的推动作用
2. 实际应用价值
3. 对后续研究的启发
4. 潜在的引用价值

评审标准：
- 8-10 分：重大影响，可能成为经典
- 6-7 分：有重要影响
- 4-5 分：有一定影响
- 0-3 分：影响有限

请客观评估论文的潜在影响力。""",
            )
        
        return self._agent
    
    @handler
    async def review(
        self,
        manuscript: Manuscript,
        ctx: WorkflowContext[IndividualReview],
    ) -> None:
        """执行影响力评审"""
        agent = self._get_agent()
        
        prompt = f"""请评估以下论文的影响力：

标题: {manuscript.title}
摘要: {manuscript.abstract}

请：
1. 评估对领域的推动作用
2. 分析实际应用价值
3. 预测对后续研究的启发
4. 给出评分（0-10）和理由

请返回 JSON 格式的评审结果。"""
        
        response = await agent.run(prompt)
        review = self._parse_review(response, "impact")
        
        await ctx.send_message(review)
    
    def _parse_review(self, response: Any, role: str) -> IndividualReview:
        """解析评审结果"""
        text = response.text if hasattr(response, 'text') else str(response)
        
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            
            data = json.loads(text.strip())
            
            return IndividualReview(
                reviewer_id=self.id,
                reviewer_role=role,
                scores=ReviewScore(
                    impact=data.get("score", 5.0),
                ),
                comments=[
                    ReviewComment(
                        reviewer_id=self.id,
                        reviewer_role=role,
                        section_id=None,
                        comment=c.get("comment", ""),
                    )
                    for c in data.get("comments", [])
                ],
                verdict=ReviewVerdict(data.get("verdict", "minor_revision")),
            )
        except Exception:
            return IndividualReview(
                reviewer_id=self.id,
                reviewer_role=role,
                scores=ReviewScore(impact=5.0),
                comments=[],
                verdict=ReviewVerdict.MINOR_REVISION,
            )


class EditorInChief(Executor):
    """
    主编/协调员
    
    负责聚合所有审稿人的意见，输出综合评审报告。
    
    职责：
    - 汇总各审稿人的分数
    - 解决评审意见冲突
    - 做出最终决定
    - 撰写编辑总结
    """
    
    def __init__(self, id: str = "editor_in_chief"):
        super().__init__(id=id)
        self._agent: Optional[Agent] = None
    
    def _get_agent(self) -> Agent:
        if self._agent is None:
            client = OpenAIChatClient(
                model_id=settings.get_llm_config().model_name,
                api_key=settings.get_llm_config().api_key,
                base_url=settings.get_llm_config().base_url,
            )
            
            self._agent = Agent(
                client=client,
                name="editor_in_chief",
                instructions="""你是期刊主编，负责综合所有审稿人的意见。

你的职责：
1. 汇总各审稿人的评分
2. 解决评审意见冲突
3. 做出最终决定
4. 撰写编辑总结

决策原则：
- 综合考虑所有审稿人的意见
- 重视方法论问题
- 平衡新颖性和影响力
- 给作者明确的修改指导

最终决定：
- Accept: 无需修改或仅需微小修改
- Minor Revision: 需要小修
- Major Revision: 需要大修
- Reject: 拒稿""",
            )
        
        return self._agent
    
    @handler
    async def consolidate(
        self,
        reviews: List[IndividualReview],  # 自动聚合
        ctx: WorkflowContext[Never, ConsolidatedReview],
    ) -> None:
        """
        聚合评审意见
        
        原生特性：接收聚合的评审结果列表
        """
        agent = self._get_agent()
        
        # 计算平均分数
        avg_scores = self._calculate_average_scores(reviews)
        
        # 构建聚合提示
        prompt = self._build_consolidation_prompt(reviews, avg_scores)
        
        # 调用 Agent
        response = await agent.run(prompt)
        
        # 解析综合报告
        consolidated = self._parse_consolidated(response, reviews, avg_scores)
        
        # 输出最终结果
        await ctx.yield_output(consolidated)
    
    def _calculate_average_scores(
        self,
        reviews: List[IndividualReview],
    ) -> ReviewScore:
        """计算平均分数"""
        if not reviews:
            return ReviewScore()
        
        novelty = sum(r.scores.novelty for r in reviews) / len(reviews)
        methodology = sum(r.scores.methodology for r in reviews) / len(reviews)
        impact = sum(r.scores.impact for r in reviews) / len(reviews)
        clarity = sum(r.scores.clarity for r in reviews) / len(reviews)
        overall = (novelty + methodology + impact + clarity) / 4
        
        return ReviewScore(
            novelty=novelty,
            methodology=methodology,
            impact=impact,
            clarity=clarity,
            overall=overall,
        )
    
    def _build_consolidation_prompt(
        self,
        reviews: List[IndividualReview],
        avg_scores: ReviewScore,
    ) -> str:
        """构建聚合提示"""
        reviews_text = "\n\n".join(
            f"审稿人 {r.reviewer_role}:\n"
            f"- 评分: {r.scores.novelty if r.reviewer_role == 'novelty' else r.scores.methodology if r.reviewer_role == 'methodology' else r.scores.impact}\n"
            f"- 结论: {r.verdict.value}\n"
            f"- 意见: {[c.comment for c in r.comments]}"
            for r in reviews
        )
        
        return f"""请综合以下审稿人的意见，做出最终决定：

{reviews_text}

平均分数：
- 新颖性: {avg_scores.novelty:.1f}
- 方法论: {avg_scores.methodology:.1f}
- 影响力: {avg_scores.impact:.1f}
- 总体: {avg_scores.overall:.1f}

请：
1. 汇总主要意见
2. 解决意见冲突
3. 做出最终决定
4. 撰写编辑总结
5. 列出修改要求

请返回 JSON 格式的综合评审报告。"""
    
    def _parse_consolidated(
        self,
        response: Any,
        reviews: List[IndividualReview],
        avg_scores: ReviewScore,
    ) -> ConsolidatedReview:
        """解析综合报告"""
        text = response.text if hasattr(response, 'text') else str(response)
        
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            
            data = json.loads(text.strip())
            
            # 聚合所有意见
            all_comments = []
            for r in reviews:
                all_comments.extend(r.comments)
            
            return ConsolidatedReview(
                manuscript_title="",
                individual_reviews=reviews,
                final_verdict=ReviewVerdict(data.get("verdict", "minor_revision")),
                final_scores=avg_scores,
                consolidated_comments=all_comments,
                revision_requirements=data.get("revision_requirements", []),
                editor_summary=data.get("editor_summary", ""),
            )
        except Exception:
            # 默认结论
            verdict = ReviewVerdict.MINOR_REVISION
            if avg_scores.overall >= 7:
                verdict = ReviewVerdict.ACCEPT
            elif avg_scores.overall >= 5:
                verdict = ReviewVerdict.MINOR_REVISION
            elif avg_scores.overall >= 3:
                verdict = ReviewVerdict.MAJOR_REVISION
            else:
                verdict = ReviewVerdict.REJECT
            
            return ConsolidatedReview(
                manuscript_title="",
                individual_reviews=reviews,
                final_verdict=verdict,
                final_scores=avg_scores,
                consolidated_comments=[],
                revision_requirements=[],
                editor_summary="",
            )


# ============================================================================
# 评审委员会工作流构建器
# ============================================================================

class PeerReviewBoardBuilder:
    """
    同行评审委员会工作流构建器
    
    构建固定编排的评审子图，完全隔离运行。
    
    原生特性：
    - 使用 WorkflowBuilder 构建固定拓扑
    - 使用 Fan-Out 并发执行评审
    - 使用 Fan-In 聚合评审结果
    - 完全隔离的子工作流
    """
    
    def build(self) -> Workflow:
        """
        构建评审委员会工作流
        
        拓扑结构：
        NoveltyReviewer ──┐
        MethodologyReviewer ──┼──> EditorInChief
        ImpactReviewer ──┘
        
        Returns:
            评审工作流
        """
        # 创建固定角色的审稿人
        novelty_reviewer = NoveltyReviewer()
        methodology_reviewer = MethodologyReviewer()
        impact_reviewer = ImpactReviewer()
        editor = EditorInChief()
        
        # 构建工作流
        # 原生特性：使用 WorkflowBuilder 构建固定拓扑
        builder = WorkflowBuilder(
            start_executor=novelty_reviewer,  # 起点可以是任意一个
            name="peer_review_board",
        )
        
        # Fan-Out: 并发评审
        # 原生特性：add_fan_out_edges 实现并发分发
        # 手稿会同时发送给三个审稿人
        builder = builder.add_fan_out_edges(
            source=novelty_reviewer,  # 这里简化处理，实际应使用分发器
            targets=[methodology_reviewer, impact_reviewer],
        )
        
        # Fan-In: 聚合评审结果
        # 原生特性：add_fan_in_edges 实现消息聚合
        # 所有评审结果聚合为列表，发送给主编
        builder = builder.add_fan_in_edges(
            sources=[novelty_reviewer, methodology_reviewer, impact_reviewer],
            target=editor,
        )
        
        return builder.build()


async def run_peer_review(
    manuscript: Manuscript,
) -> ConsolidatedReview:
    """
    运行同行评审
    
    高层 API，封装评审工作流的执行。
    
    Args:
        manuscript: 待评审的手稿
    
    Returns:
        综合评审报告
    """
    # 构建评审工作流
    builder = PeerReviewBoardBuilder()
    workflow = builder.build()
    
    # 执行工作流
    result = await workflow.run(manuscript)
    
    return result.get_output()
