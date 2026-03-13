# Docling Resume Parsing Test Guide

## 📋 Overview

This guide shows you how to test and iterate on Docling resume parsing with a single PDF file.

The test script (`test_docling_parsing_isolated.py`) parses one resume and shows:
1. ✅ Raw Docling markdown output
2. ✅ Extracted structured data (contact, skills, experience, education)
3. ✅ Docling internal structure
4. ✅ PDL-normalized format
5. ✅ Quality assessment & issues

---

## 🚀 Option 1: Run in Docker (Recommended)

### Prerequisites
- Docker Desktop running
- App container running

### Steps

```bash
# 1. Start Docker containers
cd /Users/scottgay/Documents/Eliza/eliza-platform
docker-compose up -d app

# 2. Run the test (uses first resume in tests/resumes/)
./tests/run_docling_test.sh

# 3. Or test a specific resume
./tests/run_docling_test.sh tests/resumes/resume_ml_01.pdf

# 4. View output files
docker cp $(docker-compose ps -q app):/app/full_markdown_output.txt .
docker cp $(docker-compose ps -q app):/app/docling_full_output.json .
docker cp $(docker-compose ps -q app):/app/parsed_resume_pdl_format.json .
```

---

## 🐍 Option 2: Run Locally (Faster Iteration)

### Setup Python Environment

```bash
# 1. Create virtual environment
cd /Users/scottgay/Documents/Eliza/eliza-platform
python3 -m venv venv

# 2. Activate it
source venv/bin/activate

# 3. Install dependencies
pip install docling docling-core structlog pydantic

# 4. Run test
python3 tests/test_docling_parsing_isolated.py

# Or test specific resume
python3 tests/test_docling_parsing_isolated.py tests/resumes/resume_ml_05.pdf

# 5. View output files (created in current directory)
cat full_markdown_output.txt
cat docling_full_output.json
cat parsed_resume_pdl_format.json
```

---

## 📊 Understanding the Output

### 1. Raw Markdown Output (`full_markdown_output.txt`)

This is Docling's interpretation of the PDF structure:

```markdown
# John Doe

john.doe@email.com | (555) 123-4567 | linkedin.com/in/johndoe

## Summary
Experienced software engineer with 10 years in...

## Skills
Python, JavaScript, AWS, Docker, Kubernetes

## Experience

### Senior Software Engineer at Google
2020 - Present

- Led team of 5 engineers...
- Built scalable microservices...

### Software Engineer at Facebook
2015 - 2020

- Developed React components...
```

**What to look for:**
- ✅ Is the structure preserved (headings, sections)?
- ✅ Is text in the right order?
- ⚠️  Are tables/columns properly parsed?
- ⚠️  Are special characters preserved?

### 2. Docling Full Output (`docling_full_output.json`)

Docling's internal representation with bounding boxes, fonts, layout:

```json
{
  "pages": [
    {
      "page_number": 1,
      "elements": [
        {
          "type": "heading",
          "text": "John Doe",
          "bbox": [100, 50, 500, 80],
          "font_size": 24
        }
      ]
    }
  ]
}
```

**What to look for:**
- ✅ Element types (heading, paragraph, list, table)
- ✅ Text extraction quality
- ⚠️  Layout detection accuracy

### 3. Parsed Resume (Console Output)

The script shows extracted structured data:

```
📧 CONTACT INFORMATION:
  Full Name: John Doe
  Email: john.doe@email.com
  Phone: (555) 123-4567
  LinkedIn: https://linkedin.com/in/johndoe

🛠️  SKILLS:
  Found 15 skills:
    1. Python
    2. JavaScript
    3. AWS
    ...

💼 WORK EXPERIENCE:
  Found 3 positions:
  
  Position 1:
    Title: Senior Software Engineer
    Company: Google
    Dates: 2020 - Present
    Description: Led team of 5 engineers...
```

### 4. PDL-Normalized Format (`parsed_resume_pdl_format.json`)

Resume data in PDL format (compatible with talent scoring):

```json
{
  "id": "resume_12345",
  "full_name": "John Doe",
  "emails": [{"address": "john.doe@email.com"}],
  "skills": [
    {"name": "Python"},
    {"name": "JavaScript"}
  ],
  "experience": [
    {
      "title": {"name": "Senior Software Engineer"},
      "company": {"name": "Google"},
      "start_date": "2020",
      "is_current": true
    }
  ]
}
```

---

## 🔧 Iterating on Parsing Quality

### Common Issues & Fixes

#### Issue 1: Skills Not Extracted

**Problem:** `Skills: 0 found`

**Diagnosis:** Check `full_markdown_output.txt` - does it have a "Skills" section?

**Fix in `docling_parser.py`:**

```python
# Current regex
skills_pattern = r'(?i)(skills|technical skills|core competencies|technologies)(.*?)(?=\n\n|\n#|$)'

# Add more variations
skills_pattern = r'(?i)(skills|technical skills|core competencies|technologies|expertise|proficiencies)(.*?)(?=\n\n|\n#|$)'
```

#### Issue 2: Name Not Extracted

**Problem:** `Full Name: None`

**Diagnosis:** Name might not be in first 10 lines or in unexpected format.

**Fix in `docling_parser.py`:**

```python
# _extract_contact_info method
# Expand search to first 20 lines
for line in lines[:20]:  # Was lines[:10]
    ...
```

#### Issue 3: Experience Dates Missing

**Problem:** `Dates: None - None`

**Diagnosis:** Date format not matching regex pattern.

**Fix in `docling_parser.py`:**

```python
# Current pattern
date_pattern = r'(\w+\s+)?(\d{4})\s*[-–]\s*(\w+\s+)?(\d{4}|Present|Current)'

# Support more formats: "Jan 2020 - Dec 2023", "2020-01 to 2023-12"
date_pattern = r'(\w+[\s-])?(\d{4})[\s-]*[-–to]+[\s-]*(\w+[\s-])?(\d{4}|Present|Current|Now)'
```

#### Issue 4: Company/Title Not Separated

**Problem:** `Company: Senior Software Engineer at Google` (should be in title field)

**Diagnosis:** Parsing logic not handling format correctly.

**Fix in `docling_parser.py`:**

```python
# _extract_experience method
# Add more separator variations
if ' at ' in first_line:
    parts = first_line.split(' at ')
    job_data['title'] = parts[0].strip()
    job_data['company'] = parts[1].strip()
elif ' | ' in first_line:
    parts = first_line.split(' | ')
    job_data['title'] = parts[0].strip()
    job_data['company'] = parts[1].strip()
elif ' - ' in first_line:
    parts = first_line.split(' - ', 1)
    job_data['title'] = parts[0].strip()
    job_data['company'] = parts[1].strip()
```

---

## 📝 Testing Workflow

### 1. Initial Test

```bash
# Parse first resume
python3 tests/test_docling_parsing_isolated.py

# Check quality assessment
# Look for warnings: "⚠️  No skills extracted"
```

### 2. Review Raw Markdown

```bash
# Open markdown output
cat full_markdown_output.txt

# Check:
# - Is "Skills" section present?
# - What format is it in?
# - Are dates in a different format?
```

### 3. Update Regex Patterns

```bash
# Edit the parser
vim src/services/resume_processing/docling_parser.py

# Update relevant regex in:
# - _extract_skills()
# - _extract_experience()
# - _extract_education()
# - _extract_contact_info()
```

### 4. Re-test

```bash
# Run test again
python3 tests/test_docling_parsing_isolated.py

# Compare results
# Did quality improve?
```

### 5. Test with Multiple Resumes

```bash
# Test different resumes to ensure changes work broadly
python3 tests/test_docling_parsing_isolated.py tests/resumes/resume_ml_01.pdf
python3 tests/test_docling_parsing_isolated.py tests/resumes/resume_ml_10.pdf
python3 tests/test_docling_parsing_isolated.py tests/resumes/resume_ml_25.pdf
```

---

## 🎯 Quality Metrics

Track these metrics as you improve parsing:

| Metric | Target | Current |
|--------|--------|---------|
| Name Extraction | 95%+ | ? |
| Email Extraction | 90%+ | ? |
| Skills Extraction | 80%+ | ? |
| Experience Extraction | 85%+ | ? |
| Education Extraction | 80%+ | ? |
| Date Parsing | 75%+ | ? |

Run tests on all 50 resumes and calculate:

```bash
# Quick test all resumes
for resume in tests/resumes/*.pdf; do
    echo "Testing: $(basename $resume)"
    python3 tests/test_docling_parsing_isolated.py "$resume" | grep "QUALITY ASSESSMENT" -A 10
done
```

---

## 🔍 Advanced: LLM-Based Parsing

If regex parsing quality is poor, consider using an LLM to extract structured data from the markdown:

```python
# In docling_parser.py

def _extract_with_llm(self, markdown_text: str) -> Dict[str, Any]:
    """
    Use OpenAI to extract structured data from markdown.
    
    More accurate but slower and costs API credits.
    """
    from openai import OpenAI
    
    client = OpenAI()
    
    prompt = f"""
Extract structured data from this resume in JSON format:

{markdown_text}

Return JSON with:
- full_name
- email
- phone
- skills (array)
- experience (array of objects with title, company, start_date, end_date)
- education (array)
"""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)
```

---

## 📚 Resources

- **Docling Docs**: https://github.com/docling-project/docling
- **Regex Testing**: https://regex101.com/
- **Our Parser**: `src/services/resume_processing/docling_parser.py`
- **Test Script**: `tests/test_docling_parsing_isolated.py`

---

## 🎉 Summary

You now have a complete workflow to:

1. ✅ Parse a single resume in isolation
2. ✅ View detailed output at each stage
3. ✅ Identify parsing issues
4. ✅ Iterate on regex patterns
5. ✅ Test improvements quickly
6. ✅ Scale to all 50 resumes

**Start testing:**

```bash
python3 tests/test_docling_parsing_isolated.py
```

Good luck! 🚀

