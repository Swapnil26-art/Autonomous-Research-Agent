"""Main Autonomous Research Agent."""
import asyncio
import time
from datetime import datetime
from typing import Optional
from loguru import logger

from src.models import (
    ResearchSession, ResearchQuery, ResearchSummary,
    SearchResult, ExtractedContent, SearchEngine, SourceType, ExportFormat
)
from src.search import SearchManager, SourceSelector
from src.extraction import ContentExtractor, ContentDeduplicator, ResultRanker
from src.summarization import SummarizerFactory
from src.export import ExportManager, ExportRequest
from src.memory import MemoryManager
from src.config import get_settings


class AutonomousResearchAgent:
    """Main agent that orchestrates the research process."""

    def __init__(self):
        self.settings = get_settings()
        self.search_manager = SearchManager()
        self.source_selector = SourceSelector()
        self.extractor = ContentExtractor()
        self.deduplicator = ContentDeduplicator()
        self.ranker = ResultRanker()
        self.summarizer = SummarizerFactory.create()
        self.exporter = ExportManager()
        self.memory = MemoryManager()

        logger.info("Autonomous Research Agent initialized")

    async def research(
        self,
        query: str,
        engines: Optional[list[SearchEngine]] = None,
        max_results: int = 10,
        auto_select_sources: bool = True,
        export_formats: Optional[list[ExportFormat]] = None
    ) -> ResearchSession:
        """
        Perform autonomous research on a query.

        Args:
            query: The research query
            engines: Optional specific search engines to use
            max_results: Maximum results per engine
            auto_select_sources: Whether to automatically select best sources
            export_formats: Formats to export the summary to

        Returns:
            Complete research session with results and summary
        """
        start_time = time.time()
        logger.info(f"Starting research for: {query}")

        # Create session
        session = ResearchSession(
            query=ResearchQuery(
                query=query,
                selected_engines=engines or []
            )
        )

        # Step 1: Autonomous source selection
        if auto_select_sources and not engines:
            source_type = self.source_selector.analyze_query(query)
            session.query.refined_query = self.source_selector.refine_query(query, source_type)
            session.query.selected_engines = self.source_selector.select_engines(query, source_type)
            logger.info(f"Auto-selected engines: {[e.value for e in session.query.selected_engines]}")
        elif engines:
            session.query.selected_engines = engines
            session.query.refined_query = query

        # Step 2: Parallel search across engines
        logger.info("Searching web...")
        search_results = await self.search_manager.search(
            session.query.refined_query or query,
            session.query.selected_engines,
            max_results
        )
        session.search_results = search_results
        logger.info(f"Found {len(search_results)} search results")

        # Step 3: Rank results
        search_results = self.ranker.rank_results(search_results, query)
        session.search_results = search_results

        # Step 4: Extract content in parallel
        logger.info("Extracting content...")
        urls = [str(r.url) for r in search_results]
        extracted_content = await self.extractor.extract_batch(
            urls,
            max_concurrent=self.settings.parallel.max_concurrent_extractions
        )
        session.extracted_content = extracted_content

        # Step 5: Deduplicate and filter
        logger.info("Deduplicating and filtering...")
        extracted_content = self.deduplicator.deduplicate(extracted_content)
        extracted_content = self.deduplicator.filter_relevant(extracted_content, query)
        session.extracted_content = extracted_content
        logger.info(f"Retained {len([c for c in extracted_content if c.success])} relevant sources")

        # Step 6: Generate summary
        logger.info("Generating summary...")
        summary = await self.summarizer.summarize(
            query,
            extracted_content,
            search_results
        )
        summary.query_id = session.query.id
        session.summary = summary
        session.status = "completed"
        session.completed_at = datetime.utcnow()

        # Step 7: Export if requested
        if export_formats:
            logger.info(f"Exporting to: {[f.value for f in export_formats]}")
            export_results = self.exporter.export_multiple(summary, export_formats)
            session.exports = list(export_results.values())

        # Step 8: Save to memory
        logger.info("Saving to memory...")
        self.memory.save_session(session)

        total_time = time.time() - start_time
        logger.info(f"Research completed in {total_time:.2f}s")

        return session

    async def quick_research(self, query: str) -> ResearchSummary:
        """Quick research with minimal output - just the summary."""
        session = await self.research(query, max_results=5, export_formats=None)
        return session.summary

    def get_history(self, limit: int = 20) -> list[ResearchQuery]:
        """Get recent research history."""
        return self.memory.get_recent_sessions(limit)

    def search_history(self, query: str, limit: int = 10) -> list[ResearchQuery]:
        """Search research history."""
        return self.memory.search_sessions(query, limit)

    def load_session(self, session_id: str) -> Optional[ResearchSession]:
        """Load a previous research session."""
        return self.memory.load_session(session_id)

    def export_session(self, session_id: str, formats: list[ExportFormat]) -> dict[ExportFormat, str]:
        """Export a previous session to specified formats."""
        session = self.load_session(session_id)
        if not session or not session.summary:
            raise ValueError(f"Session {session_id} not found or has no summary")

        return self.exporter.export_multiple(session.summary, formats)

    def get_stats(self) -> dict:
        """Get agent statistics."""
        return self.memory.get_stats()

    async def close(self):
        """Clean up resources."""
        await self.search_manager.close()
        await self.extractor.close()
        logger.info("Agent closed")


async def run_research(
    query: str,
    engines: Optional[list[SearchEngine]] = None,
    max_results: int = 10,
    auto_select: bool = True,
    export: Optional[list[ExportFormat]] = None
) -> ResearchSession:
    """Convenience function to run research."""
    agent = AutonomousResearchAgent()
    try:
        return await agent.research(query, engines, max_results, auto_select, export)
    finally:
        await agent.close()