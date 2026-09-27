"""Data models for the Autonomous Research Agent."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl
from uuid import uuid4


class SearchEngine(str, Enum):
    DUCKDUCKGO = "duckduckgo"
    GOOGLE = "google"
    BING = "bing"
    SERPER = "serper"


class SourceType(str, Enum):
    WEBSITE = "website"
    API = "api"
    DOCUMENTATION = "documentation"
    NEWS = "news"
    ACADEMIC = "academic"
    SOCIAL = "social"


class SearchResult(BaseModel):
    """A single search result."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    url: HttpUrl
    snippet: str
    source: SearchEngine
    source_type: SourceType = SourceType.WEBSITE
    relevance_score: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExtractedContent(BaseModel):
    """Extracted content from a URL."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    url: HttpUrl
    title: str
    content: str
    raw_html: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    word_count: int = 0
    extraction_time: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True
    error: Optional[str] = None


class ResearchQuery(BaseModel):
    """A research query from the user."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    refined_query: Optional[str] = None
    selected_engines: list[SearchEngine] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"


class SummarySection(BaseModel):
    """A section of the research summary."""
    title: str
    content: str
    sources: list[str] = Field(default_factory=list)


class ResearchSummary(BaseModel):
    """Complete research summary."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    query_id: str
    query: str
    sections: list[SummarySection] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    important_findings: list[str] = Field(default_factory=list)
    actionable_insights: list[str] = Field(default_factory=list)
    references: list[SearchResult] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_sources: int = 0
    processing_time: float = 0.0


class ResearchSession(BaseModel):
    """A complete research session with history."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    query: ResearchQuery
    search_results: list[SearchResult] = Field(default_factory=list)
    extracted_content: list[ExtractedContent] = Field(default_factory=list)
    summary: Optional[ResearchSummary] = None
    exports: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = "in_progress"


class ExportFormat(str, Enum):
    MARKDOWN = "markdown"
    PDF = "pdf"
    JSON = "json"
    HTML = "html"


class ExportRequest(BaseModel):
    """Request to export a summary."""
    summary_id: str
    format: ExportFormat
    output_path: Optional[str] = None
    include_metadata: bool = True