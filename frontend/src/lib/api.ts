/**
 * Frontend API client for backend communication.
 */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getSessionId(): string {
  if (typeof window === "undefined") return "server_session";
  let sid = localStorage.getItem("job_chat_session_id");
  if (!sid) {
    sid = "sess_" + Math.random().toString(36).substring(2, 12) + Date.now().toString(36);
    localStorage.setItem("job_chat_session_id", sid);
  }
  return sid;
}

export interface ResumeProfile {
  name: string;
  contact: {
    email?: string;
    phone?: string;
    linkedin?: string;
    github?: string;
  };
  designation: string;
  skills: string[];
  years_of_experience: number;
  experience_summary?: string;
}

export interface JobMatch {
  index: number;
  match_score: number;
  match_reasons: string[];
  matched_skills: string[];
  missing_skills: string[];
  job: {
    id: string;
    title: string;
    company: string;
    location: string;
    remote: boolean;
    experience_required: number;
    skills: string[];
    description: string;
    source_url: string;
    source?: string;
    is_active?: boolean;
    posted_at?: string;
  };
}

export interface ApplicationRecord {
  id: string;
  session_id: string;
  job_id: string;
  job_title: string;
  company: string;
  location: string;
  applied_at: string;
  status: string;
  source_url?: string;
}

export async function uploadResume(file: File, sessionId: string) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/api/upload`, {
    method: "POST",
    headers: {
      "X-Session-Id": sessionId,
    },
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed with status ${res.status}`);
  }

  return res.json();
}

export async function fetchApplications(sessionId: string): Promise<ApplicationRecord[]> {
  const res = await fetch(`${API_BASE_URL}/api/applications`, {
    headers: {
      "X-Session-Id": sessionId,
    },
  });

  if (!res.ok) {
    throw new Error("Failed to fetch applications.");
  }

  return res.json();
}

export async function applyToJobDirect(jobId: string, sessionId: string) {
  const res = await fetch(`${API_BASE_URL}/api/apply`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Id": sessionId,
    },
    body: JSON.stringify({ job_id: jobId }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to apply.");
  }

  return res.json();
}

export async function reportClosedJobDirect(jobId: string) {
  const res = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/report-closed`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to report job.");
  }
  return res.json();
}

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`);
    return await res.json();
  } catch (e) {
    return { status: "offline", jobs_loaded: 0 };
  }
}

