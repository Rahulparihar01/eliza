# Resume Parsing Test UI - Setup Guide

## 📋 Overview

We've built a **beautiful web UI** for testing Docling resume parsing quality. Upload a resume PDF and see detailed parsing results instantly in your browser!

### What's New

✅ **Backend API**: `POST /api/admin/test-resume-parsing`  
✅ **Frontend UI**: `/admin/resume-parsing-test`  
✅ **Navigation**: Added to Admin section  
✅ **50 Test Resumes**: Already in `tests/resumes/`  

---

## 🚀 Setup Steps

### Step 1: Rebuild Backend Container

The backend has a new admin API endpoint that needs to be built:

```bash
cd /Users/scottgay/Documents/Eliza/eliza-platform

# Rebuild app container with new admin endpoint
docker-compose -f docker/docker-compose.yml build app

# Restart it
docker-compose -f docker/docker-compose.yml up -d app
```

### Step 2: Generate Orval Types

Generate TypeScript types from the updated OpenAPI spec:

```bash
# Make sure app container is running (it serves the OpenAPI spec)
docker-compose -f docker/docker-compose.yml ps app

# Generate types
cd frontend
npm run generate:api

# This creates/updates frontend types for the new endpoint
```

### Step 3: Run Frontend

You can run the frontend locally (faster) or in Docker:

#### Option A: Local (Recommended for Development)

```bash
cd frontend
npm install  # If needed
npm run dev

# Frontend runs at http://localhost:3000
```

#### Option B: Docker

```bash
docker-compose -f docker/docker-compose.yml build frontend
docker-compose -f docker/docker-compose.yml up -d frontend

# Frontend runs at http://localhost:3000
```

---

## 🎨 Using the UI

### 1. Navigate to Resume Parsing Test

1. Log in as admin user
2. Go to **Admin Settings** → **Resume Parsing Test** in the left sidebar
3. Or navigate directly to: `http://localhost:3000/admin/resume-parsing-test`

### 2. Upload a Resume

- **Drag & drop** a PDF/DOCX/TXT file
- Or **click** to browse and select
- Max file size: **10MB**
- Click **"Parse Resume"**

### 3. View Results

The UI shows **8 collapsible sections**:

#### **Quality Assessment**
- Overall score (0-100%)
- Metrics: Skills, Experience, Education counts
- Issues found (e.g., "Email not extracted")

#### **Contact Information**
- Full Name, Email, Phone
- LinkedIn, GitHub URLs
- Location

#### **Skills**
- All extracted skills as badges
- Count displayed

#### **Work Experience**
- Position title, company
- Date range
- Description preview

#### **Education**
- Degree, school, field of study
- Graduation year

#### **Certifications**
- List of certifications found

#### **Raw Markdown Output**
- Docling's markdown interpretation of the PDF
- Copy to clipboard button
- Shows structure: headings, sections, formatting

#### **PDL-Normalized Format (JSON)**
- Resume data in PDL format
- Ready for talent scoring
- Copy to clipboard

#### **Docling Output Structure (JSON)**
- Full Docling internal structure
- Bounding boxes, fonts, layout
- Copy to clipboard

---

## 💡 Iteration Workflow

### 1. Upload a Resume

Pick one of the 50 test resumes:

```bash
tests/resumes/resume_ml_01.pdf  # through resume_ml_50.pdf
```

### 2. Check Quality Assessment

Look for warnings:
- ⚠️  Name not extracted
- ⚠️  Email not extracted
- ⚠️  No skills extracted
- ⚠️  No work experience extracted

### 3. Review Raw Markdown

Expand the "Raw Markdown Output" section:
- Is the "Skills" section present?
- What format are dates in?
- Are section headers different than expected?

### 4. Fix the Parser

Edit `src/services/resume_processing/docling_parser.py`:

```python
# Example: Improve skills extraction
def _extract_skills(self, text: str) -> List[str]:
    # OLD: Only matches "Skills"
    skills_pattern = r'(?i)(skills|technical skills)(.*?)(?=\n\n|\n#|$)'
    
    # NEW: Match more variations
    skills_pattern = r'(?i)(skills|technical skills|core competencies|expertise|technologies)(.*?)(?=\n\n|\n#|$)'
```

### 5. Rebuild & Retest

```bash
# Rebuild backend with changes
docker-compose -f docker/docker-compose.yml build app
docker-compose -f docker/docker-compose.yml up -d app

# Upload same resume again in UI
# Compare results - did quality improve?
```

### 6. Test More Resumes

Upload 5-10 different resumes to ensure your changes work broadly!

---

## 📊 Quality Scoring

The UI calculates an overall quality score (0-100%):

| Category | Weight | Description |
|----------|--------|-------------|
| **Contact** | 30% | Name (10%), Email (10%), Phone (5%), Social (5%) |
| **Skills** | 20% | Number of skills extracted |
| **Experience** | 30% | Number of job positions |
| **Education** | 15% | Number of degrees |
| **Summary** | 5% | Professional summary extracted |

**Score Colors:**
- 🟢 **Green** (80-100%): Excellent extraction
- 🟡 **Yellow** (60-79%): Good but missing some fields
- 🔴 **Red** (0-59%): Poor extraction, needs improvement

---

## 🎯 Features

### Upload Interface
- **Drag & drop** or click to browse
- File type validation (PDF, DOCX, TXT)
- File size validation (10MB max)
- Visual feedback on file selection

### Results Display
- **Collapsible sections** - expand what you need
- **Copy to clipboard** - for JSON outputs
- **Responsive design** - works on any screen size
- **Dark code blocks** - for JSON/markdown

### Error Handling
- **Toast notifications** for success/errors
- **Detailed error messages** from API
- **Quality warnings** with actionable feedback

---

## 🐛 Troubleshooting

### Issue: "Cannot find types for admin endpoint"

**Cause**: Orval types not generated.

**Fix**:
```bash
cd frontend
npm run generate:api
```

### Issue: "404 - Endpoint not found"

**Cause**: Backend container not rebuilt.

**Fix**:
```bash
docker-compose -f docker/docker-compose.yml build app
docker-compose -f docker/docker-compose.yml up -d app
```

### Issue: "Permission denied"

**Cause**: Not logged in as admin.

**Fix**: Log in with a user that has `system:admin` permission.

### Issue: "Parsing failed - Docling error"

**Cause**: PDF might be corrupted or unsupported format.

**Fix**: Try a different PDF or check Docker logs:
```bash
docker-compose -f docker/docker-compose.yml logs app | grep -i docling
```

---

## 📝 API Endpoint Details

### `POST /api/admin/test-resume-parsing`

**Headers:**
```
Authorization: Bearer <your_token>
Content-Type: multipart/form-data
```

**Body:**
```
file: <resume_file.pdf>
```

**Response:**
```json
{
  "success": true,
  "filename": "resume_ml_01.pdf",
  "file_size": 245678,
  "raw_markdown": "# John Doe\n\njohn@email.com...",
  "contact_info": {
    "full_name": "John Doe",
    "email": "john@email.com",
    ...
  },
  "skills": ["Python", "JavaScript", ...],
  "experience": [...],
  "education": [...],
  "certifications": [...],
  "quality_assessment": {
    "has_contact_info": true,
    "skills_count": 15,
    "experience_count": 3,
    "education_count": 2,
    "certifications_count": 3,
    "issues": [],
    "quality_score": 92.5
  },
  "pdl_format": {...},
  "docling_output": {...}
}
```

---

## 🎉 Summary

You now have a **complete web UI** for testing resume parsing!

**Benefits:**
- ✅ **No terminal needed** - everything in the browser
- ✅ **Visual feedback** - see exactly what's extracted
- ✅ **Fast iteration** - upload, view, fix, repeat
- ✅ **Copy/paste JSON** - easy debugging
- ✅ **Quality metrics** - know what needs improvement
- ✅ **50 test resumes** - comprehensive testing

**Workflow:**
1. Upload resume in UI
2. Review quality assessment
3. Check raw markdown to understand structure
4. Edit parser regex patterns
5. Rebuild backend
6. Re-upload and compare results
7. Test with more resumes

**Perfect for rapidly improving parsing quality!** 🚀

---

## 📚 Related Documentation

- **[Docling Parser Implementation](../../src/services/resume_processing/docling_parser.py)**
- **[Isolated Test Script](./DOCLING_PARSING_ITERATION.md)**
- **[Testing Guide](../../tests/DOCLING_TESTING_GUIDE.md)**
- **[FileSystem Connector](./FILESYSTEM_CONNECTOR.md)**

---

**Ready to test?** 

Start the containers, generate types, and navigate to `/admin/resume-parsing-test`!

