"""
Email Generation Service

Generates personalized email content using AI for candidate outreach.
Supports section-based templates with both static and AI-generated content.
"""

import re
import hashlib
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import structlog
import openai

from src.models.email_templates import (
    EmailTemplate, 
    EmailTemplateSection, 
    GeneratedEmail,
    PDLQueryCache,
    CustomerSettings,
    TemplateSectionType
)
from src.models.candidate import CandidateAnalysisScore
from src.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class EmailGenerationService:
    """
    Service for generating personalized emails using templates and AI.
    """
    
    def __init__(self, db: Session, customer_id: str):
        self.db = db
        self.customer_id = customer_id
        self._settings = None
    
    @property
    def customer_settings(self) -> Optional[CustomerSettings]:
        """Get customer-specific settings, lazy loaded."""
        if self._settings is None:
            self._settings = self.db.query(CustomerSettings).filter(
                CustomerSettings.customer_id == self.customer_id
            ).first()
        return self._settings
    
    def get_greenhouse_maildrop(self) -> Optional[str]:
        """Get the Greenhouse maildrop address for this customer."""
        if self.customer_settings:
            return self.customer_settings.greenhouse_maildrop_address
        # Default for Caylent
        return "maildrop@lily.greenhouse.io"
    
    def get_default_template(self, category: Optional[str] = None) -> Optional[EmailTemplate]:
        """
        Get the default email template for a category.
        
        Args:
            category: Template category (e.g., 'market_outreach', 'applicant_followup')
                     If None, returns any default template
        
        Returns:
            The default EmailTemplate or None if not found
        """
        query = self.db.query(EmailTemplate).filter(
            EmailTemplate.customer_id == self.customer_id,
            EmailTemplate.is_default == True,
            EmailTemplate.is_active == True
        )
        
        if category:
            query = query.filter(EmailTemplate.category == category)
        
        return query.first()
    
    async def generate_email_with_default_template(
        self,
        candidate_data: Dict[str, Any],
        category: Optional[str] = None,
        talent_analysis_id: Optional[str] = None,
        candidate_db_id: Optional[int] = None
    ) -> Optional[GeneratedEmail]:
        """
        Generate an email using the default template for a category.
        
        Args:
            candidate_data: Candidate information for personalization
            category: Template category to use (defaults to any default template)
            talent_analysis_id: Optional analysis ID for tracking
            candidate_db_id: Optional database ID of candidate
            
        Returns:
            GeneratedEmail if a default template exists, None otherwise
        """
        template = self.get_default_template(category)
        
        if not template:
            logger.warning(
                "no_default_template_found",
                customer_id=self.customer_id,
                category=category
            )
            return None
        
        return await self.generate_email_for_candidate(
            template_id=template.id,
            candidate_data=candidate_data,
            talent_analysis_id=talent_analysis_id,
            force_regenerate=False,
            candidate_db_id=candidate_db_id
        )
    
    async def generate_email_for_candidate(
        self,
        template_id: int,
        candidate_data: Dict[str, Any],
        talent_analysis_id: Optional[str] = None,
        force_regenerate: bool = False,
        candidate_db_id: Optional[int] = None
    ) -> GeneratedEmail:
        """
        Generate a personalized email for a candidate using a template.
        
        Args:
            template_id: ID of the email template to use
            candidate_data: Candidate information for personalization
            talent_analysis_id: Optional analysis ID for tracking
            force_regenerate: If True, regenerate even if cached
            candidate_db_id: Optional database ID of candidate (for new architecture)
            
        Returns:
            GeneratedEmail with the generated content
        """
        candidate_id = candidate_data.get('id') or candidate_data.get('pdl_id')
        
        # Check for existing generated email
        if not force_regenerate:
            existing = self.db.query(GeneratedEmail).filter(
                GeneratedEmail.customer_id == self.customer_id,
                GeneratedEmail.template_id == template_id,
                GeneratedEmail.candidate_id == candidate_id
            ).first()
            
            if existing:
                logger.info(
                    "using_cached_generated_email",
                    candidate_id=candidate_id,
                    template_id=template_id
                )
                return existing
        
        # Get template
        template = self.db.query(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.customer_id == self.customer_id
        ).first()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Generate subject
        if template.subject_is_ai_generated and template.subject_ai_prompt:
            subject = await self._generate_ai_content(
                template.subject_ai_prompt,
                candidate_data,
                max_length=100,
                tone="professional"
            )
        else:
            subject = self._substitute_variables(template.subject, candidate_data)
        
        # Generate body from sections
        body_parts = []
        for section in sorted(template.sections, key=lambda s: s.section_order):
            if section.section_type == TemplateSectionType.STATIC.value:
                content = self._substitute_variables(section.content or "", candidate_data)
            else:  # AI generated
                content = await self._generate_ai_content(
                    section.ai_prompt or "",
                    candidate_data,
                    context_fields=section.ai_context_fields,
                    max_length=section.ai_max_length or 200,
                    tone=section.ai_tone or "professional"
                )
            body_parts.append(content)
        
        body = "\n\n".join(body_parts)
        
        # Add signature if configured
        if self.customer_settings and self.customer_settings.email_signature:
            body += f"\n\n{self.customer_settings.email_signature}"
        
        # Create or update generated email record
        generated_email = GeneratedEmail(
            customer_id=self.customer_id,
            template_id=template_id,
            candidate_id=candidate_id,
            talent_analysis_id=talent_analysis_id,
            subject=subject,
            body=body,
            original_subject=subject,
            original_body=body,
            generation_context=candidate_data,
            generation_model=self.customer_settings.ai_model_preference if self.customer_settings else "gpt-4",
            status="draft"
        )
        
        self.db.add(generated_email)
        self.db.commit()
        self.db.refresh(generated_email)
        
        # Update template usage
        template.use_count += 1
        template.last_used_at = datetime.now(timezone.utc)
        self.db.commit()
        
        logger.info(
            "email_generated",
            candidate_id=candidate_id,
            template_id=template_id,
            generated_email_id=generated_email.id
        )
        
        # Also save to candidate_analysis_scores if we have both IDs (new architecture)
        if candidate_db_id and talent_analysis_id:
            try:
                score = self.db.query(CandidateAnalysisScore).filter(
                    CandidateAnalysisScore.candidate_id == candidate_db_id,
                    CandidateAnalysisScore.analysis_id == talent_analysis_id
                ).first()
                
                if score:
                    score.email_template_id = template_id
                    score.generated_email_subject = subject
                    score.generated_email_body = body
                    score.email_generated_at = datetime.now(timezone.utc)
                    self.db.commit()
                    
                    logger.info(
                        "email_saved_to_candidate_analysis_score",
                        candidate_db_id=candidate_db_id,
                        analysis_id=talent_analysis_id,
                        template_id=template_id
                    )
            except Exception as e:
                logger.warning(
                    "failed_to_save_email_to_candidate_analysis_score",
                    candidate_db_id=candidate_db_id,
                    analysis_id=talent_analysis_id,
                    error=str(e)
                )
        
        return generated_email
    
    def _substitute_variables(self, text: str, data: Dict[str, Any]) -> str:
        """
        Replace template variables with actual values.
        
        Supported variables:
        - {{candidate_name}}, {{candidate_first_name}} - Candidate's name
        - {{skill}}, {{skills}} - Candidate's skills
        - {{company_name}} - YOUR company (the hiring company)
        - {{candidate_company}}, {{current_company}} - Candidate's current employer
        - {{role_title}}, {{job_title}} - Candidate's current job title
        - {{current_date}} - Today's date
        - {{your_name}}, {{your_title}} - Sender's name and title
        - {{location}} - Candidate's location
        """
        if not text:
            return ""
        
        # Get hiring company name from customer record
        hiring_company_name = self._get_hiring_company_name()
        
        # Build substitution map
        substitutions = {
            # Candidate info
            'candidate_name': data.get('full_name') or data.get('name', ''),
            'candidate_first_name': data.get('first_name') or (data.get('name', '').split()[0] if data.get('name') else ''),
            'skill': ', '.join(data.get('skills', [])[:3]) if data.get('skills') else '',
            'skills': ', '.join(data.get('skills', [])[:5]) if data.get('skills') else '',
            # Candidate's current company
            'candidate_company': data.get('job_company_name') or data.get('current_company', ''),
            'current_company': data.get('job_company_name') or data.get('current_company', ''),
            # YOUR company (the hiring company)
            'company_name': hiring_company_name,
            # Candidate's job title
            'role_title': data.get('job_title') or data.get('role_title', ''),
            'job_title': data.get('job_title') or data.get('current_title', ''),
            # Other
            'current_date': datetime.now().strftime('%B %d, %Y'),
            'location': data.get('location_name') or data.get('location', ''),
            'years_experience': str(data.get('inferred_years_experience', '')),
        }
        
        # Add sender info from settings
        if self.customer_settings:
            substitutions['your_name'] = self.customer_settings.sender_name or '[Your Name]'
            substitutions['your_title'] = self.customer_settings.sender_title or '[Your Title]'
        else:
            substitutions['your_name'] = '[Your Name]'
            substitutions['your_title'] = '[Your Title]'
        
        # Perform substitutions
        result = text
        for var, value in substitutions.items():
            pattern = r'\{\{' + var + r'\}\}'
            result = re.sub(pattern, str(value), result, flags=re.IGNORECASE)
        
        return result
    
    def _get_hiring_company_name(self) -> str:
        """Get the hiring company name from the customer record."""
        from src.models.customer import Customer
        
        customer = self.db.query(Customer).filter(
            Customer.customer_id == self.customer_id
        ).first()
        
        if customer:
            return customer.display_name or customer.name or self.customer_id
        
        # Fallback to customer_id if no record found
        return self.customer_id
    
    async def _generate_ai_content(
        self,
        prompt: str,
        candidate_data: Dict[str, Any],
        context_fields: Optional[List[str]] = None,
        max_length: int = 200,
        tone: str = "professional"
    ) -> str:
        """
        Generate AI content for an email section.
        
        Args:
            prompt: The generation prompt
            candidate_data: Full candidate data
            context_fields: Specific fields to include in context
            max_length: Maximum characters for response
            tone: Tone of the content (professional, casual, enthusiastic)
            
        Returns:
            Generated content string
        """
        # Build context from candidate data
        if context_fields:
            context = {k: candidate_data.get(k) for k in context_fields if k in candidate_data}
        else:
            # Default context
            context = {
                'name': candidate_data.get('full_name') or candidate_data.get('name'),
                'current_title': candidate_data.get('job_title'),
                'current_company': candidate_data.get('job_company_name'),
                'skills': candidate_data.get('skills', [])[:5],
                'years_experience': candidate_data.get('inferred_years_experience'),
                'location': candidate_data.get('location_name'),
            }
        
        # First substitute any variables in the prompt
        prompt = self._substitute_variables(prompt, candidate_data)
        
        system_prompt = f"""You are an expert recruiter writing personalized outreach emails.
Your tone should be {tone}.
Keep the content concise ({max_length} characters max).
Make it feel personal and genuine, not templated.
Do not include greetings like "Hi [Name]" - those are handled separately.
Do not include sign-offs - those are handled separately.
Just write the content for this specific section."""
        
        user_prompt = f"""Generate this email section:
{prompt}

Candidate Context:
{json.dumps(context, indent=2, default=str)}

Remember: Keep it under {max_length} characters, {tone} tone, and make it personal."""
        
        try:
            # Use OpenAI API
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            
            response = await client.chat.completions.create(
                model=self.customer_settings.ai_model_preference if self.customer_settings else "gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_length // 2,  # Rough char to token conversion
                temperature=0.7
            )
            
            content = response.choices[0].message.content.strip()
            
            logger.info(
                "ai_content_generated",
                prompt_length=len(prompt),
                response_length=len(content)
            )
            
            return content
            
        except Exception as e:
            logger.error(
                "ai_generation_failed",
                error=str(e),
                prompt=prompt[:100]
            )
            # Return empty string on failure - static fallback
            return ""
    
    def update_generated_email(
        self,
        generated_email_id: int,
        subject: Optional[str] = None,
        body: Optional[str] = None
    ) -> GeneratedEmail:
        """
        Update a generated email with manual edits.
        
        Args:
            generated_email_id: ID of the generated email
            subject: New subject (optional)
            body: New body (optional)
            
        Returns:
            Updated GeneratedEmail
        """
        email = self.db.query(GeneratedEmail).filter(
            GeneratedEmail.id == generated_email_id,
            GeneratedEmail.customer_id == self.customer_id
        ).first()
        
        if not email:
            raise ValueError(f"Generated email {generated_email_id} not found")
        
        if subject is not None:
            email.subject = subject
            email.is_edited = True
        
        if body is not None:
            email.body = body
            email.is_edited = True
        
        self.db.commit()
        self.db.refresh(email)
        
        return email


class PDLCacheService:
    """
    Service for caching PDL query results to reduce API costs.
    """
    
    def __init__(self, db: Session, customer_id: str):
        self.db = db
        self.customer_id = customer_id
        self._settings = None
    
    @property
    def cache_ttl_days(self) -> int:
        """Get cache TTL from customer settings."""
        if self._settings is None:
            self._settings = self.db.query(CustomerSettings).filter(
                CustomerSettings.customer_id == self.customer_id
            ).first()
        
        if self._settings:
            return self._settings.pdl_cache_ttl_days
        return 30  # Default 30 days
    
    def _hash_query(self, query_params: Dict[str, Any]) -> str:
        """Generate a consistent hash for query parameters."""
        # Normalize the query by sorting keys
        normalized = json.dumps(query_params, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def get_cached_results(
        self,
        query_params: Dict[str, Any],
        query_type: str
    ) -> Optional[List[str]]:
        """
        Check if we have valid cached results for this query.
        
        Args:
            query_params: The query parameters
            query_type: Type of query (linkedin_enrichment, search, lookalike)
            
        Returns:
            List of PDL IDs if cached, None otherwise
        """
        query_hash = self._hash_query(query_params)
        
        cache_entry = self.db.query(PDLQueryCache).filter(
            PDLQueryCache.customer_id == self.customer_id,
            PDLQueryCache.query_hash == query_hash,
            PDLQueryCache.query_type == query_type,
            PDLQueryCache.expires_at > datetime.now(timezone.utc)
        ).first()
        
        if cache_entry:
            # Update hit count
            cache_entry.cache_hit_count += 1
            cache_entry.last_hit_at = datetime.now(timezone.utc)
            self.db.commit()
            
            logger.info(
                "pdl_cache_hit",
                query_type=query_type,
                result_count=cache_entry.result_count,
                hit_count=cache_entry.cache_hit_count
            )
            
            return cache_entry.result_pdl_ids
        
        return None
    
    def cache_results(
        self,
        query_params: Dict[str, Any],
        query_type: str,
        pdl_ids: List[str]
    ) -> PDLQueryCache:
        """
        Cache query results.
        
        Args:
            query_params: The query parameters
            query_type: Type of query
            pdl_ids: List of PDL person IDs returned
            
        Returns:
            The cache entry
        """
        query_hash = self._hash_query(query_params)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.cache_ttl_days)
        
        # Check for existing entry
        existing = self.db.query(PDLQueryCache).filter(
            PDLQueryCache.customer_id == self.customer_id,
            PDLQueryCache.query_hash == query_hash,
            PDLQueryCache.query_type == query_type
        ).first()
        
        if existing:
            # Update existing entry
            existing.result_pdl_ids = pdl_ids
            existing.result_count = len(pdl_ids)
            existing.expires_at = expires_at
            self.db.commit()
            self.db.refresh(existing)
            
            logger.info(
                "pdl_cache_updated",
                query_type=query_type,
                result_count=len(pdl_ids)
            )
            
            return existing
        
        # Create new entry
        cache_entry = PDLQueryCache(
            customer_id=self.customer_id,
            query_hash=query_hash,
            query_params=query_params,
            query_type=query_type,
            result_count=len(pdl_ids),
            result_pdl_ids=pdl_ids,
            expires_at=expires_at
        )
        
        self.db.add(cache_entry)
        self.db.commit()
        self.db.refresh(cache_entry)
        
        logger.info(
            "pdl_cache_created",
            query_type=query_type,
            result_count=len(pdl_ids),
            expires_at=expires_at.isoformat()
        )
        
        return cache_entry
    
    def invalidate_cache(self, query_type: Optional[str] = None) -> int:
        """
        Invalidate cache entries.
        
        Args:
            query_type: If provided, only invalidate this type
            
        Returns:
            Number of entries invalidated
        """
        query = self.db.query(PDLQueryCache).filter(
            PDLQueryCache.customer_id == self.customer_id
        )
        
        if query_type:
            query = query.filter(PDLQueryCache.query_type == query_type)
        
        count = query.delete()
        self.db.commit()
        
        logger.info(
            "pdl_cache_invalidated",
            query_type=query_type,
            count=count
        )
        
        return count
    
    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
            Number of entries removed
        """
        count = self.db.query(PDLQueryCache).filter(
            PDLQueryCache.expires_at < datetime.now(timezone.utc)
        ).delete()
        
        self.db.commit()
        
        logger.info("pdl_cache_cleanup", removed_count=count)
        
        return count

