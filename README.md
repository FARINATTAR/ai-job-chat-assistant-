# AI Job Chat Assistant

> **Company:** Hidani Tech  
> **Position:** Software Development Engineer (SDE) Intern - AI Agents & Automation  
> **Candidate:** Farin Attar  
> **Live Demo:** [https://ai-job-chat-assistant.vercel.app](https://ai-job-chat-assistant.vercel.app) *(Deploy link)*  
> **GitHub Repository:** [https://github.com/FARINATTAR/ai-job-chat-assistant-](https://github.com/FARINATTAR/ai-job-chat-assistant-)  

---

## Project Overview

**AI Job Chat Assistant** is a production-ready conversational agent that ingests candidate resumes (PDF or DOCX), automatically parses their skills, experience, and designation, recommends highly-matching jobs from a dataset of **over 2,900 real-world job listings**, allows natural conversational filtering (e.g. *"show only remote roles"*, *"jobs needing React"*), applies to jobs on request (*"apply to job 3"*), and tracks application statuses without duplication.

### Key Technical Highlights
- **LLM Tool-Calling Orchestrator:** Native function-calling schema loop (Gemini / OpenAI) with conversation history context and high-coverage regex fallback. Fully defendable in technical interviews.
- **Real-Time Agent Activity Trace:** Server-Sent Events (SSE) stream agent thoughts, tool calls, and handoffs to the UI in real time (`[Orchestrator] ➔ Delegating to [JobMatcher]`).
- **Grounded Matching & Zero Hallucination:** Deterministic skill overlap and experience calculation with LLM-generated explanations strictly bound to factual overlap.
- **Conversational Index-to-ID Resolution:** Seamlessly translates natural requests like *"apply to job 2"* into concrete IDs using session-level result caching.
- **2,900+ Real Job Postings Dataset:** Crawled from Jobfound, Arbeitnow, Remotive public APIs and LinkedIn/Indeed/Glassdoor via JSearch API with automatic deduplication.
- **Production Persistence:** PostgreSQL (Neon serverless) / SQLite with unique constraints `(session_id, job_id)` to prevent duplicate applications across container restarts.

---

## System Architecture

```mermaid
graph TD
    subgraph Frontend ["Frontend (Next.js 14 + Tailwind + Lucide)"]
        UI["Conversational Chat Window"]
        Trace["Live Agent Trace Indicator (Handoffs)"]
        Upload["Resume Drag & Drop (PDF/DOCX)"]
        Cards["Interactive Job Cards (Match % + Quick Apply)"]
        Drawer["Applied Jobs Drawer"]
    end

    subgraph BackendGateway ["FastAPI Backend Gateway"]
        EP_Upload["POST /api/upload"]
        EP_Chat["POST /api/chat (SSE Stream)"]
        EP_Apps["GET /api/applications"]
        EP_Health["GET /api/health"]
    end

    subgraph MultiAgentCore ["Multi-Agent Architecture"]
        Orchestrator["Master Orchestrator Agent<br/>(Intent Detection & Context Loop)"]
        SessionStore["In-Memory Session Context<br/>(last_results mapping, active filters, history)"]
        ParserAgent["ResumeParser Sub-Agent<br/>(PyMuPDF / docx + Structured LLM)"]
        MatcherAgent["JobMatcher Sub-Agent<br/>(Deterministic Scoring + Grounded Reasons)"]
        ApplyAgent["ApplicationManager Sub-Agent<br/>(Index Resolver + Dedupe + Tracking)"]
    end

    subgraph DataStorage ["Data & Storage Layer"]
        JobRepo[("JobRepository<br/>2,900+ Real Jobs in Memory")]
        Database[("Database<br/>SQLite / Neon PostgreSQL")]
        LLMProvider[("LLM Client<br/>Gemini 1.5/2.0 Flash / OpenAI")]
    end

    %% Client Interactions
    UI -->|Natural Chat & Refinements| EP_Chat
    Upload -->|Upload Resume File| EP_Upload
    Drawer -->|Fetch Status| EP_Apps
    Cards -->|Quick Apply| EP_Chat

    %% API to Orchestrator
    EP_Upload --> ParserAgent
    EP_Chat --> Orchestrator
    EP_Apps --> ApplyAgent

    %% Agent Routing
    Orchestrator <--> SessionStore
    Orchestrator -->|Handoff / Tool Call| MatcherAgent
    Orchestrator -->|Handoff / Tool Call| ApplyAgent

    %% Agent Integrations
    ParserAgent --> LLMProvider
    MatcherAgent --> JobRepo
    MatcherAgent --> LLMProvider
    ApplyAgent --> Database

    %% Real-time SSE Stream
    Orchestrator -.->|SSE Events: agent_handoff, tokens, job_results| UI
```

---

## End-to-End Dataflow & Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Candidate
    participant UI as Next.js UI
    participant API as FastAPI Backend
    participant Orch as Master Orchestrator
    participant Parser as ResumeParser Sub-Agent
    participant Matcher as JobMatcher Sub-Agent
    participant Apply as ApplicationManager
    participant DB as Neon DB / JobRepo

    Candidate->>UI: Uploads resume.pdf
    UI->>API: POST /api/upload
    API->>Parser: parse_document(file_bytes)
    Parser-->>API: Structured ResumeProfile (skills, exp, designation)
    API-->>UI: Parsed Profile Card displayed

    Candidate->>UI: "Recommend matching jobs"
    UI->>API: POST /api/chat (SSE Stream)
    API->>Orch: stream_chat("recommend matching jobs")
    Orch->>UI: SSE Event: agent_handoff -> JobMatcher
    Orch->>Matcher: match_jobs(profile, active_filters)
    Matcher->>DB: Query 2,900+ jobs in memory
    DB-->>Matcher: Filtered & Scored Candidates
    Matcher-->>Orch: Top 5 Jobs + Grounded Match Reasons
    Orch->>Orch: Update session.last_results = [job1, job2, job3...]
    Orch->>UI: SSE Event: job_results + Assistant response

    Candidate->>UI: "Show only remote roles"
    UI->>API: POST /api/chat (SSE Stream)
    Orch->>Orch: session.active_filters.remote = True
    Orch->>Matcher: match_jobs(profile, remote=True)
    Matcher-->>UI: Updated Remote-only Job Cards

    Candidate->>UI: "Apply to job 2"
    UI->>API: POST /api/chat (SSE Stream)
    Orch->>UI: SSE Event: agent_handoff -> ApplicationManager
    Orch->>Apply: apply_to_job(ref="2")
    Apply->>Apply: Resolve "2" -> session.last_results[1]
    Apply->>DB: Insert into applications table
    alt First Time Applying
        DB-->>Apply: Saved successfully
        Apply-->>UI: "Successfully applied to Frontend Engineer at Acme!"
    else Already Applied
        DB-->>Apply: Unique Constraint Detected
        Apply-->>UI: "You already applied to this job on [Date]."
    end

    Candidate->>UI: "Show my applied jobs"
    UI->>API: POST /api/chat (SSE Stream)
    Orch->>Apply: list_applied_jobs()
    Apply-->>UI: List of applied positions with status badges
```

---

## Edge-Case Handling (Mandatory Assessment Criteria)

The application handles all edge cases required by the Hidani Tech assessment:

| Edge Case Scenario | Expected Behavior | Implementation |
|---|---|---|
| **Unreadable / Corrupt Resume** | Scanned PDFs without text layer, 0-byte files, or corrupt binaries are detected. | Raises `UnreadableDocumentError` with friendly advice to provide a text-based PDF/DOCX. |
| **Unsupported File Formats** | User attempts uploading `.exe`, `.txt`, `.png`. | Rejected with HTTP 400 with clear supported format instructions (`.pdf`, `.docx`). |
| **No Matching Jobs** | Strict filter combination returns 0 results (e.g. Remote + obscure tech). | System notifies candidate politely and provides actionable advice on broadening filters. |
| **Invalid Job Reference** | User says *"apply to job 99"* when only 3 jobs were listed. | System warns that index 99 is out of range and prompts to choose between 1 and 3. |
| **Apply Before Resume Upload** | Candidate attempts to apply before uploading qualifications. | System gently halts the application and requests resume upload first. |
| **Duplicate Applications** | User applies to the same job twice. | Prevented via DB unique constraint `(session_id, job_id)`; returns existing application timestamp. |

---

## Project Directory Structure

```text
hidani assessment/
│
├── data/                                  # Datasets & Taxonomies
│   ├── jobs.json                          # 2,900+ real job records (Deliverable)
│   └── skills_taxonomy.json               # Standardized skills & synonyms
│
├── scraper/                               # Modular Job Scraper Pipeline (Deliverable)
│   ├── __init__.py
│   ├── run_scraper.py                     # CLI entrypoint to crawl data/jobs.json
│   ├── base_source.py                     # Abstract Base Scraper class (retry, rate limit)
│   ├── jobfound_source.py                 # Source 1: Jobfound.org REST API
│   ├── arbeitnow_source.py                # Source 2: Arbeitnow public API
│   └── skill_extractor.py                 # Skill & Experience taxonomy extractor
│
├── backend/                               # Python FastAPI Backend
│   ├── app/
│   │   ├── main.py                        # FastAPI entry, CORS, lifespan startup loader
│   │   ├── config.py                      # Pydantic Settings & environment variables
│   │   ├── api/
│   │   │   ├── endpoints.py               # /upload, /chat (SSE), /applications, /health
│   │   │   └── dependencies.py            # DB session & session store dependencies
│   │   ├── core/
│   │   │   ├── db.py                      # SQLAlchemy engine & SQLite/Neon Postgres setup
│   │   │   ├── events.py                  # SSE streaming helpers (handoff, thoughts, tokens)
│   │   │   └── session.py                 # In-memory session store (last_results, filters)
│   │   ├── models/
│   │   │   ├── db_models.py               # SQLAlchemy ApplicationDB model (unique constraint)
│   │   │   └── schemas.py                 # Pydantic schemas (ResumeProfile, JobMatch, etc.)
│   │   ├── repositories/
│   │   │   ├── job_repo.py                # In-memory fast search over 2,900+ jobs
│   │   │   └── app_repo.py                # Database CRUD with duplicate prevention
│   │   ├── llm/
│   │   │   ├── client.py                  # Provider-agnostic LLM wrapper (Gemini / OpenAI)
│   │   │   └── prompts.py                 # System prompts for Orchestrator & sub-agents
│   │   ├── services/
│   │   │   └── document_extractor.py      # PDF & DOCX text extraction with validation
│   │   └── agents/
│   │       ├── orchestrator.py            # Master agent loop & intent router
│   │       ├── parser_agent.py            # Sub-agent: PDF/DOCX to ResumeProfile
│   │       ├── matcher_agent.py           # Sub-agent: Skill scoring & grounded match reason
│   │       └── apply_agent.py             # Sub-agent: Index-to-ID resolver & tracking
│   ├── tests/
│   │   ├── test_parser.py                 # 5 tests: PDF/DOCX, unreadable, corrupt, skills, edu & projects
│   │   ├── test_matcher.py                # 5 tests: scoring, remote filter, zero matches, seniority gate
│   │   ├── test_apply.py                  # 5 tests: index resolution, duplicate prevention, list apps
│   │   ├── test_orchestrator.py           # 8 tests: tool calling, intent detection, filters, SSE streaming
│   │   ├── test_api_endpoints.py          # 4 tests: health check, closed job reporting, upload resume & validation
│   │   ├── test_job_repo.py               # 2 tests: job upsert, deduplication, active/inactive state
│   │   └── test_jsearch.py                # 2 tests: JSearch adapter fallback & normalized schema
│   ├── requirements.txt                   # Backend dependencies
│   └── Dockerfile                         # Containerization for deployment
│
├── frontend/                              # Next.js 14 (App Router) + TypeScript
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx                 # Root layout
│   │   │   ├── page.tsx                   # Main conversational interface (in-chat resume upload + filters)
│   │   │   └── globals.css                # Tailwind styling
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   └── MarkdownRenderer.tsx   # Custom lightweight markdown formatter
│   │   │   ├── jobs/
│   │   │   │   └── JobCard.tsx            # Match %, grounded reasons, 1-click apply with sync
│   │   │   └── applications/
│   │   │       └── AppliedJobsDrawer.tsx  # Slide-out drawer tracking applied jobs with backdrop close
│   │   └── lib/
│   │       └── api.ts                     # Backend API client, SSE reader & TypeScript schemas
│   ├── package.json
│   ├── tailwind.config.ts
│   └── tsconfig.json
│
├── CHECKLIST.md                           # Progress checklist
├── SYSTEM_DESIGN.md                       # Comprehensive design blueprint
└── README.md                              # This documentation
```

---

## Quickstart: Local Setup Guide

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 1. Clone the Repository
```bash
git clone https://github.com/FARINATTAR/ai-job-chat-assistant-.git
cd ai-job-chat-assistant-
```

### 2. Backend Setup
```bash
# Navigate to backend
cd backend

# Install Python dependencies
pip install -r requirements.txt

# (Optional) Add your Gemini API key in backend/.env:
# GEMINI_API_KEY=your_key_here

# Run backend test suite (31 tests)
python -m pytest

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Backend will be live at `http://localhost:8000`. Swagger API docs available at `http://localhost:8000/docs`.

### 3. Frontend Setup
```bash
# Open a new terminal and navigate to frontend
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```
Frontend will be live at `http://localhost:3000`.

---

## Cloud Deployment Guide

### Backend (Render / Railway / Fly.io)
1. Link your GitHub repository.
2. Select **Docker** environment (Dockerfile is located at `backend/Dockerfile`).
3. Set Environment Variables:
   - `PORT=8000`
   - `GEMINI_API_KEY=your_key`
   - `DATABASE_URL=postgresql://user:password@ep-xyz.neon.tech/neondb` (Free serverless Postgres on [Neon.tech](https://neon.tech))

### Frontend (Vercel)
1. Import repository on [Vercel](https://vercel.com).
2. Set Root Directory to `frontend`.
3. Add Environment Variable:
   - `NEXT_PUBLIC_API_URL=https://your-backend-url.onrender.com`
4. Deploy!

---
