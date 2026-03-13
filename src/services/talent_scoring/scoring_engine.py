"""
Talent Scoring Engine

Multi-dimensional scoring algorithm for matching candidates against employee baselines.

Dimensions:
1. Skills Overlap - Jaccard similarity + TF-IDF weighting
2. Experience Pattern - Years, seniority, progression
3. Career Trajectory - Company tier progression, role growth
4. Company Fit - Similar companies in history
5. Education Alignment - Degree match, school similarity
6. Semantic Similarity - Embedding cosine similarity

Final score: Weighted combination of all dimensions (0-100 scale)
"""
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter
import math
import numpy as np
from sqlalchemy.orm import Session

import structlog

from src.models.connector import PDLPerson, BaselineEmployeeProfile, ApplicantScore
from src.services.resume_processing.docling_parser import ParsedResume, DoclingParser

logger = structlog.get_logger(__name__)


class TalentScoringEngine:
    """
    Multi-dimensional scoring engine for talent matching.
    
    Scores candidates (applicants or PDL persons) against
    baseline employee profiles for a specific role.
    """
    
    # Scoring weights (must sum to 1.0)
    WEIGHTS = {
        "skills": 0.30,           # 30% - Most important
        "experience": 0.20,        # 20%
        "career_trajectory": 0.15, # 15%
        "company_fit": 0.15,       # 15%
        "education": 0.10,         # 10%
        "embedding": 0.10,         # 10%
    }
    
    # Company tier classification (simple heuristic)
    TOP_TIER_COMPANIES = {
        "google", "apple", "microsoft", "amazon", "meta", "facebook",
        "netflix", "tesla", "spacex", "openai", "anthropic",
        "stripe", "airbnb", "uber", "lyft", "coinbase"
    }
    
    SECOND_TIER_COMPANIES = {
        "salesforce", "oracle", "ibm", "intel", "nvidia", "adobe",
        "twitter", "x", "snap", "pinterest", "reddit", "dropbox",
        "slack", "zoom", "atlassian", "github", "gitlab"
    }
    
    def __init__(self, db: Session):
        """
        Initialize scoring engine.
        
        Args:
            db: Database session for querying employee data
        """
        self.logger = logger.bind(service="scoring_engine")
        self.db = db
        self.docling_parser = DoclingParser()
    
    def score_candidate(
        self,
        candidate_data: Dict[str, Any],
        baseline_profile: BaselineEmployeeProfile,
        analysis_id: str
    ) -> Dict[str, Any]:
        """
        Score a candidate against a baseline employee profile.
        
        Args:
            candidate_data: Candidate data in PDL format (can be from resume or PDL API)
            baseline_profile: Baseline employee profile for the role
            analysis_id: Talent analysis ID for tracking
            
        Returns:
            Scoring results with dimension breakdowns
        """
        try:
            self.logger.info(
                "Scoring candidate",
                candidate_name=candidate_data.get("full_name"),
                role=baseline_profile.role_title
            )
            
            # Calculate individual dimension scores
            skills_score = self._score_skills(candidate_data, baseline_profile)
            experience_score = self._score_experience(candidate_data, baseline_profile)
            trajectory_score = self._score_career_trajectory(candidate_data, baseline_profile)
            company_score = self._score_company_fit(candidate_data, baseline_profile)
            education_score = self._score_education(candidate_data, baseline_profile)
            embedding_score = self._score_embedding_similarity(candidate_data, baseline_profile)
            
            # Calculate weighted overall score
            overall_score = (
                skills_score * self.WEIGHTS["skills"] +
                experience_score * self.WEIGHTS["experience"] +
                trajectory_score * self.WEIGHTS["career_trajectory"] +
                company_score * self.WEIGHTS["company_fit"] +
                education_score * self.WEIGHTS["education"] +
                embedding_score * self.WEIGHTS["embedding"]
            )
            
            # Find most similar employees
            matched_employee_ids = self._find_similar_employees(
                candidate_data,
                baseline_profile
            )
            
            # Generate AI reasoning
            reasoning = self._generate_reasoning(
                candidate_data=candidate_data,
                overall_score=overall_score,
                dimension_scores={
                    "skills": skills_score,
                    "experience": experience_score,
                    "career_trajectory": trajectory_score,
                    "company_fit": company_score,
                    "education": education_score,
                    "embedding": embedding_score,
                }
            )
            
            result = {
                "overall_score": round(overall_score, 2),
                "skills_score": round(skills_score, 2),
                "experience_score": round(experience_score, 2),
                "career_trajectory_score": round(trajectory_score, 2),
                "company_fit_score": round(company_score, 2),
                "education_score": round(education_score, 2),
                "embedding_similarity": round(embedding_score / 100, 4),  # 0-1 scale for embeddings
                "matched_employee_ids": matched_employee_ids,
                "reasoning": reasoning,
                "dimension_scores": {
                    "skills": {
                        "score": round(skills_score, 2),
                        "weight": self.WEIGHTS["skills"],
                        "contribution": round(skills_score * self.WEIGHTS["skills"], 2)
                    },
                    "experience": {
                        "score": round(experience_score, 2),
                        "weight": self.WEIGHTS["experience"],
                        "contribution": round(experience_score * self.WEIGHTS["experience"], 2)
                    },
                    "career_trajectory": {
                        "score": round(trajectory_score, 2),
                        "weight": self.WEIGHTS["career_trajectory"],
                        "contribution": round(trajectory_score * self.WEIGHTS["career_trajectory"], 2)
                    },
                    "company_fit": {
                        "score": round(company_score, 2),
                        "weight": self.WEIGHTS["company_fit"],
                        "contribution": round(company_score * self.WEIGHTS["company_fit"], 2)
                    },
                    "education": {
                        "score": round(education_score, 2),
                        "weight": self.WEIGHTS["education"],
                        "contribution": round(education_score * self.WEIGHTS["education"], 2)
                    },
                    "embedding": {
                        "score": round(embedding_score, 2),
                        "weight": self.WEIGHTS["embedding"],
                        "contribution": round(embedding_score * self.WEIGHTS["embedding"], 2)
                    },
                }
            }
            
            self.logger.info(
                "Candidate scored",
                candidate_name=candidate_data.get("full_name"),
                overall_score=result["overall_score"]
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Scoring failed",
                candidate_name=candidate_data.get("full_name"),
                error=str(e)
            )
            raise
    
    def _score_skills(
        self,
        candidate_data: Dict[str, Any],
        baseline_profile: BaselineEmployeeProfile
    ) -> float:
        """
        Score skills overlap using Jaccard similarity with TF-IDF weighting.
        
        Considers:
        - Skill overlap with baseline skills
        - Skill frequency (more common skills weighted higher)
        - Exact match vs. similar skills
        
        Returns:
            Score 0-100
        """
        # Extract candidate skills
        candidate_skills_raw = candidate_data.get("skills", [])
        candidate_skills = set()
        
        for skill in candidate_skills_raw:
            if isinstance(skill, dict):
                skill_name = skill.get("name", "").lower().strip()
            else:
                skill_name = str(skill).lower().strip()
            
            if skill_name:
                candidate_skills.add(skill_name)
        
        if not candidate_skills:
            return 0.0
        
        # Extract baseline skills with frequencies
        baseline_skills_data = baseline_profile.aggregated_skills or {}
        baseline_skills = set(baseline_skills_data.keys())
        
        if not baseline_skills:
            return 50.0  # Neutral score if no baseline data
        
        # Calculate Jaccard similarity
        intersection = candidate_skills & baseline_skills
        union = candidate_skills | baseline_skills
        
        jaccard_score = len(intersection) / len(union) if union else 0
        
        # Apply TF-IDF weighting for matched skills
        # Skills more common in baseline are weighted higher
        weighted_score = 0
        total_weight = 0
        
        for skill in intersection:
            frequency = baseline_skills_data.get(skill, 1)
            # Use log to dampen very high frequencies
            weight = math.log(frequency + 1)
            weighted_score += weight
            total_weight += weight
        
        # Normalize weighted score
        max_possible_weight = sum(
            math.log(baseline_skills_data.get(skill, 1) + 1)
            for skill in baseline_skills
        )
        
        if max_possible_weight > 0:
            weighted_normalized = weighted_score / max_possible_weight
        else:
            weighted_normalized = 0
        
        # Combine Jaccard and weighted score (70/30 split)
        final_score = (jaccard_score * 0.7 + weighted_normalized * 0.3) * 100
        
        return min(final_score, 100)
    
    def _score_experience(
        self,
        candidate_data: Dict[str, Any],
        baseline_profile: BaselineEmployeeProfile
    ) -> float:
        """
        Score experience pattern matching.
        
        Considers:
        - Total years of experience vs. baseline average
        - Seniority progression (junior -> mid -> senior)
        - Role diversity
        - Employment gaps
        
        Returns:
            Score 0-100
        """
        candidate_experience = candidate_data.get("experience", [])
        
        if not candidate_experience:
            return 20.0  # Low score for no experience data
        
        # Calculate total years of experience
        total_years = self._calculate_years_of_experience(candidate_experience)
        baseline_years = baseline_profile.avg_years_experience or 5
        
        # Score years (optimal is within ±2 years of baseline)
        years_diff = abs(total_years - baseline_years)
        if years_diff <= 2:
            years_score = 100
        elif years_diff <= 4:
            years_score = 80
        elif years_diff <= 6:
            years_score = 60
        else:
            years_score = max(40, 100 - years_diff * 5)
        
        # Score seniority progression
        seniority_score = self._score_seniority_progression(candidate_experience)
        
        # Score role diversity (more diverse is better, up to a point)
        unique_titles = len(set(
            exp.get("title", {}).get("name", "") if isinstance(exp.get("title"), dict) else exp.get("title", "")
            for exp in candidate_experience
        ))
        diversity_score = min(unique_titles * 20, 100)
        
        # Combine scores
        final_score = (
            years_score * 0.5 +
            seniority_score * 0.3 +
            diversity_score * 0.2
        )
        
        return min(final_score, 100)
    
    def _calculate_years_of_experience(self, experience_list: List[Dict[str, Any]]) -> float:
        """Calculate total years of experience from experience list."""
        total_years = 0
        
        for exp in experience_list:
            start_date = exp.get("start_date")
            end_date = exp.get("end_date")
            is_current = exp.get("is_current", False)
            
            if start_date:
                try:
                    start_year = int(str(start_date)[:4])
                    
                    if is_current or not end_date:
                        end_year = 2025  # Current year
                    else:
                        end_year = int(str(end_date)[:4])
                    
                    years = max(end_year - start_year, 0)
                    total_years += years
                except:
                    pass
        
        return total_years
    
    def _score_seniority_progression(self, experience_list: List[Dict[str, Any]]) -> float:
        """
        Score seniority progression over time.
        
        Good progression: Junior -> Mid -> Senior -> Lead -> Principal
        """
        if not experience_list:
            return 50.0
        
        # Keywords for seniority levels
        seniority_keywords = {
            "junior": 1,
            "associate": 2,
            "mid": 3,
            "senior": 4,
            "staff": 5,
            "lead": 6,
            "principal": 7,
            "director": 8,
            "vp": 9,
            "chief": 10,
        }
        
        # Extract seniority levels over time
        seniority_progression = []
        
        for exp in experience_list:
            title_raw = exp.get("title", {})
            if isinstance(title_raw, dict):
                title = title_raw.get("name", "").lower()
            else:
                title = str(title_raw).lower()
            
            # Find highest seniority keyword in title
            level = 3  # Default to mid-level
            for keyword, value in seniority_keywords.items():
                if keyword in title:
                    level = max(level, value)
            
            seniority_progression.append(level)
        
        # Reverse to get chronological order (newest first -> oldest last)
        seniority_progression = list(reversed(seniority_progression))
        
        # Score based on progression
        if len(seniority_progression) == 1:
            return 70.0  # Single role, neutral score
        
        # Count upward movements
        upward_movements = sum(
            1 for i in range(len(seniority_progression) - 1)
            if seniority_progression[i + 1] > seniority_progression[i]
        )
        
        # Count lateral or downward movements
        lateral_movements = sum(
            1 for i in range(len(seniority_progression) - 1)
            if seniority_progression[i + 1] <= seniority_progression[i]
        )
        
        total_movements = len(seniority_progression) - 1
        
        if total_movements == 0:
            return 70.0
        
        # More upward movements = higher score
        upward_ratio = upward_movements / total_movements
        progression_score = 50 + (upward_ratio * 50)
        
        return progression_score
    
    def _score_career_trajectory(
        self,
        candidate_data: Dict[str, Any],
        baseline_profile: BaselineEmployeeProfile
    ) -> float:
        """
        Score career trajectory - company tier progression.
        
        Considers:
        - Movement from lower-tier to higher-tier companies
        - Stability (not too many job hops)
        - Company prestige
        
        Returns:
            Score 0-100
        """
        candidate_experience = candidate_data.get("experience", [])
        
        if not candidate_experience:
            return 50.0
        
        # Extract company tiers over time
        company_tiers = []
        
        for exp in candidate_experience:
            company_raw = exp.get("company", {})
            if isinstance(company_raw, dict):
                company = company_raw.get("name", "").lower()
            else:
                company = str(company_raw).lower()
            
            # Determine tier
            if any(top in company for top in self.TOP_TIER_COMPANIES):
                tier = 3
            elif any(second in company for second in self.SECOND_TIER_COMPANIES):
                tier = 2
            else:
                tier = 1
            
            company_tiers.append(tier)
        
        # Reverse to chronological order
        company_tiers = list(reversed(company_tiers))
        
        # Score based on:
        # 1. Current/recent tier (40%)
        recent_tier = company_tiers[-1] if company_tiers else 1
        tier_score = (recent_tier / 3) * 100
        
        # 2. Upward trajectory (40%)
        if len(company_tiers) > 1:
            upward_moves = sum(
                1 for i in range(len(company_tiers) - 1)
                if company_tiers[i + 1] > company_tiers[i]
            )
            trajectory_score = min((upward_moves / (len(company_tiers) - 1)) * 100, 100)
        else:
            trajectory_score = 50
        
        # 3. Stability - penalize too many short stints (20%)
        if len(company_tiers) > 5:
            stability_score = max(0, 100 - (len(company_tiers) - 5) * 10)
        else:
            stability_score = 100
        
        final_score = (
            tier_score * 0.4 +
            trajectory_score * 0.4 +
            stability_score * 0.2
        )
        
        return min(final_score, 100)
    
    def _score_company_fit(
        self,
        candidate_data: Dict[str, Any],
        baseline_profile: BaselineEmployeeProfile
    ) -> float:
        """
        Score company fit - overlap with common companies in baseline.
        
        Returns:
            Score 0-100
        """
        candidate_experience = candidate_data.get("experience", [])
        candidate_companies = set()
        
        for exp in candidate_experience:
            company_raw = exp.get("company", {})
            if isinstance(company_raw, dict):
                company = company_raw.get("name", "").lower().strip()
            else:
                company = str(company_raw).lower().strip()
            
            if company:
                candidate_companies.add(company)
        
        # Get baseline common companies
        baseline_companies_data = baseline_profile.common_companies or {}
        baseline_companies = set(baseline_companies_data.keys())
        
        if not baseline_companies:
            return 50.0  # Neutral if no baseline data
        
        if not candidate_companies:
            return 30.0  # Low score if no company data
        
        # Calculate overlap
        overlap = candidate_companies & baseline_companies
        overlap_ratio = len(overlap) / len(baseline_companies)
        
        # Score based on overlap
        score = min(overlap_ratio * 200, 100)  # 50% overlap = 100 score
        
        return score
    
    def _score_education(
        self,
        candidate_data: Dict[str, Any],
        baseline_profile: BaselineEmployeeProfile
    ) -> float:
        """
        Score education alignment.
        
        Considers:
        - Degree level match
        - School similarity
        - Field of study relevance
        
        Returns:
            Score 0-100
        """
        candidate_education = candidate_data.get("education", [])
        
        if not candidate_education:
            return 40.0  # Low score for missing education
        
        baseline_education_patterns = baseline_profile.education_patterns or {}
        
        if not baseline_education_patterns:
            return 60.0  # Neutral if no baseline
        
        # Extract candidate degrees
        candidate_degrees = []
        for edu in candidate_education:
            degrees = edu.get("degrees", [])
            if isinstance(degrees, list):
                candidate_degrees.extend([d.lower() for d in degrees])
            else:
                degree_raw = edu.get("degree")
                if degree_raw:
                    candidate_degrees.append(str(degree_raw).lower())
        
        # Extract candidate schools
        candidate_schools = []
        for edu in candidate_education:
            school_raw = edu.get("school", {})
            if isinstance(school_raw, dict):
                school = school_raw.get("name", "").lower()
            else:
                school = str(school_raw).lower()
            
            if school:
                candidate_schools.append(school)
        
        # Score degree match
        baseline_degrees = set(baseline_education_patterns.get("common_degrees", []))
        candidate_degree_set = set(candidate_degrees)
        
        degree_overlap = candidate_degree_set & baseline_degrees
        degree_score = (len(degree_overlap) / len(baseline_degrees)) * 100 if baseline_degrees else 50
        
        # Score school match
        baseline_schools = set(baseline_education_patterns.get("common_schools", []))
        candidate_school_set = set(candidate_schools)
        
        school_overlap = candidate_school_set & baseline_schools
        school_score = (len(school_overlap) / len(baseline_schools)) * 100 if baseline_schools else 50
        
        # Combine scores
        final_score = (degree_score * 0.6 + school_score * 0.4)
        
        return min(final_score, 100)
    
    def _score_embedding_similarity(
        self,
        candidate_data: Dict[str, Any],
        baseline_profile: BaselineEmployeeProfile
    ) -> float:
        """
        Score semantic similarity using embeddings (cosine similarity).
        
        Compares candidate embedding to baseline average embedding.
        
        Returns:
            Score 0-100 (scaled from cosine similarity 0-1)
        """
        # Get candidate embedding (if available)
        candidate_embedding = candidate_data.get("embedding")
        
        if not candidate_embedding:
            # Generate embedding from candidate text
            candidate_text = self._candidate_to_text(candidate_data)
            # TODO: Call OpenAI embedding API
            # For now, return neutral score
            return 50.0
        
        # Get baseline embedding
        baseline_embedding = baseline_profile.baseline_embedding
        
        if not baseline_embedding:
            return 50.0
        
        # Calculate cosine similarity
        try:
            candidate_vec = np.array(candidate_embedding)
            baseline_vec = np.array(baseline_embedding)
            
            cosine_sim = np.dot(candidate_vec, baseline_vec) / (
                np.linalg.norm(candidate_vec) * np.linalg.norm(baseline_vec)
            )
            
            # Scale to 0-100
            score = ((cosine_sim + 1) / 2) * 100  # cosine_sim is -1 to 1
            
            return min(max(score, 0), 100)
            
        except Exception as e:
            self.logger.warning("Embedding similarity calculation failed", error=str(e))
            return 50.0
    
    def _candidate_to_text(self, candidate_data: Dict[str, Any]) -> str:
        """Convert candidate data to text for embedding generation."""
        parts = []
        
        # Name and headline
        if candidate_data.get("full_name"):
            parts.append(candidate_data["full_name"])
        
        if candidate_data.get("headline"):
            parts.append(candidate_data["headline"])
        
        # Skills
        skills = candidate_data.get("skills", [])
        if skills:
            skill_names = [
                s.get("name") if isinstance(s, dict) else str(s)
                for s in skills
            ]
            parts.append("Skills: " + ", ".join(skill_names))
        
        # Experience
        experience = candidate_data.get("experience", [])
        for exp in experience[:3]:  # Top 3 most recent
            title = exp.get("title", {})
            company = exp.get("company", {})
            
            if isinstance(title, dict):
                title = title.get("name", "")
            if isinstance(company, dict):
                company = company.get("name", "")
            
            if title and company:
                parts.append(f"{title} at {company}")
        
        return " | ".join(parts)
    
    def _find_similar_employees(
        self,
        candidate_data: Dict[str, Any],
        baseline_profile: BaselineEmployeeProfile
    ) -> List[int]:
        """
        Find top 5 most similar employees from baseline.
        
        Uses simplified scoring on each employee.
        
        Returns:
            List of employee IDs (PDLPerson IDs)
        """
        employee_ids = baseline_profile.employee_ids or []
        
        if not employee_ids:
            return []
        
        # Score each employee
        employee_scores = []
        
        for emp_id in employee_ids[:20]:  # Limit to top 20 for performance
            try:
                employee = self.db.query(PDLPerson).filter(PDLPerson.id == emp_id).first()
                
                if not employee:
                    continue
                
                # Simple scoring based on skills overlap
                emp_skills = set(s.lower() for s in (employee.skills or []))
                candidate_skills_raw = candidate_data.get("skills", [])
                candidate_skills = set()
                
                for skill in candidate_skills_raw:
                    if isinstance(skill, dict):
                        skill_name = skill.get("name", "").lower()
                    else:
                        skill_name = str(skill).lower()
                    
                    if skill_name:
                        candidate_skills.add(skill_name)
                
                if emp_skills and candidate_skills:
                    overlap = len(emp_skills & candidate_skills)
                    union = len(emp_skills | candidate_skills)
                    similarity = overlap / union if union else 0
                    
                    employee_scores.append((emp_id, similarity))
            except Exception as e:
                self.logger.warning("Error scoring employee", emp_id=emp_id, error=str(e))
                continue
        
        # Sort by similarity and return top 5
        employee_scores.sort(key=lambda x: x[1], reverse=True)
        top_employees = [emp_id for emp_id, _ in employee_scores[:5]]
        
        return top_employees
    
    def _generate_reasoning(
        self,
        candidate_data: Dict[str, Any],
        overall_score: float,
        dimension_scores: Dict[str, float]
    ) -> str:
        """
        Generate human-readable reasoning for the score.
        
        Returns:
            Explanation string
        """
        name = candidate_data.get("full_name", "Candidate")
        
        # Find strongest dimensions
        sorted_dimensions = sorted(
            dimension_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        strongest = sorted_dimensions[0]
        weakest = sorted_dimensions[-1]
        
        reasoning_parts = [
            f"{name} received an overall match score of {overall_score:.1f}/100.",
            f"Strongest area: {strongest[0].replace('_', ' ').title()} ({strongest[1]:.1f}/100).",
            f"Area for development: {weakest[0].replace('_', ' ').title()} ({weakest[1]:.1f}/100).",
        ]
        
        # Add specific insights
        if dimension_scores["skills"] >= 70:
            reasoning_parts.append("Strong skills alignment with baseline employees.")
        
        if dimension_scores["experience"] >= 70:
            reasoning_parts.append("Experience pattern closely matches baseline.")
        
        if dimension_scores["career_trajectory"] >= 70:
            reasoning_parts.append("Demonstrated strong career progression.")
        
        return " ".join(reasoning_parts)

