#!/usr/bin/env python3
"""
Seed Insurance Demo Data Script

Generates realistic seed data for insurance_demo_db:
- ~1000 customers (parties) with real addresses and names
- 50-100 agents across different regions
- Auto and property policies distributed across customers
- Many customers have both auto and property policies
- Claims, exposures, and transactions with proper referential integrity
- Realistic dates, amounts, and relationships
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
    Faker.seed(42)  # For reproducibility
except ImportError:
    print("⚠️  Faker not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "faker"])
    from faker import Faker
    fake = Faker()
    Faker.seed(42)

# ============================================================================
# Configuration
# ============================================================================

NUM_CUSTOMERS = 1000
NUM_AGENTS = 75
AUTO_POLICY_RATE = 0.75  # 75% of customers have auto policies
PROPERTY_POLICY_RATE = 0.60  # 60% of customers have property policies
BOTH_POLICIES_RATE = 0.40  # 40% have both (ensures overlap)

# Customer segments
CUSTOMER_SEGMENTS = ["HNW", "PERSONAL_STANDARD", "SMB"]
SEGMENT_WEIGHTS = [0.15, 0.60, 0.25]  # 15% HNW, 60% standard, 25% SMB

# Lines of business
AUTO_LOB = "AUTO"
PROPERTY_LOB_HOME = "HOME"
PROPERTY_LOB_COMMERCIAL = "SMALL_COMMERCIAL"

# Underwriting tiers
UNDERWRITING_TIERS = ["PREFERRED", "STANDARD", "NON_STANDARD"]
TIER_WEIGHTS = [0.30, 0.55, 0.15]

# Policy statuses
POLICY_STATUSES = ["ACTIVE", "EXPIRED", "CANCELLED", "PENDING"]
STATUS_WEIGHTS = [0.70, 0.20, 0.05, 0.05]

# US States for realistic distribution
US_STATES = [
    "CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI",
    "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI",
    "CO", "MN", "SC", "AL", "LA", "KY", "OR", "OK", "CT", "IA",
    "UT", "AR", "NV", "MS", "KS", "NM", "NE", "WV", "ID", "HI",
    "NH", "ME", "RI", "MT", "DE", "SD", "ND", "AK", "VT", "WY"
]

# Vehicle makes/models for auto exposure
VEHICLE_MAKES = [
    "Toyota", "Ford", "Chevrolet", "Honda", "Nissan", "Jeep", "Ram",
    "GMC", "BMW", "Mercedes-Benz", "Audi", "Lexus", "Subaru", "Mazda",
    "Volkswagen", "Hyundai", "Kia", "Tesla", "Volvo", "Cadillac"
]

VEHICLE_MODELS_BY_MAKE = {
    "Toyota": ["Camry", "Corolla", "RAV4", "Highlander", "Prius", "Tacoma", "Tundra"],
    "Ford": ["F-150", "Explorer", "Escape", "Mustang", "Edge", "Fusion", "Ranger"],
    "Chevrolet": ["Silverado", "Equinox", "Tahoe", "Malibu", "Traverse", "Colorado"],
    "Honda": ["Civic", "Accord", "CR-V", "Pilot", "Odyssey", "Ridgeline"],
    "Nissan": ["Altima", "Rogue", "Sentra", "Pathfinder", "Frontier", "Armada"],
    "Jeep": ["Grand Cherokee", "Wrangler", "Cherokee", "Compass", "Renegade"],
    "Ram": ["1500", "2500", "3500"],
    "GMC": ["Sierra", "Yukon", "Acadia", "Terrain"],
    "BMW": ["3 Series", "5 Series", "X3", "X5"],
    "Mercedes-Benz": ["C-Class", "E-Class", "GLC", "GLE"],
    "Audi": ["A4", "A6", "Q5", "Q7"],
    "Lexus": ["RX", "ES", "NX", "GX"],
    "Subaru": ["Outback", "Forester", "Crosstrek", "Ascent"],
    "Mazda": ["CX-5", "CX-9", "Mazda3", "Mazda6"],
    "Volkswagen": ["Jetta", "Passat", "Atlas", "Tiguan"],
    "Hyundai": ["Elantra", "Sonata", "Tucson", "Santa Fe"],
    "Kia": ["Sorento", "Sportage", "Optima", "Telluride"],
    "Tesla": ["Model 3", "Model Y", "Model S", "Model X"],
    "Volvo": ["XC60", "XC90", "S60", "S90"],
    "Cadillac": ["XT5", "XT6", "Escalade", "CT5"]
}

# Property types
PROPERTY_TYPES = ["SINGLE_FAMILY", "TOWNHOME", "CONDO", "SMALL_COMMERCIAL"]
CONSTRUCTION_TYPES = ["FRAME", "BRICK", "MASONRY", "CONCRETE"]

# Claim types
AUTO_CLAIM_TYPES = ["COLLISION", "COMPREHENSIVE", "LIABILITY", "PERSONAL_INJURY"]
PROPERTY_CLAIM_TYPES = ["HOME_PROPERTY", "WIND", "WATER", "FIRE", "THEFT"]

# Cause of loss
CAUSES_OF_LOSS = [
    "VEHICLE_COLLISION", "WEATHER", "THEFT", "VANDALISM", "FIRE", "WATER_DAMAGE",
    "WIND_DAMAGE", "HAIL", "FALLING_OBJECT", "ANIMAL_COLLISION"
]

# Claim statuses
CLAIM_STATUSES = ["OPEN", "CLOSED", "PENDING"]
CLAIM_STATUS_WEIGHTS = [0.15, 0.80, 0.05]

# Transaction types
PREMIUM_TX_TYPES = ["BILL", "PAYMENT", "REFUND", "FEE"]
CLAIM_TX_TYPES = ["LOSS", "EXPENSE", "RESERVE", "RECOVERY"]
CLAIM_TX_COMPONENTS = ["LOSS", "EXPENSE", "RESERVE"]

# ============================================================================
# Helper Functions
# ============================================================================

def generate_party_id(start_id: int = 1) -> int:
    """Generate sequential party IDs"""
    return start_id

def generate_agent_id(start_id: int = 1) -> int:
    """Generate sequential agent IDs"""
    return start_id

def generate_policy_id(start_id: int = 1) -> int:
    """Generate sequential policy IDs"""
    return start_id

def generate_claim_id(start_id: int = 1) -> int:
    """Generate sequential claim IDs"""
    return start_id

def random_date(start_date: date, end_date: date) -> date:
    """Generate random date between start and end"""
    time_between = end_date - start_date
    days_between = time_between.days
    random_days = random.randrange(days_between)
    return start_date + timedelta(days=random_days)

def random_weighted_choice(choices: List[str], weights: List[float]) -> str:
    """Choose from list based on weights"""
    return random.choices(choices, weights=weights, k=1)[0]

def calculate_earned_premium(written_premium: Decimal, effective_date: date, 
                            expiration_date: date, as_of_date: date = None) -> Decimal:
    """Calculate earned premium based on time elapsed"""
    if as_of_date is None:
        as_of_date = date.today()
    
    if as_of_date < effective_date:
        return Decimal('0.00')
    
    if as_of_date >= expiration_date:
        return written_premium
    
    total_days = (expiration_date - effective_date).days
    elapsed_days = (as_of_date - effective_date).days
    
    if total_days == 0:
        return written_premium
    
    earned_ratio = Decimal(elapsed_days) / Decimal(total_days)
    return written_premium * earned_ratio

def generate_realistic_address() -> Tuple[str, str, str, str]:
    """Generate realistic US address"""
    street = fake.street_address()
    city = fake.city()
    state = random.choice(US_STATES)
    postal_code = fake.zipcode_in_state(state)
    return street, city, state, postal_code

def generate_risk_score(tier: str) -> Decimal:
    """Generate risk score based on underwriting tier"""
    if tier == "PREFERRED":
        return Decimal(random.uniform(0.1, 0.4))
    elif tier == "STANDARD":
        return Decimal(random.uniform(0.4, 0.7))
    else:  # NON_STANDARD
        return Decimal(random.uniform(0.7, 0.95))

def generate_premium(lob: str, tier: str, state: str) -> Decimal:
    """Generate realistic premium based on LOB, tier, and state"""
    base_premiums = {
        "AUTO": {"PREFERRED": 1200, "STANDARD": 1800, "NON_STANDARD": 2800},
        "HOME": {"PREFERRED": 1500, "STANDARD": 2200, "NON_STANDARD": 3500},
        "SMALL_COMMERCIAL": {"PREFERRED": 3500, "STANDARD": 5000, "NON_STANDARD": 8000}
    }
    
    base = base_premiums.get(lob, {}).get(tier, 2000)
    
    # Adjust for high-cost states (CA, NY, FL, TX)
    if state in ["CA", "NY", "FL", "TX"]:
        base *= Decimal('1.2')
    
    # Add some randomness
    variation = Decimal(random.uniform(0.8, 1.3))
    return Decimal(base) * variation

# ============================================================================
# Data Generation Functions
# ============================================================================

def generate_parties(num_parties: int, start_id: int = 1) -> List[Dict]:
    """Generate customer parties"""
    parties = []
    start_date = date(2010, 1, 1)
    end_date = date(2023, 12, 31)
    
    for i in range(num_parties):
        party_id = start_id + i
        first_name = fake.first_name()
        last_name = fake.last_name()
        full_name = f"{first_name} {last_name}"
        
        # Generate realistic DOB (ages 25-75)
        dob = fake.date_of_birth(minimum_age=25, maximum_age=75)
        
        # Generate address
        street, city, state, postal_code = generate_realistic_address()
        
        # Assign customer segment
        customer_segment = random_weighted_choice(CUSTOMER_SEGMENTS, SEGMENT_WEIGHTS)
        
        # Tenure start date (when they became a customer)
        tenure_start = random_date(start_date, end_date)
        
        # Email and phone
        email = f"{first_name.lower()}.{last_name.lower()}@{fake.domain_name()}"
        phone = fake.phone_number()
        
        party = {
            "party_id": party_id,
            "party_type": "PERSON",
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "date_of_birth": dob,
            "primary_email": email,
            "primary_phone": phone,
            "street_address": street,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": "USA",
            "customer_segment": customer_segment,
            "tenure_start_date": tenure_start,
            "created_at": tenure_start,
            "updated_at": tenure_start
        }
        parties.append(party)
    
    return parties

def generate_agents(num_agents: int, start_id: int = 1) -> List[Dict]:
    """Generate insurance agents"""
    agents = []
    regions = ["NORTHEAST", "SOUTHEAST", "MIDWEST", "SOUTHWEST", "WEST", "PACIFIC"]
    
    for i in range(num_agents):
        agent_id = start_id + i
        agent_name = fake.company()
        agent_code = f"AGT{agent_id:04d}"
        region = random.choice(regions)
        agent_type = random.choice(["INDEPENDENT", "CAPTIVE", "BROKER"])
        
        agent = {
            "agent_id": agent_id,
            "agent_code": agent_code,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "region": region,
            "active_flag": True,
            "primary_email": f"contact@{agent_name.lower().replace(' ', '')}.com",
            "primary_phone": fake.phone_number(),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        agents.append(agent)
    
    return agents

def generate_auto_policies(parties: List[Dict], agents: List[Dict], 
                          policy_rate: float, start_policy_id: int = 1) -> List[Dict]:
    """Generate auto insurance policies"""
    policies = []
    num_policies = int(len(parties) * policy_rate)
    selected_parties = random.sample(parties, num_policies)
    
    policy_id = start_policy_id
    start_date = date(2020, 1, 1)
    end_date = date(2025, 12, 31)
    
    for party in selected_parties:
        # Policy dates
        effective_date = random_date(start_date, date(2025, 11, 30))
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

def generate_property_policies(parties: List[Dict], agents: List[Dict],
                              policy_rate: float, start_policy_id: int = 1) -> List[Dict]:
    """Generate property insurance policies"""
    policies = []
    num_policies = int(len(parties) * policy_rate)
    selected_parties = random.sample(parties, num_policies)
    
    policy_id = start_policy_id
    start_date = date(2020, 1, 1)
    
    for party in selected_parties:
        # Policy dates
        effective_date = random_date(start_date, date(2025, 11, 30))
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

def generate_auto_exposures(policies: List[Dict], start_exposure_id: int = 1) -> List[Dict]:
    """Generate auto exposures (vehicles)"""
    exposures = []
    exposure_id = start_exposure_id
    
    for policy in policies:
        # Most policies have 1-2 vehicles
        num_vehicles = random.choices([1, 2], weights=[0.7, 0.3])[0]
        
        for _ in range(num_vehicles):
            make = random.choice(VEHICLE_MAKES)
            model = random.choice(VEHICLE_MODELS_BY_MAKE.get(make, ["Unknown"]))
            model_year = random.randint(2015, 2024)
            
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

def generate_property_exposures(policies: List[Dict], start_exposure_id: int = 1) -> List[Dict]:
    """Generate property exposures"""
    exposures = []
    exposure_id = start_exposure_id
    
    for policy in policies:
        property_type = random.choice(PROPERTY_TYPES)
        construction = random.choice(CONSTRUCTION_TYPES)
        year_built = random.randint(1950, 2023)
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
                        claim_rate: float = 0.15, start_claim_id: int = 1) -> List[Dict]:
    """Generate auto insurance claims"""
    claims = []
    num_claims = int(len(policies) * claim_rate)
    selected_policies = random.sample(policies, min(num_claims, len(policies)))
    
    claim_id = start_claim_id
    start_date = date(2020, 1, 1)
    end_date = date.today()
    
    # Create exposure lookup by policy
    exposure_by_policy = {}
    for exp in exposures:
        if exp["policy_id"] not in exposure_by_policy:
            exposure_by_policy[exp["policy_id"]] = []
        exposure_by_policy[exp["policy_id"]].append(exp)
    
    for policy in selected_policies:
        # Claim dates
        loss_date = random_date(start_date, end_date)
        report_date = loss_date + timedelta(days=random.randint(0, 7))
        
        # Some claims are closed
        if random.random() < 0.8:
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
                            claim_rate: float = 0.12, start_claim_id: int = 1) -> List[Dict]:
    """Generate property insurance claims"""
    claims = []
    num_claims = int(len(policies) * claim_rate)
    selected_policies = random.sample(policies, min(num_claims, len(policies)))
    
    claim_id = start_claim_id
    start_date = date(2020, 1, 1)
    end_date = date.today()
    
    # Create exposure lookup
    exposure_by_policy = {}
    for exp in exposures:
        if exp["policy_id"] not in exposure_by_policy:
            exposure_by_policy[exp["policy_id"]] = []
        exposure_by_policy[exp["policy_id"]].append(exp)
    
    for policy in selected_policies:
        loss_date = random_date(start_date, end_date)
        report_date = loss_date + timedelta(days=random.randint(0, 3))
        
        if random.random() < 0.85:
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
        
        litigation_flag = random.random() < 0.05  # Less common for property
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
            "injury_severity": "NONE",  # Property claims typically no injury
            "created_at": report_date,
            "updated_at": close_date if close_date else report_date
        }
        claims.append(claim)
        claim_id += 1
    
    return claims

def generate_premium_transactions(policies: List[Dict], start_tx_id: int = 1) -> List[Dict]:
    """Generate premium transactions (bills, payments)"""
    transactions = []
    tx_id = start_tx_id
    
    for policy in policies:
        # Generate bills and payments over policy lifetime
        effective = policy["effective_date"]
        expiration = policy["expiration_date"]
        
        # Annual billing - generate transactions
        if policy["billing_plan"] == "ANNUAL":
            # Bill at start
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
            
            # Payment (most policies pay)
            if random.random() < 0.95:
                payment_date = effective + timedelta(days=random.randint(0, 30))
                transactions.append({
                    "premium_transaction_id": tx_id,
                    "policy_id": policy["policy_id"],
                    "transaction_date": payment_date,
                    "transaction_type": "PAYMENT",
                    "amount": -policy["written_premium"],  # Negative for payment
                    "currency_code": "USD",
                    "payment_method": random.choice(["CREDIT_CARD", "ACH", "CHECK", "WIRE"]),
                    "channel": random.choice(["ONLINE", "AGENT", "PHONE"]),
                    "status": "POSTED"
                })
                tx_id += 1
        
        elif policy["billing_plan"] == "SEMI_ANNUAL":
            # Two bills per year
            for i in range(2):
                bill_date = effective + timedelta(days=i*180)
                if bill_date <= expiration:
                    transactions.append({
                        "premium_transaction_id": tx_id,
                        "policy_id": policy["policy_id"],
                        "transaction_date": bill_date,
                        "transaction_type": "BILL",
                        "amount": policy["written_premium"] / 2,
                        "currency_code": "USD",
                        "payment_method": None,
                        "channel": "SYSTEM",
                        "status": "POSTED"
                    })
                    tx_id += 1
                    
                    if random.random() < 0.95:
                        payment_date = bill_date + timedelta(days=random.randint(0, 30))
                        transactions.append({
                            "premium_transaction_id": tx_id,
                            "policy_id": policy["policy_id"],
                            "transaction_date": payment_date,
                            "transaction_type": "PAYMENT",
                            "amount": -(policy["written_premium"] / 2),
                            "currency_code": "USD",
                            "payment_method": random.choice(["CREDIT_CARD", "ACH", "CHECK"]),
                            "channel": random.choice(["ONLINE", "AGENT"]),
                            "status": "POSTED"
                        })
                        tx_id += 1
    
    return transactions

def generate_claim_transactions(claims: List[Dict], start_tx_id: int = 1) -> List[Dict]:
    """Generate claim transactions (payments, reserves)"""
    transactions = []
    tx_id = start_tx_id
    
    for claim in claims:
        # Loss payments
        if claim["paid_loss_amount"] > 0:
            # May have multiple payments
            num_payments = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
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
        
        # Recoveries
        if claim["recoveries_amount"] > 0:
            transactions.append({
                "claim_transaction_id": tx_id,
                "claim_id": claim["claim_id"],
                "transaction_date": claim["close_date"] - timedelta(days=random.randint(1, 30)),
                "transaction_type": "RECOVERY",
                "component_type": "RECOVERY",
                "amount": -claim["recoveries_amount"],  # Negative for recovery
                "currency_code": "USD",
                "payee_type": "SUBROGATION",
                "payee_name": "Subrogation Recovery",
                "note": "Subrogation recovery"
            })
            tx_id += 1
    
    return transactions

# ============================================================================
# Database Insertion Functions
# ============================================================================

def insert_data(engine, table_name: str, data: List[Dict], schema: str = None):
    """Insert data into database table"""
    if schema:
        full_table = f"{schema}.{table_name}"
    else:
        full_table = table_name
    
    if not data:
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

# ============================================================================
# Main Function
# ============================================================================

def clear_existing_data(engine):
    """Clear existing data from tables (in reverse dependency order)"""
    print("🧹 Clearing existing data...")
    
    tables_to_clear = [
        ("auto_insurance", "claim_transaction_auto"),
        ("auto_insurance", "premium_transaction_auto"),
        ("auto_insurance", "claim_auto"),
        ("auto_insurance", "auto_exposure"),
        ("auto_insurance", "policy_auto"),
        ("property_insurance", "claim_transaction_property"),
        ("property_insurance", "premium_transaction_property"),
        ("property_insurance", "claim_property"),
        ("property_insurance", "property_exposure"),
        ("property_insurance", "policy_property"),
        ("core", "agent"),
        ("core", "party"),
    ]
    
    with engine.connect() as conn:
        for schema, table in tables_to_clear:
            try:
                conn.execute(text(f"TRUNCATE TABLE {schema}.{table} CASCADE"))
                conn.commit()
                print(f"  ✅ Cleared {schema}.{table}")
            except Exception as e:
                print(f"  ⚠️  Could not clear {schema}.{table}: {e}")
    
    print("")

def main():
    """Generate and insert all seed data"""
    settings = get_settings()
    
    # Connect to insurance database
    engine = create_engine(settings.insurance_demo_db_url)
    
    print("🚀 Starting insurance demo data generation...")
    print(f"📊 Target: {NUM_CUSTOMERS} customers, {NUM_AGENTS} agents")
    print("")
    
    # Clear existing data
    clear_existing_data(engine)
    
    # Generate data
    print("👥 Generating parties (customers)...")
    parties = generate_parties(NUM_CUSTOMERS)
    print(f"  ✅ Generated {len(parties)} parties")
    
    print("🏢 Generating agents...")
    agents = generate_agents(NUM_AGENTS)
    print(f"  ✅ Generated {len(agents)} agents")
    
    print("🚗 Generating auto policies...")
    auto_policies = generate_auto_policies(parties, agents, AUTO_POLICY_RATE)
    print(f"  ✅ Generated {len(auto_policies)} auto policies")
    
    print("🏠 Generating property policies...")
    property_policies = generate_property_policies(parties, agents, PROPERTY_POLICY_RATE)
    print(f"  ✅ Generated {len(property_policies)} property policies")
    
    # Ensure overlap (customers with both)
    auto_party_ids = {p["policyholder_id"] for p in auto_policies}
    property_party_ids = {p["policyholder_id"] for p in property_policies}
    both_count = len(auto_party_ids & property_party_ids)
    print(f"  ✅ {both_count} customers have both auto and property policies")
    
    print("🚙 Generating auto exposures...")
    auto_exposures = generate_auto_exposures(auto_policies)
    print(f"  ✅ Generated {len(auto_exposures)} auto exposures")
    
    print("🏘️  Generating property exposures...")
    property_exposures = generate_property_exposures(property_policies)
    print(f"  ✅ Generated {len(property_exposures)} property exposures")
    
    print("💥 Generating auto claims...")
    auto_claims = generate_auto_claims(auto_policies, auto_exposures, claim_rate=0.15)
    print(f"  ✅ Generated {len(auto_claims)} auto claims")
    
    print("💥 Generating property claims...")
    property_claims = generate_property_claims(property_policies, property_exposures, claim_rate=0.12)
    print(f"  ✅ Generated {len(property_claims)} property claims")
    
    print("💰 Generating premium transactions...")
    auto_premium_tx = generate_premium_transactions(auto_policies)
    property_premium_tx = generate_premium_transactions(property_policies)
    print(f"  ✅ Generated {len(auto_premium_tx)} auto premium transactions")
    print(f"  ✅ Generated {len(property_premium_tx)} property premium transactions")
    
    print("💸 Generating claim transactions...")
    auto_claim_tx = generate_claim_transactions(auto_claims)
    property_claim_tx = generate_claim_transactions(property_claims)
    print(f"  ✅ Generated {len(auto_claim_tx)} auto claim transactions")
    print(f"  ✅ Generated {len(property_claim_tx)} property claim transactions")
    
    # Insert into database
    print("\n📥 Inserting data into database...")
    
    try:
        insert_data(engine, "party", parties, "core")
        insert_data(engine, "agent", agents, "core")
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
        
        print("\n🎉 Data generation and insertion complete!")
        print(f"\n📊 Summary:")
        print(f"  - Customers: {len(parties)}")
        print(f"  - Agents: {len(agents)}")
        print(f"  - Auto Policies: {len(auto_policies)}")
        print(f"  - Property Policies: {len(property_policies)}")
        print(f"  - Customers with Both: {both_count}")
        print(f"  - Auto Claims: {len(auto_claims)}")
        print(f"  - Property Claims: {len(property_claims)}")
        print(f"  - Total Transactions: {len(auto_premium_tx) + len(property_premium_tx) + len(auto_claim_tx) + len(property_claim_tx)}")
        
    except Exception as e:
        print(f"\n❌ Error inserting data: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()

