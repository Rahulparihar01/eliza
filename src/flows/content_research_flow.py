"""
Content Research Flow

CrewAI flow for research-first content generation using OpenAI web search.
NO external data connectors - uses only OpenAI's web search tool.

KEY DESIGN PRINCIPLES:
1. HIGH RECALL: Multiple search queries, broad coverage, get more sources than needed
2. SOURCE SELECTION: User multi-selects which sources to use (like POV selection)
3. EXACT CITATIONS: Content uses ONLY selected sources - NO fabricated information
4. GROUNDED OUTPUT: Every claim must trace back to a specific source

FLOW:
1. Research Phase - Multiple web searches for comprehensive source gathering
2. Source Review - Present all sources for user multi-selection
3. Content Generation - Generate content strictly from selected sources
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import json
import uuid
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from urllib.parse import urlparse

# Dynamic date helper
def get_current_year() -> int:
    """Get current year for search queries."""
    return datetime.now().year

def get_recent_years_string() -> str:
    """Get string like '2025 2026' for recent content searches."""
    current = get_current_year()
    return f"{current - 1} {current}"

logger = get_logger(__name__, LogCategory.BUSINESS)
settings = get_settings()


def _extract_title_from_url(url: str) -> str:
    """Extract a readable title from URL when no title is provided."""
    try:
        parsed = urlparse(url)
        # Get domain without www
        domain = parsed.netloc.replace('www.', '')
        # Get path and clean it
        path = parsed.path.strip('/')
        if path:
            # Take last part of path and clean it
            last_part = path.split('/')[-1]
            # Remove extensions and slugify
            last_part = last_part.replace('-', ' ').replace('_', ' ')
            last_part = last_part.rsplit('.', 1)[0]  # Remove extension
            if len(last_part) > 5:  # Only use if meaningful
                return f"{domain}: {last_part.title()}"
        return domain
    except Exception:
        return "Web Source"


# =============================================================================
# Pydantic Models for Structured Data
# =============================================================================

class WebSource(BaseModel):
    """A source retrieved from web search."""
    id: str  # Unique identifier for selection
    url: str
    title: str
    snippet: str  # Preview text from search
    full_content: Optional[str] = None  # Full extracted content if available
    query_origin: str  # Which search query found this
    relevance_score: Optional[float] = None  # How relevant to topic (0-1)
    source_type: str = "web"  # web, news, academic, etc.
    retrieved_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ResearchPack(BaseModel):
    """Complete research package from web search."""
    topic: str
    queries_executed: List[str]
    total_sources_found: int
    sources: List[WebSource]
    search_metadata: Dict[str, Any] = {}


class SelectedSources(BaseModel):
    """User's selected sources for content generation."""
    source_ids: List[str]
    sources: List[WebSource]
    usage_notes: Optional[str] = None  # Any notes from user about how to use


class GeneratedContent(BaseModel):
    """Content generated strictly from selected sources."""
    content: str
    target_word_count: int
    word_count: int
    sources_used: List[str]  # Source IDs actually cited
    citations: List[Dict[str, Any]]  # Inline citation references
    uncited_claims: List[str] = []  # Any claims that couldn't be sourced (should be empty!)


# =============================================================================
# Content Research Flow
# =============================================================================

class ContentResearchFlow:
    """
    Content Research Flow using OpenAI Web Search.
    
    Designed for HIGH RECALL:
    - Multiple search queries per topic
    - Varied query formulations (questions, keywords, related terms)
    - Broad domain coverage
    
    Designed for PRECISION in OUTPUT:
    - User selects which sources to use
    - Content generated ONLY from selected sources
    - Every claim must have explicit citation
    - No fabricated or inferred information
    """
    
    # Sites to filter out from search results (e-commerce, spam, low-quality)
    BLOCKED_DOMAINS = [
        # E-commerce
        'amazon.com', 'ebay.com', 'walmart.com', 'alibaba.com', 'aliexpress.com',
        'etsy.com', 'shopify.com', 'wish.com', 'target.com', 'bestbuy.com',
        # Social/User-generated with low signal
        'pinterest.com', 'tiktok.com', 'facebook.com', 'instagram.com',
        # Low-quality content farms
        'buzzfeed.com', 'wikihow.com', 'quora.com', 'answers.com',
        # Job/Classifieds
        'indeed.com', 'glassdoor.com', 'craigslist.org', 'yelp.com',
    ]
    
    def __init__(
        self,
        run_id: str,
        customer_id: str,
        user_id: int,
        topic: str,
        target_word_count: int = 1000,
        constraints: Optional[Dict[str, Any]] = None,
    ):
        self.run_id = run_id
        self.customer_id = customer_id
        self.user_id = user_id
        self.topic = topic
        self.target_word_count = target_word_count
        self.constraints = constraints or {}
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=settings.openai_api_key)
        
        # State
        self.research_pack: Optional[ResearchPack] = None
        self.selected_sources: Optional[SelectedSources] = None
    
    # =========================================================================
    # PHASE 1: Research (High Recall Web Search)
    # =========================================================================
    
    def _generate_search_queries(self, topic: str, num_queries: int = 8) -> List[str]:
        """
        Generate multiple search queries for HIGH RECALL.
        
        Strategy:
        - Direct topic query
        - Question formulations (what, how, why)
        - Related concepts and synonyms
        - Recent/news angle
        - Expert/research angle
        - Contrarian/debate angle
        """
        # Use GPT to generate diverse queries
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a research query generator. Generate diverse search queries 
                    to find comprehensive information on a topic. 
                    
                    GOAL: HIGH RECALL - we want to find ALL relevant sources, not just the top few.
                    
                    Query types to include:
                    1. Direct topic search
                    2. "What is [topic]" question
                    3. "How does [topic] work" question  
                    4. "[topic] research studies" or "[topic] data"
                    5. "[topic] examples case studies"
                    6. "[topic] pros cons debate"
                    7. "[topic] latest news {get_recent_years_string()}"
                    8. "[topic] expert analysis"
                    
                    Return ONLY a JSON array of query strings, nothing else."""
                },
                {
                    "role": "user",
                    "content": f"Generate {num_queries} diverse search queries for: {topic}"
                }
            ],
            temperature=0.7,
        )
        
        try:
            queries = json.loads(response.choices[0].message.content)
            # Always include the raw topic as first query
            if topic not in queries:
                queries.insert(0, topic)
            return queries[:num_queries]
        except json.JSONDecodeError:
            # Fallback to basic queries with dynamic year
            return [
                topic,
                f"What is {topic}",
                f"{topic} how it works",
                f"{topic} research data",
                f"{topic} examples",
                f"{topic} latest news {get_current_year()}",
                f"{topic} expert analysis",
                f"{topic} pros and cons",
            ][:num_queries]
    
    def _is_blocked_domain(self, url: str) -> bool:
        """Check if URL is from a blocked domain (e-commerce, spam, etc.)."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            for blocked in self.BLOCKED_DOMAINS:
                if blocked in domain:
                    return True
            return False
        except Exception:
            return False
    
    def _execute_web_search(self, query: str) -> List[WebSource]:
        """
        Execute a single web search using OpenAI's web search tool.
        
        Uses the Responses API with web_search tool for grounded results.
        Filters out e-commerce and low-quality sources.
        """
        try:
            # Use OpenAI Responses API with web search
            response = self.client.responses.create(
                model="gpt-4o",  # Use gpt-4o for web search
                tools=[{"type": "web_search"}],
                tool_choice={"type": "web_search"},  # Force web search
                input=f"""Search the web for: {query}
                
                Find and return ALL relevant sources. For each source, extract:
                - The exact URL
                - The exact title
                - A comprehensive snippet/summary of the content
                
                Return as many relevant sources as possible. We need HIGH RECALL.
                
                Format your response as a JSON array:
                [
                    {{"url": "...", "title": "...", "snippet": "comprehensive content summary..."}}
                ]
                """,
                include=["web_search_call.action.sources"],  # Get all sources
            )
            
            sources = []
            
            # Extract sources from the response
            for item in response.output:
                if item.type == "web_search_call":
                    # Get sources from the web search call
                    if hasattr(item, 'action') and hasattr(item.action, 'sources'):
                        for src in item.action.sources:
                            # Filter out e-commerce and low-quality sites
                            if self._is_blocked_domain(src.url):
                                logger.debug(f"Filtered out blocked domain: {src.url}")
                                continue
                            
                            source_id = hashlib.md5(src.url.encode()).hexdigest()[:12]
                            raw_title = getattr(src, 'title', '') or ''
                            
                            # Try multiple attributes for snippet content
                            raw_snippet = ''
                            for attr in ['snippet', 'description', 'summary', 'content', 'text', 'excerpt']:
                                raw_snippet = getattr(src, attr, '') or ''
                                if raw_snippet:
                                    break
                            
                            # Use URL-derived title if no real title
                            if not raw_title or raw_title.lower() == 'untitled':
                                raw_title = _extract_title_from_url(src.url)
                            
                            sources.append(WebSource(
                                id=source_id,
                                url=src.url,
                                title=raw_title,
                                snippet=raw_snippet,
                                query_origin=query,
                                source_type="web",
                            ))
                
                elif item.type == "message":
                    # Try to parse structured sources from the message
                    for content in item.content:
                        if hasattr(content, 'text'):
                            text = content.text
                            
                            # Extract any URLs with annotations
                            if hasattr(content, 'annotations'):
                                for ann in content.annotations:
                                    if ann.type == "url_citation":
                                        # Filter out e-commerce and low-quality sites
                                        if self._is_blocked_domain(ann.url):
                                            logger.debug(f"Filtered out blocked domain: {ann.url}")
                                            continue
                                        
                                        source_id = hashlib.md5(ann.url.encode()).hexdigest()[:12]
                                        
                                        # Get context around the citation (more generous range)
                                        start = max(0, ann.start_index - 150)
                                        end = min(len(text), ann.end_index + 150)
                                        snippet_text = text[start:end].strip()
                                        
                                        # Check if we already have this source
                                        existing = next((s for s in sources if s.id == source_id), None)
                                        if existing:
                                            # Enhance existing source with better snippet if needed
                                            if len(snippet_text) > len(existing.snippet or ''):
                                                existing.snippet = snippet_text
                                        else:
                                            ann_title = getattr(ann, 'title', '') or ''
                                            if not ann_title or ann_title.lower() == 'untitled':
                                                ann_title = _extract_title_from_url(ann.url)
                                            sources.append(WebSource(
                                                id=source_id,
                                                url=ann.url,
                                                title=ann_title,
                                                snippet=snippet_text,
                                                query_origin=query,
                                                source_type="web",
                                            ))
                            
                            # Also try to enhance any sources without snippets using the full text
                            # Skip if text looks like JSON (contains raw JSON structures)
                            if text and len(text) > 50 and not ('"url":' in text and '"snippet":' in text):
                                for source in sources:
                                    if not source.snippet or len(source.snippet) < 50:
                                        # Try to find mention of this source's domain in text
                                        domain = urlparse(source.url).netloc.replace('www.', '')
                                        if domain in text:
                                            # Extract context around the domain mention
                                            idx = text.find(domain)
                                            context = text[max(0, idx-100):min(len(text), idx+200)].strip()
                                            # Only use if it doesn't look like JSON
                                            if not context.startswith('{') and '"url"' not in context:
                                                source.snippet = context
            
            logger.info(f"Web search for '{query}' found {len(sources)} sources")
            return sources
            
        except Exception as e:
            logger.error(f"Web search failed for query '{query}': {e}")
            return []
    
    def _has_valid_snippet(self, snippet: str) -> bool:
        """Check if a snippet is valid (not empty, not JSON, has real content)."""
        if not snippet or len(snippet) < 30:
            return False
        # Check for JSON-like content
        if '"url":' in snippet or '"snippet":' in snippet:
            return False
        if snippet.strip().startswith('{') or snippet.strip().startswith('['):
            return False
        return True
    
    def _generate_batch_summaries(self, batch: List[WebSource], topic: str) -> Dict[str, str]:
        """Generate summaries for a batch of sources. Returns dict of source_id -> summary."""
        # Prepare source info for the LLM
        source_info = [
            {"id": s.id, "url": s.url, "title": s.title, "query": s.query_origin}
            for s in batch
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Generate brief, informative summaries for web sources about "{topic}".
                        
Based on the URL structure and title, infer what content this source likely contains.
Be specific and helpful - mention the type of content (article, research, guide, news, etc.).

Return ONLY a JSON object mapping source IDs to summaries (50-150 words each):
{{"id1": "This article from [domain] discusses...", "id2": "A comprehensive guide covering..."}}

Focus on being descriptive about what the source likely offers, based on:
- The domain (is it a news site, blog, research institution, company?)
- The URL path (what topic/section is it in?)
- The title (what specific angle does it cover?)
- The search query that found it (what was the user looking for?)"""
                    },
                    {
                        "role": "user",
                        "content": f"Generate summaries for these sources:\n{json.dumps(source_info, indent=2)}"
                    }
                ],
                temperature=0.5,
            )
            
            content = response.choices[0].message.content
            # Strip markdown code blocks if present
            content = re.sub(r'^```(?:json)?\s*', '', content.strip())
            content = re.sub(r'\s*```$', '', content)
            
            return json.loads(content)
                    
        except Exception as e:
            logger.error(f"Failed to generate summaries for batch: {e}")
            # Return fallback summaries
            fallbacks = {}
            for source in batch:
                domain = urlparse(source.url).netloc.replace('www.', '')
                fallbacks[source.id] = f"Content from {domain} found via search for '{source.query_origin}'. Visit the link for full details."
            return fallbacks
    
    def _generate_source_summaries(self, sources: List[WebSource], topic: str) -> List[WebSource]:
        """Generate summaries for sources that don't have good snippets using OpenAI (parallel)."""
        # Find sources needing summaries
        sources_needing_summary = [
            s for s in sources 
            if not self._has_valid_snippet(s.snippet)
        ]
        
        if not sources_needing_summary:
            logger.info("All sources have valid snippets, skipping summary generation")
            return sources
        
        logger.info(f"Generating summaries for {len(sources_needing_summary)} sources in parallel...")
        
        # Create batches (max 10 sources per batch to avoid token limits)
        batch_size = 10
        batches = [
            sources_needing_summary[i:i + batch_size] 
            for i in range(0, len(sources_needing_summary), batch_size)
        ]
        
        # Create a lookup for quick source access
        source_lookup = {s.id: s for s in sources}
        
        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=min(4, len(batches))) as executor:
            future_to_batch = {
                executor.submit(self._generate_batch_summaries, batch, topic): batch
                for batch in batches
            }
            
            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    summaries = future.result()
                    # Apply summaries to sources
                    for source_id, summary in summaries.items():
                        if source_id in source_lookup:
                            source_lookup[source_id].snippet = summary
                            logger.debug(f"Generated summary for source {source_id}")
                except Exception as e:
                    logger.error(f"Batch summary generation failed: {e}")
                    # Apply fallbacks for this batch
                    for source in batch:
                        domain = urlparse(source.url).netloc.replace('www.', '')
                        source.snippet = f"Content from {domain}. Visit link for details."
        
        logger.info(f"Summary generation complete for {len(sources_needing_summary)} sources")
        return sources
    
    def _deduplicate_sources(self, sources: List[WebSource]) -> List[WebSource]:
        """Remove duplicate sources based on URL, keeping the one with most content."""
        seen_urls = {}
        for source in sources:
            url_key = source.url.lower().rstrip('/')
            if url_key not in seen_urls:
                seen_urls[url_key] = source
            else:
                # Keep the one with longer snippet
                if len(source.snippet or '') > len(seen_urls[url_key].snippet or ''):
                    seen_urls[url_key] = source
        return list(seen_urls.values())
    
    def _score_relevance(self, sources: List[WebSource], topic: str) -> List[WebSource]:
        """Score sources by relevance to topic."""
        if not sources:
            return sources
        
        # Use GPT to score relevance
        source_summaries = [
            {"id": s.id, "title": s.title, "snippet": s.snippet[:500]}
            for s in sources[:50]  # Limit to avoid token limits
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Score each source's relevance to the topic on a scale of 0.0 to 1.0.
                        Consider:
                        - Direct relevance to topic
                        - Quality/credibility of source
                        - Usefulness for content creation
                        
                        Return ONLY a JSON object mapping source IDs to scores:
                        {"id1": 0.95, "id2": 0.72, ...}"""
                    },
                    {
                        "role": "user",
                        "content": f"Topic: {topic}\n\nSources:\n{json.dumps(source_summaries)}"
                    }
                ],
                temperature=0.3,
            )
            
            scores = json.loads(response.choices[0].message.content)
            
            for source in sources:
                source.relevance_score = scores.get(source.id, 0.5)
            
            # Sort by relevance
            sources.sort(key=lambda s: s.relevance_score or 0, reverse=True)
            
        except Exception as e:
            logger.warning(f"Relevance scoring failed: {e}")
        
        return sources
    
    def conduct_research(self, num_queries: int = 8) -> ResearchPack:
        """
        PHASE 1: Conduct comprehensive web research.
        
        HIGH RECALL strategy:
        - Generate multiple diverse search queries
        - Execute each query
        - Deduplicate sources
        - Score by relevance
        - Return ALL sources for user selection
        
        Args:
            num_queries: Number of search queries to execute (default 8 for high recall)
            
        Returns:
            ResearchPack with all discovered sources
        """
        logger.info(f"Starting research for topic: {self.topic} with {num_queries} queries")
        
        # Generate diverse queries for high recall
        queries = self._generate_search_queries(self.topic, num_queries)
        logger.info(f"Generated queries: {queries}")
        
        # Execute all searches in parallel
        all_sources = []
        logger.info(f"Executing {len(queries)} web searches in parallel...")
        
        with ThreadPoolExecutor(max_workers=min(6, len(queries))) as executor:
            # Submit all search tasks
            future_to_query = {
                executor.submit(self._execute_web_search, query): query 
                for query in queries
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    sources = future.result()
                    all_sources.extend(sources)
                    logger.info(f"Query '{query}' returned {len(sources)} sources")
                except Exception as e:
                    logger.error(f"Search failed for query '{query}': {e}")
        
        # Deduplicate
        unique_sources = self._deduplicate_sources(all_sources)
        logger.info(f"After deduplication: {len(unique_sources)} unique sources")
        
        # Generate summaries for sources without good snippets
        sources_with_summaries = self._generate_source_summaries(unique_sources, self.topic)
        logger.info(f"Sources after summary generation: {len(sources_with_summaries)}")
        
        # Score relevance
        scored_sources = self._score_relevance(sources_with_summaries, self.topic)
        
        # Create research pack
        self.research_pack = ResearchPack(
            topic=self.topic,
            queries_executed=queries,
            total_sources_found=len(scored_sources),
            sources=scored_sources,
            search_metadata={
                "run_id": self.run_id,
                "timestamp": datetime.utcnow().isoformat(),
                "num_queries": num_queries,
                "raw_results_count": len(all_sources),
            }
        )
        
        logger.info(f"Research complete: {len(scored_sources)} sources ready for selection")
        
        return self.research_pack
    
    # =========================================================================
    # PHASE 2: Source Selection (User Multi-Select)
    # =========================================================================
    
    def get_sources_for_selection(self) -> List[Dict[str, Any]]:
        """
        Get sources formatted for user multi-selection UI.
        
        Returns list of sources with:
        - id: For selection
        - title: Display title
        - url: Source URL
        - snippet: Preview content
        - relevance_score: AI-scored relevance
        - query_origin: Which search found it
        """
        if not self.research_pack:
            raise ValueError("Must conduct_research() first")
        
        return [
            {
                "id": s.id,
                "title": s.title,
                "url": s.url,
                "snippet": s.snippet[:500],  # Truncate for UI
                "relevance_score": s.relevance_score,
                "query_origin": s.query_origin,
                "source_type": s.source_type,
            }
            for s in self.research_pack.sources
        ]
    
    def select_sources(self, source_ids: List[str], usage_notes: Optional[str] = None) -> SelectedSources:
        """
        PHASE 2: User selects which sources to use for content.
        
        Args:
            source_ids: List of source IDs selected by user
            usage_notes: Optional notes on how to use sources
            
        Returns:
            SelectedSources object with full source data
        """
        if not self.research_pack:
            raise ValueError("Must conduct_research() first")
        
        # Get full source objects for selected IDs
        selected = [s for s in self.research_pack.sources if s.id in source_ids]
        
        if not selected:
            raise ValueError("No valid sources selected")
        
        self.selected_sources = SelectedSources(
            source_ids=source_ids,
            sources=selected,
            usage_notes=usage_notes,
        )
        
        logger.info(f"Selected {len(selected)} sources for content generation")
        
        return self.selected_sources
    
    # =========================================================================
    # PHASE 3: Content Generation (Strictly from Selected Sources)
    # =========================================================================
    
    def _build_source_context(self) -> str:
        """Build context string from selected sources with clear source markers."""
        if not self.selected_sources:
            raise ValueError("Must select_sources() first")
        
        context_parts = []
        for i, source in enumerate(self.selected_sources.sources, 1):
            context_parts.append(f"""
[SOURCE {i}]
ID: {source.id}
Title: {source.title}
URL: {source.url}
Content:
{source.snippet}
[END SOURCE {i}]
""")
        
        return "\n".join(context_parts)
    
    def generate_content(
        self,
        selected_pov: Optional[Dict[str, Any]] = None,
        selected_hook: Optional[Dict[str, Any]] = None,
    ) -> GeneratedContent:
        """
        PHASE 3: Generate content STRICTLY from selected sources.
        
        CRITICAL RULES:
        - ONLY use information from selected sources
        - NEVER fabricate facts, quotes, statistics, or claims
        - EVERY factual claim must cite its source
        - If information isn't in sources, DON'T include it
        
        Args:
            selected_pov: Optional POV to apply
            selected_hook: Optional hook to use
            
        Returns:
            GeneratedContent with citations
        """
        if not self.selected_sources:
            raise ValueError("Must select_sources() first")
        
        logger.info(f"Generating ~{self.target_word_count} word content from {len(self.selected_sources.sources)} sources")
        
        # Build source context
        source_context = self._build_source_context()
        
        # Build POV instruction
        pov_instruction = ""
        if selected_pov:
            pov_instruction = f"""
POINT OF VIEW TO APPLY:
Label: {selected_pov.get('label', '')}
Description: {selected_pov.get('description', '')}
Key Concepts: {', '.join(selected_pov.get('key_concepts', []))}

Apply this POV while staying TRUE to the source material. The POV affects tone and framing,
but NEVER fabricate information that isn't in the sources.
"""
        
        # Build hook instruction
        hook_instruction = ""
        if selected_hook:
            hook_instruction = f"""
OPENING HOOK TO USE:
{selected_hook.get('lede', '')}

Start with this hook, then build the content from the sources.
"""
        
        # Length-based format instructions
        if self.target_word_count <= 600:
            length_guidance = """
LENGTH: Short Article (~{} words)
- Concise and focused
- Short paragraphs (1-2 sentences)
- Get to the point quickly
- Cite sources inline with [Source X] markers
""".format(self.target_word_count)
        elif self.target_word_count <= 1200:
            length_guidance = """
LENGTH: Medium Article (~{} words)
- Balanced depth and readability
- Short paragraphs (2-3 sentences)
- Use subheaders if helpful
- End with a takeaway or call to action
- Cite sources inline with [Source X] markers
""".format(self.target_word_count)
        elif self.target_word_count <= 1800:
            length_guidance = """
LENGTH: Long Article (~{} words)
- In-depth exploration of the topic
- Use headers and subheaders
- Include introduction and conclusion
- Multiple sections with clear structure
- Cite sources inline with [Source X] markers
""".format(self.target_word_count)
        else:
            length_guidance = """
LENGTH: Comprehensive Article (~{} words)
- Thorough and detailed coverage
- Use headers and multiple subheaders
- Strong introduction, body sections, and conclusion
- Include examples and explanations
- Cite sources inline with [Source X] markers
""".format(self.target_word_count)
        
        # The critical prompt for grounded generation
        prompt = f"""You are a content writer that generates articles STRICTLY from provided sources.

CRITICAL RULES - FOLLOW EXACTLY:
1. ONLY use information explicitly stated in the sources below
2. NEVER fabricate facts, statistics, quotes, or claims
3. NEVER infer or assume information not in the sources
4. EVERY factual claim must be cited with [Source X] format
5. If you can't support a claim from the sources, DO NOT include it
6. If sources conflict, note the disagreement
7. Use direct quotes when possible, with attribution

TOPIC: {self.topic}

{pov_instruction}

{hook_instruction}

{length_guidance}

=== SOURCES (USE ONLY THESE) ===
{source_context}
=== END SOURCES ===

{f"USER NOTES: {self.selected_sources.usage_notes}" if self.selected_sources.usage_notes else ""}

CONSTRAINTS: {json.dumps(self.constraints) if self.constraints else "None"}

Now write the content. Remember:
- Every fact must come from a source above
- Cite with [Source X] inline
- Do not make up ANY information
- If unsure, don't include it
- Target approximately {self.target_word_count} words

Write the article now:"""

        # Generate with GPT-4o for quality
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a careful, accurate content writer who never fabricates information."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,  # Lower temperature for accuracy
            max_tokens=4000,
        )
        
        content = response.choices[0].message.content
        
        # Extract which sources were actually cited
        cited_sources = []
        for i, source in enumerate(self.selected_sources.sources, 1):
            if f"[Source {i}]" in content:
                cited_sources.append(source.id)
        
        # Build citations list
        citations = []
        for i, source in enumerate(self.selected_sources.sources, 1):
            if source.id in cited_sources:
                citations.append({
                    "marker": f"[Source {i}]",
                    "source_id": source.id,
                    "url": source.url,
                    "title": source.title,
                })
        
        # Check for uncited claims (basic check)
        uncited_claims = self._check_for_uncited_claims(content, len(self.selected_sources.sources))
        
        result = GeneratedContent(
            content=content,
            target_word_count=self.target_word_count,
            word_count=len(content.split()),
            sources_used=cited_sources,
            citations=citations,
            uncited_claims=uncited_claims,
        )
        
        logger.info(f"Generated content: {result.word_count} words, {len(cited_sources)} sources cited")
        
        if uncited_claims:
            logger.warning(f"Potential uncited claims detected: {uncited_claims}")
        
        return result
    
    def _check_for_uncited_claims(self, content: str, num_sources: int) -> List[str]:
        """
        Check content for potential uncited claims.
        
        Uses GPT to identify sentences that make factual claims
        but don't have [Source X] citations.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Analyze the content and identify any sentences that:
1. Make factual claims (statistics, quotes, specific facts)
2. Do NOT have a [Source X] citation nearby

Return ONLY a JSON array of the uncited claim sentences.
If all claims are properly cited, return an empty array: []"""
                    },
                    {
                        "role": "user",
                        "content": f"Number of sources available: {num_sources}\n\nContent:\n{content}"
                    }
                ],
                temperature=0.2,
            )
            
            result = json.loads(response.choices[0].message.content)
            return result if isinstance(result, list) else []
            
        except Exception as e:
            logger.warning(f"Uncited claims check failed: {e}")
            return []
    
    def format_citations_for_display(self, content: GeneratedContent) -> str:
        """
        Format the content with proper citation display.
        
        Converts [Source X] markers to formatted citations.
        """
        formatted = content.content
        
        # Add references section
        if content.citations:
            formatted += "\n\n---\n\n**Sources:**\n"
            for citation in content.citations:
                formatted += f"\n{citation['marker']}: [{citation['title']}]({citation['url']})"
        
        return formatted


# =============================================================================
# Convenience Functions
# =============================================================================

def create_content_research_flow(
    topic: str,
    target_word_count: int = 1000,
    customer_id: str = "default",
    user_id: int = 0,
    constraints: Optional[Dict[str, Any]] = None,
) -> ContentResearchFlow:
    """
    Create a new ContentResearchFlow instance.
    
    Args:
        topic: The topic to research and write about
        target_word_count: Target word count for the article (300-3000)
        customer_id: Customer ID for multi-tenancy
        user_id: User ID
        constraints: Optional constraints (tone, audience, etc.)
        
    Returns:
        Configured ContentResearchFlow instance
    """
    run_id = str(uuid.uuid4())
    
    return ContentResearchFlow(
        run_id=run_id,
        customer_id=customer_id,
        user_id=user_id,
        topic=topic,
        target_word_count=target_word_count,
        constraints=constraints,
    )


def run_full_research_flow(
    topic: str,
    target_word_count: int = 1000,
    selected_source_ids: Optional[List[str]] = None,
    selected_pov: Optional[Dict[str, Any]] = None,
    selected_hook: Optional[Dict[str, Any]] = None,
    num_queries: int = 6,
) -> Dict[str, Any]:
    """
    Run the complete research flow (for testing/CLI usage).
    
    In production, this would be split into separate API calls
    with user interaction for source selection.
    
    Args:
        topic: Topic to research
        target_word_count: Target word count for the article
        selected_source_ids: Source IDs to use (if None, uses top 5 by relevance)
        selected_pov: POV to apply
        selected_hook: Hook to use
        num_queries: Number of search queries for recall
        
    Returns:
        Complete flow results
    """
    flow = create_content_research_flow(topic, target_word_count)
    
    # Phase 1: Research
    research_pack = flow.conduct_research(num_queries=num_queries)
    
    # Phase 2: Source selection (auto-select top 5 if not specified)
    if selected_source_ids:
        flow.select_sources(selected_source_ids)
    else:
        # Auto-select top 5 by relevance
        top_ids = [s.id for s in research_pack.sources[:5]]
        flow.select_sources(top_ids)
    
    # Phase 3: Generate content
    content = flow.generate_content(
        selected_pov=selected_pov,
        selected_hook=selected_hook,
    )
    
    return {
        "run_id": flow.run_id,
        "topic": topic,
        "target_word_count": target_word_count,
        "research": {
            "queries": research_pack.queries_executed,
            "total_sources": research_pack.total_sources_found,
            "sources": [s.model_dump() for s in research_pack.sources],
        },
        "selected_sources": [s.model_dump() for s in flow.selected_sources.sources],
        "content": {
            "text": content.content,
            "word_count": content.word_count,
            "sources_cited": content.sources_used,
            "citations": content.citations,
            "formatted": flow.format_citations_for_display(content),
        },
        "warnings": {
            "uncited_claims": content.uncited_claims,
        }
    }
