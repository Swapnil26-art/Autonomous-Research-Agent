# Autonomous Research Agent

**Assessment Project: Autonomous AI Research Agent**

An autonomous AI agent capable of collecting information from external sources, analyzing it, and generating structured, actionable summaries.

---

## Assessment Requirements Coverage

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Accept user query/topic | ✅ | CLI `research-agent research "query"` |
| Search external sources | ✅ | DuckDuckGo, Google, Bing, Serper.dev |
| Extract relevant information | ✅ | trafilatura, readability, BeautifulSoup |
| Remove duplicate/irrelevant content | ✅ | ContentDeduplicator + relevance filtering |
| Generate structured summary | ✅ | Key points, findings, insights, references |
| **Bonus: Autonomous source selection** | ✅ | SourceSelector analyzes query type |
| **Bonus: Parallel information gathering** | ✅ | asyncio with semaphore concurrency control |
| **Bonus: Export as PDF/Markdown** | ✅ | Markdown, PDF, JSON, HTML exporters |
| **Bonus: Store previous searches** | ✅ | SQLite persistent memory |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Swapnil26-art/Autonomous-Research-Agent.git
cd Autonomous-Research-Agent

# 2. Install
pip install -e .

# 3. Configure API key
cp .env.example .env
# Edit .env and add: GEMINI_API_KEY=your_key_here
# Set: LLM_PROVIDER=gemini

# 4. Run research
research-agent research "quantum computing applications"
```

---

## Configuration

### Environment Variables (`.env`)

```env
# LLM Provider (choose one)
LLM_PROVIDER=gemini          # openai | anthropic | gemini
LLM_MODEL=gemini-1.5-pro     # model name
GEMINI_API_KEY=your_key_here # REQUIRED for gemini
OPENAI_API_KEY=your_key_here # for openai
ANTHROPIC_API_KEY=your_key_here # for anthropic

# Optional: Enhanced search APIs
GOOGLE_API_KEY=your_key_here
GOOGLE_CSE_ID=your_cse_id
BING_API_KEY=your_key_here
SERPER_API_KEY=your_key_here

# App settings
APP_DEBUG=false
LOG_LEVEL=INFO
```

### YAML Config (`config/settings.yaml`)

Advanced settings for search, extraction, summarization, export, memory, parallel processing.

---

## CLI Usage

```bash
# Basic research with auto source selection
research-agent research "impact of AI on healthcare"

# Specify search engines
research-agent research "Python async patterns" --engines duckduckgo,google

# Quick summary (no exports)
research-agent quick "latest TypeScript features"

# Export to multiple formats
research-agent research "climate change solutions" --export markdown,pdf,json

# History & search
research-agent history --limit 20
research-agent history --search "quantum"

# View session details
research-agent show <session-id>

# Export previous session
research-agent export <session-id> --formats markdown,pdf

# Statistics & cleanup
research-agent stats
research-agent cleanup --days 90

# View current config
research-agent config --show
```

---

## Python API

```python
import asyncio
from src.agent import AutonomousResearchAgent, run_research
from src.models import ExportFormat, SearchEngine

# Simple usage
async def main():
    agent = AutonomousResearchAgent()
    session = await agent.research(
        query="impact of AI on healthcare",
        max_results=10,
        export_formats=[ExportFormat.MARKDOWN, ExportFormat.PDF]
    )
    print("Key Points:", session.summary.key_points)
    print("Findings:", session.summary.important_findings)
    print("Insights:", session.summary.actionable_insights)
    await agent.close()

asyncio.run(main())

# With custom engines
session = await agent.research(
    query="quantum computing breakthroughs",
    engines=[SearchEngine.DUCKDUCKGO, SearchEngine.GOOGLE],
    max_results=15,
    auto_select_sources=False
)

# Quick research (summary only)
summary = await agent.quick_research("your query")
```

---

## Architecture

```
src/
├── agent/
│   └── research_agent.py      # Main orchestration
├── search/
│   ├── engines.py             # DuckDuckGo, Google, Bing, Serper
│   └── selector.py            # Autonomous source selection
├── extraction/
│   ├── extractor.py           # Multi-method content extraction
│   └── deduplicator.py        # Deduplication + relevance filtering
├── summarization/
│   └── summarizer.py          # OpenAI, Anthropic, Gemini summarizers
├── export/
│   └── exporter.py            # Markdown, PDF, JSON, HTML
├── memory/
│   └── manager.py             # SQLite persistent storage
├── cli/
│   └── main.py                # Rich CLI interface
├── config.py                  # Pydantic settings management
└── models.py                  # Pydantic data models
```

---

## Key Features Explained

### Autonomous Source Selection
```python
# Automatically detects query type and selects best engines
source_type = selector.analyze_query("latest research on transformers")
# → SourceType.ACADEMIC
engines = selector.select_engines(query)
# → [GOOGLE, SERPER, DUCKDUCKGO] for academic
```

### Parallel Processing
- Concurrent searches across engines
- Concurrent content extraction (configurable semaphore)
- Configurable via `parallel.max_concurrent_searches/extractions`

### Deduplication Pipeline
1. Exact duplicate detection (content hash)
2. Near-duplicate detection (Jaccard similarity)
3. Relevance filtering (query term coverage)

### Structured Summarization
Output includes:
- **Key Points** - 5-7 concise bullet points
- **Important Findings** - 3-5 significant discoveries
- **Actionable Insights** - 3-5 practical recommendations
- **References** - Full source citations with snippets

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Specific test class
pytest tests/test_agent.py::TestSourceSelector -v
```

**Test Results:** 20/20 passing

---

## Docker Deployment

```bash
# Build
docker build -t autonomous-research-agent .

# Run with API key
docker run -it --rm \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e LLM_PROVIDER=gemini \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  autonomous-research-agent research "your query"

# Or use docker-compose
docker-compose run --rm research-agent research "your query"
```

---

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`):
- Lint: Ruff + Black
- Type check: MyPy
- Tests: pytest with coverage
- Docker build on push/release
- Auto-changelog on release

---

## Project Structure

```
Autonomous-Research-Agent/
├── .github/workflows/ci.yml   # CI/CD
├── config/settings.yaml       # YAML configuration
├── src/                       # Source code (see Architecture)
├── tests/
│   ├── conftest.py            # Pytest fixtures
│   └── test_agent.py          # 20 unit/integration tests
├── .env.example               # Environment template (no real keys)
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── main.py                    # Entry point
├── pyproject.toml             # Package config
├── requirements.txt           # Dependencies
└── README.md                  # This file
```

---

## Dependencies

**Core:**
- `pydantic`, `pydantic-settings` - Configuration & models
- `httpx`, `beautifulsoup4`, `lxml` - HTTP & parsing
- `trafilatura`, `readability-lxml` - Content extraction
- `duckduckgo-search` - Default search engine

**LLM:**
- `openai` - OpenAI API
- `anthropic` - Anthropic API
- `google-generativeai` - Gemini API

**Export:**
- `markdown2` - Markdown processing
- `reportlab` - PDF generation
- `rich`, `typer` - CLI interface

**Storage:**
- `sqlalchemy` - SQLite ORM

**Dev:**
- `pytest`, `pytest-asyncio` - Testing
- `ruff`, `black`, `mypy` - Linting/formatting

---

## Security Notes

- **Never commit `.env` files** - they're in `.gitignore`
- Only `.env.example` with placeholders is tracked
- API keys loaded from environment at runtime
- Database stored locally in `data/research_agent.db`

---

## License

MIT License - see LICENSE file for details.

---

## Assessment Submission

This project fulfills all core requirements and bonus features:

1. ✅ **User query acceptance** - CLI & Python API
2. ✅ **External source search** - 4 search engines
3. ✅ **Information extraction** - Multi-method with fallbacks
4. ✅ **Deduplication & filtering** - Exact + near-duplicate + relevance
5. ✅ **Structured summary** - Key points, findings, insights, references
6. ✅ **Autonomous source selection** - Query analysis → engine selection
7. ✅ **Parallel gathering** - asyncio concurrency
8. ✅ **Multi-format export** - Markdown, PDF, JSON, HTML
9. ✅ **Persistent memory** - SQLite with full session history

**Repository:** https://github.com/Swapnil26-art/Autonomous-Research-Agent