from fpdf import FPDF

# Create PDF
pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", "B", 16)
pdf.cell(0, 10, "Senior Machine Learning Engineer", ln=True)

pdf.set_font("Arial", "", 12)
pdf.ln(5)
pdf.multi_cell(0, 10, """
About the Role:
We are seeking an experienced Senior Machine Learning Engineer to join our AI team.
You will be responsible for designing, developing, and deploying ML models at scale.

Requirements:
- 5+ years of experience in machine learning and data science
- Strong proficiency in Python and ML frameworks (TensorFlow, PyTorch, scikit-learn)
- Experience with cloud platforms (AWS, GCP, or Azure)
- Solid understanding of ML algorithms, deep learning, and NLP
- Experience with MLOps and model deployment
- Strong communication and collaboration skills

Responsibilities:
- Design and implement ML models for production systems
- Collaborate with data engineers and product teams
- Optimize model performance and scalability
- Mentor junior engineers and contribute to technical strategy
""")

pdf.output("test_job_description.pdf")
print("✅ Created test_job_description.pdf")
