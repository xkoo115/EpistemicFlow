"""
EpistemicFlow 工具模块

本模块为智能体提供可调用的外部工具（Tools），包括：
- 文献检索工具（Semantic Scholar、arXiv）
- 数据处理工具
- 导出工具

设计原则：
- 所有工具使用异步 HTTP 客户端（httpx）
- 支持超时控制和错误重试
- 返回结构化的 Pydantic 模型
"""

from tools.literature import (
    LiteratureSearchTool,
    SemanticScholarClient,
    ArxivClient,
    search_papers,
    get_paper_details,
    get_citations,
)

__all__ = [
    "LiteratureSearchTool",
    "SemanticScholarClient",
    "ArxivClient",
    "search_papers",
    "get_paper_details",
    "get_citations",
]
