#!/usr/bin/env python3
"""
Script to fetch candidates from Greenhouse and format them for frontend hardcoding.
Run this to get real candidate data for demo purposes.

Usage: docker exec docker-app-1 python3 /tmp/fetch_greenhouse_candidates.py
"""

import sys
import os
import json
import base64
import requests
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def fetch_candidates() -> List[Dict[str, Any]]:
    """Fetch candidates from Greenhouse."""
    # Import inside function to avoid issues if running outside container
    from src.models import database
    from src.services.ingestion.connector_service import ConnectorService
    from src.models.connector import ConnectorConfiguration
    
    # Initialize database (use module import pattern)
    if database.SessionLocal is None:
        database.init_database()
    db = database.SessionLocal()
    
    try:
        # Get connector
        config = db.query(ConnectorConfiguration).filter(
            ConnectorConfiguration.customer_id == 'eliza',
            ConnectorConfiguration.connector_type == 'greenhouse',
            ConnectorConfiguration.is_enabled == True
        ).first()
        
        if not config:
            print("❌ No Greenhouse connector found")
            return []
        
        # Get credentials
        connector_service = ConnectorService(db)
        credentials = connector_service.get_credentials(config)
        api_key = credentials.get('api_key')
        
        if not api_key:
            print("❌ No API key found")
            return []
        
        # Create auth headers
        credential = base64.b64encode(f'{api_key}:'.encode()).decode()
        headers = {
            'Authorization': f'Basic {credential}',
            'Content-Type': 'application/json'
        }
        
        # Fetch applications
        print("📡 Fetching applications from Greenhouse...")
        response = requests.get(
            'https://harvest.greenhouse.io/v1/applications',
            headers=headers,
            params={'per_page': 100, 'page': 1},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Greenhouse API error: {response.status_code}")
            print(response.text[:500])
            return []
        
        applications = response.json()
        print(f"✅ Fetched {len(applications)} applications")
        
        # Debug: Check structure of first application
        if len(applications) > 0:
            print(f"\n🔍 Debugging first application structure:")
            first_app = applications[0]
            print(f"   Top-level keys: {list(first_app.keys())}")
            if 'candidate' in first_app:
                candidate = first_app['candidate']
                print(f"   Candidate keys: {list(candidate.keys())}")
                print(f"   Candidate ID: {candidate.get('id')}")
                print(f"   Email addresses: {candidate.get('email_addresses', [])}")
            else:
                print(f"   ⚠️  No 'candidate' key found!")
                print(f"   Sample keys: {list(first_app.keys())[:10]}")
        
        # Process candidates
        candidates_map = {}
        candidates_found = 0
        target_count = 10
        skipped_no_email = 0
        skipped_no_id = 0
        
        print(f"\n🔍 Processing {len(applications)} applications to find {target_count} candidates with emails...\n")
        
        for app in applications:
            if candidates_found >= target_count:
                break
            
            # Greenhouse API returns candidate_id at top level, not nested candidate object
            candidate_id = app.get('candidate_id')
            
            if not candidate_id:
                skipped_no_id += 1
                continue
            
            if candidate_id in candidates_map:
                continue  # Skip duplicates
            
            # Fetch candidate details from Greenhouse API
            try:
                candidate_response = requests.get(
                    f'https://harvest.greenhouse.io/v1/candidates/{candidate_id}',
                    headers=headers,
                    timeout=10
                )
                
                if candidate_response.status_code != 200:
                    skipped_no_id += 1
                    continue
                
                candidate_data = candidate_response.json()
            except Exception as e:
                print(f"  ⚠️  Error fetching candidate {candidate_id}: {e}")
                skipped_no_id += 1
                continue
            
            # Extract email
            email = None
            if candidate_data.get('email_addresses'):
                email_addresses = candidate_data['email_addresses']
                if isinstance(email_addresses, list) and len(email_addresses) > 0:
                    email = email_addresses[0].get('value')
            
            if not email and candidate_data.get('email'):
                email = candidate_data.get('email')
            
            if not email:
                skipped_no_email += 1
                if skipped_no_email <= 3:  # Show first 3 examples
                    name = f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}".strip()
                    print(f"  ⚠️  Skipping candidate {candidate_id} ({name}): No email found")
                continue
            
            # Extract other fields
            phone = None
            if candidate_data.get('phone_numbers'):
                phone = candidate_data['phone_numbers'][0].get('value') if candidate_data['phone_numbers'] else None
            
            linkedin = None
            if candidate_data.get('social_media_addresses'):
                for sm in candidate_data['social_media_addresses']:
                    if sm.get('type') == 'LinkedIn':
                        linkedin = sm.get('value')
                        break
            
            location = None
            if candidate_data.get('addresses'):
                addr = candidate_data['addresses'][0]
                location_parts = []
                if addr.get('city'):
                    location_parts.append(addr['city'])
                if addr.get('state'):
                    location_parts.append(addr['state'])
                if addr.get('country'):
                    location_parts.append(addr['country'])
                location = ', '.join(location_parts) if location_parts else None
            
            current_title = None
            current_company = None
            if candidate_data.get('employments'):
                latest = candidate_data['employments'][0]
                current_title = latest.get('title')
                current_company = latest.get('company_name')
            
            # Get profile URL from application
            profile_url = app.get('profile_url')
            if not profile_url and candidate_id:
                # Try to get from candidate's applications
                if candidate_data.get('applications') and len(candidate_data['applications']) > 0:
                    profile_url = candidate_data['applications'][0].get('profile_url')
                if not profile_url:
                    profile_url = f'https://app.greenhouse.io/people/{candidate_id}'
            
            # Extract application/job information
            previous_job_title = None
            if app.get('jobs') and len(app['jobs']) > 0:
                previous_job_title = app['jobs'][0].get('name')
            
            # Extract application status and stage
            previous_application_status = app.get('status')  # e.g., "rejected", "active", "hired"
            previous_stage_name = None
            if app.get('current_stage'):
                previous_stage_name = app['current_stage'].get('name')
            
            # Extract rejection information
            rejection_reason = None
            rejected_at = None
            if app.get('rejection_reason'):
                rejection_reason_obj = app['rejection_reason']
                if isinstance(rejection_reason_obj, dict):
                    rejection_reason = rejection_reason_obj.get('name') or rejection_reason_obj.get('type')
                elif isinstance(rejection_reason_obj, str):
                    rejection_reason = rejection_reason_obj
            
            if app.get('rejected_at'):
                rejected_at = app['rejected_at']
            
            # Extract application date
            applied_at = app.get('applied_at')
            
            name = f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}".strip()
            
            candidates_map[candidate_id] = {
                'id': f'gh_{candidate_id}',
                'greenhouse_candidate_id': candidate_id,
                'name': name,
                'email': email,
                'phone': phone,
                'linkedin': linkedin,
                'location': location,
                'current_title': current_title,
                'current_company': current_company,
                'greenhouse_profile_url': profile_url,
                'previous_job_title': previous_job_title,
                'previous_application_status': previous_application_status,
                'previous_stage_name': previous_stage_name,
                'rejection_reason': rejection_reason,
                'rejected_at': rejected_at,
                'applied_at': applied_at,
            }
            
            candidates_found += 1
            name = f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}".strip()
            print(f"  ✓ Found candidate {candidates_found}/{target_count}: {name} ({email})")
        
        print(f"\n📊 Summary:")
        print(f"   - Applications processed: {len(applications)}")
        print(f"   - Candidates found: {candidates_found}")
        print(f"   - Skipped (no ID): {skipped_no_id}")
        print(f"   - Skipped (no email): {skipped_no_email}")
        
        return list(candidates_map.values())
    
    finally:
        db.close()

def format_for_frontend(candidates: List[Dict[str, Any]]) -> str:
    """Format candidates as TypeScript array for frontend."""
    formatted = []
    
    for idx, c in enumerate(candidates):
        # Generate mock score and other required fields
        score = round(8.0 + (idx * 0.3) + (hash(c['email']) % 10) * 0.1, 1)
        first_name = c['name'].split(' ')[0] if c['name'] else 'Candidate'
        current_title = c['current_title'] or 'Position'
        name_escaped = c['name'].replace("'", "\\'")
        location_escaped = (c['location'] or 'Location not specified').replace("'", "\\'")
        
        highlights = []
        if c['current_title']:
            title_escaped = c['current_title'].replace("'", "\\'")
            highlights.append(f"'{title_escaped}'")
        if c['current_company']:
            company_escaped = c['current_company'].replace("'", "\\'")
            highlights.append(f"'{company_escaped}'")
        highlights_str = ', '.join(highlights) if highlights else ''
        highlights_code = f"[{highlights_str}]" if highlights_str else '[]'
        
        # Extract previous application info
        previous_job_title = c.get('previous_job_title') or None
        previous_status = c.get('previous_application_status') or None
        previous_stage = c.get('previous_stage_name') or None
        rejection_reason = c.get('rejection_reason') or None
        rejected_at = c.get('rejected_at') or None
        applied_at = c.get('applied_at') or None
        
        # Build greenhouse history string
        history_parts = ['previouslyApplied: true']
        if previous_job_title:
            title_escaped = previous_job_title.replace("'", "\\'")
            history_parts.append(f"previousRole: '{title_escaped}'")
        if previous_status:
            history_parts.append(f"previousStatus: '{previous_status}'")
        if previous_stage:
            stage_escaped = previous_stage.replace("'", "\\'")
            history_parts.append(f"previousStage: '{stage_escaped}'")
        if rejection_reason:
            reason_escaped = rejection_reason.replace("'", "\\'")
            history_parts.append(f"rejectionReason: '{reason_escaped}'")
        if rejected_at:
            history_parts.append(f"rejectedAt: '{rejected_at}'")
        if applied_at:
            history_parts.append(f"appliedAt: '{applied_at}'")
        
        greenhouse_history_str = ',\n      '.join(history_parts)
        
        # Build email body with proper escaping
        newline = '\\n'
        email_body = f"Hi {first_name},{newline}{newline}Thank you for your interest in our company. We'd like to follow up on your application.{newline}{newline}Best regards,{newline}[Your Name]"
        
        candidate_obj = f"""  {{
    id: '{c['id']}',
    name: '{name_escaped}',
    email: '{c['email']}',
    phone: '{c['phone'] or 'N/A'}',
    linkedin: '{c['linkedin'] or '#'}',
    score: {score},
    rank: {idx + 1},
    source: 'applicant' as const,
    location: '{location_escaped}',
    timezone: 'PST',
    visaRequired: false,
    greenhouseHistory: {{
      {greenhouse_history_str}
    }},
    highlights: {highlights_code}.filter(Boolean) as string[],
    prewrittenEmail: {{
      subject: `Following Up on Your Application - {current_title}`,
      body: `{email_body}`,
    }},
    outreachStatus: 'pending' as const,
    scheduledFor: undefined,
    analysisId: 'greenhouse-import',
    analysisName: 'Greenhouse Candidates',
    analysisDate: new Date().toISOString().split('T')[0],
    greenhouseProfileUrl: '{c['greenhouse_profile_url']}',
    greenhouseCandidateId: {c['greenhouse_candidate_id']},
  }}"""
        formatted.append(candidate_obj)
    
    return '[\n' + ',\n'.join(formatted) + '\n]'

if __name__ == '__main__':
    print("🚀 Fetching Greenhouse candidates...\n")
    candidates = fetch_candidates()
    
    if not candidates:
        print("\n❌ No candidates found")
        sys.exit(1)
    
    print(f"\n✅ Found {len(candidates)} candidates")
    print("\n" + "="*80)
    print("FRONTEND CODE (copy this into CandidateOutreachPage.tsx):")
    print("="*80 + "\n")
    
    frontend_code = format_for_frontend(candidates)
    print(frontend_code)
    
    print("\n" + "="*80)
    print("JSON (for reference):")
    print("="*80 + "\n")
    print(json.dumps(candidates, indent=2))

