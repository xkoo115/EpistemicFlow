"""
EpistemicFlow 智能体模块

本模块提供多智能体系统的核心组件，包括：

阶段一：意图捕获与双轨分类
- IdeationAgent: 构思智能体，负责理解用户意图并分类

阶段二：动态文献调研与规划编排 (Map-Reduce)
- LeadResearcherAgent: 首席研究员智能体，负责协调和综述生成
- SubResearcherAgent: 助理研究员智能体，负责并行文献分析

基础设施：
- ModelClientFactory: 模型客户端工厂
- SessionManager: 会话管理器
- ResearchContextProvider: 科研上下文提供者
- AgentManager: 智能体管理器
"""

# 基础设施
from agents.base import (
    ModelClientFactory,
    SessionManager,
    AgentSessionInfo,
    ResearchContextProvider,
    BaseResearchAgent,
    AgentManager,
)

# 输出模型
from agents.schemas import (
    PaperType,
    ClassificationReasoning,
    IdeationOutput,
    LiteratureSource,
    PaperMetadata,
    LiteratureSubset,
    SubResearcherOutput,
    AggregatedResearchState,
    DomainSurveyOutput,
    WorkflowStageOutput,
    get_ideation_response_format,
    get_sub_researcher_response_format,
    get_domain_survey_response_format,
    parse_ideation_output,
    parse_sub_researcher_output,
    parse_domain_survey_output,
)

# 构思智能体
from agents.ideation import (
    IdeationAgent,
    IdeationBatchProcessor,
    create_ideation_agent,
)

# 研究智能体
from agents.research import (
    PartitionConfig,
    TaskDistributor,
    SubResearcherAgent,
    LeadResearcherAgent,
    create_lead_researcher_agent,
    create_sub_researcher_agent,
)

__all__ = [
    # 基础设施
    "ModelClientFactory",
    "SessionManager",
    "AgentSessionInfo",
    "ResearchContextProvider",
    "BaseResearchAgent",
    "AgentManager",
    # 输出模型
    "PaperType",
    "ClassificationReasoning",
    "IdeationOutput",
    "LiteratureSource",
    "PaperMetadata",
    "LiteratureSubset",
    "SubResearcherOutput",
    "AggregatedResearchState",
    "DomainSurveyOutput",
    "WorkflowStageOutput",
    "get_ideation_response_format",
    "get_sub_researcher_response_format",
    "get_domain_survey_response_format",
    "parse_ideation_output",
    "parse_sub_researcher_output",
    "parse_domain_survey_output",
    # 构思智能体
    "IdeationAgent",
    "IdeationBatchProcessor",
    "create_ideation_agent",
    # 研究智能体
    "PartitionConfig",
    "TaskDistributor",
    "SubResearcherAgent",
    "LeadResearcherAgent",
    "create_lead_researcher_agent",
    "create_sub_researcher_agent",
]
