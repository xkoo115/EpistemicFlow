"""
文献检索工具模块

本模块封装了多个学术文献检索 API，为 SubResearcherAgent 提供真实的文献获取能力。

支持的 API：
1. Semantic Scholar API（免费，推荐）
   - 提供论文搜索、引用关系、作者信息
   - API 文档：https://api.semanticscholar.org/

2. arXiv API（免费）
   - 提供预印本论文搜索
   - API 文档：https://arxiv.org/help/api/

设计原则：
- 使用 httpx 异步客户端，支持高并发
- 统一的错误处理和重试机制
- 返回结构化的 PaperMetadata 模型
- 支持超时控制，防止长时间阻塞

使用示例：
    # 直接使用函数
    papers = await search_papers("attention mechanism", limit=10)

    # 使用工具类
    tool = LiteratureSearchTool()
    result = await tool.search("deep learning", sources=["semantic_scholar", "arxiv"])
"""

from typing import List, Optional, Dict, Any, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import xml.etree.ElementTree as ET
import re

import httpx

from agents.schemas import PaperMetadata, LiteratureSource


# ============================================================================
# 配置常量
# ============================================================================

# Semantic Scholar API 配置
SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_TIMEOUT = 30.0  # 秒

# arXiv API 配置
ARXIV_BASE_URL = "http://export.arxiv.org/api/query"
ARXIV_TIMEOUT = 30.0  # 秒

# 通用配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # 秒
DEFAULT_SEARCH_LIMIT = 20


# ============================================================================
# 异常定义
# ============================================================================

class LiteratureSearchError(Exception):
    """文献检索错误基类"""
    pass


class APIRateLimitError(LiteratureSearchError):
    """API 限流错误"""
    pass


class APITimeoutError(LiteratureSearchError):
    """API 超时错误"""
    pass


class APIResponseError(LiteratureSearchError):
    """API 响应错误"""
    pass


# ============================================================================
# Semantic Scholar 客户端
# ============================================================================

class SemanticScholarClient:
    """
    Semantic Scholar API 客户端

    Semantic Scholar 是一个免费的学术搜索引擎，提供丰富的论文元数据和引用关系。

    API 特点：
    - 免费使用，无需 API Key（有速率限制）
    - 提供论文搜索、引用关系、作者信息
    - 支持批量查询

    速率限制：
    - 无 API Key：100 请求/5分钟
    - 有 API Key：5000 请求/5分钟
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = SEMANTIC_SCHOLAR_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        """
        初始化 Semantic Scholar 客户端

        Args:
            api_key: API 密钥（可选，用于提高速率限制）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self._base_url = SEMANTIC_SCHOLAR_BASE_URL
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries

        # 构建请求头
        self._headers = {"Accept": "application/json"}
        if api_key:
            self._headers["x-api-key"] = api_key

    async def search(
        self,
        query: str,
        limit: int = DEFAULT_SEARCH_LIMIT,
        offset: int = 0,
        year_range: Optional[tuple[int, int]] = None,
    ) -> List[PaperMetadata]:
        """
        搜索论文

        Args:
            query: 搜索查询（关键词或短语）
            limit: 返回结果数量限制
            offset: 偏移量（用于分页）
            year_range: 年份范围 (start_year, end_year)

        Returns:
            论文元数据列表

        Raises:
            LiteratureSearchError: 搜索失败
        """
        # 构建查询参数
        params = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "fields": "title,authors,year,abstract,venue,doi,url,citationCount",
        }

        # 添加年份过滤
        if year_range:
            start_year, end_year = year_range
            params["year"] = f"{start_year}-{end_year}"

        # 发送请求
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await self._request_with_retry(
                client,
                "GET",
                f"{self._base_url}/paper/search",
                params=params,
            )

        # 解析响应
        return self._parse_search_response(response)

    async def get_paper(self, paper_id: str) -> Optional[PaperMetadata]:
        """
        获取单篇论文详情

        Args:
            paper_id: 论文 ID（Semantic Scholar ID、DOI 或 arXiv ID）

        Returns:
            论文元数据，如果不存在则返回 None
        """
        params = {
            "fields": "title,authors,year,abstract,venue,doi,url,citationCount,references"
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await self._request_with_retry(
                    client,
                    "GET",
                    f"{self._base_url}/paper/{paper_id}",
                    params=params,
                )
                return self._parse_paper(response)
            except APIResponseError:
                return None

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 50,
    ) -> List[PaperMetadata]:
        """
        获取引用该论文的论文列表

        Args:
            paper_id: 论文 ID
            limit: 返回结果数量限制

        Returns:
            引用论文列表
        """
        params = {
            "limit": limit,
            "fields": "title,authors,year,abstract,venue,doi,url,citationCount",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await self._request_with_retry(
                client,
                "GET",
                f"{self._base_url}/paper/{paper_id}/citations",
                params=params,
            )

        return self._parse_citations_response(response)

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        带重试的请求

        Args:
            client: HTTP 客户端
            method: HTTP 方法
            url: 请求 URL
            params: 查询参数

        Returns:
            JSON 响应数据

        Raises:
            LiteratureSearchError: 请求失败
        """
        last_error = None

        for attempt in range(self._max_retries):
            try:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    headers=self._headers,
                )

                # 检查状态码
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # 限流，等待后重试
                    retry_after = float(response.headers.get("Retry-After", RETRY_DELAY * 2))
                    await asyncio.sleep(retry_after)
                    continue
                elif response.status_code == 404:
                    raise APIResponseError(f"资源不存在: {url}")
                else:
                    raise APIResponseError(
                        f"API 响应错误: {response.status_code} - {response.text}"
                    )

            except httpx.TimeoutException as e:
                last_error = APITimeoutError(f"请求超时: {url}")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            except httpx.RequestError as e:
                last_error = LiteratureSearchError(f"请求错误: {e}")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            except APIResponseError:
                raise
            except Exception as e:
                last_error = LiteratureSearchError(f"未知错误: {e}")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        raise last_error or LiteratureSearchError("请求失败")

    def _parse_search_response(self, response: Dict[str, Any]) -> List[PaperMetadata]:
        """解析搜索响应"""
        papers = []
        data = response.get("data", [])

        for item in data:
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)

        return papers

    def _parse_paper(self, item: Dict[str, Any]) -> Optional[PaperMetadata]:
        """解析单篇论文数据"""
        if not item:
            return None

        try:
            # 提取作者列表
            authors = []
            for author in item.get("authors", []):
                name = author.get("name")
                if name:
                    authors.append(name)

            return PaperMetadata(
                title=item.get("title", ""),
                authors=authors,
                abstract=item.get("abstract"),
                publication_year=item.get("year"),
                venue=item.get("venue"),
                doi=item.get("doi"),
                url=item.get("url"),
                citation_count=item.get("citationCount"),
                source=LiteratureSource.SEMANTIC_SCHOLAR,
            )
        except Exception:
            return None

    def _parse_citations_response(self, response: Dict[str, Any]) -> List[PaperMetadata]:
        """解析引用响应"""
        papers = []
        data = response.get("data", [])

        for item in data:
            # 引用响应的结构略有不同
            citing_paper = item.get("citingPaper", {})
            paper = self._parse_paper(citing_paper)
            if paper:
                papers.append(paper)

        return papers


# ============================================================================
# arXiv 客户端
# ============================================================================

class ArxivClient:
    """
    arXiv API 客户端

    arXiv 是一个免费的预印本服务器，主要涵盖物理、数学、计算机科学等领域。

    API 特点：
    - 完全免费，无需 API Key
    - 使用 Atom XML 格式返回数据
    - 支持复杂查询语法

    速率限制：
    - 建议每次请求间隔 3 秒
    """

    def __init__(
        self,
        timeout: float = ARXIV_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        """
        初始化 arXiv 客户端

        Args:
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self._base_url = ARXIV_BASE_URL
        self._timeout = timeout
        self._max_retries = max_retries

    async def search(
        self,
        query: str,
        limit: int = DEFAULT_SEARCH_LIMIT,
        start: int = 0,
        sort_by: str = "relevance",
    ) -> List[PaperMetadata]:
        """
        搜索论文

        Args:
            query: 搜索查询
            limit: 返回结果数量限制
            start: 起始位置（用于分页）
            sort_by: 排序方式（relevance, submittedDate, lastUpdatedDate）

        Returns:
            论文元数据列表

        查询语法：
        - ti: 标题搜索（如 ti:attention）
        - au: 作者搜索（如 au:Vaswani）
        - abs: 摘要搜索
        - cat: 分类搜索（如 cat:cs.AI）
        - all: 全文搜索
        """
        # 构建查询参数
        params = {
            "search_query": query,
            "start": start,
            "max_results": limit,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }

        # 发送请求
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await self._request_with_retry(
                client,
                "GET",
                self._base_url,
                params=params,
            )

        # 解析响应
        return self._parse_atom_response(response)

    async def get_paper(self, arxiv_id: str) -> Optional[PaperMetadata]:
        """
        根据 arXiv ID 获取论文详情

        Args:
            arxiv_id: arXiv ID（如 "2301.00001" 或 "cs/0001001"）

        Returns:
            论文元数据
        """
        papers = await self.search(f"id:{arxiv_id}", limit=1)
        return papers[0] if papers else None

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        带重试的请求

        Returns:
            XML 响应文本
        """
        last_error = None

        for attempt in range(self._max_retries):
            try:
                response = await client.request(method, url, params=params)

                if response.status_code == 200:
                    return response.text
                else:
                    raise APIResponseError(
                        f"API 响应错误: {response.status_code}"
                    )

            except httpx.TimeoutException:
                last_error = APITimeoutError(f"请求超时: {url}")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            except httpx.RequestError as e:
                last_error = LiteratureSearchError(f"请求错误: {e}")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            except APIResponseError:
                raise
            except Exception as e:
                last_error = LiteratureSearchError(f"未知错误: {e}")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        raise last_error or LiteratureSearchError("请求失败")

    def _parse_atom_response(self, xml_text: str) -> List[PaperMetadata]:
        """
        解析 arXiv Atom XML 响应

        arXiv 使用 Atom XML 格式返回数据，需要解析 XML。
        """
        papers = []

        try:
            root = ET.fromstring(xml_text)

            # 定义命名空间
            namespaces = {
                "atom": "http://www.w3.org/2005/Atom",
                "arxiv": "http://arxiv.org/schemas/atom",
            }

            # 遍历所有 entry 元素
            for entry in root.findall("atom:entry", namespaces):
                paper = self._parse_entry(entry, namespaces)
                if paper:
                    papers.append(paper)

        except ET.ParseError as e:
            raise APIResponseError(f"XML 解析错误: {e}")

        return papers

    def _parse_entry(
        self,
        entry: ET.Element,
        namespaces: Dict[str, str],
    ) -> Optional[PaperMetadata]:
        """解析单个 entry 元素"""
        try:
            # 提取标题
            title_elem = entry.find("atom:title", namespaces)
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

            # 提取作者
            authors = []
            for author_elem in entry.findall("atom:author", namespaces):
                name_elem = author_elem.find("atom:name", namespaces)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text.strip())

            # 提取摘要
            summary_elem = entry.find("atom:summary", namespaces)
            abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else None

            # 提取发布日期
            published_elem = entry.find("atom:published", namespaces)
            publication_year = None
            if published_elem is not None and published_elem.text:
                try:
                    date_str = published_elem.text.strip()
                    publication_year = int(date_str[:4])
                except (ValueError, IndexError):
                    pass

            # 提取链接
            url = None
            for link_elem in entry.findall("atom:link", namespaces):
                href = link_elem.get("href", "")
                if "arxiv.org/abs" in href:
                    url = href
                    break

            # 提取 DOI（如果有）
            doi = None
            doi_elem = entry.find("arxiv:doi", namespaces)
            if doi_elem is not None and doi_elem.text:
                doi = doi_elem.text.strip()

            return PaperMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                publication_year=publication_year,
                doi=doi,
                url=url,
                source=LiteratureSource.ARXIV,
            )
        except Exception:
            return None


# ============================================================================
# 统一检索工具
# ============================================================================

@dataclass
class SearchResult:
    """
    检索结果

    汇总来自多个数据源的检索结果。
    """
    query: str
    """搜索查询"""

    papers: List[PaperMetadata] = field(default_factory=list)
    """论文列表"""

    total_count: int = 0
    """总结果数"""

    sources: List[str] = field(default_factory=list)
    """使用的数据源"""

    search_time_ms: float = 0.0
    """搜索耗时（毫秒）"""

    errors: List[str] = field(default_factory=list)
    """错误信息"""


class LiteratureSearchTool:
    """
    文献检索工具

    统一封装多个学术检索 API，提供一站式检索服务。

    使用示例：
        tool = LiteratureSearchTool()

        # 搜索论文
        result = await tool.search(
            query="attention mechanism in deep learning",
            sources=["semantic_scholar", "arxiv"],
            limit=20,
        )

        # 获取论文详情
        paper = await tool.get_paper_details("2041e7f720e4ab5a5c5c5c5c5c5c5c5c5c5c5c5c")

        # 获取引用关系
        citations = await tool.get_citations("2041e7f720e4ab5a5c5c5c5c5c5c5c5c5c5c5c5")
    """

    def __init__(
        self,
        semantic_scholar_api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        初始化文献检索工具

        Args:
            semantic_scholar_api_key: Semantic Scholar API 密钥（可选）
            timeout: 请求超时时间
        """
        self._semantic_scholar = SemanticScholarClient(
            api_key=semantic_scholar_api_key,
            timeout=timeout,
        )
        self._arxiv = ArxivClient(timeout=timeout)

    async def search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
        year_range: Optional[tuple[int, int]] = None,
    ) -> SearchResult:
        """
        搜索论文

        Args:
            query: 搜索查询
            sources: 数据源列表（默认使用所有源）
                - "semantic_scholar": Semantic Scholar
                - "arxiv": arXiv
            limit: 每个数据源的返回结果数量限制
            year_range: 年份范围

        Returns:
            检索结果
        """
        import time
        start_time = time.time()

        # 默认使用所有数据源
        if sources is None:
            sources = ["semantic_scholar", "arxiv"]

        result = SearchResult(query=query, sources=sources)
        tasks = []

        # 创建并发任务
        if "semantic_scholar" in sources:
            tasks.append(("semantic_scholar", self._search_semantic_scholar(query, limit, year_range)))
        if "arxiv" in sources:
            tasks.append(("arxiv", self._search_arxiv(query, limit)))

        # 并发执行
        for source_name, task in tasks:
            try:
                papers = await task
                result.papers.extend(papers)
            except Exception as e:
                result.errors.append(f"{source_name}: {str(e)}")

        # 去重（基于标题相似度）
        result.papers = self._deduplicate_papers(result.papers)
        result.total_count = len(result.papers)
        result.search_time_ms = (time.time() - start_time) * 1000

        return result

    async def _search_semantic_scholar(
        self,
        query: str,
        limit: int,
        year_range: Optional[tuple[int, int]],
    ) -> List[PaperMetadata]:
        """Semantic Scholar 搜索"""
        return await self._semantic_scholar.search(
            query=query,
            limit=limit,
            year_range=year_range,
        )

    async def _search_arxiv(
        self,
        query: str,
        limit: int,
    ) -> List[PaperMetadata]:
        """arXiv 搜索"""
        return await self._arxiv.search(
            query=query,
            limit=limit,
        )

    async def get_paper_details(
        self,
        paper_id: str,
        source: str = "semantic_scholar",
    ) -> Optional[PaperMetadata]:
        """
        获取论文详情

        Args:
            paper_id: 论文 ID
            source: 数据源

        Returns:
            论文元数据
        """
        if source == "semantic_scholar":
            return await self._semantic_scholar.get_paper(paper_id)
        elif source == "arxiv":
            return await self._arxiv.get_paper(paper_id)
        else:
            raise ValueError(f"不支持的数据源: {source}")

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 50,
    ) -> List[PaperMetadata]:
        """
        获取引用该论文的论文列表

        Args:
            paper_id: 论文 ID（Semantic Scholar ID）
            limit: 返回结果数量限制

        Returns:
            引用论文列表
        """
        return await self._semantic_scholar.get_citations(paper_id, limit)

    def _deduplicate_papers(
        self,
        papers: List[PaperMetadata],
        similarity_threshold: float = 0.9,
    ) -> List[PaperMetadata]:
        """
        论文去重

        基于标题相似度进行去重。

        Args:
            papers: 论文列表
            similarity_threshold: 相似度阈值

        Returns:
            去重后的论文列表
        """
        if not papers:
            return papers

        unique_papers = []
        seen_titles = []

        for paper in papers:
            # 标准化标题
            normalized_title = self._normalize_title(paper.title)

            # 检查是否与已有标题相似
            is_duplicate = False
            for seen_title in seen_titles:
                similarity = self._calculate_similarity(normalized_title, seen_title)
                if similarity >= similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_papers.append(paper)
                seen_titles.append(normalized_title)

        return unique_papers

    def _normalize_title(self, title: str) -> str:
        """标准化标题"""
        # 转小写
        title = title.lower()
        # 移除标点符号
        title = re.sub(r'[^\w\s]', '', title)
        # 移除多余空格
        title = ' '.join(title.split())
        return title

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算文本相似度（Jaccard 相似度）

        Args:
            text1: 文本 1
            text2: 文本 2

        Returns:
            相似度 [0, 1]
        """
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)


# ============================================================================
# 便捷函数
# ============================================================================

async def search_papers(
    query: str,
    sources: Optional[List[str]] = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
    year_range: Optional[tuple[int, int]] = None,
) -> List[PaperMetadata]:
    """
    搜索论文（便捷函数）

    Args:
        query: 搜索查询
        sources: 数据源列表
        limit: 返回结果数量限制
        year_range: 年份范围

    Returns:
        论文元数据列表

    使用示例：
        papers = await search_papers("attention mechanism", limit=10)
    """
    tool = LiteratureSearchTool()
    result = await tool.search(query, sources, limit, year_range)
    return result.papers


async def get_paper_details(
    paper_id: str,
    source: str = "semantic_scholar",
) -> Optional[PaperMetadata]:
    """
    获取论文详情（便捷函数）

    Args:
        paper_id: 论文 ID
        source: 数据源

    Returns:
        论文元数据
    """
    tool = LiteratureSearchTool()
    return await tool.get_paper_details(paper_id, source)


async def get_citations(
    paper_id: str,
    limit: int = 50,
) -> List[PaperMetadata]:
    """
    获取引用论文列表（便捷函数）

    Args:
        paper_id: 论文 ID
        limit: 返回结果数量限制

    Returns:
        引用论文列表
    """
    tool = LiteratureSearchTool()
    return await tool.get_citations(paper_id, limit)
