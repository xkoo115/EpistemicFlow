"""
单元测试：原生工具注册模块

测试 agents/tools_native.py 中的工具定义和注册功能。
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from agents.tools_native import (
    search_semantic_scholar,
    search_arxiv,
    search_literature_unified,
    get_literature_tools,
    get_basic_literature_tools,
    ToolUsageTracker,
    get_tool_tracker,
)


class TestLiteratureTools:
    """文献检索工具测试"""
    
    @pytest.mark.asyncio
    async def test_search_semantic_scholar_basic(self):
        """测试 Semantic Scholar 基础搜索"""
        # Mock 客户端
        mock_client = MagicMock()
        mock_client.search = AsyncMock(return_value=[
            MagicMock(
                title="Test Paper 1",
                authors=["Author A", "Author B"],
                publication_year=2023,
                abstract="Test abstract",
                venue="ICML",
                doi="10.1234/test",
                url="https://example.com",
                citation_count=100,
            ),
        ])
        
        with patch(
            "agents.tools_native._get_semantic_scholar_client",
            return_value=mock_client,
        ):
            result = await search_semantic_scholar(
                query="machine learning",
                limit=10,
            )
            
            # 验证返回的是 JSON 字符串
            assert isinstance(result, str)
            
            # 解析并验证内容
            data = json.loads(result)
            assert data["source"] == "semantic_scholar"
            assert data["query"] == "machine learning"
            assert data["count"] == 1
            assert len(data["papers"]) == 1
            assert data["papers"][0]["title"] == "Test Paper 1"
    
    @pytest.mark.asyncio
    async def test_search_semantic_scholar_with_year_range(self):
        """测试带年份范围的搜索"""
        mock_client = MagicMock()
        mock_client.search = AsyncMock(return_value=[])
        
        with patch(
            "agents.tools_native._get_semantic_scholar_client",
            return_value=mock_client,
        ):
            result = await search_semantic_scholar(
                query="deep learning",
                limit=20,
                year_start=2020,
                year_end=2023,
            )
            
            # 验证调用参数
            mock_client.search.assert_called_once()
            call_args = mock_client.search.call_args
            assert call_args.kwargs["year_range"] == (2020, 2023)
    
    @pytest.mark.asyncio
    async def test_search_arxiv_basic(self):
        """测试 arXiv 基础搜索"""
        mock_client = MagicMock()
        mock_client.search = AsyncMock(return_value=[
            MagicMock(
                title="arXiv Paper",
                authors=["Author X"],
                publication_year=2024,
                abstract="Preprint abstract",
                arxiv_id="2401.12345",
                url="https://arxiv.org/abs/2401.12345",
            ),
        ])
        
        with patch(
            "agents.tools_native._get_arxiv_client",
            return_value=mock_client,
        ):
            result = await search_arxiv(
                query="ti:transformer",
                max_results=10,
            )
            
            data = json.loads(result)
            assert data["source"] == "arxiv"
            assert data["query"] == "ti:transformer"
            assert data["count"] == 1
    
    @pytest.mark.asyncio
    async def test_search_literature_unified(self):
        """测试统一文献检索"""
        mock_tool = MagicMock()
        mock_tool.search = AsyncMock(return_value=MagicMock(
            papers=[
                MagicMock(
                    title="Unified Paper",
                    authors=["Author Y"],
                    publication_year=2023,
                    abstract="Abstract",
                    source=MagicMock(value="semantic_scholar"),
                    doi="10.5678/unified",
                    url="https://example.com",
                    citation_count=50,
                ),
            ],
            deduplicated=True,
        ))
        
        with patch(
            "agents.tools_native._get_unified_tool",
            return_value=mock_tool,
        ):
            result = await search_literature_unified(
                query="attention mechanism",
                sources=["semantic_scholar", "arxiv"],
                limit_per_source=10,
            )
            
            data = json.loads(result)
            assert data["query"] == "attention mechanism"
            assert data["total_count"] == 1
            assert data["deduplicated"] is True


class TestToolRegistration:
    """工具注册测试"""
    
    def test_get_literature_tools(self):
        """测试获取所有文献工具"""
        tools = get_literature_tools()
        
        assert len(tools) == 3
        assert all(hasattr(t, 'name') for t in tools)
    
    def test_get_basic_literature_tools(self):
        """测试获取基础文献工具"""
        tools = get_basic_literature_tools()
        
        assert len(tools) == 2


class TestToolUsageTracker:
    """工具使用追踪器测试"""
    
    def test_record_call(self):
        """测试记录工具调用"""
        tracker = ToolUsageTracker()
        
        tracker.record_call("search_semantic_scholar", success=True)
        tracker.record_call("search_semantic_scholar", success=True)
        tracker.record_call("search_semantic_scholar", success=False)
        
        stats = tracker.get_stats()
        
        assert stats["call_counts"]["search_semantic_scholar"] == 3
        assert stats["success_counts"]["search_semantic_scholar"] == 2
        assert stats["error_counts"]["search_semantic_scholar"] == 1
    
    def test_get_tool_tracker_singleton(self):
        """测试全局追踪器单例"""
        tracker1 = get_tool_tracker()
        tracker2 = get_tool_tracker()
        
        assert tracker1 is tracker2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
