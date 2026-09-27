"""LLM-based summarization for research results."""
import json
import time
from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger

from src.models import ExtractedContent, ResearchSummary, SummarySection, SearchResult
from src.config import get_settings


class BaseSummarizer(ABC):
    """Abstract base class for summarizers."""

    @abstractmethod
    async def summarize(
        self,
        query: str,
        contents: list[ExtractedContent],
        sources: list[SearchResult]
    ) -> ResearchSummary:
        """Generate a structured summary from extracted content."""
        pass


class OpenAISummarizer(BaseSummarizer):
    """OpenAI-based summarization."""

    def __init__(self):
        self.settings = get_settings()
        self.llm_settings = self.settings.llm
        self.summarization_settings = self.settings.summarization

        # Import here to avoid dependency if not used
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.llm_settings.provider == "openai" and self._get_api_key())
        except ImportError:
            logger.warning("OpenAI not installed, using mock")
            self.client = None

    def _get_api_key(self) -> Optional[str]:
        import os
        return os.getenv("OPENAI_API_KEY")

    async def summarize(
        self,
        query: str,
        contents: list[ExtractedContent],
        sources: list[SearchResult]
    ) -> ResearchSummary:
        """Generate summary using OpenAI."""
        start_time = time.time()

        if not self.client:
            return self._mock_summary(query, contents, sources, start_time)

        # Prepare content for summarization
        combined_content = self._prepare_content(contents)

        # Generate summary sections
        sections = await self._generate_sections(query, combined_content, sources)

        # Extract key points, findings, insights
        key_points = await self._extract_key_points(query, combined_content)
        important_findings = await self._extract_findings(query, combined_content)
        actionable_insights = await self._extract_insights(query, combined_content)

        processing_time = time.time() - start_time

        return ResearchSummary(
            query_id="",
            query=query,
            sections=sections,
            key_points=key_points,
            important_findings=important_findings,
            actionable_insights=actionable_insights,
            references=sources,
            total_sources=len([c for c in contents if c.success]),
            processing_time=processing_time
        )

    def _prepare_content(self, contents: list[ExtractedContent]) -> str:
        """Prepare and truncate content for LLM."""
        valid_contents = [c for c in contents if c.success and c.content]

        if not valid_contents:
            return "No valid content extracted."

        # Combine with source attribution
        parts = []
        for i, content in enumerate(valid_contents[:self.summarization_settings.max_chunks]):
            source_ref = f"[Source {i+1}: {content.title}]"
            parts.append(f"{source_ref}\n{content.content[:self.summarization_settings.chunk_size]}")

        return "\n\n---\n\n".join(parts)

    async def _generate_sections(
        self,
        query: str,
        content: str,
        sources: list[SearchResult]
    ) -> list[SummarySection]:
        """Generate structured summary sections."""
        sections = []

        for section_name in self.summarization_settings.summary_sections:
            prompt = self._get_section_prompt(section_name, query, content)
            try:
                response = await self.client.chat.completions.create(
                    model=self.llm_settings.model,
                    messages=[
                        {"role": "system", "content": "You are a research analyst. Provide concise, well-structured responses."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.llm_settings.temperature,
                    max_tokens=1000
                )
                section_content = response.choices[0].message.content or ""
                source_refs = [str(s.url) for s in sources[:5]]

                sections.append(SummarySection(
                    title=section_name.replace("_", " ").title(),
                    content=section_content.strip(),
                    sources=source_refs
                ))
            except Exception as e:
                logger.error(f"Section generation failed for {section_name}: {e}")
                sections.append(SummarySection(
                    title=section_name.replace("_", " ").title(),
                    content=f"Error generating section: {e}",
                    sources=[]
                ))

        return sections

    async def _extract_key_points(self, query: str, content: str) -> list[str]:
        """Extract key points as bullet list."""
        prompt = f"""Based on the following research content about "{query}", extract 5-7 key points as a concise bullet list.
        Each point should be one sentence. Focus on the most important information.

        Content:
        {content}

        Return only the bullet points, one per line, starting with "• "."""
        try:
            response = await self.client.chat.completions.create(
                model=self.llm_settings.model,
                messages=[
                    {"role": "system", "content": "Extract key points concisely."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=500
            )
            text = response.choices[0].message.content or ""
            return [line.strip("• ").strip() for line in text.split("\n") if line.strip().startswith("•")]
        except Exception as e:
            logger.error(f"Key points extraction failed: {e}")
            return []

    async def _extract_findings(self, query: str, content: str) -> list[str]:
        """Extract important findings."""
        prompt = f"""Based on the following research content about "{query}", identify 3-5 important findings or discoveries.
        Each finding should be a complete sentence describing a significant result, trend, or conclusion.

        Content:
        {content}

        Return only the findings, one per line, starting with "• "."""
        try:
            response = await self.client.chat.completions.create(
                model=self.llm_settings.model,
                messages=[
                    {"role": "system", "content": "Extract important findings."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=500
            )
            text = response.choices[0].message.content or ""
            return [line.strip("• ").strip() for line in text.split("\n") if line.strip().startswith("•")]
        except Exception as e:
            logger.error(f"Findings extraction failed: {e}")
            return []

    async def _extract_insights(self, query: str, content: str) -> list[str]:
        """Extract actionable insights."""
        prompt = f"""Based on the following research content about "{query}", provide 3-5 actionable insights or recommendations.
        Each insight should be practical and actionable, starting with a verb (e.g., "Consider implementing...", "Monitor...", "Investigate...").

        Content:
        {content}

        Return only the insights, one per line, starting with "• "."""
        try:
            response = await self.client.chat.completions.create(
                model=self.llm_settings.model,
                messages=[
                    {"role": "system", "content": "Provide actionable insights."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            text = response.choices[0].message.content or ""
            return [line.strip("• ").strip() for line in text.split("\n") if line.strip().startswith("•")]
        except Exception as e:
            logger.error(f"Insights extraction failed: {e}")
            return []

    def _get_section_prompt(self, section: str, query: str, content: str) -> str:
        """Get prompt for a specific section."""
        prompts = {
            "key_points": f"Provide a concise overview of the key points regarding '{query}' based on the research content.",
            "important_findings": f"Detail the important findings and discoveries from the research on '{query}'.",
            "actionable_insights": f"Provide actionable insights and recommendations based on the research on '{query}'.",
            "references": f"List the key references and sources used in the research on '{query}'."
        }
        base_prompt = prompts.get(section, f"Summarize the {section} for '{query}'.")
        return f"{base_prompt}\n\nContent:\n{content}\n\nProvide a well-structured response with clear headings."

    def _mock_summary(
        self,
        query: str,
        contents: list[ExtractedContent],
        sources: list[SearchResult],
        start_time: float
    ) -> ResearchSummary:
        """Mock summary for testing without API key."""
        processing_time = time.time() - start_time
        valid_contents = [c for c in contents if c.success]

        return ResearchSummary(
            query_id="",
            query=query,
            sections=[
                SummarySection(
                    title="Key Points",
                    content=f"Research summary for: {query}. Found {len(valid_contents)} relevant sources.",
                    sources=[str(s.url) for s in sources[:3]]
                ),
                SummarySection(
                    title="Important Findings",
                    content="Key findings from the research sources.",
                    sources=[str(s.url) for s in sources[:3]]
                ),
                SummarySection(
                    title="Actionable Insights",
                    content="Recommended actions based on the research.",
                    sources=[str(s.url) for s in sources[:3]]
                ),
            ],
            key_points=[
                f"Found {len(valid_contents)} relevant sources for '{query}'",
                "Multiple perspectives identified across sources",
                "Key trends and patterns extracted"
            ],
            important_findings=[
                "Significant information gathered from multiple sources",
                "Consistent themes identified across independent sources"
            ],
            actionable_insights=[
                "Review the detailed sources for specific data points",
                "Consider follow-up research on identified subtopics",
                "Validate findings with primary sources where possible"
            ],
            references=sources,
            total_sources=len(valid_contents),
            processing_time=processing_time
        )


class AnthropicSummarizer(BaseSummarizer):
    """Anthropic Claude-based summarization."""

    def __init__(self):
        self.settings = get_settings()
        self.llm_settings = self.settings.llm

        try:
            import anthropic
            api_key = self._get_api_key()
            self.client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else None
        except ImportError:
            logger.warning("Anthropic not installed")
            self.client = None

    def _get_api_key(self) -> Optional[str]:
        import os
        return os.getenv("ANTHROPIC_API_KEY")

    async def summarize(
        self,
        query: str,
        contents: list[ExtractedContent],
        sources: list[SearchResult]
    ) -> ResearchSummary:
        """Generate summary using Anthropic Claude."""
        start_time = time.time()

        if not self.client:
            # Fall back to OpenAI summarizer logic or mock
            openai_summarizer = OpenAISummarizer()
            return await openai_summarizer.summarize(query, contents, sources)

        # Similar implementation to OpenAI but using Anthropic API
        combined_content = self._prepare_content(contents)

        prompt = f"""You are a research analyst. Based on the following content about "{query}", provide a structured summary with:
1. Key Points (5-7 bullet points)
2. Important Findings (3-5 findings)
3. Actionable Insights (3-5 recommendations)
4. References

Content:
{combined_content}

Format as JSON with keys: key_points, important_findings, actionable_insights, references."""

        try:
            response = await self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=4000,
                temperature=self.llm_settings.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            # Parse JSON response
            result_text = response.content[0].text
            # ... parse and create ResearchSummary
        except Exception as e:
            logger.error(f"Anthropic summarization failed: {e}")

        return ResearchSummary(
            query_id="",
            query=query,
            sections=[],
            key_points=[],
            important_findings=[],
            actionable_insights=[],
            references=sources,
            total_sources=len([c for c in contents if c.success]),
            processing_time=time.time() - start_time
        )

    def _prepare_content(self, contents: list[ExtractedContent]) -> str:
        valid_contents = [c for c in contents if c.success and c.content]
        parts = []
        for i, content in enumerate(valid_contents[:10]):
            parts.append(f"[Source {i+1}: {content.title}]\n{content.content[:3000]}")
        return "\n\n---\n\n".join(parts)


class GeminiSummarizer(BaseSummarizer):
    """Google Gemini-based summarization."""

    def __init__(self):
        self.settings = get_settings()
        self.llm_settings = self.settings.llm

        try:
            import google.generativeai as genai
            api_key = self._get_api_key()
            if api_key:
                genai.configure(api_key=api_key)
                self.client = genai.GenerativeModel(self.llm_settings.model or "gemini-1.5-pro")
            else:
                self.client = None
        except ImportError:
            logger.warning("google-generativeai not installed")
            self.client = None

    def _get_api_key(self) -> Optional[str]:
        import os
        return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    async def summarize(
        self,
        query: str,
        contents: list[ExtractedContent],
        sources: list[SearchResult]
    ) -> ResearchSummary:
        """Generate summary using Gemini."""
        start_time = time.time()

        if not self.client:
            logger.warning("Gemini not configured, falling back to mock")
            return self._mock_summary(query, contents, sources, start_time)

        combined_content = self._prepare_content(contents)

        prompt = f"""You are a research analyst. Based on the following content about "{query}", provide a structured summary with:
1. Key Points (5-7 bullet points)
2. Important Findings (3-5 findings)
3. Actionable Insights (3-5 recommendations)
4. References

Content:
{combined_content}

Format as JSON with keys: key_points, important_findings, actionable_insights, references."""

        try:
            import json
            response = await self.client.generate_content_async(prompt)
            result_text = response.text

            # Parse JSON response
            result = json.loads(result_text)

            sections = [
                SummarySection(
                    title="Key Points",
                    content="\n".join(f"• {p}" for p in result.get("key_points", [])),
                    sources=[str(s.url) for s in sources[:5]]
                ),
                SummarySection(
                    title="Important Findings",
                    content="\n".join(f"• {f}" for f in result.get("important_findings", [])),
                    sources=[str(s.url) for s in sources[:5]]
                ),
                SummarySection(
                    title="Actionable Insights",
                    content="\n".join(f"• {i}" for i in result.get("actionable_insights", [])),
                    sources=[str(s.url) for s in sources[:5]]
                ),
            ]

            return ResearchSummary(
                query_id="",
                query=query,
                sections=sections,
                key_points=result.get("key_points", []),
                important_findings=result.get("important_findings", []),
                actionable_insights=result.get("actionable_insights", []),
                references=sources,
                total_sources=len([c for c in contents if c.success]),
                processing_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Gemini summarization failed: {e}")
            return self._mock_summary(query, contents, sources, start_time)

    def _prepare_content(self, contents: list[ExtractedContent]) -> str:
        valid_contents = [c for c in contents if c.success and c.content]
        parts = []
        for i, content in enumerate(valid_contents[:10]):
            parts.append(f"[Source {i+1}: {content.title}]\n{content.content[:3000]}")
        return "\n\n---\n\n".join(parts)

    def _mock_summary(
        self,
        query: str,
        contents: list[ExtractedContent],
        sources: list[SearchResult],
        start_time: float
    ) -> ResearchSummary:
        """Mock summary for testing without API key."""
        processing_time = time.time() - start_time
        valid_contents = [c for c in contents if c.success]

        return ResearchSummary(
            query_id="",
            query=query,
            sections=[
                SummarySection(
                    title="Key Points",
                    content=f"Research summary for: {query}. Found {len(valid_contents)} relevant sources.",
                    sources=[str(s.url) for s in sources[:3]]
                ),
                SummarySection(
                    title="Important Findings",
                    content="Key findings from the research sources.",
                    sources=[str(s.url) for s in sources[:3]]
                ),
                SummarySection(
                    title="Actionable Insights",
                    content="Recommended actions based on the research.",
                    sources=[str(s.url) for s in sources[:3]]
                ),
            ],
            key_points=[
                f"Found {len(valid_contents)} relevant sources for '{query}'",
                "Multiple perspectives identified across sources",
                "Key trends and patterns extracted"
            ],
            important_findings=[
                "Significant information gathered from multiple sources",
                "Consistent themes identified across independent sources"
            ],
            actionable_insights=[
                "Review the detailed sources for specific data points",
                "Consider follow-up research on identified subtopics",
                "Validate findings with primary sources where possible"
            ],
            references=sources,
            total_sources=len(valid_contents),
            processing_time=processing_time
        )


class SummarizerFactory:
    """Factory for creating summarizers."""

    @staticmethod
    def create() -> BaseSummarizer:
        """Create summarizer based on configuration."""
        provider = get_settings().llm.provider.lower()

        if provider == "openai":
            return OpenAISummarizer()
        elif provider == "anthropic":
            return AnthropicSummarizer()
        elif provider == "gemini":
            return GeminiSummarizer()
        else:
            logger.warning(f"Unknown LLM provider: {provider}, defaulting to OpenAI")
            return OpenAISummarizer()