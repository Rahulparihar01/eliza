# RAG Context Retriever Component

## RAG-Enhanced Context Retrieval for Task Enrichment

```python
# From RAG context retrieval patterns - EXAMPLE
from typing import Dict, List, Any, Optional, Tuple
import asyncio
import json
from datetime import datetime
import numpy as np
from dataclasses import dataclass, field

@dataclass
class RAGRetrievalResult:
    """Result from RAG context retrieval"""
    relevant_chunks: List[Dict[str, Any]]
    relevant_qa_pairs: List[Dict[str, Any]]
    context_summary: str
    retrieval_metadata: Dict[str, Any]
    confidence_score: float
    sources_used: List[str]

@dataclass
class RAGQuery:
    """Structured query for RAG retrieval"""
    primary_query: str
    sub_queries: List[str]
    entity_queries: List[str]
    context_queries: List[str]
    intent_type: str
    user_department: str
    required_sources: List[str] = field(default_factory=list)
    max_chunks: int = 10
    similarity_threshold: float = 0.7

class RAGContextRetriever:
    """Retrieves relevant context from RAG indexes to enrich user tasks"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = self._initialize_logger()
        
        # Initialize RAG components (from existing QA RAG system)
        self.vector_index = self._initialize_vector_index()
        self.qa_database = self._initialize_qa_database()
        self.embedding_client = self._initialize_embedding_client()
        
        # Query generation strategies
        self.query_strategies = {
            'question_answering': self._generate_qa_queries,
            'data_analysis': self._generate_analysis_queries,
            'report_generation': self._generate_report_queries,
            'recommendation': self._generate_recommendation_queries,
            'comparison': self._generate_comparison_queries,
            'summarization': self._generate_summarization_queries
        }
        
        # Source priority mapping
        self.source_priorities = {
            'hr': ['hr_documents', 'employee_data', 'policy_documents'],
            'finance': ['financial_reports', 'budget_data', 'expense_data'],
            'sales': ['crm_data', 'sales_reports', 'customer_data'],
            'marketing': ['campaign_data', 'market_research', 'customer_insights'],
            'operations': ['process_documentation', 'operational_metrics', 'vendor_data'],
            'executive': ['strategic_plans', 'board_reports', 'executive_dashboards']
        }
    
    def _initialize_logger(self):
        """Initialize specialized logger for RAG retrieval"""
        from LOGGING_SPECIFICATION import EnhancedLogger, LogCategory
        return EnhancedLogger("rag_context_retriever", self.config.get('logging', {}))
    
    def _initialize_vector_index(self):
        """Initialize connection to vector index"""
        # This would connect to your existing QA RAG vector index
        # Implementation depends on your vector database (FAISS, Pinecone, Weaviate, etc.)
        from your_rag_system import VectorIndex  # Placeholder
        return VectorIndex(self.config.get('vector_index_config', {}))
    
    def _initialize_qa_database(self):
        """Initialize connection to QA pairs database"""
        # This would connect to your QA RAG structured database
        from your_rag_system import QADatabase  # Placeholder
        return QADatabase(self.config.get('qa_database_config', {}))
    
    def _initialize_embedding_client(self):
        """Initialize embedding client for query encoding"""
        import openai
        return openai.OpenAI(
            api_key=self.config.get('api_key'),
            base_url=self.config.get('api_base_url', 'http://localhost:5001/inf')
        )
    
    async def retrieve_relevant_context(
        self,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> RAGRetrievalResult:
        """Retrieve relevant context from RAG indexes"""
        
        retrieval_start_time = asyncio.get_event_loop().time()
        
        try:
            # Step 1: Generate structured queries based on task analysis
            rag_queries = await self._generate_rag_queries(user_input, task_analysis, user_context)
            
            # Step 2: Execute multi-faceted retrieval
            retrieval_results = await self._execute_multi_faceted_retrieval(rag_queries, user_context)
            
            # Step 3: Rank and filter results
            ranked_results = await self._rank_and_filter_results(
                retrieval_results, task_analysis, user_context
            )
            
            # Step 4: Generate context summary
            context_summary = await self._generate_context_summary(
                ranked_results, task_analysis, user_input
            )
            
            # Step 5: Calculate confidence and compile metadata
            confidence_score = self._calculate_retrieval_confidence(ranked_results, rag_queries)
            
            retrieval_time = asyncio.get_event_loop().time() - retrieval_start_time
            
            # Log retrieval success
            self.logger.info(
                f"Retrieved {len(ranked_results['chunks'])} chunks and {len(ranked_results['qa_pairs'])} Q&A pairs",
                operation="rag_retrieval",
                metadata={
                    "retrieval_time_ms": retrieval_time * 1000,
                    "confidence_score": confidence_score,
                    "sources_accessed": len(ranked_results.get('sources_used', [])),
                    "query_count": len(rag_queries.sub_queries) + len(rag_queries.entity_queries)
                },
                user_message=f"Found relevant information from {len(ranked_results.get('sources_used', []))} sources"
            )
            
            return RAGRetrievalResult(
                relevant_chunks=ranked_results['chunks'],
                relevant_qa_pairs=ranked_results['qa_pairs'],
                context_summary=context_summary,
                retrieval_metadata={
                    'queries_executed': len(rag_queries.sub_queries) + len(rag_queries.entity_queries),
                    'sources_searched': ranked_results.get('sources_searched', []),
                    'retrieval_time_ms': retrieval_time * 1000,
                    'total_candidates': ranked_results.get('total_candidates', 0),
                    'filtering_applied': ranked_results.get('filtering_applied', [])
                },
                confidence_score=confidence_score,
                sources_used=ranked_results.get('sources_used', [])
            )
            
        except Exception as e:
            self.logger.error(
                f"RAG context retrieval failed: {e}",
                operation="rag_retrieval",
                exception=e,
                user_message="Unable to retrieve relevant context from knowledge base"
            )
            
            # Return empty result on failure
            return RAGRetrievalResult(
                relevant_chunks=[],
                relevant_qa_pairs=[],
                context_summary="",
                retrieval_metadata={'error': str(e)},
                confidence_score=0.0,
                sources_used=[]
            )
    
    async def _generate_rag_queries(
        self,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> RAGQuery:
        """Generate structured queries for RAG retrieval"""
        
        # Get intent-specific query strategy
        strategy_func = self.query_strategies.get(
            task_analysis.intent_type.value,
            self.query_strategies['question_answering']
        )
        
        # Generate base queries
        base_queries = await strategy_func(user_input, task_analysis, user_context)
        
        # Add entity-specific queries
        entity_queries = []
        for entity in task_analysis.entities_mentioned:
            entity_queries.extend([
                f"Information about {entity}",
                f"{entity} in {user_context.department}",
                f"Recent updates regarding {entity}"
            ])
        
        # Add context-specific queries
        context_queries = [
            f"{user_context.department} department information",
            f"Current {user_context.department} priorities",
            f"Recent {user_context.department} performance data"
        ]
        
        # Determine required sources based on user department and intent
        required_sources = self._determine_required_sources(task_analysis, user_context)
        
        return RAGQuery(
            primary_query=user_input,
            sub_queries=base_queries,
            entity_queries=entity_queries,
            context_queries=context_queries,
            intent_type=task_analysis.intent_type.value,
            user_department=user_context.department,
            required_sources=required_sources,
            max_chunks=self.config.get('max_chunks_per_query', 10),
            similarity_threshold=self.config.get('similarity_threshold', 0.7)
        )
    
    async def _generate_qa_queries(
        self,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[str]:
        """Generate queries for question-answering tasks"""
        
        queries = [
            user_input,  # Original question
            f"What is {task_analysis.main_objective}",
            f"How to {task_analysis.main_objective}",
            f"Information about {task_analysis.main_objective}"
        ]
        
        # Add sub-objective queries
        for sub_obj in task_analysis.sub_objectives:
            queries.append(f"Details about {sub_obj}")
        
        return queries
    
    async def _generate_analysis_queries(
        self,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[str]:
        """Generate queries for data analysis tasks"""
        
        queries = [
            user_input,
            f"{user_context.department} performance data",
            f"{user_context.department} metrics and KPIs",
            f"Historical {user_context.department} trends",
            f"Benchmarks for {user_context.department}",
            f"Analysis methodology for {task_analysis.main_objective}"
        ]
        
        # Add entity-specific analysis queries
        for entity in task_analysis.entities_mentioned:
            queries.extend([
                f"{entity} performance analysis",
                f"{entity} trends and patterns",
                f"Factors affecting {entity}"
            ])
        
        return queries
    
    async def _generate_report_queries(
        self,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[str]:
        """Generate queries for report generation tasks"""
        
        queries = [
            user_input,
            f"{user_context.department} current status",
            f"{user_context.department} recent achievements",
            f"{user_context.department} challenges and issues",
            f"{user_context.department} future plans",
            f"Executive summary information for {user_context.department}",
            f"Key metrics for {user_context.department} reporting"
        ]
        
        return queries
    
    async def _generate_recommendation_queries(
        self,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[str]:
        """Generate queries for recommendation tasks"""
        
        queries = [
            user_input,
            f"Best practices for {task_analysis.main_objective}",
            f"Success factors for {task_analysis.main_objective}",
            f"Common challenges in {task_analysis.main_objective}",
            f"Industry standards for {task_analysis.main_objective}",
            f"Case studies related to {task_analysis.main_objective}",
            f"{user_context.department} strategic options"
        ]
        
        return queries
    
    def _determine_required_sources(
        self,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[str]:
        """Determine which data sources are most relevant"""
        
        # Start with department-specific sources
        department_sources = self.source_priorities.get(
            user_context.department.lower(), 
            ['general_documents']
        )
        
        # Add intent-specific sources
        intent_sources = {
            'data_analysis': ['analytics_data', 'performance_metrics', 'dashboard_data'],
            'report_generation': ['official_reports', 'executive_documents', 'quarterly_data'],
            'recommendation': ['best_practices', 'case_studies', 'strategic_documents'],
            'question_answering': ['faq_documents', 'knowledge_base', 'documentation']
        }
        
        intent_specific = intent_sources.get(task_analysis.intent_type.value, [])
        
        # Add user role-specific sources
        role_sources = {
            'executive': ['board_reports', 'strategic_plans', 'executive_dashboards'],
            'manager': ['team_reports', 'departmental_data', 'management_guides'],
            'employee': ['procedures', 'training_materials', 'employee_resources']
        }
        
        role_specific = role_sources.get(user_context.user_role, [])
        
        # Combine and deduplicate
        all_sources = department_sources + intent_specific + role_specific
        return list(set(all_sources))
    
    async def _execute_multi_faceted_retrieval(
        self,
        rag_queries: RAGQuery,
        user_context: 'UserContext'
    ) -> Dict[str, Any]:
        """Execute retrieval across multiple query facets"""
        
        all_chunks = []
        all_qa_pairs = []
        sources_searched = set()
        total_candidates = 0
        
        # Combine all queries for comprehensive retrieval
        all_queries = (
            [rag_queries.primary_query] + 
            rag_queries.sub_queries + 
            rag_queries.entity_queries + 
            rag_queries.context_queries
        )
        
        # Execute retrieval for each query
        retrieval_tasks = []
        for query in all_queries:
            task = self._execute_single_query_retrieval(
                query, rag_queries, user_context
            )
            retrieval_tasks.append(task)
        
        # Execute all retrievals concurrently
        retrieval_results = await asyncio.gather(*retrieval_tasks, return_exceptions=True)
        
        # Aggregate results
        for result in retrieval_results:
            if isinstance(result, Exception):
                self.logger.warning(f"Query retrieval failed: {result}")
                continue
            
            if result:
                all_chunks.extend(result.get('chunks', []))
                all_qa_pairs.extend(result.get('qa_pairs', []))
                sources_searched.update(result.get('sources', []))
                total_candidates += result.get('candidates', 0)
        
        return {
            'chunks': all_chunks,
            'qa_pairs': all_qa_pairs,
            'sources_searched': list(sources_searched),
            'total_candidates': total_candidates
        }
    
    async def _execute_single_query_retrieval(
        self,
        query: str,
        rag_queries: RAGQuery,
        user_context: 'UserContext'
    ) -> Dict[str, Any]:
        """Execute retrieval for a single query"""
        
        try:
            # Generate query embedding
            query_embedding = await self._generate_query_embedding(query)
            
            # Search vector index
            vector_results = await self.vector_index.similarity_search(
                query_embedding,
                k=rag_queries.max_chunks,
                threshold=rag_queries.similarity_threshold,
                filters={
                    'user_department': user_context.department,
                    'user_role_access': user_context.user_role,
                    'sources': rag_queries.required_sources
                }
            )
            
            # Search QA pairs database
            qa_results = await self.qa_database.search_qa_pairs(
                query,
                limit=rag_queries.max_chunks // 2,  # Fewer Q&A pairs than chunks
                department_filter=user_context.department
            )
            
            return {
                'chunks': vector_results.get('chunks', []),
                'qa_pairs': qa_results.get('qa_pairs', []),
                'sources': vector_results.get('sources', []),
                'candidates': vector_results.get('total_found', 0)
            }
            
        except Exception as e:
            self.logger.warning(f"Single query retrieval failed for '{query}': {e}")
            return {'chunks': [], 'qa_pairs': [], 'sources': [], 'candidates': 0}
    
    async def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for query"""
        
        try:
            response = await self.embedding_client.embeddings.create(
                model="sentence-transformers/all-MiniLM-L6-v2",  # Match your QA RAG model
                input=query
            )
            return response.data[0].embedding
            
        except Exception as e:
            self.logger.error(f"Query embedding generation failed: {e}")
            # Return zero embedding as fallback
            return [0.0] * 384  # Default embedding dimension
    
    async def _rank_and_filter_results(
        self,
        retrieval_results: Dict[str, Any],
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> Dict[str, Any]:
        """Rank and filter retrieval results for relevance"""
        
        chunks = retrieval_results.get('chunks', [])
        qa_pairs = retrieval_results.get('qa_pairs', [])
        
        # Deduplicate chunks by content similarity
        unique_chunks = self._deduplicate_chunks(chunks)
        
        # Deduplicate Q&A pairs
        unique_qa_pairs = self._deduplicate_qa_pairs(qa_pairs)
        
        # Score and rank chunks
        scored_chunks = await self._score_chunks_for_relevance(
            unique_chunks, task_analysis, user_context
        )
        
        # Score and rank Q&A pairs
        scored_qa_pairs = await self._score_qa_pairs_for_relevance(
            unique_qa_pairs, task_analysis, user_context
        )
        
        # Apply final filtering and limits
        max_chunks = self.config.get('max_final_chunks', 8)
        max_qa_pairs = self.config.get('max_final_qa_pairs', 5)
        
        final_chunks = scored_chunks[:max_chunks]
        final_qa_pairs = scored_qa_pairs[:max_qa_pairs]
        
        # Extract sources used
        sources_used = set()
        for chunk in final_chunks:
            if 'source_id' in chunk.get('metadata', {}):
                sources_used.add(chunk['metadata']['source_id'])
        
        for qa_pair in final_qa_pairs:
            if 'source_id' in qa_pair.get('metadata', {}):
                sources_used.add(qa_pair['metadata']['source_id'])
        
        return {
            'chunks': final_chunks,
            'qa_pairs': final_qa_pairs,
            'sources_used': list(sources_used),
            'filtering_applied': [
                'deduplication',
                'relevance_scoring',
                'quantity_limiting'
            ]
        }
    
    def _deduplicate_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate chunks based on content similarity"""
        
        if not chunks:
            return []
        
        unique_chunks = []
        seen_content_hashes = set()
        
        for chunk in chunks:
            # Create content hash for deduplication
            content = chunk.get('text', '') or chunk.get('content', '')
            content_hash = hash(content[:200])  # Use first 200 chars for hash
            
            if content_hash not in seen_content_hashes:
                unique_chunks.append(chunk)
                seen_content_hashes.add(content_hash)
        
        return unique_chunks
    
    def _deduplicate_qa_pairs(self, qa_pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate Q&A pairs"""
        
        if not qa_pairs:
            return []
        
        unique_pairs = []
        seen_questions = set()
        
        for qa_pair in qa_pairs:
            question = qa_pair.get('question', '').lower().strip()
            
            if question and question not in seen_questions:
                unique_pairs.append(qa_pair)
                seen_questions.add(question)
        
        return unique_pairs
    
    async def _score_chunks_for_relevance(
        self,
        chunks: List[Dict[str, Any]],
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[Dict[str, Any]]:
        """Score chunks for relevance and return sorted list"""
        
        scored_chunks = []
        
        for chunk in chunks:
            score = 0.0
            
            # Base similarity score (from vector search)
            base_score = chunk.get('similarity_score', 0.5)
            score += base_score * 0.4
            
            # Department relevance
            chunk_metadata = chunk.get('metadata', {})
            if chunk_metadata.get('department', '').lower() == user_context.department.lower():
                score += 0.2
            
            # Source priority
            source_id = chunk_metadata.get('source_id', '')
            department_sources = self.source_priorities.get(user_context.department.lower(), [])
            if source_id in department_sources:
                priority_index = department_sources.index(source_id)
                score += 0.15 * (1 - priority_index / len(department_sources))
            
            # Recency bonus
            if chunk_metadata.get('created_date'):
                # Add recency scoring logic here
                score += 0.1  # Placeholder
            
            # Content quality (if available from QA RAG processing)
            if 'quality_score' in chunk_metadata:
                score += chunk_metadata['quality_score'] * 0.15
            
            chunk['relevance_score'] = score
            scored_chunks.append(chunk)
        
        # Sort by relevance score (descending)
        scored_chunks.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return scored_chunks
    
    async def _score_qa_pairs_for_relevance(
        self,
        qa_pairs: List[Dict[str, Any]],
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[Dict[str, Any]]:
        """Score Q&A pairs for relevance and return sorted list"""
        
        scored_pairs = []
        
        for qa_pair in qa_pairs:
            score = 0.0
            
            # Base similarity score
            base_score = qa_pair.get('similarity_score', 0.5)
            score += base_score * 0.5
            
            # Question-intent alignment
            question = qa_pair.get('question', '').lower()
            if task_analysis.intent_type.value == 'question_answering':
                # Boost Q&A pairs for question-answering tasks
                score += 0.2
            
            # Entity mention bonus
            for entity in task_analysis.entities_mentioned:
                if entity.lower() in question or entity.lower() in qa_pair.get('answer', '').lower():
                    score += 0.15
                    break
            
            # Department relevance
            qa_metadata = qa_pair.get('metadata', {})
            if qa_metadata.get('department', '').lower() == user_context.department.lower():
                score += 0.15
            
            qa_pair['relevance_score'] = score
            scored_pairs.append(qa_pair)
        
        # Sort by relevance score (descending)
        scored_pairs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return scored_pairs
    
    async def _generate_context_summary(
        self,
        ranked_results: Dict[str, Any],
        task_analysis: 'TaskAnalysis',
        user_input: str
    ) -> str:
        """Generate a summary of the retrieved context"""
        
        chunks = ranked_results.get('chunks', [])
        qa_pairs = ranked_results.get('qa_pairs', [])
        
        if not chunks and not qa_pairs:
            return "No relevant context found in knowledge base."
        
        # Prepare context for summarization
        context_pieces = []
        
        # Add top chunks
        for chunk in chunks[:3]:  # Top 3 most relevant chunks
            content = chunk.get('text', '') or chunk.get('content', '')
            source = chunk.get('metadata', {}).get('source_id', 'Unknown')
            context_pieces.append(f"From {source}: {content[:200]}...")
        
        # Add top Q&A pairs
        for qa_pair in qa_pairs[:2]:  # Top 2 most relevant Q&A pairs
            question = qa_pair.get('question', '')
            answer = qa_pair.get('answer', '')
            context_pieces.append(f"Q: {question}\nA: {answer[:150]}...")
        
        # Generate summary using LLM
        summary_prompt = f"""
        Based on the following retrieved context, provide a concise summary that would be helpful for answering this user request: "{user_input}"

        Retrieved Context:
        {chr(10).join(context_pieces)}

        Provide a summary that:
        1. Highlights the most relevant information for the user's request
        2. Identifies key themes or patterns
        3. Notes any gaps or limitations in the available information
        4. Is concise but informative (2-3 sentences)
        """
        
        try:
            response = await self.embedding_client.chat.completions.create(
                model=self.config.get('summary_model', 'meta-llama/Llama-3.1-8B-Instruct'),
                messages=[
                    {"role": "system", "content": "You are an expert at summarizing retrieved context for task enrichment."},
                    {"role": "user", "content": summary_prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.warning(f"Context summary generation failed: {e}")
            
            # Fallback summary
            chunk_count = len(chunks)
            qa_count = len(qa_pairs)
            sources_count = len(ranked_results.get('sources_used', []))
            
            return f"Retrieved {chunk_count} relevant documents and {qa_count} Q&A pairs from {sources_count} sources related to your request."
    
    def _calculate_retrieval_confidence(
        self,
        ranked_results: Dict[str, Any],
        rag_queries: RAGQuery
    ) -> float:
        """Calculate confidence score for retrieval results"""
        
        chunks = ranked_results.get('chunks', [])
        qa_pairs = ranked_results.get('qa_pairs', [])
        
        if not chunks and not qa_pairs:
            return 0.0
        
        confidence_factors = []
        
        # Factor 1: Result quantity (more results = higher confidence, up to a point)
        total_results = len(chunks) + len(qa_pairs)
        quantity_score = min(total_results / 10.0, 1.0)  # Cap at 10 results
        confidence_factors.append(quantity_score * 0.3)
        
        # Factor 2: Average relevance scores
        all_scores = []
        for chunk in chunks:
            all_scores.append(chunk.get('relevance_score', 0.5))
        for qa_pair in qa_pairs:
            all_scores.append(qa_pair.get('relevance_score', 0.5))
        
        if all_scores:
            avg_relevance = sum(all_scores) / len(all_scores)
            confidence_factors.append(avg_relevance * 0.4)
        
        # Factor 3: Source diversity
        sources_used = len(ranked_results.get('sources_used', []))
        source_diversity = min(sources_used / 5.0, 1.0)  # Cap at 5 sources
        confidence_factors.append(source_diversity * 0.2)
        
        # Factor 4: Query coverage (how many queries returned results)
        total_queries = len(rag_queries.sub_queries) + len(rag_queries.entity_queries)
        if total_queries > 0:
            # Estimate query coverage (simplified)
            query_coverage = min(total_results / total_queries, 1.0)
            confidence_factors.append(query_coverage * 0.1)
        
        return sum(confidence_factors)
```

## Integration with Context Enricher

```python
# Update to ContextEnricher to incorporate RAG context - EXAMPLE

class ContextEnricher:
    """Enhanced context enricher that incorporates RAG retrieval results"""
    
    async def enrich_context(
        self, 
        user_input: str, 
        task_analysis: TaskAnalysis, 
        user_context: UserContext,
        rag_context: RAGRetrievalResult = None  # New parameter
    ) -> Dict[str, Any]:
        """Enrich task with comprehensive contextual information including RAG context"""
        
        # Get base enriched context (existing functionality)
        enriched_context = await self._get_base_enriched_context(
            user_input, task_analysis, user_context
        )
        
        # Add RAG-retrieved context
        if rag_context and (rag_context.relevant_chunks or rag_context.relevant_qa_pairs):
            enriched_context['rag_context'] = {
                'relevant_information': self._format_rag_context(rag_context),
                'context_summary': rag_context.context_summary,
                'confidence_score': rag_context.confidence_score,
                'sources_consulted': rag_context.sources_used,
                'retrieval_metadata': rag_context.retrieval_metadata
            }
            
            # Enhance other context areas with RAG insights
            enriched_context = self._enhance_context_with_rag_insights(
                enriched_context, rag_context, task_analysis
            )
        else:
            enriched_context['rag_context'] = {
                'relevant_information': "No specific relevant information found in knowledge base.",
                'context_summary': "Limited context available from knowledge base.",
                'confidence_score': 0.0,
                'sources_consulted': [],
                'retrieval_metadata': {}
            }
        
        return enriched_context
    
    def _format_rag_context(self, rag_context: RAGRetrievalResult) -> Dict[str, Any]:
        """Format RAG context for inclusion in enriched context"""
        
        formatted_context = {
            'document_excerpts': [],
            'relevant_qa_pairs': [],
            'key_insights': []
        }
        
        # Format document chunks
        for chunk in rag_context.relevant_chunks[:5]:  # Top 5 chunks
            formatted_context['document_excerpts'].append({
                'content': chunk.get('text', chunk.get('content', ''))[:300] + "...",
                'source': chunk.get('metadata', {}).get('source_id', 'Unknown'),
                'relevance_score': chunk.get('relevance_score', 0.0),
                'document_type': chunk.get('metadata', {}).get('document_type', 'Document')
            })
        
        # Format Q&A pairs
        for qa_pair in rag_context.relevant_qa_pairs[:3]:  # Top 3 Q&A pairs
            formatted_context['relevant_qa_pairs'].append({
                'question': qa_pair.get('question', ''),
                'answer': qa_pair.get('answer', ''),
                'source': qa_pair.get('metadata', {}).get('source_id', 'Unknown'),
                'relevance_score': qa_pair.get('relevance_score', 0.0)
            })
        
        # Extract key insights (could be enhanced with LLM analysis)
        if rag_context.context_summary:
            formatted_context['key_insights'].append(rag_context.context_summary)
        
        return formatted_context
    
    def _enhance_context_with_rag_insights(
        self,
        enriched_context: Dict[str, Any],
        rag_context: RAGRetrievalResult,
        task_analysis: TaskAnalysis
    ) -> Dict[str, Any]:
        """Enhance existing context areas with insights from RAG retrieval"""
        
        # Enhance domain context with RAG findings
        domain_context = enriched_context.get('domain_context', {})
        
        # Add specific domain knowledge found in RAG
        rag_domain_insights = []
        for chunk in rag_context.relevant_chunks:
            chunk_metadata = chunk.get('metadata', {})
            if chunk_metadata.get('domain') or chunk_metadata.get('category'):
                insight = {
                    'domain': chunk_metadata.get('domain', 'general'),
                    'category': chunk_metadata.get('category', 'information'),
                    'insight': chunk.get('text', chunk.get('content', ''))[:150] + "..."
                }
                rag_domain_insights.append(insight)
        
        domain_context['rag_insights'] = rag_domain_insights[:3]  # Top 3 insights
        enriched_context['domain_context'] = domain_context
        
        # Enhance data availability with RAG source information
        data_availability = enriched_context.get('data_availability', {})
        data_availability['rag_sources_available'] = rag_context.sources_used
        data_availability['rag_confidence'] = rag_context.confidence_score
        enriched_context['data_availability'] = data_availability
        
        return enriched_context
```

This RAG Context Retriever component provides:

1. **Multi-faceted Query Generation**: Creates diverse queries based on intent, entities, and context
2. **Comprehensive Retrieval**: Searches both vector indexes and structured Q&A databases
3. **Intelligent Ranking**: Scores results based on relevance, recency, and source priority
4. **Context Summarization**: Generates concise summaries of retrieved information
5. **Confidence Assessment**: Provides confidence scores for retrieval quality
6. **Integration Ready**: Seamlessly integrates with the existing enrichment pipeline

The system now leverages your QA RAG indexes to provide rich, relevant context that dramatically improves prompt quality and processing agent performance.
