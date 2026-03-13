# Data Analyst Agent - Implementation Plan

## Executive Summary

This document outlines the implementation plan for a new "Data Analyst Agent" feature that enables users to ask natural language questions about insurance data and receive rich insights including SQL-generated visualizations, scrollable data tables, summaries, and text-based insights.

**Key Technologies:**
- **Vanna AI** for Text-to-SQL generation
- **PostgreSQL** separate database (`insurance_demo_db`)
- **FastAPI** backend routes
- **React/TypeScript** frontend interface
- **Chart.js/Recharts** for visualizations

---

## 1. Architecture Overview

### 1.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Data Analyst Agent Page                             │  │
│  │  - Data Source Selector (Insurance, etc.)           │  │
│  │  - Chat Interface                                    │  │
│  │  - Results Display (Charts, Tables, Insights)       │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Backend API (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /v1/data-analyst/questions                          │  │
│  │  /v1/data-analyst/questions/{id}/result             │  │
│  │  /v1/data-analyst/questions/{id}/status              │  │
│  └──────────────────────────────────────────────────────┘  │
│                         │                                   │
│                         ▼                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  DataAnalystService                                  │  │
│  │  - Question management                               │  │
│  │  - Vanna AI integration                              │  │
│  │  - SQL execution                                     │  │
│  │  - Result formatting                                 │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         Vanna AI Integration Layer                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  VannaAgent                                          │  │
│  │  - Schema training                                   │  │
│  │  - SQL generation                                    │  │
│  │  - Query validation                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         PostgreSQL (insurance_demo_db)                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Schemas: core, auto_insurance, property_insurance, │  │
│  │          analytics                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow

1. **User submits question** → Frontend sends POST `/v1/data-analyst/questions`
2. **Backend creates question record** → Status: PENDING
3. **Celery task processes question**:
   - Vanna AI generates SQL from natural language
   - SQL is validated and executed
   - Results are formatted (JSON with metadata)
   - Status updated: COMPLETED
4. **Frontend polls/SSE** → GET `/v1/data-analyst/questions/{id}/status`
5. **Results displayed** → Charts, tables, insights rendered

---

## 2. Database Setup

### 2.1 Create Insurance Demo Database

**Location:** `scripts/setup_insurance_demo_db.sh`

```bash
#!/bin/bash
# Create insurance_demo_db database and schemas

psql -U user -d postgres <<EOF
CREATE DATABASE insurance_demo_db;
\c insurance_demo_db

-- Create schemas
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS auto_insurance;
CREATE SCHEMA IF NOT EXISTS property_insurance;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Run all DDL files
\i /app/scripts/insurance_ddl/core_party.sql
\i /app/scripts/insurance_ddl/core_agent.sql
\i /app/scripts/insurance_ddl/auto_policy_auto.sql
\i /app/scripts/insurance_ddl/auto_claim_auto.sql
-- ... (all other DDL files)
\i /app/scripts/insurance_ddl/analytics_customer_360_view.sql

-- Load sample data from Excel files
-- (Python script to load Excel data)
EOF
```

### 2.2 Database Connection Configuration

**Location:** `src/core/config.py`

Add new database URL:
```python
# Insurance demo database (separate from main app database)
insurance_demo_db_url: str = Field(
    default="postgresql://user:password@postgres:5432/insurance_demo_db",
    alias="INSURANCE_DEMO_DB_URL"
)
```

**Location:** `src/models/insurance_database.py` (NEW)

```python
"""
Insurance Demo Database Connection
Separate database connection for insurance analytics
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Insurance database engine and session factory
insurance_engine = None
InsuranceSessionLocal = None


def init_insurance_database():
    """Initialize insurance demo database connection."""
    global insurance_engine, InsuranceSessionLocal
    
    settings = get_settings()
    
    insurance_engine = create_engine(
        settings.insurance_demo_db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.debug
    )
    
    InsuranceSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=insurance_engine
    )
    
    logger.info("Insurance demo database initialized successfully")


def get_insurance_db() -> Generator[Session, None, None]:
    """
    Dependency to get insurance database session.
    
    Yields:
        Session: SQLAlchemy session for insurance_demo_db
    """
    if InsuranceSessionLocal is None:
        init_insurance_database()
    
    db = InsuranceSessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 3. Vanna AI Integration

### 3.1 Install Vanna

**Location:** `requirements.txt`

```
vanna>=0.7.0
```

### 3.2 Vanna Service Implementation

**Location:** `src/services/vanna_service.py` (NEW)

```python
"""
Vanna AI Service for Text-to-SQL Generation
"""
from typing import Optional, Dict, Any, List
import logging
from vanna import VannaDefault
from vanna.remote import VannaDefault as RemoteVanna

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__, component="vanna.service")

class VannaService:
    """
    Service for managing Vanna AI text-to-SQL generation.
    
    Handles:
    - Schema training (DDL, documentation, example Q&A)
    - SQL generation from natural language
    - Query validation
    """
    
    def __init__(self, database_url: str, model: Optional[str] = None):
        """
        Initialize Vanna service.
        
        Args:
            database_url: PostgreSQL connection string
            model: LLM model to use (defaults to OpenAI GPT-4)
        """
        self.database_url = database_url
        self.model = model or get_settings().default_llm_model
        
        # Initialize Vanna (using local instance)
        # For production, consider Vanna Cloud API
        self.vanna = VannaDefault(model=self.model)
        
        # Connect to database
        self.vanna.connect_to_postgres(
            host=database_url.split('@')[1].split(':')[0],
            dbname=database_url.split('/')[-1],
            user=database_url.split('//')[1].split(':')[0],
            password=database_url.split(':')[2].split('@')[0],
            port=int(database_url.split(':')[3].split('/')[0])
        )
        
        logger.info("Vanna service initialized", model=self.model)
    
    def train_on_ddl(self, ddl_statements: List[str]) -> None:
        """
        Train Vanna on database schema DDL statements.
        
        Args:
            ddl_statements: List of CREATE TABLE/VIEW statements
        """
        for ddl in ddl_statements:
            self.vanna.train(ddl=ddl)
        
        logger.info("Vanna trained on DDL", statement_count=len(ddl_statements))
    
    def train_on_documentation(self, documentation: str) -> None:
        """
        Train Vanna on domain documentation.
        
        Args:
            documentation: Insurance domain documentation text
        """
        self.vanna.train(documentation=documentation)
        logger.info("Vanna trained on documentation")
    
    def train_on_question_sql(self, question: str, sql: str) -> None:
        """
        Train Vanna on example question-SQL pairs.
        
        Args:
            question: Natural language question
            sql: Corresponding SQL query
        """
        self.vanna.train(question=question, sql=sql)
        logger.info("Vanna trained on question-SQL pair")
    
    def generate_sql(self, question: str) -> str:
        """
        Generate SQL query from natural language question.
        
        Args:
            question: Natural language question
            
        Returns:
            Generated SQL query string
        """
        try:
            sql = self.vanna.generate_sql(question=question)
            logger.info("SQL generated", question_length=len(question), sql_length=len(sql))
            return sql
        except Exception as e:
            logger.error("SQL generation failed", error=str(e), exc_info=True)
            raise
    
    def run_sql(self, sql: str) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results.
        
        Args:
            sql: SQL query string
            
        Returns:
            List of result dictionaries
        """
        try:
            results = self.vanna.run_sql(sql=sql)
            logger.info("SQL executed", result_count=len(results) if results else 0)
            return results
        except Exception as e:
            logger.error("SQL execution failed", error=str(e), sql=sql, exc_info=True)
            raise
    
    def generate_plotly_code(self, question: str, sql: str, results: List[Dict[str, Any]]) -> Optional[str]:
        """
        Generate Plotly visualization code for results.
        
        Args:
            question: Original question
            sql: SQL query used
            results: Query results
            
        Returns:
            Plotly code string (optional)
        """
        try:
            plotly_code = self.vanna.generate_plotly_code(
                question=question,
                sql=sql,
                df=results  # Vanna expects pandas DataFrame
            )
            return plotly_code
        except Exception as e:
            logger.warning("Plotly code generation failed", error=str(e))
            return None
```

### 3.3 Initial Training Setup

**Location:** `scripts/train_vanna_insurance.py` (NEW)

```python
"""
Train Vanna AI on insurance database schema and domain knowledge.
"""
import os
from pathlib import Path
from src.services.vanna_service import VannaService
from src.core.config import get_settings

def main():
    settings = get_settings()
    vanna_service = VannaService(settings.insurance_demo_db_url)
    
    # Load all DDL files
    ddl_dir = Path("design_docs/analytics_insurance/insurance_demo_ddl")
    ddl_files = [
        "core_party.sql",
        "core_agent.sql",
        "auto_policy_auto.sql",
        "auto_claim_auto.sql",
        # ... all DDL files
        "analytics_customer_360_view.sql"
    ]
    
    for ddl_file in ddl_files:
        ddl_path = ddl_dir / ddl_file
        if ddl_path.exists():
            with open(ddl_path, 'r') as f:
                ddl_content = f.read()
                vanna_service.train_on_ddl([ddl_content])
    
    # Train on domain documentation
    domain_docs = """
    Insurance Analytics Domain:
    - Loss ratio = total incurred claims / earned premium
    - Customer segments: HNW (High Net Worth), personal standard, SMB (Small Medium Business)
    - Lines of business: AUTO, HOME, SMALL_COMMERCIAL
    - Underwriting tiers: PREFERRED, STANDARD, NON_STANDARD
    - Claim statuses: OPEN, CLOSED, PENDING
    """
    vanna_service.train_on_documentation(domain_docs)
    
    # Train on example questions from persona_questions_updated.md
    example_questions = [
        ("What is the loss ratio by line of business?", 
         "SELECT line_of_business, SUM(total_incurred_amount) / SUM(earned_premium_to_date) AS loss_ratio FROM ..."),
        # ... more examples
    ]
    
    for question, sql in example_questions:
        vanna_service.train_on_question_sql(question, sql)
    
    print("Vanna training completed!")

if __name__ == "__main__":
    main()
```

---

## 4. Backend Implementation

### 4.1 Database Models

**Location:** `src/models/data_analyst.py` (NEW)

```python
"""
Data Analyst Agent Database Models
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from enum import Enum
from typing import Optional, Dict, Any

from src.models.database import BaseModel

class DataSourceType(str, Enum):
    """Supported data source types."""
    INSURANCE = "insurance"
    # Future: FINANCE, RETAIL, etc.

class QuestionStatus(str, Enum):
    """Question processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DataAnalystQuestion(BaseModel):
    """
    Data Analyst question record.
    """
    __tablename__ = "data_analyst_questions"
    
    id = Column(Integer, primary_key=True)
    question_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    
    # Question details
    data_source_type = Column(SQLEnum(DataSourceType), nullable=False)
    original_question = Column(Text, nullable=False)
    
    # Processing
    status = Column(SQLEnum(QuestionStatus), nullable=False, default=QuestionStatus.PENDING)
    generated_sql = Column(Text, nullable=True)
    sql_error = Column(Text, nullable=True)
    
    # Results
    result_data = Column(JSON, nullable=True)  # Raw query results
    result_metadata = Column(JSON, nullable=True)  # Charts, insights, etc.
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
```

### 4.2 Service Layer

**Location:** `src/services/data_analyst_service.py` (NEW)

```python
"""
Data Analyst Service
Handles question processing, SQL generation, and result formatting.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.models.data_analyst import (
    DataAnalystQuestion,
    DataSourceType,
    QuestionStatus
)
from src.services.vanna_service import VannaService
from src.core.config import get_settings
from src.core.logging import get_logger
import uuid
from datetime import datetime

logger = get_logger(__name__, component="data.analyst.service")

class DataAnalystService:
    """Service for data analyst agent operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        
        # Initialize Vanna service for each data source
        self._vanna_services: Dict[str, VannaService] = {}
    
    def _get_vanna_service(self, data_source_type: DataSourceType) -> VannaService:
        """Get or create Vanna service for data source."""
        if data_source_type.value not in self._vanna_services:
            db_url = self.settings.insurance_demo_db_url
            self._vanna_services[data_source_type.value] = VannaService(db_url)
        
        return self._vanna_services[data_source_type.value]
    
    def create_question(
        self,
        user_id: int,
        customer_id: str,
        data_source_type: DataSourceType,
        question: str
    ) -> DataAnalystQuestion:
        """Create a new question record."""
        question_id = str(uuid.uuid4())
        
        question_record = DataAnalystQuestion(
            question_id=question_id,
            user_id=user_id,
            customer_id=customer_id,
            data_source_type=data_source_type,
            original_question=question,
            status=QuestionStatus.PENDING
        )
        
        self.db.add(question_record)
        self.db.commit()
        self.db.refresh(question_record)
        
        logger.info(
            "question_created",
            question_id=question_id,
            user_id=user_id,
            data_source_type=data_source_type.value
        )
        
        return question_record
    
    def process_question(self, question_id: str) -> Dict[str, Any]:
        """
        Process a question: generate SQL, execute, format results.
        
        Returns:
            Dict with result_data and result_metadata
        """
        question = self.db.query(DataAnalystQuestion).filter(
            DataAnalystQuestion.question_id == question_id
        ).first()
        
        if not question:
            raise ValueError(f"Question {question_id} not found")
        
        # Update status
        question.status = QuestionStatus.PROCESSING
        self.db.commit()
        
        try:
            # Get Vanna service for data source
            vanna_service = self._get_vanna_service(question.data_source_type)
            
            # Generate SQL
            generated_sql = vanna_service.generate_sql(question.original_question)
            question.generated_sql = generated_sql
            self.db.commit()
            
            # Execute SQL
            results = vanna_service.run_sql(generated_sql)
            
            # Format results
            result_data = self._format_results(results)
            result_metadata = self._generate_metadata(
                question.original_question,
                generated_sql,
                results
            )
            
            # Update question with results
            question.result_data = result_data
            question.result_metadata = result_metadata
            question.status = QuestionStatus.COMPLETED
            question.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(
                "question_processed",
                question_id=question_id,
                result_count=len(results) if results else 0
            )
            
            return {
                "result_data": result_data,
                "result_metadata": result_metadata
            }
            
        except Exception as e:
            question.status = QuestionStatus.FAILED
            question.sql_error = str(e)
            self.db.commit()
            
            logger.error(
                "question_processing_failed",
                question_id=question_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def _format_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format SQL results for frontend display."""
        if not results:
            return {"rows": [], "columns": []}
        
        # Extract column names from first row
        columns = list(results[0].keys()) if results else []
        
        # Convert to list of lists for table display
        rows = [[row[col] for col in columns] for row in results]
        
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows)
        }
    
    def _generate_metadata(
        self,
        question: str,
        sql: str,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate metadata for results: charts, insights, summaries.
        
        This could use LLM to generate insights from the data.
        """
        metadata = {
            "sql": sql,
            "chart_suggestions": self._suggest_charts(results),
            "insights": self._generate_insights(question, results),
            "summary": self._generate_summary(results)
        }
        
        return metadata
    
    def _suggest_charts(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Suggest appropriate chart types based on data structure."""
        if not results:
            return []
        
        suggestions = []
        columns = list(results[0].keys()) if results else []
        
        # Simple heuristics for chart suggestions
        # Could be enhanced with ML-based detection
        numeric_cols = [col for col in columns if self._is_numeric(results, col)]
        categorical_cols = [col for col in columns if not self._is_numeric(results, col)]
        
        if len(numeric_cols) >= 2:
            suggestions.append({"type": "line", "x": categorical_cols[0] if categorical_cols else None, "y": numeric_cols})
        
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            suggestions.append({"type": "bar", "x": categorical_cols[0], "y": numeric_cols[0]})
        
        return suggestions
    
    def _is_numeric(self, results: List[Dict[str, Any]], column: str) -> bool:
        """Check if column contains numeric data."""
        if not results:
            return False
        
        for row in results[:10]:  # Sample first 10 rows
            value = row.get(column)
            if value is None:
                continue
            if not isinstance(value, (int, float)):
                return False
        
        return True
    
    def _generate_insights(self, question: str, results: List[Dict[str, Any]]) -> str:
        """Generate text insights from results (placeholder - could use LLM)."""
        # TODO: Use LLM to generate insights
        return f"Query returned {len(results)} rows of data."
    
    def _generate_summary(self, results: List[Dict[str, Any]]) -> str:
        """Generate summary statistics."""
        if not results:
            return "No data returned."
        
        return f"Query returned {len(results)} rows."
    
    def get_question(self, question_id: str) -> Optional[DataAnalystQuestion]:
        """Get question by ID."""
        return self.db.query(DataAnalystQuestion).filter(
            DataAnalystQuestion.question_id == question_id
        ).first()
    
    def list_questions(
        self,
        user_id: Optional[int] = None,
        customer_id: Optional[str] = None,
        data_source_type: Optional[DataSourceType] = None,
        limit: int = 20,
        offset: int = 0
    ) -> tuple[List[DataAnalystQuestion], int]:
        """List questions with filters."""
        query = self.db.query(DataAnalystQuestion)
        
        if user_id:
            query = query.filter(DataAnalystQuestion.user_id == user_id)
        
        if customer_id:
            query = query.filter(DataAnalystQuestion.customer_id == customer_id)
        
        if data_source_type:
            query = query.filter(DataAnalystQuestion.data_source_type == data_source_type)
        
        total = query.count()
        questions = query.order_by(
            DataAnalystQuestion.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return questions, total
```

### 4.3 API Routes

**Location:** `src/api/routes/data_analyst.py` (NEW)

```python
"""
Data Analyst Agent API Routes
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from src.models import get_db
from src.models.data_analyst import DataSourceType, QuestionStatus
from src.services.data_analyst_service import DataAnalystService
from src.middleware.authorization import AuthorizationMiddleware
from src.api.schemas.data_analyst import (
    QuestionSubmitRequest,
    QuestionSubmitResponse,
    QuestionResponse,
    QuestionListResponse,
    QuestionStatusResponse,
    AnalysisResultResponse
)
from src.core.logging import get_logger

logger = get_logger(__name__, component="data.analyst.api")
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/v1/data-analyst", tags=["Data Analyst"])


@router.post(
    "/questions",
    response_model=QuestionSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a data analyst question"
)
async def submit_question(
    request: QuestionSubmitRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("data_analyst:write"))
):
    """Submit a new data analyst question."""
    service = DataAnalystService(db)
    
    question = service.create_question(
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        data_source_type=request.data_source_type,
        question=request.question
    )
    
    # Trigger async processing (Celery task)
    from src.tasks.data_analyst_tasks import process_data_analyst_question
    process_data_analyst_question.delay(question.question_id)
    
    return QuestionSubmitResponse(
        question_id=question.question_id,
        status=question.status.value,
        message="Question submitted successfully"
    )


@router.get(
    "/questions/{question_id}",
    response_model=QuestionResponse,
    summary="Get question details"
)
async def get_question(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("data_analyst:read"))
):
    """Get question details."""
    service = DataAnalystService(db)
    question = service.get_question(question_id)
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Authorization check
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return QuestionResponse(
        question_id=question.question_id,
        user_id=question.user_id,
        customer_id=question.customer_id,
        data_source_type=question.data_source_type.value,
        original_question=question.original_question,
        status=question.status.value,
        generated_sql=question.generated_sql,
        sql_error=question.sql_error,
        result_data=question.result_data,
        result_metadata=question.result_metadata,
        created_at=question.created_at,
        updated_at=question.updated_at,
        completed_at=question.completed_at
    )


@router.get(
    "/questions/{question_id}/status",
    response_model=QuestionStatusResponse,
    summary="Get question status"
)
async def get_question_status(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("data_analyst:read"))
):
    """Get question processing status."""
    service = DataAnalystService(db)
    question = service.get_question(question_id)
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    progress_map = {
        QuestionStatus.PENDING: 0.0,
        QuestionStatus.PROCESSING: 50.0,
        QuestionStatus.COMPLETED: 100.0,
        QuestionStatus.FAILED: 0.0
    }
    
    return QuestionStatusResponse(
        question_id=question.question_id,
        status=question.status.value,
        progress_percentage=progress_map.get(question.status, 0.0),
        error_message=question.sql_error
    )


@router.get(
    "/questions/{question_id}/result",
    response_model=AnalysisResultResponse,
    summary="Get analysis result"
)
async def get_analysis_result(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("data_analyst:read"))
):
    """Get analysis result."""
    service = DataAnalystService(db)
    question = service.get_question(question_id)
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if question.status != QuestionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Question not yet completed")
    
    return AnalysisResultResponse(
        question_id=question.question_id,
        result_data=question.result_data,
        result_metadata=question.result_metadata
    )


@router.get(
    "/questions",
    response_model=QuestionListResponse,
    summary="List questions"
)
async def list_questions(
    data_source_type: Optional[DataSourceType] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("data_analyst:read"))
):
    """List questions with pagination."""
    service = DataAnalystService(db)
    
    offset = (page - 1) * page_size
    questions, total = service.list_questions(
        user_id=current_user.user_id if not current_user.is_superuser else None,
        customer_id=current_user.customer_id,
        data_source_type=data_source_type,
        limit=page_size,
        offset=offset
    )
    
    return QuestionListResponse(
        questions=[_serialize_question(q) for q in questions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


def _serialize_question(question):
    """Serialize question to dict."""
    return {
        "question_id": question.question_id,
        "user_id": question.user_id,
        "customer_id": question.customer_id,
        "data_source_type": question.data_source_type.value,
        "original_question": question.original_question,
        "status": question.status.value,
        "created_at": question.created_at,
        "completed_at": question.completed_at
    }
```

### 4.4 API Schemas

**Location:** `src/api/schemas/data_analyst.py` (NEW)

```python
"""
Data Analyst API Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from src.models.data_analyst import DataSourceType


class QuestionSubmitRequest(BaseModel):
    """Request to submit a new question."""
    data_source_type: DataSourceType = Field(..., description="Data source type")
    question: str = Field(..., min_length=1, description="Natural language question")


class QuestionSubmitResponse(BaseModel):
    """Response after submitting a question."""
    question_id: str
    status: str
    message: str


class QuestionResponse(BaseModel):
    """Full question details."""
    question_id: str
    user_id: int
    customer_id: str
    data_source_type: str
    original_question: str
    status: str
    generated_sql: Optional[str] = None
    sql_error: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    result_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class QuestionStatusResponse(BaseModel):
    """Question status response."""
    question_id: str
    status: str
    progress_percentage: float
    error_message: Optional[str] = None


class AnalysisResultResponse(BaseModel):
    """Analysis result response."""
    question_id: str
    result_data: Dict[str, Any]
    result_metadata: Dict[str, Any]


class QuestionListItem(BaseModel):
    """Question list item."""
    question_id: str
    user_id: int
    customer_id: str
    data_source_type: str
    original_question: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None


class QuestionListResponse(BaseModel):
    """Question list response."""
    questions: List[QuestionListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
```

### 4.5 Celery Task

**Location:** `src/tasks/data_analyst_tasks.py` (NEW)

```python
"""
Data Analyst Celery Tasks
"""
from celery import Task
from src.celery_app import celery_app
from src.models import database
from src.services.data_analyst_service import DataAnalystService
from src.core.logging import get_logger

logger = get_logger(__name__, component="data.analyst.tasks")


@celery_app.task(bind=True, name="data_analyst.process_question")
def process_data_analyst_question(self: Task, question_id: str):
    """
    Process a data analyst question asynchronously.
    
    Args:
        question_id: Question ID to process
    """
    # Initialize database if needed
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    try:
        service = DataAnalystService(db)
        service.process_question(question_id)
        
        logger.info("question_processed", question_id=question_id)
    except Exception as e:
        logger.error(
            "question_processing_failed",
            question_id=question_id,
            error=str(e),
            exc_info=True
        )
        raise
    finally:
        db.close()
```

### 4.6 Register Router

**Location:** `src/main.py`

Add to router includes:
```python
from src.api.routes import data_analyst
app.include_router(data_analyst.router, tags=["Data Analyst"])
```

---

## 5. Frontend Implementation

### 5.1 Navigation Update

**Location:** `frontend/src/components/layout/Navigation.tsx`

Add new navigation section:
```typescript
// Data Analyst Section
{
  label: 'Data Analyst Agent',
  path: '/data-analyst',
  icon: 'chart',
  requiredPermissions: ['data_analyst:read'],
  children: [
    {
      label: 'Insurance Analytics',
      path: '/data-analyst/insurance',
      icon: 'chart',
    },
  ],
},
```

### 5.2 Main Page Component

**Location:** `frontend/src/pages/data-analyst/DataAnalystPage.tsx` (NEW)

```typescript
/**
 * Data Analyst Agent Main Page
 * Allows users to select data source and ask questions
 */
import React, { useState } from 'react';
import { Layout } from '../../components/layout/Layout';
import DataSourceSelector from '../../components/data-analyst/DataSourceSelector';
import QuestionChat from '../../components/data-analyst/QuestionChat';
import ResultsDisplay from '../../components/data-analyst/ResultsDisplay';
import { DataSourceType } from '../../generated/models/dataSourceType';

export default function DataAnalystPage() {
  const [selectedDataSource, setSelectedDataSource] = useState<DataSourceType | null>(null);
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(null);

  return (
    <Layout>
      <div className="flex flex-col h-full">
        <div className="p-6 border-b border-border">
          <h1 className="text-2xl font-bold text-text">Data Analyst Agent</h1>
          <p className="text-muted mt-1">Ask questions about your data in natural language</p>
        </div>

        {!selectedDataSource ? (
          <DataSourceSelector
            onSelect={(source) => setSelectedDataSource(source)}
          />
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden">
            <QuestionChat
              dataSourceType={selectedDataSource}
              onQuestionSubmitted={(questionId) => setSelectedQuestionId(questionId)}
            />
            {selectedQuestionId && (
              <ResultsDisplay questionId={selectedQuestionId} />
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}
```

### 5.3 Data Source Selector Component

**Location:** `frontend/src/components/data-analyst/DataSourceSelector.tsx` (NEW)

```typescript
/**
 * Data Source Selector Component
 * Allows users to select which data source to query
 */
import React from 'react';
import { DataSourceType } from '../../generated/models/dataSourceType';

interface DataSourceSelectorProps {
  onSelect: (source: DataSourceType) => void;
}

const DATA_SOURCES = [
  {
    type: DataSourceType.Insurance,
    label: 'Insurance Analytics',
    description: 'Query insurance policy, claim, and customer data',
    icon: '📊',
  },
  // Future: Add more data sources
];

export default function DataSourceSelector({ onSelect }: DataSourceSelectorProps) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-4xl w-full">
        <h2 className="text-xl font-semibold text-text mb-6">Select Data Source</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {DATA_SOURCES.map((source) => (
            <button
              key={source.type}
              onClick={() => onSelect(source.type)}
              className="p-6 border border-border rounded-lg hover:bg-surface transition-colors text-left"
            >
              <div className="text-4xl mb-3">{source.icon}</div>
              <h3 className="text-lg font-semibold text-text mb-2">{source.label}</h3>
              <p className="text-muted text-sm">{source.description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
```

### 5.4 Question Chat Component

**Location:** `frontend/src/components/data-analyst/QuestionChat.tsx` (NEW)

```typescript
/**
 * Question Chat Component
 * Interface for submitting questions and viewing conversation history
 */
import React, { useState } from 'react';
import { DataSourceType } from '../../generated/models/dataSourceType';
import {
  useSubmitQuestionV1DataAnalystQuestionsPost,
  useListQuestionsV1DataAnalystQuestionsGet,
} from '../../generated/data-analyst/data-analyst';

interface QuestionChatProps {
  dataSourceType: DataSourceType;
  onQuestionSubmitted: (questionId: string) => void;
}

export default function QuestionChat({ dataSourceType, onQuestionSubmitted }: QuestionChatProps) {
  const [question, setQuestion] = useState('');
  
  const { mutate: submitQuestion, isPending } = useSubmitQuestionV1DataAnalystQuestionsPost();
  const { data: questionsData } = useListQuestionsV1DataAnalystQuestionsGet({
    data_source_type: dataSourceType,
    page: 1,
    page_size: 20,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    submitQuestion(
      {
        data_source_type: dataSourceType,
        question: question.trim(),
      },
      {
        onSuccess: (response) => {
          onQuestionSubmitted(response.question_id);
          setQuestion('');
        },
      }
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* Question History */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {questionsData?.questions.map((q) => (
          <div key={q.question_id} className="p-4 bg-surface rounded-lg">
            <p className="text-text">{q.original_question}</p>
            <p className="text-muted text-sm mt-2">
              {q.status} • {new Date(q.created_at).toLocaleString()}
            </p>
          </div>
        ))}
      </div>

      {/* Question Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about your data..."
            className="flex-1 px-4 py-2 border border-border rounded-lg bg-bg text-text"
            disabled={isPending}
          />
          <button
            type="submit"
            disabled={isPending || !question.trim()}
            className="px-6 py-2 bg-primary text-white rounded-lg disabled:opacity-50"
          >
            {isPending ? 'Processing...' : 'Ask'}
          </button>
        </div>
      </form>
    </div>
  );
}
```

### 5.5 Results Display Component

**Location:** `frontend/src/components/data-analyst/ResultsDisplay.tsx` (NEW)

```typescript
/**
 * Results Display Component
 * Shows charts, tables, and insights from query results
 */
import React from 'react';
import {
  useGetAnalysisResultV1DataAnalystQuestionsQuestionIdResultGet,
  useGetQuestionStatusV1DataAnalystQuestionsQuestionIdStatusGet,
} from '../../generated/data-analyst/data-analyst';
import DataTable from './DataTable';
import ChartDisplay from './ChartDisplay';
import InsightsPanel from './InsightsPanel';

interface ResultsDisplayProps {
  questionId: string;
}

export default function ResultsDisplay({ questionId }: ResultsDisplayProps) {
  const { data: statusData } = useGetQuestionStatusV1DataAnalystQuestionsQuestionIdStatusGet(
    questionId,
    {
      query: {
        refetchInterval: (data) => {
          // Poll until completed
          return data?.status === 'completed' ? false : 2000;
        },
      },
    }
  );

  const { data: resultData } = useGetAnalysisResultV1DataAnalystQuestionsQuestionIdResultGet(
    questionId,
    {
      query: {
        enabled: statusData?.status === 'completed',
      },
    }
  );

  if (statusData?.status === 'processing' || statusData?.status === 'pending') {
    return (
      <div className="p-8 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="text-muted mt-4">Processing your question...</p>
        <p className="text-sm text-muted mt-2">
          {statusData.progress_percentage}% complete
        </p>
      </div>
    );
  }

  if (statusData?.status === 'failed') {
    return (
      <div className="p-8 text-center text-error">
        <p>Failed to process question</p>
        <p className="text-sm mt-2">{statusData.error_message}</p>
      </div>
    );
  }

  if (!resultData) {
    return null;
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Charts */}
        <div className="lg:col-span-2">
          <ChartDisplay
            metadata={resultData.result_metadata}
            data={resultData.result_data}
          />
        </div>

        {/* Insights */}
        <div>
          <InsightsPanel metadata={resultData.result_metadata} />
        </div>
      </div>

      {/* Data Table */}
      <div className="mt-6">
        <DataTable data={resultData.result_data} />
      </div>
    </div>
  );
}
```

### 5.6 Chart Display Component

**Location:** `frontend/src/components/data-analyst/ChartDisplay.tsx` (NEW)

```typescript
/**
 * Chart Display Component
 * Renders charts based on metadata suggestions
 */
import React from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface ChartDisplayProps {
  metadata: any;
  data: any;
}

export default function ChartDisplay({ metadata, data }: ChartDisplayProps) {
  const chartSuggestions = metadata?.chart_suggestions || [];

  if (chartSuggestions.length === 0) {
    return (
      <div className="p-8 text-center text-muted">
        <p>No charts available for this data</p>
      </div>
    );
  }

  // Transform data for charting
  const chartData = data.rows.map((row: any[]) => {
    const obj: any = {};
    data.columns.forEach((col: string, idx: number) => {
      obj[col] = row[idx];
    });
    return obj;
  });

  return (
    <div className="space-y-6">
      {chartSuggestions.map((suggestion: any, idx: number) => (
        <div key={idx} className="bg-surface p-6 rounded-lg">
          <h3 className="text-lg font-semibold mb-4">Chart {idx + 1}</h3>
          {suggestion.type === 'bar' && (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={suggestion.x} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey={suggestion.y} fill="#8884d8" />
              </BarChart>
            </ResponsiveContainer>
          )}
          {suggestion.type === 'line' && (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey={suggestion.x} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey={suggestion.y} stroke="#8884d8" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      ))}
    </div>
  );
}
```

### 5.7 Data Table Component

**Location:** `frontend/src/components/data-analyst/DataTable.tsx` (NEW)

```typescript
/**
 * Data Table Component
 * Scrollable table displaying raw query results
 */
import React from 'react';

interface DataTableProps {
  data: {
    columns: string[];
    rows: any[][];
    row_count: number;
  };
}

export default function DataTable({ data }: DataTableProps) {
  if (!data || !data.rows || data.rows.length === 0) {
    return (
      <div className="p-8 text-center text-muted">
        <p>No data to display</p>
      </div>
    );
  }

  return (
    <div className="bg-surface rounded-lg overflow-hidden">
      <div className="p-4 border-b border-border">
        <h3 className="text-lg font-semibold">Raw Data</h3>
        <p className="text-sm text-muted">{data.row_count} rows</p>
      </div>
      <div className="overflow-x-auto max-h-96 overflow-y-auto">
        <table className="w-full">
          <thead className="bg-surface sticky top-0">
            <tr>
              {data.columns.map((col) => (
                <th key={col} className="px-4 py-2 text-left text-sm font-semibold text-text border-b border-border">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, idx) => (
              <tr key={idx} className="hover:bg-surface">
                {row.map((cell, cellIdx) => (
                  <td key={cellIdx} className="px-4 py-2 text-sm text-text border-b border-border">
                    {cell !== null && cell !== undefined ? String(cell) : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

### 5.8 Insights Panel Component

**Location:** `frontend/src/components/data-analyst/InsightsPanel.tsx` (NEW)

```typescript
/**
 * Insights Panel Component
 * Displays text-based insights and summary
 */
import React from 'react';

interface InsightsPanelProps {
  metadata: any;
}

export default function InsightsPanel({ metadata }: InsightsPanelProps) {
  const insights = metadata?.insights || '';
  const summary = metadata?.summary || '';
  const sql = metadata?.sql || '';

  return (
    <div className="space-y-4">
      {/* Summary */}
      {summary && (
        <div className="bg-surface p-4 rounded-lg">
          <h3 className="text-sm font-semibold text-text mb-2">Summary</h3>
          <p className="text-sm text-muted">{summary}</p>
        </div>
      )}

      {/* Insights */}
      {insights && (
        <div className="bg-surface p-4 rounded-lg">
          <h3 className="text-sm font-semibold text-text mb-2">Insights</h3>
          <p className="text-sm text-muted">{insights}</p>
        </div>
      )}

      {/* SQL Query */}
      {sql && (
        <div className="bg-surface p-4 rounded-lg">
          <h3 className="text-sm font-semibold text-text mb-2">Generated SQL</h3>
          <pre className="text-xs text-muted overflow-x-auto bg-bg p-2 rounded">
            {sql}
          </pre>
        </div>
      )}
    </div>
  );
}
```

### 5.9 Route Registration

**Location:** `frontend/src/App.tsx`

Add route:
```typescript
<Route
  path="/data-analyst"
  element={
    <ProtectedRoute requiredPermissions={['data_analyst:read']}>
      <DataAnalystPage />
    </ProtectedRoute>
  }
/>
```

---

## 6. Database Migration

**Location:** `alembic/versions/XXXX_add_data_analyst_tables.py` (NEW)

```python
"""Add data analyst tables

Revision ID: xxxx
Revises: yyyy
Create Date: 2025-01-XX
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'xxxx'
down_revision = 'yyyy'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'data_analyst_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.String(100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('data_source_type', sa.String(50), nullable=False),
        sa.Column('original_question', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('generated_sql', sa.Text(), nullable=True),
        sa.Column('sql_error', sa.Text(), nullable=True),
        sa.Column('result_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('result_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_id')
    )
    op.create_index('ix_data_analyst_questions_question_id', 'data_analyst_questions', ['question_id'])
    op.create_index('ix_data_analyst_questions_user_id', 'data_analyst_questions', ['user_id'])
    op.create_index('ix_data_analyst_questions_customer_id', 'data_analyst_questions', ['customer_id'])


def downgrade():
    op.drop_index('ix_data_analyst_questions_customer_id', table_name='data_analyst_questions')
    op.drop_index('ix_data_analyst_questions_user_id', table_name='data_analyst_questions')
    op.drop_index('ix_data_analyst_questions_question_id', table_name='data_analyst_questions')
    op.drop_table('data_analyst_questions')
```

---

## 7. Implementation Checklist

### Phase 1: Database & Infrastructure Setup
- [ ] Create `insurance_demo_db` database
- [ ] Run all DDL scripts to create schemas and tables
- [ ] Load sample data from Excel files
- [ ] Add `INSURANCE_DEMO_DB_URL` to config
- [ ] Create `insurance_database.py` module
- [ ] Create database migration for `data_analyst_questions` table

### Phase 2: Vanna AI Integration
- [ ] Install Vanna package (`requirements.txt`)
- [ ] Create `VannaService` class
- [ ] Create training script (`train_vanna_insurance.py`)
- [ ] Train Vanna on DDL schemas
- [ ] Train Vanna on domain documentation
- [ ] Train Vanna on example Q&A pairs
- [ ] Test SQL generation with sample questions

### Phase 3: Backend Implementation
- [ ] Create `DataAnalystQuestion` model
- [ ] Create `DataAnalystService` class
- [ ] Create API schemas (`data_analyst.py`)
- [ ] Create API routes (`data_analyst.py`)
- [ ] Create Celery task (`data_analyst_tasks.py`)
- [ ] Register router in `main.py`
- [ ] Add permissions (`data_analyst:read`, `data_analyst:write`)

### Phase 4: Frontend Implementation
- [ ] Generate TypeScript types from OpenAPI spec
- [ ] Create `DataAnalystPage` component
- [ ] Create `DataSourceSelector` component
- [ ] Create `QuestionChat` component
- [ ] Create `ResultsDisplay` component
- [ ] Create `ChartDisplay` component (using Recharts)
- [ ] Create `DataTable` component
- [ ] Create `InsightsPanel` component
- [ ] Update navigation (`Navigation.tsx`)
- [ ] Add route to `App.tsx`

### Phase 5: Testing & Refinement
- [ ] Test SQL generation with various question types
- [ ] Test error handling (invalid SQL, database errors)
- [ ] Test frontend components with real data
- [ ] Test chart rendering with different data types
- [ ] Test table scrolling and pagination
- [ ] Performance testing (large result sets)
- [ ] Security testing (SQL injection prevention)

### Phase 6: Documentation & Deployment
- [ ] Update API documentation
- [ ] Create user guide
- [ ] Add deployment notes
- [ ] Update docker-compose if needed
- [ ] Rebuild containers

---

## 8. Security Considerations

1. **SQL Injection Prevention**: Vanna AI should handle SQL sanitization, but validate generated SQL before execution
2. **Database Access**: Use read-only database user for insurance_demo_db
3. **Query Limits**: Implement query timeout and result size limits
4. **User Authorization**: Ensure users can only access their own questions
5. **Data Source Access**: Check user permissions for each data source type

---

## 9. Future Enhancements

1. **Additional Data Sources**: Finance, Retail, etc.
2. **Advanced Visualizations**: More chart types, interactive charts
3. **Query History**: Save and reuse queries
4. **Query Sharing**: Share queries with team members
5. **Scheduled Reports**: Automate recurring queries
6. **LLM-Generated Insights**: Use LLM to generate deeper insights from results
7. **Query Optimization**: Suggest query improvements
8. **Export Functionality**: Export results to CSV/Excel

---

## 10. Dependencies

### Backend
- `vanna>=0.7.0`
- `pandas` (for data manipulation)
- `plotly` (optional, for advanced charts)

### Frontend
- `recharts` (for charts)
- Existing UI components

---

## 11. Notes

- Vanna AI can be used locally or via Vanna Cloud API (consider for production)
- Consider caching Vanna training data
- Monitor SQL generation accuracy and retrain as needed
- Consider adding query result caching for frequently asked questions

