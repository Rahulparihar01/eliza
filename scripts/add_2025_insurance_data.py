#!/usr/bin/env python3
"""
Add 2025 Insurance Data Script

Adds new policies, claims, and transactions for 2025 to the existing insurance_demo_db.
Preserves all existing data and uses existing parties/agents.
"""

import sys
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
import random
from typing import List, Dict, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.core.config import get_settings

# Use Faker for realistic data generation
try:
    from faker import Faker
    fake = Faker()
    Faker.seed(2025)  # Different seed for variety
except ImportError:
    print("⚠️  Faker not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "faker"])
    from faker import Faker
    fake = Faker()
    Faker.seed(2025)

# Import generation functions from the main seed script
# We'll reuse the helper functions
from seed_insurance_demo_data import (
    US_STATES, VEHICLE_MAKES, VEHICLE_MODELS_BY_MAKE, PROPERTY_TYPES,
    CONSTRUCTION_TYPES, AUTO_CLAIM_TYPES, PROPERTY_CLAIM_TYPES, CAUSES_OF_LOSS,
    CLAIM_STATUSES, CLAIM_STATUS_WEIGHTS, UNDERWRITING_TIERS, TIER_WEIGHTS,
    POLICY_STATUSES, STATUS_WEIGHTS, AUTO_LOB, PROPERTY_LOB_HOME, PROPERTY_LOB_COMMERCIAL,
    random_date, random_weighted_choice, calculate_earned_premium, 
    generate_risk_score, generate_premium
)

# Configuration for 2025 data
POLICY_RATE_2025 = 0.15  # Generate policies for 15% of existing customers
CLAIM_RATE_AUTO = 0.15
CLAIM_RATE_PROPERTY = 0.12

# Date range for 2025 policies
START_DATE_2025 = date(2025, 1, 1)
END_DATE_2025 = date(2025, 11, 30)

def get_max_id(engine, schema: str, table: str, id_column: str) -> int:
    """Get the maximum ID from a table"""
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COALESCE(MAX({id_column}), 0) FROM {schema}.{table}"))
        max_id = result.scalar()
    return max_id

def load_existing_parties(engine) -> List[Dict]:
    """Load existing parties from database"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT party_id, party_type, full_name, first_name, last_name, 
                   date_of_birth, primary_email, primary_phone, street_address,
                   city, state, postal_code, customer_segment, tenure_start_date
            FROM core.party
        """))
        parties = []
        for row in result:
            parties.append({
                "party_id": row[0],
                "party_type": row[1],
                "full_name": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "date_of_birth": row[5],
                "primary_email": row[6],
                "primary_phone": row[7],
                "street_address": row[8],
                "city": row[9],
                "state": row[10],
                "postal_code": row[11],
                "customer_segment": row[12],
                "tenure_start_date": row[13]
            })
    return parties

def load_existing_agents(engine) -> List[Dict]:
    """Load existing agents from database"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT agent_id, agent_code, agent_name, agent_type, region, 
                   active_flag, primary_email, primary_phone
            FROM core.agent
        """))
        agents = []
        for row in result:
            agents.append({
                "agent_id": row[0],
                "agent_code": row[1],
                "agent_name": row[2],
                "agent_type": row[3],
                "region": row[4],
                "active_flag": row[5],
                "primary_email": row[6],
                "primary_phone": row[7]
            })
    return agents

def generate_2025_auto_policies(parties: List[Dict], agents: List[Dict], 
                                policy_rate: float, start_policy_id: int) -> List[Dict]:
    """Generate 2025 auto insurance policies"""
    policies = []
    num_policies = int(len(parties) * policy_rate)
    selected_parties = random.sample(parties, num_policies)
    
    policy_id = start_policy_id
    
    for party in selected_parties:
        # Policy dates - only in 2025
        effective_date = random_date(START_DATE_2025, END_DATE_2025)
        expiration_date = effective_date + timedelta(days=365)
        
        # Policy details
        tier = random_weighted_choice(UNDERWRITING_TIERS, TIER_WEIGHTS)
        risk_score = generate_risk_score(tier)
        status = random_weighted_choice(POLICY_STATUSES, STATUS_WEIGHTS)
        
        # Premium
        written_premium = generate_premium(AUTO_LOB, tier, party["state"])
        earned_premium = calculate_earned_premium(
            written_premium, effective_date, expiration_date
        )
        
        # Prior claims (0-3)
        prior_claims = random.randint(0, 3) if random.random() < 0.3 else 0
        
        # Random agent
        agent = random.choice(agents)
        
        policy = {
            "policy_id": policy_id,
            "policy_number": f"AUTO-{policy_id:06d}",
            "policyholder_id": party["party_id"],
            "agent_id": agent["agent_id"],
            "line_of_business": AUTO_LOB,
            "product_code": f"AUTO-{tier[:3]}",
            "policy_status": status,
            "effective_date": effective_date,
            "expiration_date": expiration_date,
            "billing_plan": random.choice(["ANNUAL", "SEMI_ANNUAL", "QUARTERLY"]),
            "written_premium": written_premium,
            "earned_premium_to_date": earned_premium,
            "ph_state": party["state"],
            "ph_postal_code": party["postal_code"],
            "ph_customer_segment": party["customer_segment"],
            "underwriting_tier": tier,
            "risk_score": risk_score,
            "prior_claims_count": prior_claims,
            "uw_company_code": "UW001",
            "created_at": effective_date,
            "updated_at": effective_date
        }
        policies.append(policy)
        policy_id += 1
    
    return policies

def generate_2025_property_policies(parties: List[Dict], agents: List[Dict],
                                    policy_rate: float, start_policy_id: int) -> List[Dict]:
    """Generate 2025 property insurance policies"""
    policies = []
    num_policies = int(len(parties) * policy_rate)
    selected_parties = random.sample(parties, num_policies)
    
    policy_id = start_policy_id
    
    for party in selected_parties:
        # Policy dates - only in 2025
        effective_date = random_date(START_DATE_2025, END_DATE_2025)
        expiration_date = effective_date + timedelta(days=365)
        
        # LOB (mostly HOME, some commercial)
        lob = random_weighted_choice(
            [PROPERTY_LOB_HOME, PROPERTY_LOB_COMMERCIAL],
            [0.85, 0.15]
        )
        
        # Policy details
        tier = random_weighted_choice(UNDERWRITING_TIERS, TIER_WEIGHTS)
        risk_score = generate_risk_score(tier)
        status = random_weighted_choice(POLICY_STATUSES, STATUS_WEIGHTS)
        
        # Premium
        written_premium = generate_premium(lob, tier, party["state"])
        earned_premium = calculate_earned_premium(
            written_premium, effective_date, expiration_date
        )
        
        # Prior claims
        prior_claims = random.randint(0, 2) if random.random() < 0.2 else 0
        
        # Random agent
        agent = random.choice(agents)
        
        policy = {
            "policy_id": policy_id,
            "policy_number": f"PROP-{policy_id:06d}",
            "policyholder_id": party["party_id"],
            "agent_id": agent["agent_id"],
            "line_of_business": lob,
            "product_code": f"{lob}-{tier[:3]}",
            "policy_status": status,
            "effective_date": effective_date,
            "expiration_date": expiration_date,
            "billing_plan": random.choice(["ANNUAL", "SEMI_ANNUAL"]),
            "written_premium": written_premium,
            "earned_premium_to_date": earned_premium,
            "ph_state": party["state"],
            "ph_postal_code": party["postal_code"],
            "ph_customer_segment": party["customer_segment"],
            "underwriting_tier": tier,
            "risk_score": risk_score,
            "prior_claims_count": prior_claims,
            "uw_company_code": "UW001",
            "created_at": effective_date,
            "updated_at": effective_date
        }
        policies.append(policy)
        policy_id += 1
    
    return policies

def generate_auto_exposures(policies: List[Dict], start_exposure_id: int) -> List[Dict]:
    """Generate auto exposures (vehicles)"""
    exposures = []
    exposure_id = start_exposure_id
    
    for policy in policies:
        # Most policies have 1-2 vehicles
        num_vehicles = random.choices([1, 2], weights=[0.7, 0.3])[0]
        
        for _ in range(num_vehicles):
            make = random.choice(VEHICLE_MAKES)
            model = random.choice(VEHICLE_MODELS_BY_MAKE.get(make, ["Unknown"]))
            model_year = random.randint(2020, 2025)
            
            exposure = {
                "exposure_id": exposure_id,
                "policy_id": policy["policy_id"],
                "exposure_type": "VEHICLE",
                "vehicle_make": make,
                "vehicle_model": model,
                "model_year": model_year,
                "vehicle_use": random.choice(["PERSONAL", "COMMUTE", "BUSINESS"]),
                "limit_per_occurrence": Decimal(random.randint(25000, 100000)),
                "deductible_amount": Decimal(random.choice([500, 1000, 2500])),
                "territory_code": f"{policy['ph_state']}-{random.randint(1, 10)}",
                "insured_value": Decimal(random.randint(15000, 60000))
            }
            exposures.append(exposure)
            exposure_id += 1
    
    return exposures

def generate_property_exposures(policies: List[Dict], start_exposure_id: int) -> List[Dict]:
    """Generate property exposures"""
    exposures = []
    exposure_id = start_exposure_id
    
    for policy in policies:
        property_type = random.choice(PROPERTY_TYPES)
        construction = random.choice(CONSTRUCTION_TYPES)
        year_built = random.randint(1950, 2024)
        stories = random.choice([1, 2, 3])
        square_footage = random.randint(1200, 5000)
        
        exposure = {
            "exposure_id": exposure_id,
            "policy_id": policy["policy_id"],
            "exposure_type": "PROPERTY",
            "property_type": property_type,
            "construction_type": construction,
            "year_built": year_built,
            "stories": stories,
            "square_footage": square_footage,
            "limit_per_occurrence": Decimal(random.randint(200000, 1000000)),
            "deductible_amount": Decimal(random.choice([1000, 2500, 5000])),
            "territory_code": f"{policy['ph_state']}-{random.randint(1, 10)}",
            "insured_value": Decimal(random.randint(250000, 800000))
        }
        exposures.append(exposure)
        exposure_id += 1
    
    return exposures

def generate_auto_claims(policies: List[Dict], exposures: List[Dict],
                        claim_rate: float, start_claim_id: int) -> List[Dict]:
    """Generate auto insurance claims for 2025"""
    claims = []
    num_claims = int(len(policies) * claim_rate)
    selected_policies = random.sample(policies, min(num_claims, len(policies)))
    
    claim_id = start_claim_id
    
    # Create exposure lookup by policy
    exposure_by_policy = {}
    for exp in exposures:
        if exp["policy_id"] not in exposure_by_policy:
            exposure_by_policy[exp["policy_id"]] = []
        exposure_by_policy[exp["policy_id"]].append(exp)
    
    for policy in selected_policies:
        # Claim dates - only in 2025
        loss_date = random_date(START_DATE_2025, date.today())
        report_date = loss_date + timedelta(days=random.randint(0, 7))
        
        # Some claims are closed
        if random.random() < 0.5:  # Lower close rate for recent claims
            close_date = report_date + timedelta(days=random.randint(30, 180))
            status = "CLOSED"
        else:
            close_date = None
            status = random.choice(["OPEN", "PENDING"])
        
        # Claim details
        claim_type = random.choice(AUTO_CLAIM_TYPES)
        cause_of_loss = random.choice(CAUSES_OF_LOSS)
        
        # Incurred amounts
        base_amount = Decimal(random.randint(2000, 25000))
        paid_loss = (base_amount * Decimal(str(random.uniform(0.6, 1.0)))).quantize(Decimal('0.01')) if status == "CLOSED" else Decimal('0')
        paid_expense = (base_amount * Decimal(str(random.uniform(0.05, 0.15)))).quantize(Decimal('0.01')) if status == "CLOSED" else Decimal('0')
        case_reserve = base_amount - paid_loss if status != "CLOSED" else Decimal('0')
        recoveries = Decimal(random.randint(0, int(paid_loss * Decimal('0.1')))) if status == "CLOSED" else Decimal('0')
        total_incurred = paid_loss + paid_expense + case_reserve - recoveries
        
        # Litigation flags
        litigation_flag = random.random() < 0.15
        attorney_rep_flag = litigation_flag or random.random() < 0.10
        injury_severity = random.choice(["NONE", "MINOR", "MODERATE", "SEVERE"]) if litigation_flag else "NONE"
        
        # Get exposure if available
        exposure_id = None
        if policy["policy_id"] in exposure_by_policy:
            exposure_id = random.choice(exposure_by_policy[policy["policy_id"]])["exposure_id"]
        
        claim = {
            "claim_id": claim_id,
            "claim_number": f"AUTO-CLM-{claim_id:06d}",
            "policy_id": policy["policy_id"],
            "exposure_id": exposure_id,
            "loss_date": loss_date,
            "report_date": report_date,
            "close_date": close_date,
            "claim_status": status,
            "cause_of_loss": cause_of_loss,
            "claim_type": claim_type,
            "jurisdiction_state": policy["ph_state"],
            "reported_channel": random.choice(["AGENT", "INSURED", "THIRD_PARTY"]),
            "paid_loss_amount": paid_loss,
            "paid_expense_amount": paid_expense,
            "case_reserve_amount": case_reserve,
            "recoveries_amount": recoveries,
            "total_incurred_amount": total_incurred,
            "litigation_flag": litigation_flag,
            "attorney_rep_flag": attorney_rep_flag,
            "injury_severity": injury_severity,
            "created_at": report_date,
            "updated_at": close_date if close_date else report_date
        }
        claims.append(claim)
        claim_id += 1
    
    return claims

def generate_property_claims(policies: List[Dict], exposures: List[Dict],
                            claim_rate: float, start_claim_id: int) -> List[Dict]:
    """Generate property insurance claims for 2025"""
    claims = []
    num_claims = int(len(policies) * claim_rate)
    selected_policies = random.sample(policies, min(num_claims, len(policies)))
    
    claim_id = start_claim_id
    
    # Create exposure lookup
    exposure_by_policy = {}
    for exp in exposures:
        if exp["policy_id"] not in exposure_by_policy:
            exposure_by_policy[exp["policy_id"]] = []
        exposure_by_policy[exp["policy_id"]].append(exp)
    
    for policy in selected_policies:
        loss_date = random_date(START_DATE_2025, date.today())
        report_date = loss_date + timedelta(days=random.randint(0, 3))
        
        if random.random() < 0.6:  # Lower close rate for recent claims
            close_date = report_date + timedelta(days=random.randint(45, 120))
            status = "CLOSED"
        else:
            close_date = None
            status = random.choice(["OPEN", "PENDING"])
        
        claim_type = random.choice(PROPERTY_CLAIM_TYPES)
        cause_of_loss = random.choice(["WEATHER", "WATER_DAMAGE", "WIND_DAMAGE", "FIRE", "THEFT", "VANDALISM"])
        
        base_amount = Decimal(random.randint(5000, 50000))
        paid_loss = (base_amount * Decimal(str(random.uniform(0.7, 1.0)))).quantize(Decimal('0.01')) if status == "CLOSED" else Decimal('0')
        paid_expense = (base_amount * Decimal(str(random.uniform(0.05, 0.12)))).quantize(Decimal('0.01'))
        case_reserve = base_amount - paid_loss if status != "CLOSED" else Decimal('0')
        recoveries = Decimal(random.randint(0, int(paid_loss * Decimal('0.15')))) if status == "CLOSED" else Decimal('0')
        total_incurred = paid_loss + paid_expense + case_reserve - recoveries
        
        litigation_flag = random.random() < 0.05
        attorney_rep_flag = litigation_flag
        
        exposure_id = None
        if policy["policy_id"] in exposure_by_policy:
            exposure_id = random.choice(exposure_by_policy[policy["policy_id"]])["exposure_id"]
        
        claim = {
            "claim_id": claim_id,
            "claim_number": f"PROP-CLM-{claim_id:06d}",
            "policy_id": policy["policy_id"],
            "exposure_id": exposure_id,
            "loss_date": loss_date,
            "report_date": report_date,
            "close_date": close_date,
            "claim_status": status,
            "cause_of_loss": cause_of_loss,
            "claim_type": claim_type,
            "jurisdiction_state": policy["ph_state"],
            "reported_channel": random.choice(["AGENT", "INSURED", "THIRD_PARTY"]),
            "paid_loss_amount": paid_loss,
            "paid_expense_amount": paid_expense,
            "case_reserve_amount": case_reserve,
            "recoveries_amount": recoveries,
            "total_incurred_amount": total_incurred,
            "litigation_flag": litigation_flag,
            "attorney_rep_flag": attorney_rep_flag,
            "injury_severity": "NONE",
            "created_at": report_date,
            "updated_at": close_date if close_date else report_date
        }
        claims.append(claim)
        claim_id += 1
    
    return claims

def generate_premium_transactions(policies: List[Dict], start_tx_id: int) -> List[Dict]:
    """Generate premium transactions for 2025 policies"""
    transactions = []
    tx_id = start_tx_id
    
    for policy in policies:
        effective = policy["effective_date"]
        expiration = policy["expiration_date"]
        
        if policy["billing_plan"] == "ANNUAL":
            transactions.append({
                "premium_transaction_id": tx_id,
                "policy_id": policy["policy_id"],
                "transaction_date": effective,
                "transaction_type": "BILL",
                "amount": policy["written_premium"],
                "currency_code": "USD",
                "payment_method": None,
                "channel": "SYSTEM",
                "status": "POSTED"
            })
            tx_id += 1
            
            if random.random() < 0.95:
                payment_date = effective + timedelta(days=random.randint(0, 30))
                transactions.append({
                    "premium_transaction_id": tx_id,
                    "policy_id": policy["policy_id"],
                    "transaction_date": payment_date,
                    "transaction_type": "PAYMENT",
                    "amount": -policy["written_premium"],
                    "currency_code": "USD",
                    "payment_method": random.choice(["CREDIT_CARD", "ACH", "CHECK", "WIRE"]),
                    "channel": random.choice(["ONLINE", "AGENT", "PHONE"]),
                    "status": "POSTED"
                })
                tx_id += 1
    
    return transactions

def generate_claim_transactions(claims: List[Dict], start_tx_id: int) -> List[Dict]:
    """Generate claim transactions for 2025 claims"""
    transactions = []
    tx_id = start_tx_id
    
    for claim in claims:
        # Loss payments
        if claim["paid_loss_amount"] > 0:
            num_payments = random.choices([1, 2], weights=[0.8, 0.2])[0]
            total_paid = claim["paid_loss_amount"]
            
            for i in range(num_payments):
                payment_date = claim["report_date"] + timedelta(days=random.randint(10 + i*30, 60 + i*30))
                if num_payments == 1:
                    amount = total_paid.quantize(Decimal('0.01'))
                else:
                    amount = (total_paid / Decimal(num_payments)).quantize(Decimal('0.01'))
                
                transactions.append({
                    "claim_transaction_id": tx_id,
                    "claim_id": claim["claim_id"],
                    "transaction_date": payment_date,
                    "transaction_type": "PAYMENT",
                    "component_type": "LOSS",
                    "amount": amount,
                    "currency_code": "USD",
                    "payee_type": random.choice(["INSURED", "THIRD_PARTY", "VENDOR"]),
                    "payee_name": fake.company() if random.random() < 0.3 else fake.name(),
                    "note": f"Payment for {claim['cause_of_loss']}"
                })
                tx_id += 1
        
        # Expense payments
        if claim["paid_expense_amount"] > 0:
            transactions.append({
                "claim_transaction_id": tx_id,
                "claim_id": claim["claim_id"],
                "transaction_date": claim["report_date"] + timedelta(days=random.randint(5, 20)),
                "transaction_type": "PAYMENT",
                "component_type": "EXPENSE",
                "amount": claim["paid_expense_amount"],
                "currency_code": "USD",
                "payee_type": random.choice(["VENDOR", "LAW_FIRM", "ADJUSTER"]),
                "payee_name": fake.company(),
                "note": "Claim handling expense"
            })
            tx_id += 1
        
        # Reserves
        if claim["case_reserve_amount"] > 0:
            transactions.append({
                "claim_transaction_id": tx_id,
                "claim_id": claim["claim_id"],
                "transaction_date": claim["report_date"],
                "transaction_type": "RESERVE",
                "component_type": "RESERVE",
                "amount": claim["case_reserve_amount"],
                "currency_code": "USD",
                "payee_type": None,
                "payee_name": None,
                "note": "Case reserve established"
            })
            tx_id += 1
    
    return transactions

def insert_data(engine, table_name: str, data: List[Dict], schema: str = None):
    """Insert data into database table"""
    if schema:
        full_table = f"{schema}.{table_name}"
    else:
        full_table = table_name
    
    if not data:
        print(f"  ⏭️  No data to insert into {full_table}")
        return
    
    # Build INSERT statement
    columns = list(data[0].keys())
    placeholders = ", ".join([f":{col}" for col in columns])
    columns_str = ", ".join(columns)
    
    sql = f"INSERT INTO {full_table} ({columns_str}) VALUES ({placeholders})"
    
    with engine.connect() as conn:
        conn.execute(text(sql), data)
        conn.commit()
    
    print(f"  ✅ Inserted {len(data)} rows into {full_table}")

def main():
    """Add 2025 data to existing insurance database"""
    settings = get_settings()
    
    # Connect to insurance database
    engine = create_engine(settings.insurance_demo_db_url)
    
    print("🚀 Adding 2025 data to insurance_demo_db...")
    print("")
    
    # Load existing parties and agents
    print("👥 Loading existing parties...")
    parties = load_existing_parties(engine)
    print(f"  ✅ Loaded {len(parties)} existing parties")
    
    print("🏢 Loading existing agents...")
    agents = load_existing_agents(engine)
    print(f"  ✅ Loaded {len(agents)} existing agents")
    
    # Get max IDs for new records
    print("\n🔢 Getting max IDs from existing tables...")
    max_auto_policy_id = get_max_id(engine, "auto_insurance", "policy_auto", "policy_id")
    max_property_policy_id = get_max_id(engine, "property_insurance", "policy_property", "policy_id")
    max_auto_exposure_id = get_max_id(engine, "auto_insurance", "auto_exposure", "exposure_id")
    max_property_exposure_id = get_max_id(engine, "property_insurance", "property_exposure", "exposure_id")
    max_auto_claim_id = get_max_id(engine, "auto_insurance", "claim_auto", "claim_id")
    max_property_claim_id = get_max_id(engine, "property_insurance", "claim_property", "claim_id")
    max_auto_premium_tx_id = get_max_id(engine, "auto_insurance", "premium_transaction_auto", "premium_transaction_id")
    max_property_premium_tx_id = get_max_id(engine, "property_insurance", "premium_transaction_property", "premium_transaction_id")
    max_auto_claim_tx_id = get_max_id(engine, "auto_insurance", "claim_transaction_auto", "claim_transaction_id")
    max_property_claim_tx_id = get_max_id(engine, "property_insurance", "claim_transaction_property", "claim_transaction_id")
    
    print(f"  ✅ Max auto policy ID: {max_auto_policy_id}")
    print(f"  ✅ Max property policy ID: {max_property_policy_id}")
    
    # Generate 2025 data
    print("\n🚗 Generating 2025 auto policies...")
    auto_policies = generate_2025_auto_policies(parties, agents, POLICY_RATE_2025, max_auto_policy_id + 1)
    print(f"  ✅ Generated {len(auto_policies)} new auto policies")
    
    print("🏠 Generating 2025 property policies...")
    property_policies = generate_2025_property_policies(parties, agents, POLICY_RATE_2025, max_property_policy_id + 1)
    print(f"  ✅ Generated {len(property_policies)} new property policies")
    
    print("🚙 Generating auto exposures...")
    auto_exposures = generate_auto_exposures(auto_policies, max_auto_exposure_id + 1)
    print(f"  ✅ Generated {len(auto_exposures)} auto exposures")
    
    print("🏘️  Generating property exposures...")
    property_exposures = generate_property_exposures(property_policies, max_property_exposure_id + 1)
    print(f"  ✅ Generated {len(property_exposures)} property exposures")
    
    print("💥 Generating auto claims...")
    auto_claims = generate_auto_claims(auto_policies, auto_exposures, CLAIM_RATE_AUTO, max_auto_claim_id + 1)
    print(f"  ✅ Generated {len(auto_claims)} auto claims")
    
    print("💥 Generating property claims...")
    property_claims = generate_property_claims(property_policies, property_exposures, CLAIM_RATE_PROPERTY, max_property_claim_id + 1)
    print(f"  ✅ Generated {len(property_claims)} property claims")
    
    print("💰 Generating premium transactions...")
    auto_premium_tx = generate_premium_transactions(auto_policies, max_auto_premium_tx_id + 1)
    property_premium_tx = generate_premium_transactions(property_policies, max_property_premium_tx_id + 1)
    print(f"  ✅ Generated {len(auto_premium_tx)} auto premium transactions")
    print(f"  ✅ Generated {len(property_premium_tx)} property premium transactions")
    
    print("💸 Generating claim transactions...")
    auto_claim_tx = generate_claim_transactions(auto_claims, max_auto_claim_tx_id + 1)
    property_claim_tx = generate_claim_transactions(property_claims, max_property_claim_tx_id + 1)
    print(f"  ✅ Generated {len(auto_claim_tx)} auto claim transactions")
    print(f"  ✅ Generated {len(property_claim_tx)} property claim transactions")
    
    # Insert into database
    print("\n📥 Inserting 2025 data into database...")
    
    try:
        insert_data(engine, "policy_auto", auto_policies, "auto_insurance")
        insert_data(engine, "policy_property", property_policies, "property_insurance")
        insert_data(engine, "auto_exposure", auto_exposures, "auto_insurance")
        insert_data(engine, "property_exposure", property_exposures, "property_insurance")
        insert_data(engine, "claim_auto", auto_claims, "auto_insurance")
        insert_data(engine, "claim_property", property_claims, "property_insurance")
        insert_data(engine, "premium_transaction_auto", auto_premium_tx, "auto_insurance")
        insert_data(engine, "premium_transaction_property", property_premium_tx, "property_insurance")
        insert_data(engine, "claim_transaction_auto", auto_claim_tx, "auto_insurance")
        insert_data(engine, "claim_transaction_property", property_claim_tx, "property_insurance")
        
        print("\n🎉 2025 data addition complete!")
        print(f"\n📊 Summary of NEW data added:")
        print(f"  - New Auto Policies: {len(auto_policies)}")
        print(f"  - New Property Policies: {len(property_policies)}")
        print(f"  - New Auto Claims: {len(auto_claims)}")
        print(f"  - New Property Claims: {len(property_claims)}")
        print(f"  - New Transactions: {len(auto_premium_tx) + len(property_premium_tx) + len(auto_claim_tx) + len(property_claim_tx)}")
        
    except Exception as e:
        print(f"\n❌ Error inserting data: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()

