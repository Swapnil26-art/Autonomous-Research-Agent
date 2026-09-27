"""Content extraction from web pages."""
import asyncio
import hashlib
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup
from loguru import logger
from readability import Document

from src.models import ExtractedContent
from src.config import get_settings


class ContentExtractor:
    """Extracts clean content from web pages."""

    def __init__(self):
        self.settings = get_settings().extraction
        self.client = httpx.AsyncClient(
            timeout=self.settings.timeout,
            headers={"User-Agent": get_settings().search.user_agent},
            follow_redirects=True
        )
        self._seen_content_hashes: set[str] = set()

    async def extract(self, url: str) -> ExtractedContent:
        """
        Extract content from a URL using multiple methods.

        Tries trafilatura first (best for articles), then readability,
        then BeautifulSoup as fallback.
        """
        try:
            # Fetch the page
            response = await self.client.get(url)
            response.raise_for_status()
            html = response.text

            # Try trafilatura first (best for article extraction)
            content = self._extract_with_trafilatura(html, url)

            if not content or len(content) < self.settings.min_content_length:
                # Fallback to readability
                content = self._extract_with_readability(html)

            if not content or len(content) < self.settings.min_content_length:
                # Final fallback to BeautifulSoup
                content = self._extract_with_bs4(html)

            # Clean and validate content
            content = self._clean_content(content)

            # Check for duplicates
            content_hash = self._get_content_hash(content)
            is_duplicate = content_hash in self._seen_content_hashes
            if not is_duplicate:
                self._seen_content_hashes.add(content_hash)

            # Extract title
            title = self._extract_title(html, url)

            # Extract metadata
            metadata = self._extract_metadata(html)

            word_count = len(content.split()) if content else 0

            return ExtractedContent(
                url=url,
                title=title,
                content=content or "",
                raw_html=html if self.settings.max_content_length > len(html) else html[:self.settings.max_content_length],
                metadata=metadata,
                word_count=word_count,
                success=True,
                error=None if not is_duplicate else "Duplicate content detected"
            )

        except Exception as e:
            logger.error(f"Extraction failed for {url}: {e}")
            return ExtractedContent(
                url=url,
                title="Extraction Failed",
                content="",
                success=False,
                error=str(e)
            )

    def _extract_with_trafilatura(self, html: str, url: str) -> Optional[str]:
        """Extract using trafilatura (best for articles)."""
        try:
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                url=url
            )
            return extracted
        except Exception as e:
            logger.debug(f"Trafilatura extraction failed: {e}")
            return None

    def _extract_with_readability(self, html: str) -> Optional[str]:
        """Extract using readability-lxml."""
        try:
            doc = Document(html)
            content = doc.summary()
            soup = BeautifulSoup(content, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        except Exception as e:
            logger.debug(f"Readability extraction failed: {e}")
            return None

    def _extract_with_bs4(self, html: str) -> Optional[str]:
        """Extract using BeautifulSoup with selector removal."""
        try:
            soup = BeautifulSoup(html, "lxml")

            # Remove unwanted elements
            for selector in self.settings.remove_selectors:
                for elem in soup.select(selector):
                    elem.decompose()

            # Get main content
            # Try common content containers
            main_content = (
                soup.find("main") or
                soup.find("article") or
                soup.find("div", class_=re.compile(r"(content|main|article|post)", re.I)) or
                soup.find("div", id=re.compile(r"(content|main|article|post)", re.I)) or
                soup.body
            )

            if main_content:
                return main_content.get_text(separator="\n", strip=True)

            return soup.get_text(separator="\n", strip=True)

        except Exception as e:
            logger.debug(f"BeautifulSoup extraction failed: {e}")
            return None

    def _clean_content(self, content: Optional[str]) -> Optional[str]:
        """Clean and normalize extracted content."""
        if not content:
            return None

        # Normalize whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r" {2,}", " ", content)
        content = content.strip()

        # Truncate if too long
        if len(content) > self.settings.max_content_length:
            content = content[:self.settings.max_content_length] + "..."

        return content if len(content) >= self.settings.min_content_length else None

    def _extract_title(self, html: str, url: str) -> str:
        """Extract page title."""
        try:
            soup = BeautifulSoup(html, "lxml")
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                return title_tag.string.strip()

            # Try og:title
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                return og_title["content"].strip()

            # Try h1
            h1 = soup.find("h1")
            if h1:
                return h1.get_text(strip=True)

        except Exception:
            pass

        # Fallback to domain
        return urlparse(url).netloc

    def _extract_metadata(self, html: str) -> dict:
        """Extract metadata from page."""
        metadata = {}
        try:
            soup = BeautifulSoup(html, "lxml")

            # Meta tags
            for meta in soup.find_all("meta"):
                name = meta.get("name") or meta.get("property")
                content = meta.get("content")
                if name and content:
                    metadata[name] = content

            # JSON-LD structured data
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    import json
                    data = json.loads(script.string)
                    metadata["json_ld"] = data
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Metadata extraction failed: {e}")

        return metadata

    def _get_content_hash(self, content: str) -> str:
        """Generate hash for duplicate detection."""
        # Normalize for comparison
        normalized = re.sub(r"\s+", " ", content.lower().strip())
        return hashlib.md5(normalized.encode()).hexdigest()

    async def extract_batch(self, urls: list[str], max_concurrent: int = 3) -> list[ExtractedContent]:
        """Extract content from multiple URLs with concurrency control."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_with_semaphore(url: str) -> ExtractedContent:
            async with semaphore:
                return await self.extract(url)

        tasks = [extract_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        extracted = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.error(f"Batch extraction failed for {url}: {result}")
                extracted.append(ExtractedContent(
                    url=url,
                    title="Error",
                    content="",
                    success=False,
                    error=str(result)
                ))
            else:
                extracted.append(result)

        return extracted

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def reset_duplicate_cache(self):
        """Reset the duplicate detection cache."""
        self._seen_content_hashes.clear()