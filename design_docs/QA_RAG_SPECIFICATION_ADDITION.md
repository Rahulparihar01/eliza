# QA RAG (Question-Answer Retrieval Augmented Generation) Addition

## QA RAG Architecture Overview
*Extending patterns from [MEMORY_RAG_DEEP_DIVE.md](MEMORY_RAG_DEEP_DIVE.md) with Q&A generation*

The QA RAG system transforms documents into rich, queryable knowledge by generating contextual questions and answers for each chunk. This creates a more comprehensive index that can handle complex queries and provide detailed responses.

```python
# From QA RAG processing patterns - EXAMPLE
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import asyncio
import json
from datetime import datetime
import openai

@dataclass
class QARAGConfig:
    """Configuration for QA RAG processing"""
    enabled: bool = False
    questions_per_chunk: int = 3
    max_chunk_size_for_qa: int = 2048  # Skip QA generation for very large chunks
    min_chunk_size_for_qa: int = 200   # Skip QA generation for very small chunks
    
    # Model configuration
    qa_model: str = "meta-llama/Llama-3.1-8B-Instruct"
    api_base_url: str = "http://localhost:5001/inf"
    api_key: str = None
    
    # Quality thresholds
    min_question_length: int = 10
    max_question_length: int = 200
    min_answer_length: int = 20
    max_answer_length: int = 1000
    quality_threshold: float = 0.7
    
    # Domain-specific prompts
    domain_prompts: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    # Processing options
    batch_size: int = 5
    max_retries: int = 3
    timeout_seconds: int = 60

@dataclass
class QAChunk:
    """Enhanced chunk with Q&A pairs"""
    chunk_id: str
    original_text: str
    questions: List[str]
    answers: List[str]
    metadata: Dict[str, Any]
    qa_generation_metadata: Dict[str, Any]
    quality_score: float
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

class QARAGProcessor:
    """Processes chunks to generate Q&A pairs for enhanced indexing"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = QARAGConfig(**config)
        self.client = self._initialize_openai_client()
        self.domain_prompts = self._load_domain_prompts()
    
    def _initialize_openai_client(self):
        """Initialize OpenAI-compatible client"""
        return openai.OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.api_base_url
        )
    
    def _load_domain_prompts(self) -> Dict[str, Dict[str, str]]:
        """Load domain-specific prompts for different content types"""
        return {
            "hr": {
                "question_prompt": """
                Based on the following HR document content, generate {num_questions} high-quality questions that can be answered from this text.
                Focus on employee information, policies, procedures, benefits, and organizational structure.
                
                Content: {chunk_text}
                
                Generate questions that would be useful for HR professionals, managers, and employees.
                Return only the questions, one per line.
                """,
                "answer_prompt": """
                Based on the following HR document content, provide a comprehensive answer to the question.
                
                Content: {chunk_text}
                Question: {question}
                
                Provide a detailed, accurate answer based only on the information in the content.
                If the content doesn't fully answer the question, state what information is available.
                """
            },
            "financial": {
                "question_prompt": """
                Based on the following financial document content, generate {num_questions} high-quality questions that can be answered from this text.
                Focus on financial metrics, budgets, revenue, costs, performance indicators, and financial analysis.
                
                Content: {chunk_text}
                
                Generate questions that would be useful for financial analysts, executives, and stakeholders.
                Return only the questions, one per line.
                """,
                "answer_prompt": """
                Based on the following financial document content, provide a comprehensive answer to the question.
                
                Content: {chunk_text}
                Question: {question}
                
                Provide a detailed, accurate answer with specific numbers and financial details when available.
                If calculations or analysis are needed, show the reasoning based on the provided data.
                """
            },
            "technical": {
                "question_prompt": """
                Based on the following technical document content, generate {num_questions} high-quality questions that can be answered from this text.
                Focus on procedures, specifications, requirements, configurations, and technical implementation details.
                
                Content: {chunk_text}
                
                Generate questions that would be useful for technical professionals, developers, and system administrators.
                Return only the questions, one per line.
                """,
                "answer_prompt": """
                Based on the following technical document content, provide a comprehensive answer to the question.
                
                Content: {chunk_text}
                Question: {question}
                
                Provide a detailed, technical answer with specific steps, configurations, or code examples when available.
                Include any prerequisites, warnings, or best practices mentioned in the content.
                """
            },
            "general": {
                "question_prompt": """
                Based on the following document content, generate {num_questions} high-quality questions that can be answered from this text.
                Focus on the key information, main concepts, important details, and actionable insights.
                
                Content: {chunk_text}
                
                Generate questions that would help someone understand and use the information effectively.
                Return only the questions, one per line.
                """,
                "answer_prompt": """
                Based on the following document content, provide a comprehensive answer to the question.
                
                Content: {chunk_text}
                Question: {question}
                
                Provide a clear, detailed answer based only on the information in the content.
                Include relevant context and explain any important concepts or terms.
                """
            }
        }
    
    async def process_chunks_to_qa_rag(
        self, 
        chunks: List[Dict[str, Any]], 
        source_config: 'DataSource'
    ) -> List[QAChunk]:
        """Process chunks into QA RAG format with rich Q&A pairs"""
        
        if not source_config.qa_rag_enabled:
            # Return chunks without QA processing
            return [self._convert_to_simple_chunk(chunk) for chunk in chunks]
        
        qa_chunks = []
        
        # Filter chunks suitable for QA generation
        suitable_chunks = self._filter_chunks_for_qa(chunks)
        
        # Process chunks in batches
        batch_size = self.config.batch_size
        for i in range(0, len(suitable_chunks), batch_size):
            batch = suitable_chunks[i:i + batch_size]
            
            try:
                batch_qa_chunks = await self._process_chunk_batch(batch, source_config)
                qa_chunks.extend(batch_qa_chunks)
                
                # Log progress
                progress = (i + len(batch)) / len(suitable_chunks)
                print(f"QA RAG processing progress: {progress:.1%} ({len(qa_chunks)} chunks completed)")
                
            except Exception as e:
                print(f"QA RAG batch processing failed: {e}")
                # Add chunks without QA processing as fallback
                for chunk in batch:
                    qa_chunks.append(self._convert_to_simple_chunk(chunk))
        
        return qa_chunks
    
    def _filter_chunks_for_qa(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter chunks suitable for QA generation"""
        suitable_chunks = []
        
        for chunk in chunks:
            text = chunk.get('text', '')
            text_length = len(text.strip())
            
            # Check size constraints
            if (text_length < self.config.min_chunk_size_for_qa or 
                text_length > self.config.max_chunk_size_for_qa):
                continue
            
            # Check content quality (basic heuristics)
            if self._is_suitable_for_qa(text):
                suitable_chunks.append(chunk)
        
        return suitable_chunks
    
    def _is_suitable_for_qa(self, text: str) -> bool:
        """Determine if chunk content is suitable for QA generation"""
        text = text.strip()
        
        # Basic quality checks
        if len(text.split()) < 20:  # Too short
            return False
        
        # Check for meaningful content (not just numbers/symbols)
        alpha_chars = sum(1 for c in text if c.isalpha())
        if alpha_chars / len(text) < 0.5:  # Less than 50% alphabetic characters
            return False
        
        # Check for sentence structure
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if len(sentences) < 2:  # Need at least 2 sentences
            return False
        
        return True
    
    async def _process_chunk_batch(
        self, 
        chunks: List[Dict[str, Any]], 
        source_config: 'DataSource'
    ) -> List[QAChunk]:
        """Process a batch of chunks to generate Q&A pairs"""
        
        batch_tasks = []
        for chunk in chunks:
            task = self._process_single_chunk(chunk, source_config)
            batch_tasks.append(task)
        
        # Execute batch concurrently
        results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        qa_chunks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"QA processing failed for chunk {i}: {result}")
                # Fallback to simple chunk
                qa_chunks.append(self._convert_to_simple_chunk(chunks[i]))
            else:
                qa_chunks.append(result)
        
        return qa_chunks
    
    async def _process_single_chunk(
        self, 
        chunk: Dict[str, Any], 
        source_config: 'DataSource'
    ) -> QAChunk:
        """Process a single chunk to generate Q&A pairs"""
        
        chunk_text = chunk.get('text', '')
        chunk_metadata = chunk.get('metadata', {})
        
        # Determine domain for prompt selection
        domain = self._determine_domain(chunk_metadata, source_config)
        
        try:
            # Generate questions
            questions = await self._generate_questions(chunk_text, domain)
            
            # Generate answers for each question
            answers = []
            for question in questions:
                answer = await self._generate_answer(chunk_text, question, domain)
                answers.append(answer)
            
            # Calculate quality score
            quality_score = self._calculate_qa_quality_score(questions, answers, chunk_text)
            
            # Create QA chunk
            qa_chunk = QAChunk(
                chunk_id=chunk.get('metadata', {}).get('chunk_id', f"chunk_{hash(chunk_text)%1000000}"),
                original_text=chunk_text,
                questions=questions,
                answers=answers,
                metadata={
                    **chunk_metadata,
                    'qa_rag_processed': True,
                    'domain': domain,
                    'source_id': source_config.source_id
                },
                qa_generation_metadata={
                    'model_used': self.config.qa_model,
                    'questions_requested': self.config.questions_per_chunk,
                    'questions_generated': len(questions),
                    'processing_time': datetime.utcnow().isoformat()
                },
                quality_score=quality_score
            )
            
            return qa_chunk
            
        except Exception as e:
            print(f"QA generation failed for chunk: {e}")
            # Return simple chunk as fallback
            return self._convert_to_simple_chunk(chunk)
    
    def _determine_domain(self, metadata: Dict[str, Any], source_config: 'DataSource') -> str:
        """Determine the domain for prompt selection"""
        
        # Check metadata for explicit domain
        if 'domain' in metadata:
            return metadata['domain']
        
        # Check source type
        source_type = source_config.source_type.value
        domain_mapping = {
            'hr_system': 'hr',
            'financial_system': 'financial',
            'crm_system': 'general',
            'document_repository': 'general',
            'linkedin_profiles': 'hr',
            'industry_research': 'general',
            'product_catalog': 'technical'
        }
        
        return domain_mapping.get(source_type, 'general')
    
    async def _generate_questions(self, chunk_text: str, domain: str) -> List[str]:
        """Generate questions for a chunk using domain-specific prompts"""
        
        domain_prompt = self.domain_prompts.get(domain, self.domain_prompts['general'])
        question_prompt = domain_prompt['question_prompt'].format(
            num_questions=self.config.questions_per_chunk,
            chunk_text=chunk_text
        )
        
        for attempt in range(self.config.max_retries):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.config.qa_model,
                        messages=[
                            {"role": "system", "content": "You are an expert at generating high-quality questions from document content."},
                            {"role": "user", "content": question_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=500
                    ),
                    timeout=self.config.timeout_seconds
                )
                
                questions_text = response.choices[0].message.content.strip()
                questions = [q.strip() for q in questions_text.split('\n') if q.strip()]
                
                # Filter and validate questions
                valid_questions = self._validate_questions(questions)
                
                if valid_questions:
                    return valid_questions[:self.config.questions_per_chunk]
                
            except Exception as e:
                print(f"Question generation attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return []
    
    async def _generate_answer(self, chunk_text: str, question: str, domain: str) -> str:
        """Generate an answer for a question using domain-specific prompts"""
        
        domain_prompt = self.domain_prompts.get(domain, self.domain_prompts['general'])
        answer_prompt = domain_prompt['answer_prompt'].format(
            chunk_text=chunk_text,
            question=question
        )
        
        for attempt in range(self.config.max_retries):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.config.qa_model,
                        messages=[
                            {"role": "system", "content": "You are an expert at providing accurate, detailed answers based on document content."},
                            {"role": "user", "content": answer_prompt}
                        ],
                        temperature=0.3,  # Lower temperature for more consistent answers
                        max_tokens=800
                    ),
                    timeout=self.config.timeout_seconds
                )
                
                answer = response.choices[0].message.content.strip()
                
                # Validate answer
                if self._validate_answer(answer):
                    return answer
                
            except Exception as e:
                print(f"Answer generation attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return "Unable to generate answer from the provided content."
    
    def _validate_questions(self, questions: List[str]) -> List[str]:
        """Validate and filter generated questions"""
        valid_questions = []
        
        for question in questions:
            question = question.strip()
            
            # Remove numbering or bullet points
            question = question.lstrip('0123456789.-) ')
            
            # Length check
            if (len(question) < self.config.min_question_length or 
                len(question) > self.config.max_question_length):
                continue
            
            # Must end with question mark
            if not question.endswith('?'):
                question += '?'
            
            # Basic quality checks
            if len(question.split()) < 3:  # Too short
                continue
            
            # Check for question words
            question_words = ['what', 'how', 'why', 'when', 'where', 'who', 'which', 'can', 'is', 'are', 'do', 'does', 'will', 'would']
            if not any(question.lower().startswith(word) for word in question_words):
                continue
            
            valid_questions.append(question)
        
        return valid_questions
    
    def _validate_answer(self, answer: str) -> bool:
        """Validate generated answer"""
        answer = answer.strip()
        
        # Length check
        if (len(answer) < self.config.min_answer_length or 
            len(answer) > self.config.max_answer_length):
            return False
        
        # Must have reasonable sentence structure
        sentences = [s.strip() for s in answer.split('.') if s.strip()]
        if len(sentences) < 1:
            return False
        
        # Check for meaningful content
        words = answer.split()
        if len(words) < 5:
            return False
        
        return True
    
    def _calculate_qa_quality_score(self, questions: List[str], answers: List[str], original_text: str) -> float:
        """Calculate quality score for generated Q&A pairs"""
        
        if not questions or not answers:
            return 0.0
        
        score_components = []
        
        # Question quality score
        if questions:
            avg_question_length = sum(len(q.split()) for q in questions) / len(questions)
            question_score = min(avg_question_length / 15, 1.0)  # Normalize to 15 words
            score_components.append(question_score)
        
        # Answer quality score
        if answers:
            avg_answer_length = sum(len(a.split()) for a in answers) / len(answers)
            answer_score = min(avg_answer_length / 50, 1.0)  # Normalize to 50 words
            score_components.append(answer_score)
        
        # Completeness score (did we get the requested number of Q&A pairs?)
        completeness = min(len(questions) / self.config.questions_per_chunk, 1.0)
        score_components.append(completeness)
        
        # Consistency score (same number of questions and answers)
        consistency = 1.0 if len(questions) == len(answers) else 0.5
        score_components.append(consistency)
        
        return sum(score_components) / len(score_components)
    
    def _convert_to_simple_chunk(self, chunk: Dict[str, Any]) -> QAChunk:
        """Convert regular chunk to QAChunk format without Q&A processing"""
        return QAChunk(
            chunk_id=chunk.get('metadata', {}).get('chunk_id', f"chunk_{hash(chunk.get('text', ''))%1000000}"),
            original_text=chunk.get('text', ''),
            questions=[],
            answers=[],
            metadata={
                **chunk.get('metadata', {}),
                'qa_rag_processed': False
            },
            qa_generation_metadata={},
            quality_score=0.5  # Default score for non-processed chunks
        )
```

## QA RAG Configuration Examples

```python
# From QA RAG configuration patterns - EXAMPLE

# Basic QA RAG configuration for HR documents
hr_qa_config = QARAGConfig(
    enabled=True,
    questions_per_chunk=3,
    qa_model="meta-llama/Llama-3.1-8B-Instruct",
    api_base_url="http://localhost:5001/inf",
    min_chunk_size_for_qa=300,
    max_chunk_size_for_qa=1500,
    quality_threshold=0.8
)

# Advanced QA RAG configuration for financial documents
financial_qa_config = QARAGConfig(
    enabled=True,
    questions_per_chunk=5,  # More questions for complex financial content
    qa_model="meta-llama/Llama-3.1-70B-Instruct",  # Larger model for accuracy
    api_base_url="http://localhost:5001/inf",
    min_chunk_size_for_qa=500,  # Larger minimum for financial context
    max_chunk_size_for_qa=3000,  # Allow larger chunks for complete financial statements
    quality_threshold=0.9,  # Higher quality threshold for financial accuracy
    batch_size=3,  # Smaller batches for complex processing
    timeout_seconds=120  # Longer timeout for complex financial analysis
)

# Data source configuration with QA RAG
data_sources = [
    DataSource(
        source_id="hr_documents",
        source_type=DataSourceType.DOCUMENT_REPOSITORY,
        connection_config={"path": "/data/hr_docs"},
        processing_mode=ProcessingMode.BATCH,
        qa_rag_enabled=True,  # Enable QA RAG for HR documents
        qa_rag_config=hr_qa_config.__dict__
    ),
    DataSource(
        source_id="financial_reports",
        source_type=DataSourceType.FINANCIAL_SYSTEM,
        connection_config={"api_endpoint": "https://finance.company.com/api"},
        processing_mode=ProcessingMode.BATCH,
        qa_rag_enabled=True,  # Enable QA RAG for financial documents
        qa_rag_config=financial_qa_config.__dict__
    ),
    DataSource(
        source_id="email_archives",
        source_type=DataSourceType.EMAIL_ARCHIVES,
        connection_config={"mailbox": "corporate@company.com"},
        processing_mode=ProcessingMode.STREAMING,
        qa_rag_enabled=False,  # Disable QA RAG for emails (too noisy)
        qa_rag_config={}
    )
]
```

This addition provides comprehensive QA RAG functionality with:

1. **Configurable QA Processing**: Enable/disable per data source with detailed configuration
2. **Domain-Specific Prompts**: Optimized prompts for HR, Financial, Technical, and General content
3. **Quality Validation**: Comprehensive validation of generated questions and answers
4. **Batch Processing**: Efficient processing with error recovery
5. **Rich Chunk Format**: Enhanced chunks with Q&A pairs for better retrieval
6. **Performance Monitoring**: Quality scores and processing metrics
