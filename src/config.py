"""Configuration management for the Autonomous Research Agent."""
import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class LLMSettings(BaseSettings):
    provider: str = "openai"
    model: str = "gpt-4-turbo-preview"
    temperature: float = 0.3
    max_tokens: int = 4000
    timeout: int = 60

    model_config = SettingsConfigDict(env_prefix="LLM_")


class SearchEngineSettings(BaseSettings):
    duckduckgo_enabled: bool = True
    duckduckgo_max_results: int = 10
    google_enabled: bool = False
    google_api_key: str = ""
    google_cse_id: str = ""
    bing_enabled: bool = False
    bing_api_key: str = ""
    serper_enabled: bool = False
    serper_api_key: str = ""
    default_engine: str = "duckduckgo"
    max_results: int = 10
    timeout: int = 30
    user_agent: str = "AutonomousResearchAgent/1.0"

    model_config = SettingsConfigDict(env_prefix="SEARCH_")


class ExtractionSettings(BaseSettings):
    timeout: int = 15
    min_content_length: int = 100
    max_content_length: int = 50000
    remove_selectors: list[str] = Field(default_factory=lambda: [
        "nav", "footer", "header", "aside", ".advertisement", ".ads",
        "#comments", ".sidebar", "script", "style"
    ])

    model_config = SettingsConfigDict(env_prefix="EXTRACTION_")


class SummarizationSettings(BaseSettings):
    chunk_size: int = 3000
    chunk_overlap: int = 200
    max_chunks: int = 10
    summary_sections: list[str] = Field(default_factory=lambda: [
        "key_points", "important_findings", "actionable_insights", "references"
    ])

    model_config = SettingsConfigDict(env_prefix="SUMMARIZATION_")


class ExportSettings(BaseSettings):
    formats: list[str] = Field(default_factory=lambda: ["markdown", "pdf"])
    output_dir: str = "./output"
    pdf_page_size: str = "A4"
    pdf_margin: str = "2cm"
    pdf_font_family: str = "Helvetica"
    pdf_font_size: int = 11

    model_config = SettingsConfigDict(env_prefix="EXPORT_")


class MemorySettings(BaseSettings):
    db_path: str = "./data/research_agent.db"
    max_history: int = 100
    retention_days: int = 90

    model_config = SettingsConfigDict(env_prefix="MEMORY_")


class ParallelSettings(BaseSettings):
    max_concurrent_searches: int = 5
    max_concurrent_extractions: int = 3
    request_delay: float = 1.0

    model_config = SettingsConfigDict(env_prefix="PARALLEL_")


class LoggingSettings(BaseSettings):
    level: str = "INFO"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    file: str = "./logs/agent.log"
    rotation: str = "10 MB"
    retention: str = "30 days"

    model_config = SettingsConfigDict(env_prefix="LOG_")


class Settings(BaseSettings):
    app_name: str = "Autonomous Research Agent"
    app_version: str = "1.0.0"
    debug: bool = False

    llm: LLMSettings = Field(default_factory=LLMSettings)
    search: SearchEngineSettings = Field(default_factory=SearchEngineSettings)
    extraction: ExtractionSettings = Field(default_factory=ExtractionSettings)
    summarization: SummarizationSettings = Field(default_factory=SummarizationSettings)
    export: ExportSettings = Field(default_factory=ExportSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    parallel: ParallelSettings = Field(default_factory=ParallelSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @classmethod
    def from_yaml(cls, path: str) -> "Settings":
        """Load settings from YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data.get("app", {}))


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        config_path = Path("config/settings.yaml")
        if config_path.exists():
            _settings = Settings.from_yaml(str(config_path))
        else:
            _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from config files."""
    global _settings
    _settings = None
    return get_settings()