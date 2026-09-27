"""Extraction module for Autonomous Research Agent."""
from src.extraction.extractor import ContentExtractor
from src.extraction.deduplicator import ContentDeduplicator, ResultRanker

__all__ = [
    "ContentExtractor",
    "ContentDeduplicator",
    "ResultRanker",
]