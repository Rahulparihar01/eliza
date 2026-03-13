#!/usr/bin/env python3
"""
Comprehensive Vanna AI Training Script
Loads all training data including DDL, domain docs, and question-SQL pairs
"""
import sys
import os
import re
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.services.vanna_service import VannaService
from src.core.config import get_settings

def extract_questions_from_markdown(md_file_path):
    """
    Extracts question-SQL pairs from the training markdown file.
    Returns list of (question, sql) tuples.
    """
    with open(md_file_path, 'r') as f:
        content = f.read()
    
    # Pattern to match questions and their SQL code blocks
    # Questions start with ### Q followed by number, then SQL in triple backticks
    pattern = r'### Q\d+: (.+?)\n\n```sql\n(.+?)\n```'
    matches = re.findall(pattern, content, re.DOTALL)
    
    questions = []
    for question_text, sql in matches:
        # Clean up the question text
        question = question_text.strip()
        # Clean up SQL (remove excessive blank lines but keep structure)
        sql = re.sub(r'\n{3,}', '\n\n', sql.strip())
        questions.append((question, sql))
    
    return questions

def main():
    """Train Vanna on complete insurance database knowledge."""
    settings = get_settings()
    
    print("🚀 Initializing Vanna service...")
    vanna_service = VannaService(
        database_url=settings.insurance_demo_db_url,
        model="gpt-4o-mini"
    )
    
    # ============================================================================
    # STEP 1: Train on DDL (Database Schema)
    # ============================================================================
    print("\n📋 STEP 1: Training on DDL schemas...")
    ddl_dir = Path(__file__).parent.parent / "design_docs" / "analytics_insurance" / "insurance_demo_ddl"
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
    # STEP 2: Train on Domain Documentation
    # ============================================================================
    print("\n📚 STEP 2: Training on domain documentation...")
    domain_docs = """
Insurance Analytics Domain Knowledge and Business Context

=== KEY METRICS AND CALCULATIONS ===

Loss Ratio:
- Formula: total incurred claims / earned premium
- Interpretation: < 60% is good, > 80% is concerning
- Calculation requires joining policies with claims
- Always use NULLIF to prevent division by zero

Claim Frequency:
- Formula: number of claims / number of policies
- Typically expressed per 1,000 policies
- Multiply by 1000 for per-1000 rate
- Higher frequency indicates higher risk

Average Severity:
- Formula: total incurred amount / number of claims
- Measures average cost per claim
- Higher severity indicates more expensive claims
- Use AVG(total_incurred_amount) on claim tables

=== SCHEMAS AND TABLES ===

Core Schema (core):
- core.party: Customer/party information (party_id is primary key)
- core.agent: Insurance agent information (agent_id is primary key)

Auto Insurance Schema (auto_insurance):
- auto_insurance.policy_auto: Auto policies
- auto_insurance.claim_auto: Auto claims
- auto_insurance.auto_exposure: Vehicle details
- auto_insurance.claim_transaction_auto: Claim payments/reserves
- auto_insurance.premium_transaction_auto: Premium billing/payments

Property Insurance Schema (property_insurance):
- property_insurance.policy_property: Property policies (HOME, SMALL_COMMERCIAL)
- property_insurance.claim_property: Property claims
- property_insurance.property_exposure: Property details
- property_insurance.claim_transaction_property: Claim payments/reserves
- property_insurance.premium_transaction_property: Premium billing/payments

Analytics Schema (analytics):
- analytics.customer_360: Pre-aggregated customer view combining auto and property

=== KEY RELATIONSHIPS ===

Policies to Parties:
- auto_insurance.policy_auto.policyholder_id → core.party.party_id
- property_insurance.policy_property.policyholder_id → core.party.party_id

Policies to Agents:
- auto_insurance.policy_auto.agent_id → core.agent.agent_id
- property_insurance.policy_property.agent_id → core.agent.agent_id

Claims to Policies:
- auto_insurance.claim_auto.policy_id → auto_insurance.policy_auto.policy_id
- property_insurance.claim_property.policy_id → property_insurance.policy_property.policy_id

=== CUSTOMER SEGMENTS ===

HNW (High Net Worth): Premium customers, higher policy values, lower loss ratios expected
Personal Standard: Standard personal insurance, mainstream market, moderate risk
SMB (Small Medium Business): Commercial insurance, may have higher claim frequency

=== LINES OF BUSINESS ===

AUTO: Automobile insurance (in auto_insurance schema)
HOME: Homeowners insurance (in property_insurance schema)
SMALL_COMMERCIAL: Small commercial property (in property_insurance schema)

=== UNDERWRITING TIERS ===

PREFERRED: Lowest risk, best rates, expected lower loss ratios
STANDARD: Standard risk, moderate rates, average loss ratios
NON_STANDARD: Higher risk, higher rates, expected higher loss ratios

=== POLICY STATUSES ===

ACTIVE: Currently active, premiums being collected, claims can be filed
EXPIRED: Policy has expired, no longer providing coverage
CANCELLED: Policy was cancelled, may have been mid-term cancellation

=== CLAIM STATUSES ===

OPEN: Claim is being processed, may have reserves set
CLOSED: Claim has been resolved, final amounts paid
PENDING: Claim is pending review, initial investigation phase

=== COMMON QUERY PATTERNS ===

Combining Auto and Property Data:
- Use UNION ALL to combine results from auto_insurance and property_insurance tables
- Maintain separate queries for each schema, then combine
- Example: SELECT ... FROM auto_insurance.policy_auto UNION ALL SELECT ... FROM property_insurance.policy_property

Loss Ratio Calculations:
- Join policies with claims on policy_id
- Group by desired dimension (line_of_business, ph_state, customer_segment)
- Use COALESCE(SUM(total_incurred_amount), 0) to handle policies with no claims
- Use NULLIF(SUM(earned_premium_to_date), 0) to prevent division by zero
- Filter WHERE earned_premium_to_date > 0

Date Filtering:
- Last quarter: DATE_TRUNC('quarter', CURRENT_DATE) - INTERVAL '3 months' to DATE_TRUNC('quarter', CURRENT_DATE)
- Last 24 months: CURRENT_DATE - INTERVAL '24 months'
- Last 3 years: CURRENT_DATE - INTERVAL '3 years'
- Use >= for date comparisons

Premium Collection:
- Use premium_transaction_auto or premium_transaction_property tables
- Filter by transaction_type: 'BILL', 'PAYMENT' (positive), 'REFUND' (negative)
- Sum amounts for totals

Claim Incurred:
- total_incurred_amount = paid_loss_amount + paid_expense_amount + case_reserve_amount - recoveries_amount
- Always use total_incurred_amount for loss ratio calculations
- Check claim_status to filter active vs closed claims

=== IMPORTANT SQL CONVENTIONS ===

Schema Qualification:
- Always qualify table names with schema: auto_insurance.policy_auto (not just policy_auto)
- Always qualify table names with schema: property_insurance.policy_property (not just policy_property)
- Always qualify table names with schema: core.party, core.agent
- Always qualify table names with schema: analytics.customer_360

Column Names:
- State: Use ph_state (not just state)
- Postal Code: Use ph_postal_code (not zip_code)
- Customer Segment: Use ph_customer_segment (in policy tables) or customer_segment (in customer_360)
- Policy ID: policy_id
- Claim ID: claim_id
- Party ID: party_id
- Agent ID: agent_id

Aggregations:
- Use SUM() for totals (premium, claims)
- Use AVG() for averages (severity, risk score)
- Use COUNT() for counts (policies, claims)
- Use COALESCE() to handle NULL values
- Cast to NUMERIC when dividing integers: COUNT(*)::NUMERIC

Statistical Thresholds:
- Use HAVING COUNT(DISTINCT policy_id) >= 10 for policy-level analysis
- Use HAVING COUNT(DISTINCT claim_id) >= 5 for claim-level analysis
- Filters out statistically insignificant segments
"""
    vanna_service.train_on_documentation(domain_docs)
    print("  ✅ Trained on comprehensive domain documentation")
    
    # ============================================================================
    # STEP 3: Train on Question-SQL Pairs from Markdown
    # ============================================================================
    print("\n💡 STEP 3: Training on comprehensive question-SQL pairs...")
    
    training_md_path = Path(__file__).parent.parent / "design_docs" / "analytics_insurance" / "vanna_training_questions_and_sql.md"
    
    if not training_md_path.exists():
        print(f"  ⚠️  Training markdown file not found: {training_md_path}")
        print("  📝 Using fallback basic examples...")
        example_questions = [
            (
                "How many auto insurance policies do we have?",
                "SELECT COUNT(*) AS total_auto_policies FROM auto_insurance.policy_auto;"
            ),
            (
                "What is the total written premium for all policies?",
                """
                SELECT 
                    SUM(written_premium) AS total_written_premium
                FROM (
                    SELECT written_premium FROM auto_insurance.policy_auto
                    UNION ALL
                    SELECT written_premium FROM property_insurance.policy_property
                ) all_policies;
                """
            )
        ]
    else:
        print(f"  📖 Loading questions from: {training_md_path.name}")
        example_questions = extract_questions_from_markdown(training_md_path)
        print(f"  📊 Found {len(example_questions)} question-SQL pairs")
    
    trained_count = 0
    failed_count = 0
    
    for i, (question, sql) in enumerate(example_questions, 1):
        try:
            vanna_service.train_on_question_sql(question, sql)
            print(f"  ✅ [{i}/{len(example_questions)}] {question[:80]}...")
            trained_count += 1
        except Exception as e:
            print(f"  ⚠️  [{i}/{len(example_questions)}] Failed: {str(e)[:100]}")
            failed_count += 1
    
    # ============================================================================
    # SUMMARY
    # ============================================================================
    print("\n" + "="*80)
    print("🎉 Vanna Training Completed!")
    print("="*80)
    print(f"📋 DDL Files: {len(ddl_statements)}")
    print(f"📚 Domain Documentation: ✅")
    print(f"💡 Question-SQL Pairs: {trained_count} trained, {failed_count} failed")
    print("\n✨ Vanna is now ready to generate SQL from natural language questions!")
    print("="*80)

if __name__ == "__main__":
    main()

