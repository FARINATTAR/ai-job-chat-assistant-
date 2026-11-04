"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Send,
  Briefcase,
  Sparkles,
  RotateCcw,
  Bot,
  User,
  Filter,
} from "lucide-react";
import { getSessionId, checkBackendHealth, API_BASE_URL, JobMatch, ResumeProfile, applyToJobDirect } from "@/lib/api";
import { ResumeUploader } from "@/components/resume/ResumeUploader";
import { JobCard } from "@/components/jobs/JobCard";
import { AppliedJobsDrawer } from "@/components/applications/AppliedJobsDrawer";
import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";
import { WelcomeHero } from "@/components/chat/WelcomeHero";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  jobResults?: JobMatch[];
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
    jobs_loaded: 2075,
  });
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [appliedJobIds, setAppliedJobIds] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sid = getSessionId();
    setSessionId(sid);

    // Initial greeting
    setMessages([
      {
        id: "init",
        role: "assistant",
        content: "Welcome! Upload your resume or explore verified jobs below.",
      },
    ]);

    // Check backend health
    checkBackendHealth().then((res) => setBackendStatus(res));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

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

          if (eventType === "job_results") {
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

  const handleResetChat = () => {
    setMessages([
      {
        id: "init",
        role: "assistant",
        content: "Welcome! Upload your resume or explore verified jobs below.",
      },
    ]);
  };

  return (
    <div className="flex flex-col h-screen bg-slate-50 text-slate-800 antialiased">
      {/* Top Navigation */}
      <header className="px-4 sm:px-6 py-3 border-b border-slate-200/90 bg-white/95 backdrop-blur-md flex items-center justify-between shrink-0 shadow-xs">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center shadow-md shadow-indigo-500/20">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-slate-900 flex items-center gap-2">
              Hidani Tech
              <span className="px-2 py-0.5 rounded-full bg-indigo-50 border border-indigo-200/80 text-indigo-700 text-[10px] font-semibold">
                AI Job Assistant
              </span>
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Reset Chat Button */}
          <button
            onClick={handleResetChat}
            title="Reset conversation"
            className="p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Applied Jobs Button */}
          <button
            onClick={() => setIsDrawerOpen(true)}
            className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-xs"
          >
            <Briefcase className="w-3.5 h-3.5" />
            <span>Applied Jobs</span>
            {appliedJobIds.size > 0 && (
              <span className="w-4 h-4 rounded-full bg-white text-indigo-700 text-[10px] font-bold flex items-center justify-center">
                {appliedJobIds.size}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* Main Layout: Left Sidebar + Right Chat */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        {/* Left Column: Profile & Quick Controls */}
        <aside className="lg:col-span-4 border-r border-slate-200 bg-white p-4 overflow-y-auto space-y-4 hidden lg:block">
          <ResumeUploader
            sessionId={sessionId}
            onProfileLoaded={(profile) => {
              setCurrentProfile(profile);
              handleSendMessage("I have uploaded my resume. Please recommend matching jobs for me!");
            }}
            currentProfile={currentProfile}
          />

          {/* Unified Clean Filter Card */}
          <div className="p-4 rounded-2xl bg-white border border-slate-200/90 shadow-xs space-y-3.5 text-xs">
            {/* Experience Level */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Experience Level
              </span>
              <div className="grid grid-cols-2 gap-1.5 pt-0.5">
                {[
                  { label: "All Experience", q: "Show jobs across all experience levels" },
                  { label: "🎓 Fresher (0-1 yr)", q: "Show jobs for freshers (0-1 yr)" },
                  { label: "💼 Mid (2-4 yrs)", q: "Show jobs for 2-4 years experience" },
                  { label: "🚀 Senior (5+ yrs)", q: "Show senior developer roles (5+ yrs)" },
                ].map((item, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(item.q)}
                    disabled={isStreaming}
                    className="px-2.5 py-1.5 rounded-xl bg-slate-50 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-300 border border-slate-200 text-slate-700 transition-all text-[11px] font-medium text-left shadow-xs"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Source */}
            <div className="space-y-1.5 pt-2 border-t border-slate-100">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Job Source
              </span>
              <div className="grid grid-cols-2 gap-1.5 pt-0.5">
                {[
                  { label: "🌐 All Sources", q: "Show jobs across all sources" },
                  { label: "💼 LinkedIn", q: "Show LinkedIn jobs" },
                  { label: "🇩🇪 Arbeitnow", q: "Show Arbeitnow jobs" },
                  { label: "⚡ Remotive", q: "Show Remotive jobs" },
                ].map((item, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(item.q)}
                    disabled={isStreaming}
                    className="px-2.5 py-1.5 rounded-xl bg-slate-50 hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-300 border border-slate-200 text-slate-700 transition-all text-[11px] font-medium text-left shadow-xs"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* Right Column: Chat Window */}
        <main className="lg:col-span-8 flex flex-col h-full bg-slate-50/70 overflow-hidden">
          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
            {messages.map((msg) => {
              // Rich Hero Onboarding when conversation starts
              if (msg.id === "init") {
                return (
                  <WelcomeHero
                    key={msg.id}
                    onSelectPrompt={(prompt) => handleSendMessage(prompt)}
                    hasResume={!!currentProfile}
                    totalJobs={backendStatus.jobs_loaded}
                  />
                );
              }

              return (
                <div
                  key={msg.id}
                  className={`flex gap-3 max-w-3xl ${msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"}`}
                >
                  {/* Avatar */}
                  <div
                    className={`w-7 h-7 rounded-xl flex items-center justify-center shrink-0 text-xs font-bold shadow-xs ${
                      msg.role === "user"
                        ? "bg-indigo-600 text-white"
                        : "bg-white text-indigo-600 border border-indigo-100 shadow-xs"
                    }`}
                  >
                    {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                  </div>

                  {/* Message Body */}
                  <div className="space-y-3 max-w-[85%] sm:max-w-[90%]">
                    {msg.content && (
                      <div
                        className={`p-4 rounded-2xl text-xs sm:text-sm leading-relaxed shadow-xs ${
                          msg.role === "user"
                            ? "bg-indigo-600 text-white rounded-tr-none font-medium whitespace-pre-wrap"
                            : "bg-white border border-slate-200/90 text-slate-800 rounded-tl-none"
                        }`}
                      >
                        {msg.role === "user" ? (
                          msg.content
                        ) : (
                          <MarkdownRenderer content={msg.content} />
                        )}
                      </div>
                    )}

                    {/* Render Job Cards if available */}
                    {msg.jobResults && msg.jobResults.length > 0 && (
                      <div className="space-y-3 pt-2">
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

                        {/* Pagination: Load Next 10 Jobs */}
                        <div className="flex items-center justify-between pt-1 text-xs">
                          <span className="text-[11px] text-slate-500">
                            Showing {msg.jobResults.length} positions
                          </span>
                          <button
                            type="button"
                            onClick={() => handleSendMessage("next")}
                            disabled={isStreaming}
                            className="px-3.5 py-1.5 rounded-xl bg-white hover:bg-indigo-50 text-indigo-700 hover:text-indigo-800 border border-indigo-200/90 text-xs font-semibold flex items-center gap-1.5 transition-all shadow-xs"
                          >
                            <span>Load Next 10 Jobs ⏩</span>
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Clean Streaming Indicator */}
            {isStreaming && (
              <div className="flex items-center gap-2 text-slate-500 text-xs pl-10 py-1">
                <span className="w-2 h-2 rounded-full bg-indigo-600 animate-pulse" />
                <span className="font-medium">Finding best job matches...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Chat Input Bar */}
          <div className="p-3 sm:p-4 border-t border-slate-200/90 bg-white/95 backdrop-blur-md space-y-2.5 shadow-xs">
            {/* Clean Quick Ribbon */}
            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar max-w-4xl mx-auto pb-0.5 text-[11px]">
              <span className="text-slate-400 font-semibold text-[10px] uppercase shrink-0 flex items-center gap-1">
                <Filter className="w-3 h-3 text-indigo-600" /> Quick:
              </span>
              {[
                { label: "🎓 Freshers Only", q: "Show jobs for freshers (0-1 yr)" },
                { label: "🏠 Remote Only", q: "Show only remote roles" },
                { label: "🇩🇪 Arbeitnow", q: "Show Arbeitnow jobs" },
                { label: "💼 LinkedIn", q: "Show LinkedIn jobs" },
                { label: "⏩ Next 10 Jobs", q: "Show next 10 jobs" },
                { label: "🔄 Reset", q: "Reset all filters" },
              ].map((btn, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSendMessage(btn.q)}
                  disabled={isStreaming}
                  className="px-2.5 py-1 rounded-full bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-300 border border-slate-200 text-slate-700 transition-all shrink-0 font-medium shadow-xs"
                >
                  {btn.label}
                </button>
              ))}
            </div>

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
                className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all shadow-xs"
              />
              <button
                type="submit"
                disabled={isStreaming || !inputMessage.trim()}
                className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-all shadow-sm shrink-0"
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
