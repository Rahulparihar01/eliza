"""
Multi-Dimensional Scoring Engine

Scores candidates across multiple dimensions for any role type.
Deterministic, weighted algorithm for consistent, explainable scoring.

Role-agnostic: all skill matching is driven by diagnostic output and baseline data,
not hardcoded skill lists.

Dimensions:
1. Technical Skills - Core domain/technical skills for the target role
2. Engineering Skills - General professional/engineering skills
3. Experience Level - Years and depth of experience
4. Career Trajectory - Progression and growth pattern
5. Company Background - Company cluster fit
6. Achievements - Quantified impact and results
"""
from typing import Dict, Any, List, Optional
import structlog

from src.models.talent_analysis import (
    CandidateScore,
    ScoreDimension,
    CandidateSource,
    BaselineProfile,
    DiagnosticReport,
    ParsedResume
)

logger = structlog.get_logger(__name__)


class MultiDimensionalScoringEngine:
    """
    Scores candidates across multiple weighted dimensions.
    
    Role-agnostic: skill matching is driven by diagnostic output (required/preferred
    skills from the job description) and baseline data (skill distributions from
    current employees), not hardcoded skill lists.
    
    Deterministic algorithm - no LLM calls, pure math.
    Explainable scoring with evidence for each dimension.
    """
    
    def __init__(self):
        """Initialize scoring engine."""
        self.logger = logger.bind(service="scoring_engine")
    
    def score_candidate(
        self,
        candidate_data: Dict[str, Any],
        baseline: BaselineProfile,
        candidate_source: CandidateSource,
        candidate_id: str,
        diagnostic: Optional[DiagnosticReport] = None
    ) -> CandidateScore:
        """
        Score a candidate across all dimensions.
        
        Args:
            candidate_data: Parsed resume data or PDL person data
            baseline: Baseline profile for comparison
            candidate_source: 'applicant' or 'market'
            candidate_id: Unique candidate identifier
            diagnostic: Optional diagnostic report with required/preferred skills from job description
            
        Returns:
            CandidateScore with dimension breakdowns
        """
        try:
            self.logger.info(
                "Scoring candidate",
                candidate_id=candidate_id,
                source=candidate_source
            )
            
            # Extract weights from baseline
            weights = baseline.attribute_weights
            
            # Score each dimension
            dimensions = []
            
            # 1. Technical Skills (driven by diagnostic + baseline, not hardcoded)
            tech_score = self._score_technical_skills(candidate_data, baseline, diagnostic)
            dimensions.append(tech_score)
            
            # 2. Engineering/Professional Skills
            eng_score = self._score_engineering_skills(candidate_data, baseline, diagnostic)
            dimensions.append(eng_score)
            
            # 3. Experience Level
            exp_score = self._score_experience_level(candidate_data, baseline)
            dimensions.append(exp_score)
            
            # 4. Career Trajectory
            traj_score = self._score_career_trajectory(candidate_data, baseline)
            dimensions.append(traj_score)
            
            # 5. Company Background
            company_score = self._score_company_background(candidate_data, baseline)
            dimensions.append(company_score)
            
            # 6. Achievements
            achievement_score = self._score_achievements(candidate_data)
            dimensions.append(achievement_score)
            
            # Calculate weighted overall score
            overall_score = 0.0
            for dim in dimensions:
                # Map dimension names to weight keys
                weight_key = self._map_dimension_to_weight(dim.dimension)
                weight = weights.get(weight_key, 0.10)  # Default 10%
                overall_score += (dim.score / 100.0) * weight
            
            overall_score = overall_score * 100.0  # Convert back to 0-100 scale
            
            # Calculate baseline similarity
            baseline_similarity = self._calculate_baseline_similarity(
                candidate_data,
                baseline
            )
            
            # Extract patterns matched
            patterns_matched = self._identify_patterns(candidate_data, baseline)
            
            # Confidence based on data completeness
            confidence = self._calculate_confidence(candidate_data, dimensions)
            
            # Extract profile data from candidate_data
            # For applicants, this comes from parsed resume + Greenhouse data
            # For market candidates, this comes from PDL
            full_name = candidate_data.get("full_name") or candidate_data.get("name")
            email = candidate_data.get("email") or candidate_data.get("work_email")
            phone = candidate_data.get("phone") or candidate_data.get("mobile_phone")
            linkedin_url = candidate_data.get("linkedin_url") or candidate_data.get("linkedin")
            location = candidate_data.get("location") or candidate_data.get("location_name")
            current_title = candidate_data.get("current_title") or candidate_data.get("job_title")
            current_company = candidate_data.get("current_company") or candidate_data.get("job_company_name")
            greenhouse_id = candidate_data.get("greenhouse_id") or candidate_data.get("greenhouse_candidate_id")
            
            score = CandidateScore(
                candidate_id=candidate_id,
                source=candidate_source,
                overall_score=round(overall_score, 2),
                dimensions=dimensions,
                patterns_matched=patterns_matched,
                baseline_similarity=round(baseline_similarity, 3),
                confidence=round(confidence, 3),
                # Profile data
                full_name=full_name,
                email=email,
                phone=phone,
                linkedin_url=linkedin_url,
                location=location,
                current_title=current_title,
                current_company=current_company,
                greenhouse_id=greenhouse_id
            )
            
            self.logger.info(
                "Candidate scored",
                candidate_id=candidate_id,
                overall_score=score.overall_score,
                confidence=score.confidence
            )
            
            return score
            
        except Exception as e:
            self.logger.error(
                "Failed to score candidate",
                candidate_id=candidate_id,
                error=str(e)
            )
            # Return minimal score
            return CandidateScore(
                candidate_id=candidate_id,
                source=candidate_source,
                overall_score=0.0,
                dimensions=[],
                patterns_matched=[],
                baseline_similarity=0.0,
                confidence=0.0
            )
    
    def _score_technical_skills(
        self,
        candidate: Dict[str, Any],
        baseline: BaselineProfile,
        diagnostic: Optional[DiagnosticReport] = None
    ) -> ScoreDimension:
        """
        Score technical/domain skills for the target role.
        
        Uses required and preferred skills from the diagnostic report (derived from the
        job description), plus baseline skill distributions. No hardcoded skill lists.
        """
        cand_skills = self._extract_skills(candidate)
        cand_skills_lower = [s.lower() for s in cand_skills]
        
        # Build target skills from diagnostic output (role-specific)
        required_skills = []
        preferred_skills = []
        if diagnostic:
            required_skills = [s.lower() for s in diagnostic.required_skills]
            preferred_skills = [s.lower() for s in diagnostic.preferred_skills]
        
        # Match required skills (60 pts max)
        required_matches = []
        for skill in required_skills:
            if any(skill in cand_skill for cand_skill in cand_skills_lower):
                required_matches.append(skill)
        
        if required_skills:
            required_ratio = len(required_matches) / len(required_skills)
            required_score = required_ratio * 60
        else:
            required_score = 30  # Neutral when no diagnostic
        
        # Match preferred skills (20 pts max)
        preferred_matches = []
        for skill in preferred_skills:
            if any(skill in cand_skill for cand_skill in cand_skills_lower):
                preferred_matches.append(skill)
        
        if preferred_skills:
            preferred_ratio = len(preferred_matches) / len(preferred_skills)
            preferred_score = preferred_ratio * 20
        else:
            preferred_score = 10  # Neutral when no diagnostic
        
        # Bonus for baseline skill match (20 pts max)
        baseline_skills = baseline.skill_distributions
        common_skills = set(cand_skills_lower) & set(baseline_skills.keys())
        baseline_bonus = min(len(common_skills) * 3, 20) if common_skills else 0
        
        score = min(required_score + preferred_score + baseline_bonus, 100)
        
        all_matches = required_matches + preferred_matches
        explanation = f"Matched {len(required_matches)}/{len(required_skills)} required skills"
        if preferred_matches:
            explanation += f", {len(preferred_matches)}/{len(preferred_skills)} preferred"
        if common_skills:
            explanation += f", {len(common_skills)} baseline matches"
        
        evidence = [f"Required: {skill}" for skill in required_matches[:5]]
        evidence += [f"Preferred: {skill}" for skill in preferred_matches[:5]]
        
        return ScoreDimension(
            dimension="technical_skills",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence
        )
    
    def _score_engineering_skills(
        self,
        candidate: Dict[str, Any],
        baseline: BaselineProfile,
        diagnostic: Optional[DiagnosticReport] = None
    ) -> ScoreDimension:
        """
        Score general professional/engineering skills.
        
        Uses baseline skill distributions to identify common professional skills
        among current employees, then scores candidates against those.
        """
        cand_skills = self._extract_skills(candidate)
        cand_skills_lower = [s.lower() for s in cand_skills]
        
        # Use baseline skill distributions as the reference for engineering skills
        baseline_skills = baseline.skill_distributions
        
        if baseline_skills:
            # Match against all baseline skills (broader than just required/preferred)
            matches = []
            for skill_name, frequency in baseline_skills.items():
                if any(skill_name.lower() in cand_skill for cand_skill in cand_skills_lower):
                    matches.append((skill_name, frequency))
            
            # Score weighted by frequency in baseline
            if matches:
                weighted_sum = sum(freq for _, freq in matches)
                total_possible = sum(baseline_skills.values())
                score = (weighted_sum / max(total_possible, 0.01)) * 100
                score = min(score, 100)
            else:
                score = 20  # Low score if no matches
            
            explanation = f"Matched {len(matches)} skills from baseline employee profiles"
            evidence = [f"{skill} (baseline freq: {freq:.0%})" for skill, freq in matches[:10]]
        else:
            # Fallback: score based on total skill count
            total_skills = len(cand_skills)
            score = min(total_skills * 8, 100)
            explanation = f"Candidate has {total_skills} listed skills (no baseline for comparison)"
            evidence = [f"Skill: {s}" for s in cand_skills[:10]]
        
        return ScoreDimension(
            dimension="engineering_skills",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence
        )
    
    def _score_experience_level(
        self,
        candidate: Dict[str, Any],
        baseline: BaselineProfile
    ) -> ScoreDimension:
        """Score years and depth of experience."""
        # Get years of experience
        years = self._extract_years_experience(candidate)
        baseline_avg = baseline.average_years_experience
        
        # Score based on proximity to baseline average
        # Perfect score if within +/- 2 years of average
        diff = abs(years - baseline_avg)
        
        if diff <= 2:
            score = 100
        elif diff <= 4:
            score = 80
        elif diff <= 6:
            score = 60
        else:
            score = 40
        
        # Bonus for depth (number of roles)
        experience_entries = self._extract_experience(candidate)
        if len(experience_entries) >= 4:
            score = min(score + 20, 100)
        elif len(experience_entries) >= 2:
            score = min(score + 10, 100)
        
        explanation = f"{years} years experience (baseline avg: {baseline_avg:.1f})"
        evidence = [
            f"{years} years total experience",
            f"{len(experience_entries)} roles in career history"
        ]
        
        return ScoreDimension(
            dimension="experience_level",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence
        )
    
    def _score_career_trajectory(
        self,
        candidate: Dict[str, Any],
        baseline: BaselineProfile
    ) -> ScoreDimension:
        """Score career progression pattern."""
        experience = self._extract_experience(candidate)
        
        if len(experience) < 2:
            return ScoreDimension(
                dimension="career_trajectory",
                score=50.0,
                explanation="Limited career history available",
                evidence=["Less than 2 roles in history"]
            )
        
        # Check for progression signals
        score = 50  # Base score
        progression_signals = []
        
        # Look for title progression
        titles = [job.get('title', '').lower() for job in experience]
        
        # Senior progression
        has_senior_progression = False
        for i in range(len(titles) - 1):
            if 'senior' not in titles[i] and 'senior' in titles[i + 1]:
                has_senior_progression = True
                progression_signals.append("Progressed to Senior level")
                score += 20
                break
        
        # Lead progression
        if any('lead' in t or 'principal' in t or 'staff' in t for t in titles):
            progression_signals.append("Reached leadership/senior IC level")
            score += 15
        
        # Check against baseline career paths
        baseline_paths = baseline.common_career_paths
        if baseline_paths:
            # Simplified path matching
            candidate_path_sig = self._create_simple_path_signature(experience)
            for path in baseline_paths[:5]:  # Check top 5 baseline paths
                if self._paths_similar(candidate_path_sig, path.path_description):
                    progression_signals.append(f"Similar to baseline pattern: {path.path_description[:50]}")
                    score += 15
                    break
        
        score = min(score, 100)
        
        explanation = f"{len(progression_signals)} progression signals detected"
        evidence = progression_signals if progression_signals else ["No clear progression signals"]
        
        return ScoreDimension(
            dimension="career_trajectory",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence
        )
    
    def _score_company_background(
        self,
        candidate: Dict[str, Any],
        baseline: BaselineProfile
    ) -> ScoreDimension:
        """Score company background fit."""
        experience = self._extract_experience(candidate)
        companies_worked = [job.get('company', {}) for job in experience]
        
        # Extract company names
        company_names = []
        for comp in companies_worked:
            if isinstance(comp, dict):
                name = comp.get('name', '')
            else:
                name = str(comp)
            if name:
                company_names.append(name.lower())
        
        baseline_companies = [c.lower() for c in baseline.company_clusters]
        
        # Check for matches
        matches = []
        for cand_company in company_names:
            for baseline_company in baseline_companies:
                if baseline_company in cand_company or cand_company in baseline_company:
                    matches.append(cand_company)
                    break
        
        # Score: 25 points per match, max 100
        score = min(len(matches) * 25, 100)
        
        # No hardcoded company tier bonuses - scoring is based entirely on
        # baseline company clusters from actual employee data
        
        if score == 0:
            score = 40  # Minimum score (company data may be incomplete)
        
        explanation = f"Worked at {len(matches)} companies in baseline cluster"
        evidence = [f"Company: {company}" for company in matches[:5]] if matches else ["No baseline company matches"]
        
        return ScoreDimension(
            dimension="company_background",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence
        )
    
    def _score_achievements(self, candidate: Dict[str, Any]) -> ScoreDimension:
        """Score quantified achievements and impact."""
        # Look for quantified achievements in experience descriptions
        experience = self._extract_experience(candidate)
        
        achievements = []
        for job in experience:
            desc = job.get('description', '')
            if not desc:
                continue
            
            # Look for numbers and impact words
            has_numbers = any(char.isdigit() for char in desc)
            impact_words = ['improved', 'increased', 'reduced', 'led', 'built', 'launched', 'scaled']
            has_impact = any(word in desc.lower() for word in impact_words)
            
            if has_numbers and has_impact:
                achievements.append(desc[:100])  # First 100 chars
        
        # Score based on number of quantified achievements
        score = min(len(achievements) * 20, 100)
        
        if score == 0:
            score = 50  # Default for no explicit achievements
        
        explanation = f"Found {len(achievements)} quantified achievements"
        evidence = achievements[:5] if achievements else ["No explicit quantified achievements found"]
        
        return ScoreDimension(
            dimension="achievements",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence
        )
    
    def _calculate_baseline_similarity(
        self,
        candidate: Dict[str, Any],
        baseline: BaselineProfile
    ) -> float:
        """Calculate overall similarity to baseline employees."""
        # Simple similarity based on:
        # - Skill overlap
        # - Experience proximity
        # - Company overlap
        
        cand_skills = set(s.lower() for s in self._extract_skills(candidate))
        baseline_skills = set(baseline.skill_distributions.keys())
        
        skill_overlap = len(cand_skills & baseline_skills) / max(len(baseline_skills), 1)
        
        years = self._extract_years_experience(candidate)
        exp_similarity = 1.0 - min(abs(years - baseline.average_years_experience) / 10.0, 1.0)
        
        # Average the similarities
        similarity = (skill_overlap + exp_similarity) / 2.0
        
        return similarity
    
    def _identify_patterns(
        self,
        candidate: Dict[str, Any],
        baseline: BaselineProfile
    ) -> List[str]:
        """Identify patterns this candidate matches."""
        patterns = []
        
        # Check career path patterns
        experience = self._extract_experience(candidate)
        if len(experience) >= 2:
            candidate_path = self._create_simple_path_signature(experience)
            for baseline_path in baseline.common_career_paths[:3]:
                if self._paths_similar(candidate_path, baseline_path.path_description):
                    patterns.append(baseline_path.path_description)
        
        # Check success patterns
        for success_pattern in baseline.success_patterns:
            # Simple keyword matching
            if 'startup' in success_pattern.lower():
                companies = [str(job.get('company', '')).lower() for job in experience]
                if any('startup' in c for c in companies):
                    patterns.append(success_pattern)
            elif 'progression' in success_pattern.lower():
                titles = [job.get('title', '').lower() for job in experience]
                if any('senior' in t or 'lead' in t for t in titles):
                    patterns.append(success_pattern)
        
        return patterns[:5]  # Top 5 patterns
    
    def _calculate_confidence(
        self,
        candidate: Dict[str, Any],
        dimensions: List[ScoreDimension]
    ) -> float:
        """Calculate confidence in scoring based on data completeness."""
        # Check data completeness
        has_skills = len(self._extract_skills(candidate)) > 0
        has_experience = len(self._extract_experience(candidate)) > 0
        has_name = bool(candidate.get('full_name') or candidate.get('name'))
        
        # Check dimension evidence quality
        avg_evidence_count = sum(len(d.evidence) for d in dimensions) / max(len(dimensions), 1)
        
        confidence = 0.0
        if has_name:
            confidence += 0.2
        if has_skills:
            confidence += 0.3
        if has_experience:
            confidence += 0.3
        if avg_evidence_count >= 3:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    # Helper methods
    
    def _extract_skills(self, data: Dict[str, Any]) -> List[str]:
        """Extract skills from candidate data."""
        skills = data.get('skills', [])
        
        if isinstance(skills, str):
            return [s.strip() for s in skills.split(',')]
        elif isinstance(skills, list):
            result = []
            for skill in skills:
                if isinstance(skill, dict):
                    result.append(skill.get('name', ''))
                else:
                    result.append(str(skill))
            return result
        
        return []
    
    def _extract_experience(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract experience from candidate data."""
        exp = data.get('experience', [])
        if isinstance(exp, list):
            return exp
        return []
    
    def _extract_years_experience(self, data: Dict[str, Any]) -> float:
        """Extract total years of experience."""
        # Try direct field
        years = data.get('years_experience')
        if years is not None:
            return float(years)
        
        # Calculate from experience entries
        experience = self._extract_experience(data)
        if not experience:
            return 0.0
        
        # Estimate: 2 years per role on average
        return len(experience) * 2.0
    
    def _create_simple_path_signature(self, experience: List[Dict[str, Any]]) -> str:
        """Create simple career path signature."""
        if not experience:
            return "Unknown"
        
        titles = [job.get('title', '').lower() for job in experience[-3:]]  # Last 3 roles
        simplified = []
        
        for title in titles:
            if 'lead' in title or 'principal' in title:
                simplified.append("Lead")
            elif 'senior' in title:
                simplified.append("Senior")
            else:
                simplified.append("IC")
        
        return " → ".join(simplified)
    
    def _paths_similar(self, path1: str, path2: str) -> bool:
        """Check if two career paths are similar."""
        # Simple keyword overlap
        words1 = set(path1.lower().split())
        words2 = set(path2.lower().split())
        
        overlap = len(words1 & words2)
        return overlap >= 2
    
    def _map_dimension_to_weight(self, dimension: str) -> str:
        """Map dimension name to weight key."""
        mapping = {
            "technical_skills": "technical_skills",
            "engineering_skills": "engineering_skills",
            "experience_level": "experience_level",
            "career_trajectory": "career_trajectory",
            "company_background": "company_background",
            "achievements": "achievements",
            # Backward compat: old dimension name still maps correctly
            "ml_skills": "technical_skills",
        }
        return mapping.get(dimension, dimension)

