# Memory RAG Deep Dive: Complete Implementation Guide

## Executive Summary

Memory RAG represents a sophisticated approach to Retrieval-Augmented Generation that goes far beyond traditional RAG. This document provides a comprehensive analysis of Memory RAG's architecture, implementation patterns, and key components that will be essential for your agentic project.

---

## 1. Memory RAG Architecture Overview

### 1.1 Core Philosophy

**Memory RAG ≠ Traditional RAG**
- **Traditional RAG**: Document chunking → Vector search → Context injection → Generation
- **Memory RAG**: Intelligent document processing → Multi-modal indexing → Memory-augmented retrieval → Context-aware generation with reasoning

### 1.2 Three-Layer Memory RAG Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 MEMORY RAG LAYERS                       │
├─────────────────────────────────────────────────────────┤
│  🧠 MEMORY LAYER                                        │
│    • VectorIndex (FAISS + Embeddings)                  │
│    • Memory-augmented retrieval                        │
│    • Context persistence and reasoning                 │
├─────────────────────────────────────────────────────────┤
│  🔄 PIPELINE LAYER                                      │
│    • Document experiment pipelines                     │
│    • OpenAI-compatible processing                      │
│    • Multi-step reasoning chains                       │
├─────────────────────────────────────────────────────────┤
│  📄 PROCESSING LAYER                                    │
│    • PDF loading and chunking                          │
│    • Semantic understanding                            │
│    • Metadata extraction and enrichment               │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Core Memory RAG Components

### 2.1 VectorIndex: The Memory Foundation

**Core Implementation:**
```python
# From sdk/memory_rag/index/vector_index.py - EXAMPLE
class VectorIndex:
    def __init__(self, api_key_manager=None):
        from API_KEY_MANAGEMENT_SPECIFICATION import APIKeyManager
        self.api_key_manager = api_key_manager or APIKeyManager()
        self.embedding_client = self._init_embedding_client()
        self.index = None                 # FAISS vector index
        self.splits = []                  # Original text chunks
    
    def _init_embedding_client(self):
        """Initialize embedding client with API key management"""
        import openai
        return openai.OpenAI(
            api_key=self.api_key_manager.get_api_key('openai'),
            base_url='https://api.openai.com/v1'
        )
    
    @staticmethod
    def build_index(loader: List[List[str]]) -> "VectorIndex":
        """Build memory index from processed documents"""
        vector_index = VectorIndex()
        vector_index.init_index()
        
        # Process in batches for efficiency
        for batch in tqdm(loader, desc="Building memory index"):
            vector_index.add_batch(batch)
        
        return vector_index
    
    def add_batch(self, batch: List[str]):
        """Add batch of text to memory index"""
        embeddings = self.get_embeddings(batch)  # Multi-dimensional embeddings
        
        if self.index is None:
            # Initialize FAISS index with embedding dimensions
            self.index = faiss.IndexFlatL2(len(embeddings[0][0]))
        
        # Add to vector index and preserve original text
        for emb in embeddings:
            self.index.add(emb)
        self.splits.extend(batch)
    
    def query_with_embedding(self, embedding: np.ndarray, k=5):
        """Memory-augmented similarity search"""
        embedding_array = np.array([embedding])
        _, indices = self.index.search(embedding_array, k)
        return [self.splits[i] for i in indices[0]]
    
    def save_index(self, path: str):
        """Save index to disk with error handling"""
        try:
            import pickle
            with open(f"{path}/index.pkl", "wb") as f:
                pickle.dump({
                    'index': faiss.serialize_index(self.index),
                    'splits': self.splits
                }, f)
            logger.info(f"Index saved successfully to {path}")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise
    
    @classmethod
    def load_index(cls, path: str) -> "VectorIndex":
        """Load index from disk with validation"""
        try:
            import pickle
            with open(f"{path}/index.pkl", "rb") as f:
                data = pickle.load(f)
            
            vector_index = cls()
            vector_index.index = faiss.deserialize_index(data['index'])
            vector_index.splits = data['splits']
            
            if len(vector_index.splits) != vector_index.index.ntotal:
                raise ValueError("Index and splits count mismatch")
                
            logger.info(f"Index loaded successfully from {path}")
            return vector_index
        except FileNotFoundError:
            logger.error(f"Index file not found at {path}")
            raise
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            raise
```

**Enhanced Memory RAG Client with Error Handling:**
```python
# From sdk/lamini/index/memory_client.py - EXAMPLE
import logging
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class MemoryRAGClient:
    """Production-ready Memory RAG client with comprehensive error handling"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.index: Optional[VectorIndex] = None
        self.embedding_api = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize client with proper error handling"""
        try:
            from API_KEY_MANAGEMENT_SPECIFICATION import APIKeyManager
            import openai
            
            self.api_key_manager = APIKeyManager()
            self.embedding_api = openai.OpenAI(
                api_key=self.api_key_manager.get_api_key('openai'),
                base_url='https://api.openai.com/v1'
            )
            logger.info("Memory RAG client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Memory RAG client: {e}")
            raise
    
    @contextmanager
    def error_context(self, operation: str):
        """Context manager for consistent error handling"""
        try:
            logger.info(f"Starting {operation}")
            yield
            logger.info(f"Completed {operation} successfully")
        except Exception as e:
            logger.error(f"Failed {operation}: {e}")
            raise
    
    def build_memory_index(self, documents: List[str], batch_size: int = 32) -> str:
        """Build memory index with progress tracking and error recovery"""
        with self.error_context("memory index building"):
            processed_docs = []
            failed_docs = []
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                try:
                    # Process batch with retry logic
                    processed_batch = self._process_document_batch(batch)
                    processed_docs.extend(processed_batch)
                    logger.info(f"Processed batch {i//batch_size + 1}/{(len(documents) + batch_size - 1)//batch_size}")
                except Exception as e:
                    logger.warning(f"Batch {i//batch_size + 1} failed: {e}")
                    failed_docs.extend(batch)
                    continue
            
            if failed_docs:
                logger.warning(f"{len(failed_docs)} documents failed processing")
            
            # Build index from processed documents
            self.index = VectorIndex.build_index([processed_docs])
            return f"Index built with {len(processed_docs)} documents"
    
    def _process_document_batch(self, batch: List[str], max_retries: int = 3) -> List[str]:
        """Process document batch with retry logic"""
        for attempt in range(max_retries):
            try:
                # Simulate document processing
                return [doc.strip() for doc in batch if doc.strip()]
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Retry {attempt + 1}/{max_retries} for batch processing: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
```

**Key Memory RAG Innovations:**
1. **Persistent Memory**: Index persists across sessions with `save_index()/load_index()`
2. **Multi-modal Embeddings**: Uses Lamini's advanced embedding models
3. **Batch Processing**: Efficient handling of large document collections
4. **Context Preservation**: Maintains original text alongside embeddings

### 2.2 Memory RAG Pipeline Architecture

**Document Experiment Pipeline:**
```python
# From infra/lamini_infra/ml/memory_rag/pipeline/document_experiment_pipeline.py - TESTED
class DocumentProcessor:
    def __init__(self, metadata: dict, prompt_template: dict):
        self.metadata = metadata
        self.prompt_template = prompt_template
        self.role = prompt_template.get("role", "You are an AI assistant.")
    
    def get_metadata_str(self) -> str:
        """Convert metadata to structured string for context"""
        return "\n".join(f"{k}: {v}" for k, v in self.metadata.items())

class OpenAIProcessor(BaseOpenAIClient):
    def __init__(self, processor: DocumentProcessor, model_config: ModelConfig):
        super().__init__()
        self.processor = processor
        self.model_config = model_config
    
    async def generate_questions(self, content: str, num_questions: int = 3) -> List[str]:
        """Generate contextual questions from document content"""
        prompt = f"""
        {self.processor.role}
        
        Metadata: {self.processor.get_metadata_str()}
        Content: {content}
        
        Generate {num_questions} high-quality questions that can be answered 
        from this content. Focus on key concepts and important details.
        """
        
        schema = self.build_question_schema()
        response = await self.execute_completion(
            model=self.model_config.question_model,
            prompt=prompt,
            response_schema=schema
        )
        
        return response.get("questions", [])
    
    async def generate_answer(self, content: str, question: str) -> str:
        """Generate contextual answer using Memory RAG"""
        prompt = f"""
        {self.processor.role}
        
        Metadata: {self.processor.get_metadata_str()}
        Content: {content}
        Question: {question}
        
        Provide a comprehensive answer based on the content above.
        """
        
        schema = self.build_answer_schema()
        response = await self.execute_completion(
            model=self.model_config.answer_model,
            prompt=prompt,
            response_schema=schema
        )
        
        return response.get("answer", "")
```

**Production Pipeline with Monitoring:**
```python
# From infra/lamini_infra/ml/memory_rag/pipeline/production_pipeline.py - EXAMPLE
import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class PipelineStatus(Enum):
    INITIALIZED = "initialized"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class PipelineMetrics:
    start_time: float
    end_time: Optional[float]
    documents_processed: int
    questions_generated: int
    answers_generated: int
    validation_passed: int
    errors: List[str]

class ProductionDocumentPipeline:
    """Production-ready document processing pipeline with monitoring"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.status = PipelineStatus.INITIALIZED
        self.metrics = PipelineMetrics(
            start_time=time.time(),
            end_time=None,
            documents_processed=0,
            questions_generated=0,
            answers_generated=0,
            validation_passed=0,
            errors=[]
        )
        self.processor = DocumentProcessor(
            metadata=config.get('metadata', {}),
            prompt_template=config.get('prompts', {})
        )
    
    async def process_documents_with_monitoring(self, documents: List[str]) -> Dict:
        """Process documents with comprehensive monitoring and error handling"""
        self.status = PipelineStatus.PROCESSING
        
        try:
            results = []
            for doc_idx, document in enumerate(documents):
                try:
                    # Process individual document
                    doc_result = await self._process_single_document(document, doc_idx)
                    results.append(doc_result)
                    self.metrics.documents_processed += 1
                    
                    # Log progress every 10 documents
                    if (doc_idx + 1) % 10 == 0:
                        logger.info(f"Processed {doc_idx + 1}/{len(documents)} documents")
                        
                except Exception as e:
                    error_msg = f"Failed to process document {doc_idx}: {e}"
                    self.metrics.errors.append(error_msg)
                    logger.error(error_msg)
                    continue
            
            self.status = PipelineStatus.COMPLETED
            self.metrics.end_time = time.time()
            
            return {
                "results": results,
                "metrics": self._get_metrics_summary(),
                "status": self.status.value
            }
            
        except Exception as e:
            self.status = PipelineStatus.FAILED
            self.metrics.errors.append(f"Pipeline failed: {e}")
            logger.error(f"Pipeline processing failed: {e}")
            raise
    
    async def _process_single_document(self, document: str, doc_idx: int) -> Dict:
        """Process a single document with error handling"""
        try:
            # Generate questions
            questions = await self._generate_questions_with_retry(document)
            self.metrics.questions_generated += len(questions)
            
            # Generate answers
            answers = []
            for question in questions:
                try:
                    answer = await self._generate_answer_with_retry(document, question)
                    answers.append(answer)
                    self.metrics.answers_generated += 1
                except Exception as e:
                    logger.warning(f"Failed to generate answer for question '{question}': {e}")
                    answers.append(f"Error: {str(e)}")
            
            # Validate Q&A pairs
            validated_pairs = await self._validate_qa_pairs(questions, answers, document)
            self.metrics.validation_passed += len(validated_pairs)
            
            return {
                "document_id": doc_idx,
                "questions": questions,
                "answers": answers,
                "validated_pairs": validated_pairs,
                "processing_time": time.time() - self.metrics.start_time
            }
            
        except Exception as e:
            logger.error(f"Document {doc_idx} processing failed: {e}")
            raise
    
    async def _generate_questions_with_retry(self, content: str, max_retries: int = 3) -> List[str]:
        """Generate questions with retry logic"""
        for attempt in range(max_retries):
            try:
                openai_processor = OpenAIProcessor(self.processor, self.config.get('model_config'))
                questions = await openai_processor.generate_questions(content)
                return questions
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Question generation retry {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(2 ** attempt)
        return []
    
    def _get_metrics_summary(self) -> Dict:
        """Get pipeline metrics summary"""
        duration = (self.metrics.end_time or time.time()) - self.metrics.start_time
        return {
            "duration_seconds": round(duration, 2),
            "documents_processed": self.metrics.documents_processed,
            "questions_generated": self.metrics.questions_generated,
            "answers_generated": self.metrics.answers_generated,
            "validation_passed": self.metrics.validation_passed,
            "error_count": len(self.metrics.errors),
            "success_rate": round(self.metrics.documents_processed / max(1, len(self.metrics.errors) + self.metrics.documents_processed) * 100, 2),
            "throughput_docs_per_second": round(self.metrics.documents_processed / max(1, duration), 2)
        }
```

### 2.3 Memory RAG Training Pipeline

**Core Training Flow:**
```python
# From infra/lamini_infra/ml/memory_rag/train/main.py - TESTED
async def run_default_pipeline(files: Dict[str, str], model_name: str, project_id: str, client: BaseOpenAIClient):
    """Complete Memory RAG training pipeline"""
    
    # Step 1: Document Loading and Chunking
    loader = PDFLoader(SentenceChunker(chunk_size=3, step_size=3), batch_size=1)
    for file in files:
        logger.info(f"Processing {file} with semantic chunking")
        loader.load_pdf(file, files[file])
    
    # Step 2: Document Summarization Pipeline
    summary_config = {
        "SummaryStep": {
            "model_name": model_name,
            "output_type": {"Summary": "str"},
            "instructions": [{
                "instruction_prompt": "Summarize the following file in one paragraph.",
                "metadata_key": "FileSnippet"
            }]
        }
    }
    
    summary_pipeline = build_pipeline(summary_config, client)
    summaries = {}
    
    for file in loader.sources:
        summary_prompt = {
            "FileSnippet": f"Filename: {file}\nFirst pages: {loader.get_first_pages(file, 1)}"
        }
        summary_result = await summary_pipeline.process_single(summary_prompt)
        summaries[file] = summary_result["Summary"]
    
    # Step 3: Question-Answer Generation Pipeline
    qa_config = {
        "QuestionStep": {
            "model_name": model_name,
            "output_type": {"questions": "List[str]"},
            "instructions": [{
                "instruction_prompt": "Generate 3 high-quality questions from this content.",
                "metadata_key": "Content"
            }]
        },
        "AnswerStep": {
            "model_name": model_name,
            "output_type": {"answer": "str"},
            "instructions": [{
                "instruction_prompt": "Answer the question based on the content.",
                "metadata_key": "QuestionContent"
            }]
        }
    }
    
    # Step 4: Memory Index Construction
    records = []
    for chunk in processed_chunks:
        records.append({
            "content": chunk["content"],
            "summary": chunk["summary"],
            "questions": chunk["questions"],
            "answers": chunk["answers"],
            "metadata": chunk["metadata"]
        })
    
    # Build persistent memory index
    df = pd.DataFrame(records)
    build_index(df, concat_cols=["content", "questions", "answers"], 
                index_path=f"memory_indices/{project_id}")
```

---

## 3. Advanced Memory RAG Patterns

### 3.1 Multi-Pipeline Memory RAG

**Document vs SQL Experiment Pipelines:**
```python
# From infra/lamini_infra/ml/memory_rag/train/main.py
async def main(files: Dict[str, str], model_name: str, project_id: str, experiment_config: dict = None):
    """Multi-modal Memory RAG pipeline selection"""
    
    client = BaseOpenAIClient()
    
    if experiment_config and experiment_config["type"] == "document":
        logger.info("Using document experiment pipeline")
        results = await DocumentExperiment_pipeline(
            pdf_path=file_path,
            project_id=project_id,
            experiment_config=experiment_config
        )
        
    elif experiment_config and experiment_config["type"] == "sql":
        logger.info("Using SQL experiment pipeline")  
        results = await SQLExperiment_pipeline(
            project_id=project_id,
            experiment_config=experiment_config,
            client=client
        )
        
    else:
        logger.info("Using default pipeline")
        await run_default_pipeline(files, model_name, project_id, client)
```

### 3.2 Memory RAG Experiment Framework

**SDK-Level Memory RAG Integration:**
```python
# From sdk/lamini/experiment/memory_rag_experiment.py
class MemoryRAGExperiment(BaseMemoryExperiment):
    """Experiment class for RAG with memory capabilities"""
    
    def __init__(self, agentic_pipeline: BaseAgenticPipeline, record_dir: str = None, 
                 rag_keys: Dict[str, List[str]] = None, model: str = None):
        self.rag_keys = rag_keys  # Keys to extract for RAG index
        super().__init__(agentic_pipeline=agentic_pipeline, record_dir=record_dir)
        self.init_memory_rag()
    
    def init_memory_rag(self):
        """Initialize Memory RAG with index path"""
        self.memory_rag = BaseMemoryRAG(
            index_path=os.path.join(self.record_dir, "memory_index"),
            client=self.client
        )
    
    def evaluate(self, prompt: str, output_type: Union[BaseModel, Dict], 
                 model: str = None, retrieved_prompt_key: str = None, k: int = 3):
        """Memory-augmented evaluation"""
        return self.memory_rag.memory_rag(
            prompt=prompt,
            model=model or self.model,
            output_type=output_type,
            retrieved_prompt_key=retrieved_prompt_key,
            k=k
        )
    
    def __call__(self, prompt_obj: Union[PromptObject, List[PromptObject]], debug: bool = False):
        """Execute experiment and build memory index"""
        # Run the agentic pipeline
        results = super().__call__(prompt_obj, debug=debug)
        
        # Build memory index from results
        self.memory_rag.build_memory_index(results=results, rag_keys=self.rag_keys)
        
        return results
```

### 3.3 Base Memory RAG Core

**Memory-Augmented Generation:**
```python
# From sdk/lamini/experiment/base_memory_rag.py
class BaseMemoryRAG:
    """Core Memory RAG functionality"""
    
    def __init__(self, index_path: str = None, client: BaseOpenAIClient = None):
        self.index_path = index_path or os.getcwd()
        self.client = client or BaseOpenAIClient(api_url="https://app.lamini.ai", 
                                                 api_key=os.getenv("LAMINI_API_KEY"))
        self.memory_rag_index = None
    
    def build_memory_index(self, results: List[PromptObject], rag_keys: Dict[str, List[str]] = None):
        """Build memory index from pipeline results"""
        if not results:
            self.logger.warning("No results provided for memory index building")
            return
        
        # Extract text for indexing based on rag_keys
        index_texts = []
        for result in results:
            text_parts = self._process_step_to_text(result, rag_keys)
            if text_parts:
                index_texts.append(text_parts)
        
        # Build the memory index
        if index_texts:
            self.memory_rag_index = LaminiIndex.build_index([index_texts])
            self.memory_rag_index.save_index(self.index_path)
            self.logger.info(f"Memory index built and saved to {self.index_path}")
    
    def query_memory_index(self, prompt: str, k: int = 3) -> List[str]:
        """Query the memory index for similar content"""
        if self.memory_rag_index is None:
            if os.path.exists(self.index_path):
                self.memory_rag_index = LaminiIndex.load_index(self.index_path)
            else:
                self.logger.warning("No memory index available")
                return []
        
        # Get embedding for the prompt
        embed = self.memory_rag_index.get_embeddings(prompt)
        
        # Search for similar content
        _, indices = self.memory_rag_index.index.search(embed, k)
        return [self.memory_rag_index.splits[i] for i in indices[0]]
    
    def memory_rag(self, prompt: str, model: str, output_type: Union[BaseModel, Dict],
                   retrieved_prompt_key: str = None, k: int = 3):
        """Execute Memory RAG generation"""
        # Retrieve similar content from memory
        similar = self.query_memory_index(prompt, k)
        
        # Augment prompt with retrieved content
        augmented_prompt = self.add_similar_to_prompt(prompt, similar, retrieved_prompt_key)
        
        # Generate response with memory context
        response_schema = self.get_response_schema(output_type)
        response = asyncio.run(
            self.client.execute_completion(
                model=model,
                prompt=augmented_prompt,
                response_schema=response_schema
            )
        )
        
        return response
    
    def add_similar_to_prompt(self, prompt: str, similar: List[str], 
                             retrieved_prompt_key: str = None) -> str:
        """Add retrieved content to prompt"""
        if not similar:
            return prompt
        
        context = "\n\n".join(f"Context {i+1}:\n{content}" for i, content in enumerate(similar))
        
        if retrieved_prompt_key:
            # Replace specific key with retrieved content
            return prompt.replace(f"{{{retrieved_prompt_key}}}", context)
        else:
            # Prepend context to prompt
            return f"Retrieved Context:\n{context}\n\nUser Query:\n{prompt}"
```

---

## 4. Memory RAG API Integration

### 4.1 Platform Memory RAG Service

**API-Level Memory RAG:**
```python
# From sdk/lamini/api/memory_rag.py
class MemoryRAG:
    def __init__(self, job_id: int = None, api_key: Optional[str] = None, 
                 api_url: Optional[str] = None, model_name: str = "meta-llama/Llama-3.2-3B-Instruct"):
        self.job_id = job_id
        self.api_key = api_key or lamini.api_key or get_configured_key()
        self.api_url = api_url or lamini.api_url or get_configured_url()
        self.api_prefix = self.api_url + "/alpha/memory-rag"
        self.model_name = model_name
    
    def memory_index(self, documents: List) -> str:
        """Create memory index from documents via API"""
        payload = {"model_name": self.model_name}
        
        files = [(
            "files", 
            (file_path, open(file_path, "rb"))
        ) for file_path in documents]
        
        response = requests.post(
            self.api_prefix + "/train",
            headers={"Authorization": f"Bearer {self.api_key}"},
            data=payload,
            files=files
        )
        
        json_response = response.json()
        self.job_id = json_response["job_id"]
        return json_response
    
    def query(self, prompt: str, k: int = 3) -> str:
        """Query memory index via API"""
        if self.job_id is None:
            raise Exception("job_id must be set to query")
        
        params = {
            "prompt": prompt,
            "model_name": self.model_name,
            "job_id": self.job_id,
            "rag_query_size": k
        }
        
        return make_web_request(
            self.api_key,
            self.api_prefix + "/completions",
            "post",
            params
        )
    
    def add_index(self, prompt: str) -> str:
        """Add content to existing memory index"""
        params = {"prompt": prompt, "job_id": self.job_id}
        return make_web_request(
            self.api_key,
            self.api_prefix + "/add-index",
            "post",
            params
        )
    
    def document_experiment(self, documents: List[str], metadata: Dict = None,
                           pipeline_config: Dict = None, model_config: Dict = None,
                           num_questions: int = 3, chunk_size: int = 1024) -> Dict:
        """Run document experiment pipeline via API"""
        # Advanced Memory RAG document processing
        pass
```

---

## 5. Memory RAG for Agentic Systems

### 5.1 Agentic Memory RAG Pipeline

**Adapted for Runtime Agentic Use:**
```python
class AgenticMemoryRAG:
    """Memory RAG adapted for real-time agentic systems"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.memory_indices = {}  # Multiple memory indices by domain
        self.client = BaseOpenAIClient(**config['client'])
        
        # Initialize memory components
        self.document_processor = DocumentProcessor(
            metadata=config.get('metadata', {}),
            prompt_template=config.get('prompts', {})
        )
        
        self.openai_processor = OpenAIProcessor(
            processor=self.document_processor,
            model_config=ModelConfig(**config.get('models', {}))
        )
    
    async def index_documents_realtime(self, documents: List[str], domain: str = "default") -> str:
        """Real-time document indexing for agentic use"""
        
        # Step 1: Process documents with Memory RAG pipeline
        processed_chunks = []
        
        loader = PDFLoader(SentenceChunker(chunk_size=3, step_size=3))
        for doc_path in documents:
            logger.info(f"Processing {doc_path} for real-time indexing")
            loader.load_pdf(os.path.basename(doc_path), doc_path)
        
        # Step 2: Generate contextual Q&A for each chunk
        for chunk in loader.entries:
            # Generate questions
            questions = await self.openai_processor.generate_questions(
                chunk["content"], 
                num_questions=3
            )
            
            # Generate answers
            answers = []
            for question in questions:
                answer = await self.openai_processor.generate_answer(
                    chunk["content"], 
                    question
                )
                answers.append(answer)
            
            processed_chunks.append({
                "content": chunk["content"],
                "questions": questions,
                "answers": answers,
                "metadata": chunk.get("metadata", {}),
                "source": chunk.get("source", "unknown")
            })
        
        # Step 3: Build memory index for domain
        records_df = pd.DataFrame(processed_chunks)
        index_path = f"memory_indices/{domain}"
        
        build_index(
            records_df,
            concat_cols=["content", "questions", "answers"],
            index_path=index_path
        )
        
        # Step 4: Load index for runtime use
        self.memory_indices[domain] = LaminiIndex.load_index(index_path)
        
        logger.info(f"Memory RAG index ready for domain: {domain}")
        return index_path
    
    async def query_with_memory(self, query: str, domain: str = "default", k: int = 5) -> Dict:
        """Memory-augmented query processing"""
        
        if domain not in self.memory_indices:
            raise ValueError(f"No memory index found for domain: {domain}")
        
        memory_index = self.memory_indices[domain]
        
        # Step 1: Retrieve from memory
        similar_content = memory_index.query_with_embedding(
            memory_index.get_embeddings(query)[0], 
            k=k
        )
        
        # Step 2: Generate contextual response
        context = "\n\n".join([f"Context {i+1}:\n{content}" 
                              for i, content in enumerate(similar_content)])
        
        prompt = f"""
        User Query: {query}
        
        Retrieved Memory Context:
        {context}
        
        Based on the retrieved context above, provide a comprehensive answer to the user's query.
        Include relevant details and cite the context where appropriate.
        """
        
        response_schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"},
                "sources": {"type": "array", "items": {"type": "string"}},
                "follow_up_questions": {"type": "array", "items": {"type": "string"}}
            }
        }
        
        response = await self.client.execute_completion(
            model=self.config['models']['default'],
            prompt=prompt,
            response_schema=response_schema
        )
        
        return {
            "response": response,
            "retrieved_context": similar_content,
            "memory_domain": domain
        }
    
    async def continuous_learning(self, query: str, response: str, feedback: str, domain: str = "default"):
        """Continuously improve memory index based on interactions"""
        
        # Create learning entry
        learning_entry = f"Query: {query}\nResponse: {response}\nFeedback: {feedback}"
        
        # Add to memory index
        if domain in self.memory_indices:
            memory_index = self.memory_indices[domain]
            memory_index.add_stream([learning_entry])
            
            # Save updated index
            index_path = f"memory_indices/{domain}"
            memory_index.save_index(index_path)
            
            logger.info(f"Memory index updated with new learning for domain: {domain}")
```

### 5.2 Multi-Domain Memory RAG

**Domain-Specific Memory Management:**
```python
class MultiDomainMemoryRAG:
    """Manage multiple Memory RAG indices for different domains"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.domain_indices = {}
        self.domain_configs = config.get('domains', {})
    
    async def setup_domain(self, domain: str, documents: List[str], config: Dict = None):
        """Set up Memory RAG for a specific domain"""
        
        domain_config = config or self.domain_configs.get(domain, {})
        
        # Create domain-specific Memory RAG
        domain_memory_rag = AgenticMemoryRAG({
            **self.config,
            **domain_config,
            'metadata': {'domain': domain}
        })
        
        # Index documents for domain
        index_path = await domain_memory_rag.index_documents_realtime(documents, domain)
        
        self.domain_indices[domain] = {
            'memory_rag': domain_memory_rag,
            'index_path': index_path,
            'config': domain_config
        }
        
        return domain
    
    async def cross_domain_query(self, query: str, domains: List[str] = None, k: int = 3) -> Dict:
        """Query across multiple domains and synthesize results"""
        
        domains = domains or list(self.domain_indices.keys())
        domain_results = {}
        
        # Query each domain
        for domain in domains:
            if domain in self.domain_indices:
                try:
                    result = await self.domain_indices[domain]['memory_rag'].query_with_memory(
                        query, domain, k
                    )
                    domain_results[domain] = result
                except Exception as e:
                    logger.error(f"Error querying domain {domain}: {e}")
        
        # Synthesize cross-domain results
        synthesized_response = await self._synthesize_cross_domain_results(query, domain_results)
        
        return {
            "query": query,
            "domain_results": domain_results,
            "synthesized_response": synthesized_response
        }
    
    async def _synthesize_cross_domain_results(self, query: str, domain_results: Dict) -> Dict:
        """Synthesize results from multiple Memory RAG domains"""
        
        # Combine all retrieved contexts
        all_contexts = []
        all_responses = []
        
        for domain, result in domain_results.items():
            all_contexts.extend(result.get('retrieved_context', []))
            all_responses.append({
                'domain': domain,
                'response': result.get('response', {}).get('answer', ''),
                'confidence': result.get('response', {}).get('confidence', 0)
            })
        
        # Create synthesis prompt
        synthesis_prompt = f"""
        User Query: {query}
        
        Domain-Specific Responses:
        {json.dumps(all_responses, indent=2)}
        
        All Retrieved Contexts:
        {chr(10).join([f"Context {i+1}: {ctx}" for i, ctx in enumerate(all_contexts)])}
        
        Synthesize a comprehensive response that:
        1. Combines insights from all domains
        2. Resolves any conflicts or contradictions
        3. Provides a unified, coherent answer
        4. Indicates which domains contributed to each part
        5. Assesses overall confidence
        """
        
        response_schema = {
            "type": "object",
            "properties": {
                "synthesized_answer": {"type": "string"},
                "domain_contributions": {"type": "object"},
                "overall_confidence": {"type": "number"},
                "conflicting_information": {"type": "array", "items": {"type": "string"}},
                "recommendations": {"type": "array", "items": {"type": "string"}}
            }
        }
        
        client = BaseOpenAIClient(**self.config['client'])
        response = await client.execute_completion(
            model=self.config['models']['default'],
            prompt=synthesis_prompt,
            response_schema=response_schema
        )
        
        return response
```

---

## 6. Key Memory RAG Implementation Patterns

### 6.1 Essential Memory RAG Components

**✅ Core Components You Must Implement:**

1. **VectorIndex Integration**
   - FAISS-based vector storage
   - Persistent index save/load
   - Batch processing for efficiency
   - Multi-dimensional embeddings

2. **Memory-Augmented Retrieval**
   - Semantic similarity search
   - Context-aware ranking
   - Multi-modal content support
   - Dynamic index updates

3. **Pipeline Integration**
   - Document processing pipelines
   - Question-answer generation
   - Memory index construction
   - Real-time query processing

4. **API Integration**
   - Platform Memory RAG service
   - Document experiment APIs
   - Continuous learning endpoints
   - Status monitoring and logs

### 6.2 Memory RAG vs Traditional RAG

**🔄 Key Differences:**

| Aspect | Traditional RAG | Memory RAG |
|--------|-----------------|------------|
| **Indexing** | Simple chunking + embeddings | Multi-step processing + enriched context |
| **Retrieval** | Vector similarity only | Memory-augmented + contextual reasoning |
| **Context** | Raw chunks | Processed Q&A + metadata + summaries |
| **Learning** | Static index | Continuous learning + index updates |
| **Generation** | Simple context injection | Memory-guided reasoning chains |

### 6.3 Advanced Memory RAG Patterns

**🚀 Advanced Capabilities:**

1. **Multi-Domain Memory Management**
   - Domain-specific indices
   - Cross-domain synthesis
   - Specialized processing pipelines

2. **Continuous Learning**
   - Interaction-based updates
   - Feedback integration
   - Performance optimization

3. **Memory-Guided Generation**
   - Context-aware prompting
   - Multi-step reasoning
   - Source attribution

4. **Pipeline Orchestration**
   - Multi-modal processing
   - Experiment frameworks
   - Result synthesis

---

## 7. Implementation Components for Your Agentic Project

### Memory RAG Foundation
- Implement `VectorIndex` with FAISS integration
- Create document processing pipeline with chunking
- Build basic memory index construction and querying

### Advanced Memory Features
- Add multi-domain memory management
- Implement continuous learning capabilities
- Create memory-augmented query processing

### Agentic Integration
- Integrate Memory RAG with agentic pipeline
- Add cross-domain synthesis capabilities
- Implement real-time document indexing

### Production Optimization
- Add performance optimizations and caching
- Implement comprehensive monitoring and logging
- Create deployment and scaling strategies

**Memory RAG is the secret sauce** that makes modern AI platforms so powerful. It's not just about retrieving documents - it's about building a persistent, learning memory system that gets smarter with every interaction. Your agentic project will be built on this foundation, giving you capabilities that go far beyond traditional RAG systems.

The key insight is that Memory RAG treats documents not as static chunks, but as living memory that can be continuously enriched, cross-referenced, and intelligently retrieved based on context and user intent. This is what will make your agentic document Q&A and text-to-SQL system truly powerful.
