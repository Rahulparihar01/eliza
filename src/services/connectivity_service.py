"""
Connectivity Service

Service for checking connectivity to all data sources used in the BI pipeline.
Provides robust health checks for database, vector index, and other data sources.
"""
from typing import Dict, Any, Optional
from pathlib import Path
import json

from src.core.logging import get_logger, LogCategory
from src.core.config import get_settings
from src.models.database import check_database_health_sync

logger = get_logger(__name__, component="connectivity.service")
settings = get_settings()


class ConnectivityService:
    """Service for checking data source connectivity."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def check_hr_database_connectivity(self, customer_id: str) -> Dict[str, Any]:
        """
        Check connectivity to the HR database.
        
        Args:
            customer_id: Customer ID to check data availability
            
        Returns:
            Dict with connectivity status and details
        """
        logger.info(
            "checking_hr_database_connectivity",
            category=LogCategory.SYSTEM,
            metadata={"customer_id": customer_id}
        )
        
        try:
            # Check basic database health
            health_status = check_database_health_sync()
            
            if health_status["status"] != "healthy":
                logger.warning(
                    "hr_database_connectivity_failed",
                    category=LogCategory.SYSTEM,
                    metadata={
                        "customer_id": customer_id,
                        "error": health_status.get("message", "Unknown error")
                    }
                )
                return {
                    "status": "unhealthy",
                    "source": "hr_database",
                    "message": f"Database connection failed: {health_status.get('message', 'Unknown error')}",
                    "available": False,
                    "details": health_status.get("details", {})
                }
            
            # Check if customer has HR data
            has_data = self._check_customer_hr_data(customer_id)
            
            result = {
                "status": "healthy",
                "source": "hr_database",
                "message": "HR database connection successful",
                "available": True,
                "has_customer_data": has_data,
                "details": {
                    **health_status.get("details", {}),
                    "customer_id": customer_id,
                    "data_available": has_data
                }
            }
            
            if not has_data:
                result["message"] += " (no data for this customer)"
                logger.info(
                    "hr_database_no_customer_data",
                    category=LogCategory.SYSTEM,
                    metadata={"customer_id": customer_id}
                )
            
            logger.info(
                "hr_database_connectivity_success",
                category=LogCategory.SYSTEM,
                metadata={
                    "customer_id": customer_id,
                    "has_data": has_data
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "hr_database_connectivity_error",
                exception=e,
                category=LogCategory.SYSTEM,
                metadata={"customer_id": customer_id}
            )
            return {
                "status": "unhealthy",
                "source": "hr_database",
                "message": f"HR database connectivity check failed: {str(e)}",
                "available": False,
                "has_customer_data": False,
                "details": {"error": str(e)}
            }
    
    def _check_customer_hr_data(self, customer_id: str) -> bool:
        """
        Check if customer has any HR data in the database.
        
        Args:
            customer_id: Customer ID to check
            
        Returns:
            bool: True if customer has HR data
        """
        try:
            from src.models.database import SessionLocal
            from src.models.hr import Employee
            
            if SessionLocal is None:
                from src.models.database import init_database
                init_database()
                from src.models.database import SessionLocal
            
            db = SessionLocal()
            try:
                # Quick check: does customer have any employees?
                count = db.query(Employee).filter(
                    Employee.customer_id == customer_id
                ).limit(1).count()
                
                return count > 0
            finally:
                db.close()
                
        except Exception as e:
            logger.warning(
                "check_customer_hr_data_failed",
                exception=e,
                category=LogCategory.SYSTEM,
                metadata={"customer_id": customer_id}
            )
            # Return True on error to avoid blocking the pipeline
            # The actual query will fail with a better error if there's a real issue
            return True
    
    def check_vector_index_connectivity(self, customer_id: str) -> Dict[str, Any]:
        """
        Check connectivity to the FAISS vector index.
        
        Args:
            customer_id: Customer ID to check index availability
            
        Returns:
            Dict with connectivity status and details
        """
        logger.info(
            "checking_vector_index_connectivity",
            category=LogCategory.SYSTEM,
            metadata={"customer_id": customer_id}
        )
        
        try:
            # Get vector index directory from settings
            vector_dir = Path(self.settings.vector_index_directory)
            index_file = vector_dir / "faiss_index.bin"
            mapping_file = vector_dir / "chunk_mapping.json"
            
            # Check if index files exist
            index_exists = index_file.exists()
            mapping_exists = mapping_file.exists()
            
            if not index_exists or not mapping_exists:
                missing_files = []
                if not index_exists:
                    missing_files.append("faiss_index.bin")
                if not mapping_exists:
                    missing_files.append("chunk_mapping.json")
                
                logger.warning(
                    "vector_index_files_missing",
                    category=LogCategory.SYSTEM,
                    metadata={
                        "customer_id": customer_id,
                        "missing_files": missing_files,
                        "vector_dir": str(vector_dir)
                    }
                )
                
                return {
                    "status": "unhealthy",
                    "source": "vector_index",
                    "message": f"Vector index files missing: {', '.join(missing_files)}",
                    "available": False,
                    "details": {
                        "vector_dir": str(vector_dir),
                        "index_exists": index_exists,
                        "mapping_exists": mapping_exists,
                        "missing_files": missing_files
                    }
                }
            
            # Try to get index statistics
            index_stats = self._get_index_stats(index_file, mapping_file, customer_id)
            
            result = {
                "status": "healthy",
                "source": "vector_index",
                "message": "Vector index connection successful",
                "available": True,
                "details": {
                    "vector_dir": str(vector_dir),
                    "index_exists": True,
                    "mapping_exists": True,
                    **index_stats
                }
            }
            
            if index_stats.get("total_vectors", 0) == 0:
                result["message"] += " (index is empty)"
                logger.info(
                    "vector_index_empty",
                    category=LogCategory.SYSTEM,
                    metadata={"customer_id": customer_id}
                )
            elif not index_stats.get("has_customer_data", False):
                result["message"] += " (no data for this customer)"
                logger.info(
                    "vector_index_no_customer_data",
                    category=LogCategory.SYSTEM,
                    metadata={"customer_id": customer_id}
                )
            
            logger.info(
                "vector_index_connectivity_success",
                category=LogCategory.SYSTEM,
                metadata={
                    "customer_id": customer_id,
                    "total_vectors": index_stats.get("total_vectors", 0),
                    "has_customer_data": index_stats.get("has_customer_data", False)
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "vector_index_connectivity_error",
                exception=e,
                category=LogCategory.SYSTEM,
                metadata={"customer_id": customer_id}
            )
            return {
                "status": "unhealthy",
                "source": "vector_index",
                "message": f"Vector index connectivity check failed: {str(e)}",
                "available": False,
                "details": {"error": str(e)}
            }
    
    def _get_index_stats(
        self, 
        index_file: Path, 
        mapping_file: Path,
        customer_id: str
    ) -> Dict[str, Any]:
        """
        Get statistics about the FAISS index.
        
        Args:
            index_file: Path to FAISS index file
            mapping_file: Path to chunk mapping file
            customer_id: Customer ID to check
            
        Returns:
            Dict with index statistics
        """
        try:
            import faiss
            
            # Load the index to verify it's readable
            index = faiss.read_index(str(index_file))
            total_vectors = index.ntotal
            
            # Load mapping to get chunk information
            with open(mapping_file, 'r') as f:
                chunk_mapping = json.load(f)
            
            # Check if customer has indexed documents
            has_customer_data = self._check_customer_vector_data(customer_id)
            
            return {
                "total_vectors": total_vectors,
                "total_chunks": len(chunk_mapping),
                "index_type": type(index).__name__,
                "dimension": index.d if hasattr(index, 'd') else None,
                "has_customer_data": has_customer_data
            }
            
        except Exception as e:
            logger.warning(
                "get_index_stats_failed",
                exception=e,
                category=LogCategory.SYSTEM
            )
            return {
                "total_vectors": None,
                "total_chunks": None,
                "error": str(e)
            }
    
    def _check_customer_vector_data(self, customer_id: str) -> bool:
        """
        Check if customer has any indexed documents.
        
        Args:
            customer_id: Customer ID to check
            
        Returns:
            bool: True if customer has indexed documents
        """
        try:
            from src.models.database import SessionLocal
            from src.models.document import Document
            
            if SessionLocal is None:
                from src.models.database import init_database
                init_database()
                from src.models.database import SessionLocal
            
            db = SessionLocal()
            try:
                # Check if customer has any processed documents
                count = db.query(Document).filter(
                    Document.customer_id == customer_id
                ).limit(1).count()
                
                return count > 0
            finally:
                db.close()
                
        except Exception as e:
            logger.warning(
                "check_customer_vector_data_failed",
                exception=e,
                category=LogCategory.SYSTEM,
                metadata={"customer_id": customer_id}
            )
            # Return True on error to avoid blocking the pipeline
            return True
    
    def check_all_data_sources(self, customer_id: str, company_hr_dataset: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Check connectivity to all data sources used in the BI pipeline.
        
        Args:
            customer_id: Customer ID (for document index)
            company_hr_dataset: Target company for HR data (defaults to customer_id if not specified)
            
        Returns:
            Dict mapping source names to their connectivity status
        """
        # Default company_hr_dataset to customer_id for backward compatibility
        if not company_hr_dataset:
            company_hr_dataset = customer_id
        
        logger.info(
            "checking_all_data_sources",
            category=LogCategory.SYSTEM,
            metadata={
                "customer_id": customer_id,
                "company_hr_dataset": company_hr_dataset
            }
        )
        
        results = {}
        
        # Check HR Database (use company_hr_dataset, not customer_id)
        results["hr_database"] = self.check_hr_database_connectivity(company_hr_dataset)
        
        # Check Vector Index (use customer_id for document index)
        results["vector_index"] = self.check_vector_index_connectivity(customer_id)
        
        # Determine overall status
        all_healthy = all(
            result["status"] == "healthy" 
            for result in results.values()
        )
        
        all_available = all(
            result["available"] 
            for result in results.values()
        )
        
        logger.info(
            "data_source_connectivity_check_complete",
            category=LogCategory.SYSTEM,
            metadata={
                "customer_id": customer_id,
                "all_healthy": all_healthy,
                "all_available": all_available,
                "hr_database": results["hr_database"]["status"],
                "vector_index": results["vector_index"]["status"]
            }
        )
        
        return results
    
    def get_connectivity_summary(self, results: Dict[str, Dict[str, Any]]) -> str:
        """
        Generate a human-readable summary of connectivity check results.
        
        Args:
            results: Results from check_all_data_sources()
            
        Returns:
            str: Human-readable summary
        """
        healthy_sources = [
            name for name, result in results.items() 
            if result["status"] == "healthy"
        ]
        
        unhealthy_sources = [
            name for name, result in results.items() 
            if result["status"] != "healthy"
        ]
        
        if not unhealthy_sources:
            return f"✓ All data sources ready ({len(healthy_sources)} sources verified)"
        
        summary_parts = []
        if healthy_sources:
            summary_parts.append(f"✓ {len(healthy_sources)} healthy")
        if unhealthy_sources:
            summary_parts.append(f"✗ {len(unhealthy_sources)} unavailable")
        
        return f"Data source status: {', '.join(summary_parts)}"


# Convenience function for quick checks
def check_data_source_connectivity(customer_id: str, company_hr_dataset: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function to check all data sources.
    
    Args:
        customer_id: Customer ID (for document index)
        company_hr_dataset: Target company for HR data (defaults to customer_id if not specified)
        
    Returns:
        Dict mapping source names to their connectivity status
    """
    service = ConnectivityService()
    return service.check_all_data_sources(customer_id, company_hr_dataset)

