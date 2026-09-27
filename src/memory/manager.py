"""Memory and storage for research sessions."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
from loguru import logger


def json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for datetime and other types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

from src.models import ResearchSession, ResearchQuery, ResearchSummary, SearchResult, ExtractedContent
from src.config import get_settings


class MemoryManager:
    """Manages persistent storage of research sessions."""

    def __init__(self):
        self.settings = get_settings().memory
        self.db_path = Path(self.settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS research_sessions (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    refined_query TEXT,
                    selected_engines TEXT,
                    status TEXT DEFAULT 'in_progress',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    query_data TEXT
                );

                CREATE TABLE IF NOT EXISTS search_results (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    title TEXT,
                    url TEXT,
                    snippet TEXT,
                    source TEXT,
                    source_type TEXT,
                    relevance_score REAL,
                    timestamp TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES research_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS extracted_content (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    url TEXT,
                    title TEXT,
                    content TEXT,
                    raw_html TEXT,
                    metadata TEXT,
                    word_count INTEGER,
                    extraction_time TIMESTAMP,
                    success BOOLEAN,
                    error TEXT,
                    FOREIGN KEY (session_id) REFERENCES research_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    query_id TEXT,
                    query TEXT,
                    key_points TEXT,
                    important_findings TEXT,
                    actionable_insights TEXT,
                    reference_data TEXT,
                    sections TEXT,
                    generated_at TIMESTAMP,
                    total_sources INTEGER,
                    processing_time REAL,
                    FOREIGN KEY (session_id) REFERENCES research_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS exports (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    format TEXT,
                    output_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES research_sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_created ON research_sessions(created_at);
                CREATE INDEX IF NOT EXISTS idx_results_session ON search_results(session_id);
                CREATE INDEX IF NOT EXISTS idx_content_session ON extracted_content(session_id);
                CREATE INDEX IF NOT EXISTS idx_summaries_session ON summaries(session_id);
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with context management."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_session(self, session: ResearchSession) -> str:
        """Save a research session."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO research_sessions
                (id, query, refined_query, selected_engines, status, created_at, completed_at, query_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.id,
                session.query.query,
                session.query.refined_query,
                json.dumps([e.value for e in session.query.selected_engines]),
                session.status,
                session.created_at.isoformat(),
                session.completed_at.isoformat() if session.completed_at else None,
                json.dumps(session.query.model_dump(), default=json_serializer)
            ))

            # Save search results
            for result in session.search_results:
                conn.execute("""
                    INSERT OR REPLACE INTO search_results
                    (id, session_id, title, url, snippet, source, source_type, relevance_score, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.id, session.id, result.title, str(result.url), result.snippet,
                    result.source.value, result.source_type.value, result.relevance_score,
                    result.timestamp.isoformat()
                ))

            # Save extracted content
            for content in session.extracted_content:
                conn.execute("""
                    INSERT OR REPLACE INTO extracted_content
                    (id, session_id, url, title, content, raw_html, metadata, word_count,
                     extraction_time, success, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    content.id, session.id, str(content.url), content.title, content.content,
                    content.raw_html, json.dumps(content.metadata), content.word_count,
                    content.extraction_time.isoformat(), content.success, content.error
                ))

            # Save summary
            if session.summary:
                conn.execute("""
                    INSERT OR REPLACE INTO summaries
                    (id, session_id, query_id, query, key_points, important_findings,
                     actionable_insights, reference_data, sections, generated_at, total_sources, processing_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.summary.id, session.id, session.summary.query_id, session.summary.query,
                    json.dumps(session.summary.key_points),
                    json.dumps(session.summary.important_findings),
                    json.dumps(session.summary.actionable_insights),
                    json.dumps([r.model_dump() for r in session.summary.references]),
                    json.dumps([s.model_dump() for s in session.summary.sections]),
                    session.summary.generated_at.isoformat(),
                    session.summary.total_sources,
                    session.summary.processing_time
                ))

            # Save exports
            for export_path in session.exports:
                export_id = f"{session.id}_{Path(export_path).suffix[1:]}"
                conn.execute("""
                    INSERT OR REPLACE INTO exports
                    (id, session_id, format, output_path)
                    VALUES (?, ?, ?, ?)
                """, (export_id, session.id, Path(export_path).suffix[1:], export_path))

            conn.commit()

        logger.info(f"Session saved: {session.id}")
        return session.id

    def load_session(self, session_id: str) -> Optional[ResearchSession]:
        """Load a research session by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM research_sessions WHERE id = ?", (session_id,)
            ).fetchone()

            if not row:
                return None

            # Load search results
            results_rows = conn.execute(
                "SELECT * FROM search_results WHERE session_id = ?", (session_id,)
            ).fetchall()

            search_results = []
            for r in results_rows:
                search_results.append(SearchResult(
                    id=r["id"],
                    title=r["title"],
                    url=r["url"],
                    snippet=r["snippet"],
                    source=r["source"],
                    source_type=r["source_type"],
                    relevance_score=r["relevance_score"],
                    timestamp=datetime.fromisoformat(r["timestamp"])
                ))

            # Load extracted content
            content_rows = conn.execute(
                "SELECT * FROM extracted_content WHERE session_id = ?", (session_id,)
            ).fetchall()

            extracted_content = []
            for c in content_rows:
                extracted_content.append(ExtractedContent(
                    id=c["id"],
                    url=c["url"],
                    title=c["title"],
                    content=c["content"],
                    raw_html=c["raw_html"],
                    metadata=json.loads(c["metadata"]) if c["metadata"] else {},
                    word_count=c["word_count"],
                    extraction_time=datetime.fromisoformat(c["extraction_time"]),
                    success=bool(c["success"]),
                    error=c["error"]
                ))

            # Load summary
            summary_row = conn.execute(
                "SELECT * FROM summaries WHERE session_id = ?", (session_id,)
            ).fetchone()

            summary = None
            if summary_row:
                references = []
                for r in json.loads(summary_row["reference_data"]):
                    references.append(SearchResult(**r))

                sections = []
                for s in json.loads(summary_row["sections"]):
                    sections.append(ResearchSummary.model_fields["sections"].type_.__args__[0](**s))

                summary = ResearchSummary(
                    id=summary_row["id"],
                    query_id=summary_row["query_id"],
                    query=summary_row["query"],
                    key_points=json.loads(summary_row["key_points"]),
                    important_findings=json.loads(summary_row["important_findings"]),
                    actionable_insights=json.loads(summary_row["actionable_insights"]),
                    references=references,
                    sections=sections,
                    generated_at=datetime.fromisoformat(summary_row["generated_at"]),
                    total_sources=summary_row["total_sources"],
                    processing_time=summary_row["processing_time"]
                )

            # Load exports
            exports_rows = conn.execute(
                "SELECT output_path FROM exports WHERE session_id = ?", (session_id,)
            ).fetchall()
            exports = [r["output_path"] for r in exports_rows]

            return ResearchSession(
                id=row["id"],
                query=ResearchQuery(
                    id=row["id"],
                    query=row["query"],
                    refined_query=row["refined_query"],
                    selected_engines=[SearchEngine(e) for e in json.loads(row["selected_engines"] or "[]")],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    status=row["status"]
                ),
                search_results=search_results,
                extracted_content=extracted_content,
                summary=summary,
                exports=exports,
                created_at=datetime.fromisoformat(row["created_at"]),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                status=row["status"]
            )

    def get_recent_sessions(self, limit: int = 20) -> list[ResearchQuery]:
        """Get recent research sessions."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT id, query, refined_query, selected_engines, status, created_at
                FROM research_sessions
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

            sessions = []
            for row in rows:
                sessions.append(ResearchQuery(
                    id=row["id"],
                    query=row["query"],
                    refined_query=row["refined_query"],
                    selected_engines=[SearchEngine(e) for e in json.loads(row["selected_engines"] or "[]")],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    status=row["status"]
                ))
            return sessions

    def search_sessions(self, query: str, limit: int = 10) -> list[ResearchQuery]:
        """Search sessions by query text."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT id, query, refined_query, selected_engines, status, created_at
                FROM research_sessions
                WHERE query LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (f"%{query}%", limit)).fetchall()

            sessions = []
            for row in rows:
                sessions.append(ResearchQuery(
                    id=row["id"],
                    query=row["query"],
                    refined_query=row["refined_query"],
                    selected_engines=[SearchEngine(e) for e in json.loads(row["selected_engines"] or "[]")],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    status=row["status"]
                ))
            return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a research session."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM research_sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def cleanup_old_sessions(self, days: Optional[int] = None) -> int:
        """Delete sessions older than specified days."""
        retention_days = days or self.settings.retention_days
        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM research_sessions WHERE created_at < ?",
                (cutoff.isoformat(),)
            )
            conn.commit()
            return cursor.rowcount

    def get_stats(self) -> dict:
        """Get storage statistics."""
        with self._get_connection() as conn:
            stats = {}
            stats["total_sessions"] = conn.execute("SELECT COUNT(*) FROM research_sessions").fetchone()[0]
            stats["total_results"] = conn.execute("SELECT COUNT(*) FROM search_results").fetchone()[0]
            stats["total_content"] = conn.execute("SELECT COUNT(*) FROM extracted_content").fetchone()[0]
            stats["total_summaries"] = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
            stats["total_exports"] = conn.execute("SELECT COUNT(*) FROM exports").fetchone()[0]

            # Database size
            stats["db_size_mb"] = self.db_path.stat().st_size / (1024 * 1024)

            return stats