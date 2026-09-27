# Autonomous Research Agent

An autonomous AI agent capable of collecting information from external sources, analyzing it, and generating structured, actionable summaries.

## Features

- **Autonomous Source Selection**: Automatically selects the most appropriate search engines based on query type
- **Parallel Information Gathering**: Searches multiple sources concurrently for faster results
- **Multi-Source Search**: Supports DuckDuckGo, Google, Bing, and Serper.dev
- **Smart Content Extraction**: Uses multiple extraction methods (trafilatura, readability, BeautifulSoup)
- **Deduplication & Filtering**: Removes duplicate and irrelevant content automatically
- **LLM-Powered Summarization**: Generates structured summaries with key points, findings, and actionable insights
- **Multiple Export Formats**: Export to Markdown, PDF, JSON, or HTML
- **Persistent Memory**: Stores research sessions in SQLite for history and retrieval
- **CLI Interface**: Easy-to-use command-line interface

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd Autonomous-Research-Agent

# Install dependencies
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

## Configuration

The agent can be configured via:
1. Environment variables (`.env` file)
2. YAML configuration (`config/settings.yaml`)

Key settings:
- **LLM Provider**: OpenAI (default) or Anthropic
- **Search Engines**: Enable/disable DuckDuckGo, Google, Bing, Serper
- **Export Formats**: Markdown, PDF, JSON, HTML
- **Parallel Processing**: Configure concurrency limits

## Usage

### CLI Commands

```bash
# Basic research
research-agent research "quantum computing applications"

# With specific engines
research-agent research "AI safety" --engines duckduckgo,google

# Quick summary only
research-agent quick "latest Python features"

# Export to multiple formats
research-agent research "climate change solutions" --export markdown,pdf,json

# View history
research-agent history --limit 10

# Search history
research-agent history --search "quantum"

# Show session details
research-agent show <session-id>

# Export previous session
research-agent export <session-id> --formats markdown,pdf

# View statistics
research-agent stats

# Cleanup old sessions
research-agent cleanup --days 30

# Show configuration
research-agent config --show
```

### Python API

```python
import asyncio
from src.agent import AutonomousResearchAgent, run_research
from src.models import ExportFormat

# Simple usage
async def main():
    agent = AutonomousResearchAgent()
    session = await agent.research(
        query="impact of AI on healthcare",
        max_results=10,
        export_formats=[ExportFormat.MARKDOWN, ExportFormat.PDF]
    )
    print(session.summary.key_points)
    await agent.close()

asyncio.run(main())

# Or use convenience function
session = asyncio.run(run_research("quantum computing breakthroughs"))
```

## Architecture

```
src/
├── agent/           # Main agent orchestration
├── search/          # Search engines & source selection
├── extraction/      # Content extraction & deduplication
├── summarization/   # LLM-based summarization
├── export/          # Export to multiple formats
├── memory/          # Persistent storage
├── cli/             # Command-line interface
└── config.py        # Configuration management
```

## Requirements

- Python 3.10+
- OpenAI API key (or Anthropic)
- Optional: Google Custom Search API, Bing Search API, Serper.dev API

## Environment Variables

```env
# Required
OPENAI_API_KEY=your_key_here

# Optional - for enhanced search
ANTHROPIC_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
GOOGLE_CSE_ID=your_cse_id
BING_API_KEY=your_key_here
SERPER_API_KEY=your_key_here
```

## Docker

```bash
# Build
docker build -t research-agent .

# Run
docker run -it --rm \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  research-agent research "your query"
```

## Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest --cov=src tests/
```

## License

MIT License - see LICENSE file for details.