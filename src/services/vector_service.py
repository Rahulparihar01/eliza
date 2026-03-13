"""
Vector service for the AI Enablement Platform.
Handles embedding generation, FAISS indexing, and vector similarity search.
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pickle

import numpy as np
import faiss
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models.document import Document, DocumentChunk, DocumentSearchRequest, DocumentSearchResult
from ..services.base_service import BaseService
from ..services.embedding_client import OpenAIEmbeddingClient
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class VectorService(BaseService):
    """Vector storage and similarity search service using FAISS"""
    
    def __init__(self, company_hr_dataset: Optional[str] = None):
        self.settings = get_settings()
        self.company_hr_dataset = company_hr_dataset  # Company-specific index
        
        # Embedding model configuration from settings
        self.embedding_model_name = None
        self.embedding_client = None
        self.embedding_dimension = self.settings.embedding_dimension
        
        # FAISS index
        self.index = None
        self.chunk_id_mapping = {}  # Maps FAISS index positions to chunk IDs
        
        # Vector storage directory from settings (company-specific)
        base_vector_dir = Path(self.settings.vector_index_directory)
        
        if company_hr_dataset:
            # Use company-specific subdirectory
            self.vector_dir = base_vector_dir / company_hr_dataset
        else:
            # Legacy: Use base directory (for backward compatibility)
            self.vector_dir = base_vector_dir
        
        self.vector_dir.mkdir(parents=True, exist_ok=True)
        
        # Index files
        self.index_file = self.vector_dir / "faiss_index.bin"
        self.mapping_file = self.vector_dir / "chunk_mapping.json"
        
        # Initialize lazily - will be called on first use
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Ensure the vector service is initialized"""
        if not self._initialized:
            await self._initialize_async()
    
    async def _initialize_async(self):
        """Initialize the vector service asynchronously"""
        if self._initialized:
            return
            
        try:
            # Initialize embedding client
            self.embedding_client = OpenAIEmbeddingClient(
                target_dimension=self.settings.embedding_dimension,
                model_name=self.settings.embedding_model,
            )
            self.embedding_model_name = self.embedding_client.model_name
            self.embedding_dimension = self.embedding_client.output_dimension
            logger.info(
                f"Using OpenAI embedding model: {self.embedding_model_name} "
                f"(dimension {self.embedding_dimension})"
            )
            
            # Load existing index if available
            await self._load_index()
            
            logger.info("Vector service initialized successfully")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize vector service: {e}")
            self._initialized = False
    
    async def _load_index(self):
        """Load existing FAISS index and mappings"""
        try:
            if self.index_file.exists() and self.mapping_file.exists():
                # Load FAISS index
                self.index = faiss.read_index(str(self.index_file))
                
                # Load chunk ID mapping
                with open(self.mapping_file, 'r') as f:
                    # Convert string keys back to integers
                    mapping_data = json.load(f)
                    self.chunk_id_mapping = {int(k): v for k, v in mapping_data.items()}
                
                if self.index.d != self.embedding_dimension:
                    logger.warning(
                        "FAISS index dimension mismatch; creating a new index",
                        extra={
                            "index_dimension": self.index.d,
                            "embedding_dimension": self.embedding_dimension,
                        },
                    )
                    self._create_new_index()
                else:
                    logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
            else:
                # Create new index
                self._create_new_index()
                
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            self._create_new_index()
    
    def _create_new_index(self):
        """Create a new FAISS index"""
        # Use IndexFlatIP for cosine similarity (after L2 normalization)
        self.index = faiss.IndexFlatIP(self.embedding_dimension)
        self.chunk_id_mapping = {}
        logger.info("Created new FAISS index")
    
    async def _save_index(self):
        """Save FAISS index and mappings to disk"""
        try:
            # Save FAISS index
            faiss.write_index(self.index, str(self.index_file))
            
            # Save chunk ID mapping
            with open(self.mapping_file, 'w') as f:
                json.dump(self.chunk_id_mapping, f)
            
            logger.info(f"Saved FAISS index with {self.index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
    
    async def generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for a single text"""
        await self._ensure_initialized()
        if not self.embedding_client:
            raise RuntimeError("Embedding model not initialized")
        
        # Generate embedding
        embeddings = await self.embedding_client.embed_texts([text], batch_size=1)
        if embeddings.size == 0:
            raise RuntimeError("Failed to generate embedding")
        embedding = embeddings[0]
        
        # Normalize for cosine similarity
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    async def generate_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        await self._ensure_initialized()
        if not self.embedding_client:
            raise RuntimeError("Embedding model not initialized")
        
        embeddings = await self.embedding_client.embed_texts(texts, batch_size=32)
        if embeddings.size == 0:
            return embeddings
        
        # Normalize for cosine similarity
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        return embeddings
    
    async def add_chunk_to_index(self, chunk_id: str, text: str) -> bool:
        """Add a single chunk to the FAISS index"""
        try:
            # Generate embedding
            embedding = await self.generate_embedding(text)
            
            # Add to index
            self.index.add(embedding.reshape(1, -1))
            
            # Update mapping
            index_position = self.index.ntotal - 1
            self.chunk_id_mapping[index_position] = chunk_id
            
            # Save index to disk for persistence
            await self._save_index()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add chunk {chunk_id} to index: {e}")
            return False
    
    async def add_chunks_to_index_batch(self, chunks: List[Tuple[str, str]]) -> int:
        """Add multiple chunks to the FAISS index in batch"""
        try:
            if not chunks:
                return 0
            
            # Extract texts and chunk IDs
            chunk_ids = [chunk_id for chunk_id, _ in chunks]
            texts = [text for _, text in chunks]
            
            # Generate embeddings in batch
            embeddings = await self.generate_embeddings_batch(texts)
            
            # Add to index
            start_position = self.index.ntotal
            self.index.add(embeddings)
            
            # Update mapping
            for i, chunk_id in enumerate(chunk_ids):
                self.chunk_id_mapping[start_position + i] = chunk_id
            
            # Save index after every batch to ensure persistence
            await self._save_index()
            
            logger.info(f"Added {len(chunks)} chunks to FAISS index")
            return len(chunks)
            
        except Exception as e:
            logger.error(f"Failed to add chunks to index: {e}")
            return 0
    
    async def generate_embeddings_for_document(self, document_id: int) -> bool:
        """Generate embeddings for all chunks of a document"""
        try:
            # Ensure service is initialized (loads embedding model)
            await self._ensure_initialized()
            
            with self.get_db_session() as db:
                # Get all chunks for the document
                chunks = db.query(DocumentChunk).filter(
                    DocumentChunk.document_id == document_id
                ).all()

                if not chunks:
                    logger.warning(f"No chunks found for document {document_id}")
                    return False

                # Prepare chunk data for batch processing
                chunk_data = [(chunk.chunk_id, chunk.text) for chunk in chunks]

                # Add to FAISS index
                added_count = await self.add_chunks_to_index_batch(chunk_data)

                # Update chunk records with embedding info
                for chunk in chunks:
                    chunk.embedding_model = self.embedding_model_name
                    # Note: We don't store the actual embedding in the database
                    # as it's stored in FAISS index

                db.commit()
                logger.info(f"Generated embeddings for {added_count} chunks in document {document_id}")
                return added_count > 0
                
        except Exception as e:
            logger.error(f"Failed to generate embeddings for document {document_id}: {e}")
            return False
    
    async def search_similar_chunks(
        self, 
        query: str, 
        limit: int = 10,
        similarity_threshold: float = 0.7,
        customer_id: Optional[str] = None,
        company_hr_dataset: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
        document_ids: Optional[List[int]] = None
    ) -> List[DocumentSearchResult]:
        """Search for similar chunks using vector similarity
        
        Args:
            query: Search query text
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            customer_id: DEPRECATED - Filter by customer_id (use company_hr_dataset instead)
            company_hr_dataset: Filter by company (preferred over customer_id)
            source_ids: Filter by source IDs
            document_ids: Filter by specific document IDs
        """
        
        try:
            # Ensure service is initialized (loads embedding model and index)
            await self._ensure_initialized()
            
            if not self.index or self.index.ntotal == 0:
                logger.warning("FAISS index is empty")
                return []
            
            # Generate query embedding
            query_embedding = await self.generate_embedding(query)
            
            # Search in FAISS index
            # Search for more results than needed to allow for filtering
            search_limit = min(limit * 3, self.index.ntotal)
            similarities, indices = self.index.search(
                query_embedding.reshape(1, -1), 
                search_limit
            )
            
            # Get chunk IDs from indices
            chunk_ids = []
            similarity_scores = []
            
            for i, idx in enumerate(indices[0]):
                if idx in self.chunk_id_mapping:
                    similarity_score = float(similarities[0][i])
                    if similarity_score >= similarity_threshold:
                        chunk_ids.append(self.chunk_id_mapping[idx])
                        similarity_scores.append(similarity_score)
            
            if not chunk_ids:
                return []
            
            # Get chunk details from database
            results = await self._get_chunk_details(
                chunk_ids, similarity_scores, customer_id, company_hr_dataset, source_ids, document_ids
            )
            
            # Sort by similarity and limit results
            results.sort(key=lambda x: x.similarity_score, reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search similar chunks: {e}")
            return []
    
    async def _get_chunk_details(
        self,
        chunk_ids: List[str],
        similarity_scores: List[float],
        customer_id: Optional[str] = None,
        company_hr_dataset: Optional[str] = None,
        source_ids: Optional[List[str]] = None,
        document_ids: Optional[List[int]] = None
    ) -> List[DocumentSearchResult]:
        """Get detailed information for chunks from database
        
        Args:
            chunk_ids: List of chunk IDs from FAISS index
            similarity_scores: Corresponding similarity scores
            customer_id: DEPRECATED - Filter by customer_id (use company_hr_dataset instead)
            company_hr_dataset: Filter by company (preferred over customer_id)
            source_ids: Filter by source IDs
            document_ids: Filter by specific document IDs
        """
        
        results = []
        
        try:
            with self.get_db_session() as db:
                # Build query
                query = db.query(DocumentChunk, Document).join(
                    Document, DocumentChunk.document_id == Document.id
                ).filter(DocumentChunk.chunk_id.in_(chunk_ids))

                # Apply filters - prefer company_hr_dataset over customer_id
                if company_hr_dataset:
                    query = query.filter(Document.company_hr_dataset == company_hr_dataset)
                elif customer_id:
                    # Fallback to customer_id for backward compatibility
                    query = query.filter(Document.customer_id == customer_id)

                if source_ids:
                    query = query.filter(Document.source_id.in_(source_ids))

                if document_ids:
                    query = query.filter(Document.id.in_(document_ids))

                # Execute query
                chunk_docs = query.all()

                # Create similarity score mapping
                score_map = dict(zip(chunk_ids, similarity_scores))

                # Build results
                for chunk, document in chunk_docs:
                    similarity_score = score_map.get(chunk.chunk_id, 0.0)

                    result = DocumentSearchResult(
                        chunk_id=chunk.chunk_id,
                        document_id=document.id,
                        document_filename=document.original_filename,
                        text=chunk.text,
                        similarity_score=similarity_score,
                        section_title=chunk.section_title,
                        qa_questions=chunk.qa_questions,
                        qa_answers=chunk.qa_answers,
                        metadata=chunk.chunk_metadata or {}  # Use chunk_metadata field
                    )
                    results.append(result)
                
        except Exception as e:
            logger.error(f"Failed to get chunk details: {e}")
        
        return results
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the FAISS index"""
        await self._ensure_initialized()
        return {
            'total_vectors': self.index.ntotal if self.index else 0,
            'embedding_dimension': self.embedding_dimension,
            'embedding_model': self.embedding_model_name,
            'index_type': type(self.index).__name__ if self.index else None,
            'index_file_exists': self.index_file.exists(),
            'mapping_file_exists': self.mapping_file.exists()
        }
    
    async def rebuild_index(self, customer_id: Optional[str] = None) -> Dict[str, Any]:
        """Rebuild the FAISS index from database chunks"""
        try:
            logger.info("Starting FAISS index rebuild")
            
            # Ensure service is initialized (loads embedding model)
            await self._ensure_initialized()
            
            # Create new index
            self._create_new_index()
            
            with self.get_db_session() as db:
                # Get all chunks
                query = db.query(DocumentChunk, Document).join(
                    Document, DocumentChunk.document_id == Document.id
                )

                if customer_id:
                    query = query.filter(Document.customer_id == customer_id)

                chunk_docs = query.all()

                if not chunk_docs:
                    logger.warning("No chunks found for index rebuild")
                    return {'success': False, 'message': 'No chunks found'}

                # Prepare chunk data
                chunk_data = [(chunk.chunk_id, chunk.text) for chunk, _ in chunk_docs]

                # Add to index in batches
                batch_size = 1000
                total_added = 0

                for i in range(0, len(chunk_data), batch_size):
                    batch = chunk_data[i:i + batch_size]
                    added = await self.add_chunks_to_index_batch(batch)
                    total_added += added

                    logger.info(f"Processed {i + len(batch)}/{len(chunk_data)} chunks")

                # Save final index
                await self._save_index()

                logger.info(f"Index rebuild completed: {total_added} chunks indexed")

                return {
                    'success': True,
                    'total_chunks': len(chunk_data),
                    'indexed_chunks': total_added,
                    'index_size': self.index.ntotal
                }
                
        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")
            return {'success': False, 'error': str(e)}
    
    async def remove_document_from_index(self, document_id: int) -> bool:
        """Remove all chunks of a document from the index"""
        # Note: FAISS doesn't support efficient deletion
        # For now, we'll mark chunks as deleted and rebuild index periodically
        # TODO: Implement more efficient deletion strategy
        
        try:
            with self.get_db_session() as db:
                chunks = db.query(DocumentChunk).filter(
                    DocumentChunk.document_id == document_id
                ).all()

                chunk_ids = [chunk.chunk_id for chunk in chunks]

                # Remove from mapping (index positions will be invalid after rebuild)
                positions_to_remove = [
                    pos for pos, chunk_id in self.chunk_id_mapping.items()
                    if chunk_id in chunk_ids
                ]

                for pos in positions_to_remove:
                    del self.chunk_id_mapping[pos]

                logger.info(f"Marked {len(chunk_ids)} chunks for removal from index")
                return True
                
        except Exception as e:
            logger.error(f"Failed to remove document {document_id} from index: {e}")
            return False
