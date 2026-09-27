"""Autonomous Research Agent - Main package."""
from src.agent import AutonomousResearchAgent, run_research
from src.models import (
    ResearchSession, ResearchQuery, ResearchSummary,
    SearchResult, ExtractedContent, SearchEngine, SourceType, ExportFormat
)
from src.config import get_settings, Settings

__version__ = "1.0.0"

__all__ = [
    "AutonomousResearchAgent",
    "run_research",
    "ResearchSession",
    "ResearchQuery",
    "ResearchSummary",
    "SearchResult",
    "ExtractedContent",
    "SearchEngine",
    "SourceType",
    "ExportFormat",
    "get_settings",
    "Settings",
]