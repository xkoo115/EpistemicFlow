"""
VLM（视觉语言模型）图表审查与润色整合模块

本模块实现：
1. VLM 图表审查：对实验生成的可视化图表进行美学和逻辑审查
2. 润色与整合智能体：将各阶段文本统一梳理，遵循学术排版标准导出

设计原则：
- 多模态理解：支持图像输入，理解图表语义
- 学术标准：遵循顶级期刊的图表规范
- 可解释性：提供详细的审查意见和改进建议
"""

from typing import Optional, Dict, Any, List, Sequence, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import base64
import json
from datetime import datetime

from pydantic import BaseModel, Field

from agents.base import (
    BaseResearchAgent,
    ModelClientFactory,
    LLMConfig,
    SessionManager,
    ResearchContextProvider,
)
from agents.schemas import DomainSurveyOutput
from core.config import settings


# ============================================================================
# 枚举和常量定义
# ============================================================================

class ReviewAspect(str, Enum):
    """审查维度枚举"""
    AESTHETICS = "aesthetics"           # 美学审查
    CLARITY = "clarity"                 # 清晰度审查
    ACCURACY = "accuracy"               # 准确性审查
    COMPLIANCE = "compliance"           # 规范合规审查
    ACCESSIBILITY = "accessibility"     # 可访问性审查


class ReviewVerdict(str, Enum):
    """审查结论枚举"""
    ACCEPT = "accept"                   # 接受
    MINOR_REVISION = "minor_revision"   # 小修
    MAJOR_REVISION = "major_revision"   # 大修
    REJECT = "reject"                   # 拒绝


class FigureType(str, Enum):
    """图表类型枚举"""
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    SCATTER_PLOT = "scatter_plot"
    HEATMAP = "heatmap"
    BOX_PLOT = "box_plot"
    VIOLIN_PLOT = "violin_plot"
    NETWORK_GRAPH = "network_graph"
    TABLE = "table"
    DIAGRAM = "diagram"
    OTHER = "other"


# ============================================================================
# Pydantic 模型定义
# ============================================================================

class FigureReviewScore(BaseModel):
    """图表审查评分"""
    aspect: ReviewAspect = Field(description="审查维度")
    score: float = Field(ge=0.0, le=10.0, description="评分（0-10）")
    rationale: str = Field(description="评分理由")
    suggestions: List[str] = Field(
        default_factory=list,
        description="改进建议",
    )


class FigureReviewOutput(BaseModel):
    """图表审查输出"""
    figure_id: str = Field(description="图表 ID")
    figure_type: FigureType = Field(description="图表类型")

    # 各维度评分
    scores: List[FigureReviewScore] = Field(
        default_factory=list,
        description="各维度评分",
    )

    # 综合评价
    overall_score: float = Field(
        ge=0.0,
        le=10.0,
        description="综合评分",
    )
    verdict: ReviewVerdict = Field(description="审查结论")

    # 详细意见
    strengths: List[str] = Field(
        default_factory=list,
        description="优点",
    )
    weaknesses: List[str] = Field(
        default_factory=list,
        description="缺点",
    )
    improvement_suggestions: List[str] = Field(
        default_factory=list,
        description="改进建议",
    )

    # 学术规范检查
    has_proper_labels: bool = Field(
        default=False,
        description="是否有正确的标签",
    )
    has_legend: bool = Field(
        default=False,
        description="是否有图例",
    )
    has_error_bars: bool = Field(
        default=False,
        description="是否有误差棒（如适用）",
    )
    colorblind_friendly: bool = Field(
        default=False,
        description="是否色盲友好",
    )

    # 元数据
    review_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="审查时间戳",
    )


class ManuscriptSection(BaseModel):
    """手稿章节"""
    section_id: str = Field(description="章节 ID")
    title: str = Field(description="章节标题")
    content: str = Field(description="章节内容")
    order: int = Field(description="章节顺序")
    word_count: int = Field(default=0, description="字数")
    figures: List[str] = Field(
        default_factory=list,
        description="引用的图表 ID",
    )
    references: List[str] = Field(
        default_factory=list,
        description="引用的文献 ID",
    )


class PolishedManuscript(BaseModel):
    """润色后的手稿"""
    title: str = Field(description="标题")
    abstract: str = Field(description="摘要")
    sections: List[ManuscriptSection] = Field(
        default_factory=list,
        description="章节列表",
    )
    conclusion: str = Field(description="结论")

    # 质量指标
    total_word_count: int = Field(default=0, description="总字数")
    coherence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="连贯性得分",
    )
    academic_style_score: float = Field(
        ge=0.0,
        le=1.0,
        description="学术风格得分",
    )

    # 元数据
    generation_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="生成时间戳",
    )


# ============================================================================
# VLM 图表审查智能体
# ============================================================================

class VLMFigureReviewer(BaseResearchAgent[FigureReviewOutput]):
    """
    VLM 图表审查智能体

    使用视觉语言模型对实验生成的图表进行多维度审查：
    - 美学审查：配色、布局、字体、分辨率
    - 清晰度审查：标签、图例、坐标轴、数据点
    - 准确性审查：数据表示、比例关系、误差处理
    - 规范合规审查：是否符合目标期刊要求
    - 可访问性审查：色盲友好、高对比度、可读性

    支持的图表格式：PNG, JPEG, SVG, PDF
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        session_manager: Optional[SessionManager] = None,
        target_journal: Optional[str] = None,
    ):
        """
        初始化 VLM 图表审查智能体

        Args:
            llm_config: LLM 配置（需要支持多模态）
            session_manager: 会话管理器
            target_journal: 目标期刊（用于规范检查）
        """
        super().__init__(
            name="vlm_figure_reviewer",
            llm_config=llm_config,
            session_manager=session_manager,
            instructions=self._default_instructions(),
        )
        self._target_journal = target_journal

    def _default_instructions(self) -> str:
        """默认系统指令"""
        return """你是一位资深的学术图表审查专家，拥有丰富的数据可视化和学术出版经验。

你的职责是对科研图表进行全面的审查，确保其符合顶级学术期刊的标准。

## 审查维度

### 1. 美学审查 (Aesthetics)
- 配色方案是否专业、协调
- 布局是否合理、平衡
- 字体大小和样式是否统一
- 分辨率是否满足出版要求（通常 300 DPI 以上）

### 2. 清晰度审查 (Clarity)
- 坐标轴标签是否清晰、完整
- 图例是否准确、易懂
- 数据点是否可辨识
- 是否有必要的注释和说明

### 3. 准确性审查 (Accuracy)
- 数据表示是否准确无误
- 比例关系是否正确
- 误差棒/置信区间是否正确显示
- 统计显著性标记是否正确

### 4. 规范合规审查 (Compliance)
- 是否符合目标期刊的图表规范
- 图表尺寸是否符合要求
- 文件格式是否正确
- 命名是否规范

### 5. 可访问性审查 (Accessibility)
- 是否色盲友好（避免红绿对比）
- 对比度是否足够
- 在灰度模式下是否可读
- 是否有文字替代说明

## 输出要求

请以 JSON 格式输出审查结果，包含：
1. 各维度的评分（0-10 分）和详细理由
2. 综合评分和审查结论（接受/小修/大修/拒绝）
3. 具体的改进建议
4. 学术规范检查结果

审查时要严格、公正，同时提供建设性的改进建议。"""

    def _encode_image(self, image_path: str) -> str:
        """
        将图像编码为 base64

        Args:
            image_path: 图像文件路径

        Returns:
            base64 编码的图像数据
        """
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _detect_figure_type(self, image_path: str) -> FigureType:
        """
        检测图表类型

        Args:
            image_path: 图像文件路径

        Returns:
            图表类型枚举
        """
        # 简单的文件名启发式检测
        filename = Path(image_path).stem.lower()

        if "line" in filename or "curve" in filename:
            return FigureType.LINE_CHART
        elif "bar" in filename or "histogram" in filename:
            return FigureType.BAR_CHART
        elif "scatter" in filename:
            return FigureType.SCATTER_PLOT
        elif "heatmap" in filename or "correlation" in filename:
            return FigureType.HEATMAP
        elif "box" in filename:
            return FigureType.BOX_PLOT
        elif "violin" in filename:
            return FigureType.VIOLIN_PLOT
        elif "network" in filename or "graph" in filename:
            return FigureType.NETWORK_GRAPH
        elif "table" in filename:
            return FigureType.TABLE
        elif "diagram" in filename or "flowchart" in filename:
            return FigureType.DIAGRAM
        else:
            return FigureType.OTHER

    async def review_figure(
        self,
        figure_path: str,
        figure_id: Optional[str] = None,
        context: Optional[str] = None,
    ) -> FigureReviewOutput:
        """
        审查图表

        Args:
            figure_path: 图表文件路径
            figure_id: 图表 ID（可选）
            context: 图表上下文说明（可选）

        Returns:
            图表审查输出
        """
        from agent_framework import Message, Content

        # 确保会话已初始化
        if self._current_session is None:
            await self.initialize_session()

        # 编码图像
        image_base64 = self._encode_image(figure_path)

        # 检测图表类型
        figure_type = self._detect_figure_type(figure_path)

        # 构建审查提示词
        prompt = f"""请审查以下学术图表。

图表 ID: {figure_id or Path(figure_path).stem}
图表类型: {figure_type.value}
"""
        if context:
            prompt += f"\n图表上下文: {context}\n"

        if self._target_journal:
            prompt += f"\n目标期刊: {self._target_journal}\n"

        prompt += "\n请提供详细的审查意见和改进建议。"

        # 构建消息（包含图像）
        messages = [
            Message(
                role="user",
                contents=[
                    Content.from_text(prompt),
                    Content.from_uri(f"data:image/png;base64,{image_base64}", media_type="image/png"),
                ],
            )
        ]

        # 获取聊天选项（强制 JSON 输出）
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "figure_review_output",
                "schema": FigureReviewOutput.model_json_schema(),
                "strict": True,
            }
        }
        options = ModelClientFactory.get_chat_options(
            self._llm_config,
            response_format=response_format,
        )

        # 调用模型
        response = await self._agent.client.get_response(
            messages=messages,
            options=options,
        )

        # 解析输出
        if response.messages:
            content = response.messages[0].contents[0].text
            return FigureReviewOutput.model_validate_json(content)

        # 返回默认值
        return FigureReviewOutput(
            figure_id=figure_id or Path(figure_path).stem,
            figure_type=figure_type,
            verdict=ReviewVerdict.MAJOR_REVISION,
        )

    async def batch_review(
        self,
        figure_paths: List[str],
        contexts: Optional[Dict[str, str]] = None,
    ) -> List[FigureReviewOutput]:
        """
        批量审查图表

        Args:
            figure_paths: 图表文件路径列表
            contexts: 图表上下文映射 {figure_id: context}

        Returns:
            审查结果列表
        """
        results = []
        contexts = contexts or {}

        for path in figure_paths:
            figure_id = Path(path).stem
            context = contexts.get(figure_id)
            result = await self.review_figure(path, figure_id, context)
            results.append(result)

        return results


# ============================================================================
# 润色与整合智能体
# ============================================================================

class IntegrationPolishingAgent(BaseResearchAgent[PolishedManuscript]):
    """
    润色与整合智能体

    负责将各阶段生成的文本内容统一梳理，生成符合学术标准的最终手稿。

    核心功能：
    - 逻辑流梳理：确保章节之间的逻辑连贯性
    - 语言润色：提升学术写作质量
    - 格式规范：遵循目标期刊的排版要求
    - 引用整合：统一管理参考文献
    - 图表整合：确保图表引用正确
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        session_manager: Optional[SessionManager] = None,
        target_journal: Optional[str] = None,
        style_guide: Optional[str] = None,
    ):
        """
        初始化润色与整合智能体

        Args:
            llm_config: LLM 配置
            session_manager: 会话管理器
            target_journal: 目标期刊
            style_guide: 风格指南（如 APA, IEEE, Nature）
        """
        self._target_journal = target_journal
        self._style_guide = style_guide or "APA"
        super().__init__(
            name="integration_polishing_agent",
            llm_config=llm_config,
            session_manager=session_manager,
            instructions=self._default_instructions(),
        )

    def _default_instructions(self) -> str:
        """默认系统指令"""
        return f"""你是一位资深的学术写作专家和编辑，精通各类学术期刊的写作规范。

你的职责是将科研过程中生成的各阶段内容整合润色，生成高质量的学术手稿。

## 核心任务

### 1. 逻辑流梳理
- 确保章节之间的逻辑连贯性
- 检查论证链条的完整性
- 优化段落结构和过渡
- 消除冗余和重复

### 2. 语言润色
- 提升学术写作的专业性
- 确保术语使用准确一致
- 改善句式多样性
- 提高可读性和流畅度

### 3. 格式规范
- 遵循 {self._style_guide} 风格指南
- 符合目标期刊的排版要求
- 统一标题层级和编号
- 规范图表和公式格式

### 4. 引用整合
- 统一参考文献格式
- 检查引用的完整性
- 消除重复引用
- 确保引用顺序正确

### 5. 图表整合
- 确保图表引用正确
- 检查图表编号连续性
- 优化图表位置
- 补量图表与文字的平衡

## 输出要求

请以 JSON 格式输出润色后的手稿，包含：
1. 标题和摘要
2. 结构化的章节列表
3. 结论
4. 质量指标（字数、连贯性得分、学术风格得分）

确保输出符合学术出版的高标准。"""

    async def polish_manuscript(
        self,
        domain_survey: DomainSurveyOutput,
        figure_reviews: Optional[List[FigureReviewOutput]] = None,
        additional_sections: Optional[List[ManuscriptSection]] = None,
        custom_instructions: Optional[str] = None,
    ) -> PolishedManuscript:
        """
        润色手稿

        Args:
            domain_survey: 领域综述输出
            figure_reviews: 图表审查结果
            additional_sections: 额外章节
            custom_instructions: 自定义指令

        Returns:
            润色后的手稿
        """
        from agent_framework import Message, Content

        # 确保会话已初始化
        if self._current_session is None:
            await self.initialize_session()

        # 构建输入内容
        input_content = f"""请将以下领域综述内容整合润色为完整的学术手稿。

## 原始内容

### 标题
{domain_survey.title}

### 摘要
{domain_survey.abstract}

### 引言
{domain_survey.introduction}

### 方法论综述
{domain_survey.methodology_review}

### 当前挑战
{chr(10).join(f'- {c}' for c in domain_survey.current_challenges)}

### 未来方向
{chr(10).join(f'- {d}' for d in domain_survey.future_directions)}

### 结论
{domain_survey.conclusion}
"""

        # 添加图表审查信息
        if figure_reviews:
            input_content += "\n## 图表审查结果\n"
            for review in figure_reviews:
                input_content += f"\n### 图表 {review.figure_id}\n"
                input_content += f"- 类型: {review.figure_type.value}\n"
                input_content += f"- 综合评分: {review.overall_score:.1f}/10\n"
                input_content += f"- 审查结论: {review.verdict.value}\n"
                if review.improvement_suggestions:
                    input_content += "- 改进建议:\n"
                    for sug in review.improvement_suggestions:
                        input_content += f"  - {sug}\n"

        # 添加额外章节
        if additional_sections:
            input_content += "\n## 额外章节\n"
            for section in additional_sections:
                input_content += f"\n### {section.title}\n"
                input_content += section.content + "\n"

        # 添加自定义指令
        if custom_instructions:
            input_content += f"\n## 特殊要求\n{custom_instructions}\n"

        # 添加目标期刊信息
        if self._target_journal:
            input_content += f"\n## 目标期刊\n{self._target_journal}\n"

        # 构建消息
        messages = [Message(role="user", contents=[Content.from_text(input_content)])]

        # 获取聊天选项
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "polished_manuscript",
                "schema": PolishedManuscript.model_json_schema(),
                "strict": True,
            }
        }
        options = ModelClientFactory.get_chat_options(
            self._llm_config,
            response_format=response_format,
        )

        # 调用模型
        response = await self._agent.client.get_response(
            messages=messages,
            options=options,
        )

        # 解析输出
        if response.messages:
            content = response.messages[0].contents[0].text
            return PolishedManuscript.model_validate_json(content)

        # 返回默认值
        return PolishedManuscript(
            title=domain_survey.title,
            abstract=domain_survey.abstract,
            conclusion=domain_survey.conclusion,
        )

    async def export_to_markdown(
        self,
        manuscript: PolishedManuscript,
        output_path: str,
    ) -> str:
        """
        导出为 Markdown 格式

        Args:
            manuscript: 润色后的手稿
            output_path: 输出路径

        Returns:
            Markdown 文本
        """
        md_content = f"""# {manuscript.title}

## 摘要

{manuscript.abstract}

"""

        # 添加章节
        for section in sorted(manuscript.sections, key=lambda s: s.order):
            md_content += f"## {section.title}\n\n{section.content}\n\n"

        # 添加结论
        md_content += f"""## 结论

{manuscript.conclusion}

---

*生成时间: {manuscript.generation_timestamp}*
*总字数: {manuscript.total_word_count}*
*连贯性得分: {manuscript.coherence_score:.2f}*
*学术风格得分: {manuscript.academic_style_score:.2f}*
"""

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return md_content

    async def export_to_latex(
        self,
        manuscript: PolishedManuscript,
        output_path: str,
    ) -> str:
        """
        导出为 LaTeX 格式

        Args:
            manuscript: 润色后的手稿
            output_path: 输出路径

        Returns:
            LaTeX 文本
        """
        latex_content = f"""\\documentclass{{article}}
\\usepackage{{graphicx}}
\\usepackage{{amsmath}}
\\usepackage{{hyperref}}

\\title{{{manuscript.title}}}
\\author{{EpistemicFlow}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

\\begin{{abstract}}
{manuscript.abstract}
\\end{{abstract}}

"""

        # 添加章节
        for section in sorted(manuscript.sections, key=lambda s: s.order):
            latex_content += f"\\section{{{section.title}}}\n\n{section.content}\n\n"

        # 添加结论
        latex_content += f"""\\section{{结论}}

{manuscript.conclusion}

\\end{{document}}
"""

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(latex_content)

        return latex_content


# ============================================================================
# 便捷函数
# ============================================================================

async def review_figure_with_vlm(
    figure_path: str,
    llm_config: Optional[LLMConfig] = None,
    target_journal: Optional[str] = None,
) -> FigureReviewOutput:
    """
    使用 VLM 审查图表（便捷函数）

    Args:
        figure_path: 图表文件路径
        llm_config: LLM 配置
        target_journal: 目标期刊

    Returns:
        图表审查输出
    """
    config = llm_config or settings.get_llm_config()
    reviewer = VLMFigureReviewer(config, target_journal=target_journal)
    return await reviewer.review_figure(figure_path)


async def polish_research_manuscript(
    domain_survey: DomainSurveyOutput,
    llm_config: Optional[LLMConfig] = None,
    target_journal: Optional[str] = None,
) -> PolishedManuscript:
    """
    润色研究手稿（便捷函数）

    Args:
        domain_survey: 领域综述输出
        llm_config: LLM 配置
        target_journal: 目标期刊

    Returns:
        润色后的手稿
    """
    config = llm_config or settings.get_llm_config()
    agent = IntegrationPolishingAgent(config, target_journal=target_journal)
    return await agent.polish_manuscript(domain_survey)
