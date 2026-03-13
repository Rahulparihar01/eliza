#!/usr/bin/env python3
"""
Isolated Docling Parsing Test

Parse a single resume and view detailed output at each stage.
Use this to iterate on and improve the parsing logic.

Usage:
    python tests/test_docling_parsing_isolated.py [resume_file]
    
    # If no file specified, uses first resume in tests/resumes/
"""
import sys
import json
from pathlib import Path
from pprint import pprint

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.resume_processing.docling_parser import DoclingParser, ParsedResume


def print_section(title: str, content: str = None):
    """Print a formatted section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)
    if content:
        print(content)


def parse_and_display(resume_path: Path):
    """Parse a resume and display detailed output."""
    print_section("DOCLING RESUME PARSING TEST")
    print(f"Resume: {resume_path.name}")
    print(f"Path: {resume_path}")
    
    # Read resume file
    with open(resume_path, 'rb') as f:
        resume_bytes = f.read()
    
    print(f"File size: {len(resume_bytes):,} bytes")
    
    # Initialize parser
    parser = DoclingParser()
    
    print_section("STEP 1: DOCLING DOCUMENT CONVERSION")
    print("Converting PDF to structured format with Docling...")
    
    try:
        # Parse resume
        parsed_resume = parser.parse_resume(resume_bytes, resume_path.name)
        
        print("✓ Conversion complete")
        
        # Display raw markdown
        print_section("STEP 2: RAW MARKDOWN OUTPUT")
        if parsed_resume.raw_text:
            # Show first 2000 characters
            preview_length = 2000
            if len(parsed_resume.raw_text) > preview_length:
                print(parsed_resume.raw_text[:preview_length])
                print(f"\n... (truncated, total length: {len(parsed_resume.raw_text)} chars)")
                print(f"\nTo see full markdown, check: full_markdown_output.txt")
                
                # Save full markdown to file
                with open("full_markdown_output.txt", "w") as f:
                    f.write(parsed_resume.raw_text)
            else:
                print(parsed_resume.raw_text)
        else:
            print("(No markdown output)")
        
        # Display extracted structured data
        print_section("STEP 3: EXTRACTED STRUCTURED DATA")
        
        print("\n📧 CONTACT INFORMATION:")
        print(f"  Full Name: {parsed_resume.full_name}")
        print(f"  First Name: {parsed_resume.first_name}")
        print(f"  Last Name: {parsed_resume.last_name}")
        print(f"  Email: {parsed_resume.email}")
        print(f"  Phone: {parsed_resume.phone}")
        print(f"  LinkedIn: {parsed_resume.linkedin_url}")
        print(f"  GitHub: {parsed_resume.github_url}")
        print(f"  Location: {parsed_resume.location}")
        
        print("\n💼 PROFESSIONAL SUMMARY:")
        if parsed_resume.summary:
            print(f"  {parsed_resume.summary[:200]}...")
        else:
            print("  (None found)")
        
        print("\n🛠️  SKILLS:")
        if parsed_resume.skills:
            print(f"  Found {len(parsed_resume.skills)} skills:")
            for i, skill in enumerate(parsed_resume.skills[:20], 1):  # Show first 20
                print(f"    {i}. {skill}")
            if len(parsed_resume.skills) > 20:
                print(f"    ... and {len(parsed_resume.skills) - 20} more")
        else:
            print("  (None found)")
        
        print("\n💼 WORK EXPERIENCE:")
        if parsed_resume.experience:
            print(f"  Found {len(parsed_resume.experience)} positions:")
            for i, exp in enumerate(parsed_resume.experience, 1):
                print(f"\n  Position {i}:")
                print(f"    Title: {exp.title}")
                print(f"    Company: {exp.company}")
                print(f"    Dates: {exp.start_date} - {exp.end_date or 'Present' if exp.is_current else 'Unknown'}")
                if exp.description:
                    desc_preview = exp.description[:150].replace('\n', ' ')
                    print(f"    Description: {desc_preview}...")
        else:
            print("  (None found)")
        
        print("\n🎓 EDUCATION:")
        if parsed_resume.education:
            print(f"  Found {len(parsed_resume.education)} entries:")
            for i, edu in enumerate(parsed_resume.education, 1):
                print(f"\n  Education {i}:")
                print(f"    Degree: {edu.degree}")
                print(f"    School: {edu.school}")
                print(f"    Field: {edu.field_of_study}")
                print(f"    Year: {edu.end_date}")
        else:
            print("  (None found)")
        
        print("\n📜 CERTIFICATIONS:")
        if parsed_resume.certifications:
            print(f"  Found {len(parsed_resume.certifications)} certifications:")
            for i, cert in enumerate(parsed_resume.certifications, 1):
                print(f"    {i}. {cert}")
        else:
            print("  (None found)")
        
        # Display Docling output structure
        print_section("STEP 4: DOCLING OUTPUT STRUCTURE")
        if parsed_resume.docling_output:
            print("Docling document structure:")
            # Show keys and first level structure
            if isinstance(parsed_resume.docling_output, dict):
                for key in parsed_resume.docling_output.keys():
                    print(f"  - {key}: {type(parsed_resume.docling_output[key]).__name__}")
            
            # Save full structure to JSON
            output_file = "docling_full_output.json"
            with open(output_file, "w") as f:
                json.dump(parsed_resume.docling_output, f, indent=2, default=str)
            print(f"\nFull Docling output saved to: {output_file}")
        else:
            print("(No Docling output structure available)")
        
        # Display PDL-normalized format
        print_section("STEP 5: PDL-NORMALIZED FORMAT")
        pdl_format = parser.normalize_to_pdl_format(parsed_resume)
        
        # Save to JSON
        pdl_output_file = "parsed_resume_pdl_format.json"
        with open(pdl_output_file, "w") as f:
            json.dump(pdl_format, f, indent=2, default=str)
        
        print(f"PDL-normalized format saved to: {pdl_output_file}")
        print("\nPreview:")
        print(f"  ID: {pdl_format.get('id')}")
        print(f"  Name: {pdl_format.get('full_name')}")
        print(f"  Skills: {len(pdl_format.get('skills', []))} skills")
        print(f"  Experience: {len(pdl_format.get('experience', []))} positions")
        print(f"  Education: {len(pdl_format.get('education', []))} degrees")
        
        # Summary
        print_section("PARSING SUMMARY")
        print(f"✓ Resume parsed successfully")
        print(f"  Contact info: {'✓' if parsed_resume.email or parsed_resume.phone else '✗'}")
        print(f"  Skills: {len(parsed_resume.skills)} found")
        print(f"  Experience: {len(parsed_resume.experience)} positions")
        print(f"  Education: {len(parsed_resume.education)} degrees")
        print(f"  Certifications: {len(parsed_resume.certifications)} found")
        
        print("\n📁 OUTPUT FILES:")
        print("  - full_markdown_output.txt (raw Docling markdown)")
        print("  - docling_full_output.json (full Docling structure)")
        print("  - parsed_resume_pdl_format.json (normalized PDL format)")
        
        # Quality assessment
        print_section("QUALITY ASSESSMENT")
        issues = []
        
        if not parsed_resume.full_name:
            issues.append("⚠️  Name not extracted")
        if not parsed_resume.email:
            issues.append("⚠️  Email not extracted")
        if len(parsed_resume.skills) == 0:
            issues.append("⚠️  No skills extracted")
        if len(parsed_resume.experience) == 0:
            issues.append("⚠️  No work experience extracted")
        if len(parsed_resume.education) == 0:
            issues.append("⚠️  No education extracted")
        
        if issues:
            print("Potential issues found:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("✓ All expected fields extracted successfully")
        
        print_section("NEXT STEPS")
        print("1. Review the output files to understand what Docling is extracting")
        print("2. Check full_markdown_output.txt to see the raw structure")
        print("3. If parsing quality is poor, improve regex patterns in:")
        print("   src/services/resume_processing/docling_parser.py")
        print("4. Re-run this script to test improvements")
        print("\nTo test with a different resume:")
        print(f"  python {Path(__file__).name} path/to/resume.pdf")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        print_section("TROUBLESHOOTING")
        print("Common issues:")
        print("1. Docling not installed:")
        print("   pip install docling docling-core")
        print("2. PDF parsing error:")
        print("   Try a different PDF or check if file is corrupted")
        print("3. Import errors:")
        print("   Ensure you're running from project root")


def main():
    """Main entry point."""
    # Determine which resume to parse
    if len(sys.argv) > 1:
        resume_path = Path(sys.argv[1])
        if not resume_path.exists():
            print(f"Error: Resume file not found: {resume_path}")
            sys.exit(1)
    else:
        # Use first resume in tests/resumes/
        resumes_dir = Path(__file__).parent / "resumes"
        if not resumes_dir.exists():
            print(f"Error: Resumes directory not found: {resumes_dir}")
            print("Please provide a resume path:")
            print(f"  python {Path(__file__).name} path/to/resume.pdf")
            sys.exit(1)
        
        resume_files = list(resumes_dir.glob("*.pdf"))
        if not resume_files:
            print(f"Error: No PDF files found in {resumes_dir}")
            sys.exit(1)
        
        resume_path = resume_files[0]
        print(f"No resume specified, using: {resume_path.name}")
    
    # Parse and display
    parse_and_display(resume_path)


if __name__ == "__main__":
    main()

