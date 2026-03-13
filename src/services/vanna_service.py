"""
Vanna AI Service for Text-to-SQL Generation
"""
from typing import Optional, Dict, Any, List
import logging
from urllib.parse import urlparse
import pandas as pd
from pathlib import Path

from vanna.local import LocalContext_OpenAI

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
    - Result execution
    """
    
    def __init__(self, database_url: str, model: Optional[str] = None):
        """
        Initialize Vanna service.
        
        Args:
            database_url: PostgreSQL connection string
            model: LLM model to use (defaults to OpenAI GPT-4)
        """
        self.database_url = database_url
        self.settings = get_settings()
        self.model = model or self.settings.default_llm_model
        
        # Parse database URL
        parsed = urlparse(database_url)
        self.db_host = parsed.hostname or "postgres"
        self.db_port = parsed.port or 5432
        self.db_name = parsed.path.lstrip('/') if parsed.path else "insurance_demo_db"
        self.db_user = parsed.username or "user"
        self.db_password = parsed.password or "password"
        
        # Initialize Vanna with local ChromaDB vector store
        try:
            # Get OpenAI API key from settings
            api_key = self.settings.openai_api_key
            if not api_key:
                raise ValueError("OPENAI_API_KEY not configured. Vanna requires an OpenAI API key.")
            
            config = {
                "api_key": api_key,
                "model": self.model,
            }
            vector_store = "in_memory"

            # ChromaDB disabled for now (build issue in current env).
            # If re-enabled, restore PersistentClient setup here.
            # persist_dir = Path(self.settings.data_path) / "vanna" / self.db_name
            # persist_dir.mkdir(parents=True, exist_ok=True)
            #
            # import chromadb
            # from chromadb.config import Settings as ChromaSettings
            #
            # chroma_client = chromadb.PersistentClient(
            #     path=str(persist_dir),
            #     settings=ChromaSettings(anonymized_telemetry=False)
            # )
            #
            # config["client"] = chroma_client  # Pass the persistent client directly
            # vector_store = "ChromaDB"
            self.vanna = LocalContext_OpenAI(config=config)
            
            # Connect to database
            self.vanna.connect_to_postgres(
                host=self.db_host,
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password,
                port=self.db_port
            )
            
            logger.info(
                "vanna_service_initialized",
                model=self.model,
                database=self.db_name,
                host=self.db_host,
                vector_store=vector_store
            )
        except Exception as e:
            logger.error(
                "vanna_service_init_failed",
                error=str(e),
                exc_info=True
            )
            raise
    
    def train_on_ddl(self, ddl_statements: List[str]) -> None:
        """
        Train Vanna on database schema DDL statements.
        
        Args:
            ddl_statements: List of CREATE TABLE/VIEW statements
        """
        try:
            for ddl in ddl_statements:
                if ddl.strip():
                    self.vanna.train(ddl=ddl)
            
            logger.info(
                "vanna_trained_on_ddl",
                statement_count=len(ddl_statements)
            )
        except Exception as e:
            logger.error(
                "vanna_ddl_training_failed",
                error=str(e),
                exc_info=True
            )
            raise
    
    def train_on_documentation(self, documentation: str) -> None:
        """
        Train Vanna on domain documentation.
        
        Args:
            documentation: Insurance domain documentation text
        """
        try:
            self.vanna.train(documentation=documentation)
            logger.info("vanna_trained_on_documentation")
        except Exception as e:
            logger.error(
                "vanna_documentation_training_failed",
                error=str(e),
                exc_info=True
            )
            raise
    
    def train_on_question_sql(self, question: str, sql: str) -> None:
        """
        Train Vanna on example question-SQL pairs.
        
        Args:
            question: Natural language question
            sql: Corresponding SQL query
        """
        try:
            self.vanna.train(question=question, sql=sql)
            logger.info("vanna_trained_on_question_sql")
        except Exception as e:
            logger.error(
                "vanna_question_sql_training_failed",
                error=str(e),
                exc_info=True
            )
            raise
    
    def generate_sql(self, question: str) -> str:
        """
        Generate SQL query from natural language question.
        
        Uses Vanna's ask() method which retrieves context and generates SQL.
        ask() returns a tuple: (sql_string, dataframe, plotly_figure)
        We extract the SQL from the first element of the tuple.
        If ask() fails due to SQL execution errors, we fall back to generate_sql()
        which should work now that context is cached.
        
        Args:
            question: Natural language question
            
        Returns:
            Generated SQL query string
        """
        try:
            # Use ask() to retrieve context and generate SQL
            # ask() returns: (sql_string, dataframe, plotly_figure)
            try:
                result = self.vanna.ask(question=question)
                # Extract SQL from tuple (first element)
                if isinstance(result, tuple) and len(result) > 0:
                    sql = result[0]
                    logger.debug("SQL extracted from ask() result")
                else:
                    # Fallback: if result format is unexpected, try generate_sql()
                    sql = self.vanna.generate_sql(question=question)
            except Exception as ask_error:
                # ask() failed (likely SQL execution error), but context was retrieved
                # Now generate_sql() should work with cached context
                logger.debug(f"ask() failed, trying generate_sql() with cached context: {ask_error}")
                sql = self.vanna.generate_sql(question=question)
            
            # Validate that the response is actually SQL, not an error message
            if not sql or not isinstance(sql, str):
                raise ValueError("Vanna returned empty or invalid SQL")
            
            # Remove leading comments and whitespace to check for SQL keywords
            sql_cleaned = sql.strip()
            # Remove SQL comments (-- style)
            lines = sql_cleaned.split('\n')
            sql_without_comments = []
            for line in lines:
                # Remove inline comments
                comment_pos = line.find('--')
                if comment_pos >= 0:
                    line = line[:comment_pos]
                sql_without_comments.append(line.strip())
            sql_cleaned = ' '.join(sql_without_comments).strip()
            
            # Check if it looks like SQL (starts with SELECT, WITH, etc.)
            sql_upper = sql_cleaned.upper()
            sql_keywords = ['SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP']
            if not any(sql_upper.startswith(kw) for kw in sql_keywords):
                # If it doesn't start with SQL keywords, it's likely an error message
                error_msg = f"Vanna returned text instead of SQL: {sql[:200]}"
                logger.error("sql_generation_returned_text", error=error_msg, question=question[:100])
                raise ValueError(error_msg)
            
            # Fix common PostgreSQL interval syntax errors
            # Replace '1 quarter' with '3 months' (PostgreSQL doesn't support 'quarter' unit)
            sql = sql.replace("INTERVAL '1 quarter'", "INTERVAL '3 months'")
            sql = sql.replace("INTERVAL '1 QUARTER'", "INTERVAL '3 months'")
            sql = sql.replace("INTERVAL '1 Quarter'", "INTERVAL '3 months'")
            
            logger.info(
                "sql_generated",
                question_length=len(question),
                sql_length=len(sql) if sql else 0
            )
            return sql
        except Exception as e:
            logger.error(
                "sql_generation_failed",
                error=str(e),
                question=question[:100],  # Log first 100 chars
                exc_info=True
            )
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
            
            # Convert to list of dicts if needed
            if isinstance(results, pd.DataFrame):
                results = results.to_dict('records')
            elif not isinstance(results, list):
                results = list(results) if results else []
            
            logger.info(
                "sql_executed",
                result_count=len(results) if results else 0,
                sql_preview=sql[:100]  # Log first 100 chars
            )
            return results
        except Exception as e:
            logger.error(
                "sql_execution_failed",
                error=str(e),
                sql=sql[:200],  # Log first 200 chars
                exc_info=True
            )
            raise
    
    def generate_plotly_code(
        self,
        question: str,
        sql: str,
        results: List[Dict[str, Any]]
    ) -> Optional[str]:
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
            # Convert results to DataFrame if needed
            if not isinstance(results, pd.DataFrame):
                df = pd.DataFrame(results)
            else:
                df = results
            
            plotly_code = self.vanna.generate_plotly_code(
                question=question,
                sql=sql,
                df=df
            )
            return plotly_code
        except Exception as e:
            logger.warning(
                "plotly_code_generation_failed",
                error=str(e)
            )
            return None
