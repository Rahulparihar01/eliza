"""
Candidate Service

Handles candidate profile management and analysis score storage.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import and_, or_
import structlog

from src.models.candidate import Candidate, CandidateAnalysisScore

logger = structlog.get_logger()


class CandidateService:
    """Service for managing candidates and their analysis scores."""
    
    def __init__(self, db: Session, customer_id: str):
        self.db = db
        self.customer_id = customer_id
    
    def upsert_candidate(
        self,
        email: Optional[str] = None,
        greenhouse_id: Optional[int] = None,
        pdl_id: Optional[str] = None,
        full_name: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        github_url: Optional[str] = None,
        location: Optional[str] = None,
        current_title: Optional[str] = None,
        current_company: Optional[str] = None,
        skills: Optional[List[str]] = None,
        experience: Optional[List[Dict]] = None,
        education: Optional[List[Dict]] = None,
        certifications: Optional[List[str]] = None,
        summary: Optional[str] = None,
        source: Optional[str] = None,
        source_metadata: Optional[Dict] = None,
    ) -> Candidate:
        """
        Upsert a candidate profile.
        
        Matches by email (primary) or greenhouse_id or pdl_id.
        Updates existing record or creates new one.
        """
        # Ensure greenhouse_id is an integer if provided
        if greenhouse_id is not None:
            try:
                greenhouse_id = int(greenhouse_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid greenhouse_id type: {type(greenhouse_id)}, value: {greenhouse_id}")
                greenhouse_id = None
        
        # Find existing candidate
        existing = self._find_existing_candidate(email, greenhouse_id, pdl_id)
        
        if existing:
            # Update existing candidate
            if email and not existing.email:
                existing.email = email
            if greenhouse_id and not existing.greenhouse_id:
                existing.greenhouse_id = greenhouse_id
            if pdl_id and not existing.pdl_id:
                existing.pdl_id = pdl_id
            if full_name:
                existing.full_name = full_name
            if first_name:
                existing.first_name = first_name
            if last_name:
                existing.last_name = last_name
            if phone:
                existing.phone = phone
            if linkedin_url:
                existing.linkedin_url = linkedin_url
            if github_url:
                existing.github_url = github_url
            if location:
                existing.location = location
            if current_title:
                existing.current_title = current_title
            if current_company:
                existing.current_company = current_company
            if skills:
                existing.skills = skills
            if experience:
                existing.experience = experience
            if education:
                existing.education = education
            if certifications:
                existing.certifications = certifications
            if summary:
                existing.summary = summary
            if source and not existing.source:
                existing.source = source
            if source_metadata:
                existing.source_metadata = {**(existing.source_metadata or {}), **source_metadata}
            
            existing.updated_at = datetime.utcnow()
            existing.last_verified_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(existing)
            
            logger.info(
                "candidate_updated",
                candidate_id=existing.id,
                email=existing.email,
                full_name=existing.full_name
            )
            return existing
        
        # Create new candidate
        logger.info(
            "creating_new_candidate",
            email=email,
            greenhouse_id=greenhouse_id,
            full_name=full_name,
            source=source
        )
        new_candidate = Candidate(
            customer_id=self.customer_id,
            email=email,
            greenhouse_id=greenhouse_id,
            pdl_id=pdl_id,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            linkedin_url=linkedin_url,
            github_url=github_url,
            location=location,
            current_title=current_title,
            current_company=current_company,
            skills=skills,
            experience=experience,
            education=education,
            certifications=certifications,
            summary=summary,
            source=source,
            source_metadata=source_metadata,
            load_date=datetime.utcnow(),
            last_verified_at=datetime.utcnow(),
        )
        
        self.db.add(new_candidate)
        self.db.commit()
        self.db.refresh(new_candidate)
        
        logger.info(
            "candidate_created",
            candidate_id=new_candidate.id,
            email=new_candidate.email,
            full_name=new_candidate.full_name,
            source=source
        )
        return new_candidate
    
    def _find_existing_candidate(
        self,
        email: Optional[str],
        greenhouse_id: Optional[int],
        pdl_id: Optional[str]
    ) -> Optional[Candidate]:
        """Find an existing candidate by email, greenhouse_id, or pdl_id."""
        conditions = []
        
        if email:
            conditions.append(and_(Candidate.customer_id == self.customer_id, Candidate.email == email))
        if greenhouse_id:
            conditions.append(and_(Candidate.customer_id == self.customer_id, Candidate.greenhouse_id == greenhouse_id))
        if pdl_id:
            conditions.append(and_(Candidate.customer_id == self.customer_id, Candidate.pdl_id == pdl_id))
        
        if not conditions:
            return None
        
        return self.db.query(Candidate).filter(or_(*conditions)).first()
    
    def save_analysis_score(
        self,
        candidate_id: int,
        analysis_id: str,
        overall_score: float,
        source: str,  # 'applicant' or 'market'
        score_breakdown: Dict[str, Any],
        confidence: Optional[float] = None,
        patterns_matched: Optional[List[str]] = None,
        match_metadata: Optional[Dict] = None,
        rank_overall: Optional[int] = None,
        rank_in_source: Optional[int] = None,
    ) -> CandidateAnalysisScore:
        """
        Save or update a candidate's score for an analysis.
        """
        # Check for existing score
        existing = self.db.query(CandidateAnalysisScore).filter(
            CandidateAnalysisScore.candidate_id == candidate_id,
            CandidateAnalysisScore.analysis_id == analysis_id
        ).first()
        
        if existing:
            existing.overall_score = overall_score
            existing.score_breakdown = score_breakdown
            existing.confidence = confidence
            existing.patterns_matched = patterns_matched
            existing.match_metadata = match_metadata
            existing.rank_overall = rank_overall
            existing.rank_in_source = rank_in_source
            existing.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        # Create new score
        new_score = CandidateAnalysisScore(
            candidate_id=candidate_id,
            analysis_id=analysis_id,
            overall_score=overall_score,
            source=source,
            score_breakdown=score_breakdown,
            confidence=confidence,
            patterns_matched=patterns_matched,
            match_metadata=match_metadata,
            rank_overall=rank_overall,
            rank_in_source=rank_in_source,
        )
        
        self.db.add(new_score)
        self.db.commit()
        self.db.refresh(new_score)
        
        logger.info(
            "analysis_score_saved",
            candidate_id=candidate_id,
            analysis_id=analysis_id,
            overall_score=overall_score,
            source=source
        )
        return new_score
    
    def save_generated_email(
        self,
        candidate_id: int,
        analysis_id: str,
        email_template_id: int,
        subject: str,
        body: str
    ) -> CandidateAnalysisScore:
        """
        Save a generated email for a candidate in an analysis.
        """
        score = self.db.query(CandidateAnalysisScore).filter(
            CandidateAnalysisScore.candidate_id == candidate_id,
            CandidateAnalysisScore.analysis_id == analysis_id
        ).first()
        
        if not score:
            raise ValueError(f"No score found for candidate {candidate_id} in analysis {analysis_id}")
        
        score.email_template_id = email_template_id
        score.generated_email_subject = subject
        score.generated_email_body = body
        score.email_generated_at = datetime.utcnow()
        score.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(score)
        
        logger.info(
            "generated_email_saved",
            candidate_id=candidate_id,
            analysis_id=analysis_id,
            email_template_id=email_template_id
        )
        return score
    
    def update_outreach_status(
        self,
        candidate_id: int,
        analysis_id: str,
        status: str,
        notes: Optional[str] = None
    ) -> CandidateAnalysisScore:
        """
        Update the outreach status for a candidate in an analysis.
        """
        score = self.db.query(CandidateAnalysisScore).filter(
            CandidateAnalysisScore.candidate_id == candidate_id,
            CandidateAnalysisScore.analysis_id == analysis_id
        ).first()
        
        if not score:
            raise ValueError(f"No score found for candidate {candidate_id} in analysis {analysis_id}")
        
        score.outreach_status = status
        if status == 'sent':
            score.outreach_sent_at = datetime.utcnow()
        if notes:
            score.outreach_notes = notes
        score.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(score)
        
        return score
    
    def get_candidates_for_analysis(
        self,
        analysis_id: str,
        source: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get all candidates with their scores for an analysis.
        """
        query = self.db.query(CandidateAnalysisScore).join(Candidate).filter(
            CandidateAnalysisScore.analysis_id == analysis_id
        )
        
        if source:
            query = query.filter(CandidateAnalysisScore.source == source)
        if min_score is not None:
            query = query.filter(CandidateAnalysisScore.overall_score >= min_score)
        
        query = query.order_by(CandidateAnalysisScore.overall_score.desc()).limit(limit)
        
        results = []
        for score in query.all():
            candidate = score.candidate
            results.append({
                **candidate.to_dict(),
                "score": score.to_dict()
            })
        
        return results
    
    def get_candidate_by_id(self, candidate_id: int) -> Optional[Candidate]:
        """Get a candidate by ID."""
        return self.db.query(Candidate).filter(
            Candidate.id == candidate_id,
            Candidate.customer_id == self.customer_id
        ).first()
    
    def get_candidate_by_email(self, email: str) -> Optional[Candidate]:
        """Get a candidate by email."""
        return self.db.query(Candidate).filter(
            Candidate.email == email,
            Candidate.customer_id == self.customer_id
        ).first()
    
    def get_candidate_by_greenhouse_id(self, greenhouse_id: int) -> Optional[Candidate]:
        """Get a candidate by Greenhouse ID."""
        return self.db.query(Candidate).filter(
            Candidate.greenhouse_id == greenhouse_id,
            Candidate.customer_id == self.customer_id
        ).first()
    
    def get_cached_parsed_resume(
        self,
        email: Optional[str] = None,
        greenhouse_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if we have a cached parsed resume for this candidate.
        
        Returns candidate data suitable for scoring if found, None otherwise.
        A candidate is considered "cached" if they have skills or experience data.
        """
        candidate = None
        
        if greenhouse_id:
            candidate = self.get_candidate_by_greenhouse_id(greenhouse_id)
        if not candidate and email:
            candidate = self.get_candidate_by_email(email)
        
        if not candidate:
            return None
        
        # Check if we have meaningful parsed data (skills or experience)
        has_skills = candidate.skills and len(candidate.skills) > 0
        has_experience = candidate.experience and len(candidate.experience) > 0
        
        if not has_skills and not has_experience:
            return None
        
        # Return candidate data in a format compatible with scoring engine
        return {
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "linkedin_url": candidate.linkedin_url,
            "github_url": candidate.github_url,
            "location": candidate.location,
            "current_title": candidate.current_title,
            "current_company": candidate.current_company,
            "skills": candidate.skills or [],
            "experience": candidate.experience or [],
            "education": candidate.education or [],
            "certifications": candidate.certifications or [],
            "summary": candidate.summary,
            "greenhouse_id": candidate.greenhouse_id,
        }
    
    def search_candidates(
        self,
        query: Optional[str] = None,
        skills: Optional[List[str]] = None,
        location: Optional[str] = None,
        limit: int = 50
    ) -> List[Candidate]:
        """
        Search candidates by name, skills, or location.
        """
        db_query = self.db.query(Candidate).filter(
            Candidate.customer_id == self.customer_id
        )
        
        if query:
            search_term = f"%{query}%"
            db_query = db_query.filter(
                or_(
                    Candidate.full_name.ilike(search_term),
                    Candidate.email.ilike(search_term),
                    Candidate.current_title.ilike(search_term),
                    Candidate.current_company.ilike(search_term)
                )
            )
        
        if location:
            db_query = db_query.filter(Candidate.location.ilike(f"%{location}%"))
        
        # TODO: Add skills search using JSONB operators
        
        return db_query.order_by(Candidate.updated_at.desc()).limit(limit).all()

