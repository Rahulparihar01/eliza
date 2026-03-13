"""
RAG Chat Service - Question answering with retrieved context.

Uses LiteLLM for LLM abstraction, supporting OpenAI, Anthropic, etc.
"""

import logging
import json
from typing import List, Optional, Dict, Any, AsyncIterator
from dataclasses import dataclass

from .retrieval import RetrievalService, RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """A chat message."""
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class ChatResponse:
    """Response from RAG chat."""
    answer: str
    chunks: List[RetrievedChunk]
    model: str
    prompt_tokens: int
    completion_tokens: int
    metadata: Dict[str, Any]


DEFAULT_SYSTEM_PROMPT = """You are a knowledgeable assistant that answers questions using retrieved document context.

Your retrieved context includes chunks from potentially multiple knowledge bases and documents. Each chunk is labeled with its source document, knowledge base, section, and page number.

Instructions:
- Answer ONLY from the provided context. Never fabricate information.
- Synthesize information across multiple sources when the answer spans different documents or knowledge bases.
- Use numbered citations [1], [2], [3] etc. matching the source indices in the context.
- When citing, prefer citing the most specific source (e.g., the chunk that directly states the fact).
- Include page numbers when referencing specific claims so the user can verify (e.g., "according to [1] (p.34)").
- If the context is insufficient, state what you found and what is missing.
- Be concise but thorough. Structure longer answers with bullet points or numbered lists.
- If sources disagree, acknowledge the discrepancy and cite both.

Context from documents:
{context}
"""

DEFAULT_QUERY_REWRITE_PROMPT = """Rewrite the following user question to improve retrieval from a document knowledge base. Make it more specific and search-friendly while preserving the original intent.

Rules:
- Expand abbreviations and acronyms where possible.
- If the question is multi-part, focus on the core information need.
- Add relevant synonyms or domain terms that documents might use.
- Keep it as a single clear question (not multiple).
- Return ONLY the rewritten question, nothing else.

Original question: {question}"""

DEFAULT_SYNTHESIS_PROMPT = """When synthesizing your answer from the retrieved context:
- Lead with the direct answer to the question.
- Support each claim with a citation [N] referencing the source chunk.
- If information comes from different knowledge bases, note which source provides which facts.
- For numerical data (financial figures, dates, percentages), always cite the specific source.
- End with a brief note if the context suggests there may be additional relevant information not retrieved."""

DEFAULT_RETRIEVAL_PROMPT = """When evaluating retrieved context for relevance:
- Prioritize chunks that directly answer the question over tangentially related ones.
- Consider information from all knowledge bases — the answer may require combining facts from multiple sources.
- Pay attention to document metadata (titles, sections, page numbers) to understand the source authority.
- If a chunk contains a definition or explicit statement, it is more authoritative than one that merely mentions the topic."""


class RAGChatService:
    """
    RAG-based chat service for document Q&A.
    
    Retrieves relevant context and generates answers using LLM.
    """
    
    def __init__(
        self,
        retrieval_service: RetrievalService,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None
    ):
        """
        Initialize chat service.
        
        Args:
            retrieval_service: Service for retrieving context
            model: LLM model to use (via LiteLLM)
            temperature: Generation temperature
            max_tokens: Max tokens for response
            system_prompt: Custom system prompt (use {context} placeholder)
        """
        self.retrieval_service = retrieval_service
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    
    async def chat(
        self,
        domain_id: str,
        question: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        top_k: int = 5,
        min_score: float = 0.0,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> ChatResponse:
        """
        Answer a question using RAG.
        
        Args:
            domain_id: Domain to search
            question: User's question
            conversation_history: Previous messages for context
            top_k: Number of chunks to retrieve
            min_score: Minimum retrieval score
            
        Returns:
            ChatResponse with answer and sources
        """
        # Retrieve relevant context using hybrid search (keyword + semantic)
        # This helps with queries that include specific section numbers, names, etc.
        chunks = await self.retrieval_service.hybrid_retrieve(
            domain_id=domain_id,
            query=question,
            top_k=top_k,
            knowledge_base_ids=knowledge_base_ids,
        )
        
        # Build enriched context from chunks with numbered indices for citation
        context_parts = []
        for idx, chunk in enumerate(chunks[:5], start=1):
            doc_label = chunk.document_title or chunk.document_name
            header = f"[{idx}] {doc_label}"
            if chunk.knowledge_base_name:
                header += f" (KB: {chunk.knowledge_base_name})"
            if chunk.section_hierarchy:
                header += f" — {' > '.join(chunk.section_hierarchy)}"
            elif chunk.section_title:
                header += f" — {chunk.section_title}"
            if chunk.page_number:
                page_str = str(chunk.page_number)
                if chunk.page_range and len(chunk.page_range) == 2 and chunk.page_range[0] != chunk.page_range[1]:
                    page_str = f"{chunk.page_range[0]}-{chunk.page_range[1]}"
                header += f" [p.{page_str}]"
            context_parts.append(f"{header}\n{chunk.text}")
        context = "\n\n---\n\n".join(context_parts)
        
        if not chunks:
            return ChatResponse(
                answer="I couldn't find any relevant information in the documents to answer your question.",
                chunks=[],
                model=self.model,
                prompt_tokens=0,
                completion_tokens=0,
                metadata={"no_context": True}
            )
        
        # Build messages
        system_content = self.system_prompt.format(context=context)
        
        messages = [{"role": "system", "content": system_content}]
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages
                messages.append({"role": msg.role, "content": msg.content})
        
        # Add current question
        messages.append({"role": "user", "content": question})
        
        # Call LLM
        try:
            from litellm import acompletion
            
            response = await acompletion(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            answer = response.choices[0].message.content
            
            return ChatResponse(
                answer=answer,
                chunks=chunks,
                model=self.model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                metadata={
                    "total_tokens": response.usage.total_tokens,
                    "chunks_retrieved": len(chunks)
                }
            )
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    async def chat_stream(
        self,
        domain_id: str,
        question: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        top_k: int = 5,
        min_score: float = 0.0,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream chat response for real-time UI updates.
        
        Yields:
            Dict with either "chunk" (text) or "metadata" (final info)
        """
        # Retrieve context first
        chunks, context = await self.retrieval_service.retrieve_with_context(
            domain_id=domain_id,
            query=question,
            top_k=top_k,
            min_score=min_score,
            knowledge_base_ids=knowledge_base_ids,
        )
        
        # Yield retrieved chunks info
        yield {
            "type": "retrieval",
            "chunks": [c.to_dict() for c in chunks]
        }
        
        if not chunks:
            yield {
                "type": "chunk",
                "content": "I couldn't find any relevant information in the documents to answer your question."
            }
            yield {"type": "done", "metadata": {"no_context": True}}
            return
        
        # Build messages
        system_content = self.system_prompt.format(context=context)
        messages = [{"role": "system", "content": system_content}]
        
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg.role, "content": msg.content})
        
        messages.append({"role": "user", "content": question})
        
        # Stream from LLM
        try:
            from litellm import acompletion
            
            response = await acompletion(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )
            
            full_content = ""
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield {"type": "chunk", "content": content}
            
            yield {
                "type": "done",
                "metadata": {
                    "model": self.model,
                    "chunks_retrieved": len(chunks),
                    "answer_length": len(full_content)
                }
            }
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"type": "error", "error": str(e)}
    
    async def summarize_document(
        self,
        domain_id: str,
        document_id: str,
        max_chunks: int = 10
    ) -> str:
        """
        Generate a summary of a specific document.
        
        Retrieves chunks from the document and asks LLM to summarize.
        """
        # Retrieve chunks specifically from this document
        # TODO: Add document filter to retrieval
        
        from litellm import acompletion
        
        # For now, use a general query
        chunks, context = await self.retrieval_service.retrieve_with_context(
            domain_id=domain_id,
            query=f"document:{document_id}",  # Metadata filter would be better
            top_k=max_chunks
        )
        
        if not chunks:
            return "No content found for this document."
        
        messages = [
            {"role": "system", "content": "You are a document summarizer. Provide a clear, concise summary."},
            {"role": "user", "content": f"Please summarize the following document content:\n\n{context}"}
        ]
        
        response = await acompletion(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=500
        )
        
        return response.choices[0].message.content
