"""Autonomous source selection based on query analysis."""
import re
from typing import Optional
from loguru import logger

from src.models import SearchEngine, SourceType
from src.config import get_settings


class SourceSelector:
    """Automatically selects the most appropriate search sources based on query."""

    # Query patterns for different source types
    PATTERNS = {
        SourceType.ACADEMIC: [
            r"\b(research|paper|study|journal|academic|scholar|publication)\b",
            r"\b(peer.review|doi|arxiv|pubmed|ieee|acm|springer)\b",
            r"\b(literature.review|meta.analysis|systematic.review)\b",
        ],
        SourceType.NEWS: [
            r"\b(news|latest|recent|breaking|today|yesterday|this.week)\b",
            r"\b(current.events|headlines|press.release|announcement)\b",
        ],
        SourceType.DOCUMENTATION: [
            r"\b(documentation|docs|api.reference|tutorial|guide|how.to)\b",
            r"\b(README|specification|manual|handbook)\b",
            r"\b(github|gitlab|npm|pypi|docker|kubernetes)\b",
        ],
        SourceType.SOCIAL: [
            r"\b(reddit|twitter|x\.com|linkedin|facebook|discord|slack)\b",
            r"\b(community|forum|discussion|opinion|review)\b",
        ],
    }

    # Engine preferences by source type
    ENGINE_PREFERENCES = {
        SourceType.ACADEMIC: [SearchEngine.GOOGLE, SearchEngine.SERPER, SearchEngine.DUCKDUCKGO],
        SourceType.NEWS: [SearchEngine.GOOGLE, SearchEngine.BING, SearchEngine.DUCKDUCKGO],
        SourceType.DOCUMENTATION: [SearchEngine.GOOGLE, SearchEngine.DUCKDUCKGO, SearchEngine.BING],
        SourceType.SOCIAL: [SearchEngine.DUCKDUCKGO, SearchEngine.BING],
        SourceType.WEBSITE: [SearchEngine.DUCKDUCKGO, SearchEngine.GOOGLE, SearchEngine.BING],
    }

    def __init__(self):
        self.settings = get_settings().search
        self._compiled_patterns = {
            source_type: [re.compile(p, re.IGNORECASE) for p in patterns]
            for source_type, patterns in self.PATTERNS.items()
        }

    def analyze_query(self, query: str) -> SourceType:
        """
        Analyze query and determine the most likely source type.

        Returns:
            The detected source type
        """
        scores = {source_type: 0 for source_type in SourceType}

        for source_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                matches = len(pattern.findall(query))
                scores[source_type] += matches

        # Default to WEBSITE if no specific type detected
        detected_type = max(scores, key=scores.get)
        if scores[detected_type] == 0:
            detected_type = SourceType.WEBSITE

        logger.info(f"Query analyzed as: {detected_type.value} (scores: {scores})")
        return detected_type

    def select_engines(
        self,
        query: str,
        source_type: Optional[SourceType] = None,
        max_engines: int = 3
    ) -> list[SearchEngine]:
        """
        Select the best search engines for a query.

        Args:
            query: The search query
            source_type: Optional pre-detected source type
            max_engines: Maximum number of engines to return

        Returns:
            List of selected search engines in priority order
        """
        if source_type is None:
            source_type = self.analyze_query(query)

        # Get preferred engines for this source type
        preferred = self.ENGINE_PREFERENCES.get(source_type, self.ENGINE_PREFERENCES[SourceType.WEBSITE])

        # Filter to only enabled engines
        available_engines = []
        for engine in preferred:
            if engine == SearchEngine.DUCKDUCKGO:
                available_engines.append(engine)
            elif engine == SearchEngine.GOOGLE and self.settings.google_enabled:
                available_engines.append(engine)
            elif engine == SearchEngine.BING and self.settings.bing_enabled:
                available_engines.append(engine)
            elif engine == SearchEngine.SERPER and self.settings.serper_enabled:
                available_engines.append(engine)

        # Always ensure DuckDuckGo is included as fallback
        if SearchEngine.DUCKDUCKGO not in available_engines:
            available_engines.insert(0, SearchEngine.DUCKDUCKGO)

        return available_engines[:max_engines]

    def refine_query(self, query: str, source_type: SourceType) -> str:
        """
        Refine query based on source type for better results.

        Args:
            query: Original query
            source_type: Detected source type

        Returns:
            Refined query
        """
        refinements = {
            SourceType.ACADEMIC: " site:scholar.google.com OR site:arxiv.org OR site:pubmed.ncbi.nlm.nih.gov",
            SourceType.NEWS: " site:news.google.com OR site:reuters.com OR site:apnews.com OR site:bbc.com",
            SourceType.DOCUMENTATION: " site:docs. OR site:github.com OR site:gitlab.com OR site:readthedocs.io",
            SourceType.SOCIAL: " site:reddit.com OR site:twitter.com OR site:linkedin.com",
        }

        refinement = refinements.get(source_type, "")
        if refinement and refinement not in query:
            return f"{query} {refinement}"

        return query