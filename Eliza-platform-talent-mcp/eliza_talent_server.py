#!/usr/bin/env python3
"""
Eliza Platform Talent Intelligence MCP Server - AI-powered talent analysis interface
"""
import os
import sys
import logging
import json
from datetime import datetime, timezone
import httpx
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("eliza-talent-server")

# Initialize MCP server
mcp = FastMCP("eliza-talent")

# Configuration
ELIZA_API_BASE = os.environ.get("ELIZA_API_BASE", "http://localhost:5001")

# API Key authentication (preferred method)
ELIZA_API_KEY = os.environ.get("ELIZA_API_KEY", "")

# Legacy email/password authentication (deprecated)
ELIZA_EMAIL = os.environ.get("ELIZA_EMAIL", "")
ELIZA_PASSWORD = os.environ.get("ELIZA_PASSWORD", "")

# Token storage (only used for legacy auth)
ACCESS_TOKEN = None
REFRESH_TOKEN = None

# === UTILITY FUNCTIONS ===

def format_datetime(dt_string):
    """Format ISO datetime to readable format"""
    try:
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return dt_string

async def ensure_authenticated():
    """Ensure we have valid authentication credentials"""
    global ACCESS_TOKEN, REFRESH_TOKEN

    # Prefer API key authentication
    if ELIZA_API_KEY:
        return True, None

    # Fall back to legacy email/password authentication
    if not ELIZA_EMAIL or not ELIZA_PASSWORD:
        return False, """❌ Authentication not configured.

Please set one of:
  • ELIZA_API_KEY (recommended) - Permanent API key for programmatic access
  • ELIZA_EMAIL + ELIZA_PASSWORD (legacy) - User credentials

To generate an API key, use the 'create_api_key' tool or visit the platform settings.
"""

    if ACCESS_TOKEN:
        return True, None

    # Attempt login with email/password
    logger.warning("Using legacy email/password authentication. Consider switching to API keys.")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ELIZA_API_BASE}/auth/login",
                json={
                    "email": ELIZA_EMAIL,
                    "password": ELIZA_PASSWORD,
                    "remember_me": False
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            ACCESS_TOKEN = data["access_token"]
            REFRESH_TOKEN = data["refresh_token"]
            logger.info("Successfully authenticated with Eliza Platform (legacy method)")
            return True, None
    except httpx.HTTPStatusError as e:
        logger.error(f"Authentication failed: {e.response.status_code}")
        return False, f"❌ Authentication failed: {e.response.status_code}"
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return False, f"❌ Authentication error: {str(e)}"

async def make_api_request(method, endpoint, data=None, files=None):
    """Make authenticated API request"""
    global ACCESS_TOKEN, REFRESH_TOKEN

    authenticated, error = await ensure_authenticated()
    if not authenticated:
        return None, error

    # Use API key if available, otherwise use JWT token
    if ELIZA_API_KEY:
        headers = {"Authorization": f"Bearer {ELIZA_API_KEY}"}
    else:
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    try:
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(
                    f"{ELIZA_API_BASE}{endpoint}",
                    headers=headers,
                    timeout=60
                )
            elif method == "POST":
                if files:
                    response = await client.post(
                        f"{ELIZA_API_BASE}{endpoint}",
                        headers=headers,
                        data=data,
                        files=files,
                        timeout=120
                    )
                else:
                    response = await client.post(
                        f"{ELIZA_API_BASE}{endpoint}",
                        headers=headers,
                        json=data,
                        timeout=60
                    )
            elif method == "PUT":
                response = await client.put(
                    f"{ELIZA_API_BASE}{endpoint}",
                    headers=headers,
                    json=data,
                    timeout=60
                )
            elif method == "DELETE":
                response = await client.delete(
                    f"{ELIZA_API_BASE}{endpoint}",
                    headers=headers,
                    timeout=60
                )
            else:
                return None, f"❌ Unsupported method: {method}"
            
            response.raise_for_status()
            
            # Handle 204 No Content
            if response.status_code == 204:
                return {}, None
            
            return response.json(), None
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            # Try to refresh token
            ACCESS_TOKEN = None
            return None, "❌ Authentication expired. Please try again."
        error_detail = e.response.text
        try:
            error_json = e.response.json()
            error_detail = error_json.get("detail", error_detail)
        except:
            pass
        return None, f"❌ API Error {e.response.status_code}: {error_detail}"
    except Exception as e:
        logger.error(f"Request error: {e}")
        return None, f"❌ Request error: {str(e)}"

# === MCP TOOLS ===

# === AUTHENTICATION & API KEY MANAGEMENT ===

@mcp.tool()
async def check_authentication_status() -> str:
    """Check if authenticated with Eliza Platform and show current user info"""
    logger.info("Checking authentication status")

    authenticated, error = await ensure_authenticated()
    if not authenticated:
        return error

    data, error = await make_api_request("GET", "/auth/me")
    if error:
        return error

    user = data
    auth_method = "🔑 API Key" if ELIZA_API_KEY else "🔐 Email/Password (legacy)"

    return f"""✅ Authenticated as {user.get('full_name', user.get('email'))}

📧 Email: {user.get('email')}
👤 Username: {user.get('username')}
🎭 Roles: {', '.join(user.get('roles', []))}
🔑 Permissions: {', '.join(user.get('permissions', [])[:5])}{'...' if len(user.get('permissions', [])) > 5 else ''}
⏰ Last Login: {format_datetime(user.get('last_login_at', 'N/A'))}
🔐 Auth Method: {auth_method}
"""

@mcp.tool()
async def create_api_key(name: str = "", description: str = "", expires_in_days: str = "") -> str:
    """Create a new API key for programmatic access - SAVE THE KEY IMMEDIATELY as it's only shown once!"""
    logger.info("Creating new API key")

    if not name.strip():
        return """❌ Error: name is required

📝 Parameters:
- name: Human-readable name for the API key (required)
- description: Optional description of what this key is for
- expires_in_days: Optional expiration in days (1-365)

Example:
name: "MCP Server Production"
description: "API key for talent intelligence MCP server"
expires_in_days: "90"

⚠️ IMPORTANT: The full API key will only be shown ONCE after creation.
Save it immediately in a secure location (e.g., Docker secrets, environment variables).
"""

    payload = {
        "name": name.strip(),
    }

    if description.strip():
        payload["description"] = description.strip()

    if expires_in_days.strip():
        try:
            days = int(expires_in_days)
            if days < 1 or days > 365:
                return "❌ Error: expires_in_days must be between 1 and 365"
            payload["expires_in_days"] = days
        except ValueError:
            return "❌ Error: expires_in_days must be a number"

    data, error = await make_api_request("POST", "/v1/auth/api-keys", data=payload)
    if error:
        return error

    return f"""✅ API Key Created Successfully!

🔑 API KEY: {data.get('api_key')}

⚠️ SAVE THIS KEY NOW! It will never be shown again.

📋 Key Details:
   • Name: {data.get('name')}
   • Key ID: {data.get('key_id')}
   • Prefix: {data.get('key_prefix')}...
   • Created: {format_datetime(data.get('created_at'))}
   • Expires: {format_datetime(data.get('expires_at')) if data.get('expires_at') else 'Never'}

💡 To use this key:
   1. Save it to a file: echo "{data.get('api_key')}" > secrets/eliza_api_key.txt
   2. Update docker-compose.yml to mount as secret
   3. Set environment variable: ELIZA_API_KEY={data.get('api_key')}
   4. Restart the MCP server

🔒 Security: Store this key securely. Anyone with this key can access your account.
"""

@mcp.tool()
async def list_api_keys() -> str:
    """List all API keys for the current user"""
    logger.info("Listing API keys")

    data, error = await make_api_request("GET", "/v1/auth/api-keys")
    if error:
        return error

    keys = data if isinstance(data, list) else []

    if not keys:
        return """📋 No API keys found.

Use 'create_api_key' to generate a new API key for programmatic access.
"""

    output = f"📋 Your API Keys ({len(keys)} total)\n\n"

    for key in keys:
        status_emoji = "✅" if key.get('is_active') else "❌"
        expired = ""
        if key.get('expires_at'):
            from datetime import datetime
            exp_date = datetime.fromisoformat(key.get('expires_at').replace('Z', '+00:00'))
            if exp_date < datetime.now(timezone.utc):
                expired = " (EXPIRED)"
                status_emoji = "⏰"

        output += f"""{status_emoji} {key.get('name')}{expired}
   • Key ID: {key.get('key_id')}
   • Prefix: {key.get('key_prefix')}...
   • Created: {format_datetime(key.get('created_at'))}
   • Last Used: {format_datetime(key.get('last_used_at')) if key.get('last_used_at') else 'Never'}
   • Requests: {key.get('request_count', 0)}
   • Expires: {format_datetime(key.get('expires_at')) if key.get('expires_at') else 'Never'}

"""

    return output

@mcp.tool()
async def revoke_api_key(key_id: str = "") -> str:
    """Revoke an API key - this action cannot be undone"""
    logger.info(f"Revoking API key {key_id}")

    if not key_id.strip():
        return """❌ Error: key_id is required

Use 'list_api_keys' to see all your API keys and their IDs.

Example:
key_id: "abc123def456"

⚠️ WARNING: Revoking a key cannot be undone. Any applications using this key will lose access.
"""

    data, error = await make_api_request("DELETE", f"/v1/auth/api-keys/{key_id.strip()}")
    if error:
        return error

    return f"""✅ API key revoked successfully!

🔑 Key ID: {key_id}

⚠️ This key can no longer be used for authentication.
Any applications using this key will need to be updated with a new key.
"""

# === TALENT INTELLIGENCE TOOLS ===

@mcp.tool()
async def start_talent_analysis_from_connector(job_description: str = "", ideal_candidate_description: str = "", role: str = "", data_source_connector_id: str = "", baseline_employee_ids: str = "") -> str:
    """Start a talent analysis using resumes from a data connector - returns analysis_id to check status"""
    logger.info("Starting talent analysis from connector")
    
    # Validate required parameters
    missing = []
    if not job_description.strip():
        missing.append("job_description")
    if not ideal_candidate_description.strip():
        missing.append("ideal_candidate_description")
    if not role.strip():
        missing.append("role")
    if not data_source_connector_id.strip():
        missing.append("data_source_connector_id")
    
    if missing:
        return f"""❌ Missing required parameters: {', '.join(missing)}

📋 Required Information:
- job_description: Complete job description text
- ideal_candidate_description: Description of ideal candidate (skills, experience, etc.)
- role: Job role/title (e.g., "Machine Learning Engineer")
- data_source_connector_id: Connector ID with resume files

📝 Optional:
- baseline_employee_ids: Comma-separated employee IDs for baseline (e.g., "1,2,3")

Example:
job_description: "Senior ML Engineer role requiring Python and TensorFlow..."
ideal_candidate_description: "5+ years ML experience, strong Python skills..."
role: "Machine Learning Engineer"
data_source_connector_id: "conn_fs_resumes"
baseline_employee_ids: "1,2,3"
"""
    
    # Parse baseline employee IDs
    employee_ids = []
    if baseline_employee_ids.strip():
        try:
            employee_ids = [int(id.strip()) for id in baseline_employee_ids.split(",") if id.strip()]
        except ValueError:
            return "❌ Error: baseline_employee_ids must be comma-separated numbers (e.g., '1,2,3')"
    
    payload = {
        "job_description": job_description.strip(),
        "ideal_candidate_description": ideal_candidate_description.strip(),
        "role": role.strip(),
        "data_source_connector_id": data_source_connector_id.strip()
    }
    
    if employee_ids:
        payload["baseline_employee_ids"] = employee_ids
    
    data, error = await make_api_request("POST", "/api/v1/ml-talent/analyze-from-connector", data=payload)
    if error:
        return error
    
    return f"""✅ Talent analysis started successfully!

🆔 Analysis ID: {data.get('analysis_id')}
📊 Status: {data.get('status')}
💬 Message: {data.get('message', 'Analysis in progress')}

Use 'get_analysis_status' with this analysis_id to check progress.
"""

@mcp.tool()
async def get_analysis_status(analysis_id: str = "") -> str:
    """Get the current status of a talent analysis with progress percentage"""
    logger.info(f"Getting status for analysis {analysis_id}")
    
    if not analysis_id.strip():
        return "❌ Error: analysis_id is required"
    
    data, error = await make_api_request("GET", f"/api/v1/ml-talent/analysis/{analysis_id.strip()}/status")
    if error:
        return error
    
    status_emoji = {
        "pending": "⏳",
        "processing": "⚙️",
        "completed": "✅",
        "failed": "❌"
    }
    
    status = data.get('status', 'unknown')
    emoji = status_emoji.get(status, "❓")
    
    return f"""{emoji} Analysis Status

🆔 Analysis ID: {data.get('analysis_id')}
📊 Status: {status.upper()}
📈 Progress: {data.get('progress_percentage', 0)}%
💬 Message: {data.get('message', 'No message')}

{f"Use 'get_analysis_results' with this analysis_id to view full results." if status == 'completed' else ''}
"""

@mcp.tool()
async def get_analysis_results(analysis_id: str = "") -> str:
    """Get complete results of a completed talent analysis including top candidates and synthesis"""
    logger.info(f"Getting results for analysis {analysis_id}")
    
    if not analysis_id.strip():
        return "❌ Error: analysis_id is required"
    
    data, error = await make_api_request("GET", f"/api/v1/ml-talent/analysis/{analysis_id.strip()}")
    if error:
        return error
    
    status = data.get('status', 'unknown')
    if status != 'completed':
        return f"⚠️ Analysis not yet completed. Current status: {status}\nUse 'get_analysis_status' to check progress."
    
    # Format top candidates
    top_overall = data.get('top_overall', [])[:5]
    candidates_text = ""
    for i, candidate in enumerate(top_overall, 1):
        candidates_text += f"\n{i}. {candidate.get('full_name', 'Unknown')} - Score: {candidate.get('overall_score', 0):.2f}"
        dimensions = candidate.get('dimensions', [])[:3]
        for dim in dimensions:
            candidates_text += f"\n   • {dim.get('name', 'Unknown')}: {dim.get('score', 0):.2f} - {dim.get('rationale', 'N/A')[:60]}..."
    
    # Format synthesis
    synthesis = data.get('synthesis', {})
    exec_summary = synthesis.get('executive_summary', 'No summary available') if synthesis else 'Analysis synthesis not available'
    
    output = f"""✅ Analysis Results Complete

🆔 Analysis ID: {analysis_id}
👔 Role: {data.get('role', 'N/A')}
📊 Candidates: {data.get('candidate_count', 0)} total ({data.get('applicant_count', 0)} applicants, {data.get('market_count', 0)} market)
⏰ Completed: {format_datetime(data.get('completed_at', 'N/A'))}
🎯 Confidence: {data.get('overall_confidence', 0):.2%}

🏆 TOP 5 CANDIDATES:
{candidates_text}

📝 EXECUTIVE SUMMARY:
{exec_summary[:500]}{'...' if len(exec_summary) > 500 else ''}

💡 Use 'get_detailed_candidate' to see full details for specific candidates.
💡 Use 'refine_analysis' to adjust search criteria and find more candidates.
"""
    
    return output

@mcp.tool()
async def list_talent_analyses(page: str = "1", page_size: str = "20", status_filter: str = "") -> str:
    """List all talent analyses with pagination and optional status filter"""
    logger.info("Listing talent analyses")
    
    # Validate and convert parameters
    try:
        page_int = int(page) if page.strip() else 1
        page_size_int = int(page_size) if page_size.strip() else 20
    except ValueError:
        return "❌ Error: page and page_size must be numbers"
    
    if page_size_int > 100:
        page_size_int = 100
    
    endpoint = f"/api/v1/ml-talent/analyses?page={page_int}&page_size={page_size_int}"
    if status_filter.strip():
        endpoint += f"&status={status_filter.strip()}"
    
    data, error = await make_api_request("GET", endpoint)
    if error:
        return error
    
    analyses = data.get('analyses', [])
    if not analyses:
        return "📋 No analyses found."
    
    output = f"""📊 Talent Analyses (Page {data.get('page')} of {data.get('pages')})
Total: {data.get('total')} analyses

"""
    
    for analysis in analyses:
        status_emoji = {
            "pending": "⏳",
            "processing": "⚙️",
            "completed": "✅",
            "failed": "❌"
        }.get(analysis.get('status', 'unknown'), "❓")
        
        output += f"""{status_emoji} {analysis.get('analysis_id')}
   Role: {analysis.get('role', 'N/A')}
   Status: {analysis.get('status', 'unknown')}
   Candidates: {analysis.get('candidate_count', 0)} ({analysis.get('applicant_count', 0)} applicants, {analysis.get('market_count', 0)} market)
   Created: {format_datetime(analysis.get('created_at', 'N/A'))}
   
"""
    
    return output

@mcp.tool()
async def refine_talent_analysis(analysis_id: str = "", add_skills: str = "", remove_skills: str = "", min_years: str = "") -> str:
    """Refine PDL market search query by adding/removing skills or adjusting experience requirements"""
    logger.info(f"Refining analysis {analysis_id}")
    
    if not analysis_id.strip():
        return "❌ Error: analysis_id is required"
    
    if not add_skills.strip() and not remove_skills.strip() and not min_years.strip():
        return """❌ Error: At least one refinement parameter is required

📝 Refinement Options:
- add_skills: Comma-separated skills to add (e.g., "scikit-learn,pytorch")
- remove_skills: Comma-separated skills to remove (e.g., "java,c++")
- min_years: Minimum years of experience (e.g., "3")

Example:
add_skills: "scikit-learn,pytorch"
remove_skills: "java"
min_years: "3"
"""
    
    refinement = {}
    
    if add_skills.strip():
        refinement['add_skills'] = [s.strip() for s in add_skills.split(',') if s.strip()]
    
    if remove_skills.strip():
        refinement['remove_skills'] = [s.strip() for s in remove_skills.split(',') if s.strip()]
    
    if min_years.strip():
        try:
            refinement['adjust_experience'] = {"min_years": int(min_years)}
        except ValueError:
            return "❌ Error: min_years must be a number"
    
    payload = {
        "analysis_id": analysis_id.strip(),
        "refinement_feedback": refinement
    }
    
    data, error = await make_api_request("POST", f"/api/v1/ml-talent/analysis/{analysis_id.strip()}/refine", data=payload)
    if error:
        return error
    
    return f"""✅ Analysis refined successfully!

🆔 New Analysis ID: {data.get('analysis_id')}
📊 Status: {data.get('status')}
💬 Message: {data.get('message', 'Refinement in progress')}

Use 'get_analysis_status' with the new analysis_id to check progress.
"""

@mcp.tool()
async def submit_analysis_feedback(analysis_id: str = "", candidate_ratings: str = "", comments: str = "") -> str:
    """Submit feedback on analysis results for future improvements - candidate_ratings format: candidate_id:rating,candidate_id:rating"""
    logger.info(f"Submitting feedback for analysis {analysis_id}")
    
    if not analysis_id.strip():
        return "❌ Error: analysis_id is required"
    
    feedback = {}
    
    if candidate_ratings.strip():
        try:
            ratings = {}
            for rating in candidate_ratings.split(','):
                if ':' in rating:
                    cid, rate = rating.split(':', 1)
                    ratings[cid.strip()] = rate.strip()
            if ratings:
                feedback['candidate_ratings'] = ratings
        except Exception as e:
            return f"❌ Error parsing candidate_ratings: {str(e)}\nFormat: candidate_id:rating,candidate_id:rating (e.g., 'candidate_001:great,candidate_002:good')"
    
    if comments.strip():
        feedback['comments'] = comments.strip()
    
    if not feedback:
        return """❌ Error: At least one feedback parameter is required

📝 Feedback Options:
- candidate_ratings: Format: candidate_id:rating,candidate_id:rating
  Ratings: great, good, fair, poor
  Example: "candidate_001:great,candidate_002:good"
- comments: Text feedback about the analysis

Example:
candidate_ratings: "candidate_001:great,candidate_002:good"
comments: "Great results, need more focus on Python experience"
"""
    
    data, error = await make_api_request("POST", f"/api/v1/ml-talent/analysis/{analysis_id.strip()}/feedback", data=feedback)
    if error:
        return error
    
    return f"""✅ Feedback submitted successfully!

Thank you for your feedback. It will be used to improve future analyses.
"""

@mcp.tool()
async def get_analysis_diagnostic(analysis_id: str = "") -> str:
    """Get the diagnostic report showing job competencies and attribute weights"""
    logger.info(f"Getting diagnostic for analysis {analysis_id}")
    
    if not analysis_id.strip():
        return "❌ Error: analysis_id is required"
    
    data, error = await make_api_request("GET", f"/api/v1/ml-talent/analysis/{analysis_id.strip()}")
    if error:
        return error
    
    diagnostic = data.get('diagnostic_report')
    if not diagnostic:
        return "⚠️ Diagnostic report not yet available or analysis failed."
    
    # Format ML competencies
    ml_comp = diagnostic.get('ml_competencies', {})
    tech_skills = ml_comp.get('technical_skills', {})
    required = tech_skills.get('required_skills', [])
    nice_to_have = tech_skills.get('nice_to_have_skills', [])
    
    exp_req = ml_comp.get('experience_requirements', {})
    min_years = exp_req.get('min_years', 'N/A')
    pref_years = exp_req.get('preferred_years', 'N/A')
    
    # Format attribute weights
    weights = diagnostic.get('attribute_weights', [])
    weights_text = ""
    for weight in weights[:10]:
        weights_text += f"\n   • {weight.get('name', 'Unknown')}: {weight.get('weight', 0):.2%}"
    
    return f"""📋 Diagnostic Report for Analysis {analysis_id}

🎯 REQUIRED SKILLS:
{', '.join(required) if required else 'None specified'}

💡 NICE-TO-HAVE SKILLS:
{', '.join(nice_to_have) if nice_to_have else 'None specified'}

⏱️ EXPERIENCE REQUIREMENTS:
   • Minimum: {min_years} years
   • Preferred: {pref_years} years

⚖️ ATTRIBUTE WEIGHTS:
{weights_text}

These weights determine how candidates are scored across different dimensions.
"""

@mcp.tool()
async def get_pdl_query(analysis_id: str = "") -> str:
    """Get the People Data Labs query used for market candidate search"""
    logger.info(f"Getting PDL query for analysis {analysis_id}")
    
    if not analysis_id.strip():
        return "❌ Error: analysis_id is required"
    
    data, error = await make_api_request("GET", f"/api/v1/ml-talent/analysis/{analysis_id.strip()}")
    if error:
        return error
    
    pdl_query = data.get('pdl_query')
    if not pdl_query:
        return "⚠️ PDL query not yet available or analysis didn't include market search."
    
    return f"""🔍 People Data Labs Search Query

🆔 Analysis ID: {analysis_id}

📋 Query Parameters:
   • Job Title: {pdl_query.get('job_title', 'N/A')}
   • Required Skills: {', '.join(pdl_query.get('required_skills', []))}
   • Optional Skills: {', '.join(pdl_query.get('optional_skills', []))}
   • Min Experience: {pdl_query.get('min_experience_years', 'N/A')} years
   • Location: {', '.join(pdl_query.get('location_country', []))}

This query was used to search the market for additional candidates.
Use 'refine_talent_analysis' to adjust these parameters.
"""

# === SERVER STARTUP ===
if __name__ == "__main__":
    logger.info("Starting Eliza Platform Talent Intelligence MCP server...")

    if not ELIZA_API_BASE:
        logger.warning("ELIZA_API_BASE not set, using default: http://localhost:5001")

    # Check authentication configuration
    if ELIZA_API_KEY:
        logger.info("✅ Using API key authentication (recommended)")
    elif ELIZA_EMAIL and ELIZA_PASSWORD:
        logger.warning("⚠️ Using legacy email/password authentication. Consider switching to API keys.")
        logger.warning("   Use the 'create_api_key' tool to generate an API key.")
    else:
        logger.error("❌ No authentication configured!")
        logger.error("   Set ELIZA_API_KEY (recommended) or ELIZA_EMAIL + ELIZA_PASSWORD")
        logger.error("   Authentication will fail until configured.")

    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


