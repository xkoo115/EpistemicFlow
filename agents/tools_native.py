"""
原生工具注册模块 (Native Tool Calling)

本模块利用 agent_framework 的原生 @tool 装饰器，将文献检索功能封装为标准工具。
大模型将自主决定何时调用工具、如何传递参数，彻底废弃之前的手动调用逻辑。

核心变更：
- 使用 @tool 装饰器替代手动函数调用
- 工具结果作为原生 ToolMessage 返回给环境
- LLM 拥有完全的调用自主权

设计原则：
- 单一职责：每个工具专注于单一功能
- 类型安全：使用 Pydantic 模型定义输入/输出
- 可观测性：工具调用自动进入事件流
"""

from typing import Annotated, Optional, List, Dict, Any
from pydantic import BaseModel, Field

from agent_framework import tool, FunctionTool

from tools.literature import (
    SemanticScholarClient,
    ArxivClient,
    LiteratureSearchTool,
)
from agents.schemas import PaperMetadata


# ============================================================================
# 工具输入模型定义 (Pydantic)
# ============================================================================

class SemanticScholarSearchInput(BaseModel):
    """Semantic Scholar 搜索工具输入模型"""
    query: Annotated[str, Field(
        description="搜索查询字符串，可以是关键词、短语或论文标题"
    )]
    limit: Annotated[int, Field(
        default=20,
        ge=1,
        le=100,
        description="返回结果数量限制，默认20，最大100"
    )]
    year_range: Annotated[Optional[tuple[int, int]], Field(
        default=None,
        description="年份范围过滤，格式为 (起始年份, 结束年份)"
    )] = None


class ArxivSearchInput(BaseModel):
    """arXiv 搜索工具输入模型"""
    query: Annotated[str, Field(
        description="arXiv 搜索查询，支持复杂语法如 'au:作者名 AND ti:标题关键词'"
    )]
    max_results: Annotated[int, Field(
        default=20,
        ge=1,
        le=100,
        description="最大返回结果数"
    )]
    sort_by: Annotated[str, Field(
        default="relevance",
        description="排序方式：relevance(相关性), submittedDate(提交日期), lastUpdatedDate(更新日期)"
    )] = "relevance"


class UnifiedLiteratureSearchInput(BaseModel):
    """统一文献检索工具输入模型"""
    query: Annotated[str, Field(
        description="研究主题或关键词"
    )]
    sources: Annotated[List[str], Field(
        default=["semantic_scholar", "arxiv"],
        description="检索源列表，可选值：semantic_scholar, arxiv"
    )]
    limit_per_source: Annotated[int, Field(
        default=10,
        ge=1,
        le=50,
        description="每个检索源的结果数量限制"
    )]
    deduplicate: Annotated[bool, Field(
        default=True,
        description="是否对结果去重"
    )] = True


# ============================================================================
# 原生工具定义 (使用 @tool 装饰器)
# ============================================================================

# 初始化底层客户端（延迟初始化，避免模块加载时创建连接）
_semantic_scholar_client: Optional[SemanticScholarClient] = None
_arxiv_client: Optional[ArxivClient] = None
_unified_tool: Optional[LiteratureSearchTool] = None


def _get_semantic_scholar_client() -> SemanticScholarClient:
    """获取 Semantic Scholar 客户端（单例）"""
    global _semantic_scholar_client
    if _semantic_scholar_client is None:
        _semantic_scholar_client = SemanticScholarClient()
    return _semantic_scholar_client


def _get_arxiv_client() -> ArxivClient:
    """获取 arXiv 客户端（单例）"""
    global _arxiv_client
    if _arxiv_client is None:
        _arxiv_client = ArxivClient()
    return _arxiv_client


def _get_unified_tool() -> LiteratureSearchTool:
    """获取统一检索工具（单例）"""
    global _unified_tool
    if _unified_tool is None:
        _unified_tool = LiteratureSearchTool()
    return _unified_tool


@tool(approval_mode="never_require")
async def search_semantic_scholar(
    query: Annotated[str, "搜索查询字符串"],
    limit: Annotated[int, "返回结果数量"] = 20,
    year_start: Annotated[Optional[int], "起始年份"] = None,
    year_end: Annotated[Optional[int], "结束年份"] = None,
) -> str:
    """
    使用 Semantic Scholar API 搜索学术论文。
    
    Semantic Scholar 是一个免费的学术搜索引擎，提供丰富的论文元数据和引用关系。
    适用于搜索已发表的学术论文、获取引用信息、查找相关研究。
    
    Args:
        query: 搜索查询，可以是关键词、论文标题或作者名
        limit: 返回结果数量，默认20
        year_start: 起始年份过滤（可选）
        year_end: 结束年份过滤（可选）
    
    Returns:
        JSON 格式的搜索结果，包含论文标题、作者、摘要、年份、引用数等信息
    """
    import json
    
    client = _get_semantic_scholar_client()
    
    # 构建年份范围
    year_range = None
    if year_start is not None and year_end is not None:
        year_range = (year_start, year_end)
    
    # 执行搜索
    papers = await client.search(
        query=query,
        limit=limit,
        year_range=year_range,
    )
    
    # 转换为 JSON 字符串返回
    # 注意：agent_framework 会将此字符串作为 ToolMessage 返回
    result = {
        "source": "semantic_scholar",
        "query": query,
        "count": len(papers),
        "papers": [
            {
                "title": p.title,
                "authors": p.authors,
                "year": p.publication_year,
                "abstract": p.abstract,
                "venue": p.venue,
                "doi": p.doi,
                "url": p.url,
                "citation_count": p.citation_count,
            }
            for p in papers
        ]
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool(approval_mode="never_require")
async def search_arxiv(
    query: Annotated[str, "arXiv 搜索查询"],
    max_results: Annotated[int, "最大结果数"] = 20,
    sort_by: Annotated[str, "排序方式"] = "relevance",
) -> str:
    """
    使用 arXiv API 搜索预印本论文。
    
    arXiv 是物理学、数学、计算机科学等领域的预印本服务器。
    适用于搜索最新研究成果、尚未正式发表的论文。
    
    支持的查询语法：
    - ti:标题关键词 - 搜索标题
    - au:作者名 - 搜索作者
    - abs:摘要关键词 - 搜索摘要
    - cat:类别 - 按类别过滤（如 cs.AI, cs.LG）
    - 组合查询：ti:machine learning AND au:Smith
    
    Args:
        query: 搜索查询，支持复杂语法
        max_results: 最大返回结果数，默认20
        sort_by: 排序方式 (relevance/submittedDate/lastUpdatedDate)
    
    Returns:
        JSON 格式的搜索结果
    """
    import json
    
    client = _get_arxiv_client()
    
    # 执行搜索
    papers = await client.search(
        query=query,
        max_results=max_results,
        sort_by=sort_by,
    )
    
    # 转换为 JSON 字符串返回
    result = {
        "source": "arxiv",
        "query": query,
        "count": len(papers),
        "papers": [
            {
                "title": p.title,
                "authors": p.authors,
                "year": p.publication_year,
                "abstract": p.abstract,
                "arxiv_id": p.arxiv_id,
                "url": p.url,
                "categories": p.categories if hasattr(p, 'categories') else [],
            }
            for p in papers
        ]
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool(approval_mode="never_require")
async def search_literature_unified(
    query: Annotated[str, "研究主题或关键词"],
    sources: Annotated[List[str], "检索源列表"] = ["semantic_scholar", "arxiv"],
    limit_per_source: Annotated[int, "每个源的结果数"] = 10,
) -> str:
    """
    统一文献检索工具 - 同时搜索多个学术数据库。
    
    这是最推荐的文献检索工具，它会：
    1. 并发查询多个检索源（Semantic Scholar + arXiv）
    2. 自动去重（基于标题相似度）
    3. 返回统一格式的结果
    
    适用场景：
    - 需要全面了解某个研究领域的现状
    - 需要同时获取已发表论文和预印本
    - 需要快速收集大量相关文献
    
    Args:
        query: 研究主题或关键词
        sources: 检索源列表，默认同时搜索两个源
        limit_per_source: 每个检索源的结果数量
    
    Returns:
        JSON 格式的统一搜索结果，包含去重后的论文列表
    """
    import json
    
    tool = _get_unified_tool()
    
    # 执行统一检索
    result = await tool.search(
        query=query,
        sources=sources,
        limit_per_source=limit_per_source,
    )
    
    # 转换为 JSON 字符串返回
    output = {
        "query": query,
        "sources": sources,
        "total_count": len(result.papers),
        "deduplicated": result.deduplicated,
        "papers": [
            {
                "title": p.title,
                "authors": p.authors,
                "year": p.publication_year,
                "abstract": p.abstract,
                "source": p.source.value if hasattr(p.source, 'value') else str(p.source),
                "doi": p.doi,
                "url": p.url,
                "citation_count": p.citation_count,
            }
            for p in result.papers
        ]
    }
    
    return json.dumps(output, ensure_ascii=False, indent=2)


# ============================================================================
# 工具集合导出
# ============================================================================

def get_literature_tools() -> List[FunctionTool]:
    """
    获取所有文献检索工具的集合。
    
    用于在创建 Agent 时一次性注册所有工具。
    
    Returns:
        工具列表，可直接传递给 Agent 的 tools 参数
    
    使用示例：
        from agents.tools_native import get_literature_tools
        
        agent = Agent(
            client=client,
            name="research_agent",
            tools=get_literature_tools(),  # 注册所有工具
        )
    """
    return [
        search_semantic_scholar,
        search_arxiv,
        search_literature_unified,
    ]


def get_basic_literature_tools() -> List[FunctionTool]:
    """
    获取基础文献检索工具（不含统一检索）。
    
    适用于需要更细粒度控制的场景。
    
    Returns:
        基础工具列表
    """
    return [
        search_semantic_scholar,
        search_arxiv,
    ]


# ============================================================================
# 工具使用统计（可选，用于可观测性）
# ============================================================================

class ToolUsageTracker:
    """
    工具使用追踪器
    
    用于统计工具调用次数、成功率等指标。
    可集成到 OpenTelemetry 遥测系统。
    """
    
    def __init__(self):
        self._call_counts: Dict[str, int] = {}
        self._success_counts: Dict[str, int] = {}
        self._error_counts: Dict[str, int] = {}
    
    def record_call(self, tool_name: str, success: bool) -> None:
        """记录工具调用"""
        self._call_counts[tool_name] = self._call_counts.get(tool_name, 0) + 1
        if success:
            self._success_counts[tool_name] = self._success_counts.get(tool_name, 0) + 1
        else:
            self._error_counts[tool_name] = self._error_counts.get(tool_name, 0) + 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "call_counts": self._call_counts.copy(),
            "success_counts": self._success_counts.copy(),
            "error_counts": self._error_counts.copy(),
        }


# 全局追踪器实例
_tool_tracker = ToolUsageTracker()


def get_tool_tracker() -> ToolUsageTracker:
    """获取全局工具追踪器"""
    return _tool_tracker
