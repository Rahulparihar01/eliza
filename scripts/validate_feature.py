#!/usr/bin/env python3
"""
Feature Validation Script

Validates that a feature implementation follows all platform patterns and rules.
Run this before submitting a PR to catch common issues.

Usage:
    python scripts/validate_feature.py [feature_name]
    python scripts/validate_feature.py --all
    python scripts/validate_feature.py --check routes
    python scripts/validate_feature.py --check tasks
    python scripts/validate_feature.py --check models
    python scripts/validate_feature.py --check agents
"""

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple


class CheckStatus(Enum):
    PASS = "✅"
    WARN = "⚠️"
    FAIL = "❌"
    SKIP = "⏭️"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    file: Optional[str] = None
    line: Optional[int] = None


class FeatureValidator:
    """Validates feature implementations against platform patterns."""
    
    def __init__(self, project_root: Path):
        self.root = project_root
        self.results: List[CheckResult] = []
    
    def add_result(self, name: str, status: CheckStatus, message: str, 
                   file: Optional[str] = None, line: Optional[int] = None):
        self.results.append(CheckResult(name, status, message, file, line))
    
    # ================================================================
    # API Route Checks
    # ================================================================
    def check_routes(self, route_file: Path) -> List[CheckResult]:
        """Validate API route file."""
        results = []
        
        if not route_file.exists():
            return [CheckResult("Route File", CheckStatus.SKIP, f"File not found: {route_file}")]
        
        content = route_file.read_text()
        
        # Check 1: Response model on all endpoints
        endpoints = re.findall(r'@router\.(get|post|put|patch|delete)\([^)]*\)', content)
        response_models = re.findall(r'response_model=\w+', content)
        
        if len(endpoints) > 0 and len(response_models) < len(endpoints):
            results.append(CheckResult(
                "Response Models",
                CheckStatus.WARN,
                f"Found {len(endpoints)} endpoints but only {len(response_models)} have response_model",
                str(route_file)
            ))
        else:
            results.append(CheckResult(
                "Response Models",
                CheckStatus.PASS,
                "All endpoints have response models"
            ))
        
        # Check 2: Authorization middleware used
        if 'auth_middleware' not in content and 'require_permission' not in content:
            results.append(CheckResult(
                "Authorization",
                CheckStatus.FAIL,
                "No authorization middleware found - endpoints may be unprotected",
                str(route_file)
            ))
        else:
            results.append(CheckResult(
                "Authorization",
                CheckStatus.PASS,
                "Authorization middleware is used"
            ))
        
        # Check 3: No hardcoded None in responses
        hardcoded_none = re.findall(r'\w+=None.*#.*[Nn]ot stored|TODO', content)
        if hardcoded_none:
            results.append(CheckResult(
                "Hardcoded Values",
                CheckStatus.FAIL,
                "Found hardcoded None values with TODO comments - map to actual database fields",
                str(route_file)
            ))
        else:
            results.append(CheckResult(
                "Hardcoded Values",
                CheckStatus.PASS,
                "No suspicious hardcoded None values"
            ))
        
        # Check 4: Proper HTTP status codes
        if '@router.post' in content and 'status.HTTP_201' not in content and 'status.HTTP_202' not in content:
            results.append(CheckResult(
                "HTTP Status Codes",
                CheckStatus.WARN,
                "POST endpoint may not have correct status code (201 for sync, 202 for async)",
                str(route_file)
            ))
        else:
            results.append(CheckResult(
                "HTTP Status Codes",
                CheckStatus.PASS,
                "HTTP status codes appear correct"
            ))
        
        # Check 5: Logging at key operations
        if 'logger.info' not in content and 'logger.error' not in content:
            results.append(CheckResult(
                "Logging",
                CheckStatus.WARN,
                "No logging found - add logging for key operations",
                str(route_file)
            ))
        else:
            results.append(CheckResult(
                "Logging",
                CheckStatus.PASS,
                "Logging is present"
            ))
        
        return results
    
    # ================================================================
    # Celery Task Checks
    # ================================================================
    def check_tasks(self, task_file: Path) -> List[CheckResult]:
        """Validate Celery task file."""
        results = []
        
        if not task_file.exists():
            return [CheckResult("Task File", CheckStatus.SKIP, f"File not found: {task_file}")]
        
        content = task_file.read_text()
        
        # Check 1: Module-level database import (CRITICAL!)
        if 'from src.models.database import SessionLocal' in content:
            results.append(CheckResult(
                "Database Import",
                CheckStatus.FAIL,
                "CRITICAL: Direct SessionLocal import will cause 'SessionLocal is None' error. Use: from src.models import database",
                str(task_file)
            ))
        elif 'from src.models import database' in content:
            results.append(CheckResult(
                "Database Import",
                CheckStatus.PASS,
                "Using correct module-level database import"
            ))
        else:
            results.append(CheckResult(
                "Database Import",
                CheckStatus.WARN,
                "Could not verify database import pattern",
                str(task_file)
            ))
        
        # Check 2: SessionLocal initialization check
        if 'database.SessionLocal is None' in content or 'if SessionLocal is None' in content:
            results.append(CheckResult(
                "Session Init Check",
                CheckStatus.PASS,
                "SessionLocal None check present"
            ))
        elif '@celery_app.task' in content:
            results.append(CheckResult(
                "Session Init Check",
                CheckStatus.FAIL,
                "Missing SessionLocal None check before use",
                str(task_file)
            ))
        
        # Check 3: try/finally for session cleanup
        if 'finally:' in content and ('db.close()' in content or 'session.close()' in content):
            results.append(CheckResult(
                "Session Cleanup",
                CheckStatus.PASS,
                "Database session cleanup in finally block"
            ))
        elif '@celery_app.task' in content:
            results.append(CheckResult(
                "Session Cleanup",
                CheckStatus.FAIL,
                "Missing try/finally for database session cleanup",
                str(task_file)
            ))
        
        # Check 4: Task has bind=True
        if '@celery_app.task' in content and 'bind=True' not in content:
            results.append(CheckResult(
                "Task Binding",
                CheckStatus.WARN,
                "Task missing bind=True - won't have access to self.request",
                str(task_file)
            ))
        else:
            results.append(CheckResult(
                "Task Binding",
                CheckStatus.PASS,
                "Task has bind=True"
            ))
        
        # Check 5: Timeout handling
        if '@celery_app.task' in content and 'SoftTimeLimitExceeded' not in content:
            results.append(CheckResult(
                "Timeout Handling",
                CheckStatus.WARN,
                "Consider adding SoftTimeLimitExceeded handling for long tasks",
                str(task_file)
            ))
        else:
            results.append(CheckResult(
                "Timeout Handling",
                CheckStatus.PASS,
                "Timeout handling present"
            ))
        
        return results
    
    # ================================================================
    # Database Model Checks
    # ================================================================
    def check_models(self, model_file: Path) -> List[CheckResult]:
        """Validate SQLAlchemy model file."""
        results = []
        
        if not model_file.exists():
            return [CheckResult("Model File", CheckStatus.SKIP, f"File not found: {model_file}")]
        
        content = model_file.read_text()
        
        # Check 1: customer_id for multi-tenant
        if 'class ' in content and '(BaseModel)' in content:
            if 'customer_id' not in content:
                results.append(CheckResult(
                    "Multi-Tenant",
                    CheckStatus.WARN,
                    "Model missing customer_id - may not support multi-tenancy",
                    str(model_file)
                ))
            else:
                results.append(CheckResult(
                    "Multi-Tenant",
                    CheckStatus.PASS,
                    "customer_id field present"
                ))
        
        # Check 2: BaseModel vs Base usage
        if '(Base)' in content and 'created_at' in content:
            results.append(CheckResult(
                "Base Class",
                CheckStatus.WARN,
                "Using Base with created_at - consider if BaseModel is more appropriate",
                str(model_file)
            ))
        
        # Check 3: Status enum defined
        if 'status' in content.lower() and 'class' in content:
            if 'Enum' not in content:
                results.append(CheckResult(
                    "Status Enum",
                    CheckStatus.WARN,
                    "Status field found but no Enum defined - consider using an Enum for status values",
                    str(model_file)
                ))
            else:
                results.append(CheckResult(
                    "Status Enum",
                    CheckStatus.PASS,
                    "Status enum defined"
                ))
        
        # Check 4: Index on foreign keys
        if 'ForeignKey' in content and 'index=True' not in content:
            results.append(CheckResult(
                "FK Indexes",
                CheckStatus.WARN,
                "Foreign keys found without index=True - may cause slow queries",
                str(model_file)
            ))
        else:
            results.append(CheckResult(
                "FK Indexes",
                CheckStatus.PASS,
                "Foreign keys have indexes"
            ))
        
        return results
    
    # ================================================================
    # Migration Checks
    # ================================================================
    def check_migrations(self, migration_dir: Path) -> List[CheckResult]:
        """Validate migration files."""
        results = []
        
        if not migration_dir.exists():
            return [CheckResult("Migrations", CheckStatus.SKIP, f"Directory not found: {migration_dir}")]
        
        migration_files = list(migration_dir.glob("*.py"))
        if not migration_files:
            return [CheckResult("Migrations", CheckStatus.SKIP, "No migration files found")]
        
        # Check latest migration
        latest = sorted(migration_files)[-1]
        content = latest.read_text()
        
        # Check 1: down_revision is set
        if "down_revision = None" in content and "Initial" not in str(latest):
            results.append(CheckResult(
                "Migration Chain",
                CheckStatus.WARN,
                f"down_revision is None in {latest.name} - verify this is intentional",
                str(latest)
            ))
        else:
            results.append(CheckResult(
                "Migration Chain",
                CheckStatus.PASS,
                "Migration chaining looks correct"
            ))
        
        # Check 2: downgrade function exists and has content
        if 'def downgrade()' in content:
            downgrade_match = re.search(r'def downgrade\(\)[^:]*:\s*\n([\s\S]*?)(?=\ndef |\Z)', content)
            if downgrade_match and 'pass' in downgrade_match.group(1) and 'op.' not in downgrade_match.group(1):
                results.append(CheckResult(
                    "Downgrade",
                    CheckStatus.WARN,
                    "downgrade() appears to only have 'pass' - add rollback logic",
                    str(latest)
                ))
            else:
                results.append(CheckResult(
                    "Downgrade",
                    CheckStatus.PASS,
                    "downgrade() has rollback logic"
                ))
        else:
            results.append(CheckResult(
                "Downgrade",
                CheckStatus.FAIL,
                "No downgrade() function found",
                str(latest)
            ))
        
        return results
    
    # ================================================================
    # Agent / Langfuse Checks
    # ================================================================
    def check_agents_langfuse(self) -> List[CheckResult]:
        """
        Ensure agent-bearing modules are instrumented with Langfuse service.

        Rule:
        - Any file that instantiates Agent(...) must:
          1) call get_langfuse_service(), and
          2) emit at least one Langfuse tracing call.
        """
        results: List[CheckResult] = []
        candidate_files: List[Path] = []
        source_dirs = [self.root / "src/flows", self.root / "src/services"]

        for source_dir in source_dirs:
            if not source_dir.exists():
                continue
            for py_file in source_dir.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if re.search(r"\bAgent\s*\(", content):
                    candidate_files.append(py_file)

        if not candidate_files:
            return [CheckResult(
                "Agent Langfuse Tracing",
                CheckStatus.SKIP,
                "No Agent(...) usages found in src/flows or src/services",
            )]

        trace_call_pattern = re.compile(
            r"\.(?:"
            r"span_scope|trace_scope|begin_trace_scope|end_trace_scope|trace_event|"
            r"trace_generation|trace_retrieval|trace_workspace_chat|"
            r"trace_workspace_span|trace_workspace_chain"
            r")\s*\("
        )

        missing_files: List[str] = []
        for py_file in candidate_files:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            has_get_call = bool(re.search(r"\bget_langfuse_service\s*\(", content))
            has_trace_call = bool(trace_call_pattern.search(content))
            if not (has_get_call and has_trace_call):
                try:
                    rel_path = str(py_file.relative_to(self.root))
                except Exception:
                    rel_path = str(py_file)
                missing_files.append(rel_path)

        if missing_files:
            for rel_path in missing_files:
                results.append(CheckResult(
                    "Agent Langfuse Tracing",
                    CheckStatus.FAIL,
                    (
                        "File instantiates Agent(...) but is missing required Langfuse "
                        "service wiring and/or trace emission calls."
                    ),
                    rel_path,
                ))
            return results

        results.append(CheckResult(
            "Agent Langfuse Tracing",
            CheckStatus.PASS,
            f"All {len(candidate_files)} agent-bearing file(s) include Langfuse tracing",
        ))
        return results

    # ================================================================
    # Run All Checks
    # ================================================================
    def validate_feature(self, feature_name: str) -> List[CheckResult]:
        """Run all validations for a feature."""
        results = []
        
        # Check routes
        route_file = self.root / f"src/api/routes/{feature_name}.py"
        if route_file.exists():
            results.extend(self.check_routes(route_file))
        
        # Check tasks
        task_file = self.root / f"src/tasks/{feature_name}_tasks.py"
        if task_file.exists():
            results.extend(self.check_tasks(task_file))
        
        # Check models
        model_file = self.root / f"src/models/{feature_name}.py"
        if model_file.exists():
            results.extend(self.check_models(model_file))
        
        # Check migrations
        results.extend(self.check_migrations(self.root / "alembic/versions"))

        # Cross-cutting agent observability guardrail
        results.extend(self.check_agents_langfuse())
        
        return results
    
    def validate_all(self) -> List[CheckResult]:
        """Run validations on all source files."""
        results = []
        
        # Check all routes
        routes_dir = self.root / "src/api/routes"
        if routes_dir.exists():
            for route_file in routes_dir.glob("*.py"):
                if route_file.name != "__init__.py":
                    results.extend(self.check_routes(route_file))
        
        # Check all tasks
        tasks_dir = self.root / "src/tasks"
        if tasks_dir.exists():
            for task_file in tasks_dir.glob("*_tasks.py"):
                results.extend(self.check_tasks(task_file))
        
        # Check all models
        models_dir = self.root / "src/models"
        if models_dir.exists():
            for model_file in models_dir.glob("*.py"):
                if model_file.name not in ["__init__.py", "database.py"]:
                    results.extend(self.check_models(model_file))
        
        # Check migrations
        results.extend(self.check_migrations(self.root / "alembic/versions"))

        # Check Langfuse instrumentation for all agent-bearing modules
        results.extend(self.check_agents_langfuse())
        
        return results


def print_results(results: List[CheckResult]):
    """Print validation results in a formatted way."""
    print("\n" + "=" * 60)
    print("FEATURE VALIDATION RESULTS")
    print("=" * 60 + "\n")
    
    # Group by status
    passes = [r for r in results if r.status == CheckStatus.PASS]
    warns = [r for r in results if r.status == CheckStatus.WARN]
    fails = [r for r in results if r.status == CheckStatus.FAIL]
    skips = [r for r in results if r.status == CheckStatus.SKIP]
    
    # Print failures first
    if fails:
        print("❌ FAILURES (must fix):\n")
        for r in fails:
            print(f"  {r.status.value} {r.name}")
            print(f"     {r.message}")
            if r.file:
                print(f"     File: {r.file}")
            print()
    
    # Print warnings
    if warns:
        print("⚠️  WARNINGS (should review):\n")
        for r in warns:
            print(f"  {r.status.value} {r.name}")
            print(f"     {r.message}")
            if r.file:
                print(f"     File: {r.file}")
            print()
    
    # Print passes
    if passes:
        print("✅ PASSED:\n")
        for r in passes:
            print(f"  {r.status.value} {r.name}")
        print()
    
    # Print skips
    if skips:
        print("⏭️  SKIPPED:\n")
        for r in skips:
            print(f"  {r.status.value} {r.name}: {r.message}")
        print()
    
    # Summary
    print("=" * 60)
    print(f"SUMMARY: {len(passes)} passed, {len(warns)} warnings, {len(fails)} failures, {len(skips)} skipped")
    print("=" * 60)
    
    return len(fails) == 0


def main():
    parser = argparse.ArgumentParser(description="Validate feature implementation")
    parser.add_argument("feature", nargs="?", help="Feature name to validate")
    parser.add_argument("--all", action="store_true", help="Validate all features")
    parser.add_argument("--check", choices=["routes", "tasks", "models", "migrations", "agents"],
                        help="Run specific check type")
    args = parser.parse_args()
    
    # Find project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    
    validator = FeatureValidator(project_root)
    
    if args.all:
        results = validator.validate_all()
    elif args.check:
        if args.check == "routes":
            routes_dir = project_root / "src/api/routes"
            results = []
            for f in routes_dir.glob("*.py"):
                if f.name != "__init__.py":
                    results.extend(validator.check_routes(f))
        elif args.check == "tasks":
            tasks_dir = project_root / "src/tasks"
            results = []
            for f in tasks_dir.glob("*_tasks.py"):
                results.extend(validator.check_tasks(f))
        elif args.check == "models":
            models_dir = project_root / "src/models"
            results = []
            for f in models_dir.glob("*.py"):
                if f.name not in ["__init__.py", "database.py"]:
                    results.extend(validator.check_models(f))
        elif args.check == "migrations":
            results = validator.check_migrations(project_root / "alembic/versions")
        elif args.check == "agents":
            results = validator.check_agents_langfuse()
    elif args.feature:
        results = validator.validate_feature(args.feature)
    else:
        parser.print_help()
        sys.exit(1)
    
    success = print_results(results)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
