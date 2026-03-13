"""
Custom CrewAI Tool for Document Search

Provides CrewAI agents with semantic search capabilities across document embeddings.
"""
from typing import Optional
from crewai.tools import BaseTool
from pydantic import Field

from src.services.vector_service import VectorService
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, component="crewai.tools")


class DocumentSearchTool(BaseTool):
    """
    CrewAI tool for searching document embeddings via FAISS vector index.
    
    Performs semantic search across all ingested documents to find
    relevant context for answering questions.
    
    THIS TOOL SHOULD ALWAYS BE USED FOR EVERY QUERY to ensure
    comprehensive context retrieval from the knowledge base.
    """
    
    name: str = "Document Semantic Search"
    description: str = """
    ALWAYS USE THIS TOOL to search company documents for relevant information.
    
    Performs semantic search across all ingested documents using FAISS vector similarity.
    Returns the most relevant document chunks based on the query.
    
    Input format: Plain text search query (e.g., "What are our hiring policies?")
    
    This tool provides context from:
    - Company policies and procedures
    - Technical documentation
    - Training materials
    - Meeting notes and reports
    - Any other uploaded documents
    
    Returns: JSON string with:
    - Top matching document chunks
    - Relevance scores
    - Document metadata (filename, upload date, etc.)
    
    IMPORTANT: Use this tool for EVERY query to ensure comprehensive answers.
    """
    
    customer_id: str = Field(description="Customer ID for data isolation")
    company_hr_dataset: Optional[str] = Field(None, description="Target company for document index (defaults to customer_id)")
    limit: int = Field(default=10, description="Max number of results to return")
    similarity_threshold: float = Field(default=0.7, description="Minimum similarity score (0-1)")
    
    def _get_vector_service(self) -> VectorService:
        """Lazy initialization of vector service"""
        if not hasattr(self, '_vector_service_instance'):
            # Use company-specific index if specified
            company = self.company_hr_dataset or self.customer_id
            self._vector_service_instance = VectorService(company_hr_dataset=company)
        return self._vector_service_instance
    
    def _run(self, search_query: str) -> str:
        """
        Execute semantic search across document embeddings.
        
        Args:
            search_query: Natural language search query
            
        Returns:
            JSON string with search results
        """
        import json
        import asyncio
        
        try:
            # Initialize service lazily
            vector_service = self._get_vector_service()
            logger.info(
                "document_search_tool_query",
                category=LogCategory.BUSINESS,
                metadata={
                    "query": search_query[:100],  # Log first 100 chars
                    "company_hr_dataset": self.company_hr_dataset or self.customer_id,
                    "limit": self.limit,
                    "threshold": self.similarity_threshold
                }
            )
            
            # Run async search in sync context
            # Use ThreadPoolExecutor to avoid event loop conflicts
            from concurrent.futures import ThreadPoolExecutor
            
            def run_async_search():
                """Run async search in a new thread with its own event loop"""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Use company_hr_dataset for filtering (not customer_id)
                    # The FAISS index is already company-specific
                    company = self.company_hr_dataset or self.customer_id
                    return loop.run_until_complete(
                        vector_service.search_similar_chunks(
                            query=search_query,
                            company_hr_dataset=company,
                            limit=self.limit,
                            similarity_threshold=self.similarity_threshold
                        )
                    )
                finally:
                    loop.close()
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_async_search)
                results = future.result(timeout=30)  # 30 second timeout
            
            logger.info(
                "document_search_tool_complete",
                category=LogCategory.BUSINESS,
                metadata={
                    "results_count": len(results),
                    "company_hr_dataset": self.company_hr_dataset or self.customer_id
                }
            )
            
            # Format results for LLM consumption
            # Results are DocumentSearchResult Pydantic models, not dicts
            formatted_results = {
                "query": search_query,
                "results_count": len(results),
                "results": [
                    {
                        "document_id": r.document_id,
                        "document_name": r.document_filename,
                        "chunk_text": r.text,  # Full chunk text
                        "similarity_score": round(r.similarity_score, 3),
                        "section_title": r.section_title,
                        "metadata": r.metadata or {}
                    }
                    for r in results
                ],
                "search_metadata": {
                    "company_hr_dataset": self.company_hr_dataset or self.customer_id,
                    "limit": self.limit,
                    "threshold": self.similarity_threshold
                }
            }
            
            return json.dumps(formatted_results, default=str)
            
        except Exception as e:
            logger.error(
                "document_search_tool_error",
                exception=e,
                category=LogCategory.BUSINESS,
                metadata={
                    "query": search_query[:100],
                    "company_hr_dataset": self.company_hr_dataset or self.customer_id
                }
            )
            return json.dumps({
                "error": str(e),
                "query": search_query,
                "results_count": 0,
                "results": []
            })
