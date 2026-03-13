#!/usr/bin/env python3
"""
Seed script for Email Templates and Section Library

Run this script to populate dummy data for development/testing:

    python scripts/seed_email_templates.py

Or from within the Docker container:

    docker-compose exec app python scripts/seed_email_templates.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import database
from src.models.email_templates import (
    EmailTemplate,
    EmailTemplateSection,
    EmailSectionLibrary,
)


# ============================================================================
# SECTION LIBRARY DATA
# ============================================================================

LIBRARY_SECTIONS = [
    # Opening / Greeting sections
    {
        "name": "Friendly First Name Greeting",
        "description": "Simple, friendly greeting using candidate's first name",
        "category": "opening",
        "section_type": "static",
        "content": "Hi {{candidate_first_name}},\n\nI hope this message finds you well!",
        "is_shared": True,
    },
    {
        "name": "Professional Opening",
        "description": "Formal opening for senior candidates",
        "category": "opening",
        "section_type": "static",
        "content": "Dear {{candidate_name}},\n\nI'm reaching out from {{company_name}} regarding an exciting opportunity that aligns with your background.",
        "is_shared": True,
    },
    {
        "name": "AI Personalized Introduction",
        "description": "AI generates a personalized opening based on candidate's current role",
        "category": "opening",
        "section_type": "ai_generated",
        "ai_prompt": "Write a warm, personalized opening paragraph. Reference their current role as {{job_title}} at {{candidate_company}} and mention how their {{years_experience}} years of experience caught our attention. Keep it brief and genuine - 2-3 sentences max.",
        "ai_tone": "professional",
        "ai_max_length": 150,
        "is_shared": True,
    },
    
    # Skills Match sections
    {
        "name": "Skills Highlight",
        "description": "Highlight the candidate's relevant skills",
        "category": "skills_match",
        "section_type": "static",
        "content": "Your expertise in {{skills}} particularly stood out to us, and we believe it would be a great match for what we're building.",
        "is_shared": True,
    },
    {
        "name": "AI Skills Connection",
        "description": "AI generates personalized skills match paragraph",
        "category": "skills_match",
        "section_type": "ai_generated",
        "ai_prompt": "Write a paragraph connecting the candidate's skills ({{skills}}) to the role. Explain why their specific combination of skills makes them uniquely qualified. Be specific about 2-3 skills and how they apply. Sound impressed but not over-the-top.",
        "ai_tone": "enthusiastic",
        "ai_max_length": 200,
        "is_shared": True,
    },
    {
        "name": "Experience Recognition",
        "description": "Acknowledge their experience level",
        "category": "skills_match",
        "section_type": "static",
        "content": "With {{years_experience}} years in the industry, you've clearly developed deep expertise that would be valuable to our team.",
        "is_shared": True,
    },
    
    # Value Proposition sections
    {
        "name": "Growth Opportunity",
        "description": "Emphasize career growth potential",
        "category": "value_proposition",
        "section_type": "static",
        "content": "This role offers significant growth potential, with opportunities to lead major initiatives and shape the direction of our {{job_title}} practice.",
        "is_shared": True,
    },
    {
        "name": "AI Why This Role",
        "description": "AI generates personalized value proposition",
        "category": "value_proposition",
        "section_type": "ai_generated",
        "ai_prompt": "Based on the candidate's background at {{candidate_company}} with skills in {{skills}}, write 2-3 sentences explaining why this specific opportunity at {{company_name}} would be a great next step in their career. Focus on growth, impact, and challenges they'd find interesting.",
        "ai_tone": "enthusiastic",
        "ai_max_length": 180,
        "is_shared": True,
    },
    
    # Company Pitch sections
    {
        "name": "Company Introduction",
        "description": "Brief introduction to the company",
        "category": "company_pitch",
        "section_type": "static",
        "content": "{{company_name}} is at the forefront of innovation in our industry. We're a team of passionate professionals dedicated to solving complex challenges and making a real impact.",
        "is_shared": True,
    },
    {
        "name": "Team Culture",
        "description": "Highlight team culture and environment",
        "category": "company_pitch",
        "section_type": "static",
        "content": "We pride ourselves on a collaborative, growth-oriented culture where your ideas are valued and you'll have the autonomy to make an impact from day one.",
        "is_shared": True,
    },
    
    # Call to Action sections
    {
        "name": "Quick Chat Request",
        "description": "Request for a brief call",
        "category": "call_to_action",
        "section_type": "static",
        "content": "Would you be open to a quick 15-minute chat to explore this further? I'd love to share more details about the role and learn about your career goals.",
        "is_shared": True,
    },
    {
        "name": "Meeting Request",
        "description": "Suggest scheduling a meeting",
        "category": "call_to_action",
        "section_type": "static",
        "content": "I'd welcome the opportunity to tell you more about this role. Are you available for a brief call this week or next? I'm happy to work around your schedule.",
        "is_shared": True,
    },
    {
        "name": "Soft CTA",
        "description": "Low-pressure call to action",
        "category": "call_to_action",
        "section_type": "static",
        "content": "If this sounds interesting, I'd be happy to share more details. Just reply to this email and we can set up a time to chat at your convenience.",
        "is_shared": True,
    },
    
    # Closing sections
    {
        "name": "Professional Signoff",
        "description": "Standard professional closing",
        "category": "closing",
        "section_type": "static",
        "content": "Thank you for considering this opportunity. I look forward to hearing from you.\n\nBest regards,\n{{your_name}}\n{{your_title}}\n{{company_name}}",
        "is_shared": True,
    },
    {
        "name": "Friendly Signoff",
        "description": "Warm, friendly closing",
        "category": "closing",
        "section_type": "static",
        "content": "Looking forward to connecting!\n\nBest,\n{{your_name}}",
        "is_shared": True,
    },
    {
        "name": "Casual Signoff",
        "description": "Casual, brief closing",
        "category": "closing",
        "section_type": "static",
        "content": "Cheers,\n{{your_name}}",
        "is_shared": True,
    },
]


# ============================================================================
# EMAIL TEMPLATES DATA
# ============================================================================

TEMPLATES = [
    {
        "name": "Initial Outreach - Professional",
        "description": "Professional first contact for senior candidates",
        "category": "market_outreach",
        "subject": "Opportunity at {{company_name}} - Your {{skills}} expertise",
        "subject_is_ai_generated": False,
        "is_default": True,
        "sections": [
            {
                "order": 0,
                "section_type": "static",
                "section_name": "Greeting",
                "content": "Dear {{candidate_name}},\n\nI came across your profile and was impressed by your background in {{skills}}.",
            },
            {
                "order": 1,
                "section_type": "ai_generated",
                "section_name": "Personalized Intro",
                "ai_prompt": "Write a personalized paragraph about why the candidate's experience as {{job_title}} at {{candidate_company}} makes them a great fit. Reference their {{years_experience}} years of experience. Be specific and genuine, 2-3 sentences.",
                "ai_tone": "professional",
                "ai_max_length": 180,
            },
            {
                "order": 2,
                "section_type": "static",
                "section_name": "Opportunity",
                "content": "We're currently looking for someone with exactly your skill set to join our team at {{company_name}}. This role offers the opportunity to work on cutting-edge projects while growing your career.",
            },
            {
                "order": 3,
                "section_type": "static",
                "section_name": "CTA",
                "content": "Would you be open to a quick 15-minute call this week to learn more?\n\nBest regards,\n{{your_name}}\n{{your_title}}",
            },
        ],
    },
    {
        "name": "Initial Outreach - Casual",
        "description": "Friendly, casual first contact for tech talent",
        "category": "market_outreach",
        "subject": "Quick question about your next move, {{candidate_first_name}}",
        "subject_is_ai_generated": False,
        "is_default": False,
        "sections": [
            {
                "order": 0,
                "section_type": "static",
                "section_name": "Greeting",
                "content": "Hey {{candidate_first_name}},\n\nHope you're doing well!",
            },
            {
                "order": 1,
                "section_type": "ai_generated",
                "section_name": "Hook",
                "ai_prompt": "Write a casual, friendly 1-2 sentence hook about their skills in {{skills}} and how it caught our attention. Make it sound like a genuine message from a real person, not a template.",
                "ai_tone": "casual",
                "ai_max_length": 100,
            },
            {
                "order": 2,
                "section_type": "static",
                "section_name": "The Ask",
                "content": "We're building something cool at {{company_name}} and I think you'd be a great fit. No pressure, but would you be down for a quick chat?\n\nCheers,\n{{your_name}}",
            },
        ],
    },
    {
        "name": "Applicant Follow-up",
        "description": "Follow up with candidates who applied",
        "category": "applicant_followup",
        "subject": "Thanks for applying to {{company_name}}!",
        "subject_is_ai_generated": False,
        "is_default": True,
        "sections": [
            {
                "order": 0,
                "section_type": "static",
                "section_name": "Thanks",
                "content": "Hi {{candidate_first_name}},\n\nThank you for your interest in joining {{company_name}}! We've reviewed your application and were impressed by your background.",
            },
            {
                "order": 1,
                "section_type": "ai_generated",
                "section_name": "Why You Stand Out",
                "ai_prompt": "Write 2 sentences about why their skills ({{skills}}) and experience at {{candidate_company}} make them stand out as a candidate. Be specific and encouraging.",
                "ai_tone": "enthusiastic",
                "ai_max_length": 120,
            },
            {
                "order": 2,
                "section_type": "static",
                "section_name": "Next Steps",
                "content": "We'd love to schedule a call to discuss the opportunity in more detail and learn more about your career goals. Are you available for a 30-minute conversation this week?\n\nLooking forward to connecting!\n\n{{your_name}}\n{{your_title}}",
            },
        ],
    },
    {
        "name": "Previous Candidate Re-engagement",
        "description": "Reach out to candidates from past searches",
        "category": "previous_candidate",
        "subject": "{{candidate_first_name}}, we have a new opportunity that might interest you",
        "subject_is_ai_generated": False,
        "is_default": True,
        "sections": [
            {
                "order": 0,
                "section_type": "static",
                "section_name": "Re-introduction",
                "content": "Hi {{candidate_first_name}},\n\nI hope this message finds you well! We connected previously about opportunities at {{company_name}}, and I wanted to reach out about an exciting new role that might be a great fit for you.",
            },
            {
                "order": 1,
                "section_type": "ai_generated",
                "section_name": "The New Opportunity",
                "ai_prompt": "Write 2-3 sentences about why this new opportunity would be particularly interesting for someone with their skills in {{skills}} and experience as {{job_title}}. Emphasize what's different or exciting about this role compared to typical opportunities.",
                "ai_tone": "professional",
                "ai_max_length": 150,
            },
            {
                "order": 2,
                "section_type": "static",
                "section_name": "CTA",
                "content": "Would you be interested in learning more? I'd love to catch up and hear about what you've been up to.\n\nBest,\n{{your_name}}",
            },
        ],
    },
    {
        "name": "AI-Powered Personalized Outreach",
        "description": "Fully AI-generated personalized email",
        "category": "custom",
        "subject": "",
        "subject_is_ai_generated": True,
        "subject_ai_prompt": "Write a compelling subject line for a recruiting email to {{candidate_first_name}} who works at {{candidate_company}}. Make it personal and intriguing, not salesy. Maximum 8 words.",
        "is_default": False,
        "sections": [
            {
                "order": 0,
                "section_type": "ai_generated",
                "section_name": "Complete Email",
                "ai_prompt": "Write a complete recruiting email to {{candidate_name}} who is a {{job_title}} at {{candidate_company}} with {{years_experience}} years of experience and skills in {{skills}}. They are located in {{location}}.\n\nThe email should:\n1. Open with a personalized, genuine greeting\n2. Reference something specific about their background\n3. Explain why we're reaching out\n4. Briefly mention what {{company_name}} offers\n5. End with a soft call-to-action\n\nKeep the tone professional but warm. Make it feel like a personal message, not a template. Sign off from {{your_name}}, {{your_title}}.",
                "ai_tone": "professional",
                "ai_max_length": 400,
            },
        ],
    },
    {
        "name": "Interview Invitation",
        "description": "Invite candidate to interview",
        "category": "interview_invite",
        "subject": "Interview Invitation - {{company_name}}",
        "subject_is_ai_generated": False,
        "is_default": False,
        "sections": [
            {
                "order": 0,
                "section_type": "static",
                "section_name": "Great News",
                "content": "Hi {{candidate_first_name}},\n\nGreat news! After reviewing your application, we'd like to invite you to interview for the position at {{company_name}}.",
            },
            {
                "order": 1,
                "section_type": "static",
                "section_name": "Details",
                "content": "The interview will be approximately 45 minutes and will give you the opportunity to meet with members of our team and learn more about the role.\n\nPlease let me know your availability over the next week, and I'll send over a calendar invite.",
            },
            {
                "order": 2,
                "section_type": "static",
                "section_name": "Closing",
                "content": "Looking forward to speaking with you!\n\nBest regards,\n{{your_name}}\n{{your_title}}\n{{company_name}}",
            },
        ],
    },
]


def seed_data(customer_id: str = "eliza"):
    """Seed email templates and section library for a customer."""
    
    # Initialize database if needed
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        print(f"\n🌱 Seeding email templates data for customer: {customer_id}\n")
        
        # Check if data already exists
        existing_templates = db.query(EmailTemplate).filter(
            EmailTemplate.customer_id == customer_id
        ).count()
        
        existing_sections = db.query(EmailSectionLibrary).filter(
            EmailSectionLibrary.customer_id == customer_id
        ).count()
        
        if existing_templates > 0 or existing_sections > 0:
            print(f"⚠️  Found existing data: {existing_templates} templates, {existing_sections} library sections")
            response = input("Do you want to delete and recreate? (y/N): ")
            if response.lower() != 'y':
                print("❌ Aborted.")
                return
            
            # Delete existing data
            db.query(EmailTemplateSection).filter(
                EmailTemplateSection.template_id.in_(
                    db.query(EmailTemplate.id).filter(EmailTemplate.customer_id == customer_id)
                )
            ).delete(synchronize_session=False)
            db.query(EmailTemplate).filter(EmailTemplate.customer_id == customer_id).delete()
            db.query(EmailSectionLibrary).filter(EmailSectionLibrary.customer_id == customer_id).delete()
            db.commit()
            print("🗑️  Deleted existing data")
        
        # Seed Section Library
        print("\n📚 Creating Section Library entries...")
        for section_data in LIBRARY_SECTIONS:
            section = EmailSectionLibrary(
                customer_id=customer_id,
                name=section_data["name"],
                description=section_data.get("description"),
                category=section_data.get("category"),
                section_type=section_data.get("section_type", "static"),
                content=section_data.get("content"),
                ai_prompt=section_data.get("ai_prompt"),
                ai_tone=section_data.get("ai_tone"),
                ai_max_length=section_data.get("ai_max_length"),
                is_shared=section_data.get("is_shared", True),
                use_count=0,
            )
            db.add(section)
            print(f"   ✓ {section_data['name']}")
        
        db.commit()
        print(f"\n   Created {len(LIBRARY_SECTIONS)} library sections")
        
        # Seed Email Templates
        print("\n📧 Creating Email Templates...")
        for template_data in TEMPLATES:
            template = EmailTemplate(
                customer_id=customer_id,
                name=template_data["name"],
                description=template_data.get("description"),
                category=template_data["category"],
                subject=template_data["subject"],
                subject_is_ai_generated=template_data.get("subject_is_ai_generated", False),
                subject_ai_prompt=template_data.get("subject_ai_prompt"),
                is_default=template_data.get("is_default", False),
                use_count=0,
            )
            db.add(template)
            db.flush()  # Get template ID
            
            # Add sections
            for section_data in template_data.get("sections", []):
                section = EmailTemplateSection(
                    template_id=template.id,
                    section_order=section_data["order"],
                    section_type=section_data.get("section_type", "static"),
                    section_name=section_data.get("section_name"),
                    content=section_data.get("content"),
                    ai_prompt=section_data.get("ai_prompt"),
                    ai_tone=section_data.get("ai_tone"),
                    ai_max_length=section_data.get("ai_max_length"),
                )
                db.add(section)
            
            section_count = len(template_data.get("sections", []))
            ai_count = sum(1 for s in template_data.get("sections", []) if s.get("section_type") == "ai_generated")
            default_marker = " ⭐ DEFAULT" if template_data.get("is_default") else ""
            print(f"   ✓ {template_data['name']} ({section_count} sections, {ai_count} AI){default_marker}")
        
        db.commit()
        print(f"\n   Created {len(TEMPLATES)} templates")
        
        print("\n✅ Seed complete!\n")
        print("You can now view the data at: http://localhost:3000/talent/email-templates")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed email templates and section library")
    parser.add_argument(
        "--customer-id",
        default="eliza",
        help="Customer ID to seed data for (default: eliza)"
    )
    
    args = parser.parse_args()
    seed_data(args.customer_id)
