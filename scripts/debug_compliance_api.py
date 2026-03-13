#!/usr/bin/env python3
"""
Debug script to fetch raw data from OpenAI Compliance API and save to CSV.

This helps investigate the parsing bug in adoption metrics.

Usage:
    source .venv/bin/activate
    python scripts/debug_compliance_api.py

Environment variables required (in .env file):
    - OPENAI_API_COMPLIANCE_KEY or OPENAI_API_KEY
    - CHATGPT_WORKSPACE_ID
"""

import os
import sys
import csv
import json
import requests
from datetime import date, datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv("OPENAI_API_COMPLIANCE_KEY") or os.getenv("OPENAI_API_KEY")
WORKSPACE_ID = os.getenv("CHATGPT_WORKSPACE_ID")
BASE_URL = "https://api.chatgpt.com/v1"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "debug_output"
OUTPUT_DIR.mkdir(exist_ok=True)


def get_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def fetch_users() -> list:
    """Fetch all users from workspace."""
    print("\n📥 Fetching users...")
    all_users = []
    after = None
    
    while True:
        params = {"limit": 200}
        if after:
            params["after"] = after
        
        response = requests.get(
            f"{BASE_URL}/compliance/workspaces/{WORKSPACE_ID}/users",
            headers=get_headers(),
            params=params,
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"  ❌ Error fetching users: {response.status_code}")
            print(f"     {response.text[:500]}")
            break
        
        data = response.json()
        users = data.get("data", [])
        all_users.extend(users)
        
        print(f"  ✓ Fetched {len(users)} users (total: {len(all_users)})")
        
        if not data.get("has_more"):
            break
        after = data.get("last_id")
    
    return all_users


def fetch_conversations(since_date: date = None, max_count: int = 1000) -> list:
    """Fetch conversations from workspace."""
    print(f"\n📥 Fetching conversations (max {max_count})...")
    all_conversations = []
    after = None
    
    since_timestamp = None
    if since_date:
        since_timestamp = int(datetime.combine(since_date, datetime.min.time()).timestamp())
        print(f"  📅 Since: {since_date} (timestamp: {since_timestamp})")
    
    while len(all_conversations) < max_count:
        params = {"limit": 500}
        if after:
            params["after"] = after
        elif since_timestamp:
            params["since_timestamp"] = since_timestamp
        
        response = requests.get(
            f"{BASE_URL}/compliance/workspaces/{WORKSPACE_ID}/conversations",
            headers=get_headers(),
            params=params,
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"  ❌ Error fetching conversations: {response.status_code}")
            print(f"     {response.text[:500]}")
            break
        
        data = response.json()
        convos = data.get("data", [])
        all_conversations.extend(convos)
        
        print(f"  ✓ Fetched {len(convos)} conversations (total: {len(all_conversations)})")
        
        if not data.get("has_more"):
            break
        after = data.get("last_id")
    
    return all_conversations


def fetch_gpts() -> list:
    """Fetch all GPTs from workspace."""
    print("\n📥 Fetching GPTs...")
    all_gpts = []
    after = None
    
    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after
        
        response = requests.get(
            f"{BASE_URL}/compliance/workspaces/{WORKSPACE_ID}/gpts",
            headers=get_headers(),
            params=params,
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"  ❌ Error fetching GPTs: {response.status_code}")
            print(f"     {response.text[:500]}")
            break
        
        data = response.json()
        gpts = data.get("data", [])
        all_gpts.extend(gpts)
        
        print(f"  ✓ Fetched {len(gpts)} GPTs (total: {len(all_gpts)})")
        
        if not data.get("has_more"):
            break
        after = data.get("last_id")
    
    return all_gpts


def save_users_csv(users: list, filepath: Path):
    """Save users to CSV."""
    if not users:
        print("  ⚠️  No users to save")
        return
    
    # Get all unique keys from all users
    all_keys = set()
    for user in users:
        all_keys.update(user.keys())
    
    fieldnames = sorted(all_keys)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for user in users:
            # Flatten nested dicts to JSON strings
            row = {}
            for k, v in user.items():
                if isinstance(v, (dict, list)):
                    row[k] = json.dumps(v)
                else:
                    row[k] = v
            writer.writerow(row)
    
    print(f"  ✓ Saved {len(users)} users to {filepath}")


def save_conversations_csv(conversations: list, filepath: Path):
    """Save conversations to CSV."""
    if not conversations:
        print("  ⚠️  No conversations to save")
        return
    
    # Flatten conversation data for CSV
    rows = []
    for conv in conversations:
        messages = conv.get("messages", {}).get("data", [])
        message_count = len(messages)
        
        # Parse timestamps
        created_at = conv.get("created_at")
        last_active_at = conv.get("last_active_at")
        
        # Convert epoch to readable date
        created_date = None
        if created_at:
            try:
                created_date = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        last_active_date = None
        if last_active_at:
            try:
                last_active_date = datetime.fromtimestamp(last_active_at).strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        row = {
            "id": conv.get("id"),
            "user_id": conv.get("user_id"),
            "user_email": conv.get("user_email"),
            "title": conv.get("title", "")[:100] if conv.get("title") else "",
            "created_at_epoch": created_at,
            "created_at": created_date,
            "last_active_at_epoch": last_active_at,
            "last_active_at": last_active_date,
            "message_count": message_count,
            "gizmo_id": conv.get("gizmo_id"),  # GPT used
            "model": conv.get("model"),
        }
        
        rows.append(row)
    
    if not rows:
        return
    
    fieldnames = list(rows[0].keys())
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"  ✓ Saved {len(rows)} conversations to {filepath}")


def save_gpts_csv(gpts: list, filepath: Path):
    """Save GPTs to CSV."""
    if not gpts:
        print("  ⚠️  No GPTs to save")
        return
    
    rows = []
    for gpt in gpts:
        sharing = gpt.get("sharing", {})
        row = {
            "id": gpt.get("id"),
            "short_url": gpt.get("short_url"),
            "name": gpt.get("name"),
            "builder_name": gpt.get("builder_name"),
            "owner_id": gpt.get("owner_id"),
            "owner_email": gpt.get("owner_email"),
            "visibility": sharing.get("visibility"),
            "created_at": gpt.get("created_at"),
            "updated_at": gpt.get("updated_at"),
        }
        rows.append(row)
    
    fieldnames = list(rows[0].keys())
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"  ✓ Saved {len(rows)} GPTs to {filepath}")


def save_raw_json(data: list, filepath: Path):
    """Save raw data as JSON for complete inspection."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"  ✓ Saved raw JSON to {filepath}")


def analyze_conversations(conversations: list):
    """Analyze conversation data to understand structure."""
    print("\n" + "=" * 60)
    print("📊 CONVERSATION ANALYSIS")
    print("=" * 60)
    
    if not conversations:
        print("  No conversations to analyze")
        return
    
    # Unique users
    user_ids = set()
    user_emails = set()
    total_messages = 0
    total_user_messages = 0
    convos_with_messages = 0
    
    # Daily breakdown
    daily_users = {}
    daily_convos = {}
    daily_all_messages = {}
    daily_user_messages = {}
    
    # Message role breakdown
    role_counts = {}
    
    for conv in conversations:
        user_id = conv.get("user_id")
        user_email = conv.get("user_email")
        
        if user_id:
            user_ids.add(user_id)
        if user_email:
            user_emails.add(user_email)
        
        messages = conv.get("messages", {}).get("data", [])
        msg_count = len(messages)
        total_messages += msg_count
        if msg_count > 0:
            convos_with_messages += 1
        
        # Count messages by role
        user_msg_count = 0
        for msg in messages:
            author = msg.get("author", {})
            role = author.get("role", "unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
            if role == "user":
                user_msg_count += 1
                total_user_messages += 1
        
        # Get date from created_at (conversation creation date)
        created_at = conv.get("created_at")
        if created_at:
            try:
                conv_date = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d")
                
                # Track daily unique users
                if conv_date not in daily_users:
                    daily_users[conv_date] = set()
                if user_id:
                    daily_users[conv_date].add(user_id)
                
                # Track daily conversations
                daily_convos[conv_date] = daily_convos.get(conv_date, 0) + 1
                
                # Track daily messages (all)
                daily_all_messages[conv_date] = daily_all_messages.get(conv_date, 0) + msg_count
                
                # Track daily USER messages only
                daily_user_messages[conv_date] = daily_user_messages.get(conv_date, 0) + user_msg_count
            except:
                pass
    
    print(f"\n  TOTALS (across all fetched data):")
    print(f"  ─────────────────────────────────")
    print(f"  Total conversations: {len(conversations)}")
    print(f"  Unique user IDs: {len(user_ids)}")
    print(f"  Unique user emails: {len(user_emails)}")
    print(f"  Conversations with embedded messages: {convos_with_messages}")
    print(f"  Total messages (all roles): {total_messages}")
    print(f"  Total USER messages only: {total_user_messages}")
    
    print(f"\n  MESSAGE ROLE BREAKDOWN:")
    print(f"  ─────────────────────────────────")
    for role, count in sorted(role_counts.items(), key=lambda x: -x[1]):
        marker = "✓" if role == "user" else " "
        print(f"  {marker} {role:<12}: {count:>6}")
    
    print(f"\n  DAILY BREAKDOWN (by conversation created_at):")
    print(f"  ─────────────────────────────────────────────────────")
    print(f"  {'Date':<12} {'Users':<8} {'Convos':<10} {'UserMsgs':<10} {'AllMsgs':<10}")
    print(f"  {'-'*12} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    
    for conv_date in sorted(daily_users.keys(), reverse=True)[:10]:
        users = len(daily_users.get(conv_date, set()))
        convos = daily_convos.get(conv_date, 0)
        user_msgs = daily_user_messages.get(conv_date, 0)
        all_msgs = daily_all_messages.get(conv_date, 0)
        print(f"  {conv_date:<12} {users:<8} {convos:<10} {user_msgs:<10} {all_msgs:<10}")
    
    # Check a sample conversation structure
    if conversations:
        sample = conversations[0]
        print(f"\n  SAMPLE CONVERSATION STRUCTURE:")
        print(f"  ─────────────────────────────────")
        print(f"  Top-level keys: {list(sample.keys())}")
        
        messages_obj = sample.get("messages", {})
        print(f"  messages field type: {type(messages_obj)}")
        if isinstance(messages_obj, dict):
            print(f"  messages dict keys: {list(messages_obj.keys())}")
            msg_data = messages_obj.get("data", [])
            print(f"  messages.data length: {len(msg_data)}")
            if msg_data:
                print(f"  Sample message keys: {list(msg_data[0].keys())}")
                author = msg_data[0].get("author", {})
                print(f"  Sample author keys: {list(author.keys())}")


def main():
    print("=" * 60)
    print("OpenAI Compliance API Debug Tool")
    print("=" * 60)
    
    # Validate config
    if not API_KEY:
        print("❌ Error: No API key found!")
        print("   Set OPENAI_API_COMPLIANCE_KEY or OPENAI_API_KEY in .env")
        return
    
    if not WORKSPACE_ID:
        print("❌ Error: No workspace ID found!")
        print("   Set CHATGPT_WORKSPACE_ID in .env")
        return
    
    print(f"\n🔧 Configuration:")
    print(f"   API Key: {API_KEY[:10]}...{API_KEY[-4:]}")
    print(f"   Workspace ID: {WORKSPACE_ID}")
    print(f"   Output Dir: {OUTPUT_DIR}")
    
    # Test connection
    print("\n🔌 Testing connection...")
    try:
        response = requests.get(
            f"{BASE_URL}/compliance/workspaces/{WORKSPACE_ID}/users",
            headers=get_headers(),
            params={"limit": 1},
            timeout=30
        )
        if response.status_code == 200:
            print("  ✓ Connection successful!")
        else:
            print(f"  ❌ Connection failed: {response.status_code}")
            print(f"     {response.text}")
            return
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return
    
    # Fetch all data
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Users
    users = fetch_users()
    save_users_csv(users, OUTPUT_DIR / f"users_{timestamp}.csv")
    save_raw_json(users, OUTPUT_DIR / f"users_{timestamp}.json")
    
    # GPTs
    gpts = fetch_gpts()
    save_gpts_csv(gpts, OUTPUT_DIR / f"gpts_{timestamp}.csv")
    save_raw_json(gpts, OUTPUT_DIR / f"gpts_{timestamp}.json")
    
    # Conversations - last 7 days
    since_date = date.today() - timedelta(days=7)
    conversations = fetch_conversations(since_date=since_date, max_count=2000)
    save_conversations_csv(conversations, OUTPUT_DIR / f"conversations_{timestamp}.csv")
    save_raw_json(conversations, OUTPUT_DIR / f"conversations_{timestamp}.json")
    
    # Analyze
    analyze_conversations(conversations)
    
    print("\n" + "=" * 60)
    print(f"✅ Done! Output saved to: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
