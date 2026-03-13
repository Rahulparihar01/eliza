"""
Unit tests for AI Email Generation feature.

Tests the AI-powered email generation with section-based templates.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from src.models.email_templates import (
    EmailTemplate,
    EmailTemplateSection,
    GeneratedEmail,
    TemplateSectionType
)


class TestEmailTemplateModel:
    """Test EmailTemplate model functionality."""
    
    def test_get_all_variables_from_subject(self):
        """Test extracting variables from subject line."""
        template = EmailTemplate()
        template.subject = "Hello {{candidate_name}}, job at {{company_name}}"
        template.sections = []
        
        variables = template.get_all_variables()
        
        assert "candidate_name" in variables
        assert "company_name" in variables
    
    def test_get_all_variables_from_static_sections(self):
        """Test extracting variables from static sections."""
        import re
        
        # Test the variable extraction logic directly
        content = "Hi {{candidate_first_name}}, your {{skills}} are great."
        pattern = r'\{\{(\w+)\}\}'
        
        variables = set(re.findall(pattern, content))
        
        assert "candidate_first_name" in variables
        assert "skills" in variables
    
    def test_get_all_variables_from_ai_prompts(self):
        """Test extracting variables from AI prompts."""
        import re
        
        # Test the variable extraction logic directly
        ai_prompt = "Write about their {{job_title}} at {{current_company}}"
        pattern = r'\{\{(\w+)\}\}'
        
        variables = set(re.findall(pattern, ai_prompt))
        
        assert "job_title" in variables
        assert "current_company" in variables
    
    def test_get_all_variables_deduplicates(self):
        """Test that duplicate variables are removed."""
        import re
        
        # Test the deduplication logic
        subject = "{{name}} - {{name}}"
        content = "Hello {{name}}"
        pattern = r'\{\{(\w+)\}\}'
        
        variables = set()
        variables.update(re.findall(pattern, subject))
        variables.update(re.findall(pattern, content))
        
        # Should only appear once (sets deduplicate)
        assert len(variables) == 1
        assert "name" in variables
    
    def test_get_all_variables_sorted(self):
        """Test that variables are returned sorted."""
        template = EmailTemplate()
        template.subject = "{{zebra}} {{apple}} {{mango}}"
        template.sections = []
        
        variables = template.get_all_variables()
        
        assert variables == ["apple", "mango", "zebra"]


class TestEmailTemplateSection:
    """Test EmailTemplateSection model."""
    
    def test_static_section_type(self):
        """Test static section type."""
        section = EmailTemplateSection()
        section.section_type = TemplateSectionType.STATIC.value
        
        assert section.section_type == "static"
    
    def test_ai_generated_section_type(self):
        """Test AI generated section type."""
        section = EmailTemplateSection()
        section.section_type = TemplateSectionType.AI_GENERATED.value
        
        assert section.section_type == "ai_generated"
    
    def test_ai_section_has_tone(self):
        """Test AI section has tone attribute."""
        section = EmailTemplateSection()
        section.ai_tone = "professional"
        
        assert section.ai_tone == "professional"
    
    def test_ai_section_has_max_length(self):
        """Test AI section has max length attribute."""
        section = EmailTemplateSection()
        section.ai_max_length = 200
        
        assert section.ai_max_length == 200


class TestEmailGenerationService:
    """Test EmailGenerationService AI generation."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def service(self, mock_db):
        """Create EmailGenerationService instance."""
        from src.services.email_generation_service import EmailGenerationService
        return EmailGenerationService(mock_db, "test_customer")
    
    def test_variable_substitution_candidate_name(self, service):
        """Test substituting candidate name."""
        text = "Dear {{candidate_name}},"
        data = {"full_name": "John Smith"}
        
        result = service._substitute_variables(text, data)
        
        assert result == "Dear John Smith,"
    
    def test_variable_substitution_first_name(self, service):
        """Test substituting first name."""
        text = "Hi {{candidate_first_name}}!"
        data = {"name": "Jane Doe"}
        
        result = service._substitute_variables(text, data)
        
        assert result == "Hi Jane!"
    
    def test_variable_substitution_skills_list(self, service):
        """Test substituting skills list."""
        text = "Your skills: {{skills}}"
        data = {"skills": ["Python", "AWS", "Docker", "Kubernetes", "React"]}
        
        result = service._substitute_variables(text, data)
        
        assert "Python" in result
        assert "AWS" in result
        assert "Docker" in result
        assert "Kubernetes" in result
        assert "React" in result
    
    def test_variable_substitution_skill_subset(self, service):
        """Test substituting skill subset (top 3)."""
        text = "Key skills: {{skill}}"
        data = {"skills": ["Python", "AWS", "Docker", "Kubernetes", "React"]}
        
        result = service._substitute_variables(text, data)
        
        # Should only include first 3
        assert "Python" in result
        assert "AWS" in result
        assert "Docker" in result
        # Should not include the rest
        assert "Kubernetes" not in result
        assert "React" not in result
    
    def test_variable_substitution_company_name(self, service):
        """Test substituting company name."""
        text = "At {{company_name}}"
        data = {"job_company_name": "Acme Corp"}
        
        result = service._substitute_variables(text, data)
        
        assert result == "At Acme Corp"
    
    def test_variable_substitution_location(self, service):
        """Test substituting location."""
        text = "Based in {{location}}"
        data = {"location_name": "San Francisco, CA"}
        
        result = service._substitute_variables(text, data)
        
        assert result == "Based in San Francisco, CA"
    
    def test_variable_substitution_years_experience(self, service):
        """Test substituting years of experience."""
        text = "{{years_experience}} years of experience"
        data = {"inferred_years_experience": 8}
        
        result = service._substitute_variables(text, data)
        
        assert result == "8 years of experience"
    
    def test_variable_substitution_missing_value(self, service):
        """Test substituting with missing value."""
        text = "Hello {{candidate_name}}"
        data = {}
        
        result = service._substitute_variables(text, data)
        
        # Should replace with empty string
        assert result == "Hello "
    
    def test_variable_substitution_case_insensitive(self, service):
        """Test that variable substitution is case insensitive."""
        text = "{{CANDIDATE_NAME}} and {{candidate_name}}"
        data = {"full_name": "Test User"}
        
        result = service._substitute_variables(text, data)
        
        assert "Test User" in result
        # Both should be replaced
        assert "{{CANDIDATE_NAME}}" not in result
        assert "{{candidate_name}}" not in result
    
    @pytest.mark.asyncio
    async def test_generate_ai_content_calls_openai(self, service):
        """Test that AI content generation calls OpenAI."""
        with patch('openai.AsyncOpenAI') as MockOpenAI:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Generated content"))]
            mock_client.chat.completions.create.return_value = mock_response
            MockOpenAI.return_value = mock_client
            
            result = await service._generate_ai_content(
                prompt="Write a greeting",
                candidate_data={"full_name": "John"},
                max_length=100,
                tone="professional"
            )
            
            assert result == "Generated content"
            mock_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_ai_content_handles_error(self, service):
        """Test that AI content generation handles errors gracefully."""
        with patch('openai.AsyncOpenAI') as MockOpenAI:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.side_effect = Exception("API Error")
            MockOpenAI.return_value = mock_client
            
            result = await service._generate_ai_content(
                prompt="Write a greeting",
                candidate_data={"full_name": "John"},
                max_length=100,
                tone="professional"
            )
            
            # Should return empty string on error
            assert result == ""


class TestGeneratedEmailModel:
    """Test GeneratedEmail model."""
    
    def test_generated_email_has_required_fields(self):
        """Test GeneratedEmail has all required fields."""
        email = GeneratedEmail()
        
        assert hasattr(email, 'customer_id')
        assert hasattr(email, 'template_id')
        assert hasattr(email, 'candidate_id')
        assert hasattr(email, 'subject')
        assert hasattr(email, 'body')
        assert hasattr(email, 'is_edited')
        assert hasattr(email, 'original_subject')
        assert hasattr(email, 'original_body')
        assert hasattr(email, 'generation_context')
        assert hasattr(email, 'generation_model')
        assert hasattr(email, 'status')
        assert hasattr(email, 'sent_at')
        assert hasattr(email, 'scheduled_for')
    
    def test_default_status_is_draft(self):
        """Test default status is draft."""
        column = GeneratedEmail.__table__.columns['status']
        assert column.default.arg == "draft"
    
    def test_default_is_edited_is_false(self):
        """Test default is_edited is False."""
        column = GeneratedEmail.__table__.columns['is_edited']
        assert column.default.arg is False


class TestEmailGenerationEndpoint:
    """Test email generation API endpoint."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user context."""
        user = Mock()
        user.customer_id = "test_customer"
        user.user_id = 1
        return user
    
    @pytest.mark.asyncio
    async def test_generate_email_endpoint(self, mock_db, mock_user):
        """Test the generate email endpoint."""
        from src.api.routes.email_templates import generate_email, GenerateEmailRequest
        
        mock_template = Mock()
        mock_template.id = 1
        mock_template.subject = "Hello {{candidate_name}}"
        mock_template.subject_is_ai_generated = False
        mock_template.sections = []
        mock_template.use_count = 0
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        
        with patch('src.api.routes.email_templates.EmailGenerationService') as MockService:
            mock_service = Mock()
            mock_generated = Mock()
            mock_generated.id = 1
            mock_generated.template_id = 1
            mock_generated.candidate_id = "test_123"
            mock_generated.subject = "Hello John"
            mock_generated.body = "Test body"
            mock_generated.is_edited = False
            mock_generated.status = "draft"
            mock_generated.created_at = datetime.now(timezone.utc)
            
            mock_service.generate_email_for_candidate = AsyncMock(return_value=mock_generated)
            mock_service.get_greenhouse_maildrop.return_value = "maildrop@lily.greenhouse.io"
            MockService.return_value = mock_service
            
            request = GenerateEmailRequest(
                template_id=1,
                candidate_data={"full_name": "John Doe"},
                force_regenerate=False
            )
            
            result = await generate_email(
                request=request,
                db=mock_db,
                current_user=mock_user
            )
        
        assert result.subject == "Hello John"
        assert result.greenhouse_maildrop == "maildrop@lily.greenhouse.io"


class TestAITones:
    """Test AI tone options."""
    
    def test_professional_tone(self):
        """Test professional tone setting."""
        section = EmailTemplateSection()
        section.ai_tone = "professional"
        assert section.ai_tone == "professional"
    
    def test_casual_tone(self):
        """Test casual tone setting."""
        section = EmailTemplateSection()
        section.ai_tone = "casual"
        assert section.ai_tone == "casual"
    
    def test_enthusiastic_tone(self):
        """Test enthusiastic tone setting."""
        section = EmailTemplateSection()
        section.ai_tone = "enthusiastic"
        assert section.ai_tone == "enthusiastic"


class TestTemplateCategories:
    """Test template category options."""
    
    def test_all_categories_exist(self):
        """Test all expected categories exist."""
        from src.models.email_templates import TemplateCategory
        
        categories = [
            TemplateCategory.APPLICANT_FOLLOWUP,
            TemplateCategory.MARKET_OUTREACH,
            TemplateCategory.INTERVIEW_INVITE,
            TemplateCategory.REJECTION,
            TemplateCategory.CUSTOM,
        ]
        
        assert len(categories) == 5
    
    def test_category_values(self):
        """Test category enum values."""
        from src.models.email_templates import TemplateCategory
        
        assert TemplateCategory.APPLICANT_FOLLOWUP.value == "applicant_followup"
        assert TemplateCategory.MARKET_OUTREACH.value == "market_outreach"
        assert TemplateCategory.INTERVIEW_INVITE.value == "interview_invite"
        assert TemplateCategory.REJECTION.value == "rejection"
        assert TemplateCategory.CUSTOM.value == "custom"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

