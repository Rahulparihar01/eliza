"""
Workspace-scoped Pydantic AI backend for RAG chat.

This module provides:
- WorkspacePromptTemplate persisted per workspace
- Structured chat input/output models
- WorkspacePydanticAgent wrapper (Pydantic AI + LiteLLM fallback)
- Workspace agent factory/cache with invalidation hooks
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.logging import get_logger
from src.models.prompt_template import (
    DomainPromptConfig,
    PromptStatus,
    PromptTemplate,
    PromptType,
)
from src.models.ragflow_domain import RAGFlowDomain
from src.services.langfuse_service import get_langfuse_service

from eliza_rag.chat import (
    ChatMessage, ChatResponse,
    DEFAULT_SYSTEM_PROMPT, DEFAULT_QUERY_REWRITE_PROMPT,
    DEFAULT_SYNTHESIS_PROMPT, DEFAULT_RETRIEVAL_PROMPT,
)
from eliza_rag.retrieval import RetrievalService, RetrievedChunk

logger = get_logger(__name__, component="services.workspace_rag_backend")


class WorkspacePromptTemplate(BaseModel):
    """Standard Pydantic prompt template for a workspace."""

    workspace_id: int
    workspace_name: str
    domain: str

    system_prompt: str
    query_rewrite_prompt: Optional[str] = None
    synthesis_prompt: Optional[str] = None
    retrieval_prompt: Optional[str] = None

    model: str = "gpt-4o-mini"
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=32000)

    top_k: int = Field(default=5, ge=1, le=50)
    similarity_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    use_query_rewrite: bool = True
    use_hybrid_search: bool = True

    citation_mode: bool = True
    max_context_chunks: int = Field(default=5, ge=1, le=20)

    gepa_variant_id: Optional[int] = None
    gepa_job_id: Optional[int] = None
    prompt_version: int = 1


class RAGChatInput(BaseModel):
    """Structured input for a RAG chat call."""

    question: str
    conversation_history: List[dict] = Field(default_factory=list)
    domain_id: str
    customer_id: str
    knowledge_base_ids: Optional[List[int]] = None


class RAGChatOutput(BaseModel):
    """Structured output from a RAG chat call."""

    answer: str
    citations: List[str] = Field(default_factory=list)
    chunks_used: int
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    confidence: Optional[float] = None


@dataclass
class _WorkspaceAgentDeps:
    retrieval_service: RetrievalService
    domain_id: str
    template: WorkspacePromptTemplate
    knowledge_base_ids: Optional[List[int]] = None


class WorkspacePydanticAgent:
    """Workspace-scoped RAG chat wrapper using Pydantic AI with LiteLLM fallback."""

    def __init__(
        self,
        retrieval_service: RetrievalService,
        template: WorkspacePromptTemplate,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.template = template
        self.settings = get_settings()
        self.langfuse_service = get_langfuse_service()
        self._agent = self._build_agent()

    @staticmethod
    def _resolve_pydantic_model(model_name: str) -> Any:
        """Best-effort model resolver across pydantic-ai versions."""
        try:
            from pydantic_ai.providers.litellm import LiteLLMProvider

            provider = LiteLLMProvider()
            try:
                from pydantic_ai.models.openai import OpenAIChatModel

                return OpenAIChatModel(model_name, provider=provider)
            except Exception:
                from pydantic_ai.models.openai import OpenAIModel

                return OpenAIModel(model_name, provider=provider)
        except Exception:
            pass

        try:
            from pydantic_ai.models.litellm import LiteLLMModel

            return LiteLLMModel(model_name)
        except Exception:
            return model_name

    def _build_agent(self):
        """Build Pydantic AI agent if available, otherwise return None."""
        try:
            from pydantic_ai import Agent
        except Exception as exc:
            logger.warning("pydantic_ai_unavailable_fallback", error=str(exc))
            return None

        model = self._resolve_pydantic_model(self.template.model)

        instructions = self._build_system_instructions()

        agent = None
        agent_build_attempts = [
            {
                "model": model,
                "output_type": RAGChatOutput,
                "deps_type": _WorkspaceAgentDeps,
                "instructions": instructions,
            },
            {
                "model": model,
                "result_type": RAGChatOutput,
                "deps_type": _WorkspaceAgentDeps,
                "instructions": instructions,
            },
            {
                "model": model,
                "result_type": RAGChatOutput,
                "deps_type": _WorkspaceAgentDeps,
                "system_prompt": instructions,
            },
        ]
        for kwargs in agent_build_attempts:
            try:
                agent = Agent(**kwargs)
                break
            except TypeError:
                continue
            except Exception as exc:
                logger.warning("workspace_pydantic_agent_build_failed", error=str(exc))
                return None
        if agent is None:
            logger.warning("workspace_pydantic_agent_build_failed_all_signatures")
            return None

        @agent.tool
        async def retrieve_context(
            ctx,
            query: str,
            top_k: int = 5,
        ) -> str:
            """Retrieve additional context for follow-up reasoning."""
            requested_k = max(1, min(top_k, ctx.deps.template.max_context_chunks))
            chunks = await ctx.deps.retrieval_service.hybrid_retrieve(
                domain_id=ctx.deps.domain_id,
                query=query,
                top_k=requested_k,
                knowledge_base_ids=ctx.deps.knowledge_base_ids,
            )
            return self._format_context(chunks, requested_k)

        return agent

    def _build_system_instructions(self) -> str:
        instructions = [self.template.system_prompt]

        if self.template.retrieval_prompt:
            instructions.append(f"Retrieval guidance:\n{self.template.retrieval_prompt}")
        if self.template.synthesis_prompt:
            instructions.append(f"Synthesis guidance:\n{self.template.synthesis_prompt}")
        if self.template.citation_mode:
            instructions.append(
                "Always cite retrieved chunks with [1], [2], ... that map to context indices."
            )

        instructions.append(
            "Return valid JSON matching RAGChatOutput with answer, citations, chunks_used, "
            "model, prompt_tokens, completion_tokens, and optional confidence."
        )
        return "\n\n".join(instructions)

    @staticmethod
    def _render_template(template: str, **variables: str) -> str:
        class _SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        try:
            return template.format_map(_SafeDict(**variables))
        except Exception:
            rendered = template
            for key, value in variables.items():
                rendered = rendered.replace("{" + key + "}", value)
            return rendered

    async def _rewrite_query(
        self,
        question: str,
        customer_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        if not self.template.use_query_rewrite or not self.template.query_rewrite_prompt:
            return question

        prompt = self._render_template(self.template.query_rewrite_prompt, question=question)
        started = time.time()
        try:
            from litellm import acompletion

            response = await acompletion(
                model=self.template.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=256,
                success_callback=[],
                failure_callback=[],
            )
            rewritten = (response.choices[0].message.content or "").strip()
            if not rewritten:
                return question
            rewritten_query = rewritten[:1024]
            self.langfuse_service.trace_generation(
                name="workspace-query-rewrite",
                model=self.template.model,
                input_data={"question": question, "prompt": prompt},
                output_data={"rewritten_query": rewritten_query},
                model_parameters={"temperature": 0, "max_tokens": 256},
                workspace_id=self.template.workspace_id,
                domain=self.template.domain,
                customer_id=customer_id,
                prompt_version=self.template.prompt_version,
                gepa_variant_id=self.template.gepa_variant_id,
                session_id=session_id,
                extra_metadata={"latency_ms": (time.time() - started) * 1000},
            )
            return rewritten_query
        except Exception as exc:
            logger.warning("workspace_query_rewrite_failed", error=str(exc))
            return question

    @staticmethod
    def _format_context(chunks: List[RetrievedChunk], max_chunks: int) -> str:
        parts: List[str] = []
        for i, chunk in enumerate(chunks[:max_chunks], start=1):
            doc_label = chunk.document_title or chunk.document_name
            header_parts = [f"[{i}] {doc_label}"]
            if chunk.knowledge_base_name:
                header_parts.append(f"KB: {chunk.knowledge_base_name}")
            if chunk.section_hierarchy:
                header_parts.append(f"Section: {' > '.join(chunk.section_hierarchy)}")
            elif chunk.section_title:
                header_parts.append(f"Section: {chunk.section_title}")
            if chunk.page_number:
                page_str = str(chunk.page_number)
                if chunk.page_range and len(chunk.page_range) == 2 and chunk.page_range[0] != chunk.page_range[1]:
                    page_str = f"{chunk.page_range[0]}-{chunk.page_range[1]}"
                header_parts.append(f"p.{page_str}")
            source = " | ".join(header_parts)
            parts.append(f"{source}\n{chunk.text}")
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _extract_citation_indices(answer: str) -> List[int]:
        return sorted({int(match) for match in re.findall(r"\[(\d+)\]", answer or "")})

    @staticmethod
    def _build_extractive_fallback_answer(chunks: List[RetrievedChunk]) -> str:
        """Build a deterministic fallback answer directly from retrieved chunks."""
        snippets: List[str] = []
        for idx, chunk in enumerate(chunks[:3], start=1):
            raw_text = chunk.text or ""
            normalized = re.sub(r"\s+", " ", raw_text).strip()
            if not normalized:
                continue

            if len(normalized) > 420:
                normalized = normalized[:420].rsplit(" ", 1)[0] + "..."
            snippets.append(f"[{idx}] {normalized}")

        if not snippets:
            return (
                "I found relevant documents, but couldn't synthesize a complete answer right now. "
                "Please try again in a moment."
            )

        return "I found relevant passages in your documents:\n\n" + "\n\n".join(snippets)

    @staticmethod
    def _coerce_usage(result: Any) -> tuple[int, int]:
        prompt_tokens = 0
        completion_tokens = 0
        try:
            usage = result.usage() if callable(getattr(result, "usage", None)) else None
            if usage is None:
                return prompt_tokens, completion_tokens
            prompt_tokens = int(
                getattr(usage, "request_tokens", None)
                or getattr(usage, "prompt_tokens", None)
                or getattr(usage, "input_tokens", None)
                or 0
            )
            completion_tokens = int(
                getattr(usage, "response_tokens", None)
                or getattr(usage, "completion_tokens", None)
                or getattr(usage, "output_tokens", None)
                or 0
            )
        except Exception:
            pass
        return prompt_tokens, completion_tokens

    async def _generate_with_litellm(
        self,
        chat_input: RAGChatInput,
        chunks: List[RetrievedChunk],
        context: str,
        session_id: Optional[str] = None,
    ) -> RAGChatOutput:
        from litellm import acompletion

        system_parts = [self._render_template(self.template.system_prompt, context=context)]
        if self.template.retrieval_prompt:
            system_parts.append(
                self._render_template(self.template.retrieval_prompt, context=context)
            )
        if self.template.synthesis_prompt:
            system_parts.append(
                self._render_template(self.template.synthesis_prompt, context=context)
            )
        if self.template.citation_mode:
            system_parts.append(
                "Use citations [1], [2], ... tied to retrieved context chunk indices."
            )
        system_prompt = "\n\n".join(part for part in system_parts if part)
        user_prompt = (
            f"Question:\n{chat_input.question}\n\n"
            f"Retrieved context:\n{context}\n\n"
            "Answer the question from context."
        )
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in chat_input.conversation_history[-6:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_prompt})

        started = time.time()
        try:
            response = await acompletion(
                model=self.template.model,
                messages=messages,
                temperature=self.template.temperature,
                max_tokens=self.template.max_tokens,
                success_callback=[],
                failure_callback=[],
            )
            answer = (response.choices[0].message.content or "").strip()
            citation_indices = self._extract_citation_indices(answer)
            citations = [
                chunks[idx - 1].document_name for idx in citation_indices if 1 <= idx <= len(chunks)
            ]

            output = RAGChatOutput(
                answer=answer,
                citations=citations,
                chunks_used=min(len(chunks), self.template.max_context_chunks),
                model=self.template.model,
                prompt_tokens=int(getattr(response.usage, "prompt_tokens", 0) if response.usage else 0),
                completion_tokens=int(
                    getattr(response.usage, "completion_tokens", 0) if response.usage else 0
                ),
            )
            self.langfuse_service.trace_generation(
                name="workspace-chat-generation",
                model=self.template.model,
                input_data={"messages": messages},
                output_data=output.model_dump(),
                usage_details={
                    "input": output.prompt_tokens,
                    "output": output.completion_tokens,
                },
                model_parameters={
                    "temperature": self.template.temperature,
                    "max_tokens": self.template.max_tokens,
                },
                workspace_id=self.template.workspace_id,
                domain=self.template.domain,
                customer_id=chat_input.customer_id,
                prompt_version=self.template.prompt_version,
                gepa_variant_id=self.template.gepa_variant_id,
                session_id=session_id,
                extra_metadata={"latency_ms": (time.time() - started) * 1000},
            )
            return output
        except Exception as exc:
            # Never fail the chat request because of model/provider/callback issues.
            # Return an extractive fallback from retrieved chunks instead.
            logger.warning(
                "workspace_litellm_generation_failed_extractive_fallback",
                error=str(exc),
                model=self.template.model,
            )
            used_chunks = min(len(chunks), self.template.max_context_chunks)
            fallback_chunks = chunks[:used_chunks]
            return RAGChatOutput(
                answer=self._build_extractive_fallback_answer(fallback_chunks),
                citations=[chunk.document_name for chunk in fallback_chunks],
                chunks_used=used_chunks,
                model=f"{self.template.model}-extractive-fallback",
                prompt_tokens=0,
                completion_tokens=0,
                confidence=0.3,
            )

    async def _generate_output(
        self,
        chat_input: RAGChatInput,
        chunks: List[RetrievedChunk],
        context: str,
        session_id: Optional[str] = None,
    ) -> RAGChatOutput:
        if self._agent is None:
            return await self._generate_with_litellm(
                chat_input,
                chunks,
                context,
                session_id=session_id,
            )

        prompt = (
            f"Question:\n{chat_input.question}\n\n"
            f"Conversation history:\n{json.dumps(chat_input.conversation_history[-6:])}\n\n"
            f"Retrieved context:\n{context}\n\n"
            "Use the provided context and return the requested JSON output."
        )
        deps = _WorkspaceAgentDeps(
            retrieval_service=self.retrieval_service,
            domain_id=chat_input.domain_id,
            template=self.template,
            knowledge_base_ids=chat_input.knowledge_base_ids,
        )

        try:
            result = await self._agent.run(prompt, deps=deps)
            output = (
                getattr(result, "output", None)
                or getattr(result, "data", None)
                or result
            )
            parsed = output if isinstance(output, RAGChatOutput) else RAGChatOutput.model_validate(output)
            prompt_tokens, completion_tokens = self._coerce_usage(result)
            if prompt_tokens:
                parsed.prompt_tokens = prompt_tokens
            if completion_tokens:
                parsed.completion_tokens = completion_tokens
            if not parsed.model:
                parsed.model = self.template.model
            if parsed.chunks_used <= 0:
                parsed.chunks_used = min(len(chunks), self.template.max_context_chunks)
            if self.template.citation_mode and not parsed.citations:
                indices = self._extract_citation_indices(parsed.answer)
                parsed.citations = [
                    chunks[idx - 1].document_name
                    for idx in indices
                    if 1 <= idx <= len(chunks)
                ]
            return parsed
        except Exception as exc:
            logger.warning("workspace_pydantic_agent_failed_fallback", error=str(exc))
            # Avoid repeated failing agent calls in this worker process.
            self._agent = None
            return await self._generate_with_litellm(
                chat_input,
                chunks,
                context,
                session_id=session_id,
            )

    async def _retrieve_chunks(
        self,
        domain_id: str,
        query: str,
        top_k: int,
        min_score: float,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> List[RetrievedChunk]:
        effective_top_k = max(1, min(top_k or self.template.top_k, self.template.max_context_chunks))
        if self.template.use_hybrid_search:
            chunks = await self.retrieval_service.hybrid_retrieve(
                domain_id=domain_id,
                query=query,
                top_k=effective_top_k,
                knowledge_base_ids=knowledge_base_ids,
            )
        else:
            chunks = await self.retrieval_service.retrieve(
                domain_id=domain_id,
                query=query,
                top_k=effective_top_k,
                min_score=max(min_score, self.template.similarity_threshold),
                knowledge_base_ids=knowledge_base_ids,
            )

        threshold = max(min_score, self.template.similarity_threshold)
        if threshold > 0:
            chunks = [chunk for chunk in chunks if chunk.score >= threshold]
        return chunks[:effective_top_k]

    async def _run_chat(
        self,
        domain_id: str,
        question: str,
        conversation_history: Optional[List[ChatMessage]],
        top_k: int,
        min_score: float,
        customer_id: str,
        knowledge_base_ids: Optional[List[int]] = None,
        session_id: Optional[str] = None,
    ) -> Tuple[RAGChatOutput, List[RetrievedChunk]]:
        rewritten_query = await self._rewrite_query(
            question,
            customer_id=customer_id,
            session_id=session_id,
        )
        chunks = await self._retrieve_chunks(
            domain_id=domain_id,
            query=rewritten_query,
            top_k=top_k,
            min_score=min_score,
            knowledge_base_ids=knowledge_base_ids,
        )

        self.langfuse_service.trace_retrieval(
            query=rewritten_query,
            chunks=[chunk.to_dict() for chunk in chunks],
            workspace_id=self.template.workspace_id,
            domain=self.template.domain,
            customer_id=customer_id,
            prompt_version=self.template.prompt_version,
            gepa_variant_id=self.template.gepa_variant_id,
            session_id=session_id,
        )

        if not chunks:
            output = RAGChatOutput(
                answer=(
                    "I couldn't find any relevant information in the documents to answer your question."
                ),
                citations=[],
                chunks_used=0,
                model=self.template.model,
                prompt_tokens=0,
                completion_tokens=0,
                confidence=0.0,
            )
            return output, []

        context = self._format_context(chunks, self.template.max_context_chunks)
        history_items = []
        for msg in conversation_history or []:
            history_items.append({"role": msg.role, "content": msg.content})

        chat_input = RAGChatInput(
            question=question,
            conversation_history=history_items,
            domain_id=domain_id,
            customer_id=customer_id,
            knowledge_base_ids=knowledge_base_ids,
        )

        started = time.time()
        output = await self._generate_output(
            chat_input,
            chunks,
            context,
            session_id=session_id,
        )
        latency_ms = (time.time() - started) * 1000

        self.langfuse_service.trace_workspace_chat(
            model=output.model,
            input_data=chat_input.model_dump(),
            output_data=output.model_dump(),
            usage_details={
                "input": output.prompt_tokens,
                "output": output.completion_tokens,
            },
            workspace_id=self.template.workspace_id,
            domain=self.template.domain,
            customer_id=customer_id,
            prompt_version=self.template.prompt_version,
            gepa_variant_id=self.template.gepa_variant_id,
            session_id=session_id,
            latency_ms=latency_ms,
        )
        return output, chunks

    async def chat(
        self,
        domain_id: str,
        question: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        top_k: int = 5,
        min_score: float = 0.0,
        knowledge_base_ids: Optional[List[int]] = None,
        customer_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> ChatResponse:
        customer = customer_id or "unknown"
        output, chunks = await self._run_chat(
            domain_id=domain_id,
            question=question,
            conversation_history=conversation_history,
            top_k=top_k,
            min_score=min_score,
            customer_id=customer,
            knowledge_base_ids=knowledge_base_ids,
            session_id=session_id,
        )
        return ChatResponse(
            answer=output.answer,
            chunks=chunks,
            model=output.model,
            prompt_tokens=output.prompt_tokens,
            completion_tokens=output.completion_tokens,
            metadata={
                "chunks_retrieved": len(chunks),
                "citations": output.citations,
                "confidence": output.confidence,
            },
        )

    async def chat_stream(
        self,
        domain_id: str,
        question: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        top_k: int = 5,
        min_score: float = 0.0,
        knowledge_base_ids: Optional[List[int]] = None,
        customer_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        customer = customer_id or "unknown"
        output, chunks = await self._run_chat(
            domain_id=domain_id,
            question=question,
            conversation_history=conversation_history,
            top_k=top_k,
            min_score=min_score,
            customer_id=customer,
            knowledge_base_ids=knowledge_base_ids,
            session_id=session_id,
        )

        yield {"type": "retrieval", "chunks": [chunk.to_dict() for chunk in chunks]}
        if not output.answer:
            yield {"type": "done", "metadata": {"no_context": True}}
            return

        chunk_size = 160
        for i in range(0, len(output.answer), chunk_size):
            yield {"type": "chunk", "content": output.answer[i : i + chunk_size]}

        yield {
            "type": "done",
            "metadata": {
                "model": output.model,
                "chunks_retrieved": len(chunks),
                "prompt_tokens": output.prompt_tokens,
                "completion_tokens": output.completion_tokens,
            },
        }


_WORKSPACE_AGENT_CACHE: Dict[Tuple[int, str], Tuple[str, WorkspacePydanticAgent]] = {}
_WORKSPACE_AGENT_CACHE_LOCK = Lock()


def _prompt_type_key(prompt_type: PromptType) -> str:
    mapping = {
        PromptType.SYSTEM: "system_prompt",
        PromptType.QUERY_REWRITE: "query_rewrite_prompt",
        PromptType.SYNTHESIS: "synthesis_prompt",
        PromptType.RETRIEVAL: "retrieval_prompt",
    }
    return mapping.get(prompt_type, "")


def _normalize_similarity_threshold(value: Any, default_value: float = 0.0) -> float:
    if value is None:
        return default_value
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default_value
    if parsed > 1:
        parsed = parsed / 100.0
    return max(0.0, min(parsed, 1.0))


def _normalize_temperature(value: Any, default_value: float) -> float:
    if value is None:
        return default_value
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default_value
    if parsed > 2:
        parsed = parsed / 100.0
    return max(0.0, min(parsed, 2.0))


def _build_template_from_db(
    workspace: RAGFlowDomain,
    customer_id: str,
    db: Session,
) -> WorkspacePromptTemplate:
    settings = get_settings()

    active_prompts = db.query(PromptTemplate).filter(
        PromptTemplate.customer_id == customer_id,
        PromptTemplate.domain == workspace.name,
        PromptTemplate.status == PromptStatus.ACTIVE,
        PromptTemplate.is_active == True,
    ).all()

    prompt_data: Dict[str, Optional[str]] = {
        "system_prompt": None,
        "query_rewrite_prompt": None,
        "synthesis_prompt": None,
        "retrieval_prompt": None,
    }
    prompt_version = 1
    gepa_variant_id: Optional[int] = None
    gepa_job_id: Optional[int] = None
    for prompt in active_prompts:
        prompt_key = _prompt_type_key(prompt.prompt_type)
        if prompt_key:
            prompt_data[prompt_key] = prompt.content
        prompt_version = max(prompt_version, prompt.version or 1)
        if prompt.gepa_variant_id is not None:
            gepa_variant_id = prompt.gepa_variant_id
        if prompt.gepa_job_id is not None:
            gepa_job_id = prompt.gepa_job_id

    domain_cfg = db.query(DomainPromptConfig).filter(
        DomainPromptConfig.customer_id == customer_id,
        DomainPromptConfig.domain == workspace.name,
        DomainPromptConfig.is_active == True,
    ).first()

    model_name = (
        (domain_cfg.default_model if domain_cfg and domain_cfg.default_model else None)
        or settings.default_llm_model
        or "gpt-4o-mini"
    )
    temperature = _normalize_temperature(
        domain_cfg.temperature if domain_cfg else None,
        0.1,
    )
    similarity_threshold = _normalize_similarity_threshold(
        domain_cfg.similarity_threshold if domain_cfg else None,
        0.0,
    )
    top_k = int(
        (domain_cfg.retrieval_top_k if domain_cfg and domain_cfg.retrieval_top_k else None)
        or workspace.top_k
        or 5
    )

    return WorkspacePromptTemplate(
        workspace_id=workspace.id,
        workspace_name=workspace.display_name or workspace.name,
        domain=workspace.name,
        system_prompt=prompt_data["system_prompt"] or DEFAULT_SYSTEM_PROMPT,
        query_rewrite_prompt=prompt_data["query_rewrite_prompt"] or DEFAULT_QUERY_REWRITE_PROMPT,
        synthesis_prompt=prompt_data["synthesis_prompt"] or DEFAULT_SYNTHESIS_PROMPT,
        retrieval_prompt=prompt_data["retrieval_prompt"] or DEFAULT_RETRIEVAL_PROMPT,
        model=model_name,
        temperature=temperature,
        max_tokens=1024,
        top_k=max(1, min(top_k, 50)),
        similarity_threshold=similarity_threshold,
        use_query_rewrite=domain_cfg.use_query_rewrite if domain_cfg else True,
        use_hybrid_search=True,
        citation_mode=True,
        max_context_chunks=max(1, min(top_k, 20)),
        gepa_variant_id=gepa_variant_id,
        gepa_job_id=gepa_job_id,
        prompt_version=prompt_version,
    )


def _get_workspace_or_raise(workspace_id: int, customer_id: str, db: Session) -> RAGFlowDomain:
    workspace = db.query(RAGFlowDomain).filter(
        RAGFlowDomain.id == workspace_id,
        RAGFlowDomain.customer_id == customer_id,
        RAGFlowDomain.is_active == True,
    ).first()
    if not workspace:
        raise ValueError(f"Workspace {workspace_id} not found")
    return workspace


def invalidate_workspace_agent(workspace_id: Optional[int] = None, customer_id: Optional[str] = None) -> None:
    """Invalidate workspace agent cache globally or for a specific workspace."""
    with _WORKSPACE_AGENT_CACHE_LOCK:
        if workspace_id is None:
            _WORKSPACE_AGENT_CACHE.clear()
            return
        keys = list(_WORKSPACE_AGENT_CACHE.keys())
        for key in keys:
            key_workspace_id, key_customer_id = key
            if key_workspace_id != workspace_id:
                continue
            if customer_id is not None and key_customer_id != customer_id:
                continue
            _WORKSPACE_AGENT_CACHE.pop(key, None)


def get_workspace_prompt_template(
    workspace_id: int,
    customer_id: str,
    db: Session,
    *,
    force_refresh: bool = False,
) -> WorkspacePromptTemplate:
    """Get workspace prompt template from snapshot or prompt tables."""
    workspace = _get_workspace_or_raise(workspace_id, customer_id, db)

    if not force_refresh and workspace.prompt_config_json:
        try:
            template = WorkspacePromptTemplate.model_validate(workspace.prompt_config_json)
            # Ensure identity fields stay aligned with current workspace values.
            template.workspace_id = workspace.id
            template.workspace_name = workspace.display_name or workspace.name
            template.domain = workspace.name
            return template
        except Exception as exc:
            logger.warning(
                "workspace_prompt_snapshot_invalid_rebuilding",
                workspace_id=workspace_id,
                error=str(exc),
            )

    template = _build_template_from_db(workspace, customer_id, db)
    workspace.prompt_config_json = template.model_dump(mode="json")
    db.commit()
    db.refresh(workspace)
    return template


def save_workspace_prompt_template(
    workspace_id: int,
    customer_id: str,
    db: Session,
    template: WorkspacePromptTemplate,
) -> WorkspacePromptTemplate:
    """Persist workspace prompt template snapshot and invalidate agent cache."""
    workspace = _get_workspace_or_raise(workspace_id, customer_id, db)
    template.workspace_id = workspace.id
    template.workspace_name = workspace.display_name or workspace.name
    template.domain = workspace.name

    workspace.prompt_config_json = template.model_dump(mode="json")
    db.commit()
    db.refresh(workspace)
    invalidate_workspace_agent(workspace_id=workspace_id, customer_id=customer_id)
    return template


def refresh_workspace_prompt_template(
    workspace_id: int,
    customer_id: str,
    db: Session,
    *,
    gepa_variant_id: Optional[int] = None,
    gepa_job_id: Optional[int] = None,
) -> WorkspacePromptTemplate:
    """Rebuild workspace prompt snapshot from active prompts and persist it."""
    template = get_workspace_prompt_template(
        workspace_id=workspace_id,
        customer_id=customer_id,
        db=db,
        force_refresh=True,
    )
    if gepa_variant_id is not None:
        template.gepa_variant_id = gepa_variant_id
    if gepa_job_id is not None:
        template.gepa_job_id = gepa_job_id
    return save_workspace_prompt_template(
        workspace_id=workspace_id,
        customer_id=customer_id,
        db=db,
        template=template,
    )


def refresh_workspace_prompt_templates_for_domain(
    domain: str,
    customer_id: str,
    db: Session,
    *,
    gepa_variant_id: Optional[int] = None,
    gepa_job_id: Optional[int] = None,
) -> List[WorkspacePromptTemplate]:
    """Refresh prompt snapshots for all active workspaces in a domain."""
    workspaces = db.query(RAGFlowDomain).filter(
        RAGFlowDomain.customer_id == customer_id,
        RAGFlowDomain.name == domain,
        RAGFlowDomain.is_active == True,
    ).all()
    refreshed: List[WorkspacePromptTemplate] = []
    for workspace in workspaces:
        refreshed.append(
            refresh_workspace_prompt_template(
                workspace_id=workspace.id,
                customer_id=customer_id,
                db=db,
                gepa_variant_id=gepa_variant_id,
                gepa_job_id=gepa_job_id,
            )
        )
    return refreshed


def get_workspace_agent(
    workspace_id: int,
    customer_id: str,
    db: Session,
    retrieval_service: Optional[RetrievalService] = None,
) -> WorkspacePydanticAgent:
    """Create/get cached workspace agent, invalidating on prompt version changes."""
    if retrieval_service is None:
        raise ValueError("retrieval_service is required to build workspace agents")

    template = get_workspace_prompt_template(
        workspace_id=workspace_id,
        customer_id=customer_id,
        db=db,
    )
    template_hash = json.dumps(template.model_dump(mode="json"), sort_keys=True)
    cache_key = (workspace_id, customer_id)

    with _WORKSPACE_AGENT_CACHE_LOCK:
        cached = _WORKSPACE_AGENT_CACHE.get(cache_key)
        if cached and cached[0] == template_hash:
            cached_agent = cached[1]
            cached_agent.retrieval_service = retrieval_service
            return cached_agent

        agent = WorkspacePydanticAgent(
            retrieval_service=retrieval_service,
            template=template,
        )
        _WORKSPACE_AGENT_CACHE[cache_key] = (template_hash, agent)
        return agent


def seed_workspace_prompts(
    workspace_id: int,
    workspace_name: str,
    customer_id: str,
    db: Session,
) -> None:
    """
    Seed default prompt templates for a new workspace into the prompt_templates table.

    This makes the prompts visible in the admin Prompt Management UI and
    available for GEPA optimization from day one. Only seeds if no active
    prompts exist for this workspace domain.
    """
    domain = workspace_name

    existing = db.query(PromptTemplate).filter(
        PromptTemplate.customer_id == customer_id,
        PromptTemplate.domain == domain,
        PromptTemplate.is_active == True,
    ).count()
    if existing > 0:
        return

    prompt_specs = [
        (PromptType.SYSTEM, "System Prompt", DEFAULT_SYSTEM_PROMPT,
         "Main system instructions for the RAG assistant. Controls tone, citation style, and answer format.",
         ["{context}"]),
        (PromptType.QUERY_REWRITE, "Query Rewrite", DEFAULT_QUERY_REWRITE_PROMPT,
         "Rewrites user questions to improve retrieval quality. Expands abbreviations, adds synonyms.",
         ["{question}"]),
        (PromptType.SYNTHESIS, "Answer Synthesis", DEFAULT_SYNTHESIS_PROMPT,
         "Guides how the LLM synthesizes answers from retrieved chunks. Controls citation density and structure.",
         None),
        (PromptType.RETRIEVAL, "Retrieval Guidance", DEFAULT_RETRIEVAL_PROMPT,
         "Instructions for evaluating and prioritizing retrieved context chunks.",
         None),
    ]

    for prompt_type, name, content, description, variables in prompt_specs:
        prompt = PromptTemplate(
            customer_id=customer_id,
            domain=domain,
            prompt_type=prompt_type,
            name=f"{workspace_name} — {name}",
            description=description,
            content=content,
            variables=variables,
            version=1,
            is_active=True,
            status=PromptStatus.ACTIVE,
        )
        db.add(prompt)

    db.flush()
    logger.info(
        "workspace_prompts_seeded",
        workspace_id=workspace_id,
        domain=domain,
        prompts_created=len(prompt_specs),
    )
