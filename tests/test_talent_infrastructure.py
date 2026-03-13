#!/usr/bin/env python3
"""
Talent Analysis Infrastructure Test

This script tests the infrastructure components required for the talent analysis pipeline:
1. Database connectivity
2. Redis/Celery connectivity
3. OpenAI API connectivity
4. Neo4j connectivity (for baseline profiles)
5. Elasticsearch connectivity (for document search)
6. PDL API connectivity (for market search)

Usage:
    python tests/test_talent_infrastructure.py
"""

import os
import sys
import time
from datetime import datetime
from typing import Optional, Tuple

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ENVIRONMENT", "development")


def log(message: str, status: str = "INFO"):
    """Log with timestamp and status icon"""
    icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARN": "⚠️",
        "CHECK": "🔍"
    }
    timestamp = datetime.now().strftime("%H:%M:%S")
    icon = icons.get(status, "")
    print(f"[{timestamp}] {icon} {message}")


def test_database() -> Tuple[bool, str]:
    """Test PostgreSQL database connectivity"""
    log("Testing PostgreSQL database...", "CHECK")
    try:
        from src.models import database
        from sqlalchemy import text
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        
        # Test query
        result = db.execute(text("SELECT 1")).fetchone()
        
        # Check for talent analysis table
        from src.models.connector import TalentAnalysis
        count = db.query(TalentAnalysis).count()
        
        db.close()
        
        return True, f"Connected. {count} talent analyses in database."
    except Exception as e:
        return False, str(e)


def test_redis() -> Tuple[bool, str]:
    """Test Redis connectivity (used by Celery)"""
    log("Testing Redis connectivity...", "CHECK")
    try:
        import redis
        from src.core.config import get_settings
        
        settings = get_settings()
        
        # Parse Redis URL
        redis_url = settings.redis_url
        client = redis.from_url(redis_url)
        
        # Test ping
        client.ping()
        
        # Get some info
        info = client.info()
        connected_clients = info.get('connected_clients', 'unknown')
        
        return True, f"Connected. {connected_clients} connected clients."
    except Exception as e:
        return False, str(e)


def test_celery() -> Tuple[bool, str]:
    """Test Celery worker connectivity"""
    log("Testing Celery worker...", "CHECK")
    try:
        from src.celery_app import celery_app
        
        # Check if workers are available
        inspect = celery_app.control.inspect()
        active = inspect.active()
        
        if active:
            worker_count = len(active)
            task_count = sum(len(tasks) for tasks in active.values())
            return True, f"{worker_count} worker(s) active, {task_count} tasks running."
        else:
            return False, "No active Celery workers found."
    except Exception as e:
        return False, str(e)


def test_openai() -> Tuple[bool, str]:
    """Test OpenAI API connectivity"""
    log("Testing OpenAI API...", "CHECK")
    try:
        from src.core.config import get_settings
        import openai
        
        settings = get_settings()
        
        if not settings.openai_api_key:
            return False, "OPENAI_API_KEY not configured"
        
        client = openai.OpenAI(api_key=settings.openai_api_key)
        
        # Simple test - list models
        models = client.models.list()
        model_count = len(list(models))
        
        return True, f"Connected. {model_count} models available."
    except Exception as e:
        return False, str(e)


def test_neo4j() -> Tuple[bool, str]:
    """Test Neo4j connectivity (for baseline profiles)"""
    log("Testing Neo4j connectivity...", "CHECK")
    try:
        from src.core.config import get_settings
        from neo4j import GraphDatabase
        
        settings = get_settings()
        
        if not settings.neo4j_uri:
            return False, "NEO4J_URI not configured"
        
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count LIMIT 1")
            record = result.single()
            node_count = record["count"] if record else 0
        
        driver.close()
        
        return True, f"Connected. {node_count} nodes in database."
    except Exception as e:
        return False, str(e)


def test_elasticsearch() -> Tuple[bool, str]:
    """Test Elasticsearch connectivity"""
    log("Testing Elasticsearch...", "CHECK")
    try:
        from src.core.config import get_settings
        from elasticsearch import Elasticsearch
        
        settings = get_settings()
        
        # Use elasticsearch_hosts instead of elasticsearch_url
        es_hosts = settings.elasticsearch_hosts
        if isinstance(es_hosts, str):
            es_hosts = [es_hosts]
        
        if not es_hosts:
            return False, "ELASTICSEARCH_HOSTS not configured"
        
        es = Elasticsearch(es_hosts)
        
        if not es.ping():
            return False, "Elasticsearch ping failed"
        
        # Get cluster info
        info = es.info()
        version = info.get('version', {}).get('number', 'unknown')
        
        # Count indices
        indices = es.cat.indices(format='json')
        index_count = len(indices) if indices else 0
        
        return True, f"Connected. Version {version}, {index_count} indices."
    except Exception as e:
        return False, str(e)


def test_pdl_api() -> Tuple[bool, str]:
    """Test People Data Labs API connectivity (checks connector config)"""
    log("Testing PDL API...", "CHECK")
    try:
        from src.models import database
        from src.models.connector import ConnectorConfiguration
        
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        
        # Check for PDL connector configuration
        pdl_configs = db.query(ConnectorConfiguration).filter(
            ConnectorConfiguration.connector_type == "people_data_labs"
        ).all()
        
        db.close()
        
        if pdl_configs:
            return True, f"{len(pdl_configs)} PDL connector(s) configured."
        else:
            return False, "No PDL connector configuration found."
    except Exception as e:
        return False, str(e)


def test_greenhouse_connector() -> Tuple[bool, str]:
    """Test Greenhouse connector configuration"""
    log("Testing Greenhouse connector...", "CHECK")
    try:
        from src.models import database
        from src.models.connector import ConnectorConfiguration
        
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        
        # Find Greenhouse connectors
        connectors = db.query(ConnectorConfiguration).filter(
            ConnectorConfiguration.connector_type == "greenhouse"
        ).all()
        
        db.close()
        
        if connectors:
            return True, f"{len(connectors)} Greenhouse connector(s) found."
        else:
            return False, "No Greenhouse connectors configured."
    except Exception as e:
        return False, str(e)


def test_talent_analysis_status() -> Tuple[bool, str]:
    """Check status of recent talent analyses"""
    log("Checking recent talent analyses...", "CHECK")
    try:
        from src.models import database
        from src.models.connector import TalentAnalysis
        from sqlalchemy import desc
        
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        
        # Get recent analyses
        recent = db.query(TalentAnalysis).order_by(
            desc(TalentAnalysis.created_at)
        ).limit(5).all()
        
        if not recent:
            db.close()
            return True, "No recent analyses found."
        
        # Count by status
        status_counts = {}
        for analysis in recent:
            status = analysis.status or "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Check for stuck analyses
        stuck = [a for a in recent if a.status == "processing" and a.started_at]
        
        db.close()
        
        status_str = ", ".join(f"{s}: {c}" for s, c in status_counts.items())
        
        if stuck:
            return False, f"Recent: {status_str}. {len(stuck)} stuck in processing!"
        
        return True, f"Recent: {status_str}"
    except Exception as e:
        return False, str(e)


def test_stuck_analysis_details() -> Tuple[bool, str]:
    """Get details on stuck analyses to help diagnose issues"""
    log("Analyzing stuck analyses...", "CHECK")
    try:
        from src.models import database
        from src.models.connector import TalentAnalysis, TalentAnalysisEvent
        from sqlalchemy import desc
        from datetime import datetime, timezone
        
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        
        # Get stuck analyses (processing for more than 5 minutes)
        stuck = db.query(TalentAnalysis).filter(
            TalentAnalysis.status == "processing"
        ).all()
        
        if not stuck:
            db.close()
            return True, "No stuck analyses found."
        
        details = []
        for analysis in stuck:
            # Get the last event for this analysis
            last_event = db.query(TalentAnalysisEvent).filter(
                TalentAnalysisEvent.analysis_id == analysis.analysis_id
            ).order_by(desc(TalentAnalysisEvent.timestamp)).first()
            
            age = ""
            if analysis.started_at:
                # Handle timezone-aware/naive datetime comparison
                started = analysis.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                age_mins = (now - started).total_seconds() / 60
                age = f"{age_mins:.0f}min"
            
            last_step = last_event.event_type if last_event else "unknown"
            progress = last_event.progress_percentage if last_event else 0
            
            details.append(f"{analysis.analysis_id[:8]}({age}, {progress}%, {last_step})")
        
        db.close()
        
        return False, f"{len(stuck)} stuck: " + ", ".join(details[:3])
    except Exception as e:
        return False, str(e)


def main():
    print("\n" + "="*60)
    print("🏗️  TALENT ANALYSIS INFRASTRUCTURE TEST")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    tests = [
        ("PostgreSQL Database", test_database),
        ("Redis", test_redis),
        ("Celery Workers", test_celery),
        ("OpenAI API", test_openai),
        ("Neo4j", test_neo4j),
        ("Elasticsearch", test_elasticsearch),
        ("PDL API", test_pdl_api),
        ("Greenhouse Connector", test_greenhouse_connector),
        ("Recent Analyses Status", test_talent_analysis_status),
        ("Stuck Analysis Details", test_stuck_analysis_details),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success, message = test_func()
            results.append((name, success, message))
            
            if success:
                log(f"{name}: {message}", "SUCCESS")
            else:
                log(f"{name}: {message}", "ERROR")
        except Exception as e:
            results.append((name, False, str(e)))
            log(f"{name}: {e}", "ERROR")
    
    # Summary
    print("\n" + "="*60)
    print("📊 INFRASTRUCTURE TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, success, _ in results if success)
    failed = len(results) - passed
    
    print(f"\n{'Component':<25} {'Status':<10} {'Details'}")
    print("-" * 70)
    
    for name, success, message in results:
        status = "✅ PASS" if success else "❌ FAIL"
        # Truncate message if too long
        msg = message[:40] + "..." if len(message) > 40 else message
        print(f"{name:<25} {status:<10} {msg}")
    
    print("-" * 70)
    print(f"{'Total':<25} {passed}/{len(results)} passed")
    
    if failed > 0:
        print(f"\n⚠️  {failed} component(s) failed. Fix these before running pipeline tests.")
        sys.exit(1)
    else:
        print(f"\n✅ All infrastructure components are healthy!")
        sys.exit(0)


if __name__ == "__main__":
    main()

