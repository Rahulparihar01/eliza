# Template Patterns for Agentic Document Q&A and Text-to-SQL Project

## Executive Summary

This document analyzes existing AI platform template patterns to extract key implementation strategies for building a new agentic project that combines **Document Q&A with indexing** and **Text-to-SQL** capabilities. Both existing templates are designed for **training data generation**, but we'll adapt these patterns for **runtime agentic execution** with proper indexing and retrieval.

---

## 1. Core Template Architecture Patterns

### 1.1 Training Data Generation Pipeline (Current Templates)

**Q&A Template Flow:**
```
Documents → Semantic Chunking → Q&A Generation → Validation → Training Data
     ↓              ↓                ↓               ↓            ↓
  PDF Files    Rich Chunks    Question/Answer    Factuality   JSONL Format
                              Generation         Validation    for Training
```

**Text-to-SQL Template Flow:**
```
Schema + Seed Data → Question Variations → SQL Generation → Validation → Training Data
        ↓                    ↓                 ↓              ↓            ↓
   SQLite Schema      Pattern/Variation    Generated SQL   SQL Execution   JSONL Format
   + Examples         Questions            Queries         Validation      for Training
```

### 1.2 Key Pattern Extraction for Agentic Runtime

**What We Need to Adapt:**
1. **Document Processing** → Real-time indexing and retrieval
2. **Question Generation** → User query understanding and decomposition  
3. **Answer Generation** → Context-aware response generation
4. **Validation** → Response quality and accuracy checking
5. **SQL Generation** → Dynamic query generation from natural language
6. **Schema Understanding** → Runtime schema analysis and adaptation

---

## 2. Document Q&A Patterns (Adapted for Agentic Runtime)

### 2.1 Document Processing & Indexing Architecture

**Current Q&A Template Pattern:**
```python
# Document chunking for training data generation
semantic_chunker = PDFSemanticChunker(
    api_key=config['AI_Platform']['api_key']['value'],
    api_base_url=config['AI_Platform']['base_url_inf']['value'],
    embedding_model="text-embedding-3-small",
    window_size=3,
    breakpoint_percentile=95.0
)

chunks = semantic_chunker.chunk_pdf(pdf_file)
```

**Adapted for Agentic Runtime:**
```python
# Real-time document indexing system
class AgenticDocumentIndexer:
    def __init__(self, config):
        self.memory_rag = MemoryRAG(model_name=config['model'])
        self.semantic_chunker = PDFSemanticChunker(**config['chunking'])
        self.vector_index = FAISSIndex()
        
    def index_documents(self, documents: List[str]) -> str:
        """Index documents for real-time retrieval"""
        # 1. Process documents with semantic chunking
        chunks = []
        for doc in documents:
            doc_chunks = self.semantic_chunker.chunk_pdf(doc)
            chunks.extend(doc_chunks)
        
        # 2. Create memory RAG index
        job_id = self.memory_rag.memory_index(documents)
        
        # 3. Build vector index for fast retrieval
        self.vector_index.build_index(chunks)
        
        return job_id
    
    def retrieve_context(self, query: str, k: int = 5) -> List[Dict]:
        """Retrieve relevant context for user query"""
        # Hybrid retrieval: Memory RAG + Vector similarity
        memory_results = self.memory_rag.query(query, k=k)
        vector_results = self.vector_index.similarity_search(query, k=k)
        
        return self.merge_and_rank_results(memory_results, vector_results)
```

### 2.2 Question Understanding & Decomposition

**Current Pattern (Training Data Generation):**
```python
# Static prompt for question generation from chunks
QUESTION_PROMPT = """
Follow these steps closely:
1. Consider the document collection: {product}
2. Review the section title: {title}  
3. Read the overview: {description}
4. Inspect the excerpt: {chunk_text}
5. Craft one clear question that can be answered from the excerpt
"""
```

**Adapted for Agentic Runtime:**
```python
# Dynamic query understanding and decomposition
class QueryDecomposer:
    def __init__(self, config):
        self.client = BaseOpenAIClient(**config['client'])
        self.model = config['model']['default']
    
    async def decompose_query(self, user_query: str, context: Dict) -> Dict:
        """Break down complex queries into answerable sub-questions"""
        prompt = f"""
        User Query: {user_query}
        Document Context: {context['metadata']}
        
        Analyze this query and:
        1. Identify the main information need
        2. Break into sub-questions if complex
        3. Determine required context types
        4. Suggest retrieval strategy
        
        Return structured analysis.
        """
        
        schema = {
            "type": "object",
            "properties": {
                "main_intent": {"type": "string"},
                "sub_questions": {"type": "array", "items": {"type": "string"}},
                "context_requirements": {"type": "array", "items": {"type": "string"}},
                "retrieval_strategy": {"type": "string"}
            }
        }
        
        return await self.client.execute_completion(
            model=self.model,
            prompt=prompt,
            response_schema=schema
        )
```

### 2.3 Context-Aware Answer Generation

**Current Pattern (Training):**
```python
# Static answer generation prompt
ANSWER_PROMPT = """
Context: {chunk_text}
Question: {question}

Provide a clear answer with citations [1], [2], etc.
Output only the answer text.
"""
```

**Adapted for Agentic Runtime:**
```python
# Dynamic context-aware answer generation
class ContextualAnswerGenerator:
    def __init__(self, config):
        self.client = BaseOpenAIClient(**config['client'])
        self.model = config['model']['default']
    
    async def generate_answer(self, query: str, contexts: List[Dict], metadata: Dict) -> Dict:
        """Generate contextual answer from retrieved documents"""
        
        # Format contexts with source attribution
        context_text = self.format_contexts(contexts)
        
        prompt = f"""
        User Query: {query}
        
        Document Contexts:
        {context_text}
        
        Document Metadata:
        - Collection: {metadata.get('product', 'Unknown')}
        - Domain: {metadata.get('keywords', [])}
        
        Generate a comprehensive answer that:
        1. Directly addresses the user's question
        2. Synthesizes information from multiple sources
        3. Provides proper citations [Doc1], [Doc2], etc.
        4. Indicates confidence level and limitations
        5. Suggests follow-up questions if relevant
        
        Structure your response with clear sections.
        """
        
        schema = {
            "type": "object", 
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"},
                "sources": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "string"},
                "follow_up_questions": {"type": "array", "items": {"type": "string"}}
            }
        }
        
        return await self.client.execute_completion(
            model=self.model,
            prompt=prompt,
            response_schema=schema
        )
```

---

## 3. Text-to-SQL Patterns (Adapted for Agentic Runtime)

### 3.1 Schema Understanding & Analysis

**Current Pattern (Training):**
```python
# Static schema loading for training data generation
def load_schema_from_sqlite(sqlite_file):
    with sqlite3.connect(sqlite_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
        return "\n".join(row[0] for row in cursor.fetchall())
```

**Adapted for Agentic Runtime:**
```python
# Dynamic schema analysis and understanding
class SchemaAnalyzer:
    def __init__(self, config):
        self.client = BaseOpenAIClient(**config['client'])
        self.model = config['model']['default']
        
    async def analyze_schema(self, db_connection: str) -> Dict:
        """Analyze database schema for natural language querying"""
        
        # Extract schema information
        schema_info = self.extract_schema_metadata(db_connection)
        
        prompt = f"""
        Database Schema Analysis:
        {schema_info['ddl']}
        
        Sample Data:
        {schema_info['samples']}
        
        Analyze this schema and provide:
        1. Business domain and purpose
        2. Key entities and relationships
        3. Common query patterns
        4. Important constraints and business rules
        5. Natural language description of each table
        6. Suggested query templates for common operations
        """
        
        schema = {
            "type": "object",
            "properties": {
                "domain": {"type": "string"},
                "entities": {"type": "array", "items": {"type": "object"}},
                "relationships": {"type": "array", "items": {"type": "object"}},
                "query_patterns": {"type": "array", "items": {"type": "string"}},
                "business_rules": {"type": "array", "items": {"type": "string"}},
                "table_descriptions": {"type": "object"},
                "query_templates": {"type": "array", "items": {"type": "object"}}
            }
        }
        
        analysis = await self.client.execute_completion(
            model=self.model,
            prompt=prompt,
            response_schema=schema
        )
        
        return analysis
```

### 3.2 Natural Language to SQL Translation

**Current Pattern (Training):**
```python
# Static SQL generation for training examples
sql_gen = SchemaToSQLGenerator(
    model="meta-llama/Llama-3.1-8B-Instruct",
    schema=schema,
    db_type="sqlite",
    instruction="""Generate SQL query that answers the question..."""
)
```

**Adapted for Agentic Runtime:**
```python
# Dynamic SQL generation with validation
class NLToSQLAgent:
    def __init__(self, config):
        self.client = BaseOpenAIClient(**config['client'])
        self.model = config['model']['default']
        self.schema_analyzer = SchemaAnalyzer(config)
        
    async def generate_sql(self, natural_query: str, schema_analysis: Dict) -> Dict:
        """Generate SQL from natural language with multi-step reasoning"""
        
        # Step 1: Query understanding and decomposition
        query_analysis = await self.analyze_query_intent(natural_query, schema_analysis)
        
        # Step 2: SQL generation with reasoning
        sql_result = await self.generate_sql_with_reasoning(
            natural_query, 
            query_analysis, 
            schema_analysis
        )
        
        # Step 3: SQL validation and correction
        validated_sql = await self.validate_and_correct_sql(
            sql_result, 
            schema_analysis
        )
        
        return validated_sql
    
    async def generate_sql_with_reasoning(self, query: str, analysis: Dict, schema: Dict) -> Dict:
        """Generate SQL with step-by-step reasoning"""
        
        prompt = f"""
        Natural Language Query: {query}
        
        Query Analysis: {analysis}
        
        Database Schema:
        {schema['table_descriptions']}
        
        Available Tables and Columns:
        {schema['entities']}
        
        Generate SQL query with reasoning:
        1. Identify required tables and joins
        2. Determine filtering conditions  
        3. Specify aggregations or calculations
        4. Consider ordering and limits
        5. Write the final SQL query
        
        Provide step-by-step reasoning and final SQL.
        """
        
        schema_def = {
            "type": "object",
            "properties": {
                "reasoning_steps": {"type": "array", "items": {"type": "string"}},
                "required_tables": {"type": "array", "items": {"type": "string"}},
                "join_conditions": {"type": "array", "items": {"type": "string"}},
                "filters": {"type": "array", "items": {"type": "string"}},
                "sql_query": {"type": "string"},
                "confidence": {"type": "number"}
            }
        }
        
        return await self.client.execute_completion(
            model=self.model,
            prompt=prompt,
            response_schema=schema_def
        )
```

### 3.3 SQL Validation & Execution

**Current Pattern (Training):**
```python
# Simple SQL validation for training data
class SQLValidator:
    def validate_sql(self, sql_query: str, schema: str) -> bool:
        # Basic syntax and schema validation
        pass
```

**Adapted for Agentic Runtime:**
```python
# Comprehensive SQL validation and safe execution
class SQLExecutionAgent:
    def __init__(self, config):
        self.client = BaseOpenAIClient(**config['client'])
        self.model = config['model']['default']
        self.max_rows = config.get('max_rows', 1000)
        
    async def validate_and_execute_sql(self, sql_query: str, db_connection: str, schema: Dict) -> Dict:
        """Safely validate and execute SQL with result interpretation"""
        
        # Step 1: Security validation
        security_check = self.validate_sql_security(sql_query)
        if not security_check['safe']:
            return {"error": "SQL query failed security validation", "details": security_check}
        
        # Step 2: Syntax and schema validation  
        syntax_check = await self.validate_sql_syntax(sql_query, schema)
        if not syntax_check['valid']:
            return {"error": "SQL syntax or schema error", "details": syntax_check}
        
        # Step 3: Safe execution with limits
        try:
            results = self.execute_sql_safely(sql_query, db_connection)
            
            # Step 4: Result interpretation
            interpretation = await self.interpret_results(sql_query, results, schema)
            
            return {
                "success": True,
                "sql_query": sql_query,
                "results": results,
                "interpretation": interpretation,
                "row_count": len(results)
            }
            
        except Exception as e:
            return {"error": f"SQL execution failed: {str(e)}"}
    
    async def interpret_results(self, sql_query: str, results: List[Dict], schema: Dict) -> Dict:
        """Interpret SQL results in natural language"""
        
        if not results:
            return {"summary": "No results found", "insights": []}
        
        # Sample results for interpretation (limit for prompt size)
        sample_results = results[:10]
        
        prompt = f"""
        SQL Query: {sql_query}
        
        Query Results (showing first 10 of {len(results)} rows):
        {json.dumps(sample_results, indent=2)}
        
        Schema Context: {schema.get('domain', 'Unknown')}
        
        Interpret these results:
        1. Summarize what the query found
        2. Highlight key insights or patterns
        3. Note any limitations or caveats
        4. Suggest related questions or analysis
        """
        
        schema_def = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "key_insights": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "string"},
                "suggested_followups": {"type": "array", "items": {"type": "string"}}
            }
        }
        
        return await self.client.execute_completion(
            model=self.model,
            prompt=prompt,
            response_schema=schema_def
        )
```

---

## 4. Agentic Pipeline Architecture

### 4.1 Multi-Agent Orchestration Pattern

**Adapted from Template Pipeline Patterns:**
```python
# Unified agentic pipeline for both Q&A and SQL
class AgenticQueryPipeline:
    def __init__(self, config):
        self.config = config
        
        # Document Q&A agents
        self.document_indexer = AgenticDocumentIndexer(config['document_qa'])
        self.query_decomposer = QueryDecomposer(config['document_qa'])
        self.answer_generator = ContextualAnswerGenerator(config['document_qa'])
        
        # SQL agents  
        self.schema_analyzer = SchemaAnalyzer(config['text_to_sql'])
        self.nl_to_sql_agent = NLToSQLAgent(config['text_to_sql'])
        self.sql_execution_agent = SQLExecutionAgent(config['text_to_sql'])
        
        # Orchestration
        self.query_router = QueryRouter(config)
        self.response_synthesizer = ResponseSynthesizer(config)
    
    async def process_query(self, user_query: str, context: Dict) -> Dict:
        """Main pipeline for processing user queries"""
        
        # Step 1: Route query to appropriate agent(s)
        routing_decision = await self.query_router.route_query(user_query, context)
        
        results = {}
        
        # Step 2: Execute document Q&A if needed
        if routing_decision['needs_document_qa']:
            doc_results = await self.process_document_query(user_query, context)
            results['document_qa'] = doc_results
        
        # Step 3: Execute SQL generation if needed
        if routing_decision['needs_sql']:
            sql_results = await self.process_sql_query(user_query, context)
            results['sql_analysis'] = sql_results
        
        # Step 4: Synthesize final response
        final_response = await self.response_synthesizer.synthesize(
            user_query, 
            results, 
            routing_decision
        )
        
        return final_response
    
    async def process_document_query(self, query: str, context: Dict) -> Dict:
        """Process document-based queries"""
        
        # Decompose query
        query_analysis = await self.query_decomposer.decompose_query(query, context)
        
        # Retrieve relevant contexts
        contexts = self.document_indexer.retrieve_context(
            query, 
            k=context.get('retrieval_k', 5)
        )
        
        # Generate answer
        answer = await self.answer_generator.generate_answer(
            query, 
            contexts, 
            context['metadata']
        )
        
        return {
            "query_analysis": query_analysis,
            "retrieved_contexts": contexts,
            "answer": answer
        }
    
    async def process_sql_query(self, query: str, context: Dict) -> Dict:
        """Process SQL-related queries"""
        
        # Analyze schema if not cached
        if 'schema_analysis' not in context:
            schema_analysis = await self.schema_analyzer.analyze_schema(
                context['db_connection']
            )
            context['schema_analysis'] = schema_analysis
        
        # Generate SQL
        sql_result = await self.nl_to_sql_agent.generate_sql(
            query, 
            context['schema_analysis']
        )
        
        # Execute and interpret
        execution_result = await self.sql_execution_agent.validate_and_execute_sql(
            sql_result['sql_query'],
            context['db_connection'],
            context['schema_analysis']
        )
        
        return {
            "sql_generation": sql_result,
            "execution_result": execution_result
        }
```

### 4.2 Query Routing Intelligence

```python
class QueryRouter:
    def __init__(self, config):
        self.client = BaseOpenAIClient(**config['client'])
        self.model = config['model']['default']
    
    async def route_query(self, user_query: str, context: Dict) -> Dict:
        """Intelligently route queries to appropriate agents"""
        
        prompt = f"""
        User Query: {user_query}
        
        Available Capabilities:
        1. Document Q&A: Search and answer questions from indexed documents
        2. SQL Analysis: Generate and execute SQL queries on structured data
        
        Context:
        - Has documents indexed: {bool(context.get('document_index'))}
        - Has database connection: {bool(context.get('db_connection'))}
        - Document types: {context.get('document_types', [])}
        - Database schema: {bool(context.get('schema_analysis'))}
        
        Analyze this query and determine:
        1. Does it need document search and Q&A?
        2. Does it need SQL generation and data analysis?
        3. What's the primary intent?
        4. What information is needed?
        5. How should results be combined?
        """
        
        schema = {
            "type": "object",
            "properties": {
                "needs_document_qa": {"type": "boolean"},
                "needs_sql": {"type": "boolean"},
                "primary_intent": {"type": "string"},
                "information_needs": {"type": "array", "items": {"type": "string"}},
                "result_combination_strategy": {"type": "string"},
                "confidence": {"type": "number"}
            }
        }
        
        return await self.client.execute_completion(
            model=self.model,
            prompt=prompt,
            response_schema=schema
        )
```

---

## 5. Configuration-Driven Template System

### 5.1 Unified Configuration Schema

**Adapted from Template YAML Patterns:**
```yaml
# agentic_project.yml - Unified configuration
AI_Platform:
  api_key:
    value: ${OPENAI_API_KEY}
    description: AI platform API key
  base_url:
    value: ${AI_PLATFORM_BASE_URL:-https://api.openai.com/v1}
    description: AI platform base URL
  base_url_inf:
    value: ${AI_PLATFORM_BASE_URL_INF:-https://api.openai.com/v1}
    description: AI platform inference URL

Project:
  name:
    value: agentic_qa_sql
    description: Project name
  description:
    value: Agentic document Q&A and text-to-SQL system
  mode:
    value: runtime  # vs 'training' in templates
    description: Execution mode

Models:
  default:
    value: meta-llama/Llama-3.1-8B-Instruct
    description: Default model for reasoning
  embedding:
    value: sentence-transformers/all-MiniLM-L6-v2
    description: Embedding model for document indexing

DocumentQA:
  indexing:
    chunk_strategy: semantic
    window_size: 3
    breakpoint_percentile: 95.0
    max_chunk_size: 1024
  retrieval:
    k: 5
    rerank: true
    hybrid_search: true
  generation:
    max_context_length: 4096
    include_sources: true
    confidence_threshold: 0.7

TextToSQL:
  schema_analysis:
    include_samples: true
    max_sample_rows: 10
    analyze_relationships: true
  sql_generation:
    max_complexity: medium
    include_reasoning: true
    validate_syntax: true
  execution:
    max_rows: 1000
    timeout_seconds: 30
    safe_mode: true

Agents:
  query_router:
    model: meta-llama/Llama-3.1-8B-Instruct
    confidence_threshold: 0.8
  response_synthesizer:
    model: meta-llama/Llama-3.1-8B-Instruct
    max_response_length: 2048
```

### 5.2 Dynamic Agent Configuration

```python
# Agent factory pattern from templates
class AgentFactory:
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        
    def create_pipeline(self) -> AgenticQueryPipeline:
        """Create configured pipeline from YAML"""
        return AgenticQueryPipeline(self.config)
    
    def create_document_indexer(self) -> AgenticDocumentIndexer:
        """Create document indexer with config"""
        return AgenticDocumentIndexer(self.config['DocumentQA'])
    
    def create_sql_agent(self) -> NLToSQLAgent:
        """Create SQL agent with config"""
        return NLToSQLAgent(self.config['TextToSQL'])
```

---

## 6. Key Implementation Patterns Summary

### 6.1 What to Adapt from Q&A Template

**✅ Keep & Adapt:**
1. **Semantic chunking approach** → Real-time indexing
2. **Multi-step prompt engineering** → Agentic reasoning chains
3. **Context-grounded generation** → RAG with proper attribution
4. **Validation patterns** → Response quality checking
5. **Configuration-driven design** → Runtime agent configuration

**🔄 Transform:**
- Training data generation → Runtime query processing
- Static prompt templates → Dynamic prompt construction
- Batch processing → Real-time response generation
- File-based storage → Vector/memory indexing

### 6.2 What to Adapt from Text-to-SQL Template

**✅ Keep & Adapt:**
1. **Schema analysis patterns** → Dynamic schema understanding
2. **Multi-variation generation** → Query decomposition strategies
3. **SQL validation logic** → Safe execution framework
4. **Pipeline orchestration** → Multi-agent coordination
5. **Error handling and debugging** → Self-correcting SQL generation

**🔄 Transform:**
- Training example generation → Runtime SQL generation
- Static schema loading → Dynamic schema analysis
- Batch SQL validation → Real-time execution with safety
- Pattern-based variations → Intent-based query understanding

### 6.3 New Agentic Capabilities to Add

**🚀 Enhance Beyond Templates:**
1. **Query routing intelligence** → Multi-modal query understanding
2. **Response synthesis** → Combining document and SQL results
3. **Memory and context management** → Conversation continuity
4. **Real-time indexing** → Dynamic document addition
5. **Security and safety** → SQL injection prevention, data privacy
6. **Performance optimization** → Caching, parallel processing
7. **User experience** → Interactive clarification, progressive disclosure

---

## 7. Implementation Components

### Core Agent Framework
- Implement base agent classes and configuration system
- Create query routing and response synthesis framework
- Set up basic document indexing with Memory RAG integration

### Document Q&A Agents
- Build document indexer with semantic chunking
- Implement query decomposer and context retrieval
- Create contextual answer generator with source attribution

### Text-to-SQL Agents
- Develop schema analyzer and natural language SQL generator
- Implement SQL validation and safe execution framework
- Create result interpretation and explanation system

### Pipeline Integration
- Integrate document Q&A and SQL agents into unified pipeline
- Implement intelligent query routing and response synthesis
- Add conversation memory and context management

### Advanced Features
- Add real-time document indexing and schema adaptation
- Implement security, safety, and performance optimizations
- Create comprehensive testing and evaluation framework

This analysis provides a solid foundation for building your agentic project by adapting the proven patterns from the existing templates while adding the runtime intelligence and multi-modal capabilities needed for your use case.
