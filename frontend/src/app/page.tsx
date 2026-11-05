"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Send,
  Briefcase,
  Sparkles,
  Bot,
  User,
  UploadCloud,
  FileText,
  Loader2,
  AlertCircle,
  CheckCircle,
  CheckCircle2,
  ArrowLeft,
  ArrowRight,
  Paperclip,
  Globe,
  Zap,
  Code2,
  Building2,
  MapPin,
  Clock,
  RotateCcw,
} from "lucide-react";
import { getSessionId, API_BASE_URL, JobMatch, ResumeProfile, uploadResume, applyToJobDirect } from "@/lib/api";
import { JobCard } from "@/components/jobs/JobCard";
import { AppliedJobsDrawer } from "@/components/applications/AppliedJobsDrawer";
import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  jobResults?: JobMatch[];
}

type AppStep = "upload" | "filters" | "chat";

export default function Home() {
  const [sessionId, setSessionId] = useState<string>(() => {
    if (typeof window !== "undefined") return getSessionId();
    return "session_init";
  });

  // Default to interactive conversational chat as required by assessment
  const [step, setStep] = useState<AppStep>("chat");

  // Resume
  const [currentProfile, setCurrentProfile] = useState<ResumeProfile | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [showAllSkills, setShowAllSkills] = useState(false);

  // Filters
  const [selectedExp, setSelectedExp] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);

  // Chat
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [appliedJobIds, setAppliedJobIds] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatFileInputRef = useRef<HTMLInputElement>(null);

  // Interactive top filter bar state
  const [activeWorkMode, setActiveWorkMode] = useState<"all" | "remote" | "onsite">("all");
  const [activeExpLevel, setActiveExpLevel] = useState<"all" | "fresher" | "mid">("all");
  const [activeDatePosted, setActiveDatePosted] = useState<"all" | "24h" | "3d" | "7d">("all");

  useEffect(() => {
    setSessionId(getSessionId());
  }, []);

  // Smart auto-scroll: if job cards are rendered, scroll to TOP of the results so Job #1 is in view!
  useEffect(() => {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.role === "assistant" && lastMsg.jobResults && lastMsg.jobResults.length > 0) {
      const el = document.getElementById(`msg-${lastMsg.id}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
    }
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // ─── In-Chat Resume Upload ───────────────────────────
  const handleFileUploadInChat = async (file: File) => {
    setUploading(true);
    const userMsgId = String(Date.now());
    const botMsgId = String(Date.now() + 1);

    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: "user",
        content: `Uploaded resume: ${file.name}`,
      },
      {
        id: botMsgId,
        role: "assistant",
        content: "Parsing your resume and extracting technical skills, experience, and designation...",
      },
    ]);

    try {
      const data = await uploadResume(file, sessionId);
      if (data?.profile) {
        setCurrentProfile(data.profile);
        setActiveWorkMode("all");
        setActiveExpLevel("all");
        const p = data.profile;
        const skillsList = p.skills?.slice(0, 8).join(", ") || "General Tech";

        // Build education summary
        let educationLine = "";
        if (p.education && p.education.length > 0) {
          const eduItems = p.education.map((e: any) => {
            const parts = [e.degree, e.institution, e.year].filter(Boolean);
            return parts.join(", ");
          });
          educationLine = `\n- **Education:** ${eduItems.join("; ")}`;
        }

        // Build projects summary
        let projectsLine = "";
        if (p.projects && p.projects.length > 0) {
          const projNames = p.projects.slice(0, 4).map((pr: any) => pr.name);
          projectsLine = `\n- **Projects:** ${projNames.join(", ")}`;
        }

        // Build contact summary
        let contactLine = "";
        const contactParts: string[] = [];
        if (p.contact?.email) contactParts.push(p.contact.email);
        if (p.contact?.phone) contactParts.push(p.contact.phone);
        if (p.contact?.linkedin) contactParts.push(`[LinkedIn](${p.contact.linkedin})`);
        if (p.contact?.github) contactParts.push(`[GitHub](${p.contact.github})`);
        if (contactParts.length > 0) {
          contactLine = `\n- **Contact:** ${contactParts.join(" | ")}`;
        }

        const parseSummary = `**Resume parsed successfully**\n\n- **Candidate:** ${p.name || "Candidate"}${contactLine}\n- **Designation:** ${p.designation || "Software Engineer"}\n- **Experience:** ${p.years_of_experience || 0} years\n- **Identified Skills:** ${skillsList}${educationLine}${projectsLine}\n\nFinding top matching jobs for your profile...`;

        setMessages((prev) =>
          prev.map((m) => (m.id === botMsgId ? { ...m, content: parseSummary } : m))
        );

        // Auto trigger recommendations for the newly uploaded resume
        await handleSendMessage("recommend matching jobs for my uploaded resume");
      }
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === botMsgId
            ? { ...m, content: `Could not parse resume: ${err.message || "Unreadable file format. Please upload PDF or DOCX."}` }
            : m
        )
      );
    } finally {
      setUploading(false);
    }
  };

  // ─── Resume Upload ────────────────────────────────────
  const handleFileUpload = async (file: File) => {
    setUploadError(null);
    setUploading(true);
    try {
      const data = await uploadResume(file, sessionId);
      if (data?.profile) {
        setCurrentProfile(data.profile);
        setStep("filters");
      }
    } catch (err: any) {
      setUploadError(err.message || "Failed to parse resume.");
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.[0]) handleFileUpload(e.dataTransfer.files[0]);
  };

  // ─── Filters → Chat ──────────────────────────────────
  const handleStartChat = () => {
    // Build an initial query from filters
    let query = "Recommend matching jobs for my resume";
    if (selectedExp) query += ` for ${selectedExp}`;
    if (selectedSource) query += ` from ${selectedSource}`;

    setMessages([]);
    setStep("chat");

    // Auto-send first query after transition
    setTimeout(() => handleSendMessage(query), 100);
  };

  // ─── Filter Bar Handler ────────────────────────────────
  const handleFilterChange = (filterType: string, value: string) => {
    if (isStreaming) return;

    let wm = activeWorkMode;
    let el = activeExpLevel;
    let dp = activeDatePosted;

    if (filterType === "workMode") {
      wm = value as "all" | "remote" | "onsite";
      setActiveWorkMode(wm);
    } else if (filterType === "expLevel") {
      el = value as "all" | "fresher" | "mid";
      setActiveExpLevel(el);
    } else if (filterType === "datePosted") {
      dp = value as "all" | "24h" | "3d" | "7d";
      setActiveDatePosted(dp);
    } else {
      wm = "all";
      el = "all";
      dp = "all";
      setActiveWorkMode("all");
      setActiveExpLevel("all");
      setActiveDatePosted("all");
    }

    const overrides: Record<string, any> = {
      remote: wm === "remote" ? true : wm === "onsite" ? false : null,
      max_experience: el === "fresher" ? 1 : el === "mid" ? 4 : null,
      posted_within_days: dp === "24h" ? 1 : dp === "3d" ? 3 : dp === "7d" ? 7 : null,
    };

    const parts: string[] = [];
    if (wm === "remote") parts.push("remote");
    else if (wm === "onsite") parts.push("on-site");
    if (el === "fresher") parts.push("fresher (0-1 yr)");
    else if (el === "mid") parts.push("mid-level (2+ yrs)");
    if (dp === "24h") parts.push("posted in last 24 hours");
    else if (dp === "3d") parts.push("posted in last 3 days");
    else if (dp === "7d") parts.push("posted in past week");

    const msg = parts.length > 0
      ? `Show ${parts.join(", ")} software engineering jobs`
      : "Show all jobs without filters";

    handleSendMessage(msg, overrides);
  };

  // ─── Chat ─────────────────────────────────────────────
  const handleSendMessage = async (customMessage?: string, filterOverrides?: Record<string, any>) => {
    const textToSend = (customMessage || inputMessage).trim();
    if (!textToSend || isStreaming) return;

    setInputMessage("");

    const userMsgId = "user_" + Date.now();
    const assistantMsgId = "asst_" + Date.now();

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: textToSend },
      { id: assistantMsgId, role: "assistant", content: "" },
    ]);

    setIsStreaming(true);
    let assistantText = "";
    let receivedJobs: JobMatch[] | undefined = undefined;

    try {
      const body: Record<string, any> = { session_id: sessionId, message: textToSend };
      if (filterOverrides) body.filter_overrides = filterOverrides;

      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.body) throw new Error("No response stream available.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          if (!block.trim()) continue;
          const matchEvent = block.match(/^event:\s*(.+)$/m);
          const matchData = block.match(/^data:\s*(.+)$/m);
          const eventType = matchEvent ? matchEvent[1].trim() : "message";
          const rawData = matchData ? matchData[1].trim() : "";

          let parsedData: any = rawData;
          try { parsedData = JSON.parse(rawData); } catch {}

          if (eventType === "job_results") {
            receivedJobs = parsedData.jobs;
          } else if (eventType === "token") {
            assistantText += parsedData.content || "";
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: assistantText, jobResults: receivedJobs }
                  : m
              )
            );
          }
        }
      }
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? { ...m, content: `Error: ${err.message || "Could not reach backend."}` }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
    }
  };

  const handleApplyToJob = async (reference: string, jobId: string) => {
    try {
      const data = await applyToJobDirect(jobId, sessionId);
      setAppliedJobIds((prev) => {
        const next = new Set(prev);
        next.add(jobId);
        return next;
      });
      setMessages((prev) => [
        ...prev,
        {
          id: "apply_conf_" + Date.now(),
          role: "assistant",
          content: data.message || `Application submitted for Job #${reference}.`,
        },
      ]);
    } catch {
      await handleSendMessage(`apply to job ${reference}`);
    }
  };

  // ─── Render ───────────────────────────────────────────

  // Step 1: Upload Resume
  if (step === "upload") {
    return (
      <div className="flex flex-col h-screen bg-slate-50 antialiased">
        <Header
          onOpenDrawer={() => setIsDrawerOpen(true)}
          appliedCount={appliedJobIds.size}
        />

        <div className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-xl space-y-8">
            <div className="text-center space-y-2.5">
              <h2 className="text-3xl font-bold text-slate-900 tracking-tight">
                Upload Your Resume
              </h2>
              <p className="text-base text-slate-600">
                We will extract your skills, experience level, and designation to find the best matching roles.
              </p>
            </div>

            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all ${
                isDragging
                  ? "border-indigo-500 bg-indigo-50/60"
                  : "border-slate-300 hover:border-indigo-400 bg-white hover:bg-indigo-50/10 shadow-sm"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.[0]) handleFileUpload(e.target.files[0]);
                }}
              />
              {uploading ? (
                <div className="flex flex-col items-center gap-3 py-4">
                  <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
                  <p className="text-base text-indigo-600 font-medium">Extracting skills and experience...</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4 py-4">
                  <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                    <UploadCloud className="w-7 h-7" />
                  </div>
                  <div>
                    <p className="text-base font-semibold text-slate-900">
                      Drop your resume here or click to browse
                    </p>
                    <p className="text-sm text-slate-500 mt-1">Supports PDF or DOCX</p>
                  </div>
                </div>
              )}
            </div>

            {uploadError && (
              <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{uploadError}</span>
              </div>
            )}

            <div className="text-center pt-2">
              <button
                onClick={() => {
                  setStep("chat");
                  if (messages.length === 0) {
                    handleSendMessage("hi");
                  }
                }}
                className="text-sm font-semibold text-indigo-600 hover:text-indigo-700 hover:underline transition-colors"
              >
                Or explore jobs directly through chat without resume →
              </button>
            </div>
          </div>
        </div>

        <AppliedJobsDrawer isOpen={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} sessionId={sessionId} />
      </div>
    );
  }

  // Step 2: Filters
  if (step === "filters") {
    const expOptions = [
      { label: "Fresher (0-1 yr)", value: "freshers (0-1 year experience)" },
      { label: "Mid-Level (2-4 yrs)", value: "2-4 years experience" },
      { label: "Senior (5+ yrs)", value: "senior roles (5+ years)" },
      { label: "All Levels", value: "all experience levels" },
    ];

    const sourceOptions = [
      { label: "All Sources", value: "all sources" },
      { label: "LinkedIn", value: "LinkedIn" },
      { label: "Arbeitnow", value: "Arbeitnow" },
      { label: "Remotive", value: "Remotive" },
    ];

    const SKILLS_PREVIEW = 10;
    const allSkills = currentProfile?.skills || [];
    const visibleSkills = showAllSkills ? allSkills : allSkills.slice(0, SKILLS_PREVIEW);
    const hiddenCount = allSkills.length - SKILLS_PREVIEW;

    return (
      <div className="flex flex-col h-screen bg-slate-50 antialiased">
        <Header
          onOpenDrawer={() => setIsDrawerOpen(true)}
          appliedCount={appliedJobIds.size}
        />

        <div className="flex-1 overflow-y-auto">
          <div className="w-full max-w-2xl mx-auto px-6 py-10 space-y-10">
            {/* Profile summary */}
            {currentProfile && (
              <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-xl font-bold text-slate-900">{currentProfile.name}</p>
                    <p className="text-base text-slate-600 mt-0.5">{currentProfile.designation}</p>
                  </div>
                  <span className="text-sm font-medium px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-2">
                    <CheckCircle className="w-4 h-4" /> Resume parsed
                  </span>
                </div>
                {allSkills.length > 0 && (
                  <div className="pt-4 border-t border-slate-100">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
                      Extracted Skills ({allSkills.length})
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {visibleSkills.map((skill, i) => (
                        <span key={i} className="text-sm font-medium px-3 py-1 rounded-lg bg-slate-100 text-slate-700 border border-slate-200">
                          {skill}
                        </span>
                      ))}
                      {!showAllSkills && hiddenCount > 0 && (
                        <button
                          onClick={() => setShowAllSkills(true)}
                          className="text-sm font-medium px-3 py-1 rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-200 hover:bg-indigo-100 transition-colors cursor-pointer"
                        >
                          +{hiddenCount} more
                        </button>
                      )}
                      {showAllSkills && allSkills.length > SKILLS_PREVIEW && (
                        <button
                          onClick={() => setShowAllSkills(false)}
                          className="text-sm font-medium px-3 py-1 rounded-lg bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100 transition-colors cursor-pointer"
                        >
                          Show less
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Experience Level */}
            <div className="space-y-4">
              <h3 className="text-lg font-bold text-slate-900">Experience Level</h3>
              <div className="grid grid-cols-2 gap-3">
                {expOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setSelectedExp(selectedExp === opt.value ? null : opt.value)}
                    className={`p-4 rounded-xl border text-base font-medium text-left transition-all ${
                      selectedExp === opt.value
                        ? "border-indigo-500 bg-indigo-50 text-indigo-700 shadow-sm"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:shadow-xs"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Job Source */}
            <div className="space-y-4">
              <h3 className="text-lg font-bold text-slate-900">Job Source</h3>
              <div className="grid grid-cols-2 gap-3">
                {sourceOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setSelectedSource(selectedSource === opt.value ? null : opt.value)}
                    className={`p-4 rounded-xl border text-base font-medium text-left transition-all ${
                      selectedSource === opt.value
                        ? "border-indigo-500 bg-indigo-50 text-indigo-700 shadow-sm"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:shadow-xs"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-between pt-4">
              <button
                onClick={() => setStep("upload")}
                className="px-5 py-2.5 rounded-xl text-base font-medium text-slate-600 hover:text-slate-800 flex items-center gap-2 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" /> Back to resume
              </button>
              <button
                onClick={handleStartChat}
                className="px-7 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-base font-semibold flex items-center gap-2 transition-all shadow-sm"
              >
                Find Jobs <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>

        <AppliedJobsDrawer isOpen={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} sessionId={sessionId} />
      </div>
    );
  }

  // Step 3: Chat
  return (
    <div className="flex flex-col h-screen bg-slate-50 antialiased">
      <Header
        onOpenDrawer={() => setIsDrawerOpen(true)}
        appliedCount={appliedJobIds.size}
        profileName={currentProfile?.name}
        onUploadClick={() => chatFileInputRef.current?.click()}
      />

      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Interactive Filter Bar */}
        <div className="border-b border-slate-200/80 bg-white/95 backdrop-blur-sm px-4 sm:px-6 py-2 shrink-0">
          <div className="max-w-4xl mx-auto flex flex-wrap items-center gap-x-3 gap-y-1.5">
            {/* Workplace Mode */}
            <div className="flex items-center gap-1 text-xs">
              <MapPin className="w-3.5 h-3.5 text-slate-400 mr-0.5 shrink-0" />
              {([
                { label: "All Modes", value: "all" },
                { label: "Remote", value: "remote" },
                { label: "On-Site", value: "onsite" },
              ] as const).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleFilterChange("workMode", opt.value)}
                  disabled={isStreaming}
                  className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                    activeWorkMode === opt.value
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="w-px h-5 bg-slate-200 hidden sm:block" />

            {/* Experience Level */}
            <div className="flex items-center gap-1 text-xs">
              <Briefcase className="w-3.5 h-3.5 text-slate-400 mr-0.5 shrink-0" />
              {([
                { label: "All Levels", value: "all" },
                { label: "Fresher (0-1 yr)", value: "fresher" },
                { label: "Mid (2+ yrs)", value: "mid" },
              ] as const).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleFilterChange("expLevel", opt.value)}
                  disabled={isStreaming}
                  className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                    activeExpLevel === opt.value
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="w-px h-5 bg-slate-200 hidden sm:block" />

            {/* Date Posted (Recency) */}
            <div className="flex items-center gap-1 text-xs">
              <Clock className="w-3.5 h-3.5 text-slate-400 mr-0.5 shrink-0" />
              {([
                { label: "All Time", value: "all" },
                { label: "Past 24h", value: "24h" },
                { label: "Past 3 Days", value: "3d" },
                { label: "Past Week", value: "7d" },
              ] as const).map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleFilterChange("datePosted", opt.value)}
                  disabled={isStreaming}
                  className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                    activeDatePosted === opt.value
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Reset All */}
            {(activeWorkMode !== "all" || activeExpLevel !== "all" || activeDatePosted !== "all") && (
              <>
                <div className="w-px h-5 bg-slate-200 hidden sm:block" />
                <button
                  onClick={() => handleFilterChange("reset", "all")}
                  disabled={isStreaming}
                  className="px-2.5 py-1 rounded-lg text-xs font-medium text-rose-600 bg-rose-50 hover:bg-rose-100 border border-rose-200/60 transition-all flex items-center gap-1"
                >
                  <RotateCcw className="w-3 h-3" />
                  Reset
                </button>
              </>
            )}
          </div>
        </div>

        {/* Messages scroll viewport: full-width so no vertical gray scrollbar line cuts through desktop */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 sm:px-6 py-6 space-y-5 max-w-4xl w-full mx-auto">
            {messages.length === 0 && (
              <div className="py-6 sm:py-10 px-4 max-w-2xl mx-auto text-center space-y-6">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100/80 text-xs font-semibold text-indigo-700 shadow-xs">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                  <span>AI Job Assistant</span>
                  <span className="text-indigo-300">•</span>
                  <span className="text-slate-600 font-normal">2,800+ Verified Roles</span>
                </div>

                <div className="space-y-2">
                  <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                    Find and explore engineering roles
                  </h2>
                  <p className="text-sm sm:text-base text-slate-600 max-w-lg mx-auto">
                    Upload your resume to get instant grounded recommendations, or explore opportunities directly through conversation.
                  </p>
                </div>

                {/* Drag and Drop Box in Welcome Screen */}
                <div
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setIsDragging(false);
                    if (e.dataTransfer.files?.[0]) handleFileUploadInChat(e.dataTransfer.files[0]);
                  }}
                  onClick={() => chatFileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-2xl p-6 sm:p-7 text-center cursor-pointer transition-all ${
                    isDragging
                      ? "border-indigo-500 bg-indigo-50/80"
                      : "border-slate-300 hover:border-indigo-400 bg-white hover:bg-indigo-50/20 shadow-xs"
                  }`}
                >
                  <div className="flex flex-col items-center gap-2.5">
                    <div className="w-11 h-11 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center border border-indigo-100">
                      <UploadCloud className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900">
                        Drop your resume here or click to browse
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">Supports PDF or DOCX format</p>
                    </div>
                  </div>
                </div>

                {/* Quick Action Suggestion Chips - Professional Lucide Icons, Zero Emojis */}
                <div className="space-y-2.5 text-left pt-2">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider text-center">
                    Or start with a conversational query
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {[
                      {
                        icon: Globe,
                        iconColor: "text-indigo-600 bg-indigo-50 border border-indigo-100",
                        label: "Remote developer roles",
                        query: "show only remote roles",
                        onSelect: () => {
                          setActiveWorkMode("remote");
                          handleSendMessage("show only remote roles", { remote: true });
                        },
                      },
                      {
                        icon: Zap,
                        iconColor: "text-amber-600 bg-amber-50 border border-amber-100",
                        label: "Entry-level / Fresher jobs (0-1 yr)",
                        query: "show fresher and entry level software jobs",
                        onSelect: () => {
                          setActiveExpLevel("fresher");
                          handleSendMessage("show fresher and entry level software jobs", { max_experience: 1 });
                        },
                      },
                      {
                        icon: Code2,
                        iconColor: "text-emerald-600 bg-emerald-50 border border-emerald-100",
                        label: "Roles needing React & TypeScript",
                        query: "jobs needing React and TypeScript",
                        onSelect: () => {
                          handleSendMessage("jobs needing React and TypeScript", { skills: ["React", "TypeScript"] });
                        },
                      },
                      {
                        icon: Building2,
                        iconColor: "text-violet-600 bg-violet-50 border border-violet-100",
                        label: "Top tech companies (Google, Meta)",
                        query: "show software engineer jobs at Google, Meta, or Amazon",
                        onSelect: () => {
                          handleSendMessage("show software engineer jobs at Google, Meta, or Amazon");
                        },
                      },
                    ].map((chip) => {
                      const IconComp = chip.icon;
                      return (
                        <button
                          key={chip.query}
                          onClick={chip.onSelect}
                          className="p-3 rounded-xl border border-slate-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/40 text-xs sm:text-sm font-medium text-slate-700 text-left transition-all flex items-center justify-between group shadow-xs hover:shadow-sm"
                        >
                          <div className="flex items-center gap-2.5">
                            <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${chip.iconColor}`}>
                              <IconComp className="w-3.5 h-3.5" />
                            </div>
                            <span className="font-medium text-slate-800">{chip.label}</span>
                          </div>
                          <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition-all shrink-0 ml-2" />
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <div
                key={msg.id}
                id={`msg-${msg.id}`}
                className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && (
                  <div className="w-7 h-7 rounded-xl bg-white text-indigo-600 border border-indigo-100 flex items-center justify-center shrink-0 shadow-xs">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div className={`${msg.jobResults && msg.jobResults.length > 0 ? "w-full" : "max-w-[85%]"} space-y-3`}>
                  {msg.content && (
                    <div
                      className={`p-4 rounded-2xl text-sm leading-relaxed ${
                        msg.role === "user"
                          ? "bg-indigo-600 text-white rounded-tr-sm"
                          : "bg-white border border-slate-200 text-slate-800 rounded-tl-sm shadow-xs"
                      }`}
                    >
                      {msg.role === "user" ? msg.content : <MarkdownRenderer content={msg.content} />}
                    </div>
                  )}

                  {msg.jobResults && msg.jobResults.length > 0 && (
                    <div className="space-y-3 pt-1">
                      <div className="flex items-center justify-between text-xs px-1 text-slate-500">
                        <span className="font-semibold text-slate-700">
                          {msg.jobResults.length} Roles Recommended
                        </span>
                        <span className="text-[11px] text-indigo-600 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-100 font-medium">
                          Scroll down to view all {msg.jobResults.length} jobs ↓
                        </span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {msg.jobResults.map((match) => (
                          <JobCard
                            key={match.job.id}
                            match={match}
                            onApply={handleApplyToJob}
                            isApplied={appliedJobIds.has(match.job.id)}
                          />
                        ))}
                      </div>
                      <div className="flex items-center justify-between text-xs pt-1">
                        <span className="text-slate-500 font-medium">
                          Showing {msg.jobResults.length} positions
                        </span>
                        <button
                          type="button"
                          onClick={() => handleSendMessage("next")}
                          disabled={isStreaming}
                          className="px-3 py-1.5 rounded-xl bg-white hover:bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-semibold transition-all shadow-xs"
                        >
                          Load Next 10 Jobs
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {msg.role === "user" && (
                  <div className="w-7 h-7 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))}

            {isStreaming && (
              <div className="flex items-center gap-2 text-slate-500 text-sm pl-10 py-1">
                <span className="w-2 h-2 rounded-full bg-indigo-600 animate-pulse" />
                <span>Finding matching jobs...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Bar */}
        <div className="border-t border-slate-200 bg-white p-3 sm:p-4 shadow-xs">
          <form
            onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }}
            className="flex items-center gap-2 max-w-4xl mx-auto"
          >
            <input
              ref={chatFileInputRef}
              type="file"
              accept=".pdf,.docx,.doc"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.[0]) handleFileUploadInChat(e.target.files[0]);
              }}
            />
            <button
              type="button"
              onClick={() => chatFileInputRef.current?.click()}
              disabled={isStreaming || uploading}
              className="p-2.5 rounded-xl border border-slate-200 text-slate-500 hover:text-indigo-600 hover:border-indigo-300 hover:bg-indigo-50/50 transition-colors shrink-0"
              title="Upload resume (PDF or DOCX) in chat"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Ask anything, e.g. 'show remote roles' or 'apply to job 2'..."
              disabled={isStreaming}
              className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all"
            />
            <button
              type="submit"
              disabled={isStreaming || !inputMessage.trim()}
              className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-semibold flex items-center gap-1.5 transition-all shadow-sm shrink-0"
            >
              <Send className="w-4 h-4" />
              <span className="hidden sm:inline">Send</span>
            </button>
          </form>
        </div>
      </main>

      <AppliedJobsDrawer isOpen={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} sessionId={sessionId} />
    </div>
  );
}

// ─── Shared Header ────────────────────────────────────────
function Header({
  onOpenDrawer,
  appliedCount,
  onGoBack,
  profileName,
  onUploadClick,
}: {
  onOpenDrawer: () => void;
  appliedCount: number;
  onGoBack?: () => void;
  profileName?: string;
  onUploadClick?: () => void;
}) {
  return (
    <header className="px-4 sm:px-6 py-3 border-b border-slate-200 bg-white flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        {onGoBack && (
          <button
            onClick={onGoBack}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
            title="Back to filters"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
        )}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center shadow-sm">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-900">
              Hidani Tech
              <span className="ml-2 text-xs font-normal text-slate-400 hidden sm:inline">
                AI Job Assistant
              </span>
            </h1>
            {profileName ? (
              <p className="text-[11px] font-medium text-emerald-600 flex items-center gap-1">
                <CheckCircle className="w-3 h-3 inline" /> {profileName}
              </p>
            ) : (
              <p className="text-[11px] text-slate-400">2,800+ Verified Roles</p>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {onUploadClick && (
          <button
            onClick={onUploadClick}
            className="px-3 py-1.5 rounded-xl border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/50 text-slate-700 hover:text-indigo-600 text-xs font-semibold flex items-center gap-1.5 transition-all"
            title="Attach Resume (PDF/DOCX)"
          >
            <Paperclip className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Upload Resume</span>
          </button>
        )}
        <button
          onClick={onOpenDrawer}
          className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-xs"
        >
          <Briefcase className="w-3.5 h-3.5" />
          <span>Applied Jobs</span>
          {appliedCount > 0 && (
            <span className="w-4 h-4 rounded-full bg-white text-indigo-700 text-[10px] font-bold flex items-center justify-center">
              {appliedCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
