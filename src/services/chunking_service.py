"""
Chunking service for the AI Enablement Platform.
Implements various chunking strategies: semantic, fixed, hierarchical, adaptive.
"""

import logging
import hashlib
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from abc import ABC, abstractmethod

import spacy
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..models.document import ChunkingStrategy
from ..services.embedding_client import OpenAIEmbeddingClient

logger = logging.getLogger(__name__)


class BaseChunker(ABC):
    """Abstract base class for all chunking strategies"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.chunk_size = config.get('chunk_size', 1024)
        self.chunk_overlap = config.get('chunk_overlap', 128)
        self.min_chunk_size = config.get('min_chunk_size', 100)
        self.max_chunk_size = config.get('max_chunk_size', 4096)
    
    @abstractmethod
    async def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Chunk text into meaningful segments"""
        pass
    
    def _create_chunk(self, text: str, start_idx: int, end_idx: int, **kwargs) -> Dict[str, Any]:
        """Create a standardized chunk object"""
        chunk_text = text[start_idx:end_idx].strip()
        chunk_id = self._generate_chunk_id(chunk_text, start_idx)
        
        return {
            'chunk_id': chunk_id,
            'text': chunk_text,
            'start_char': start_idx,
            'end_char': end_idx,
            'character_count': len(chunk_text),
            'token_count': len(chunk_text.split()),
            'quality_score': kwargs.get('quality_score', 0.8),
            'section_title': kwargs.get('section_title'),
            'section_level': kwargs.get('section_level'),
            'metadata': kwargs.get('metadata', {})
        }
    
    def _generate_chunk_id(self, text: str, start_idx: int) -> str:
        """Generate unique chunk ID"""
        content_hash = hashlib.md5(f"{text[:50]}_{start_idx}".encode()).hexdigest()[:8]
        return f"chunk_{content_hash}"


class FixedChunker(BaseChunker):
    """Simple fixed-size chunking with overlap"""
    
    async def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Create fixed-size chunks with configurable overlap"""
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # Try to break at word boundary
            if end < len(text):
                # Look for space within reasonable distance
                for i in range(end, max(start + self.chunk_size // 2, end - 50), -1):
                    if text[i] == ' ':
                        end = i
                        break
            
            chunk_text = text[start:end].strip()
            if chunk_text and len(chunk_text) >= self.min_chunk_size:
                chunks.append(self._create_chunk(text, start, end))
            
            start = end - self.chunk_overlap if end < len(text) else end
        
        logger.info(f"Fixed chunking created {len(chunks)} chunks")
        return chunks


class SemanticChunker(BaseChunker):
    """Semantic chunking using sentence embeddings"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.similarity_threshold = config.get('similarity_threshold', 0.85)
        self.window_size = config.get('window_size', 3)
        self.breakpoint_percentile = config.get('breakpoint_percentile', 95.0)
        
        # Initialize models
        self.embedding_client = OpenAIEmbeddingClient(
            target_dimension=config.get('embedding_dimension'),
            model_name=config.get('embedding_model'),
        )
        self.embedding_model_name = self.embedding_client.model_name
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model not found, using simple sentence splitting")
            self.nlp = None
    
    async def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Chunk text using semantic similarity analysis"""
        
        try:
            # Step 1: Split into sentences
            sentences = self._split_into_sentences(text)
            if len(sentences) < 2:
                return [self._create_chunk(text, 0, len(text))]
            
            # Step 2: Create sentence embeddings
            sentence_embeddings = await self._get_sentence_embeddings(sentences)
            
            # Step 3: Calculate similarity scores between adjacent sentences
            similarity_scores = self._calculate_similarity_scores(sentence_embeddings)
            
            # Step 4: Identify breakpoints using configurable threshold
            breakpoints = self._identify_breakpoints(similarity_scores)
            
            # Step 5: Create chunks based on breakpoints
            chunks = self._create_semantic_chunks(text, sentences, breakpoints)
            
            # Step 6: Post-process chunks (merge small, split large)
            optimized_chunks = self._optimize_chunks(chunks, text)
            
            logger.info(f"Semantic chunking created {len(optimized_chunks)} chunks")
            return optimized_chunks
            
        except Exception as e:
            logger.error(f"Semantic chunking failed: {e}")
            # Fallback to fixed chunking
            fallback_chunker = FixedChunker(self.config)
            return await fallback_chunker.chunk_text(text)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        if self.nlp:
            doc = self.nlp(text)
            sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        else:
            # Simple sentence splitting
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    async def _get_sentence_embeddings(self, sentences: List[str]) -> np.ndarray:
        """Get embeddings for sentences"""
        return await self.embedding_client.embed_texts(sentences, batch_size=32)
    
    def _calculate_similarity_scores(self, embeddings: np.ndarray) -> List[float]:
        """Calculate cosine similarity between adjacent sentence embeddings"""
        similarities = []
        
        for i in range(len(embeddings) - 1):
            # Cosine similarity between adjacent sentences
            similarity = cosine_similarity(
                embeddings[i].reshape(1, -1), 
                embeddings[i + 1].reshape(1, -1)
            )[0][0]
            similarities.append(similarity)
        
        return similarities
    
    def _identify_breakpoints(self, similarity_scores: List[float]) -> List[int]:
        """Identify breakpoints using percentile-based threshold"""
        if not similarity_scores:
            return []
        
        # Calculate threshold based on percentile
        threshold = np.percentile(similarity_scores, 100 - self.breakpoint_percentile)
        
        # Find breakpoints where similarity drops below threshold
        breakpoints = []
        for i, score in enumerate(similarity_scores):
            if score < threshold:
                breakpoints.append(i + 1)  # +1 because we break after sentence i
        
        # Ensure we have reasonable breakpoints
        if not breakpoints:
            # If no breakpoints found, create some based on window size
            for i in range(self.window_size, len(similarity_scores), self.window_size):
                breakpoints.append(i)
        
        return breakpoints
    
    def _create_semantic_chunks(
        self, 
        text: str, 
        sentences: List[str], 
        breakpoints: List[int]
    ) -> List[Dict[str, Any]]:
        """Create chunks based on identified breakpoints"""
        chunks = []
        
        # Add breakpoints at beginning and end
        all_breakpoints = [0] + breakpoints + [len(sentences)]
        
        for i in range(len(all_breakpoints) - 1):
            start_sentence = all_breakpoints[i]
            end_sentence = all_breakpoints[i + 1]
            
            # Get text span for this chunk
            chunk_sentences = sentences[start_sentence:end_sentence]
            chunk_text = ' '.join(chunk_sentences)
            
            # Find character positions in original text
            char_start = text.find(chunk_sentences[0])
            if char_start == -1:
                continue
                
            char_end = char_start + len(chunk_text)
            
            if len(chunk_text.strip()) >= self.min_chunk_size:
                chunk_metadata = {
                    'sentence_range': [start_sentence, end_sentence],
                    'sentence_count': len(chunk_sentences),
                    'chunking_strategy': 'semantic'
                }
                
                chunks.append(self._create_chunk(
                    text, char_start, char_end, 
                    metadata=chunk_metadata,
                    quality_score=0.9  # Higher quality for semantic chunks
                ))
        
        return chunks
    
    def _optimize_chunks(self, chunks: List[Dict[str, Any]], original_text: str) -> List[Dict[str, Any]]:
        """Optimize chunks by merging small ones and splitting large ones"""
        optimized = []
        i = 0
        
        while i < len(chunks):
            current_chunk = chunks[i]
            
            # If chunk is too small, try to merge with next
            if (len(current_chunk['text']) < self.min_chunk_size and 
                i + 1 < len(chunks)):
                
                next_chunk = chunks[i + 1]
                merged_length = len(current_chunk['text']) + len(next_chunk['text'])
                
                if merged_length <= self.max_chunk_size:
                    # Merge chunks
                    merged_chunk = self._create_chunk(
                        original_text,
                        current_chunk['start_char'],
                        next_chunk['end_char'],
                        metadata={'merged': True, 'chunking_strategy': 'semantic'}
                    )
                    optimized.append(merged_chunk)
                    i += 2  # Skip both chunks
                    continue
            
            # If chunk is too large, split it
            if len(current_chunk['text']) > self.max_chunk_size:
                split_chunks = self._split_large_chunk(current_chunk, original_text)
                optimized.extend(split_chunks)
            else:
                optimized.append(current_chunk)
            
            i += 1
        
        return optimized
    
    def _split_large_chunk(self, chunk: Dict[str, Any], original_text: str) -> List[Dict[str, Any]]:
        """Split a large chunk into smaller ones"""
        chunk_text = chunk['text']
        target_size = self.chunk_size
        overlap = self.chunk_overlap
        
        splits = []
        start = 0
        
        while start < len(chunk_text):
            end = min(start + target_size, len(chunk_text))
            
            # Try to break at sentence boundary
            if end < len(chunk_text):
                for i in range(end, max(start + target_size // 2, end - 100), -1):
                    if chunk_text[i] in '.!?':
                        end = i + 1
                        break
            
            split_text = chunk_text[start:end].strip()
            if split_text:
                split_metadata = {
                    'parent_chunk_id': chunk['chunk_id'],
                    'split_index': len(splits),
                    'chunking_strategy': 'semantic_split'
                }
                
                splits.append(self._create_chunk(
                    original_text,
                    chunk['start_char'] + start,
                    chunk['start_char'] + end,
                    metadata=split_metadata
                ))
            
            start = end - overlap if end < len(chunk_text) else end
        
        return splits


class HierarchicalChunker(BaseChunker):
    """Hierarchical chunking that preserves document structure"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.preserve_structure = config.get('preserve_structure', True)
        self.hierarchy_levels = config.get('hierarchy_levels', ['document', 'section', 'paragraph'])
        
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model not found, using simple text processing")
            self.nlp = None
    
    async def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Create hierarchical chunks based on document structure"""
        
        try:
            # Step 1: Detect document structure
            structure = self._detect_document_structure(text)
            
            # Step 2: Create hierarchical chunks
            chunks = self._create_hierarchical_chunks(text, structure)
            
            logger.info(f"Hierarchical chunking created {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Hierarchical chunking failed: {e}")
            # Fallback to semantic chunking
            semantic_chunker = SemanticChunker(self.config)
            return await semantic_chunker.chunk_text(text)
    
    def _detect_document_structure(self, text: str) -> Dict[str, Any]:
        """Detect document structure (headers, sections, paragraphs)"""
        structure = {
            'sections': [],
            'paragraphs': [],
            'headers': []
        }
        
        # Detect headers (simple heuristic)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if line and self._is_likely_header(line):
                structure['headers'].append({
                    'text': line,
                    'line_number': i,
                    'level': self._estimate_header_level(line)
                })
        
        # Detect paragraphs
        paragraphs = text.split('\n\n')
        start_pos = 0
        for para in paragraphs:
            para = para.strip()
            if para:
                structure['paragraphs'].append({
                    'text': para,
                    'start_pos': start_pos,
                    'end_pos': start_pos + len(para)
                })
            start_pos += len(para) + 2  # +2 for \n\n
        
        return structure
    
    def _is_likely_header(self, line: str) -> bool:
        """Heuristic to determine if a line is likely a header"""
        if len(line) > 100:  # Too long for header
            return False
        
        # Check for common header patterns
        header_indicators = [
            line.isupper(),  # ALL CAPS
            line.endswith(':'),  # Ends with colon
            len(line.split()) <= 10,  # Short enough
            not line.endswith('.'),  # Doesn't end with period
            line[0].isupper() if line else False  # Starts with capital
        ]
        
        return sum(header_indicators) >= 2
    
    def _estimate_header_level(self, header: str) -> int:
        """Estimate header level (1-6)"""
        if header.isupper():
            return 1
        elif len(header.split()) <= 3:
            return 2
        elif len(header.split()) <= 6:
            return 3
        else:
            return 4
    
    def _create_hierarchical_chunks(self, text: str, structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create chunks based on document structure"""
        chunks = []
        
        # If we have clear paragraph structure, use it
        if structure['paragraphs']:
            for i, para in enumerate(structure['paragraphs']):
                if len(para['text']) >= self.min_chunk_size:
                    # Find associated header
                    section_title = self._find_section_title(para, structure['headers'])
                    
                    chunk_metadata = {
                        'paragraph_index': i,
                        'chunking_strategy': 'hierarchical'
                    }
                    
                    chunks.append(self._create_chunk(
                        text,
                        para['start_pos'],
                        para['end_pos'],
                        section_title=section_title,
                        section_level=2,
                        metadata=chunk_metadata,
                        quality_score=0.85
                    ))
        else:
            # Fallback to sentence-based chunking
            if self.nlp:
                doc = self.nlp(text)
                sentences = list(doc.sents)
                
                current_chunk = []
                current_start = 0
                
                for sent in sentences:
                    current_chunk.append(sent.text)
                    chunk_text = ' '.join(current_chunk)
                    
                    if len(chunk_text) >= self.chunk_size:
                        chunks.append(self._create_chunk(
                            text,
                            current_start,
                            current_start + len(chunk_text),
                            metadata={'chunking_strategy': 'hierarchical_sentence'}
                        ))
                        current_chunk = []
                        current_start = sent.end_char
                
                # Add remaining chunk
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    chunks.append(self._create_chunk(
                        text,
                        current_start,
                        len(text),
                        metadata={'chunking_strategy': 'hierarchical_sentence'}
                    ))
        
        return chunks
    
    def _find_section_title(self, paragraph: Dict[str, Any], headers: List[Dict[str, Any]]) -> Optional[str]:
        """Find the most relevant section title for a paragraph"""
        if not headers:
            return None
        
        # Find the header that appears before this paragraph
        para_start = paragraph['start_pos']
        relevant_header = None
        
        for header in headers:
            if header['line_number'] * 50 < para_start:  # Rough estimate of line position
                relevant_header = header
            else:
                break
        
        return relevant_header['text'] if relevant_header else None


class ChunkingService:
    """Main chunking service that coordinates different chunking strategies"""
    
    def __init__(self):
        self.chunkers = {}
    
    def _get_chunker(self, strategy: ChunkingStrategy, config: Dict[str, Any]) -> BaseChunker:
        """Get appropriate chunker for strategy"""
        
        if strategy == ChunkingStrategy.FIXED:
            return FixedChunker(config)
        elif strategy == ChunkingStrategy.SEMANTIC:
            return SemanticChunker(config)
        elif strategy == ChunkingStrategy.HIERARCHICAL:
            return HierarchicalChunker(config)
        elif strategy == ChunkingStrategy.ADAPTIVE:
            # For now, adaptive uses semantic chunking
            # TODO: Implement true adaptive chunking
            return SemanticChunker(config)
        elif strategy == ChunkingStrategy.HYBRID:
            # For now, hybrid uses semantic chunking
            # TODO: Implement hybrid chunking
            return SemanticChunker(config)
        else:
            # Default to semantic
            return SemanticChunker(config)
    
    async def chunk_document(
        self, 
        text: str, 
        strategy: ChunkingStrategy, 
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Chunk document using specified strategy"""
        
        logger.info(f"Chunking document with strategy: {strategy}")
        
        # Get appropriate chunker
        chunker = self._get_chunker(strategy, config)
        
        # Chunk the text
        chunks = await chunker.chunk_text(text)
        
        # Add common metadata
        for chunk in chunks:
            chunk['metadata']['chunking_timestamp'] = datetime.utcnow().isoformat()
            chunk['metadata']['chunking_strategy'] = strategy
        
        return chunks
