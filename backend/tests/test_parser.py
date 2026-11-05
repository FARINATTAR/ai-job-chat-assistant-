"""
Tests for DocumentExtractor and ResumeParserAgent.
Verifies parsing of valid documents and edge cases: unreadable documents, corrupted files, and unsupported formats.
"""
import io
import pytest
import pymupdf as fitz
from app.services.document_extractor import (
    DocumentExtractor,
    UnreadableDocumentError,
    UnsupportedFileError,
)
from app.agents.parser_agent import ResumeParserAgent


def create_sample_pdf(text: str) -> bytes:
    """Helper to generate an in-memory test PDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_valid_pdf_extraction():
    sample_text = (
        "John Doe\n"
        "Email: john.doe@example.com | Phone: +1 555-123-4567\n"
        "Full Stack Developer with 2 years of experience.\n"
        "Skills: Python, FastAPI, React, Docker, PostgreSQL, Git\n"
        "Education: B.S. Computer Science, State University, 2022\n"
        "Projects: Built an AI Chatbot using FastAPI and React."
    )
    pdf_bytes = create_sample_pdf(sample_text)
    extracted = DocumentExtractor.extract_from_bytes(pdf_bytes, "resume.pdf")

    assert "John Doe" in extracted
    assert "john.doe@example.com" in extracted
    assert "Python" in extracted


def test_unreadable_or_empty_document():
    """JD Edge-Case: Clear handling of unreadable resumes."""
    # 1. Zero bytes
    with pytest.raises(UnreadableDocumentError):
        DocumentExtractor.extract_from_bytes(b"", "resume.pdf")

    # 2. Scanned image without selectable text (< 50 chars)
    tiny_pdf = create_sample_pdf("Hi")
    with pytest.raises(UnreadableDocumentError):
        DocumentExtractor.extract_from_bytes(tiny_pdf, "scanned_resume.pdf")


def test_unsupported_file_extension():
    """JD Edge-Case: Clear rejection of unsupported file types."""
    with pytest.raises(UnsupportedFileError):
        DocumentExtractor.extract_from_bytes(b"sample text", "resume.txt")

    with pytest.raises(UnsupportedFileError):
        DocumentExtractor.extract_from_bytes(b"sample text", "resume.exe")


def test_resume_parser_agent_profile_building():
    sample_text = (
        "Alex Rivera\n"
        "alex@example.com | +91 9876543210\n"
        "Backend Developer with 3 years of experience in distributed systems.\n"
        "Technical Skills: Python, FastAPI, Docker, PostgreSQL, Redis, Kubernetes, AWS\n"
        "Experience:\n"
        "Software Engineer at TechCorp (2021 - 2024)\n"
        "Education: Bachelor of Technology in Computer Science, 2021\n"
        "Projects: High-throughput API gateway built with Python and Redis."
    )
    pdf_bytes = create_sample_pdf(sample_text)
    agent = ResumeParserAgent()
    profile = agent.parse_document(pdf_bytes, "alex_resume.pdf")

    assert profile.name != ""
    assert profile.contact.email == "alex@example.com"
    # Skills should be detected and normalized
    skills_lower = [s.lower() for s in profile.skills]
    assert "python" in skills_lower
    assert "docker" in skills_lower
    assert "postgresql" in skills_lower
    assert profile.years_of_experience >= 2.0
    assert len(profile.education) > 0
    assert "Bachelor" in profile.education[0].degree
    assert len(profile.projects) > 0
    assert "High-throughput API" in profile.projects[0].name or "API gateway" in profile.projects[0].description


def test_skill_normalization():
    agent = ResumeParserAgent()
    assert agent.normalize_skill("JS") == "JavaScript"
    assert agent.normalize_skill("ts") == "TypeScript"
    assert agent.normalize_skill("k8s") == "Kubernetes"
    assert agent.normalize_skill("postgres") == "PostgreSQL"
    assert agent.normalize_skill("reactjs") == "React"
