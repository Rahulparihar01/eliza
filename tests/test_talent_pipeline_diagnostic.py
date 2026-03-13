#!/usr/bin/env python3
"""
Talent Analysis Pipeline Diagnostic Test

This script tests the talent analysis pipeline to identify where failures occur.

Usage:
    python tests/test_talent_pipeline_diagnostic.py [--verbose] [--timeout SECONDS]
"""

import os
import sys
import json
import time
import asyncio
import argparse
import signal
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from contextlib import contextmanager

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ENVIRONMENT", "development")


class TimeoutException(Exception):
    """Raised when a stage times out"""
    pass


@contextmanager
def timeout(seconds: int, stage_name: str):
    """Context manager for timing out long-running stages"""
    def timeout_handler(signum, frame):
        raise TimeoutException(f"Stage '{stage_name}' timed out after {seconds}s")
    
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


@dataclass
class StageResult:
    """Result of a pipeline stage test"""
    stage_name: str
    stage_number: int
    success: bool
    duration_seconds: float
    output: Any = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class TalentPipelineDiagnostic:
    """Diagnostic tool for testing talent analysis pipeline"""
    
    def __init__(self, verbose: bool = False, timeout_seconds: int = 60):
        self.verbose = verbose
        self.timeout_seconds = timeout_seconds
        self.results: List[StageResult] = []
        self.db = None
        self.customer_id = "eliza"
        self.analysis_id = f"diagnostic-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        
        self.test_job_description = """
        Senior Machine Learning Engineer
        
        We are looking for an experienced ML Engineer to join our team.
        
        Requirements:
        - 5+ years of experience in machine learning
        - Strong Python skills
        - Experience with TensorFlow or PyTorch
        - Experience with cloud platforms (AWS, GCP, or Azure)
        - Strong communication skills
        
        Nice to have:
        - Experience with LLMs and transformers
        - Kubernetes experience
        - MLOps experience
        """
        
        self.test_ideal_candidate = """
        The ideal candidate has deep experience building production ML systems,
        particularly with deep learning and NLP. They should be comfortable
        with the full ML lifecycle from data preparation to model deployment.
        Leadership experience is a plus.
        """
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️"}.get(level, "")
        print(f"[{timestamp}] {prefix} {message}")
    
    def log_verbose(self, message: str):
        """Log only if verbose mode is enabled"""
        if self.verbose:
            self.log(message)
    
    def init_database(self):
        """Initialize database connection"""
        self.log("Initializing database connection...")
        try:
            from src.models import database
            if database.SessionLocal is None:
                database.init_database()
            self.db = database.SessionLocal()
            self.log("Database connection established", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Database initialization failed: {e}", "ERROR")
            return False
    
    def cleanup(self):
        """Clean up resources"""
        if self.db:
            self.db.close()
            self.log_verbose("Database connection closed")
    
    # =========================================================================
    # Component Tests
    # =========================================================================
    def test_openai(self) -> StageResult:
        """Test OpenAI API connectivity"""
        self.log("\n" + "="*60)
        self.log("TEST: OpenAI API")
        self.log("="*60)
        
        start_time = time.time()
        
        try:
            import openai
            from src.core.config import get_settings
            
            settings = get_settings()
            client = openai.OpenAI(api_key=settings.openai_api_key)
            
            self.log("Testing simple completion...")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'test successful'"}],
                max_tokens=10
            )
            
            result = response.choices[0].message.content
            duration = time.time() - start_time
            
            self.log(f"OpenAI response: {result}", "SUCCESS")
            
            return StageResult(
                stage_name="openai_api",
                stage_number=1,
                success=True,
                duration_seconds=duration,
                output=result,
                details={"model": "gpt-4o-mini"}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.log(f"OpenAI test failed: {e}", "ERROR")
            return StageResult(
                stage_name="openai_api",
                stage_number=1,
                success=False,
                duration_seconds=duration,
                error=str(e)
            )
    
    def test_neo4j(self) -> StageResult:
        """Test Neo4j connectivity"""
        self.log("\n" + "="*60)
        self.log("TEST: Neo4j")
        self.log("="*60)
        
        start_time = time.time()
        
        try:
            from src.core.config import get_settings
            from neo4j import GraphDatabase
            
            settings = get_settings()
            
            self.log("Connecting to Neo4j...")
            driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
            
            with driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) as count")
                record = result.single()
                node_count = record["count"] if record else 0
            
            driver.close()
            duration = time.time() - start_time
            
            self.log(f"Neo4j has {node_count} nodes", "SUCCESS")
            
            return StageResult(
                stage_name="neo4j",
                stage_number=2,
                success=True,
                duration_seconds=duration,
                details={"node_count": node_count}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.log(f"Neo4j test failed: {e}", "ERROR")
            return StageResult(
                stage_name="neo4j",
                stage_number=2,
                success=False,
                duration_seconds=duration,
                error=str(e)
            )
    
    def test_diagnostic_agent(self) -> StageResult:
        """Test the Diagnostic Agent"""
        self.log("\n" + "="*60)
        self.log("TEST: Diagnostic Agent")
        self.log("="*60)
        
        start_time = time.time()
        
        try:
            from src.services.talent import DiagnosticAgentService
            from src.services.talent.diagnostic_agent import DiagnosticInput
            from src.models.talent_analysis import BaselineProfile
            
            self.log("Initializing Diagnostic Agent...")
            agent = DiagnosticAgentService(
                customer_id=self.customer_id,
                user_id=1
            )
            
            # Create minimal baseline profile
            baseline = BaselineProfile(
                prototype_employee_ids=[],
                common_skills=["Python", "TensorFlow"],
                common_titles=["ML Engineer"],
                experience_range=(3, 10),
                education_patterns=[],
                company_patterns=[]
            )
            
            diagnostic_input = DiagnosticInput(
                job_description=self.test_job_description,
                ideal_candidate_description=self.test_ideal_candidate,
                baseline_profile=baseline
            )
            
            self.log("Running diagnostic analysis (this may take 15-30 seconds)...")
            
            with timeout(self.timeout_seconds, "diagnostic_agent"):
                report = agent.analyze(diagnostic_input)
            
            duration = time.time() - start_time
            
            if report:
                attr_count = len(report.attribute_priorities) if hasattr(report, 'attribute_priorities') else 0
                self.log(f"Diagnostic complete: {attr_count} attributes prioritized", "SUCCESS")
                
                return StageResult(
                    stage_name="diagnostic_agent",
                    stage_number=3,
                    success=True,
                    duration_seconds=duration,
                    output=report,
                    details={"attribute_count": attr_count}
                )
            else:
                return StageResult(
                    stage_name="diagnostic_agent",
                    stage_number=3,
                    success=False,
                    duration_seconds=duration,
                    error="No diagnostic report generated"
                )
            
        except TimeoutException as e:
            duration = time.time() - start_time
            self.log(f"Diagnostic Agent timed out: {e}", "ERROR")
            return StageResult(
                stage_name="diagnostic_agent",
                stage_number=3,
                success=False,
                duration_seconds=duration,
                error=str(e)
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log(f"Diagnostic Agent failed: {e}", "ERROR")
            import traceback
            if self.verbose:
                traceback.print_exc()
            return StageResult(
                stage_name="diagnostic_agent",
                stage_number=3,
                success=False,
                duration_seconds=duration,
                error=str(e)
            )
    
    def test_scoring_engine(self) -> StageResult:
        """Test the Scoring Engine"""
        self.log("\n" + "="*60)
        self.log("TEST: Scoring Engine")
        self.log("="*60)
        
        start_time = time.time()
        
        try:
            from src.services.talent import MultiDimensionalScoringEngine
            from src.models.talent_analysis import ParsedResume
            
            self.log("Initializing Scoring Engine...")
            engine = MultiDimensionalScoringEngine()
            
            # Create mock parsed resume
            mock_resume = ParsedResume(
                candidate_name="Test Candidate",
                email="test@example.com",
                phone=None,
                current_title="Senior ML Engineer",
                current_company="Google",
                skills=["Python", "TensorFlow", "AWS", "Kubernetes"],
                education=[{"degree": "MS", "field": "Computer Science", "school": "Stanford"}],
                experience_years=7,
                work_history=[
                    {"company": "Google", "title": "Senior ML Engineer", "duration_years": 3},
                ],
                raw_text="Test resume content...",
                parse_confidence=0.95
            )
            
            self.log("Testing scoring engine initialization...")
            duration = time.time() - start_time
            
            # Just test that the engine initializes properly
            self.log("Scoring engine initialized successfully", "SUCCESS")
            
            return StageResult(
                stage_name="scoring_engine",
                stage_number=4,
                success=True,
                duration_seconds=duration,
                details={"initialized": True}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.log(f"Scoring Engine failed: {e}", "ERROR")
            import traceback
            if self.verbose:
                traceback.print_exc()
            return StageResult(
                stage_name="scoring_engine",
                stage_number=4,
                success=False,
                duration_seconds=duration,
                error=str(e)
            )
    
    def test_synthesis_agent(self) -> StageResult:
        """Test the Synthesis Agent"""
        self.log("\n" + "="*60)
        self.log("TEST: Synthesis Agent")
        self.log("="*60)
        
        start_time = time.time()
        
        try:
            from src.services.talent import SynthesisAgentService
            
            self.log("Initializing Synthesis Agent...")
            agent = SynthesisAgentService(
                customer_id=self.customer_id,
                user_id=1
            )
            
            self.log("Synthesis agent initialized successfully", "SUCCESS")
            duration = time.time() - start_time
            
            return StageResult(
                stage_name="synthesis_agent",
                stage_number=5,
                success=True,
                duration_seconds=duration,
                details={"initialized": True}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.log(f"Synthesis Agent failed: {e}", "ERROR")
            import traceback
            if self.verbose:
                traceback.print_exc()
            return StageResult(
                stage_name="synthesis_agent",
                stage_number=5,
                success=False,
                duration_seconds=duration,
                error=str(e)
            )
    
    def test_stuck_analyses(self) -> StageResult:
        """Check for stuck analyses and their last state"""
        self.log("\n" + "="*60)
        self.log("TEST: Stuck Analyses Check")
        self.log("="*60)
        
        start_time = time.time()
        
        try:
            from src.models.connector import TalentAnalysis, TalentAnalysisEvent
            from sqlalchemy import desc
            
            # Get stuck analyses
            stuck = self.db.query(TalentAnalysis).filter(
                TalentAnalysis.status == "processing"
            ).all()
            
            if not stuck:
                self.log("No stuck analyses found", "SUCCESS")
                return StageResult(
                    stage_name="stuck_analyses",
                    stage_number=6,
                    success=True,
                    duration_seconds=time.time() - start_time,
                    details={"stuck_count": 0}
                )
            
            # Get details for each stuck analysis
            details = []
            for analysis in stuck:
                last_event = self.db.query(TalentAnalysisEvent).filter(
                    TalentAnalysisEvent.analysis_id == analysis.analysis_id
                ).order_by(desc(TalentAnalysisEvent.timestamp)).first()
                
                last_step = last_event.event_type if last_event else "unknown"
                details.append(f"{analysis.analysis_id[:12]}:{last_step}")
            
            self.log(f"Found {len(stuck)} stuck analyses", "WARN")
            for d in details[:5]:
                self.log(f"  - {d}")
            
            return StageResult(
                stage_name="stuck_analyses",
                stage_number=6,
                success=False,
                duration_seconds=time.time() - start_time,
                details={"stuck_count": len(stuck), "analyses": details[:5]}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.log(f"Stuck analyses check failed: {e}", "ERROR")
            return StageResult(
                stage_name="stuck_analyses",
                stage_number=6,
                success=False,
                duration_seconds=duration,
                error=str(e)
            )
    
    def run_all_tests(self) -> List[StageResult]:
        """Run all diagnostic tests"""
        results = []
        
        results.append(self.test_openai())
        results.append(self.test_neo4j())
        results.append(self.test_diagnostic_agent())
        results.append(self.test_scoring_engine())
        results.append(self.test_synthesis_agent())
        results.append(self.test_stuck_analyses())
        
        return results
    
    def print_summary(self, results: List[StageResult]):
        """Print a summary of all test results"""
        self.log("\n" + "="*60)
        self.log("DIAGNOSTIC SUMMARY")
        self.log("="*60)
        
        total_duration = sum(r.duration_seconds for r in results)
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        print(f"\n{'Test':<25} {'Status':<10} {'Duration':<12} {'Details'}")
        print("-" * 70)
        
        for r in results:
            status = "✅ PASS" if r.success else "❌ FAIL"
            duration = f"{r.duration_seconds:.2f}s"
            details = ""
            
            if r.details:
                details = ", ".join(f"{k}={v}" for k, v in list(r.details.items())[:2])
            elif r.error:
                error_msg = r.error[:35].replace('\n', ' ')
                details = f"Error: {error_msg}..."
            
            print(f"{r.stage_number}. {r.stage_name:<21} {status:<10} {duration:<12} {details}")
        
        print("-" * 70)
        print(f"{'Total':<25} {successful}/{len(results)} passed  {total_duration:.2f}s")
        
        if failed > 0:
            print(f"\n⚠️  {failed} test(s) failed.")
        else:
            print(f"\n✅ All tests passed!")


def main():
    parser = argparse.ArgumentParser(description="Talent Pipeline Diagnostic Test")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout per test in seconds")
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("🔍 TALENT ANALYSIS PIPELINE DIAGNOSTIC")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Timeout: {args.timeout}s per test")
    
    diagnostic = TalentPipelineDiagnostic(verbose=args.verbose, timeout_seconds=args.timeout)
    
    if not diagnostic.init_database():
        print("\n❌ Failed to initialize database. Exiting.")
        sys.exit(1)
    
    try:
        results = diagnostic.run_all_tests()
        diagnostic.print_summary(results)
        
        if any(not r.success for r in results):
            sys.exit(1)
            
    finally:
        diagnostic.cleanup()


if __name__ == "__main__":
    main()
