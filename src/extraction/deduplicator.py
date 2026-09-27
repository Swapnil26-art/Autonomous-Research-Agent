"""Content deduplication and relevance filtering."""
import hashlib
import re
from typing import Optional
from loguru import logger

from src.models import ExtractedContent, SearchResult
from src.config import get_settings


class ContentDeduplicator:
    """Removes duplicate and irrelevant content from extracted results."""

    def __init__(self):
        self.settings = get_settings().extraction
        self._content_hashes: set[str] = set()
        self._similarity_threshold = 0.85

    def deduplicate(self, contents: list[ExtractedContent]) -> list[ExtractedContent]:
        """
        Remove duplicate content based on content hash and similarity.

        Args:
            contents: List of extracted content

        Returns:
            Deduplicated list
        """
        unique_contents = []
        seen_hashes = set()

        for content in contents:
            if not content.success or not content.content:
                # Keep failed extractions for debugging
                unique_contents.append(content)
                continue

            content_hash = self._get_content_hash(content.content)

            if content_hash in seen_hashes:
                logger.debug(f"Duplicate removed: {content.url}")
                continue

            # Check for near-duplicates using similarity
            is_near_duplicate = False
            for existing in unique_contents:
                if existing.success and existing.content:
                    similarity = self._calculate_similarity(content.content, existing.content)
                    if similarity >= self._similarity_threshold:
                        logger.debug(f"Near-duplicate removed (similarity: {similarity:.2f}): {content.url}")
                        is_near_duplicate = True
                        break

            if not is_near_duplicate:
                seen_hashes.add(content_hash)
                unique_contents.append(content)

        logger.info(f"Deduplication: {len(contents)} -> {len(unique_contents)} items")
        return unique_contents

    def filter_relevant(
        self,
        contents: list[ExtractedContent],
        query: str,
        min_relevance: float = 0.1
    ) -> list[ExtractedContent]:
        """
        Filter content by relevance to query.

        Args:
            contents: List of extracted content
            query: Original search query
            min_relevance: Minimum relevance score to keep

        Returns:
            Filtered list sorted by relevance
        """
        query_terms = self._extract_query_terms(query)

        scored_contents = []
        for content in contents:
            if not content.success or not content.content:
                scored_contents.append((0.0, content))
                continue

            relevance = self._calculate_relevance(content.content, query_terms)
            scored_contents.append((relevance, content))

        # Sort by relevance descending
        scored_contents.sort(key=lambda x: x[0], reverse=True)

        # Filter by minimum relevance
        filtered = [c for score, c in scored_contents if score >= min_relevance]

        logger.info(f"Relevance filtering: {len(contents)} -> {len(filtered)} items")
        return filtered

    def _extract_query_terms(self, query: str) -> set[str]:
        """Extract meaningful terms from query."""
        # Remove stop words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "what", "how", "why", "when", "where", "who", "which", "can", "could",
            "should", "would", "will", "shall", "may", "might", "must", "do", "does",
            "did", "have", "has", "had", "i", "you", "he", "she", "it", "we", "they"
        }

        terms = re.findall(r"\b\w+\b", query.lower())
        return {t for t in terms if t not in stop_words and len(t) > 2}

    def _calculate_relevance(self, content: str, query_terms: set[str]) -> float:
        """Calculate relevance score based on query term frequency."""
        if not query_terms:
            return 0.5

        content_lower = content.lower()
        content_words = set(re.findall(r"\b\w+\b", content_lower))

        # Term frequency score
        matches = sum(1 for term in query_terms if term in content_lower)
        tf_score = matches / len(query_terms) if query_terms else 0

        # Coverage score (how many unique query terms appear)
        coverage = len(query_terms & content_words) / len(query_terms) if query_terms else 0

        # Combined score
        return (tf_score * 0.6) + (coverage * 0.4)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two texts."""
        # Use word-level shingles for efficiency
        words1 = set(self._get_shingles(text1))
        words2 = set(self._get_shingles(text2))

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _get_shingles(self, text: str, k: int = 3) -> list[str]:
        """Generate k-shingles from text."""
        words = re.findall(r"\b\w+\b", text.lower())
        return [" ".join(words[i:i+k]) for i in range(len(words) - k + 1)]

    def _get_content_hash(self, content: str) -> str:
        """Generate hash for exact duplicate detection."""
        normalized = re.sub(r"\s+", " ", content.lower().strip())
        return hashlib.md5(normalized.encode()).hexdigest()


class ResultRanker:
    """Ranks search results by relevance and quality."""

    def __init__(self):
        self.settings = get_settings().extraction

    def rank_results(
        self,
        results: list[SearchResult],
        query: str
    ) -> list[SearchResult]:
        """Rank search results by combined relevance and quality signals."""
        query_terms = self._extract_query_terms(query)

        for result in results:
            score = result.relevance_score

            # Boost for exact phrase matches in title
            if query.lower() in result.title.lower():
                score += 0.3

            # Boost for query terms in title
            title_terms = set(re.findall(r"\b\w+\b", result.title.lower()))
            title_match = len(query_terms & title_terms) / len(query_terms) if query_terms else 0
            score += title_match * 0.2

            # Boost for query terms in snippet
            snippet_terms = set(re.findall(r"\b\w+\b", result.snippet.lower()))
            snippet_match = len(query_terms & snippet_terms) / len(query_terms) if query_terms else 0
            score += snippet_match * 0.1

            # Quality signals
            if self._is_high_quality_domain(result.url):
                score += 0.15

            result.relevance_score = min(score, 1.0)

        # Sort by score descending
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    def _extract_query_terms(self, query: str) -> set[str]:
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "what", "how", "why", "when"
        }
        terms = re.findall(r"\b\w+\b", query.lower())
        return {t for t in terms if t not in stop_words and len(t) > 2}

    def _is_high_quality_domain(self, url: str) -> bool:
        """Check if domain is typically high quality."""
        quality_domains = {
            "wikipedia.org", "github.com", "stackoverflow.com", "arxiv.org",
            "pubmed.ncbi.nlm.nih.gov", "scholar.google.com", "docs.python.org",
            "developer.mozilla.org", "aws.amazon.com", "cloud.google.com",
            "microsoft.com", "docs.microsoft.com", "kubernetes.io", "docker.com"
        }
        from urllib.parse import urlparse
        domain = urlparse(str(url)).netloc.lower().replace("www.", "")
        return any(qd in domain for qd in quality_domains)