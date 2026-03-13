# Docling Resume Parsing - Iteration & Testing Setup

## 📋 What We Built

Created an **isolated testing environment** for iterating on Docling resume parsing quality.

### Key Components

1. **`tests/test_docling_parsing_isolated.py`** - Standalone test script
   - Parses a single resume
   - Shows output at each stage
   - Saves detailed files for analysis

2. **`tests/run_docling_test.sh`** - Docker wrapper script
   - Runs test inside app container
   - Handles environment setup automatically

3. **`tests/DOCLING_TESTING_GUIDE.md`** - Complete documentation
   - Setup instructions (Docker & local)
   - How to interpret output
   - Common issues & fixes
   - Iteration workflow

---

## 🎯 Purpose

**Problem:** Need to improve resume parsing quality but testing the full pipeline is slow.

**Solution:** Test parsing in isolation with one PDF, iterate quickly.

---

## 🚀 Quick Start

### Option 1: Local (Fastest)

```bash
# Setup once
cd /Users/scottgay/Documents/Eliza/eliza-platform
python3 -m venv venv
source venv/bin/activate
pip install docling docling-core structlog pydantic

# Test parsing
python3 tests/test_docling_parsing_isolated.py

# Or specific resume
python3 tests/test_docling_parsing_isolated.py tests/resumes/resume_ml_05.pdf
```

### Option 2: Docker

```bash
# Start containers
docker-compose up -d app

# Run test
./tests/run_docling_test.sh

# Get output files
docker cp $(docker-compose ps -q app):/app/full_markdown_output.txt .
```

---

## 📊 What You'll See

### Terminal Output

```
================================================================================
  DOCLING RESUME PARSING TEST
================================================================================
Resume: resume_ml_01.pdf
Path: /Users/.../tests/resumes/resume_ml_01.pdf
File size: 245,678 bytes

================================================================================
  STEP 1: DOCLING DOCUMENT CONVERSION
================================================================================
Converting PDF to structured format with Docling...
✓ Conversion complete

================================================================================
  STEP 2: RAW MARKDOWN OUTPUT
================================================================================
# John Doe

john.doe@email.com | (555) 123-4567

## Summary
Experienced software engineer...

## Skills
Python, JavaScript, AWS, Docker...

## Experience

### Senior Software Engineer at Google
2020 - Present
...

================================================================================
  STEP 3: EXTRACTED STRUCTURED DATA
================================================================================

📧 CONTACT INFORMATION:
  Full Name: John Doe
  First Name: John
  Last Name: Doe
  Email: john.doe@email.com
  Phone: (555) 123-4567
  LinkedIn: https://linkedin.com/in/johndoe
  GitHub: https://github.com/johndoe

💼 PROFESSIONAL SUMMARY:
  Experienced software engineer with 10 years...

🛠️  SKILLS:
  Found 15 skills:
    1. Python
    2. JavaScript
    3. AWS
    4. Docker
    5. Kubernetes
    ...

💼 WORK EXPERIENCE:
  Found 3 positions:

  Position 1:
    Title: Senior Software Engineer
    Company: Google
    Dates: 2020 - Present
    Description: Led team of 5 engineers...

  Position 2:
    Title: Software Engineer
    Company: Facebook
    Dates: 2015 - 2020
    Description: Developed React components...

🎓 EDUCATION:
  Found 2 entries:

  Education 1:
    Degree: Bachelor of Science in Computer Science
    School: MIT
    Year: 2015

📜 CERTIFICATIONS:
  Found 3 certifications:
    1. AWS Certified Solutions Architect
    2. Google Cloud Professional
    3. Certified Kubernetes Administrator

================================================================================
  PARSING SUMMARY
================================================================================
✓ Resume parsed successfully
  Contact info: ✓
  Skills: 15 found
  Experience: 3 positions
  Education: 2 degrees
  Certifications: 3 found

📁 OUTPUT FILES:
  - full_markdown_output.txt (raw Docling markdown)
  - docling_full_output.json (full Docling structure)
  - parsed_resume_pdl_format.json (normalized PDL format)

================================================================================
  QUALITY ASSESSMENT
================================================================================
✓ All expected fields extracted successfully

================================================================================
  NEXT STEPS
================================================================================
1. Review the output files to understand what Docling is extracting
2. Check full_markdown_output.txt to see the raw structure
3. If parsing quality is poor, improve regex patterns in:
   src/services/resume_processing/docling_parser.py
4. Re-run this script to test improvements
```

### Output Files

1. **`full_markdown_output.txt`** - Raw Docling markdown
2. **`docling_full_output.json`** - Full Docling structure with layout data
3. **`parsed_resume_pdl_format.json`** - Final normalized format

---

## 🔧 Iteration Workflow

### 1. Run Initial Test

```bash
python3 tests/test_docling_parsing_isolated.py
```

Look for warnings in "QUALITY ASSESSMENT":
- ⚠️  Name not extracted
- ⚠️  Email not extracted
- ⚠️  No skills extracted
- ⚠️  No work experience extracted

### 2. Review Raw Markdown

```bash
cat full_markdown_output.txt
```

**Ask yourself:**
- Is the "Skills" section present?
- What format are the dates in?
- How is experience structured?
- Are section headers different than expected?

### 3. Update Parser

Edit `src/services/resume_processing/docling_parser.py`:

```python
# Example: Improve skills extraction
def _extract_skills(self, text: str) -> List[str]:
    # Add more section header variations
    skills_pattern = r'(?i)(skills|technical skills|core competencies|technologies|expertise|technical expertise)(.*?)(?=\n\n|\n#|$)'
    ...
```

### 4. Re-test

```bash
python3 tests/test_docling_parsing_isolated.py
```

**Check:**
- Did the warning go away?
- Are more skills extracted?
- Is quality better?

### 5. Test Multiple Resumes

```bash
# Test 5 random resumes
python3 tests/test_docling_parsing_isolated.py tests/resumes/resume_ml_01.pdf
python3 tests/test_docling_parsing_isolated.py tests/resumes/resume_ml_15.pdf
python3 tests/test_docling_parsing_isolated.py tests/resumes/resume_ml_30.pdf
python3 tests/test_docling_parsing_isolated.py tests/resumes/resume_ml_42.pdf
python3 tests/test_docling_parsing_isolated.py tests/resumes/resume_ml_50.pdf
```

Ensure changes work across different resume formats!

---

## 🎯 Common Issues & Fixes

### Issue: "No skills extracted"

**Diagnosis:**
```bash
cat full_markdown_output.txt | grep -i skill
```

If skills section exists but not extracted:
- Section header might be different ("Technical Expertise" vs "Skills")
- Skills might be in table format (not just comma-separated)

**Fix:**
Update `_extract_skills()` regex pattern to match actual format.

### Issue: "Name not extracted"

**Diagnosis:**
```bash
head -20 full_markdown_output.txt
```

Name might be:
- Beyond first 10 lines
- In all caps: "JOHN DOE"
- With title: "John Doe, Ph.D."

**Fix:**
Update `_extract_contact_info()` to:
- Check more lines
- Handle different formats

### Issue: "Experience dates missing"

**Diagnosis:**
```bash
cat full_markdown_output.txt | grep -A 3 "Experience"
```

Dates might be in format:
- "Jan 2020 - Dec 2023"
- "2020-01 to 2023-12"
- "2020 – 2023" (different dash character)

**Fix:**
Update date regex in `_extract_experience()`.

---

## 📈 Measuring Quality

Track improvements across all 50 resumes:

```bash
# Create quick test script
cat > test_all_resumes.sh << 'EOF'
#!/bin/bash
for resume in tests/resumes/*.pdf; do
    echo "=== $(basename $resume) ==="
    python3 tests/test_docling_parsing_isolated.py "$resume" 2>&1 | grep -A 6 "PARSING SUMMARY"
done
EOF

chmod +x test_all_resumes.sh
./test_all_resumes.sh | tee parsing_results.txt
```

Analyze results:
```bash
# Count successful extractions
grep "Contact info: ✓" parsing_results.txt | wc -l
grep "Skills: [1-9]" parsing_results.txt | wc -l
grep "Experience: [1-9]" parsing_results.txt | wc -l
```

**Target Metrics:**
- Contact info: 90%+ (45+ out of 50)
- Skills: 80%+ (40+ out of 50)
- Experience: 85%+ (42+ out of 50)
- Education: 80%+ (40+ out of 50)

---

## 🚀 Advanced: LLM-Based Parsing

If regex-based extraction quality plateaus, consider LLM extraction:

```python
# In src/services/resume_processing/docling_parser.py

def _extract_with_llm(self, markdown_text: str) -> Dict[str, Any]:
    """
    Use LLM to extract structured data from markdown.
    More accurate but slower and costs API credits.
    """
    from openai import OpenAI
    client = OpenAI()
    
    prompt = f"""
Extract structured data from this resume:

{markdown_text[:5000]}  # Limit to first 5000 chars

Return JSON with:
- full_name, email, phone
- skills (array of strings)
- experience (array with title, company, start_date, end_date)
- education (array with degree, school, year)
"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Cheaper model
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)
```

**Pros:**
- Higher accuracy
- Handles varied formats better
- Less maintenance

**Cons:**
- API cost ($0.15-0.60 per 1M tokens)
- Slower (2-5 seconds per resume)
- Requires API key

---

## 📚 Related Files

- **Parser Implementation**: `src/services/resume_processing/docling_parser.py`
- **Test Script**: `tests/test_docling_parsing_isolated.py`
- **Full Guide**: `tests/DOCLING_TESTING_GUIDE.md`
- **Resume Service**: `src/services/resume_processing/resume_service.py`

---

## ✅ Next Steps

1. **Run initial test** to see current parsing quality:
   ```bash
   python3 tests/test_docling_parsing_isolated.py
   ```

2. **Review output files** to understand Docling's extraction

3. **Iterate on parser** to improve quality

4. **Test across all 50 resumes** to validate improvements

5. **Integrate with full pipeline** once satisfied with quality

---

## 🎉 Summary

You now have:

✅ **Isolated test environment** for quick iteration  
✅ **Detailed output** at every parsing stage  
✅ **Clear workflow** for improving quality  
✅ **Complete documentation** for reference  
✅ **Multiple testing options** (Docker & local)  

**Start testing now:**

```bash
python3 tests/test_docling_parsing_isolated.py
```

Happy parsing! 🚀

