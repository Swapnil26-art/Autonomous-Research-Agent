"""Pytest configuration and fixtures."""
import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    tmp = Path(tempfile.mkdtemp())
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    from src.config import Settings, LLMSettings, SearchEngineSettings, ExtractionSettings
    from src.config import SummarizationSettings, ExportSettings, MemorySettings, ParallelSettings, LoggingSettings

    settings = Settings(
        debug=True,
        llm=LLMSettings(provider="openai", model="gpt-3.5-turbo"),
        search=SearchEngineSettings(
            duckduckgo_enabled=True,
            google_enabled=False,
            bing_enabled=False,
            serper_enabled=False
        ),
        extraction=ExtractionSettings(),
        summarization=SummarizationSettings(),
        export=ExportSettings(output_dir=str(tempfile.mkdtemp())),
        memory=MemorySettings(db_path=str(Path(tempfile.mkdtemp()) / "test.db")),
        parallel=ParallelSettings(),
        logging=LoggingSettings(level="DEBUG")
    )

    import src.config
    src.config._settings = settings
    yield settings
    src.config._settings = None


# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio