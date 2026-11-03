"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Send,
  Briefcase,
  Sparkles,
  RefreshCw,
  Cpu,
  Bot,
  User,
  CheckCircle2,
  Filter,
} from "lucide-react";
import { getSessionId, checkBackendHealth, API_BASE_URL, JobMatch, ResumeProfile, applyToJobDirect } from "@/lib/api";
import { ResumeUploader } from "@/components/resume/ResumeUploader";
import { JobCard } from "@/components/jobs/JobCard";
import { AgentTraceBadge, AgentTraceEvent } from "@/components/chat/AgentTraceBadge";
import { AppliedJobsDrawer } from "@/components/applications/AppliedJobsDrawer";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  jobResults?: JobMatch[];
  traceEvents?: AgentTraceEvent[];
}

export default function Home() {
  const [sessionId, setSessionId] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return getSessionId();
    }
    return "session_init";
  });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentProfile, setCurrentProfile] = useState<ResumeProfile | null>(null);
  const [backendStatus, setBackendStatus] = useState<{ status: string; jobs_loaded: number }>({
    status: "checking",
    jobs_loaded: 0,
  });
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [appliedJobIds, setAppliedJobIds] = useState<Set<string>>(new Set());
  const [currentTrace, setCurrentTrace] = useState<AgentTraceEvent[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sid = getSessionId();
    setSessionId(sid);

    // Initial greeting
    setMessages([
      {
        id: "init",
        role: "assistant",
        content:
          "👋 Welcome! I am your **AI Job Chat Assistant**.\n\n" +
          "1. **Upload your resume** (PDF or DOCX) on the left to get started.\n" +
          "2. I'll auto-extract your skills and designation to recommend the best matching jobs from our 1,600+ verified software engineering dataset.\n" +
          "3. You can naturally refine searches (*'show remote roles'*, *'jobs needing Python'*) and apply (*'apply to job 1'* or click Quick Apply).",
      },
    ]);

    // Check backend health
    checkBackendHealth().then((res) => setBackendStatus(res));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming, currentTrace]);

  const handleSendMessage = async (customMessage?: string) => {
    const textToSend = (customMessage || inputMessage).trim();
    if (!textToSend || isStreaming) return;

    setInputMessage("");

    // Add user message to chat
    const userMsgId = "user_" + Date.now();
    const assistantMsgId = "asst_" + Date.now();

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: textToSend },
      { id: assistantMsgId, role: "assistant", content: "" },
    ]);

    setIsStreaming(true);
    setCurrentTrace([]);

    const traceAcc: AgentTraceEvent[] = [];
    let assistantText = "";
    let receivedJobs: JobMatch[] | undefined = undefined;

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: textToSend,
        }),
      });

      if (!response.body) {
        throw new Error("No response stream available.");
      }

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
          try {
            parsedData = JSON.parse(rawData);
          } catch {}

          const nowTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

          if (eventType === "agent_start") {
            traceAcc.push({
              type: "start",
              agent: parsedData.agent || "Orchestrator",
              thought: parsedData.thought,
              timestamp: nowTime,
            });
            setCurrentTrace([...traceAcc]);
          } else if (eventType === "agent_handoff") {
            traceAcc.push({
              type: "handoff",
              agent: parsedData.from_agent || "Orchestrator",
              to_agent: parsedData.to_agent || "SubAgent",
              thought: parsedData.reason,
              timestamp: nowTime,
            });
            setCurrentTrace([...traceAcc]);
          } else if (eventType === "agent_thought") {
            traceAcc.push({
              type: "thought",
              agent: parsedData.agent || "Orchestrator",
              thought: parsedData.thought,
              timestamp: nowTime,
            });
            setCurrentTrace([...traceAcc]);
          } else if (eventType === "job_results") {
            receivedJobs = parsedData.jobs;
          } else if (eventType === "token") {
            assistantText += parsedData.content || "";
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      content: assistantText,
                      jobResults: receivedJobs,
                      traceEvents: [...traceAcc],
                    }
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
            ? {
                ...m,
                content: `⚠️ Error: ${err.message || "Could not reach assistant backend."}`,
              }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
      setCurrentTrace([]);
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

      const confirmMsg: ChatMessage = {
        id: "apply_conf_" + Date.now(),
        role: "assistant",
        content: data.message || `✅ Successfully submitted application for Job #${reference}!`,
      };
      setMessages((prev) => [...prev, confirmMsg]);
    } catch (e: any) {
      await handleSendMessage(`apply to job ${reference}`);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100">
      {/* Top Navigation */}
      <header className="px-4 sm:px-6 py-3 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
              Hidani Tech <span className="text-slate-400 font-normal hidden sm:inline">| AI Job Chat Assistant</span>
            </h1>
            <p className="text-[10px] text-slate-400">Multi-Agent SDE Intern Assessment</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Backend Status indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700/60 text-[11px] text-slate-300">
            <span
              className={`w-2 h-2 rounded-full ${
                backendStatus.status === "healthy" ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
              }`}
            />
            <span className="hidden sm:inline">
              {backendStatus.jobs_loaded > 0
                ? `${backendStatus.jobs_loaded.toLocaleString()} Real Jobs`
                : "Connecting..."}
            </span>
          </div>

          {/* Applied Jobs Button */}
          <button
            onClick={() => setIsDrawerOpen(true)}
            className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md shadow-indigo-600/20"
          >
            <Briefcase className="w-3.5 h-3.5" />
            <span>Applied Jobs</span>
          </button>
        </div>
      </header>

      {/* Main Grid: Left Sidebar + Right Chat */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        {/* Left Column: Resume Profile & Quick Filters */}
        <aside className="lg:col-span-4 border-r border-slate-800 bg-slate-900/50 p-4 overflow-y-auto space-y-4 hidden lg:block">
          <ResumeUploader
            sessionId={sessionId}
            onProfileLoaded={(profile) => {
              setCurrentProfile(profile);
              handleSendMessage("I have uploaded my resume. Please recommend matching jobs for me!");
            }}
            currentProfile={currentProfile}
          />

          {/* Quick Search Chips */}
          <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2 text-xs">
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-indigo-400" /> Conversational Refinements
            </p>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {[
                "Recommend matching jobs",
                "Show only remote roles",
                "Jobs needing Python",
                "Jobs needing React",
                "Show my applied jobs",
                "Reset all filters",
              ].map((chip, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(chip)}
                  disabled={isStreaming}
                  className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-indigo-950/80 hover:text-indigo-300 hover:border-indigo-500/40 border border-slate-700/80 text-slate-300 transition-all text-[11px]"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* Right Column: Chat Window */}
        <main className="lg:col-span-8 flex flex-col h-full bg-slate-950 overflow-hidden">
          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-3xl ${msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"}`}
              >
                {/* Avatar */}
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold ${
                    msg.role === "user"
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-800 text-indigo-400 border border-slate-700"
                  }`}
                >
                  {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                {/* Message Body */}
                <div className="space-y-3 max-w-[85%] sm:max-w-[90%]">
                  {/* Trace badge on assistant messages */}
                  {msg.traceEvents && msg.traceEvents.length > 0 && (
                    <AgentTraceBadge events={msg.traceEvents} isStreaming={false} />
                  )}

                  {msg.content && (
                    <div
                      className={`p-3.5 sm:p-4 rounded-2xl text-xs sm:text-sm whitespace-pre-wrap leading-relaxed shadow-sm ${
                        msg.role === "user"
                          ? "bg-indigo-600 text-white rounded-tr-none font-medium"
                          : "bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none"
                      }`}
                    >
                      {msg.content}
                    </div>
                  )}

                  {/* Render Job Cards if available */}
                  {msg.jobResults && msg.jobResults.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                      {msg.jobResults.map((match) => (
                        <JobCard
                          key={match.job.id}
                          match={match}
                          onApply={handleApplyToJob}
                          isApplied={appliedJobIds.has(match.job.id)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Live Streaming Trace Badge */}
            {isStreaming && currentTrace.length > 0 && (
              <div className="max-w-xl mr-auto pl-10">
                <AgentTraceBadge events={currentTrace} isStreaming={true} />
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Chat Input Bar */}
          <div className="p-3 sm:p-4 border-t border-slate-800 bg-slate-900/70 backdrop-blur-md">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center gap-2 max-w-4xl mx-auto"
            >
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder={
                  currentProfile
                    ? "Ask naturally, e.g. 'show only remote roles' or 'apply to job 2'..."
                    : "Upload resume on the left or type your query here..."
                }
                disabled={isStreaming}
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
              />
              <button
                type="submit"
                disabled={isStreaming || !inputMessage.trim()}
                className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-all shadow-md shadow-indigo-600/20 shrink-0"
              >
                <Send className="w-4 h-4" />
                <span className="hidden sm:inline">Send</span>
              </button>
            </form>
          </div>
        </main>
      </div>

      {/* Applied Jobs Slide-Out Drawer */}
      <AppliedJobsDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        sessionId={sessionId}
      />
    </div>
  );
}

