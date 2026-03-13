# Advanced Candidate Analysis Features

## Overview

This document outlines advanced features for improving candidate identification and scoring in the HR Intelligence platform. These features leverage People Data Labs (PDL) and internal employee data to create more targeted searches and better scoring.

---

## 1. Career Trajectory Fingerprinting

### Concept
Build a "fingerprint" of ideal career paths by analyzing 1+ LinkedIn profiles of successful employees or target candidates. This fingerprint captures patterns that go beyond simple skill matching.

### How It Works
1. **User uploads LinkedIn URLs** of exemplary candidates/employees
2. **System enriches profiles** via PDL API
3. **Patterns are extracted**:
   - Company progression (startup → big tech → startup)
   - Role progression (IC → senior → staff → principal)
   - Industry transitions
   - Skill acquisition velocity
   - Education patterns
   - Average tenure at each company
4. **Fingerprint is stored** and can be selected when configuring an analysis
5. **PDL queries are enhanced** with fingerprint hints
6. **Scoring includes trajectory match** as a dimension

### Data Model
```python
CareerFingerprint:
  - name: str
  - description: str
  - source_profiles: List[LinkedInProfile]
  - company_progression: {pattern, sizes, industries}
  - role_progression: {pattern, avg_promotion_months}
  - skill_velocity: {skills_per_year, core_skills, recent_skills}
  - pdl_query_hints: {suggested_titles, suggested_skills, experience_range}
  - scoring_weights: Dict[dimension, weight]
```

### Impact
- More targeted PDL searches (find people with similar career paths)
- Better scoring (trajectory match dimension)
- User can define "what good looks like" without writing complex queries

---

## 2. Company DNA Matching

### Concept
Build a profile of what makes employees successful at a specific company by analyzing the current workforce. Use this DNA to find candidates who would fit the company culture and succeed.

### How It Works
1. **Analyze existing employees** in the database (PDL profiles)
2. **Extract patterns**:
   - Common backgrounds (FAANG alumni rate, startup experience rate)
   - Education profile (PhD rate, top school rate, common degrees)
   - Skill profile (core skills, emerging skills, skill diversity)
   - Company progression patterns
3. **Infer culture indicators**:
   - Pace (fast/moderate/steady based on avg tenure)
   - Technical depth
   - Remote-friendly signals
4. **Generate hiring preferences**:
   - Preferred source companies
   - Preferred backgrounds
   - Red flags to watch for
5. **Modify PDL queries** to boost candidates matching DNA

### Data Model
```python
CompanyDNAProfile:
  - company_name: str
  - company_website: str
  - workforce_dna: {
      avg_experience_years,
      common_backgrounds: {faang_alumni, startup_experience},
      skill_profile: {core_skills, emerging_skills}
    }
  - culture_indicators: {pace, technical_depth, remote_friendly}
  - hiring_preferences: {preferred_companies, preferred_skills}
  - pdl_query_modifiers: {boost_companies, boost_skills}
```

### For Caylent Specifically
- Company: Caylent
- Website: caylent.com
- Focus: AWS/Cloud consulting
- Employee data already in database from previous analyses

### Impact
- PDL searches automatically favor candidates from similar companies
- Scoring includes "company fit" based on DNA match
- Hiring managers understand what backgrounds succeed at their company

---

## 3. Skill Velocity Analysis

### Concept
Measure how quickly candidates acquire new skills and technologies. High skill velocity indicates adaptability and continuous learning.

### How It Works
1. **Analyze job history timeline** from PDL profiles
2. **Track skill acquisition**:
   - When did they add each skill?
   - How many new skills per year?
   - Are skills trending (recent) or stale?
3. **Calculate velocity score**:
   - Skills acquired per year
   - Recency of skill updates
   - Breadth vs depth ratio
4. **Use in scoring** as a dimension

### Metrics
- Skills per year: Average new skills added annually
- Recency score: How recent are their latest skills?
- Trend alignment: Do their recent skills match market trends?

### Impact
- Identify fast learners who can adapt to new technologies
- Distinguish between static and growing candidates
- Predict future skill acquisition potential

---

## 4. Advanced PDL Search Strategies

### Available PDL Fields for Targeting
```
- job_title / job_title_role / job_title_sub_role / job_title_levels
- job_company_name / job_company_size / job_company_industry
- location_name / location_region / location_country
- education_school_name / education_degree_name / education_major
- skills (array)
- experience_years_min / experience_years_max
- inferred_salary_min / inferred_salary_max
- linkedin_url / github_url
```

### Search Strategies

#### 1. Company Clustering
Search for candidates from companies similar to successful sources:
```python
{
  "job_company_name": ["stripe", "plaid", "square", "databricks"],
  "skills": ["python", "aws"],
  "experience_years_min": 5
}
```

#### 2. Experience-Bracketed Search
Target specific experience levels:
```python
{
  "job_title": ["senior software engineer", "staff engineer"],
  "experience_years_min": 5,
  "experience_years_max": 10,
  "job_company_size": ["51-200", "201-500"]  # Growth-stage companies
}
```

#### 3. Education-Filtered Search
Target specific educational backgrounds:
```python
{
  "education_school_name": ["stanford", "mit", "berkeley"],
  "education_major": ["computer science", "machine learning"],
  "job_title_role": "engineering"
}
```

#### 4. Geographic Clustering
Target specific regions:
```python
{
  "location_region": ["california", "washington", "new york"],
  "skills": ["kubernetes", "terraform"],
  "job_title_levels": ["senior", "manager"]
}
```

---

## Implementation Priority

### Phase 1: Company DNA (Immediate)
- Build Caylent company DNA profile from existing employees
- Integrate DNA into scoring engine
- Modify PDL queries based on DNA

### Phase 2: Career Fingerprinting (Next)
- Build UI for uploading LinkedIn profiles
- Implement fingerprint extraction
- Add fingerprint selection to analysis config
- Integrate into scoring

### Phase 3: Skill Velocity (Future)
- Add velocity calculation to scoring engine
- Create velocity visualization
- Use velocity in candidate ranking

---

## API Endpoints

### Career Fingerprints
- `POST /api/v1/career-fingerprints` - Create fingerprint from LinkedIn URLs
- `GET /api/v1/career-fingerprints` - List fingerprints
- `GET /api/v1/career-fingerprints/{id}` - Get fingerprint details
- `POST /api/v1/career-fingerprints/{id}/add-profile` - Add profile to fingerprint
- `DELETE /api/v1/career-fingerprints/{id}` - Delete fingerprint

### Company DNA
- `POST /api/v1/career-fingerprints/company-dna` - Create/update company DNA
- `GET /api/v1/career-fingerprints/company-dna` - List company DNA profiles
- `GET /api/v1/career-fingerprints/company-dna/{company_name}` - Get specific DNA

---

## Database Tables

### career_fingerprints
- id, customer_id, name, description
- source_profiles (JSON)
- company_progression, role_progression, skill_velocity (JSON)
- pdl_query_hints, scoring_weights (JSON)
- is_active, profile_count
- created_at, updated_at

### company_dna_profiles
- id, customer_id
- company_name, company_website, company_description
- workforce_dna, culture_indicators, success_patterns (JSON)
- hiring_preferences, pdl_query_modifiers (JSON)
- employee_count_analyzed
- last_analyzed_at, created_at, updated_at


