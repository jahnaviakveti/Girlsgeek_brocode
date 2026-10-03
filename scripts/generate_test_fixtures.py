import os
from pathlib import Path
import fitz  # PyMuPDF

def generate_fixtures(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Basic single page text PDF
    doc1 = fitz.open()
    page1 = doc1.new_page()
    page1.insert_text(
        (50, 72),
        "Engineering Document\nThis is a standard single-page document used to verify basic text extraction.",
        fontsize=11
    )
    doc1.save(str(output_dir / "basic_single_page.pdf"))
    doc1.close()

    # 2. Multi-page PDF (3 pages)
    doc2 = fitz.open()
    for i in range(1, 4):
        p = doc2.new_page()
        p.insert_text(
            (50, 72),
            f"Document Header - Confidential\n\nContent for Page {i}.\nThis text belongs exclusively to page {i} for provenance testing.",
            fontsize=11
        )
    doc2.save(str(output_dir / "multipage_document.pdf"))
    doc2.close()

    # 3. Text containing unusual whitespace & hyphenation
    doc3 = fitz.open()
    page3 = doc3.new_page()
    raw_text = (
        "Heading With Whitespace\n\n\n\n\n"
        "This  sentence   contains    irregular    spaces   and\ttabs.\n"
        "Here is an example of broken hyphen-\nation across line boundaries.\n\n\n"
        "Final paragraph after excess blank lines."
    )
    page3.insert_text((50, 72), raw_text, fontsize=11)
    doc3.save(str(output_dir / "unusual_whitespace.pdf"))
    doc3.close()

    # 4. Text containing standard section headings
    doc4 = fitz.open()
    page4 = doc4.new_page()
    sections_text = (
        "Document Overview\n"
        "This document contains standard structural sections.\n\n"
        "TECHNICAL SKILLS\n"
        "Python, JavaScript, SQL, Docker\n\n"
        "Work Experience\n"
        "Software Engineering Intern at Demo Corp (2023).\n"
        "Developed backend microservices.\n\n"
        "EDUCATION\n"
        "B.S. in Computer Science (2020 - 2024).\n\n"
        "Projects:\n"
        "Built a distributed event queue system."
    )
    page4.insert_text((50, 72), sections_text, fontsize=11)
    doc4.save(str(output_dir / "sections_document.pdf"))
    doc4.close()

    # 5. Document with non-standard / unusual sections
    doc5 = fitz.open()
    page5 = doc5.new_page()
    unusual_text = (
        "NON-STANDARD DOCUMENT\n\n"
        "TOOLBOX\n"
        "Vim, Bash, Git, Docker\n\n"
        "WHERE I STUDIED\n"
        "Tech University, class of 2022.\n\n"
        "MY RANDOM JOURNEY\n"
        "Self-taught programmer and open-source contributor."
    )
    page5.insert_text((50, 72), unusual_text, fontsize=11)
    doc5.save(str(output_dir / "unusual_headings_document.pdf"))
    doc5.close()

    # 6. Document with NO section headings (pure prose)
    doc6 = fitz.open()
    page6 = doc6.new_page()
    page6.insert_text(
        (50, 72),
        "This is an essay with no headings. It consists entirely of consecutive prose paragraphs. "
        "The parser should not fail when no structural headings exist in the document.",
        fontsize=11
    )
    doc6.save(str(output_dir / "no_sections_document.pdf"))
    doc6.close()

    # 7. Two-column layout document (using explicit rectangular textboxes)
    doc7 = fitz.open()
    page7 = doc7.new_page()
    rect_col1 = fitz.Rect(50, 50, 250, 300)
    rect_col2 = fitz.Rect(300, 50, 500, 300)
    page7.insert_textbox(rect_col1, "Column 1: Left column text block detailing primary qualifications.", fontsize=10)
    page7.insert_textbox(rect_col2, "Column 2: Right column text block detailing secondary certifications.", fontsize=10)
    doc7.save(str(output_dir / "two_column_layout.pdf"))
    doc7.close()

    # 8. Empty pages with no text
    doc8 = fitz.open()
    doc8.new_page()
    doc8.save(str(output_dir / "empty_pages_no_text.pdf"))
    doc8.close()

    # 9. 0-byte empty file
    with open(output_dir / "zero_byte_empty.pdf", "wb") as f:
        pass

    # 10. Corrupt PDF file (invalid structure after magic bytes)
    with open(output_dir / "corrupt_damaged.pdf", "wb") as f:
        f.write(b"%PDF-1.4\n%corrupt-random-garbage-binary-not-a-real-xref\x00\xff\xfe")

    # ==================== Phase 3: JD Test Fixtures ====================

    # 11. Standard bulleted Job Description sample
    doc11 = fitz.open()
    page11 = doc11.new_page()
    jd_standard_text = (
        "Job Opportunity: Junior Full Stack Developer\n\n"
        "Company Overview:\n"
        "TechNova Solutions is a leading software provider.\n\n"
        "Minimum Qualifications:\n"
        "• Must have 2+ years of backend development experience.\n"
        "• Bachelor's degree in Computer Science or related field required.\n"
        "• Hands-on experience with Python, Django, PostgreSQL and Docker.\n"
        "• Experience with React or Angular for frontend development.\n"
        "• Demonstrated experience designing scalable distributed systems.\n\n"
        "Preferred Qualifications:\n"
        "• Familiarity with AWS or GCP is a plus.\n"
        "• AWS Certified Solutions Architect certification preferred.\n"
        "• Knowledge of GraphQL is desirable.\n"
        "• Java experience is not required.\n\n"
        "About Our Team:\n"
        "• Working with a collaborative engineering team.\n"
        "• Competitive compensation and comprehensive health benefits."
    )
    page11.insert_text((50, 60), jd_standard_text, fontsize=10)
    doc11.save(str(output_dir / "jd_standard_sample.pdf"))
    doc11.close()

    # 12. Paragraph-style Job Description sample (use insert_textbox for multi-line flow)
    doc12 = fitz.open()
    page12 = doc12.new_page()
    jd_paragraph_text = (
        "Backend Developer Opening\n\n"
        "We are seeking a talented Backend Engineer to join our team. "
        "The candidate must have at least 3 years of professional experience in Python and FastAPI. "
        "Experience with Redis or MongoDB is preferred. "
        "A Master's degree in Computer Science is desirable. "
        "Prior C++ knowledge is not required. "
        "Our company values a fast-paced and dynamic workplace."
    )
    rect_para = fitz.Rect(50, 50, 550, 500)
    page12.insert_textbox(rect_para, jd_paragraph_text, fontsize=11)
    doc12.save(str(output_dir / "jd_paragraph_sample.pdf"))
    doc12.close()

    # 13. Multi-page Job Description with section-page provenance
    doc13 = fitz.open()
    page13_1 = doc13.new_page()
    page13_1.insert_text(
        (50, 72),
        "Job Description - Page 1\n\n"
        "Senior Cloud Engineer\n\n"
        "Job Summary:\n"
        "Responsible for building reliable cloud infrastructure.\n\n"
        "Must have 5+ years of Linux systems engineering experience.",
        fontsize=10
    )
    page13_2 = doc13.new_page()
    page13_2.insert_text(
        (50, 72),
        "Job Description - Page 2\n\n"
        "Technical Requirements:\n"
        "• Proficiency in Kubernetes and Terraform.\n"
        "• CKAD certification is a plus.\n"
        "• Experience with Python or Go.",
        fontsize=10
    )
    doc13.save(str(output_dir / "jd_multipage_sample.pdf"))
    doc13.close()

    # ==================== Phase 4: Resume Test Fixtures ====================

    # 14. Standard structured resume sample
    doc14 = fitz.open()
    page14 = doc14.new_page()
    resume_standard_text = (
        "Jane Doe\n"
        "jane.doe@example.com | (555) 123-4567 | San Francisco, CA\n\n"
        "Professional Summary\n"
        "Passionate Full Stack Software Engineer with over 4 years of experience building distributed systems and high-throughput web APIs.\n\n"
        "Skills\n"
        "Python, TypeScript, React, Docker, Kubernetes, PostgreSQL, AWS, GraphQL\n\n"
        "Experience\n"
        "Senior Software Engineer | TechCorp Inc.\n"
        "Jan 2023 - Present\n"
        "• Architected scalable microservices using Python and FastAPI.\n"
        "• Managed container deployments using Kubernetes and Docker.\n"
        "• Mentored junior engineers and led sprint planning sessions.\n\n"
        "Software Engineer | DevWorks\n"
        "Jun 2020 - Dec 2022\n"
        "• Developed reactive frontend applications using React and TypeScript.\n"
        "• Designed relational databases and optimized queries with PostgreSQL.\n\n"
        "Education\n"
        "Bachelor of Science in Computer Science\n"
        "Tech University\n"
        "Aug 2016 - May 2020 | GPA: 3.8/4.0\n\n"
        "Certifications\n"
        "AWS Certified Solutions Architect - Amazon Web Services (AWS)\n"
        "Issued: Mar 2022\n\n"
        "Projects\n"
        "CloudSync Engine\n"
        "• Built real-time file synchronization service using Python and Redis."
    )
    rect_std = fitz.Rect(50, 40, 550, 780)
    page14.insert_textbox(rect_std, resume_standard_text, fontsize=9.5)
    doc14.save(str(output_dir / "resume_standard_sample.pdf"))
    doc14.close()

    # 15. Messy resume with non-standard headings, aliases, and aspirational skills
    doc15 = fitz.open()
    page15 = doc15.new_page()
    resume_messy_text = (
        "Alex Mercer\n"
        "alex.mercer@testmail.org • 555-987-6543\n\n"
        "Employment History:\n"
        "Backend Developer at FinTech Systems (2022 - 2024)\n"
        "• Developed secure transaction processing pipelines in Python and NodeJS.\n"
        "• Administered data storage layer using Postgres and Redis.\n"
        "• Implemented robust CI/CD deployment pipelines using Docker.\n\n"
        "Skills & Technologies:\n"
        "Languages: NodeJS, Python, Go, CustomDSL\n"
        "Databases: Postgres, MongoDB\n"
        "Interested in learning Rust and WebAssembly for systems programming.\n\n"
        "Academic History:\n"
        "B.Tech in Information Technology\n"
        "National Institute of Technology\n"
        "2018 - 2022\n"
        "GPA: 3.9/4.0\n\n"
        "Selected Projects:\n"
        "DataStream Engine: Scalable streaming platform built with Go and Kafka.\n"
        "Distributed Key-Value Store: In-memory store using Python and Docker.\n\n"
        "Licenses & Certifications:\n"
        "Certified Kubernetes Application Developer (CKAD) - Linux Foundation\n"
        "Issued: 2023"
    )
    rect_messy = fitz.Rect(50, 40, 550, 780)
    page15.insert_textbox(rect_messy, resume_messy_text, fontsize=9.5)
    doc15.save(str(output_dir / "resume_messy_sample.pdf"))
    doc15.close()

    # 16. Two-column layout resume sample
    doc16 = fitz.open()
    page16 = doc16.new_page()
    left_column_text = (
        "Samantha Reed\n"
        "samantha.reed@domain.com\n"
        "(555) 432-1098\n\n"
        "Skills\n"
        "Python, Java, Docker, Git\n\n"
        "Education\n"
        "B.S. in Software Engineering\n"
        "City College of Technology\n"
        "2019 - 2023\n\n"
        "Certifications\n"
        "Oracle Certified Professional: Java SE Developer"
    )
    right_column_text = (
        "Work Experience\n\n"
        "Software Engineer | Global Logistics\n"
        "Jul 2023 - Present\n"
        "• Designed automated inventory pipelines using Python and Docker.\n"
        "• Maintained legacy order management system in Java.\n\n"
        "Projects\n\n"
        "Microservices Dashboard\n"
        "• Real-time monitoring metrics using Python and Java microservices."
    )
    rect_left = fitz.Rect(40, 50, 240, 750)
    rect_right = fitz.Rect(260, 50, 550, 750)
    page16.insert_textbox(rect_left, left_column_text, fontsize=9.5)
    page16.insert_textbox(rect_right, right_column_text, fontsize=9.5)
    doc16.save(str(output_dir / "resume_two_column_sample.pdf"))
    doc16.close()

    print(f"Generated test fixtures in {output_dir}")

if __name__ == "__main__":
    fixtures_path = Path(__file__).resolve().parent.parent / "data" / "test_fixtures"
    generate_fixtures(fixtures_path)
