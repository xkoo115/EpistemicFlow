"""
文献检索工具测试模块

本模块提供针对 tools/literature.py 的 Mock 测试，包括：
- Semantic Scholar API Mock
- arXiv API Mock
- 统一检索工具测试

设计原则：
- 使用 pytest-httpx 或手动 Mock 拦截 HTTP 请求
- 防止持续调用外部 API 导致限流或费用消耗
- 测试正常流程和异常处理
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import datetime

from tools.literature import (
    SemanticScholarClient,
    ArxivClient,
    LiteratureSearchTool,
    search_papers,
    get_paper_details,
    get_citations,
    LiteratureSearchError,
    APIRateLimitError,
    APITimeoutError,
    APIResponseError,
)
from agents.schemas import PaperMetadata, LiteratureSource


# ============================================================================
# Mock 数据
# ============================================================================

# Semantic Scholar Mock 响应
MOCK_SEMANTIC_SCHOLAR_SEARCH_RESPONSE = {
    "total": 2,
    "offset": 0,
    "data": [
        {
            "paperId": "abc123",
            "title": "Attention Is All You Need",
            "authors": [
                {"authorId": "1", "name": "Ashish Vaswani"},
                {"authorId": "2", "name": "Noam Shazeer"},
            ],
            "year": 2017,
            "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
            "venue": "NeurIPS",
            "doi": "10.48550/arXiv.1706.03762",
            "url": "https://semanticscholar.org/paper/abc123",
            "citationCount": 50000,
        },
        {
            "paperId": "def456",
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "authors": [
                {"authorId": "3", "name": "Jacob Devlin"},
            ],
            "year": 2019,
            "abstract": "We introduce a new language representation model called BERT...",
            "venue": "NAACL",
            "doi": "10.18653/v1/N19-1423",
            "url": "https://semanticscholar.org/paper/def456",
            "citationCount": 30000,
        },
    ],
}

MOCK_SEMANTIC_SCHOLAR_PAPER_RESPONSE = {
    "paperId": "abc123",
    "title": "Attention Is All You Need",
    "authors": [
        {"authorId": "1", "name": "Ashish Vaswani"},
    ],
    "year": 2017,
    "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
    "venue": "NeurIPS",
    "doi": "10.48550/arXiv.1706.03762",
    "url": "https://semanticscholar.org/paper/abc123",
    "citationCount": 50000,
}

# arXiv Mock 响应（Atom XML 格式）
MOCK_ARXIV_SEARCH_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>arXiv Query: search_query=all:attention</title>
  <entry>
    <id>http://arxiv.org/abs/1706.03762v5</id>
    <title>Attention Is All You Need</title>
    <author>
      <name>Ashish Vaswani</name>
    </author>
    <author>
      <name>Noam Shazeer</name>
    </author>
    <published>2017-06-12T00:00:00Z</published>
    <summary>The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...</summary>
    <link href="http://arxiv.org/abs/1706.03762v5" rel="alternate" type="text/html"/>
    <arxiv:doi>10.48550/arXiv.1706.03762</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/1810.04805v2</id>
    <title>BERT: Pre-training of Deep Bidirectional Transformers</title>
    <author>
      <name>Jacob Devlin</name>
    </author>
    <published>2018-10-11T00:00:00Z</published>
    <summary>We introduce a new language representation model called BERT...</summary>
    <link href="http://arxiv.org/abs/1810.04805v2" rel="alternate" type="text/html"/>
  </entry>
</feed>
"""


# ============================================================================
# Semantic Scholar 客户端测试
# ============================================================================

class TestSemanticScholarClient:
    """Semantic Scholar 客户端测试"""

    @pytest.mark.asyncio
    async def test_search_success(self):
        """测试搜索成功"""
        # Mock httpx.AsyncClient
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock 响应
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = MOCK_SEMANTIC_SCHOLAR_SEARCH_RESPONSE
            mock_client.request.return_value = mock_response

            # 执行搜索
            client = SemanticScholarClient()
            results = await client.search("attention mechanism", limit=10)

            # 验证结果
            assert len(results) == 2
            assert results[0].title == "Attention Is All You Need"
            assert results[0].authors[0] == "Ashish Vaswani"
            assert results[0].publication_year == 2017
            assert results[0].source == LiteratureSource.SEMANTIC_SCHOLAR

    @pytest.mark.asyncio
    async def test_search_rate_limit(self):
        """测试限流处理"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock 限流响应
            mock_response_429 = MagicMock()
            mock_response_429.status_code = 429
            mock_response_429.headers = {"Retry-After": "1"}

            # Mock 成功响应（重试后）
            mock_response_200 = MagicMock()
            mock_response_200.status_code = 200
            mock_response_200.json.return_value = MOCK_SEMANTIC_SCHOLAR_SEARCH_RESPONSE

            mock_client.request.side_effect = [mock_response_429, mock_response_200]

            client = SemanticScholarClient()
            results = await client.search("attention mechanism", limit=10)

            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_paper_success(self):
        """测试获取单篇论文"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = MOCK_SEMANTIC_SCHOLAR_PAPER_RESPONSE
            mock_client.request.return_value = mock_response

            client = SemanticScholarClient()
            paper = await client.get_paper("abc123")

            assert paper is not None
            assert paper.title == "Attention Is All You Need"
            assert paper.citation_count == 50000

    @pytest.mark.asyncio
    async def test_get_paper_not_found(self):
        """测试论文不存在"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.request.return_value = mock_response

            client = SemanticScholarClient()
            paper = await client.get_paper("nonexistent")

            assert paper is None


# ============================================================================
# arXiv 客户端测试
# ============================================================================

class TestArxivClient:
    """arXiv 客户端测试"""

    @pytest.mark.asyncio
    async def test_search_success(self):
        """测试搜索成功"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = MOCK_ARXIV_SEARCH_RESPONSE
            mock_client.request.return_value = mock_response

            client = ArxivClient()
            results = await client.search("attention", limit=10)

            assert len(results) == 2
            assert results[0].title == "Attention Is All You Need"
            assert results[0].authors[0] == "Ashish Vaswani"
            assert results[0].publication_year == 2017
            assert results[0].source == LiteratureSource.ARXIV

    @pytest.mark.asyncio
    async def test_get_paper_success(self):
        """测试根据 arXiv ID 获取论文"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = MOCK_ARXIV_SEARCH_RESPONSE
            mock_client.request.return_value = mock_response

            client = ArxivClient()
            paper = await client.get_paper("1706.03762")

            assert paper is not None
            assert paper.title == "Attention Is All You Need"


# ============================================================================
# 统一检索工具测试
# ============================================================================

class TestLiteratureSearchTool:
    """统一检索工具测试"""

    @pytest.mark.asyncio
    async def test_search_multiple_sources(self):
        """测试多数据源搜索"""
        # Mock Semantic Scholar
        with patch.object(
            SemanticScholarClient, "search", new_callable=AsyncMock
        ) as mock_ss_search:
            mock_ss_search.return_value = [
                PaperMetadata(
                    title="Attention Is All You Need",
                    authors=["Ashish Vaswani"],
                    publication_year=2017,
                    source=LiteratureSource.SEMANTIC_SCHOLAR,
                ),
            ]

            # Mock arXiv
            with patch.object(
                ArxivClient, "search", new_callable=AsyncMock
            ) as mock_arxiv_search:
                mock_arxiv_search.return_value = [
                    PaperMetadata(
                        title="BERT: Pre-training of Deep Bidirectional Transformers",
                        authors=["Jacob Devlin"],
                        publication_year=2019,
                        source=LiteratureSource.ARXIV,
                    ),
                ]

                tool = LiteratureSearchTool()
                result = await tool.search(
                    query="attention mechanism",
                    sources=["semantic_scholar", "arxiv"],
                    limit=10,
                )

                assert result.total_count == 2
                assert len(result.papers) == 2
                assert "semantic_scholar" in result.sources
                assert "arxiv" in result.sources

    @pytest.mark.asyncio
    async def test_search_with_year_range(self):
        """测试带年份范围的搜索"""
        with patch.object(
            SemanticScholarClient, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [
                PaperMetadata(
                    title="Recent Paper",
                    publication_year=2023,
                    source=LiteratureSource.SEMANTIC_SCHOLAR,
                ),
            ]

            tool = LiteratureSearchTool()
            result = await tool.search(
                query="deep learning",
                sources=["semantic_scholar"],
                year_range=(2020, 2024),
            )

            # 验证年份范围参数被传递
            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["year_range"] == (2020, 2024)

    @pytest.mark.asyncio
    async def test_deduplicate_papers(self):
        """测试论文去重"""
        tool = LiteratureSearchTool()

        papers = [
            PaperMetadata(
                title="Attention Is All You Need",
                authors=["A"],
                source=LiteratureSource.SEMANTIC_SCHOLAR,
            ),
            PaperMetadata(
                title="Attention Is All You Need",  # 重复
                authors=["B"],
                source=LiteratureSource.ARXIV,
            ),
            PaperMetadata(
                title="BERT: Pre-training of Deep Bidirectional Transformers",
                authors=["C"],
                source=LiteratureSource.SEMANTIC_SCHOLAR,
            ),
        ]

        unique_papers = tool._deduplicate_papers(papers)

        assert len(unique_papers) == 2

    @pytest.mark.asyncio
    async def test_get_paper_details(self):
        """测试获取论文详情"""
        with patch.object(
            SemanticScholarClient, "get_paper", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = PaperMetadata(
                title="Attention Is All You Need",
                authors=["Ashish Vaswani"],
                source=LiteratureSource.SEMANTIC_SCHOLAR,
            )

            tool = LiteratureSearchTool()
            paper = await tool.get_paper_details("abc123", source="semantic_scholar")

            assert paper is not None
            assert paper.title == "Attention Is All You Need"

    @pytest.mark.asyncio
    async def test_get_citations(self):
        """测试获取引用"""
        with patch.object(
            SemanticScholarClient, "get_citations", new_callable=AsyncMock
        ) as mock_citations:
            mock_citations.return_value = [
                PaperMetadata(
                    title="Citing Paper 1",
                    source=LiteratureSource.SEMANTIC_SCHOLAR,
                ),
                PaperMetadata(
                    title="Citing Paper 2",
                    source=LiteratureSource.SEMANTIC_SCHOLAR,
                ),
            ]

            tool = LiteratureSearchTool()
            citations = await tool.get_citations("abc123", limit=50)

            assert len(citations) == 2


# ============================================================================
# 便捷函数测试
# ============================================================================

class TestConvenienceFunctions:
    """便捷函数测试"""

    @pytest.mark.asyncio
    async def test_search_papers(self):
        """测试 search_papers 便捷函数"""
        with patch.object(
            LiteratureSearchTool, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = MagicMock(
                papers=[
                    PaperMetadata(
                        title="Test Paper",
                        source=LiteratureSource.SEMANTIC_SCHOLAR,
                    ),
                ]
            )

            papers = await search_papers("test query")

            assert len(papers) == 1

    @pytest.mark.asyncio
    async def test_get_paper_details(self):
        """测试 get_paper_details 便捷函数"""
        with patch.object(
            LiteratureSearchTool, "get_paper_details", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = PaperMetadata(
                title="Test Paper",
                source=LiteratureSource.SEMANTIC_SCHOLAR,
            )

            paper = await get_paper_details("test_id")

            assert paper is not None

    @pytest.mark.asyncio
    async def test_get_citations(self):
        """测试 get_citations 便捷函数"""
        with patch.object(
            LiteratureSearchTool, "get_citations", new_callable=AsyncMock
        ) as mock_citations:
            mock_citations.return_value = [
                PaperMetadata(
                    title="Citing Paper",
                    source=LiteratureSource.SEMANTIC_SCHOLAR,
                ),
            ]

            citations = await get_citations("test_id")

            assert len(citations) == 1


# ============================================================================
# 异常处理测试
# ============================================================================

class TestErrorHandling:
    """异常处理测试"""

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """测试超时错误"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock 超时
            import httpx
            mock_client.request.side_effect = httpx.TimeoutException("Timeout")

            client = SemanticScholarClient(max_retries=1)

            with pytest.raises(APITimeoutError):
                await client.search("test")

    @pytest.mark.asyncio
    async def test_api_response_error(self):
        """测试 API 响应错误"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client.request.return_value = mock_response

            client = SemanticScholarClient(max_retries=1)

            with pytest.raises(APIResponseError):
                await client.search("test")


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
