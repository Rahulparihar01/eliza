"""
PDL Query Construction Rules and Guidelines.

This module defines rules for building effective PDL (People Data Labs) search queries
based on empirical testing and PDL API documentation.

These rules are used by the diagnostic agent and query builder to construct
optimized queries dynamically based on job requirements and baseline analysis.
"""

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class PDLFieldRules:
    """Rules and guidance for a specific PDL field."""
    field_name: str
    field_type: str  # "term", "match", "terms", "wildcard"
    is_standardized: bool  # True if field uses predefined values
    typical_values: List[str]  # Example valid values
    use_cases: str  # When to use this field
    result_size_impact: str  # "broad", "moderate", "narrow"
    best_practices: List[str]
    example_query: Dict[str, Any]


# PDL Field Rules Database
PDL_FIELD_RULES = {
    "job_title_role": PDLFieldRules(
        field_name="job_title_role",
        field_type="term",
        is_standardized=True,
        typical_values=[
            "engineering",
            "sales",
            "marketing",
            "operations",
            "finance",
            "education",
            "health",
            "legal",
            "media"
        ],
        use_cases="Use for broad role categorization. NOT for specific job titles.",
        result_size_impact="broad",
        best_practices=[
            "Use standardized values only (e.g., 'engineering', not 'software engineer')",
            "Combine with skills for better targeting",
            "Good for initial broad filtering",
            "Verified: 'engineering' returns 27.4M results"
        ],
        example_query={
            "term": {"job_title_role": "engineering"}
        }
    ),
    
    "job_title": PDLFieldRules(
        field_name="job_title",
        field_type="match",
        is_standardized=False,
        typical_values=[
            "software engineer",
            "machine learning engineer",
            "data scientist",
            "senior ml engineer",
            "ai researcher"
        ],
        use_cases="Use for specific job title matching. Allows partial text matching.",
        result_size_impact="moderate",
        best_practices=[
            "Use 'match' query type for partial matching",
            "Include key terms like 'machine learning', 'data scientist', etc.",
            "Works with actual job titles from resumes/profiles",
            "Verified: 'machine learning engineer' returns 8,590 results",
            "More specific than job_title_role but broader than exact match"
        ],
        example_query={
            "match": {"job_title": "machine learning engineer"}
        }
    ),
    
    "skills": PDLFieldRules(
        field_name="skills",
        field_type="term",
        is_standardized=False,
        typical_values=[
            "python",
            "tensorflow",
            "pytorch",
            "machine learning",
            "deep learning",
            "scikit-learn",
            "kubernetes",
            "aws"
        ],
        use_cases="Use for technical skill requirements. Can be very specific.",
        result_size_impact="moderate to narrow",
        best_practices=[
            "Use specific technology names (lowercase)",
            "Each skill is an AND condition (must have all)",
            "Combine required vs optional skills carefully",
            "Verified: 'python' + US location returns 1.6M results",
            "Adding 'machine learning' + 'python' narrows to 156K results",
            "Don't over-constrain: 3-5 skills is usually optimal"
        ],
        example_query={
            "term": {"skills": "tensorflow"}
        }
    ),
    
    "location_country": PDLFieldRules(
        field_name="location_country",
        field_type="term",
        is_standardized=True,
        typical_values=[
            "united states",
            "canada",
            "united kingdom",
            "germany",
            "india",
            "australia"
        ],
        use_cases="Use for geographic filtering. Highly recommended to include.",
        result_size_impact="broad",
        best_practices=[
            "Always use lowercase",
            "Use full country names",
            "Highly recommended to include for credit control",
            "Verified: 'united states' alone returns 193M results",
            "Combining with other filters is essential"
        ],
        example_query={
            "term": {"location_country": "united states"}
        }
    ),
    
    "job_company_name": PDLFieldRules(
        field_name="job_company_name",
        field_type="term",
        is_standardized=False,
        typical_values=[
            "google",
            "microsoft",
            "amazon",
            "facebook",
            "apple"
        ],
        use_cases="Use for targeting candidates from specific companies.",
        result_size_impact="narrow",
        best_practices=[
            "Use lowercase company names",
            "Good for 'look-alike' searches (find people from similar companies)",
            "Verified: 'google' returns 348K results",
            "Can use multiple companies with 'terms' query"
        ],
        example_query={
            "term": {"job_company_name": "google"}
        }
    ),
    
    "job_title_levels": PDLFieldRules(
        field_name="job_title_levels",
        field_type="terms",
        is_standardized=True,
        typical_values=[
            "entry",
            "senior",
            "lead",
            "principal",
            "manager",
            "director",
            "vp",
            "c-level"
        ],
        use_cases="Use for seniority filtering. Can be too restrictive.",
        result_size_impact="narrow",
        best_practices=[
            "Use with caution - may over-constrain results",
            "Use 'terms' for multiple levels",
            "Consider omitting for broader searches",
            "Verified: Adding levels can reduce results to 0"
        ],
        example_query={
            "terms": {"job_title_levels": ["senior", "lead", "principal"]}
        }
    ),
    
    "job_title_sub_role": PDLFieldRules(
        field_name="job_title_sub_role",
        field_type="term",
        is_standardized=True,
        typical_values=[
            "software",
            "data",
            "web",
            "mobile",
            "infrastructure",
            "security"
        ],
        use_cases="Use for sub-role categorization within engineering.",
        result_size_impact="moderate",
        best_practices=[
            "More specific than job_title_role",
            "Good for narrowing within a role category",
            "Combine with job_title_role='engineering' for best results"
        ],
        example_query={
            "term": {"job_title_sub_role": "data"}
        }
    )
}


# Query Construction Strategies
QUERY_STRATEGIES = {
    "broad_exploration": {
        "name": "Broad Exploration",
        "description": "Cast a wide net to discover candidate pool size",
        "recommended_fields": ["job_title_role", "location_country"],
        "avoid_fields": ["job_title_levels", "job_company_name"],
        "expected_results": "10K - 1M+ candidates",
        "use_when": [
            "Initial market sizing",
            "Exploring available talent pool",
            "Role is common (e.g., 'software engineer')"
        ],
        "example": {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"job_title_role": "engineering"}},
                        {"term": {"location_country": "united states"}}
                    ]
                }
            }
        }
    },
    
    "targeted_search": {
        "name": "Targeted Search",
        "description": "Balance specificity and pool size for quality matches",
        "recommended_fields": ["job_title", "skills", "location_country"],
        "avoid_fields": ["job_title_levels"],
        "expected_results": "1K - 50K candidates",
        "use_when": [
            "Looking for specific role (e.g., 'ML engineer')",
            "Have clear skill requirements",
            "Need quality over quantity"
        ],
        "example": {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"job_title": "machine learning engineer"}},
                        {"term": {"skills": "tensorflow"}},
                        {"term": {"location_country": "united states"}}
                    ]
                }
            }
        }
    },
    
    "precision_search": {
        "name": "Precision Search",
        "description": "Highly specific search for niche requirements",
        "recommended_fields": ["job_title", "skills", "location_country", "job_company_name"],
        "avoid_fields": [],
        "expected_results": "10 - 1K candidates",
        "use_when": [
            "Very specific technical requirements",
            "Looking for experts in niche area",
            "Targeting candidates from specific companies"
        ],
        "example": {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"job_title": "machine learning"}},
                        {"term": {"job_title_role": "engineering"}},
                        {"term": {"skills": "tensorflow"}},
                        {"term": {"skills": "pytorch"}},
                        {"term": {"location_country": "united states"}}
                    ]
                }
            }
        }
    },
    
    "company_cluster_search": {
        "name": "Company Cluster Search",
        "description": "Find candidates from similar companies (look-alike)",
        "recommended_fields": ["job_company_name", "job_title", "skills"],
        "avoid_fields": ["location_country"],  # Optional - may be too restrictive
        "expected_results": "100 - 10K candidates",
        "use_when": [
            "Baseline shows candidates from specific companies perform well",
            "Want candidates with similar company experience",
            "Looking for 'look-alike' profiles"
        ],
        "example": {
            "query": {
                "bool": {
                    "must": [
                        {"terms": {"job_company_name": ["google", "microsoft", "amazon"]}},
                        {"match": {"job_title": "machine learning"}}
                    ]
                }
            }
        }
    }
}


# Query Construction Rules
QUERY_CONSTRUCTION_RULES = {
    "credit_control": {
        "rule": "Always set a 'size' limit to control credit usage",
        "rationale": "PDL charges per result returned",
        "implementation": "Set 'size' parameter to max_records (typically 50-100)",
        "critical": True
    },
    
    "location_filter": {
        "rule": "Include location_country unless specifically omitted",
        "rationale": "Reduces result set significantly (193M → smaller subset)",
        "implementation": "Add location_country='united states' or target country",
        "critical": False
    },
    
    "field_standardization": {
        "rule": "Use standardized values for standardized fields",
        "rationale": "job_title_role, job_title_levels, etc. have predefined values",
        "implementation": "Check PDL_FIELD_RULES[field].is_standardized before use",
        "critical": True
    },
    
    "query_type_selection": {
        "rule": "Use 'term' for exact match, 'match' for partial, 'terms' for multiple values",
        "rationale": "PDL Elasticsearch requires correct query type",
        "implementation": "Check PDL_FIELD_RULES[field].field_type",
        "critical": True
    },
    
    "skill_balance": {
        "rule": "Use 2-5 required skills, avoid over-constraining",
        "rationale": "Too many skills returns 0 results, too few is too broad",
        "implementation": "Separate 'required' (must have) from 'optional' (nice to have)",
        "critical": False
    },
    
    "lowercase_values": {
        "rule": "Convert all string values to lowercase",
        "rationale": "PDL stores values in lowercase",
        "implementation": "Apply .lower() to all string values",
        "critical": True
    },
    
    "avoid_over_filtering": {
        "rule": "Start broad, then narrow based on result count",
        "rationale": "Too many filters = 0 results",
        "implementation": "Begin with 2-3 filters, check result count, add more if needed",
        "critical": False
    },
    
    "minimum_should_match_not_supported": {
        "rule": "Do NOT use 'minimum_should_match' or complex 'should' clauses",
        "rationale": "PDL API returns 400 error for this clause",
        "implementation": "Use 'must' clauses only, or 'terms' for OR logic",
        "critical": True
    }
}


# Field Compatibility Matrix
FIELD_COMPATIBILITY = {
    "high_compatibility": [
        ("job_title_role", "skills"),
        ("job_title", "skills"),
        ("job_title", "location_country"),
        ("skills", "location_country"),
        ("job_company_name", "job_title")
    ],
    "moderate_compatibility": [
        ("job_title_role", "job_title"),  # Can work but may be redundant
        ("job_title_role", "job_title_sub_role"),
        ("skills", "job_company_name")
    ],
    "low_compatibility": [
        ("job_title_levels", "job_title"),  # Often over-constrains
        ("job_title_role", "job_company_name"),  # May be too specific
    ]
}


# Verified Query Performance (from testing)
VERIFIED_QUERIES = {
    "location_only": {
        "query": {"term": {"location_country": "united states"}},
        "results": 193_892_946,
        "status": "works"
    },
    "skills_python_us": {
        "query": {
            "bool": {
                "must": [
                    {"term": {"skills": "python"}},
                    {"term": {"location_country": "united states"}}
                ]
            }
        },
        "results": 1_648_307,
        "status": "works"
    },
    "engineering_ml_skills": {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_title_role": "engineering"}},
                    {"term": {"skills": "machine learning"}},
                    {"term": {"skills": "python"}},
                    {"term": {"location_country": "united states"}}
                ]
            }
        },
        "results": 156_833,
        "status": "works"
    },
    "ml_engineer_title": {
        "query": {
            "bool": {
                "must": [
                    {"match": {"job_title": "machine learning engineer"}},
                    {"term": {"location_country": "united states"}}
                ]
            }
        },
        "results": 8_590,
        "status": "works"
    },
    "google_employees": {
        "query": {"term": {"job_company_name": "google"}},
        "results": 348_872,
        "status": "works"
    },
    "engineering_role_only": {
        "query": {"term": {"job_title_role": "engineering"}},
        "results": 27_453_611,
        "status": "works"
    },
    "software_engineer_role": {
        "query": {"term": {"job_title_role": "software engineer"}},
        "results": 0,
        "status": "fails - not a valid standardized value"
    }
}


def get_field_rules(field_name: str) -> PDLFieldRules:
    """Get rules for a specific PDL field."""
    return PDL_FIELD_RULES.get(field_name)


def get_query_strategy(strategy_name: str) -> Dict[str, Any]:
    """Get a specific query construction strategy."""
    return QUERY_STRATEGIES.get(strategy_name)


def get_rule(rule_name: str) -> Dict[str, Any]:
    """Get a specific query construction rule."""
    return QUERY_CONSTRUCTION_RULES.get(rule_name)


def validate_field_value(field_name: str, value: Any) -> tuple[bool, str]:
    """
    Validate that a field value is appropriate for the field.
    
    Returns:
        (is_valid, message)
    """
    rules = get_field_rules(field_name)
    if not rules:
        return True, f"No rules defined for field '{field_name}'"
    
    # Check if value is lowercase (for string fields)
    if isinstance(value, str) and value != value.lower():
        return False, f"Value '{value}' should be lowercase: '{value.lower()}'"
    
    # Check if standardized field uses known values
    if rules.is_standardized and isinstance(value, str):
        if value not in rules.typical_values:
            return False, (
                f"Value '{value}' may not be valid for standardized field '{field_name}'. "
                f"Typical values: {', '.join(rules.typical_values[:5])}"
            )
    
    return True, "Valid"


def recommend_query_strategy(
    role_specificity: str,  # "broad", "moderate", "specific"
    skill_count: int,
    has_company_baseline: bool
) -> str:
    """
    Recommend a query strategy based on search parameters.
    
    Args:
        role_specificity: How specific the role is
        skill_count: Number of required skills
        has_company_baseline: Whether baseline includes specific companies
        
    Returns:
        Strategy name (key from QUERY_STRATEGIES)
    """
    if has_company_baseline:
        return "company_cluster_search"
    
    if role_specificity == "specific" and skill_count >= 3:
        return "precision_search"
    
    if role_specificity == "moderate" or skill_count >= 2:
        return "targeted_search"
    
    return "broad_exploration"


