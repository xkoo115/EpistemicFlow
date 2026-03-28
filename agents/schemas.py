"""
Pydantic 输出模型定义

本模块定义所有智能体的结构化输出模型，用于：
- 强制模型返回符合预期的 JSON 格式
- 提供类型安全和数据验证
- 支持思维链 (Chain of Thought) 输出

设计原则：
- 所有输出模型继承自 Pydantic BaseModel
- 使用 Field 提供详细的字段描述，帮助模型理解输出要求
- 枚举类型用于约束输出范围
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# 阶段一：意图捕获与双轨分类
# ============================================================================

class PaperType(str, Enum):
    """
    论文类型枚举

    用于双轨分类机制，区分用户意图：
    - RESEARCH_PAPER: 原创研究论文（提出新方法、新理论、新实验）
    - SURVEY_PAPER: 综述论文（系统梳理某一领域的研究现状）
    """
    RESEARCH_PAPER = "research_paper"
    SURVEY_PAPER = "survey_paper"


class ClassificationReasoning(BaseModel):
    """
    分类推理过程

    记录思维链 (Chain of Thought) 推理过程，确保分类决策的可解释性。
    """
    key_indicators: List[str] = Field(
        default_factory=list,
        description="识别出的关键指标，如'提出新方法'、'对比分析'、'系统性综述'等",
    )
    reasoning_steps: List[str] = Field(
        default_factory=list,
        description="推理步骤，逐步解释如何得出分类结论",
    )
    confidence_factors: List[str] = Field(
        default_factory=list,
        description="影响置信度的因素，如'明确的方法论描述'、'缺少实验设计'等",
    )


class IdeationOutput(BaseModel):
    """
    构思智能体输出模型

    这是 IdeationAgent 的核心输出结构，包含：
    - 二元分类结果（研究论文 vs 综述论文）
    - 分类依据（思维链推理）
    - 提取的研究主题和关键词

    使用 Pydantic 确保输出格式的一致性，便于后续工作流处理。
    """
    # 核心分类结果
    paper_type: PaperType = Field(
        description="论文类型分类：research_paper（原创研究）或 survey_paper（综述）",
    )

    # 分类置信度
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="分类置信度，范围 [0, 1]，越高表示越确定",
    )

    # 思维链推理
    reasoning: ClassificationReasoning = Field(
        description="分类推理过程，包含关键指标、推理步骤和置信度因素",
    )

    # 提取的研究信息
    research_topic: str = Field(
        description="识别出的研究主题或问题",
    )

    keywords: List[str] = Field(
        default_factory=list,
        description="提取的关键词列表，用于后续文献检索",
    )

    # 可选的补充信息
    research_questions: Optional[List[str]] = Field(
        default=None,
        description="识别出的研究问题（针对研究论文）",
    )

    survey_scope: Optional[str] = Field(
        default=None,
        description="综述范围描述（针对综述论文）",
    )

    # 原始输入摘要
    input_summary: str = Field(
        description="用户输入的简要摘要",
    )

    class Config:
        """Pydantic 配置"""
        json_schema_extra = {
            "example": {
                "paper_type": "research_paper",
                "confidence": 0.85,
                "reasoning": {
                    "key_indicators": ["提出新方法", "包含实验设计", "有创新点描述"],
                    "reasoning_steps": [
                        "1. 分析用户输入，识别关键意图",
                        "2. 发现'提出一种新的深度学习架构'，表明是原创研究",
                        "3. 包含实验对比和性能评估，进一步确认",
                    ],
                    "confidence_factors": ["明确的创新点", "完整的实验设计"],
                },
                "research_topic": "基于注意力机制的图像分类方法研究",
                "keywords": ["深度学习", "注意力机制", "图像分类", "卷积神经网络"],
                "research_questions": [
                    "如何设计更高效的注意力机制？",
                    "新方法在标准数据集上的性能如何？",
                ],
                "input_summary": "用户希望研究一种新的基于注意力机制的图像分类方法",
            }
        }


# ============================================================================
# 阶段二：动态文献调研与规划编排
# ============================================================================

class LiteratureSource(str, Enum):
    """
    文献来源枚举
    """
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    GOOGLE_SCHOLAR = "google_scholar"
    LOCAL_DATABASE = "local_database"


class PaperMetadata(BaseModel):
    """
    论文元数据

    存储单篇论文的基本信息。
    """
    title: str = Field(description="论文标题")
    authors: List[str] = Field(default_factory=list, description="作者列表")
    abstract: Optional[str] = Field(default=None, description="摘要")
    publication_year: Optional[int] = Field(default=None, description="发表年份")
    venue: Optional[str] = Field(default=None, description="发表 venue（期刊/会议）")
    doi: Optional[str] = Field(default=None, description="DOI")
    url: Optional[str] = Field(default=None, description="论文链接")
    citation_count: Optional[int] = Field(default=None, description="引用次数")
    source: LiteratureSource = Field(
        default=LiteratureSource.ARXIV,
        description="文献来源",
    )
    relevance_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="相关性得分",
    )


class LiteratureSubset(BaseModel):
    """
    文献子集

    用于 Map-Reduce 架构中，将文献集合分割为多个子集，
    分配给不同的 SubResearcherAgent 并行处理。
    """
    subset_id: str = Field(description="子集唯一标识")
    papers: List[PaperMetadata] = Field(
        default_factory=list,
        description="子集中的论文列表",
    )
    theme: Optional[str] = Field(
        default=None,
        description="子集主题（用于主题分组）",
    )
    estimated_tokens: Optional[int] = Field(
        default=None,
        description="预估 token 数量",
    )


class SubResearcherOutput(BaseModel):
    """
    助理研究员智能体输出

    SubResearcherAgent 处理单个文献子集后的输出结果。
    """
    subset_id: str = Field(description="处理的子集 ID")
    agent_id: str = Field(description="智能体实例 ID")

    # 分析结果
    key_findings: List[str] = Field(
        default_factory=list,
        description="关键发现列表",
    )
    methodologies: List[str] = Field(
        default_factory=list,
        description="识别出的方法论",
    )
    research_gaps: List[str] = Field(
        default_factory=list,
        description="发现的研究空白",
    )
    trends: List[str] = Field(
        default_factory=list,
        description="识别出的研究趋势",
    )

    # 质量指标
    papers_analyzed: int = Field(
        default=0,
        description="分析的论文数量",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="分析置信度",
    )

    # 原始响应（用于调试）
    raw_summary: Optional[str] = Field(
        default=None,
        description="原始分析摘要",
    )


class AggregatedResearchState(BaseModel):
    """
    聚合研究状态

    Reduce 阶段的输出，汇总所有 SubResearcherAgent 的结果。
    """
    # 聚合统计
    total_papers: int = Field(default=0, description="总论文数")
    total_subsets: int = Field(default=0, description="总子集数")
    successful_analyses: int = Field(default=0, description="成功分析数")

    # 聚合内容
    all_key_findings: List[str] = Field(
        default_factory=list,
        description="所有关键发现（去重后）",
    )
    all_methodologies: List[str] = Field(
        default_factory=list,
        description="所有方法论（去重后）",
    )
    all_research_gaps: List[str] = Field(
        default_factory=list,
        description="所有研究空白（去重后）",
    )
    all_trends: List[str] = Field(
        default_factory=list,
        description="所有研究趋势（去重后）",
    )

    # 子结果引用
    sub_results: Dict[str, SubResearcherOutput] = Field(
        default_factory=dict,
        description="各子集的分析结果，key 为 subset_id",
    )

    # 元数据
    processing_time_ms: Optional[float] = Field(
        default=None,
        description="总处理时间（毫秒）",
    )


class DomainSurveyOutput(BaseModel):
    """
    领域现状综述输出

    LeadResearcherAgent 生成的最终综述报告。
    """
    # 综述标题和摘要
    title: str = Field(description="综述标题")
    abstract: str = Field(description="综述摘要")

    # 结构化内容
    introduction: str = Field(description="引言部分")
    methodology_review: str = Field(description="方法论综述")
    current_challenges: List[str] = Field(
        default_factory=list,
        description="当前挑战",
    )
    future_directions: List[str] = Field(
        default_factory=list,
        description="未来研究方向",
    )
    conclusion: str = Field(description="结论")

    # 参考文献
    key_references: List[PaperMetadata] = Field(
        default_factory=list,
        description="关键参考文献",
    )

    # 质量指标
    coverage_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="覆盖度得分",
    )
    coherence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="连贯性得分",
    )


# ============================================================================
# 工作流状态模型
# ============================================================================

class WorkflowStageOutput(BaseModel):
    """
    工作流阶段输出

    记录单个工作流阶段的执行结果。
    """
    stage_name: str = Field(description="阶段名称")
    success: bool = Field(description="是否成功")
    output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="阶段输出数据",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="错误信息（如果失败）",
    )
    processing_time_ms: float = Field(
        default=0.0,
        description="处理时间（毫秒）",
    )


# ============================================================================
# 辅助函数
# ============================================================================

def get_ideation_response_format() -> Dict[str, Any]:
    """
    获取 IdeationOutput 的 JSON Schema

    用于传递给模型客户端，强制结构化输出。

    Returns:
        OpenAI 兼容的 response_format 字典
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ideation_output",
            "schema": IdeationOutput.model_json_schema(),
            "strict": True,
        }
    }


def get_sub_researcher_response_format() -> Dict[str, Any]:
    """
    获取 SubResearcherOutput 的 JSON Schema
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "sub_researcher_output",
            "schema": SubResearcherOutput.model_json_schema(),
            "strict": True,
        }
    }


def get_domain_survey_response_format() -> Dict[str, Any]:
    """
    获取 DomainSurveyOutput 的 JSON Schema
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "domain_survey_output",
            "schema": DomainSurveyOutput.model_json_schema(),
            "strict": True,
        }
    }


def parse_ideation_output(json_str: str) -> IdeationOutput:
    """
    解析 IdeationOutput JSON 字符串

    Args:
        json_str: JSON 字符串

    Returns:
        解析后的 IdeationOutput 对象

    Raises:
        ValidationError: 如果 JSON 不符合模型定义
    """
    return IdeationOutput.model_validate_json(json_str)


def parse_sub_researcher_output(json_str: str) -> SubResearcherOutput:
    """
    解析 SubResearcherOutput JSON 字符串
    """
    return SubResearcherOutput.model_validate_json(json_str)


def parse_domain_survey_output(json_str: str) -> DomainSurveyOutput:
    """
    解析 DomainSurveyOutput JSON 字符串
    """
    return DomainSurveyOutput.model_validate_json(json_str)
