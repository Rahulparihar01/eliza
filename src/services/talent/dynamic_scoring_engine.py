"""
Dynamic Scoring Engine

Role-agnostic scoring engine that uses Career Blueprints and Company DNA
instead of hardcoded skill lists. Enables flexible scoring across any role type.

Dimensions:
1. Skill Alignment - Match to blueprint skill profile
2. Experience Fit - Years and depth vs blueprint expectations
3. Trajectory Match - Career progression vs blueprint patterns
4. Company Background - Previous companies vs blueprint/DNA patterns
5. Organizational Fit - Match to Company DNA profile
"""
from typing import Dict, Any, List, Optional
import structlog

from src.models.talent_analysis import (
    CandidateScore,
    ScoreDimension,
    CandidateSource,
    BaselineProfile,
    DiagnosticReport,
)
from src.models.talent_config import CareerBlueprint, CompanyDNAProfile

logger = structlog.get_logger(__name__)


class DynamicScoringEngine:
    """
    Dynamic scoring engine that uses blueprints and DNA profiles.
    
    No hardcoded skill lists - everything derived from:
    1. Career Blueprint (from look-alike profiles)
    2. Company DNA (from organizational patterns)
    3. Job description requirements (via baseline)
    """
    
    # Default weights if not specified in blueprint
    DEFAULT_WEIGHTS = {
        "skill_alignment": 0.30,
        "experience_fit": 0.20,
        "trajectory_match": 0.20,
        "company_background": 0.15,
        "organizational_fit": 0.15
    }
    
    def __init__(
        self,
        blueprint: Optional[CareerBlueprint] = None,
        company_dna: Optional[CompanyDNAProfile] = None
    ):
        """
        Initialize scoring engine with optional blueprint and DNA.
        
        Args:
            blueprint: Career Blueprint for trajectory/skill matching
            company_dna: Company DNA for organizational fit scoring
        """
        self.blueprint = blueprint
        self.company_dna = company_dna
        self.logger = logger.bind(
            service="dynamic_scoring",
            blueprint_id=blueprint.id if blueprint else None,
            dna_id=company_dna.id if company_dna else None
        )
        
        # Extract weights from blueprint or use defaults
        if blueprint and blueprint.scoring_weights:
            self.weights = {**self.DEFAULT_WEIGHTS, **blueprint.scoring_weights}
        else:
            self.weights = self.DEFAULT_WEIGHTS
        
        # Extract skill profile from blueprint
        self.target_skills = set()
        self.core_skills = set()
        if blueprint and blueprint.skill_profile:
            sp = blueprint.skill_profile
            self.core_skills = set(sp.get("core_skills", []))
            self.target_skills = self.core_skills | set(sp.get("common_skills", []))
        
        # Extract target companies from blueprint and DNA
        self.target_companies = set()
        if blueprint and blueprint.company_progression:
            self.target_companies.update(
                blueprint.company_progression.get("common_companies", [])
            )
        if company_dna and company_dna.success_patterns:
            self.target_companies.update(
                company_dna.success_patterns.get("common_previous_companies", [])
            )
        
        # Extract experience expectations
        self.exp_profile = {}
        if blueprint and blueprint.experience_profile:
            self.exp_profile = blueprint.experience_profile
    
    def score_candidate(
        self,
        candidate_data: Dict[str, Any],
        baseline: BaselineProfile,
        candidate_source: CandidateSource,
        candidate_id: str,
        diagnostic: Optional[DiagnosticReport] = None
    ) -> CandidateScore:
        """
        Score a candidate using blueprint and DNA patterns.
        
        Args:
            candidate_data: Parsed resume data or PDL person data
            baseline: Baseline profile for additional context
            candidate_source: 'applicant' or 'market'
            candidate_id: Unique candidate identifier
            diagnostic: Optional diagnostic report with JD-extracted required/preferred skills
            
        Returns:
            CandidateScore with dimension breakdowns
        """
        try:
            self.logger.info(
                "Scoring candidate dynamically",
                candidate_id=candidate_id,
                source=candidate_source,
                has_blueprint=self.blueprint is not None,
                has_dna=self.company_dna is not None,
                has_diagnostic=diagnostic is not None
            )
            
            # Enrich target skills from diagnostic report (JD-extracted)
            if diagnostic:
                for skill in (diagnostic.required_skills or []):
                    skill_lower = skill.lower().strip()
                    if skill_lower and skill_lower not in self.core_skills:
                        self.core_skills.add(skill_lower)
                        self.target_skills.add(skill_lower)
                for skill in (diagnostic.preferred_skills or []):
                    skill_lower = skill.lower().strip()
                    if skill_lower:
                        self.target_skills.add(skill_lower)
            
            dimensions = []
            
            # 1. Skill Alignment
            skill_score = self._score_skill_alignment(candidate_data, baseline)
            dimensions.append(skill_score)
            
            # 2. Experience Fit
            exp_score = self._score_experience_fit(candidate_data, baseline)
            dimensions.append(exp_score)
            
            # 3. Trajectory Match
            traj_score = self._score_trajectory_match(candidate_data)
            dimensions.append(traj_score)
            
            # 4. Company Background
            company_score = self._score_company_background(candidate_data)
            dimensions.append(company_score)
            
            # 5. Organizational Fit
            org_score = self._score_organizational_fit(candidate_data)
            dimensions.append(org_score)
            
            # Calculate weighted overall score
            overall_score = 0.0
            for dim in dimensions:
                weight = self.weights.get(dim.dimension, 0.10)
                overall_score += (dim.score / 100.0) * weight
            
            overall_score = overall_score * 100.0
            
            # Calculate similarities and patterns
            baseline_similarity = self._calculate_baseline_similarity(candidate_data, baseline)
            patterns_matched = self._identify_patterns(candidate_data)
            confidence = self._calculate_confidence(candidate_data, dimensions)
            
            # Extract profile data
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
                error=str(e),
                exc_info=True,
                candidate_data_keys=list(candidate_data.keys()) if candidate_data else []
            )
            # Re-raise so the orchestrator can handle it properly
            # This ensures we don't silently produce 0-score candidates
            raise
    
    def _score_skill_alignment(
        self,
        candidate: Dict[str, Any],
        baseline: BaselineProfile
    ) -> ScoreDimension:
        """Score skill alignment with blueprint and baseline."""
        cand_skills = self._extract_skills(candidate)
        # Safely convert to lowercase, filtering out any None values
        cand_skills_lower = set(s.lower() for s in cand_skills if s and isinstance(s, str))
        
        # Combine target skills from blueprint and baseline
        target_skills = self.target_skills.copy()
        target_skills.update(baseline.skill_distributions.keys())
        
        if not target_skills:
            # Fallback: no target skills defined
            return ScoreDimension(
                dimension="skill_alignment",
                score=50.0,
                explanation="No target skill profile defined",
                evidence=["Using default scoring"]
            )
        
        # Calculate matches
        core_matches = cand_skills_lower & self.core_skills
        all_matches = cand_skills_lower & target_skills
        
        # Score: core skills worth more
        core_score = len(core_matches) / max(len(self.core_skills), 1) * 60
        other_score = len(all_matches - core_matches) / max(len(target_skills - self.core_skills), 1) * 40
        
        score = min(core_score + other_score, 100)
        
        # Minimum score of 20 if they have any relevant skills
        if all_matches and score < 20:
            score = 20
        
        explanation = f"Matched {len(all_matches)} of {len(target_skills)} target skills"
        evidence = [f"Core: {skill}" for skill in list(core_matches)[:5]]
        evidence.extend([f"Skill: {skill}" for skill in list(all_matches - core_matches)[:5]])
        
        return ScoreDimension(
            dimension="skill_alignment",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence if evidence else ["No matching skills found"]
        )
    
    def _score_experience_fit(
        self,
        candidate: Dict[str, Any],
        baseline: BaselineProfile
    ) -> ScoreDimension:
        """Score experience level fit."""
        years = self._extract_years_experience(candidate)
        
        # Get target experience from blueprint or baseline
        target_avg = self.exp_profile.get("avg_years", baseline.average_years_experience)
        target_min = self.exp_profile.get("min_years", max(0, target_avg - 3))
        target_max = self.exp_profile.get("max_years", target_avg + 5)
        
        # Score based on fit within range
        if target_min <= years <= target_max:
            # Perfect fit - closer to avg is better
            diff_from_avg = abs(years - target_avg)
            score = 100 - (diff_from_avg * 5)  # -5 per year from avg
            score = max(score, 80)  # Minimum 80 if in range
        elif years < target_min:
            # Under-experienced
            gap = target_min - years
            score = max(40 - (gap * 10), 10)
        else:
            # Over-experienced
            gap = years - target_max
            score = max(70 - (gap * 5), 30)  # Over-experience less penalized
        
        # Bonus for depth (multiple roles)
        experience = self._extract_experience(candidate)
        role_count = len(experience)
        expected_roles = self.exp_profile.get("avg_role_count", 3)
        
        if role_count >= expected_roles:
            score = min(score + 10, 100)
        
        explanation = f"{years} years experience (target: {target_min:.0f}-{target_max:.0f})"
        evidence = [
            f"Total experience: {years} years",
            f"Career roles: {role_count}",
            f"Target range: {target_min:.0f}-{target_max:.0f} years"
        ]
        
        return ScoreDimension(
            dimension="experience_fit",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence
        )
    
    def _score_trajectory_match(self, candidate: Dict[str, Any]) -> ScoreDimension:
        """Score career trajectory match with blueprint patterns."""
        experience = self._extract_experience(candidate)
        
        if len(experience) < 2:
            return ScoreDimension(
                dimension="trajectory_match",
                score=50.0,
                explanation="Limited career history",
                evidence=["Less than 2 roles in history"]
            )
        
        score = 50  # Base score
        matches = []
        
        # Get blueprint trajectory patterns
        if self.blueprint and self.blueprint.role_progression:
            rp = self.blueprint.role_progression
            
            # Check title progression - safely handle None titles
            titles = [(job.get('title') or '').lower() for job in experience]
            
            # Check common titles
            common_titles = set(rp.get("common_titles", []))
            title_matches = sum(1 for t in titles if any(ct in t for ct in common_titles))
            if title_matches > 0:
                score += min(title_matches * 10, 25)
                matches.append(f"Matched {title_matches} common titles")
            
            # Check progression pattern
            pattern = rp.get("pattern", "")
            if "Lead" in pattern or "Staff" in pattern:
                if any('lead' in t or 'staff' in t or 'principal' in t for t in titles):
                    score += 15
                    matches.append("Reached leadership level (matches pattern)")
            
            if "Senior" in pattern:
                if any('senior' in t for t in titles):
                    score += 10
                    matches.append("Reached senior level (matches pattern)")
        else:
            # No blueprint - use generic progression scoring
            titles = [(job.get('title') or '').lower() for job in experience]
            
            if any('lead' in t or 'principal' in t or 'staff' in t for t in titles):
                score += 20
                matches.append("Leadership/senior IC level achieved")
            elif any('senior' in t for t in titles):
                score += 10
                matches.append("Senior level achieved")
        
        score = min(score, 100)
        
        explanation = f"{len(matches)} trajectory patterns matched"
        evidence = matches if matches else ["No specific trajectory patterns matched"]
        
        return ScoreDimension(
            dimension="trajectory_match",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence
        )
    
    def _score_company_background(self, candidate: Dict[str, Any]) -> ScoreDimension:
        """Score company background against blueprint and DNA patterns."""
        experience = self._extract_experience(candidate)
        
        # Extract companies from candidate - safely handle None values
        candidate_companies = set()
        for job in experience:
            company = job.get('company', {})
            if isinstance(company, dict):
                name = (company.get('name') or '').lower()
            elif company is not None:
                name = str(company).lower()
            else:
                name = ''
            if name:
                candidate_companies.add(name)
        
        if not self.target_companies:
            # No target companies defined - use generic scoring
            top_tier = {'google', 'facebook', 'meta', 'amazon', 'microsoft', 'apple', 'netflix', 'stripe', 'airbnb'}
            matches = [c for c in candidate_companies if any(t in c for t in top_tier)]
            
            if matches:
                return ScoreDimension(
                    dimension="company_background",
                    score=70.0,
                    explanation=f"Worked at {len(matches)} notable companies",
                    evidence=[f"Company: {c}" for c in matches[:5]]
                )
            return ScoreDimension(
                dimension="company_background",
                score=50.0,
                explanation="No target company profile defined",
                evidence=["Using default scoring"]
            )
        
        # Check for matches with target companies
        matches = []
        for cand_company in candidate_companies:
            if not cand_company:
                continue
            for target in self.target_companies:
                if not target or not isinstance(target, str):
                    continue
                if target.lower() in cand_company or cand_company in target.lower():
                    matches.append(cand_company)
                    break
        
        # Score: 20 points per match, max 100
        score = min(len(matches) * 20, 80)
        
        # Bonus for DNA boost companies
        if self.company_dna and self.company_dna.pdl_query_modifiers:
            boost_companies = self.company_dna.pdl_query_modifiers.get("boost_companies", [])
            # Filter out None/empty values and safely call .lower()
            dna_matches = [c for c in candidate_companies if c and any(
                b.lower() in c for b in boost_companies if b and isinstance(b, str)
            )]
            if dna_matches:
                score = min(score + 20, 100)
                matches.extend([f"DNA boost: {c}" for c in dna_matches[:2]])
        
        # Minimum score
        if score == 0:
            score = 30
        
        explanation = f"Matched {len(matches)} target companies"
        evidence = [f"Company: {c}" for c in matches[:5]] if matches else ["No target company matches"]
        
        return ScoreDimension(
            dimension="company_background",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence
        )
    
    def _score_organizational_fit(self, candidate: Dict[str, Any]) -> ScoreDimension:
        """Score organizational fit using Company DNA."""
        if not self.company_dna or not self.company_dna.workforce_dna:
            return ScoreDimension(
                dimension="organizational_fit",
                score=50.0,
                explanation="No Company DNA profile available",
                evidence=["Using default organizational fit score"]
            )
        
        dna = self.company_dna.workforce_dna
        score = 50  # Base score
        fit_signals = []
        
        # Experience fit
        candidate_years = self._extract_years_experience(candidate)
        dna_avg_years = dna.get("avg_experience_years", 5)
        exp_diff = abs(candidate_years - dna_avg_years)
        
        if exp_diff <= 2:
            score += 15
            fit_signals.append(f"Experience aligns with org avg ({dna_avg_years:.0f} yrs)")
        elif exp_diff <= 4:
            score += 8
        
        # Skill fit - safely handle None values
        cand_skills = set(s.lower() for s in self._extract_skills(candidate) if s and isinstance(s, str))
        dna_core_skills = set(s for s in dna.get("skill_profile", {}).get("core_skills", []) if s and isinstance(s, str))
        
        if dna_core_skills:
            skill_overlap = len(cand_skills & dna_core_skills) / len(dna_core_skills)
            if skill_overlap >= 0.5:
                score += 20
                fit_signals.append(f"Strong skill overlap ({skill_overlap:.0%})")
            elif skill_overlap >= 0.25:
                score += 10
                fit_signals.append(f"Moderate skill overlap ({skill_overlap:.0%})")
        
        # Background fit - safely handle None values
        experience = self._extract_experience(candidate)
        candidate_companies = []
        for job in experience:
            company = job.get('company', {})
            if isinstance(company, dict):
                name = company.get('name') or ''
            else:
                name = str(company) if company else ''
            if name:
                candidate_companies.append(name.lower())
        
        common_backgrounds = dna.get("common_backgrounds", {})
        
        # Check FAANG background
        faang = {'google', 'facebook', 'meta', 'amazon', 'microsoft', 'apple', 'netflix'}
        has_faang = any(any(f in c for f in faang) for c in candidate_companies)
        if has_faang:
            faang_rate = common_backgrounds.get("faang_alumni_rate", 0)
            if faang_rate >= 0.1:  # If org values FAANG background
                score += 15
                fit_signals.append("FAANG background (valued by org)")
        
        score = min(score, 100)
        
        explanation = f"Organizational fit based on {len(fit_signals)} signals"
        evidence = fit_signals if fit_signals else ["No strong organizational fit signals"]
        
        return ScoreDimension(
            dimension="organizational_fit",
            score=round(score, 2),
            explanation=explanation,
            evidence=evidence
        )
    
    def _calculate_baseline_similarity(
        self,
        candidate: Dict[str, Any],
        baseline: BaselineProfile
    ) -> float:
        """Calculate similarity to baseline profile."""
        cand_skills = set(s.lower() for s in self._extract_skills(candidate) if s and isinstance(s, str))
        baseline_skills = set(baseline.skill_distributions.keys())
        
        if not baseline_skills:
            return 0.5
        
        skill_overlap = len(cand_skills & baseline_skills) / len(baseline_skills)
        
        years = self._extract_years_experience(candidate)
        exp_similarity = 1.0 - min(abs(years - baseline.average_years_experience) / 10.0, 1.0)
        
        return (skill_overlap + exp_similarity) / 2.0
    
    def _identify_patterns(self, candidate: Dict[str, Any]) -> List[str]:
        """Identify patterns matched by this candidate."""
        patterns = []
        
        if not self.blueprint:
            return patterns
        
        experience = self._extract_experience(candidate)
        
        # Check role progression pattern
        if self.blueprint.role_progression:
            pattern = self.blueprint.role_progression.get("pattern", "")
            if pattern:
                titles = [(job.get('title') or '').lower() for job in experience]
                
                if "Lead" in pattern and any('lead' in t or 'staff' in t for t in titles):
                    patterns.append(f"Career pattern: {pattern}")
                elif "Senior" in pattern and any('senior' in t for t in titles):
                    patterns.append(f"Career pattern: {pattern}")
        
        # Check company progression pattern
        if self.blueprint.company_progression:
            cp = self.blueprint.company_progression
            common_companies = cp.get("common_companies", [])
            
            candidate_companies = set()
            for job in experience:
                company = job.get('company', {})
                name = (company.get('name') or '') if isinstance(company, dict) else (str(company) if company else '')
                if name:
                    candidate_companies.add(name.lower())
            
            # Safely handle None values in common_companies
            matches = [c for c in common_companies if c and isinstance(c, str) and c.lower() in ' '.join(candidate_companies)]
            if matches:
                patterns.append(f"Company pattern: worked at {', '.join(matches[:3])}")
        
        return patterns[:5]
    
    def _calculate_confidence(
        self,
        candidate: Dict[str, Any],
        dimensions: List[ScoreDimension]
    ) -> float:
        """Calculate confidence in scoring."""
        has_skills = len(self._extract_skills(candidate)) > 0
        has_experience = len(self._extract_experience(candidate)) > 0
        has_name = bool(candidate.get('full_name') or candidate.get('name'))
        has_blueprint = self.blueprint is not None
        has_dna = self.company_dna is not None
        
        avg_evidence = sum(len(d.evidence) for d in dimensions) / max(len(dimensions), 1)
        
        confidence = 0.0
        if has_name:
            confidence += 0.15
        if has_skills:
            confidence += 0.25
        if has_experience:
            confidence += 0.25
        if has_blueprint:
            confidence += 0.15
        if has_dna:
            confidence += 0.10
        if avg_evidence >= 3:
            confidence += 0.10
        
        return min(confidence, 1.0)
    
    # Helper methods
    
    def _extract_skills(self, data: Dict[str, Any]) -> List[str]:
        """Extract skills from candidate data."""
        skills = data.get('skills', [])
        
        if isinstance(skills, str):
            return [s.strip() for s in skills.split(',') if s.strip()]
        elif isinstance(skills, list):
            result = []
            for skill in skills:
                if isinstance(skill, dict):
                    name = skill.get('name')
                    if name and isinstance(name, str):
                        result.append(name)
                elif skill is not None:
                    skill_str = str(skill).strip()
                    if skill_str:
                        result.append(skill_str)
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
        years = data.get('years_experience') or data.get('inferred_years_experience')
        if years is not None:
            return float(years)
        
        experience = self._extract_experience(data)
        if not experience:
            return 0.0
        
        return len(experience) * 2.0  # Estimate 2 years per role

