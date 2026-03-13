"""Create test PDFs for cross-KB retrieval testing and upload to S3."""
import fitz
import boto3

s3 = boto3.client("s3", region_name="us-east-1")
BUCKET = "misc-docs-eliza"


def make_pdf(pages):
    doc = fitz.open()
    for page_items in pages:
        page = doc.new_page(width=612, height=792)
        tw = fitz.TextWriter(page.rect)
        y = 60
        for text, size, bold in page_items:
            if not text.strip():
                y += 8
                continue
            font = fitz.Font("helv")
            lines = []
            words = text.split()
            line = ""
            for w in words:
                test = (line + " " + w).strip()
                if font.text_length(test, fontsize=size) > 490 and line:
                    lines.append(line)
                    line = w
                else:
                    line = test
            if line:
                lines.append(line)
            for ln in lines:
                if y > 740:
                    page = doc.new_page(width=612, height=792)
                    tw = fitz.TextWriter(page.rect)
                    y = 60
                tw.append((56, y), ln, font=font, fontsize=size)
                y += size + 4
            y += 8
        tw.write_text(page)
    b = doc.tobytes()
    doc.close()
    return b


# === KB1: Financial ===
fin1 = make_pdf([[
    ("Nextera Corp - Q3 2025 Financial Results", 16, True), ("", 8, False),
    ("Revenue Summary", 13, True),
    ("Nextera Corporation reported total consolidated revenue of $847.3 million for Q3 2025, a 12.4% increase year-over-year. Cloud Services contributed $412.6 million (48.7%), Enterprise Software $298.1 million (35.2%), Professional Services $136.6 million (16.1%). Operating margins were 18.7%, up from 16.2% in Q3 2024.", 10, False),
    ("", 8, False),
    ("Geographic Revenue", 13, True),
    ("North America: $528.1M (62.3%), Europe: $210.1M (24.8%), Asia-Pacific: $109.3M (12.9%). Europe grew 18.2% YoY. New Frankfurt data center opened August 2025. Japan largest APAC contributor at $47.2M.", 10, False),
    ("", 8, False),
    ("Cash Flow and Balance Sheet", 13, True),
    ("Operating cash flow: $168.4M. Free cash flow: $124.7M after $43.7M capex. Cash: $892.3M. Total debt: $1.23B. Debt-to-equity: 0.42. Repurchased $75M of stock.", 10, False),
]])

fin2 = make_pdf([[
    ("Nextera Corp - FY 2025 Budget vs Actual", 16, True), ("", 8, False),
    ("Division Performance", 13, True),
    ("Cloud Services exceeded budget by 8.3% ($1.58B vs $1.46B). Enterprise Software underperformed by 4.1% ($1.12B vs $1.17B). ARR grew 28% to $890M. Professional Services met budget ($523M vs $517M).", 10, False),
    ("", 8, False),
    ("Headcount", 13, True),
    ("Total employees: 14,827. Revenue per employee: $216,400. Hired 2,340 (1,180 engineering). Attrition: 11.2% (down from 14.8%). Bangalore R&D: 2,150.", 10, False),
]])

fin3 = make_pdf([[
    ("Capital Allocation Strategy 2026-2028", 16, True), ("", 8, False),
    ("Investment Plan", 13, True),
    ("Board approved $2.4B plan: R&D $1.1B (46%), Infrastructure $800M (33%), Acquisitions $300M (13%), Buybacks $200M (8%). R&D: AI cloud $450M (Meridian AI), Project Fortress $380M, Edge computing $270M.", 10, False),
    ("", 8, False),
    ("Acquisition Targets", 13, True),
    ("DataStream Analytics (~$120M), SecureVault Inc. (~$85M), CloudBridge Solutions (~$95M), fourth under NDA. Led by CSO Maria Chen. Goal: 2+ acquisitions by H1 2026.", 10, False),
]])

# === KB2: Legal ===
legal1 = make_pdf([[
    ("Meridian AI - Master Services Agreement", 16, True), ("", 8, False),
    ("Agreement Overview", 13, True),
    ("Effective October 15, 2025. Nextera Corp (San Jose) and Meridian AI (Boston). 36-month term. Min annual commitment: $45M. Total value: $180M. Meridian provides AI hosting, fine-tuning, inference on NexCloud.", 10, False),
    ("", 8, False),
    ("Data Processing (Section 7)", 13, True),
    ("Data in US, EU, Japan only. Fine-tuning data retained 90 days max. Comply with GDPR, CCPA, EU AI Act. SOC 2 Type II required. Annual AI ethics audits.", 10, False),
    ("", 8, False),
    ("IP and Liability (Sections 9, 12)", 13, True),
    ("Custom models jointly owned. Base models: Meridian. Liability cap: 200% of 12-month fees. Uncapped for data breaches and IP infringement. Meridian indemnifies for IP claims and regulatory penalties.", 10, False),
]])

legal2 = make_pdf([[
    ("Regulatory Compliance Report Q3 2025", 16, True), ("", 8, False),
    ("Certifications", 13, True),
    ("SOC 2 Type II by E&Y: zero material findings (Aug 2025). ISO 27001:2022 renewed Jul 2025. ISO 27701 audit Q1 2026.", 10, False),
    ("", 8, False),
    ("Privacy Metrics", 13, True),
    ("847 GDPR DSARs (4.2 day avg). 1,234 CCPA deletions (99.7% on time). Meridian AI DPIA completed Sep 2025: moderate risk, mitigated by 90-day retention, AES-256, dedicated compute.", 10, False),
    ("", 8, False),
    ("Security Incident Aug 3 2025", 13, True),
    ("API gateway misconfiguration exposed 2,847 emails. Contained 2 hours. Notified Irish DPC within 72 hours per GDPR Art 33. Root cause: deployment automation error. Initially SEV-1, reclassified security incident.", 10, False),
]])

# === KB3: Operations ===
ops1 = make_pdf([[
    ("Engineering Team Structure", 16, True), ("", 8, False),
    ("Platform Engineering", 13, True),
    ("2,340 engineers. Cloud Infrastructure (890, VP James Rodriguez), App Services (620, VP Sarah Kim), Data Platform (480, VP Raj Patel), AI/ML Engineering (350, VP Dr. Lisa Zhang - created Jul 2025 for Meridian partnership). SAFe 2-week sprints. SLA 99.97%, actual 99.993%.", 10, False),
    ("", 8, False),
    ("NexCloud 3.0 Architecture", 13, True),
    ("12 AWS + 3 Azure regions. 4,800 microservices on K8s. V3: gRPC (35% faster), Kafka (2.1B events/day), row-level security. 340M daily API calls, 890M peak. P99: 47ms (was 82ms).", 10, False),
    ("", 8, False),
    ("Incident Response", 13, True),
    ("24/7 on-call (San Jose, London, Bangalore). Q3: 3 SEV-1 (was 7), MTTR 23 min. Aug 3 API breach was most significant (see Compliance Report).", 10, False),
]])

ops2 = make_pdf([[
    ("Product Roadmap H1 2026", 16, True), ("", 8, False),
    ("AI-Native Features", 13, True),
    ("AI Everywhere initiative: (1) Auto-Scaling GA Mar 2026 (20-30% cost savings), (2) Query Optimizer Beta Feb 2026 (40% faster), (3) Code Review GA Apr 2026. $127M, 420 engineers. Sponsors: Maria Chen, Dr. Lisa Zhang.", 10, False),
    ("", 8, False),
    ("Project Fortress", 13, True),
    ("Enterprise security beta Q2 2026. Zero-trust: Identity Mesh, Data Shield, Threat Hunter. SecureVault acquisition ($85M) accelerates Identity Mesh by 9 months. Due diligence Phase 2, close Mar 2026. SecureVault 120 engineers join Cloud Infra (VP James Rodriguez). Revenue: $200-250M/yr by 2028.", 10, False),
]])

uploads = [
    ("cross-kb-test/financial/", "Q3_2025_Financial_Results.pdf", fin1),
    ("cross-kb-test/financial/", "FY2025_Budget_vs_Actual.pdf", fin2),
    ("cross-kb-test/financial/", "Capital_Allocation_2026-2028.pdf", fin3),
    ("cross-kb-test/legal/", "Meridian_AI_MSA.pdf", legal1),
    ("cross-kb-test/legal/", "Regulatory_Compliance_Q3_2025.pdf", legal2),
    ("cross-kb-test/operations/", "Engineering_Team_Structure.pdf", ops1),
    ("cross-kb-test/operations/", "Product_Roadmap_H1_2026.pdf", ops2),
]

for prefix, name, content in uploads:
    key = f"{prefix}{name}"
    s3.put_object(Bucket=BUCKET, Key=key, Body=content, ContentType="application/pdf")
    print(f"Uploaded {key} ({len(content):,} bytes)")

print(f"\nDone: {len(uploads)} PDFs to s3://{BUCKET}/cross-kb-test/")
