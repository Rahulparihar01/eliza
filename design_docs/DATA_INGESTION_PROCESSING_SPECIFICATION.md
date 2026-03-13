# Data Ingestion & Processing Specification

## Executive Summary

This document provides comprehensive technical specifications for the data ingestion and processing layer of the AI Enablement Platform. It details multi-source data ingestion, configurable chunking strategies, document processing workflows, and indexing mechanisms leveraging advanced RAG patterns and modern AI architectures.

**Key Capabilities:**
- Multi-format document ingestion with intelligent parsing
- Configurable chunking strategies (semantic, fixed, hybrid)
- Real-time and batch processing modes
- Memory RAG integration with FAISS indexing
- Knowledge graph population with relationship extraction
- Quality validation and error recovery

---

## 1. Data Ingestion Architecture Overview

### 1.1 Multi-Source Ingestion Pipeline
*Building on patterns from [MEMORY_RAG_DEEP_DIVE.md](MEMORY_RAG_DEEP_DIVE.md) and [TEMPLATE_PATTERNS_FOR_AGENTIC_PROJECT.md](TEMPLATE_PATTERNS_FOR_AGENTIC_PROJECT.md)*

```python
# From multi-source ingestion patterns - TESTED
from crewai import Flow, Agent, Task
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
from pathlib import Path
import mimetypes

logger = logging.getLogger(__name__)

class DataSourceType(Enum):
    """Supported data source types"""
    HR_SYSTEM = "hr_system"
    FINANCIAL_SYSTEM = "financial_system"
    CRM_SYSTEM = "crm_system"
    DOCUMENT_REPOSITORY = "document_repository"
    LINKEDIN_PROFILES = "linkedin_profiles"
    INDUSTRY_RESEARCH = "industry_research"
    PRODUCT_CATALOG = "product_catalog"
    EMAIL_ARCHIVES = "email_archives"
    MEETING_TRANSCRIPTS = "meeting_transcripts"
    KNOWLEDGE_BASE = "knowledge_base"

class ProcessingMode(Enum):
    """Data processing modes"""
    REAL_TIME = "real_time"
    BATCH = "batch"
    STREAMING = "streaming"
    SCHEDULED = "scheduled"

@dataclass
class DataSource:
    """Configuration for a data source"""
    source_id: str
    source_type: DataSourceType
    connection_config: Dict[str, Any]
    processing_mode: ProcessingMode
    refresh_interval: Optional[int] = None  # minutes
    priority: int = 1  # 1=highest, 5=lowest
    enabled: bool = True
    qa_rag_enabled: bool = False  # Enable QA RAG processing for this source
    qa_rag_config: Dict[str, Any] = field(default_factory=dict)  # QA RAG specific configuration
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class IngestionConfig:
    """Complete ingestion configuration"""
    data_sources: List[DataSource]
    chunking_strategy: str = "semantic"
    chunking_config: Dict[str, Any] = field(default_factory=dict)
    processing_config: Dict[str, Any] = field(default_factory=dict)
    quality_config: Dict[str, Any] = field(default_factory=dict)
    indexing_config: Dict[str, Any] = field(default_factory=dict)

class MultiSourceIngestionFlow(Flow):
    """CrewAI flow for comprehensive data ingestion"""
    
    def __init__(self, config: IngestionConfig):
        super().__init__()
        self.config = config
        
        # Initialize specialized ingestion agents
        self.agents = self._create_ingestion_agents()
        
        # Initialize processing components
        self.document_processor = DocumentProcessor(config.chunking_config)
        self.quality_validator = QualityValidator(config.quality_config)
        self.index_manager = IndexManager(config.indexing_config)
        self.qa_rag_processor = QARAGProcessor(config.get('qa_rag_config', {}))
        
        # Initialize monitoring
        self.metrics_collector = MetricsCollector()
    
    def _create_ingestion_agents(self) -> Dict[str, Agent]:
        """Create specialized agents for each data source type"""
        agents = {}
        
        # HR Data Agent
        agents['hr_agent'] = Agent(
            role="HR Data Ingestion Specialist",
            goal="Extract and process HR data including employee profiles, performance, and organizational structure",
            backstory="""You are an expert in HR data systems with deep knowledge of employee 
            data structures, privacy requirements, and organizational hierarchies.""",
            tools=[
                self.create_hr_extractor(),
                self.create_employee_profiler(),
                self.create_org_structure_analyzer(),
                self.create_skills_extractor()
            ],
            llm_config=self._get_llm_config()
        )
        
        # Document Processing Agent
        agents['document_agent'] = Agent(
            role="Document Processing Specialist", 
            goal="Process documents with intelligent parsing, chunking, and metadata extraction",
            backstory="""You are a document processing expert who understands various 
            document formats and can extract meaningful structure and content.""",
            tools=[
                self.create_document_parser(),
                self.create_content_extractor(),
                self.create_metadata_extractor(),
                self.create_structure_analyzer()
            ],
            llm_config=self._get_llm_config()
        )
        
        # Financial Data Agent
        agents['financial_agent'] = Agent(
            role="Financial Data Analyst",
            goal="Process financial data and extract department-level insights",
            backstory="""You are a financial analyst expert in corporate accounting, 
            budgeting, and department-level financial analysis.""",
            tools=[
                self.create_financial_parser(),
                self.create_budget_analyzer(),
                self.create_cost_center_mapper(),
                self.create_roi_calculator()
            ],
            llm_config=self._get_llm_config()
        )
        
        return agents
    
    async def _process_qa_rag_if_enabled(self, processed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data through QA RAG if enabled for any data sources"""
        
        qa_rag_results = {
            'data': processed_data,
            'metrics': {
                'sources_with_qa_rag': 0,
                'total_chunks_processed': 0,
                'qa_chunks_created': 0,
                'total_questions_generated': 0,
                'total_answers_generated': 0,
                'avg_quality_score': 0.0,
                'processing_time_seconds': 0.0
            }
        }
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            enhanced_data = {}
            
            for source_id, source_data in processed_data.items():
                # Get source configuration
                source_config = self._get_source_config_by_id(source_id)
                
                if source_config and source_config.qa_rag_enabled:
                    logger.info(f"Processing QA RAG for source: {source_id}")
                    
                    # Extract chunks from source data
                    chunks = source_data.get('chunks', [])
                    
                    # Process through QA RAG
                    qa_chunks = await self.qa_rag_processor.process_chunks_to_qa_rag(
                        chunks, 
                        source_config
                    )
                    
                    # Update metrics
                    qa_rag_results['metrics']['sources_with_qa_rag'] += 1
                    qa_rag_results['metrics']['total_chunks_processed'] += len(chunks)
                    qa_rag_results['metrics']['qa_chunks_created'] += len(qa_chunks)
                    
                    # Calculate Q&A metrics
                    for chunk in qa_chunks:
                        if hasattr(chunk, 'questions') and hasattr(chunk, 'answers'):
                            qa_rag_results['metrics']['total_questions_generated'] += len(chunk.questions)
                            qa_rag_results['metrics']['total_answers_generated'] += len(chunk.answers)
                    
                    # Calculate average quality score
                    quality_scores = [chunk.quality_score for chunk in qa_chunks if hasattr(chunk, 'quality_score')]
                    if quality_scores:
                        avg_quality = sum(quality_scores) / len(quality_scores)
                        qa_rag_results['metrics']['avg_quality_score'] = avg_quality
                    
                    # Store enhanced data
                    enhanced_data[source_id] = {
                        **source_data,
                        'qa_chunks': qa_chunks,
                        'qa_rag_enabled': True
                    }
                    
                else:
                    # Keep original data for sources without QA RAG
                    enhanced_data[source_id] = {
                        **source_data,
                        'qa_rag_enabled': False
                    }
            
            qa_rag_results['data'] = enhanced_data
            qa_rag_results['metrics']['processing_time_seconds'] = asyncio.get_event_loop().time() - start_time
            
            return qa_rag_results
            
        except Exception as e:
            logger.error(f"QA RAG processing failed: {e}")
            # Return original data with error metrics
            qa_rag_results['data'] = processed_data
            qa_rag_results['metrics']['error'] = str(e)
            return qa_rag_results
    
    def _get_source_config_by_id(self, source_id: str) -> Optional[DataSource]:
        """Get source configuration by ID"""
        for source in self.config.data_sources:
            if source.source_id == source_id:
                return source
        return None
    
    async def execute_ingestion_pipeline(self, data_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute complete multi-source ingestion pipeline"""
        
        ingestion_results = {}
        processing_metrics = {}
        
        try:
            # Phase 1: Data Source Discovery and Validation
            discovery_tasks = []
            for source_config in data_sources:
                task = Task(
                    description=f"Discover and validate data source: {source_config['source_id']}",
                    agent=self._get_agent_for_source_type(source_config['source_type']),
                    context=source_config,
                    expected_output="Data source validation report with schema and sample data"
                )
                discovery_tasks.append(task)
            
            discovery_results = await self.execute_tasks(discovery_tasks)
            processing_metrics['discovery'] = self._collect_discovery_metrics(discovery_results)
            
            # Phase 2: Data Extraction
            extraction_tasks = []
            for i, source_config in enumerate(data_sources):
                if discovery_results[i]['status'] == 'validated':
                    task = Task(
                        description=f"Extract data from {source_config['source_id']}",
                        agent=self._get_agent_for_source_type(source_config['source_type']),
                        context={
                            'source_config': source_config,
                            'validation_result': discovery_results[i]
                        },
                        expected_output="Extracted raw data with metadata"
                    )
                    extraction_tasks.append(task)
            
            extraction_results = await self.execute_tasks(extraction_tasks)
            processing_metrics['extraction'] = self._collect_extraction_metrics(extraction_results)
            
            # Phase 3: Data Processing and Chunking
            processing_results = await self._process_extracted_data(extraction_results)
            processing_metrics['processing'] = processing_results['metrics']
            
            # Phase 4: QA RAG Processing (if enabled)
            qa_rag_results = await self._process_qa_rag_if_enabled(processing_results['data'])
            processing_metrics['qa_rag'] = qa_rag_results['metrics']
            
            # Phase 5: Quality Validation
            validation_results = await self._validate_processed_data(qa_rag_results['data'])
            processing_metrics['validation'] = validation_results['metrics']
            
            # Phase 6: Indexing and Storage
            indexing_results = await self._index_validated_data(validation_results['validated_data'])
            processing_metrics['indexing'] = indexing_results['metrics']
            
            return {
                'status': 'completed',
                'ingestion_results': ingestion_results,
                'processing_metrics': processing_metrics,
                'total_documents_processed': sum(m.get('document_count', 0) for m in processing_metrics.values()),
                'total_chunks_created': processing_metrics.get('processing', {}).get('total_chunks', 0),
                'indexing_summary': indexing_results['summary']
            }
            
        except Exception as e:
            logger.error(f"Ingestion pipeline failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'partial_results': ingestion_results,
                'metrics': processing_metrics
            }
```

### 1.2 Document Format Support Matrix

```python
# From document processing patterns - EXAMPLE
class DocumentFormatHandler:
    """Handles multiple document formats with specialized processors"""
    
    SUPPORTED_FORMATS = {
        # Text Documents
        'application/pdf': {
            'processor': 'PDFProcessor',
            'chunking_strategies': ['semantic', 'page_based', 'section_based'],
            'metadata_extraction': ['text', 'images', 'tables', 'structure'],
            'quality_checks': ['text_extraction_quality', 'layout_preservation']
        },
        'application/msword': {
            'processor': 'DocProcessor', 
            'chunking_strategies': ['semantic', 'paragraph_based', 'section_based'],
            'metadata_extraction': ['text', 'styles', 'comments', 'track_changes'],
            'quality_checks': ['formatting_preservation', 'content_completeness']
        },
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {
            'processor': 'DocxProcessor',
            'chunking_strategies': ['semantic', 'paragraph_based', 'section_based'],
            'metadata_extraction': ['text', 'styles', 'comments', 'metadata'],
            'quality_checks': ['formatting_preservation', 'content_completeness']
        },
        
        # Spreadsheets
        'application/vnd.ms-excel': {
            'processor': 'ExcelProcessor',
            'chunking_strategies': ['sheet_based', 'row_based', 'semantic_table'],
            'metadata_extraction': ['data', 'formulas', 'charts', 'metadata'],
            'quality_checks': ['data_integrity', 'formula_preservation']
        },
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {
            'processor': 'XlsxProcessor',
            'chunking_strategies': ['sheet_based', 'row_based', 'semantic_table'],
            'metadata_extraction': ['data', 'formulas', 'charts', 'metadata'],
            'quality_checks': ['data_integrity', 'formula_preservation']
        },
        
        # Presentations
        'application/vnd.ms-powerpoint': {
            'processor': 'PowerPointProcessor',
            'chunking_strategies': ['slide_based', 'semantic', 'section_based'],
            'metadata_extraction': ['text', 'images', 'animations', 'notes'],
            'quality_checks': ['slide_completeness', 'media_extraction']
        },
        
        # Text Files
        'text/plain': {
            'processor': 'TextProcessor',
            'chunking_strategies': ['semantic', 'paragraph_based', 'line_based'],
            'metadata_extraction': ['encoding', 'structure'],
            'quality_checks': ['encoding_detection', 'content_completeness']
        },
        'text/markdown': {
            'processor': 'MarkdownProcessor',
            'chunking_strategies': ['semantic', 'section_based', 'heading_based'],
            'metadata_extraction': ['structure', 'links', 'metadata'],
            'quality_checks': ['markdown_validity', 'link_integrity']
        },
        
        # Structured Data
        'application/json': {
            'processor': 'JSONProcessor',
            'chunking_strategies': ['object_based', 'array_based', 'semantic'],
            'metadata_extraction': ['schema', 'structure', 'types'],
            'quality_checks': ['json_validity', 'schema_compliance']
        },
        'text/csv': {
            'processor': 'CSVProcessor',
            'chunking_strategies': ['row_based', 'column_based', 'semantic'],
            'metadata_extraction': ['headers', 'data_types', 'statistics'],
            'quality_checks': ['data_integrity', 'format_consistency']
        },
        
        # Web Content
        'text/html': {
            'processor': 'HTMLProcessor',
            'chunking_strategies': ['semantic', 'element_based', 'section_based'],
            'metadata_extraction': ['structure', 'links', 'metadata', 'scripts'],
            'quality_checks': ['html_validity', 'content_extraction']
        },
        
        # Email
        'message/rfc822': {
            'processor': 'EmailProcessor',
            'chunking_strategies': ['message_based', 'thread_based', 'semantic'],
            'metadata_extraction': ['headers', 'attachments', 'thread_info'],
            'quality_checks': ['header_completeness', 'attachment_extraction']
        }
    }
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.processors = self._initialize_processors()
    
    def _initialize_processors(self) -> Dict[str, Any]:
        """Initialize document processors for each supported format"""
        processors = {}
        
        for mime_type, format_config in self.SUPPORTED_FORMATS.items():
            processor_class = getattr(self, format_config['processor'])
            processors[mime_type] = processor_class(
                chunking_strategies=format_config['chunking_strategies'],
                metadata_config=format_config['metadata_extraction'],
                quality_config=format_config['quality_checks']
            )
        
        return processors
    
    async def process_document(self, document_path: str, processing_config: Dict[str, Any]) -> Dict[str, Any]:
        """Process a document with appropriate format handler"""
        
        # Detect document format
        mime_type, _ = mimetypes.guess_type(document_path)
        if mime_type not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported document format: {mime_type}")
        
        # Get appropriate processor
        processor = self.processors[mime_type]
        
        # Process document
        processing_result = await processor.process(document_path, processing_config)
        
        return {
            'document_path': document_path,
            'mime_type': mime_type,
            'processing_result': processing_result,
            'format_capabilities': self.SUPPORTED_FORMATS[mime_type]
        }
```

---

## 2. Advanced Chunking Strategies

### 2.1 Configurable Chunking Framework
*Extending patterns from [MEMORY_RAG_DEEP_DIVE.md](MEMORY_RAG_DEEP_DIVE.md)*

```python
# From advanced chunking patterns - EXAMPLE
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

@dataclass
class ChunkingConfig:
    """Configuration for chunking strategies"""
    strategy: str  # 'semantic', 'fixed', 'hybrid', 'adaptive', 'hierarchical'
    chunk_size: int = 1024  # characters for fixed, tokens for others
    chunk_overlap: int = 128  # overlap between chunks
    min_chunk_size: int = 100  # minimum chunk size
    max_chunk_size: int = 4096  # maximum chunk size
    
    # Semantic chunking specific
    similarity_threshold: float = 0.85  # similarity threshold for semantic boundaries
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    window_size: int = 3  # sentences to consider for semantic boundaries
    breakpoint_percentile: float = 95.0  # percentile for breakpoint detection
    
    # Hierarchical chunking specific
    hierarchy_levels: List[str] = None  # ['document', 'section', 'paragraph', 'sentence']
    preserve_structure: bool = True  # maintain document structure
    
    # Adaptive chunking specific
    content_type_detection: bool = True  # adapt strategy based on content type
    quality_threshold: float = 0.8  # minimum quality score for chunks
    
    # Domain-specific options
    domain: str = "general"  # 'hr', 'financial', 'technical', 'legal', etc.
    language: str = "en"  # language for processing
    
    def __post_init__(self):
        if self.hierarchy_levels is None:
            self.hierarchy_levels = ['document', 'section', 'paragraph', 'sentence']

class BaseChunker(ABC):
    """Abstract base class for all chunking strategies"""
    
    def __init__(self, config: ChunkingConfig):
        self.config = config
        self.metrics = ChunkingMetrics()
    
    @abstractmethod
    async def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk text into meaningful segments"""
        pass
    
    def _create_chunk(self, text: str, start_idx: int, end_idx: int, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create a standardized chunk object"""
        return {
            'text': text[start_idx:end_idx].strip(),
            'start_idx': start_idx,
            'end_idx': end_idx,
            'length': end_idx - start_idx,
            'metadata': {
                **metadata,
                'chunk_strategy': self.config.strategy,
                'chunk_id': self._generate_chunk_id(start_idx, end_idx),
                'creation_timestamp': datetime.utcnow().isoformat()
            }
        }
    
    def _generate_chunk_id(self, start_idx: int, end_idx: int) -> str:
        """Generate unique chunk ID"""
        import hashlib
        content_hash = hashlib.md5(f"{start_idx}_{end_idx}_{self.config.strategy}".encode()).hexdigest()[:8]
        return f"chunk_{content_hash}"

class SemanticChunker(BaseChunker):
    """Advanced semantic chunking with configurable similarity detection"""
    
    def __init__(self, config: ChunkingConfig):
        super().__init__(config)
        self.embedding_model = SentenceTransformer(config.embedding_model)
        self.nlp = spacy.load("en_core_web_sm")
        
    async def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk text using semantic similarity analysis"""
        
        try:
            # Step 1: Split into sentences
            sentences = self._split_into_sentences(text)
            if len(sentences) < 2:
                return [self._create_chunk(text, 0, len(text), metadata)]
            
            # Step 2: Create sentence embeddings
            sentence_embeddings = await self._get_sentence_embeddings(sentences)
            
            # Step 3: Calculate similarity scores between adjacent sentences
            similarity_scores = self._calculate_similarity_scores(sentence_embeddings)
            
            # Step 4: Identify breakpoints using configurable threshold
            breakpoints = self._identify_breakpoints(similarity_scores)
            
            # Step 5: Create chunks based on breakpoints
            chunks = self._create_semantic_chunks(text, sentences, breakpoints, metadata)
            
            # Step 6: Post-process chunks (merge small, split large)
            optimized_chunks = self._optimize_chunks(chunks, text, metadata)
            
            # Update metrics
            self.metrics.record_chunking_operation(
                strategy='semantic',
                input_length=len(text),
                output_chunks=len(optimized_chunks),
                avg_chunk_size=np.mean([len(c['text']) for c in optimized_chunks])
            )
            
            return optimized_chunks
            
        except Exception as e:
            logger.error(f"Semantic chunking failed: {e}")
            # Fallback to fixed chunking
            fallback_chunker = FixedChunker(self.config)
            return await fallback_chunker.chunk_text(text, metadata)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using spaCy"""
        doc = self.nlp(text)
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        return sentences
    
    async def _get_sentence_embeddings(self, sentences: List[str]) -> np.ndarray:
        """Get embeddings for sentences with batching"""
        # Process in batches to handle memory efficiently
        batch_size = 32
        all_embeddings = []
        
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            batch_embeddings = self.embedding_model.encode(
                batch, 
                show_progress_bar=False,
                convert_to_numpy=True
            )
            all_embeddings.append(batch_embeddings)
        
        return np.vstack(all_embeddings)
    
    def _calculate_similarity_scores(self, embeddings: np.ndarray) -> List[float]:
        """Calculate cosine similarity between adjacent sentence embeddings"""
        similarities = []
        
        for i in range(len(embeddings) - 1):
            # Cosine similarity between adjacent sentences
            similarity = np.dot(embeddings[i], embeddings[i + 1]) / (
                np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i + 1])
            )
            similarities.append(similarity)
        
        return similarities
    
    def _identify_breakpoints(self, similarity_scores: List[float]) -> List[int]:
        """Identify breakpoints using percentile-based threshold"""
        if not similarity_scores:
            return []
        
        # Calculate threshold based on percentile
        threshold = np.percentile(similarity_scores, 100 - self.config.breakpoint_percentile)
        
        # Find breakpoints where similarity drops below threshold
        breakpoints = []
        for i, score in enumerate(similarity_scores):
            if score < threshold:
                breakpoints.append(i + 1)  # +1 because we break after sentence i
        
        # Ensure we have reasonable breakpoints
        if not breakpoints:
            # If no breakpoints found, create some based on window size
            window_size = self.config.window_size
            for i in range(window_size, len(similarity_scores), window_size):
                breakpoints.append(i)
        
        return breakpoints
    
    def _create_semantic_chunks(
        self, 
        text: str, 
        sentences: List[str], 
        breakpoints: List[int], 
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create chunks based on identified breakpoints"""
        chunks = []
        start_idx = 0
        
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
            char_end = char_start + len(chunk_text)
            
            if char_start != -1 and len(chunk_text.strip()) >= self.config.min_chunk_size:
                chunk_metadata = {
                    **metadata,
                    'sentence_range': [start_sentence, end_sentence],
                    'sentence_count': len(chunk_sentences)
                }
                
                chunks.append(self._create_chunk(text, char_start, char_end, chunk_metadata))
        
        return chunks
    
    def _optimize_chunks(
        self, 
        chunks: List[Dict[str, Any]], 
        original_text: str, 
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Optimize chunks by merging small ones and splitting large ones"""
        optimized = []
        i = 0
        
        while i < len(chunks):
            current_chunk = chunks[i]
            
            # If chunk is too small, try to merge with next
            if (len(current_chunk['text']) < self.config.min_chunk_size and 
                i + 1 < len(chunks)):
                
                next_chunk = chunks[i + 1]
                merged_length = len(current_chunk['text']) + len(next_chunk['text'])
                
                if merged_length <= self.config.max_chunk_size:
                    # Merge chunks
                    merged_chunk = self._create_chunk(
                        original_text,
                        current_chunk['start_idx'],
                        next_chunk['end_idx'],
                        {**metadata, 'merged': True}
                    )
                    optimized.append(merged_chunk)
                    i += 2  # Skip both chunks
                    continue
            
            # If chunk is too large, split it
            if len(current_chunk['text']) > self.config.max_chunk_size:
                split_chunks = self._split_large_chunk(current_chunk, original_text, metadata)
                optimized.extend(split_chunks)
            else:
                optimized.append(current_chunk)
            
            i += 1
        
        return optimized
    
    def _split_large_chunk(
        self, 
        chunk: Dict[str, Any], 
        original_text: str, 
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Split a large chunk into smaller ones"""
        chunk_text = chunk['text']
        target_size = self.config.chunk_size
        overlap = self.config.chunk_overlap
        
        splits = []
        start = 0
        
        while start < len(chunk_text):
            end = min(start + target_size, len(chunk_text))
            
            # Try to break at sentence boundary
            if end < len(chunk_text):
                # Look for sentence end within reasonable distance
                for i in range(end, max(start + target_size // 2, end - 100), -1):
                    if chunk_text[i] in '.!?':
                        end = i + 1
                        break
            
            split_text = chunk_text[start:end].strip()
            if split_text:
                split_metadata = {
                    **metadata,
                    'parent_chunk_id': chunk['metadata']['chunk_id'],
                    'split_index': len(splits)
                }
                
                splits.append(self._create_chunk(
                    original_text,
                    chunk['start_idx'] + start,
                    chunk['start_idx'] + end,
                    split_metadata
                ))
            
            start = end - overlap if end < len(chunk_text) else end
        
        return splits

class HierarchicalChunker(BaseChunker):
    """Hierarchical chunking that preserves document structure"""
    
    def __init__(self, config: ChunkingConfig):
        super().__init__(config)
        self.nlp = spacy.load("en_core_web_sm")
    
    async def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create hierarchical chunks based on document structure"""
        
        try:
            # Step 1: Detect document structure
            structure = await self._detect_document_structure(text)
            
            # Step 2: Create hierarchical chunks
            hierarchical_chunks = self._create_hierarchical_chunks(text, structure, metadata)
            
            # Step 3: Flatten hierarchy based on configuration
            final_chunks = self._flatten_hierarchy(hierarchical_chunks)
            
            return final_chunks
            
        except Exception as e:
            logger.error(f"Hierarchical chunking failed: {e}")
            # Fallback to semantic chunking
            semantic_chunker = SemanticChunker(self.config)
            return await semantic_chunker.chunk_text(text, metadata)
    
    async def _detect_document_structure(self, text: str) -> Dict[str, Any]:
        """Detect document structure (headers, sections, paragraphs)"""
        structure = {
            'sections': [],
            'paragraphs': [],
            'sentences': [],
            'headers': []
        }
        
        # Detect headers (simple heuristic - can be enhanced)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if line:
                # Check if line looks like a header
                if self._is_likely_header(line):
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
        
        # Detect sentences using spaCy
        doc = self.nlp(text)
        for sent in doc.sents:
            structure['sentences'].append({
                'text': sent.text.strip(),
                'start_pos': sent.start_char,
                'end_pos': sent.end_char
            })
        
        return structure
    
    def _is_likely_header(self, line: str) -> bool:
        """Heuristic to determine if a line is likely a header"""
        # Simple heuristics - can be enhanced with ML
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
        # Simple heuristic based on length and formatting
        if header.isupper():
            return 1
        elif len(header.split()) <= 3:
            return 2
        elif len(header.split()) <= 6:
            return 3
        else:
            return 4

class AdaptiveChunker(BaseChunker):
    """Adaptive chunking that selects strategy based on content type"""
    
    def __init__(self, config: ChunkingConfig):
        super().__init__(config)
        self.content_classifier = ContentTypeClassifier()
        
        # Initialize all chunking strategies
        self.chunkers = {
            'semantic': SemanticChunker(config),
            'hierarchical': HierarchicalChunker(config),
            'fixed': FixedChunker(config)
        }
    
    async def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Adaptively choose chunking strategy based on content analysis"""
        
        try:
            # Step 1: Classify content type
            content_analysis = await self.content_classifier.analyze_content(text, metadata)
            
            # Step 2: Select optimal chunking strategy
            optimal_strategy = self._select_chunking_strategy(content_analysis)
            
            # Step 3: Apply selected strategy
            chunker = self.chunkers[optimal_strategy]
            chunks = await chunker.chunk_text(text, metadata)
            
            # Step 4: Add adaptive metadata
            for chunk in chunks:
                chunk['metadata']['adaptive_strategy'] = optimal_strategy
                chunk['metadata']['content_analysis'] = content_analysis
            
            return chunks
            
        except Exception as e:
            logger.error(f"Adaptive chunking failed: {e}")
            # Fallback to semantic chunking
            return await self.chunkers['semantic'].chunk_text(text, metadata)
    
    def _select_chunking_strategy(self, content_analysis: Dict[str, Any]) -> str:
        """Select optimal chunking strategy based on content analysis"""
        
        content_type = content_analysis.get('primary_type', 'general')
        structure_score = content_analysis.get('structure_score', 0.5)
        complexity_score = content_analysis.get('complexity_score', 0.5)
        
        # Strategy selection logic
        if content_type in ['technical_manual', 'legal_document', 'policy']:
            if structure_score > 0.7:
                return 'hierarchical'
            else:
                return 'semantic'
        
        elif content_type in ['email', 'chat', 'informal_text']:
            return 'semantic'
        
        elif content_type in ['financial_report', 'structured_data']:
            if structure_score > 0.8:
                return 'hierarchical'
            else:
                return 'semantic'
        
        else:
            # Default strategy selection based on content characteristics
            if structure_score > 0.8 and complexity_score > 0.6:
                return 'hierarchical'
            elif complexity_score > 0.7:
                return 'semantic'
            else:
                return 'fixed'

class ContentTypeClassifier:
    """Classifies content type to inform chunking strategy selection"""
    
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.tfidf = TfidfVectorizer(max_features=1000, stop_words='english')
    
    async def analyze_content(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze content to determine type and characteristics"""
        
        analysis = {
            'primary_type': 'general',
            'structure_score': 0.5,
            'complexity_score': 0.5,
            'formality_score': 0.5,
            'technical_score': 0.5,
            'characteristics': []
        }
        
        try:
            # Basic text statistics
            doc = self.nlp(text)
            sentences = list(doc.sents)
            tokens = [token for token in doc if not token.is_stop and not token.is_punct]
            
            # Structure analysis
            structure_indicators = self._analyze_structure(text, sentences)
            analysis['structure_score'] = structure_indicators['score']
            analysis['characteristics'].extend(structure_indicators['indicators'])
            
            # Complexity analysis
            complexity_indicators = self._analyze_complexity(doc, sentences, tokens)
            analysis['complexity_score'] = complexity_indicators['score']
            analysis['characteristics'].extend(complexity_indicators['indicators'])
            
            # Content type classification
            content_type = self._classify_content_type(text, doc, metadata)
            analysis['primary_type'] = content_type
            
            return analysis
            
        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            return analysis
    
    def _analyze_structure(self, text: str, sentences: List) -> Dict[str, Any]:
        """Analyze document structure"""
        indicators = []
        score_components = []
        
        # Check for headers/titles
        lines = text.split('\n')
        potential_headers = [line for line in lines if line.strip() and len(line.strip()) < 100]
        header_ratio = len(potential_headers) / max(len(lines), 1)
        score_components.append(min(header_ratio * 2, 1.0))  # Cap at 1.0
        
        if header_ratio > 0.1:
            indicators.append('structured_headers')
        
        # Check for lists and bullet points
        list_patterns = ['•', '-', '*', '1.', '2.', '3.', 'a)', 'b)', 'c)']
        list_lines = sum(1 for line in lines if any(line.strip().startswith(p) for p in list_patterns))
        list_ratio = list_lines / max(len(lines), 1)
        score_components.append(list_ratio)
        
        if list_ratio > 0.05:
            indicators.append('contains_lists')
        
        # Check for consistent paragraph structure
        paragraphs = text.split('\n\n')
        if len(paragraphs) > 1:
            avg_para_length = np.mean([len(p.split()) for p in paragraphs if p.strip()])
            para_length_std = np.std([len(p.split()) for p in paragraphs if p.strip()])
            consistency = 1 - (para_length_std / max(avg_para_length, 1))
            score_components.append(max(0, consistency))
            
            if consistency > 0.7:
                indicators.append('consistent_paragraphs')
        
        overall_score = np.mean(score_components) if score_components else 0.5
        
        return {
            'score': overall_score,
            'indicators': indicators
        }
    
    def _analyze_complexity(self, doc, sentences: List, tokens: List) -> Dict[str, Any]:
        """Analyze text complexity"""
        indicators = []
        score_components = []
        
        # Vocabulary diversity
        unique_words = set(token.lemma_.lower() for token in tokens if token.is_alpha)
        total_words = len([token for token in tokens if token.is_alpha])
        vocab_diversity = len(unique_words) / max(total_words, 1)
        score_components.append(vocab_diversity)
        
        if vocab_diversity > 0.7:
            indicators.append('high_vocabulary_diversity')
        
        # Average sentence length
        if sentences:
            avg_sentence_length = np.mean([len(sent.text.split()) for sent in sentences])
            # Normalize to 0-1 scale (assuming 30 words is very complex)
            length_complexity = min(avg_sentence_length / 30, 1.0)
            score_components.append(length_complexity)
            
            if avg_sentence_length > 20:
                indicators.append('long_sentences')
        
        # Technical terms (simple heuristic)
        technical_patterns = [
            lambda token: len(token.text) > 12,  # Long words often technical
            lambda token: token.pos_ in ['NOUN'] and token.text.endswith(('tion', 'sion', 'ment', 'ness')),
            lambda token: token.ent_type_ in ['ORG', 'PRODUCT', 'EVENT']  # Named entities
        ]
        
        technical_count = sum(1 for token in tokens if any(pattern(token) for pattern in technical_patterns))
        technical_ratio = technical_count / max(len(tokens), 1)
        score_components.append(technical_ratio)
        
        if technical_ratio > 0.1:
            indicators.append('technical_terminology')
        
        overall_score = np.mean(score_components) if score_components else 0.5
        
        return {
            'score': overall_score,
            'indicators': indicators
        }
    
    def _classify_content_type(self, text: str, doc, metadata: Dict[str, Any]) -> str:
        """Classify the primary content type"""
        
        # Check metadata first
        if 'content_type' in metadata:
            return metadata['content_type']
        
        # Check file extension or source
        source = metadata.get('source', '').lower()
        if any(term in source for term in ['hr', 'human_resources', 'employee']):
            return 'hr_document'
        elif any(term in source for term in ['financial', 'budget', 'finance', 'accounting']):
            return 'financial_document'
        elif any(term in source for term in ['technical', 'manual', 'documentation']):
            return 'technical_document'
        elif any(term in source for term in ['email', 'message', 'correspondence']):
            return 'communication'
        
        # Content-based classification (simple heuristics)
        text_lower = text.lower()
        
        # Financial indicators
        financial_terms = ['budget', 'revenue', 'profit', 'cost', 'expense', 'financial', 'accounting']
        if sum(text_lower.count(term) for term in financial_terms) > 5:
            return 'financial_document'
        
        # HR indicators
        hr_terms = ['employee', 'performance', 'salary', 'benefits', 'training', 'skills', 'department']
        if sum(text_lower.count(term) for term in hr_terms) > 5:
            return 'hr_document'
        
        # Technical indicators
        tech_terms = ['system', 'process', 'procedure', 'implementation', 'configuration', 'technical']
        if sum(text_lower.count(term) for term in tech_terms) > 5:
            return 'technical_document'
        
        return 'general'

class FixedChunker(BaseChunker):
    """Simple fixed-size chunking with overlap"""
    
    async def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create fixed-size chunks with configurable overlap"""
        
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap
        
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            
            # Try to break at word boundary
            if end < len(text):
                # Look for space within reasonable distance
                for i in range(end, max(start + chunk_size // 2, end - 50), -1):
                    if text[i] == ' ':
                        end = i
                        break
            
            chunk_text = text[start:end].strip()
            if chunk_text and len(chunk_text) >= self.config.min_chunk_size:
                chunks.append(self._create_chunk(text, start, end, metadata))
            
            start = end - overlap if end < len(text) else end
        
        return chunks
```

### 2.2 User-Configurable Chunking Interface

```python
# From user configuration patterns - EXAMPLE
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum

class ChunkingStrategy(str, Enum):
    """Available chunking strategies"""
    SEMANTIC = "semantic"
    FIXED = "fixed"
    HIERARCHICAL = "hierarchical"
    ADAPTIVE = "adaptive"
    HYBRID = "hybrid"

class UserChunkingConfig(BaseModel):
    """User-configurable chunking parameters"""
    
    # Strategy selection
    strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC
    fallback_strategy: ChunkingStrategy = ChunkingStrategy.FIXED
    
    # Size parameters
    target_chunk_size: int = Field(default=1024, ge=100, le=8192, description="Target chunk size in characters")
    min_chunk_size: int = Field(default=100, ge=50, le=1000, description="Minimum chunk size")
    max_chunk_size: int = Field(default=4096, ge=500, le=16384, description="Maximum chunk size")
    chunk_overlap: int = Field(default=128, ge=0, le=512, description="Overlap between chunks")
    
    # Semantic chunking parameters
    similarity_threshold: float = Field(default=0.85, ge=0.5, le=0.99, description="Similarity threshold for semantic boundaries")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", description="Embedding model for semantic analysis")
    window_size: int = Field(default=3, ge=1, le=10, description="Sentence window for semantic analysis")
    breakpoint_percentile: float = Field(default=95.0, ge=80.0, le=99.0, description="Percentile for breakpoint detection")
    
    # Hierarchical chunking parameters
    preserve_structure: bool = Field(default=True, description="Preserve document structure in chunks")
    hierarchy_levels: List[str] = Field(default=["document", "section", "paragraph"], description="Hierarchy levels to consider")
    
    # Content-specific parameters
    domain: str = Field(default="general", description="Content domain for specialized processing")
    language: str = Field(default="en", description="Content language")
    content_type: Optional[str] = Field(default=None, description="Specific content type override")
    
    # Quality parameters
    quality_threshold: float = Field(default=0.8, ge=0.5, le=1.0, description="Minimum quality score for chunks")
    enable_quality_filtering: bool = Field(default=True, description="Enable quality-based chunk filtering")
    
    # Performance parameters
    batch_size: int = Field(default=32, ge=1, le=128, description="Batch size for processing")
    max_concurrent_tasks: int = Field(default=4, ge=1, le=16, description="Maximum concurrent processing tasks")
    
    @validator('min_chunk_size', 'max_chunk_size')
    def validate_chunk_sizes(cls, v, values):
        if 'target_chunk_size' in values:
            target = values['target_chunk_size']
            if v == values.get('min_chunk_size') and v >= target:
                raise ValueError('min_chunk_size must be less than target_chunk_size')
            if v == values.get('max_chunk_size') and v <= target:
                raise ValueError('max_chunk_size must be greater than target_chunk_size')
        return v
    
    @validator('chunk_overlap')
    def validate_overlap(cls, v, values):
        if 'target_chunk_size' in values and v >= values['target_chunk_size']:
            raise ValueError('chunk_overlap must be less than target_chunk_size')
        return v

class ChunkingConfigurationManager:
    """Manages user chunking configurations with validation and presets"""
    
    PRESET_CONFIGURATIONS = {
        "general_documents": UserChunkingConfig(
            strategy=ChunkingStrategy.SEMANTIC,
            target_chunk_size=1024,
            similarity_threshold=0.85,
            domain="general"
        ),
        "technical_manuals": UserChunkingConfig(
            strategy=ChunkingStrategy.HIERARCHICAL,
            target_chunk_size=1536,
            preserve_structure=True,
            domain="technical"
        ),
        "financial_reports": UserChunkingConfig(
            strategy=ChunkingStrategy.ADAPTIVE,
            target_chunk_size=2048,
            quality_threshold=0.9,
            domain="financial"
        ),
        "hr_documents": UserChunkingConfig(
            strategy=ChunkingStrategy.SEMANTIC,
            target_chunk_size=1024,
            similarity_threshold=0.8,
            domain="hr"
        ),
        "legal_documents": UserChunkingConfig(
            strategy=ChunkingStrategy.HIERARCHICAL,
            target_chunk_size=2048,
            preserve_structure=True,
            quality_threshold=0.95,
            domain="legal"
        ),
        "email_archives": UserChunkingConfig(
            strategy=ChunkingStrategy.SEMANTIC,
            target_chunk_size=512,
            similarity_threshold=0.75,
            domain="communication"
        )
    }
    
    def __init__(self):
        self.custom_configurations: Dict[str, UserChunkingConfig] = {}
    
    def get_preset_config(self, preset_name: str) -> UserChunkingConfig:
        """Get a preset configuration"""
        if preset_name not in self.PRESET_CONFIGURATIONS:
            available = list(self.PRESET_CONFIGURATIONS.keys())
            raise ValueError(f"Unknown preset '{preset_name}'. Available presets: {available}")
        
        return self.PRESET_CONFIGURATIONS[preset_name].copy(deep=True)
    
    def create_custom_config(
        self, 
        config_name: str, 
        base_preset: str = "general_documents",
        overrides: Dict[str, Any] = None
    ) -> UserChunkingConfig:
        """Create a custom configuration based on a preset with overrides"""
        
        base_config = self.get_preset_config(base_preset)
        
        if overrides:
            # Apply overrides
            config_dict = base_config.dict()
            config_dict.update(overrides)
            custom_config = UserChunkingConfig(**config_dict)
        else:
            custom_config = base_config
        
        self.custom_configurations[config_name] = custom_config
        return custom_config
    
    def validate_config(self, config: UserChunkingConfig) -> Dict[str, Any]:
        """Validate configuration and return validation report"""
        
        validation_report = {
            'is_valid': True,
            'warnings': [],
            'recommendations': []
        }
        
        # Check for potential performance issues
        if config.target_chunk_size > 4096:
            validation_report['warnings'].append(
                "Large chunk size may impact processing performance"
            )
        
        if config.similarity_threshold > 0.95:
            validation_report['warnings'].append(
                "Very high similarity threshold may result in too many small chunks"
            )
        
        if config.chunk_overlap > config.target_chunk_size * 0.5:
            validation_report['warnings'].append(
                "High overlap ratio may cause significant content duplication"
            )
        
        # Provide recommendations
        if config.strategy == ChunkingStrategy.SEMANTIC and config.domain == "technical":
            validation_report['recommendations'].append(
                "Consider using hierarchical chunking for technical documents with clear structure"
            )
        
        if config.strategy == ChunkingStrategy.FIXED and config.domain in ["legal", "financial"]:
            validation_report['recommendations'].append(
                "Semantic or hierarchical chunking may preserve important context better for this domain"
            )
        
        return validation_report
    
    def get_recommended_config(self, content_analysis: Dict[str, Any]) -> UserChunkingConfig:
        """Get recommended configuration based on content analysis"""
        
        content_type = content_analysis.get('primary_type', 'general')
        structure_score = content_analysis.get('structure_score', 0.5)
        complexity_score = content_analysis.get('complexity_score', 0.5)
        
        # Map content type to preset
        type_to_preset = {
            'hr_document': 'hr_documents',
            'financial_document': 'financial_reports',
            'technical_document': 'technical_manuals',
            'legal_document': 'legal_documents',
            'communication': 'email_archives'
        }
        
        preset_name = type_to_preset.get(content_type, 'general_documents')
        base_config = self.get_preset_config(preset_name)
        
        # Adjust based on analysis
        adjustments = {}
        
        if structure_score > 0.8:
            adjustments['strategy'] = ChunkingStrategy.HIERARCHICAL
            adjustments['preserve_structure'] = True
        elif structure_score < 0.3:
            adjustments['strategy'] = ChunkingStrategy.SEMANTIC
        
        if complexity_score > 0.8:
            adjustments['target_chunk_size'] = min(base_config.target_chunk_size * 1.5, 4096)
            adjustments['quality_threshold'] = 0.9
        elif complexity_score < 0.3:
            adjustments['target_chunk_size'] = max(base_config.target_chunk_size * 0.7, 512)
        
        # Apply adjustments
        if adjustments:
            config_dict = base_config.dict()
            config_dict.update(adjustments)
            return UserChunkingConfig(**config_dict)
        
        return base_config

# Usage example for API endpoint
class ChunkingConfigAPI:
    """API interface for chunking configuration management"""
    
    def __init__(self):
        self.config_manager = ChunkingConfigurationManager()
    
    async def get_presets(self) -> Dict[str, Dict[str, Any]]:
        """Get all available preset configurations"""
        return {
            name: config.dict() 
            for name, config in self.config_manager.PRESET_CONFIGURATIONS.items()
        }
    
    async def validate_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a user configuration"""
        try:
            config = UserChunkingConfig(**config_data)
            validation_report = self.config_manager.validate_config(config)
            return {
                'valid': validation_report['is_valid'],
                'config': config.dict(),
                'validation_report': validation_report
            }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'validation_report': {'is_valid': False, 'warnings': [], 'recommendations': []}
            }
    
    async def recommend_config(self, content_sample: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Recommend configuration based on content analysis"""
        
        # Analyze content (simplified for example)
        content_classifier = ContentTypeClassifier()
        content_analysis = await content_classifier.analyze_content(content_sample, metadata or {})
        
        # Get recommendation
        recommended_config = self.config_manager.get_recommended_config(content_analysis)
        
        return {
            'recommended_config': recommended_config.dict(),
            'content_analysis': content_analysis,
            'rationale': self._generate_recommendation_rationale(content_analysis, recommended_config)
        }
    
    def _generate_recommendation_rationale(
        self, 
        content_analysis: Dict[str, Any], 
        config: UserChunkingConfig
    ) -> str:
        """Generate human-readable rationale for configuration recommendation"""
        
        rationale_parts = []
        
        content_type = content_analysis.get('primary_type', 'general')
        structure_score = content_analysis.get('structure_score', 0.5)
        complexity_score = content_analysis.get('complexity_score', 0.5)
        
        rationale_parts.append(f"Content classified as: {content_type}")
        
        if structure_score > 0.8:
            rationale_parts.append("High structure detected - hierarchical chunking recommended")
        elif structure_score > 0.5:
            rationale_parts.append("Moderate structure detected - semantic chunking with structure preservation")
        else:
            rationale_parts.append("Low structure detected - semantic chunking for coherent segments")
        
        if complexity_score > 0.8:
            rationale_parts.append("High complexity - larger chunks to preserve context")
        elif complexity_score < 0.3:
            rationale_parts.append("Low complexity - smaller chunks for focused content")
        
        rationale_parts.append(f"Recommended strategy: {config.strategy.value}")
        rationale_parts.append(f"Target chunk size: {config.target_chunk_size} characters")
        
        return ". ".join(rationale_parts) + "."
```

---

## 3. Document Processing Workflows

### 3.1 Multi-Stage Document Processing Pipeline

```python
# From document processing workflows - EXAMPLE
from typing import Dict, List, Any, Optional, Tuple, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import aiofiles
from pathlib import Path
import mimetypes
import hashlib
from datetime import datetime

class ProcessingStage(Enum):
    """Document processing stages"""
    DISCOVERY = "discovery"
    VALIDATION = "validation"
    EXTRACTION = "extraction"
    CHUNKING = "chunking"
    ENRICHMENT = "enrichment"
    QUALITY_CHECK = "quality_check"
    INDEXING = "indexing"
    COMPLETION = "completion"

@dataclass
class ProcessingResult:
    """Result of a processing stage"""
    stage: ProcessingStage
    status: str  # 'success', 'error', 'warning'
    data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

class DocumentProcessingPipeline:
    """Comprehensive document processing pipeline with error recovery"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.chunking_manager = ChunkingConfigurationManager()
        self.format_handler = DocumentFormatHandler(config)
        self.quality_validator = QualityValidator(config.get('quality', {}))
        self.metrics_collector = ProcessingMetricsCollector()
        
        # Processing stages
        self.stages = [
            ProcessingStage.DISCOVERY,
            ProcessingStage.VALIDATION,
            ProcessingStage.EXTRACTION,
            ProcessingStage.CHUNKING,
            ProcessingStage.ENRICHMENT,
            ProcessingStage.QUALITY_CHECK,
            ProcessingStage.INDEXING,
            ProcessingStage.COMPLETION
        ]
    
    async def process_documents(
        self, 
        document_sources: List[Dict[str, Any]], 
        chunking_config: UserChunkingConfig = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process multiple documents with streaming results"""
        
        if chunking_config is None:
            chunking_config = self.chunking_manager.get_preset_config("general_documents")
        
        total_documents = len(document_sources)
        processed_count = 0
        
        # Process documents in batches to manage memory
        batch_size = self.config.get('batch_size', 10)
        
        for i in range(0, total_documents, batch_size):
            batch = document_sources[i:i + batch_size]
            
            # Process batch concurrently
            batch_tasks = [
                self.process_single_document(doc_source, chunking_config)
                for doc_source in batch
            ]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in batch_results:
                processed_count += 1
                
                if isinstance(result, Exception):
                    yield {
                        'status': 'error',
                        'error': str(result),
                        'document_index': processed_count - 1,
                        'progress': processed_count / total_documents
                    }
                else:
                    yield {
                        'status': 'success',
                        'result': result,
                        'document_index': processed_count - 1,
                        'progress': processed_count / total_documents
                    }
    
    async def process_single_document(
        self, 
        document_source: Dict[str, Any], 
        chunking_config: UserChunkingConfig
    ) -> Dict[str, Any]:
        """Process a single document through all stages"""
        
        document_id = self._generate_document_id(document_source)
        processing_context = {
            'document_id': document_id,
            'source': document_source,
            'chunking_config': chunking_config,
            'stage_results': {},
            'overall_start_time': asyncio.get_event_loop().time()
        }
        
        try:
            # Execute processing stages sequentially
            for stage in self.stages:
                stage_result = await self._execute_stage(stage, processing_context)
                processing_context['stage_results'][stage.value] = stage_result
                
                # Check if stage failed and handle accordingly
                if stage_result.status == 'error':
                    if self._is_critical_stage(stage):
                        # Critical failure - abort processing
                        return self._create_failure_result(processing_context, stage_result)
                    else:
                        # Non-critical failure - continue with warning
                        logger.warning(f"Non-critical stage {stage.value} failed: {stage_result.errors}")
            
            # Create final result
            return self._create_success_result(processing_context)
            
        except Exception as e:
            logger.error(f"Document processing failed for {document_id}: {e}")
            return self._create_exception_result(processing_context, e)
    
    async def _execute_stage(self, stage: ProcessingStage, context: Dict[str, Any]) -> ProcessingResult:
        """Execute a specific processing stage"""
        
        stage_start_time = asyncio.get_event_loop().time()
        
        try:
            if stage == ProcessingStage.DISCOVERY:
                result = await self._stage_discovery(context)
            elif stage == ProcessingStage.VALIDATION:
                result = await self._stage_validation(context)
            elif stage == ProcessingStage.EXTRACTION:
                result = await self._stage_extraction(context)
            elif stage == ProcessingStage.CHUNKING:
                result = await self._stage_chunking(context)
            elif stage == ProcessingStage.ENRICHMENT:
                result = await self._stage_enrichment(context)
            elif stage == ProcessingStage.QUALITY_CHECK:
                result = await self._stage_quality_check(context)
            elif stage == ProcessingStage.INDEXING:
                result = await self._stage_indexing(context)
            elif stage == ProcessingStage.COMPLETION:
                result = await self._stage_completion(context)
            else:
                raise ValueError(f"Unknown processing stage: {stage}")
            
            result.processing_time = asyncio.get_event_loop().time() - stage_start_time
            return result
            
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - stage_start_time
            return ProcessingResult(
                stage=stage,
                status='error',
                errors=[str(e)],
                processing_time=processing_time
            )
    
    async def _stage_discovery(self, context: Dict[str, Any]) -> ProcessingResult:
        """Stage 1: Document discovery and basic metadata extraction"""
        
        source = context['source']
        
        # Extract basic information
        if 'file_path' in source:
            file_path = Path(source['file_path'])
            if not file_path.exists():
                return ProcessingResult(
                    stage=ProcessingStage.DISCOVERY,
                    status='error',
                    errors=[f"File not found: {file_path}"]
                )
            
            # Get file metadata
            file_stats = file_path.stat()
            mime_type, encoding = mimetypes.guess_type(str(file_path))
            
            discovery_data = {
                'file_path': str(file_path),
                'file_name': file_path.name,
                'file_size': file_stats.st_size,
                'mime_type': mime_type,
                'encoding': encoding,
                'modified_time': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                'file_hash': await self._calculate_file_hash(file_path)
            }
            
        elif 'content' in source:
            # Direct content processing
            content = source['content']
            discovery_data = {
                'content_length': len(content),
                'content_type': source.get('content_type', 'text/plain'),
                'content_hash': hashlib.md5(content.encode()).hexdigest()
            }
            
        else:
            return ProcessingResult(
                stage=ProcessingStage.DISCOVERY,
                status='error',
                errors=["No valid document source provided (file_path or content required)"]
            )
        
        return ProcessingResult(
            stage=ProcessingStage.DISCOVERY,
            status='success',
            data=discovery_data,
            metadata={'discovery_method': 'file_system' if 'file_path' in source else 'direct_content'}
        )
    
    async def _stage_validation(self, context: Dict[str, Any]) -> ProcessingResult:
        """Stage 2: Document validation and format checking"""
        
        discovery_result = context['stage_results']['discovery']
        if discovery_result.status != 'success':
            return ProcessingResult(
                stage=ProcessingStage.VALIDATION,
                status='error',
                errors=["Cannot validate document without successful discovery"]
            )
        
        discovery_data = discovery_result.data
        mime_type = discovery_data.get('mime_type')
        
        validation_results = {
            'format_supported': False,
            'file_size_ok': True,
            'file_accessible': True,
            'content_readable': False
        }
        
        warnings = []
        errors = []
        
        # Check format support
        if mime_type in self.format_handler.SUPPORTED_FORMATS:
            validation_results['format_supported'] = True
        else:
            errors.append(f"Unsupported document format: {mime_type}")
        
        # Check file size
        file_size = discovery_data.get('file_size', 0)
        max_size = self.config.get('max_file_size', 100 * 1024 * 1024)  # 100MB default
        if file_size > max_size:
            validation_results['file_size_ok'] = False
            errors.append(f"File too large: {file_size} bytes (max: {max_size})")
        elif file_size == 0:
            warnings.append("Empty file detected")
        
        # Test content readability
        try:
            if 'file_path' in context['source']:
                async with aiofiles.open(context['source']['file_path'], 'rb') as f:
                    # Try to read first 1KB
                    sample = await f.read(1024)
                    if sample:
                        validation_results['content_readable'] = True
            else:
                # Direct content is already readable
                validation_results['content_readable'] = True
        except Exception as e:
            errors.append(f"Cannot read file content: {e}")
        
        status = 'success' if not errors else 'error'
        if warnings and not errors:
            status = 'warning'
        
        return ProcessingResult(
            stage=ProcessingStage.VALIDATION,
            status=status,
            data=validation_results,
            errors=errors,
            warnings=warnings
        )
    
    async def _stage_extraction(self, context: Dict[str, Any]) -> ProcessingResult:
        """Stage 3: Content extraction from document"""
        
        discovery_data = context['stage_results']['discovery'].data
        source = context['source']
        
        try:
            # Use appropriate format handler
            if 'file_path' in source:
                extraction_result = await self.format_handler.process_document(
                    source['file_path'],
                    self.config.get('extraction', {})
                )
            else:
                # Handle direct content
                extraction_result = {
                    'text_content': source['content'],
                    'metadata': source.get('metadata', {}),
                    'structure': {'type': 'plain_text'}
                }
            
            # Validate extraction quality
            text_content = extraction_result.get('text_content', '')
            if not text_content or len(text_content.strip()) < 10:
                return ProcessingResult(
                    stage=ProcessingStage.EXTRACTION,
                    status='error',
                    errors=["No meaningful text content extracted"]
                )
            
            return ProcessingResult(
                stage=ProcessingStage.EXTRACTION,
                status='success',
                data=extraction_result,
                metadata={
                    'extracted_text_length': len(text_content),
                    'extraction_method': 'format_handler'
                }
            )
            
        except Exception as e:
            return ProcessingResult(
                stage=ProcessingStage.EXTRACTION,
                status='error',
                errors=[f"Content extraction failed: {e}"]
            )
    
    async def _stage_chunking(self, context: Dict[str, Any]) -> ProcessingResult:
        """Stage 4: Text chunking using configured strategy"""
        
        extraction_result = context['stage_results']['extraction']
        if extraction_result.status != 'success':
            return ProcessingResult(
                stage=ProcessingStage.CHUNKING,
                status='error',
                errors=["Cannot chunk document without successful extraction"]
            )
        
        text_content = extraction_result.data.get('text_content', '')
        document_metadata = extraction_result.data.get('metadata', {})
        chunking_config = context['chunking_config']
        
        try:
            # Create appropriate chunker
            chunker = self._create_chunker(chunking_config)
            
            # Perform chunking
            chunks = await chunker.chunk_text(text_content, document_metadata)
            
            # Validate chunks
            if not chunks:
                return ProcessingResult(
                    stage=ProcessingStage.CHUNKING,
                    status='error',
                    errors=["No chunks created from document"]
                )
            
            # Filter out low-quality chunks
            quality_chunks = [chunk for chunk in chunks if len(chunk['text'].strip()) >= chunking_config.min_chunk_size]
            
            chunking_metrics = {
                'total_chunks': len(chunks),
                'quality_chunks': len(quality_chunks),
                'avg_chunk_size': np.mean([len(c['text']) for c in quality_chunks]) if quality_chunks else 0,
                'chunking_strategy': chunking_config.strategy.value
            }
            
            return ProcessingResult(
                stage=ProcessingStage.CHUNKING,
                status='success',
                data=quality_chunks,
                metadata=chunking_metrics
            )
            
        except Exception as e:
            return ProcessingResult(
                stage=ProcessingStage.CHUNKING,
                status='error',
                errors=[f"Chunking failed: {e}"]
            )
    
    def _create_chunker(self, config: UserChunkingConfig):
        """Create appropriate chunker based on configuration"""
        
        chunking_config = ChunkingConfig(
            strategy=config.strategy.value,
            chunk_size=config.target_chunk_size,
            chunk_overlap=config.chunk_overlap,
            min_chunk_size=config.min_chunk_size,
            max_chunk_size=config.max_chunk_size,
            similarity_threshold=config.similarity_threshold,
            embedding_model=config.embedding_model,
            window_size=config.window_size,
            breakpoint_percentile=config.breakpoint_percentile,
            hierarchy_levels=config.hierarchy_levels,
            preserve_structure=config.preserve_structure,
            domain=config.domain,
            language=config.language
        )
        
        if config.strategy == ChunkingStrategy.SEMANTIC:
            return SemanticChunker(chunking_config)
        elif config.strategy == ChunkingStrategy.HIERARCHICAL:
            return HierarchicalChunker(chunking_config)
        elif config.strategy == ChunkingStrategy.ADAPTIVE:
            return AdaptiveChunker(chunking_config)
        elif config.strategy == ChunkingStrategy.FIXED:
            return FixedChunker(chunking_config)
        else:
            # Default to semantic
            return SemanticChunker(chunking_config)
    
    async def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _generate_document_id(self, document_source: Dict[str, Any]) -> str:
        """Generate unique document ID"""
        if 'file_path' in document_source:
            base = document_source['file_path']
        elif 'content' in document_source:
            base = hashlib.md5(document_source['content'][:1000].encode()).hexdigest()
        else:
            base = str(datetime.utcnow().timestamp())
        
        return f"doc_{hashlib.md5(base.encode()).hexdigest()[:12]}"
    
    def _is_critical_stage(self, stage: ProcessingStage) -> bool:
        """Determine if a stage failure should abort processing"""
        critical_stages = {
            ProcessingStage.DISCOVERY,
            ProcessingStage.VALIDATION,
            ProcessingStage.EXTRACTION,
            ProcessingStage.CHUNKING
        }
        return stage in critical_stages
```

This comprehensive data ingestion and processing specification provides:

1. **Multi-Source Data Pipeline** with CrewAI flows and specialized agents
2. **Advanced Chunking Strategies** with user-configurable options
3. **Document Format Support** for all major business document types
4. **Quality Validation** and error recovery mechanisms
5. **Real-time Processing** with streaming results and progress tracking
6. **User Configuration Interface** with presets and custom options

The system is designed to handle enterprise-scale document processing while providing flexibility for different content types and user preferences. Would you like me to elaborate on any specific aspect or add additional processing capabilities?
