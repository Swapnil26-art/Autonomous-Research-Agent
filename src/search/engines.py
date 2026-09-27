"""Search engine implementations for the Autonomous Research Agent."""
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.models import SearchEngine, SearchResult, SourceType
from src.config import get_settings


class BaseSearchEngine(ABC):
    """Abstract base class for search engines."""

    def __init__(self, engine_name: SearchEngine):
        self.engine_name = engine_name
        self.settings = get_settings().search
        self.client = httpx.AsyncClient(
            timeout=self.settings.timeout,
            headers={"User-Agent": self.settings.user_agent}
        )

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Perform a search and return results."""
        pass

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def _create_result(
        self,
        title: str,
        url: str,
        snippet: str,
        source_type: SourceType = SourceType.WEBSITE,
        relevance_score: float = 0.0
    ) -> SearchResult:
        """Create a SearchResult object."""
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet,
            source=self.engine_name,
            source_type=source_type,
            relevance_score=relevance_score
        )


class DuckDuckGoSearchEngine(BaseSearchEngine):
    """DuckDuckGo search engine implementation."""

    def __init__(self):
        super().__init__(SearchEngine.DUCKDUCKGO)
        self.base_url = "https://html.duckduckgo.com/html/"

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Search using DuckDuckGo HTML interface."""
        results = []
        try:
            params = {"q": query, "kl": "us-en"}
            response = await self.client.post(self.base_url, data=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            result_elements = soup.select(".result__snippet")

            for i, elem in enumerate(result_elements[:max_results]):
                try:
                    title_elem = elem.find_previous("a", class_="result__url")
                    link_elem = elem.find_previous("a", class_="result__snippet")

                    title = title_elem.get_text(strip=True) if title_elem else "No title"
                    url = link_elem.get("href", "") if link_elem else ""
                    snippet = elem.get_text(strip=True)

                    if url and not url.startswith("http"):
                        url = "https:" + url if url.startswith("//") else "https://" + url

                    relevance = 1.0 - (i * 0.1)
                    results.append(self._create_result(title, url, snippet, relevance_score=relevance))

                except Exception as e:
                    logger.warning(f"Error parsing DuckDuckGo result: {e}")
                    continue

        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")

        return results


class GoogleSearchEngine(BaseSearchEngine):
    """Google Custom Search API implementation."""

    def __init__(self):
        super().__init__(SearchEngine.GOOGLE)
        self.api_key = get_settings().search.google_api_key
        self.cse_id = get_settings().search.google_cse_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Search using Google Custom Search API."""
        results = []

        if not self.api_key or not self.cse_id:
            logger.warning("Google Search API not configured")
            return results

        try:
            params = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": query,
                "num": min(max_results, 10)
            }

            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            for i, item in enumerate(data.get("items", [])):
                title = item.get("title", "No title")
                url = item.get("link", "")
                snippet = item.get("snippet", "")
                relevance = 1.0 - (i * 0.1)
                results.append(self._create_result(title, url, snippet, relevance_score=relevance))

        except Exception as e:
            logger.error(f"Google search failed: {e}")

        return results


class BingSearchEngine(BaseSearchEngine):
    """Bing Search API implementation."""

    def __init__(self):
        super().__init__(SearchEngine.BING)
        self.api_key = get_settings().search.bing_api_key
        self.base_url = "https://api.bing.microsoft.com/v7.0/search"

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Search using Bing Search API."""
        results = []

        if not self.api_key:
            logger.warning("Bing Search API not configured")
            return results

        try:
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            params = {"q": query, "count": min(max_results, 50), "responseFilter": "Webpages"}

            response = await self.client.get(self.base_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            for i, item in enumerate(data.get("webPages", {}).get("value", [])):
                title = item.get("name", "No title")
                url = item.get("url", "")
                snippet = item.get("snippet", "")
                relevance = 1.0 - (i * 0.1)
                results.append(self._create_result(title, url, snippet, relevance_score=relevance))

        except Exception as e:
            logger.error(f"Bing search failed: {e}")

        return results


class SerperSearchEngine(BaseSearchEngine):
    """Serper.dev search API implementation."""

    def __init__(self):
        super().__init__(SearchEngine.SERPER)
        self.api_key = get_settings().search.serper_api_key
        self.base_url = "https://google.serper.dev/search"

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Search using Serper.dev API."""
        results = []

        if not self.api_key:
            logger.warning("Serper API not configured")
            return results

        try:
            headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
            payload = {"q": query, "num": max_results}

            response = await self.client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            for i, item in enumerate(data.get("organic", [])):
                title = item.get("title", "No title")
                url = item.get("link", "")
                snippet = item.get("snippet", "")
                relevance = 1.0 - (i * 0.1)
                results.append(self._create_result(title, url, snippet, relevance_score=relevance))

        except Exception as e:
            logger.error(f"Serper search failed: {e}")

        return results


class SearchManager:
    """Manages multiple search engines and coordinates searches."""

    def __init__(self):
        self.settings = get_settings().search
        self.engines: dict[SearchEngine, BaseSearchEngine] = {}
        self._init_engines()

    def _init_engines(self):
        """Initialize enabled search engines."""
        if self.settings.duckduckgo_enabled:
            self.engines[SearchEngine.DUCKDUCKGO] = DuckDuckGoSearchEngine()

        if self.settings.google_enabled:
            self.engines[SearchEngine.GOOGLE] = GoogleSearchEngine()

        if self.settings.bing_enabled:
            self.engines[SearchEngine.BING] = BingSearchEngine()

        if self.settings.serper_enabled:
            self.engines[SearchEngine.SERPER] = SerperSearchEngine()

        # Ensure at least DuckDuckGo is available
        if SearchEngine.DUCKDUCKGO not in self.engines:
            self.engines[SearchEngine.DUCKDUCKGO] = DuckDuckGoSearchEngine()

    async def search(
        self,
        query: str,
        engines: Optional[list[SearchEngine]] = None,
        max_results: int = 10
    ) -> list[SearchResult]:
        """
        Search across multiple engines in parallel.

        Args:
            query: Search query
            engines: List of engines to use (None = all enabled)
            max_results: Maximum results per engine

        Returns:
            Combined and deduplicated search results
        """
        if engines is None:
            engines = list(self.engines.keys())

        # Filter to only available engines
        available_engines = [e for e in engines if e in self.engines]

        if not available_engines:
            logger.warning("No search engines available")
            return []

        # Search in parallel
        tasks = [
            self.engines[engine].search(query, max_results)
            for engine in available_engines
        ]

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        combined_results = []
        for engine, results in zip(available_engines, all_results):
            if isinstance(results, Exception):
                logger.error(f"Search failed for {engine}: {results}")
                continue
            combined_results.extend(results)

        # Deduplicate by URL
        seen_urls = set()
        deduplicated = []
        for result in combined_results:
            url_str = str(result.url)
            if url_str not in seen_urls:
                seen_urls.add(url_str)
                deduplicated.append(result)

        # Sort by relevance score
        deduplicated.sort(key=lambda x: x.relevance_score, reverse=True)

        return deduplicated[:max_results]

    async def close(self):
        """Close all search engine clients."""
        for engine in self.engines.values():
            await engine.close()


async def search_web(
    query: str,
    engines: Optional[list[SearchEngine]] = None,
    max_results: int = 10
) -> list[SearchResult]:
    """Convenience function for web search."""
    manager = SearchManager()
    try:
        return await manager.search(query, engines, max_results)
    finally:
        await manager.close()