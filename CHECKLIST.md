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
- [ ] **1.1 Define Job Schema:**
  - Standard fields: `id`, `title`, `company`, `location`, `remote` (bool), `experience_required`, `skills` (list), `description`, `source_url`, `posted_at`.
- [ ] **1.2 Build Scraper Client (`scraper/`):**
  - Use legal, reliable public APIs & job boards (Arbeitnow, Remotive, Greenhouse/Lever open endpoints) to avoid IP bans/CAPTCHAs.
  - Implement retry logic with exponential backoff and rate-limiting.
- [ ] **1.3 Taxonomy & Data Extraction:**
  - Standardized tech skill extractor (e.g., regex + taxonomy for Python, React, Docker, Node.js, etc.).
  - Experience level parser (maps "Entry", "3+ years", etc. to integer ranges).
- [ ] **1.4 Dataset Generation & Verification:**
  - Scrape and deduplicate 1,500 – 2,000 real job records.
  - Save to `data/jobs.json`.
  - Validate dataset completeness with a verification script.

---

### Phase 2: Backend Core & Database Setup (FastAPI)
- [ ] **2.1 Monorepo / Backend Skeleton:**
  - Setup FastAPI app structure: `app/core`, `app/agents`, `app/api`, `app/services`, `app/models`.
  - Configure environment management (`pydantic-settings`), logging, and CORS.
- [ ] **2.2 In-Memory Job Repository (`JobRepository`):**
  - Load `jobs.json` into memory on app startup for sub-millisecond querying and indexing.
- [ ] **2.3 Database & Application Schema (SQLAlchemy + Alembic):**
  - Model: `applications` (`id`, `session_id`, `job_id`, `applied_date`, `status`, `notes`).
  - Add DB-level Unique Constraint on `(session_id, job_id)` to prevent duplicates.
  - Support SQLite for local testing and PostgreSQL (Neon) for production.
- [ ] **2.4 Session & Context Store:**
  - In-memory/Redis/DB session store holding:
    - User resume profile
    - `last_results` (Job ID list matching the numbers 1, 2, 3 shown in chat)
    - Active query filters (e.g. `remote=True`, `skills=['React']`)
    - Chat message history

---

### Phase 3: Sub-Agent 1 — Resume Parser Agent
- [ ] **3.1 Document Text Extraction:**
  - Support PDF parsing via `PyMuPDF` (`fitz`) / `pdfplumber`.
  - Support DOCX parsing via `python-docx`.
- [ ] **3.2 Structured LLM Extraction:**
  - Pydantic Schema: `Name`, `Contact` (Email, Phone, LinkedIn), `Designation`, `Skills` (categorized), `Experience` (years + roles), `Education`, `Projects`.
  - Native structured output using Gemini / OpenAI API.
- [ ] **3.3 Resume Edge-Case Handling (Mandatory):**
  - Corrupt or unreadable files.
  - Scanned image PDFs without selectable text (returns clear user guidance).
  - Unsupported file formats.

---

### Phase 4: Sub-Agent 2 — Job Matcher Engine
- [ ] **4.1 Deterministic Match Engine:**
  - Skill overlap calculation with synonym support (e.g., `JS` == `JavaScript`, `FastAPI` == `Python`).
  - Designation/title similarity scoring.
  - Experience suitability matching.
  - Overall match score (0–100%).
- [ ] **4.2 Grounded Match Reason Generator:**
  - Generates bulleted match highlights (e.g., *"Matched 4/5 skills: Python, FastAPI, Docker, SQL; matches your 2 yrs experience"*).
- [ ] **4.3 Natural Language Filter Refiner:**
  - Parse conversational modifications:
    - *"Show only remote roles"*
    - *"Jobs with React or TypeScript"*
    - *"Filter for Bangalore / Delhi / US"*
    - *"Reset filters"*
  - Stack filters persistently across chat turns.
- [ ] **4.4 Matcher Edge-Case Handling (Mandatory):**
  - Graceful message when zero jobs match: suggest specific filters to loosen.

---

### Phase 5: Sub-Agent 3 — Application & Tracker Agent
- [ ] **5.1 Reference Resolver:**
  - Support index numbers: *"apply to job 1"*, *"apply to the second one"*.
  - Support direct Job IDs: *"apply to job #1428"*.
- [ ] **5.2 Application Persistence & Deduplication:**
  - Validate job exists.
  - Check for existing application under current `session_id`.
  - Save application record with status `APPLIED` and current timestamp.
- [ ] **5.3 Application Tracking Query:**
  - Respond to *"show my applied jobs"* or *"what jobs have I applied to?"*.
  - List job title, company, applied date, and status.
- [ ] **5.4 Application Edge-Case Handling (Mandatory):**
  - Invalid job reference (e.g., user asks for "job 7" when only 3 were listed).
  - Attempting to apply before uploading a resume (gentle prompt to upload first).
  - Duplicate application attempt (clear warning with timestamp of original application).

---

### Phase 6: Orchestrator Agent & Real-Time Streaming
- [ ] **6.1 Master Orchestrator Architecture:**
  - Tool-calling loop with system prompt routing between:
    - `parse_resume_tool`
    - `match_jobs_tool`
    - `refine_filter_tool`
    - `apply_job_tool`
    - `track_applications_tool`
- [ ] **6.2 Agent-to-Agent Handoff Events:**
  - Emit real-time events over Server-Sent Events (SSE):
    - `event: agent_start` -> `{"agent": "Orchestrator", "thought": "Analyzing user intent..."}`
    - `event: handoff` -> `{"from": "Orchestrator", "to": "ResumeParser", "reason": "New document uploaded"}`
    - `event: tool_result` -> `{"status": "success", "summary": "Extracted 12 skills"}`
    - `event: token` -> Live text streaming of final response
- [ ] **6.3 Guardrails:**
  - Loop limit cap (prevent infinite tool calls).
  - Off-topic redirection (politely guide user back to job searching).

---

### Phase 7: Frontend UI/UX (Next.js + Tailwind + shadcn/ui)
- [ ] **7.1 Modern Conversational Chat Interface:**
  - Clean chat layout (not a plain form).
  - Markdown message rendering with streaming text support.
- [ ] **7.2 Resume Upload Component:**
  - Drag-and-drop zone directly in chat or side dock.
  - Displays parsed profile card (Name, Designation, Skills badges, Experience).
- [ ] **7.3 Interactive Job Cards:**
  - Title, Company, Location, Remote tag, Experience badge.
  - Match percentage score with visual progress indicator.
  - Grounded match reason callout.
  - Quick **"Apply Now"** button directly on the card (in addition to natural chat apply).
- [ ] **7.4 Live Agent Trace Indicator:**
  - Expandable badge/pill in chat showing agent handoffs:
    `[Orchestrator] ➔ [JobMatcher] ➔ [Searching 1,842 listings]`.
- [ ] **7.5 Applied Jobs Drawer / Tab:**
  - Visual panel showing all applied jobs, timestamps, and status badges.
- [ ] **7.6 Suggested Quick Prompts:**
  - Chips: *"Show only remote jobs"*, *"Jobs matching Python"*, *"What have I applied to?"*.

---

### Phase 8: High-Impact Differentiators (Top Novel Features)
- [ ] **8.1 Skill-Gap Analysis & Readiness Score:**
  - For each recommended job, show what skills the candidate is missing and provide a 1-sentence tip.
- [ ] **8.2 One-Click Tailored Cover Pitch:**
  - In chat, user can ask: *"Write a short pitch for job 2"*.
  - Generates a customized 3-sentence application note based on the candidate's actual projects.

---

### Phase 9: Testing & Edge-Case Verification
- [ ] **9.1 Automated Test Suite (`pytest`):**
  - Unit tests for Resume Parser (valid PDF, valid DOCX, empty file, corrupted file).
  - Unit tests for Matcher Engine (synonyms, filter stacking, top-k ranking).
  - Integration tests for Apply & Dedupe flows.
- [ ] **9.2 Verification of 3 Mandatory Assessment Edge Cases:**
  - Case 1: Unreadable/malformed resume -> friendly error message.
  - Case 2: Zero job matches -> advice on broadening filters.
  - Case 3: Invalid job reference -> clear correction.

---

### Phase 10: Production Deployment
- [ ] **10.1 Backend Deployment (Render / Railway / Fly.io):**
  - Containerize via Dockerfile.
  - Connect to cloud Postgres (Neon.tech).
  - Health check endpoint `/health` verified.
- [ ] **10.2 Frontend Deployment (Vercel):**
  - Deploy Next.js app on Vercel with environment variables set.
  - Test CORS and live SSE streaming from deployed backend.
- [ ] **10.3 Live Smoke Test:**
  - Perform complete end-to-end user journey on the live production URL.

---

### Phase 11: Documentation & Submission Deliverables
- [ ] **11.1 Comprehensive `README.md`:**
  - System Architecture diagram (Mermaid).
  - Dataflow diagram (upload -> parse -> match -> apply -> track).
  - Sub-agent handoff explanation.
  - Local setup & Docker instructions.
  - API endpoints documentation.
- [ ] **11.2 Public GitHub Repository:**
  - Clean commit history following Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`).
  - No secret keys in repo (`.env.example` provided).
- [ ] **11.3 Video Demo Recording (3–5 Minutes):**
  - Full walkthrough: Upload resume -> Auto-parse -> Job recommendations -> Conversational filter refinement -> Apply by index -> View applied jobs -> Error handling demonstration.

