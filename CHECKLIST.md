# 🚀 Hidani Tech - SDE Intern Assessment: Master Checklist & Roadmap

> **Project:** AI Job Chat Assistant  
> **Company:** Hidani Tech  
> **Role:** Software Development Engineer (SDE) Intern - AI Agents & Automation  
> **Deliverables:** Live Deployed Link, Public GitHub Repo, `jobs.json` (1.5k–2k listings) + Scraping Script, Comprehensive README, 3–5 Min Video Demo.

---

## 📌 Architecture & Design Principles

1. **Lightweight Custom Orchestrator (No LangChain/CrewAI Bloat):**
   - Pure Python tool-calling loop with explicit state machine.
   - 100% transparent code you can confidently explain line-by-line during the technical interview.
2. **Explicit Multi-Agent Handoffs:**
   - Clearly defined sub-agents: **ResumeParser**, **JobMatcher**, and **ApplicationManager**.
   - Handoff events streamed in real-time to the UI via Server-Sent Events (SSE).
3. **Deterministic Matching + Grounded LLM Explanations:**
   - Code calculates exact skill overlap and experience fit.
   - LLM articulates the match reasoning based solely on facts (zero hallucinations).
4. **Persistent Conversational State & Index-to-ID Mapping:**
   - Translates natural user requests like *"apply to job 3"* using a session-level `last_results` cache.
   - Conversational filter stacking (e.g., *"show only remote"* followed by *"needing React"*).
5. **Production-Ready Persistence:**
   - Cloud Postgres (Neon Free Tier) for live deployment to ensure applied jobs survive container restarts.
   - SQLite fallback for frictionless local development.

---

## 📋 Comprehensive Phase-by-Phase Checklist

### Phase 1: Job Dataset & Scraper Pipeline
- [x] **1.1 Define Job Schema:**
  - Standard fields: `id`, `title`, `company`, `location`, `remote` (bool), `experience_required`, `skills` (list), `description`, `source_url`, `posted_at`.
- [x] **1.2 Build Scraper Client (`scraper/`):**
  - Use legal, reliable public APIs & job boards (Jobfound, Arbeitnow) to avoid IP bans/CAPTCHAs.
  - Implement retry logic with exponential backoff and rate-limiting.
- [x] **1.3 Taxonomy & Data Extraction:**
  - Standardized tech skill extractor (e.g., regex + taxonomy for Python, React, Docker, Node.js, etc.).
  - Experience level parser (maps "Entry", "3+ years", etc. to integer ranges).
- [x] **1.4 Dataset Generation & Verification:**
  - Scraped and deduplicated 2,900+ real job records from Jobfound, Arbeitnow, Remotive, and LinkedIn (via JSearch API).
  - Saved to `data/jobs.json`.
  - Validated dataset completeness: 2,900+ unique jobs across multiple sources with full schema coverage.

---

### Phase 2: Backend Core & Database Setup (FastAPI)
- [x] **2.1 Monorepo / Backend Skeleton:**
  - Setup FastAPI app structure: `app/core`, `app/api`, `app/models`, `app/repositories`.
  - Configure environment management (`pydantic-settings`), logging, and CORS.
- [x] **2.2 In-Memory Job Repository (`JobRepository`):**
  - Load `data/jobs.json` into memory on app startup (sub-millisecond indexed lookup and filter).
- [x] **2.3 Database & Application Schema (SQLAlchemy):**
  - Model: `applications` (`id`, `session_id`, `job_id`, `job_title`, `company`, `applied_at`, `status`).
  - Added DB-level Unique Constraint on `(session_id, job_id)` to prevent duplicates.
  - Supports SQLite for local dev and PostgreSQL (Neon) for deployment.
- [x] **2.4 Session & Context Store:**
  - In-memory session store holding:
    - User resume profile
    - `last_results` (Job ID list matching the numbers 1, 2, 3 shown in chat)
    - Active query filters (e.g. `remote=True`, `skills=['React']`)
    - Chat message history

---

### Phase 3: Sub-Agent 1 — Resume Parser Agent
- [x] **3.1 Document Text Extraction:**
  - Support PDF parsing via `PyMuPDF` (`fitz`).
  - Support DOCX parsing via `python-docx` (including tables and paragraphs).
- [x] **3.2 Structured LLM Extraction:**
  - Pydantic Schema: `Name`, `Contact` (Email, Phone, LinkedIn, GitHub), `Designation`, `Skills` (normalized), `Experience` (years + roles), `Education`, `Projects`.
  - Native structured output using Gemini / OpenAI API with deterministic heuristic fallback.
- [x] **3.3 Resume Edge-Case Handling (Mandatory):**
  - Corrupt or unreadable files (scanned image PDFs without selectable text raise `UnreadableDocumentError` with clear guidance).
  - Unsupported file formats (`.exe`, `.txt` raise `UnsupportedFileError`).
  - Unit tests verified: 5/5 passing in pytest.

---

### Phase 4: Sub-Agent 2 — Job Matcher Engine
- [x] **4.1 Deterministic Match Engine:**
  - Skill overlap calculation with synonym support (e.g., `JS` == `JavaScript`, `FastAPI` == `Python`).
  - Designation/title similarity scoring.
  - Experience suitability matching.
  - Overall composite match score (0–100%).
- [x] **4.2 Grounded Match Reason Generator:**
  - Factual bullets generated without hallucination (e.g., *"Matches 4 of your key skills: Python, Docker, SQL, AWS"*).
- [x] **4.3 Natural Language Filter Refiner:**
  - Support conversational modifications:
    - *"Show only remote roles"* (`remote=True`)
    - *"Jobs with React or SQL"* (`skills=['SQL']`)
    - Stacks filters statefully in session context.
- [x] **4.4 Matcher Edge-Case Handling (Mandatory):**
  - Tested zero matching jobs edge case (returns graceful status and filter relaxation guidance).
  - 9/9 backend unit tests passing.

---

### Phase 5: Sub-Agent 3 — Application & Tracker Agent
- [x] **5.1 Reference Resolver:**
  - Support index numbers: *"apply to job 1"*, *"apply to job 3"*.
  - Support direct Job IDs: *"apply to job jf_..."*.
- [x] **5.2 Application Persistence & Deduplication:**
  - Checks database for existing application under current `session_id`.
  - Database-level unique constraint prevents duplicates.
  - Returns friendly notification on duplicate application without error.
- [x] **5.3 Application Tracking Query:**
  - Responds to *"show my applied jobs"* or *"what jobs have I applied to?"*.
  - Lists job title, company, applied date, and status (`APPLIED`).
- [x] **5.4 Application Edge-Case Handling (Mandatory):**
  - Invalid job reference (e.g., user asks for "job 99" when only 3 were listed) -> returns guidance.
  - Attempting to apply before uploading a resume -> prompts user to upload first.
  - 14/14 unit & integration tests passing.

---

### Phase 6: Orchestrator Agent & Real-Time Streaming
- [x] **6.1 Master Orchestrator Architecture:**
  - Conversational state machine and intent detection (`GREETING`, `SEARCH_OR_REFINE`, `APPLY`, `TRACK`, `RESET_FILTERS`).
  - Seamless routing between `ResumeParser`, `JobMatcher`, and `ApplicationManager`.
- [x] **6.2 Agent-to-Agent Handoff Events:**
  - Emits real-time Server-Sent Events (SSE):
    - `event: agent_start` -> Initial intent analysis
    - `event: agent_handoff` -> Real-time handoff trace (`Orchestrator ➔ JobMatcher`, `Orchestrator ➔ ApplicationManager`)
    - `event: job_results` -> Structured JSON cards for UI
    - `event: token` -> Live conversational message stream
- [x] **6.3 Guardrails & Testing:**
  - Enforces resume upload pre-condition before applying or matching.
  - Complete backend test suite: 30/30 tests passing in pytest.

---

### Phase 7: Frontend UI/UX (Next.js + Tailwind + shadcn/ui)
- [x] **7.1 Modern Conversational Chat Interface:**
  - Responsive two-column layout with theme and Markdown streaming support.
- [x] **7.2 Resume Upload Component:**
  - Drag-and-drop zone directly in UI with candidate profile preview card.
- [x] **7.3 Interactive Job Cards:**
  - Displays Job Title, Company, Location, Remote tag, Experience badge.
  - Match percentage score with visual progress color indicator.
  - Bulleted Grounded Match Reasons (factual, zero hallucination).
  - 1-click **"Quick Apply"** button directly on the card.
- [x] **7.4 Live Agent Trace Indicator:**
  - Expandable badge showing sub-agent handoffs in real-time (`[Orchestrator] ➔ [JobMatcher]`).
- [x] **7.5 Applied Jobs Drawer:**
  - Slide-out drawer tracking applied roles, dates, and status badges.
- [x] **7.6 Suggested Quick Prompts:**
  - Interactive chips: *"Show only remote roles"*, *"Jobs needing React"*, *"Reset all filters"*.
  - Next.js production build verified (`next build` compiled with 0 errors).

---

### Phase 8: High-Impact Differentiators (Top Novel Features)
- [x] **8.1 Skill-Gap Analysis & Readiness Score:**
  - Displays match percentage, matched skills, and missing skills for every recommended role.
- [x] **8.2 One-Click Quick Apply & Natural Conversation:**
  - Integrated 1-click Quick Apply buttons alongside natural conversational applying (*"apply to job 1"*).

---

### Phase 9: Testing & Edge-Case Verification
- [x] **9.1 Automated Test Suite (`pytest`):**
  - Unit tests for Resume Parser (valid PDF, unreadable document, unsupported formats, skills).
  - Unit tests for Matcher Engine (synonyms, filter stacking, top-k ranking, zero matches).
  - Integration tests for Apply & Dedupe flows.
  - Complete backend test suite: **31/31 tests passing**.
- [x] **9.2 Verification of 3 Mandatory Assessment Edge Cases:**
  - Case 1: Unreadable/malformed resume -> friendly error message.
  - Case 2: Zero job matches -> advice on broadening filters.
  - Case 3: Invalid job reference -> clear correction.

---

### Phase 10: Production Deployment
- [x] **10.1 Backend Deployment Ready:**
  - Production `Dockerfile` created with Python 3.11-slim and uvicorn.
  - Supports Neon.tech serverless PostgreSQL and local SQLite.
  - Health check endpoint `/api/health` verified.
- [x] **10.2 Frontend Deployment Ready:**
  - Next.js production build verified (`next build` compiled with 0 errors).
  - Configured for single-click deployment on Vercel.

---

### Phase 11: Documentation & Submission Deliverables
- [x] **11.1 Comprehensive `README.md`:**
  - System Architecture diagram (Mermaid).
  - End-to-end Sequence & Dataflow diagram (Mermaid).
  - Sub-agent handoffs explained.
  - Local setup & Docker instructions.
  - API endpoints documentation.
  - 3–5 Minute Video Demo Script with timing and talking points.
- [x] **11.2 Public GitHub Repository:**
  - Human-style English commit history.
  - Zero secrets committed (`.env.example` provided).
  - Repository link: https://github.com/FARINATTAR/ai-job-chat-assistant-

