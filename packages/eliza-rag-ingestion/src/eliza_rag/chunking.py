"""
Chunking Service - Split text into semantic chunks for embedding.

Provides multiple chunking strategies:
- Fixed size with overlap
- Sentence-based
- Semantic (paragraph/section aware)
"""

import logging
import re
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkingStrategy(str, Enum):
    """Text chunking strategies."""
    FIXED = "fixed"           # Fixed token count with overlap
    SENTENCE = "sentence"     # Sentence-based chunking
    SEMANTIC = "semantic"     # Paragraph/section aware
    LLM = "llm"              # LLM-identified logical sections (from structured parse)


@dataclass
class TextChunk:
    """A chunk of text ready for embedding."""
    text: str
    index: int
    start_char: int
    end_char: int
    token_count: int
    metadata: dict


class ChunkingService:
    """
    Split text into chunks suitable for embedding and retrieval.
    
    Optimized for RAG applications with configurable overlap
    to maintain context across chunk boundaries.
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC
    ):
        """
        Initialize chunking service.
        
        Args:
            chunk_size: Target chunk size in tokens (approximate)
            chunk_overlap: Overlap between chunks in tokens
            strategy: Chunking strategy to use
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        
        # Approximate chars per token (for estimation)
        self._chars_per_token = 4
    
    def chunk_text(
        self,
        text: str,
        metadata: Optional[dict] = None
    ) -> List[TextChunk]:
        """
        Split text into chunks.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to chunks
            
        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []
        
        metadata = metadata or {}
        
        if self.strategy == ChunkingStrategy.FIXED:
            return self._chunk_fixed(text, metadata)
        elif self.strategy == ChunkingStrategy.SENTENCE:
            return self._chunk_by_sentence(text, metadata)
        else:
            return self._chunk_semantic(text, metadata)
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(text) // self._chars_per_token
    
    def _chunk_fixed(self, text: str, metadata: dict) -> List[TextChunk]:
        """Fixed-size chunking with overlap."""
        chunks = []
        char_chunk_size = self.chunk_size * self._chars_per_token
        char_overlap = self.chunk_overlap * self._chars_per_token
        
        start = 0
        index = 0
        
        while start < len(text):
            end = min(start + char_chunk_size, len(text))
            
            # Try to break at word boundary
            if end < len(text):
                # Look for last space within the chunk
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append(TextChunk(
                    text=chunk_text,
                    index=index,
                    start_char=start,
                    end_char=end,
                    token_count=self._estimate_tokens(chunk_text),
                    metadata=metadata.copy()
                ))
                index += 1
            
            start = end - char_overlap
            if start < 0:
                start = 0
            # Prevent infinite loop
            if end >= len(text):
                break
            if start >= end:
                start = end
        
        return chunks
    
    def _chunk_by_sentence(self, text: str, metadata: dict) -> List[TextChunk]:
        """Chunk by sentences, grouping to reach target size."""
        # Split into sentences
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(sentence_pattern, text)
        
        chunks = []
        current_chunk = []
        current_size = 0
        start_char = 0
        index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_tokens = self._estimate_tokens(sentence)
            
            # If single sentence exceeds chunk size, split it
            if sentence_tokens > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    chunks.append(TextChunk(
                        text=chunk_text,
                        index=index,
                        start_char=start_char,
                        end_char=start_char + len(chunk_text),
                        token_count=current_size,
                        metadata=metadata.copy()
                    ))
                    index += 1
                    start_char += len(chunk_text) + 1
                    current_chunk = []
                    current_size = 0
                
                # Split long sentence using fixed chunking
                sub_chunks = self._chunk_fixed(sentence, metadata)
                for sc in sub_chunks:
                    sc.index = index
                    chunks.append(sc)
                    index += 1
                continue
            
            # Check if adding this sentence exceeds limit
            if current_size + sentence_tokens > self.chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append(TextChunk(
                    text=chunk_text,
                    index=index,
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    token_count=current_size,
                    metadata=metadata.copy()
                ))
                index += 1
                start_char += len(chunk_text) + 1
                
                # Keep some overlap (last sentence)
                overlap_sentences = current_chunk[-1:] if current_chunk else []
                current_chunk = overlap_sentences
                current_size = sum(self._estimate_tokens(s) for s in current_chunk)
            
            current_chunk.append(sentence)
            current_size += sentence_tokens
        
        # Don't forget the last chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(TextChunk(
                text=chunk_text,
                index=index,
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                token_count=current_size,
                metadata=metadata.copy()
            ))
        
        return chunks
    
    def _chunk_semantic(self, text: str, metadata: dict) -> List[TextChunk]:
        """Semantic chunking - respects paragraphs and sections."""
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        current_chunk = []
        current_size = 0
        start_char = 0
        index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_tokens = self._estimate_tokens(para)
            
            # If single paragraph exceeds chunk size, use sentence chunking
            if para_tokens > self.chunk_size:
                # Flush current chunk
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append(TextChunk(
                        text=chunk_text,
                        index=index,
                        start_char=start_char,
                        end_char=start_char + len(chunk_text),
                        token_count=current_size,
                        metadata=metadata.copy()
                    ))
                    index += 1
                    start_char += len(chunk_text) + 2
                    current_chunk = []
                    current_size = 0
                
                # Chunk the long paragraph by sentences
                para_chunks = self._chunk_by_sentence(para, metadata)
                for pc in para_chunks:
                    pc.index = index
                    chunks.append(pc)
                    index += 1
                continue
            
            # Check if adding this paragraph exceeds limit
            if current_size + para_tokens > self.chunk_size and current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append(TextChunk(
                    text=chunk_text,
                    index=index,
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    token_count=current_size,
                    metadata=metadata.copy()
                ))
                index += 1
                start_char += len(chunk_text) + 2
                current_chunk = []
                current_size = 0
            
            current_chunk.append(para)
            current_size += para_tokens
        
        # Last chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append(TextChunk(
                text=chunk_text,
                index=index,
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                token_count=current_size,
                metadata=metadata.copy()
            ))
        
        return chunks
    
    def chunk_from_structured_sections(
        self,
        sections: List[dict],
        metadata: Optional[dict] = None,
    ) -> List[TextChunk]:
        """
        Build chunks from LLM-identified structured sections.

        Each section from the parser is a logical unit (paragraph, table, list, etc.)
        with heading and type metadata. We group small sections to reach the target
        chunk size, but never merge across different headings.
        """
        metadata = metadata or {}
        chunks: List[TextChunk] = []
        current_parts: List[str] = []
        current_size = 0
        current_heading: Optional[str] = None
        current_page: Optional[int] = None
        current_section_type: Optional[str] = None
        start_char = 0
        index = 0

        def _flush():
            nonlocal index, start_char, current_parts, current_size, current_heading, current_page, current_section_type
            if not current_parts:
                return
            chunk_text = "\n\n".join(current_parts)
            chunk_meta = dict(metadata)
            if current_heading:
                chunk_meta["section_title"] = current_heading
            if current_page is not None:
                chunk_meta["page_number"] = current_page
            if current_section_type:
                chunk_meta["chunk_type"] = current_section_type
            chunk_meta["chunking_strategy"] = "llm"
            chunks.append(TextChunk(
                text=chunk_text,
                index=index,
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                token_count=self._estimate_tokens(chunk_text),
                metadata=chunk_meta,
            ))
            index += 1
            start_char += len(chunk_text) + 2
            current_parts = []
            current_size = 0

        for section in sections:
            if not isinstance(section, dict):
                continue
            text = (section.get("text") or "").strip()
            if not text:
                continue

            heading = section.get("heading")
            page = section.get("page_number")
            stype = section.get("type", "paragraph")
            tokens = self._estimate_tokens(text)

            # Flush on heading change (new logical section boundary)
            if heading and heading != current_heading and current_parts:
                _flush()

            # Flush if adding this section would exceed chunk size
            if current_size + tokens > self.chunk_size and current_parts:
                _flush()

            # If a single section exceeds chunk size, split it by sentences
            if tokens > self.chunk_size:
                _flush()
                sub_chunks = self._chunk_by_sentence(text, metadata)
                for sc in sub_chunks:
                    sc.index = index
                    sc.metadata = dict(sc.metadata)
                    if heading:
                        sc.metadata["section_title"] = heading
                    if page is not None:
                        sc.metadata["page_number"] = page
                    sc.metadata["chunk_type"] = stype
                    sc.metadata["chunking_strategy"] = "llm"
                    chunks.append(sc)
                    index += 1
                continue

            current_parts.append(text)
            current_size += tokens
            if heading:
                current_heading = heading
            if page is not None:
                current_page = page
            current_section_type = stype

        _flush()
        return chunks

    def rechunk(
        self,
        chunks: List[TextChunk],
        new_size: int,
        new_overlap: int
    ) -> List[TextChunk]:
        """
        Re-chunk existing chunks with different parameters.
        
        Useful for experimenting with chunk sizes without re-parsing.
        """
        # Concatenate all chunks
        full_text = ' '.join(c.text for c in chunks)
        
        # Create new chunker with new parameters
        new_chunker = ChunkingService(
            chunk_size=new_size,
            chunk_overlap=new_overlap,
            strategy=self.strategy
        )
        
        return new_chunker.chunk_text(full_text)
