"""Tests for Autonomous Research Agent."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import asyncio

from src.models import (
    SearchResult, ExtractedContent, ResearchQuery, ResearchSummary,
    SearchEngine, SourceType, ExportFormat, SummarySection
)
from src.search.engines import DuckDuckGoSearchEngine, SearchManager
from src.search.selector import SourceSelector
from src.extraction.extractor import ContentExtractor
from src.extraction.deduplicator import ContentDeduplicator, ResultRanker
from src.summarization.summarizer import OpenAISummarizer, SummarizerFactory
from src.export.exporter import MarkdownExporter, ExportManager, ExportRequest
from src.memory.manager import MemoryManager
from src.agent.research_agent import AutonomousResearchAgent


class TestModels:
    """Test data models."""

    def test_search_result_creation(self):
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            snippet="Test snippet",
            source=SearchEngine.DUCKDUCKGO
        )
        assert result.title == "Test Title"
        assert str(result.url) == "https://example.com/"
        assert result.source == SearchEngine.DUCKDUCKGO

    def test_extracted_content_creation(self):
        content = ExtractedContent(
            url="https://example.com",
            title="Test",
            content="Test content",
            word_count=2
        )
        assert content.word_count == 2
        assert content.success is True

    def test_research_summary_creation(self):
        summary = ResearchSummary(
            query_id="test-id",
            query="test query",
            key_points=["point 1", "point 2"],
            important_findings=["finding 1"],
            actionable_insights=["insight 1"],
            references=[]
        )
        assert len(summary.key_points) == 2
        assert summary.total_sources == 0


class TestSourceSelector:
    """Test source selection logic."""

    def setup_method(self):
        self.selector = SourceSelector()

    def test_analyze_academic_query(self):
        query = "research paper on machine learning arxiv"
        source_type = self.selector.analyze_query(query)
        assert source_type == SourceType.ACADEMIC

    def test_analyze_news_query(self):
        query = "latest news about AI today"
        source_type = self.selector.analyze_query(query)
        assert source_type == SourceType.NEWS

    def test_analyze_documentation_query(self):
        query = "python documentation tutorial"
        source_type = self.selector.analyze_query(query)
        assert source_type == SourceType.DOCUMENTATION

    def test_analyze_default_query(self):
        query = "what is the capital of france"
        source_type = self.selector.analyze_query(query)
        assert source_type == SourceType.WEBSITE

    def test_select_engines(self):
        engines = self.selector.select_engines("machine learning research")
        assert SearchEngine.DUCKDUCKGO in engines
        assert len(engines) > 0

    def test_refine_query_academic(self):
        query = "transformer architecture"
        refined = self.selector.refine_query(query, SourceType.ACADEMIC)
        assert "arxiv" in refined.lower() or "scholar" in refined.lower()


class TestContentDeduplicator:
    """Test content deduplication."""

    def setup_method(self):
        self.deduplicator = ContentDeduplicator()

    def test_deduplicate_exact(self):
        contents = [
            ExtractedContent(url="https://a.com", title="A", content="Same content here"),
            ExtractedContent(url="https://b.com", title="B", content="Same content here"),
            ExtractedContent(url="https://c.com", title="C", content="Different content"),
        ]
        result = self.deduplicator.deduplicate(contents)
        assert len(result) == 2

    def test_filter_relevant(self):
        contents = [
            ExtractedContent(url="https://a.com", title="A", content="Python programming language tutorial guide python"),
            ExtractedContent(url="https://b.com", title="B", content="Java development coding software"),
            ExtractedContent(url="https://c.com", title="C", content="Cooking recipes food kitchen"),
        ]
        result = self.deduplicator.filter_relevant(contents, "Python programming", min_relevance=0.3)
        assert len(result) == 1
        assert "Python" in result[0].content


class TestResultRanker:
    """Test result ranking."""

    def setup_method(self):
        self.ranker = ResultRanker()

    def test_rank_results(self):
        results = [
            SearchResult(title="Python Tutorial", url="https://a.com", snippet="Learn Python", source=SearchEngine.DUCKDUCKGO),
            SearchResult(title="Java Guide", url="https://b.com", snippet="Java basics", source=SearchEngine.DUCKDUCKGO),
            SearchResult(title="Python Docs", url="https://docs.python.org", snippet="Official docs", source=SearchEngine.DUCKDUCKGO),
        ]
        ranked = self.ranker.rank_results(results, "Python")
        assert ranked[0].title == "Python Docs"  # High quality domain boost
        assert ranked[1].title == "Python Tutorial"


class TestMarkdownExporter:
    """Test markdown export."""

    def setup_method(self):
        self.exporter = MarkdownExporter()

    def test_export_markdown(self, tmp_path):
        summary = ResearchSummary(
            query_id="test-id",
            query="Test Query",
            key_points=["Point 1", "Point 2"],
            important_findings=["Finding 1"],
            actionable_insights=["Insight 1"],
            references=[
                SearchResult(title="Ref 1", url="https://example.com/1", snippet="Snippet 1", source=SearchEngine.DUCKDUCKGO)
            ],
            sections=[
                SummarySection(title="Section 1", content="Content 1", sources=["https://example.com/1"])
            ]
        )

        request = ExportRequest(
            summary_id="test-id",
            format=ExportFormat.MARKDOWN,
            output_path=str(tmp_path / "test.md")
        )

        path = self.exporter.export(summary, request)
        assert Path(path).exists()

        content = Path(path).read_text()
        assert "Test Query" in content
        assert "Point 1" in content
        assert "Finding 1" in content
        assert "Insight 1" in content


class TestExportManager:
    """Test export manager."""

    def setup_method(self):
        self.manager = ExportManager()

    def test_export_multiple_formats(self, tmp_path):
        summary = ResearchSummary(
            query_id="test-id",
            query="Test",
            key_points=["Point 1"],
            important_findings=[],
            actionable_insights=[],
            references=[]
        )

        formats = [ExportFormat.MARKDOWN, ExportFormat.JSON]
        results = self.manager.export_multiple(summary, formats)

        assert ExportFormat.MARKDOWN in results
        assert ExportFormat.JSON in results
        assert Path(results[ExportFormat.MARKDOWN]).exists()
        assert Path(results[ExportFormat.JSON]).exists()


class TestMemoryManager:
    """Test memory management."""

    def setup_method(self):
        self.manager = MemoryManager()

    def test_save_and_load_session(self):
        from src.models import ResearchSession
        import uuid

        session = ResearchSession(
            id=str(uuid.uuid4()),
            query=ResearchQuery(query="Test query"),
            search_results=[],
            extracted_content=[],
            summary=ResearchSummary(
                query_id=str(uuid.uuid4()),
                query="Test query",
                key_points=[],
                important_findings=[],
                actionable_insights=[],
                references=[]
            ),
            exports=[]
        )

        saved_id = self.manager.save_session(session)
        assert saved_id == session.id

        loaded = self.manager.load_session(session.id)
        assert loaded is not None
        assert loaded.query.query == "Test query"

    def test_get_recent_sessions(self):
        sessions = self.manager.get_recent_sessions(limit=5)
        assert isinstance(sessions, list)

    def test_get_stats(self):
        stats = self.manager.get_stats()
        assert "total_sessions" in stats
        assert "db_size_mb" in stats


class TestAutonomousResearchAgent:
    """Test main agent."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        with patch('httpx.AsyncClient') as mock_client_class, \
             patch('src.summarization.summarizer.OpenAISummarizer') as mock_summarizer:
            mock_client = AsyncMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_summarizer.return_value = Mock()
            agent = AutonomousResearchAgent()
            assert agent.search_manager is not None
            assert agent.extractor is not None
            assert agent.summarizer is not None
            await agent.close()

    @pytest.mark.asyncio
    async def test_quick_research_mock(self):
        with patch('httpx.AsyncClient') as mock_client_class, \
             patch('src.summarization.summarizer.OpenAISummarizer') as mock_summarizer_class, \
             patch.object(SearchManager, 'search', new_callable=AsyncMock) as mock_search, \
             patch.object(ContentExtractor, 'extract_batch', new_callable=AsyncMock) as mock_extract:
            
            mock_client = AsyncMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_summarizer = Mock()
            mock_summarizer.summarize = AsyncMock(return_value=ResearchSummary(
                query_id="test",
                query="test query",
                key_points=["Mock point"],
                important_findings=[],
                actionable_insights=[],
                references=[],
                total_sources=0,
                processing_time=0.1
            ))
            mock_summarizer_class.return_value = mock_summarizer
            
            # Mock search to return some results
            mock_search.return_value = [
                SearchResult(
                    title="Test Result",
                    url="https://example.com",
                    snippet="Test snippet",
                    source=SearchEngine.DUCKDUCKGO
                )
            ]
            
            # Mock extraction to return content
            mock_extract.return_value = [
                ExtractedContent(
                    url="https://example.com",
                    title="Test Result",
                    content="Test content about the query",
                    success=True
                )
            ]
            
            agent = AutonomousResearchAgent()
            summary = await agent.quick_research("test query")
            assert summary.key_points == ["Mock point"]
            await agent.close()


class TestSearchEngines:
    """Test search engines (mocked)."""

    @pytest.mark.asyncio
    async def test_duckduckgo_search_mock(self):
        with patch('httpx.AsyncClient'):
            engine = DuckDuckGoSearchEngine()
            # Mock the client
            engine.client = AsyncMock()
            engine.client.post = AsyncMock(return_value=Mock(
                text="""
                <html>
                    <a class="result__url">Test Title</a>
                    <a class="result__snippet" href="/url?q=https://example.com">Link</a>
                    <a class="result__snippet">Test snippet</a>
                </html>
                """,
                raise_for_status=Mock()
            ))

            results = await engine.search("test", max_results=5)
            await engine.close()
            # Just verify it doesn't crash
            assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])