#!/usr/bin/env python3
"""
Train Vanna AI on insurance database schema and domain knowledge.

This script follows Vanna best practices:
1. Comprehensive DDL training (all schema files)
2. Rich domain documentation (business context, metrics, terminology)
3. Diverse question-SQL pairs covering common patterns, complex logic, and KPIs

Best Practices Applied:
- High-quality, accurate SQL examples
- Diverse query patterns (aggregations, joins, date filters, groupings)
- Clear, well-commented SQL
- Business context in documentation
- Representative examples from different personas
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.services.vanna_service import VannaService
from src.core.config import get_settings

def main():
    """Train Vanna on insurance database following best practices."""
    settings = get_settings()
    
    print("🚀 Initializing Vanna service...")
    vanna_service = VannaService(
        database_url=settings.insurance_demo_db_url,
        model="gpt-4o-mini"  # Use OpenAI model for Vanna
    )
    
    # ============================================================================
    # STEP 1: Train on DDL (Database Schema)
    # ============================================================================
    print("\n📋 STEP 1: Training on DDL schemas...")
    ddl_dir = Path("/app/design_docs/analytics_insurance/insurance_demo_ddl")
    ddl_files = [
        "core_party.sql",
        "core_agent.sql",
        "auto_auto_exposure.sql",
        "auto_policy_auto.sql",
        "auto_claim_auto.sql",
        "auto_claim_transaction.sql",
        "auto_premium_transaction.sql",
        "property_property_exposure.sql",
        "property_policy_property.sql",
        "property_claim_property.sql",
        "property_claim_transaction.sql",
        "property_premium_transaction.sql",
        "analytics_customer_360_view.sql"
    ]
    
    ddl_statements = []
    for ddl_file in ddl_files:
        ddl_path = ddl_dir / ddl_file
        if ddl_path.exists():
            print(f"  ✅ Loading {ddl_file}")
            with open(ddl_path, 'r') as f:
                ddl_content = f.read()
                if ddl_content.strip():
                    ddl_statements.append(ddl_content)
        else:
            print(f"  ⚠️  File not found: {ddl_path}")
    
    if ddl_statements:
        vanna_service.train_on_ddl(ddl_statements)
        print(f"  ✅ Trained on {len(ddl_statements)} DDL files")
    
    # ============================================================================
    # STEP 2: Train on Domain Documentation (Business Context)
    # ============================================================================
    print("\n📚 STEP 2: Training on domain documentation...")
    domain_docs = """
Insurance Analytics Domain Knowledge and Business Context

=== KEY METRICS AND CALCULATIONS ===

Loss Ratio:
- Formula: total incurred claims / earned premium
- Interpretation: < 60% is good, > 80% is concerning
- Calculation requires joining policies with claims

Claim Frequency:
- Formula: number of claims / number of policies
- Typically expressed per 1,000 policies
- Higher frequency indicates higher risk

Average Severity:
- Formula: total incurred amount / number of claims
- Measures average cost per claim
- Higher severity indicates more expensive claims

=== CUSTOMER SEGMENTS ===

HNW (High Net Worth):
- Premium customer segment
- Typically higher policy values
- Lower loss ratios expected

Personal Standard:
- Standard personal insurance customers
- Mainstream market segment
- Moderate risk profile

SMB (Small Medium Business):
- Small to medium business customers
- Commercial insurance policies
- May have higher claim frequency

=== LINES OF BUSINESS ===

AUTO:
- Automobile insurance policies
- Tables: auto_insurance.policy_auto, auto_insurance.claim_auto
- Key metrics: loss ratio by state, severity by vehicle type

HOME:
- Homeowners insurance policies
- Tables: property_insurance.policy_property, property_insurance.claim_property
- Key metrics: loss ratio by construction type, severity by property type

SMALL_COMMERCIAL:
- Small commercial property insurance
- Tables: property_insurance.policy_property
- Key metrics: loss ratio by business type

=== UNDERWRITING TIERS ===

PREFERRED:
- Lowest risk tier
- Best rates
- Expected lower loss ratios

STANDARD:
- Standard risk tier
- Moderate rates
- Average loss ratios

NON_STANDARD:
- Higher risk tier
- Higher rates
- Expected higher loss ratios

=== POLICY STATUSES ===

ACTIVE:
- Currently active policy
- Premiums being collected
- Claims can be filed

EXPIRED:
- Policy has expired
- No longer providing coverage
- Historical data only

CANCELLED:
- Policy was cancelled
- May have been mid-term cancellation
- Check cancellation reasons

=== CLAIM STATUSES ===

OPEN:
- Claim is still being processed
- May have reserves set
- Awaiting resolution

CLOSED:
- Claim has been resolved
- Final amounts paid
- No further activity expected

PENDING:
- Claim is pending review
- Initial investigation phase
- May move to OPEN or CLOSED

=== KEY TABLES AND RELATIONSHIPS ===

core.party:
- Customer/party information
- Primary key: party_id
- Links to policies via policyholder_id

core.agent:
- Insurance agent information
- Primary key: agent_id
- Links to policies via agent_id

auto_insurance.policy_auto:
- Auto insurance policies
- Links to: core.party (policyholder_id), core.agent (agent_id)
- Key columns: written_premium, earned_premium_to_date, line_of_business

auto_insurance.claim_auto:
- Auto insurance claims
- Links to: auto_insurance.policy_auto (policy_id)
- Key columns: total_incurred_amount, loss_date, claim_status

auto_insurance.premium_transaction_auto:
- Premium payment transactions
- Links to: auto_insurance.policy_auto (policy_id)
- Key columns: amount, transaction_date, transaction_type
- Transaction types: BILL (positive), PAYMENT (positive), REFUND (negative)

property_insurance.policy_property:
- Property insurance policies
- Links to: core.party (policyholder_id), core.agent (agent_id)
- Key columns: written_premium, earned_premium_to_date, line_of_business

property_insurance.claim_property:
- Property insurance claims
- Links to: property_insurance.policy_property (policy_id)
- Key columns: total_incurred_amount, loss_date, claim_status

property_insurance.premium_transaction_property:
- Premium payment transactions
- Links to: property_insurance.policy_property (policy_id)
- Key columns: amount, transaction_date, transaction_type

analytics.customer_360:
- Pre-aggregated customer view
- Combines auto and property policies
- Includes aggregated claims data
- Key columns: total_written_premium, total_claim_incurred, total_policies

=== COMMON QUERY PATTERNS ===

Loss Ratio Calculations:
- Join policies with claims
- Group by desired dimension (LOB, state, segment)
- Use NULLIF to handle division by zero
- Filter out zero earned premium

Premium Collection:
- Use premium_transaction tables
- Filter by transaction_type (BILL, PAYMENT)
- Sum amounts for collection totals
- Filter by date ranges for time periods

Date Filtering:
- Last quarter: DATE_TRUNC('quarter', CURRENT_DATE) - INTERVAL '3 months' to DATE_TRUNC('quarter', CURRENT_DATE)
- Last 24 months: CURRENT_DATE - INTERVAL '24 months' to CURRENT_DATE
- Last 3 years: CURRENT_DATE - INTERVAL '3 years' to CURRENT_DATE

Aggregations:
- Use SUM for totals (premium, claims)
- Use AVG for averages (severity, risk score)
- Use COUNT for counts (policies, claims)
- Use COALESCE to handle NULL values

=== BUSINESS RULES ===

Premium Collection:
- BILL transactions are positive amounts (premiums billed)
- PAYMENT transactions are positive amounts (payments received)
- REFUND transactions are negative amounts (refunds issued)
- Total collected = SUM of BILL and PAYMENT transactions

Claim Incurred:
- total_incurred_amount includes paid + reserves
- Use total_incurred_amount for loss ratio calculations
- Check claim_status to filter active vs closed claims

Customer Tenure:
- Calculate from policy effective_date
- Compare earliest policy date to current date
- Group customers by tenure buckets (new, 1-3 years, 3-5 years, 5+ years)
"""
    vanna_service.train_on_documentation(domain_docs)
    print("  ✅ Trained on comprehensive domain documentation")
    
    # ============================================================================
    # STEP 3: Train on Question-SQL Pairs (Diverse Examples)
    # ============================================================================
    print("\n💡 STEP 3: Training on diverse question-SQL pairs...")
    
    # Group examples by pattern type for better coverage
    example_questions = [
        # ===== BASIC AGGREGATIONS =====
        (
            "What is the total premium collected in the last quarter?",
            """
            -- Total premium collected in the last quarter (previous 3 months)
            -- Combines auto and property premium transactions
            -- Uses DATE_TRUNC for quarter boundaries and INTERVAL '3 months' for PostgreSQL
            SELECT 
                SUM(amount) AS total_premium_collected
            FROM (
                SELECT amount, transaction_date
                FROM auto_insurance.premium_transaction_auto
                WHERE transaction_date >= DATE_TRUNC('quarter', CURRENT_DATE) - INTERVAL '3 months'
                  AND transaction_date < DATE_TRUNC('quarter', CURRENT_DATE)
                  AND transaction_type IN ('BILL', 'PAYMENT')
                UNION ALL
                SELECT amount, transaction_date
                FROM property_insurance.premium_transaction_property
                WHERE transaction_date >= DATE_TRUNC('quarter', CURRENT_DATE) - INTERVAL '3 months'
                  AND transaction_date < DATE_TRUNC('quarter', CURRENT_DATE)
                  AND transaction_type IN ('BILL', 'PAYMENT')
            ) combined_transactions
            """
        ),
        
        # ===== LOSS RATIO CALCULATIONS =====
        (
            "What is the loss ratio by line of business?",
            """
            -- Loss ratio = total incurred claims / earned premium
            -- Query combines auto and property policies with their claims
            -- Uses NULLIF to handle division by zero
            SELECT 
                p.line_of_business,
                COALESCE(SUM(c.total_incurred_amount), 0) / NULLIF(SUM(p.earned_premium_to_date), 0) AS loss_ratio
            FROM auto_insurance.policy_auto p
            LEFT JOIN auto_insurance.claim_auto c ON p.policy_id = c.policy_id
            WHERE p.earned_premium_to_date > 0
            GROUP BY p.line_of_business
            
            UNION ALL
            
            SELECT 
                p.line_of_business,
                COALESCE(SUM(c.total_incurred_amount), 0) / NULLIF(SUM(p.earned_premium_to_date), 0) AS loss_ratio
            FROM property_insurance.policy_property p
            LEFT JOIN property_insurance.claim_property c ON p.policy_id = c.policy_id
            WHERE p.earned_premium_to_date > 0
            GROUP BY p.line_of_business
            """
        ),
        
        (
            "Show me customer segment profitability",
            """
            -- Customer segment profitability using customer_360 view
            -- Shows written premium, total incurred claims, and loss ratio by segment
            SELECT 
                customer_segment,
                SUM(total_written_premium) AS total_written_premium,
                SUM(total_claim_incurred) AS total_incurred,
                SUM(total_claim_incurred) / NULLIF(SUM(total_written_premium), 0) AS loss_ratio
            FROM analytics.customer_360
            WHERE customer_segment IS NOT NULL
            GROUP BY customer_segment
            ORDER BY loss_ratio DESC
            """
        ),
        
        # ===== AVERAGE SEVERITY =====
        (
            "What is the average claim severity by state?",
            """
            -- Average claim severity = average total_incurred_amount per claim
            -- Joins claims to policies to get state information
            -- Combines auto and property claims
            SELECT 
                p.ph_state,
                AVG(c.total_incurred_amount) AS avg_severity,
                COUNT(*) AS claim_count
            FROM auto_insurance.claim_auto c
            JOIN auto_insurance.policy_auto p ON c.policy_id = p.policy_id
            WHERE c.total_incurred_amount > 0 AND p.ph_state IS NOT NULL
            GROUP BY p.ph_state
            
            UNION ALL
            
            SELECT 
                p.ph_state,
                AVG(c.total_incurred_amount) AS avg_severity,
                COUNT(*) AS claim_count
            FROM property_insurance.claim_property c
            JOIN property_insurance.policy_property p ON c.policy_id = p.policy_id
            WHERE c.total_incurred_amount > 0 AND p.ph_state IS NOT NULL
            GROUP BY p.ph_state
            
            ORDER BY avg_severity DESC
            """
        ),
        
        # ===== AGENT PERFORMANCE =====
        (
            "Which agents have the highest written premium?",
            """
            -- Combines written premium from both auto and property policies
            -- Shows top agents by total premium across all lines of business
            SELECT 
                a.agent_id,
                a.agent_name,
                COALESCE(SUM(pa.written_premium), 0) + COALESCE(SUM(pp.written_premium), 0) AS total_written_premium,
                COUNT(DISTINCT pa.policy_id) + COUNT(DISTINCT pp.policy_id) AS policy_count
            FROM core.agent a
            LEFT JOIN auto_insurance.policy_auto pa ON a.agent_id = pa.agent_id
            LEFT JOIN property_insurance.policy_property pp ON a.agent_id = pp.agent_id
            GROUP BY a.agent_id, a.agent_name
            HAVING COALESCE(SUM(pa.written_premium), 0) + COALESCE(SUM(pp.written_premium), 0) > 0
            ORDER BY total_written_premium DESC
            LIMIT 10
            """
        ),
        
        # ===== UNDERWRITING TIER ANALYSIS =====
        (
            "What is the loss ratio by underwriting tier?",
            """
            -- Loss ratio by underwriting tier for auto policies
            -- Shows performance across risk tiers
            SELECT 
                p.underwriting_tier,
                COUNT(DISTINCT p.policy_id) AS policy_count,
                SUM(p.earned_premium_to_date) AS total_earned_premium,
                COALESCE(SUM(c.total_incurred_amount), 0) AS total_incurred,
                COALESCE(SUM(c.total_incurred_amount), 0) / NULLIF(SUM(p.earned_premium_to_date), 0) AS loss_ratio
            FROM auto_insurance.policy_auto p
            LEFT JOIN auto_insurance.claim_auto c ON p.policy_id = c.policy_id
            WHERE p.underwriting_tier IS NOT NULL AND p.earned_premium_to_date > 0
            GROUP BY p.underwriting_tier
            ORDER BY loss_ratio DESC
            """
        ),
        
        # ===== DATE RANGE QUERIES =====
        (
            "What is the total written premium for the last 24 months?",
            """
            -- Total written premium over last 24 months
            -- Combines auto and property policies
            SELECT 
                SUM(written_premium) AS total_written_premium,
                COUNT(*) AS policy_count
            FROM (
                SELECT written_premium, effective_date
                FROM auto_insurance.policy_auto
                WHERE effective_date >= CURRENT_DATE - INTERVAL '24 months'
                UNION ALL
                SELECT written_premium, effective_date
                FROM property_insurance.policy_property
                WHERE effective_date >= CURRENT_DATE - INTERVAL '24 months'
            ) all_policies
            """
        ),
        
        # ===== CLAIM FREQUENCY =====
        (
            "What is the claim frequency by line of business?",
            """
            -- Claim frequency = number of claims / number of policies
            -- Expressed per 1,000 policies
            SELECT 
                'AUTO' AS line_of_business,
                COUNT(DISTINCT c.claim_id) AS claim_count,
                COUNT(DISTINCT p.policy_id) AS policy_count,
                (COUNT(DISTINCT c.claim_id)::NUMERIC / NULLIF(COUNT(DISTINCT p.policy_id), 0)) * 1000 AS claim_frequency_per_1000
            FROM auto_insurance.policy_auto p
            LEFT JOIN auto_insurance.claim_auto c ON p.policy_id = c.policy_id
            
            UNION ALL
            
            SELECT 
                'PROPERTY' AS line_of_business,
                COUNT(DISTINCT c.claim_id) AS claim_count,
                COUNT(DISTINCT p.policy_id) AS policy_count,
                (COUNT(DISTINCT c.claim_id)::NUMERIC / NULLIF(COUNT(DISTINCT p.policy_id), 0)) * 1000 AS claim_frequency_per_1000
            FROM property_insurance.policy_property p
            LEFT JOIN property_insurance.claim_property c ON p.policy_id = c.policy_id
            """
        ),
        
        # ===== STATE ANALYSIS =====
        (
            "What is the loss ratio by state?",
            """
            -- Loss ratio by state for auto policies
            -- Shows geographic performance
            SELECT 
                p.ph_state,
                COUNT(DISTINCT p.policy_id) AS policy_count,
                SUM(p.earned_premium_to_date) AS total_earned_premium,
                COALESCE(SUM(c.total_incurred_amount), 0) AS total_incurred,
                COALESCE(SUM(c.total_incurred_amount), 0) / NULLIF(SUM(p.earned_premium_to_date), 0) AS loss_ratio
            FROM auto_insurance.policy_auto p
            LEFT JOIN auto_insurance.claim_auto c ON p.policy_id = c.policy_id
            WHERE p.ph_state IS NOT NULL AND p.earned_premium_to_date > 0
            GROUP BY p.ph_state
            HAVING COUNT(DISTINCT p.policy_id) >= 10
            ORDER BY loss_ratio DESC
            """
        ),
        
        # ===== CUSTOMER 360 VIEW USAGE =====
        (
            "How many customers have both auto and property policies?",
            """
            -- Uses customer_360 view to find multi-policy customers
            -- multi_policy_flag indicates customers with 2+ policies
            SELECT 
                COUNT(*) AS multi_policy_customers,
                SUM(total_written_premium) AS total_premium_from_multi_policy
            FROM analytics.customer_360
            WHERE multi_policy_flag = TRUE
            """
        ),
        
        # ===== OPEN CLAIMS ANALYSIS =====
        (
            "How many open claims do we have by line of business?",
            """
            -- Count of open claims by line of business
            -- Combines auto and property claims
            SELECT 
                'AUTO' AS line_of_business,
                COUNT(*) AS open_claim_count,
                SUM(total_incurred_amount) AS total_incurred_on_open_claims
            FROM auto_insurance.claim_auto
            WHERE claim_status = 'OPEN'
            
            UNION ALL
            
            SELECT 
                'PROPERTY' AS line_of_business,
                COUNT(*) AS open_claim_count,
                SUM(total_incurred_amount) AS total_incurred_on_open_claims
            FROM property_insurance.claim_property
            WHERE claim_status = 'OPEN'
            """
        ),
        
        # ===== TIME-BASED ANALYSIS =====
        (
            "What is the average time to close claims?",
            """
            -- Average time from report_date to close_date for closed claims
            -- Only includes claims that have been closed
            SELECT 
                'AUTO' AS line_of_business,
                AVG(close_date - report_date) AS avg_days_to_close,
                COUNT(*) AS closed_claim_count
            FROM auto_insurance.claim_auto
            WHERE claim_status = 'CLOSED' AND close_date IS NOT NULL
            
            UNION ALL
            
            SELECT 
                'PROPERTY' AS line_of_business,
                AVG(close_date - report_date) AS avg_days_to_close,
                COUNT(*) AS closed_claim_count
            FROM property_insurance.claim_property
            WHERE claim_status = 'CLOSED' AND close_date IS NOT NULL
            """
        ),
    ]
    
    trained_count = 0
    failed_count = 0
    for question, sql in example_questions:
        try:
            vanna_service.train_on_question_sql(question, sql)
            print(f"  ✅ Trained on: {question[:60]}...")
            trained_count += 1
        except Exception as e:
            print(f"  ⚠️  Failed to train on question: {e}")
            failed_count += 1
    
    print(f"\n📊 Training Summary:")
    print(f"  ✅ Successfully trained: {trained_count} question-SQL pairs")
    if failed_count > 0:
        print(f"  ⚠️  Failed: {failed_count} question-SQL pairs")
    
    print("\n🎉 Vanna training completed!")
    print("📊 Ready to generate SQL from natural language questions")
    print("\n💡 Best Practices Applied:")
    print("   - Comprehensive DDL coverage (all schema files)")
    print("   - Rich domain documentation (business context, metrics, rules)")
    print("   - Diverse question-SQL pairs (12 examples covering multiple patterns)")
    print("   - High-quality SQL (well-commented, correct syntax, handles edge cases)")


if __name__ == "__main__":
    main()
