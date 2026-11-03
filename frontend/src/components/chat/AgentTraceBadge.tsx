"use client";

import React, { useState } from "react";
import { Bot, ChevronDown, ChevronUp, Cpu, Sparkles } from "lucide-react";

export interface AgentTraceEvent {
  type: "start" | "handoff" | "thought";
  agent: string;
  to_agent?: string;
  thought?: string;
  timestamp: string;
}

interface AgentTraceBadgeProps {
  events: AgentTraceEvent[];
  isStreaming: boolean;
}

export const AgentTraceBadge: React.FC<AgentTraceBadgeProps> = ({ events, isStreaming }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (events.length === 0 && !isStreaming) return null;

  const latestEvent = events[events.length - 1];

  return (
    <div className="my-2 border border-indigo-500/30 bg-indigo-950/40 rounded-xl overflow-hidden backdrop-blur-sm transition-all text-xs">
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-indigo-900/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className="relative">
            <Cpu className="w-3.5 h-3.5 text-indigo-400" />
            {isStreaming && (
              <span className="absolute -top-1 -right-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
              </span>
            )}
          </div>

          <span className="font-medium text-indigo-300">
            {latestEvent?.type === "handoff"
              ? `Handoff: ${latestEvent.agent} ➔ ${latestEvent.to_agent}`
              : isStreaming
              ? "Multi-Agent Orchestrator Active"
              : "Agent Trace Completed"}
          </span>

          {latestEvent?.thought && (
            <span className="text-slate-400 truncate max-w-[280px] hidden sm:inline">
              — {latestEvent.thought}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 text-indigo-400">
          <span className="text-[10px] bg-indigo-500/20 px-1.5 py-0.5 rounded font-mono">
            {events.length} step{events.length === 1 ? "" : "s"}
          </span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </div>
      </div>

      {isOpen && (
        <div className="px-3 py-2.5 border-t border-indigo-500/20 bg-slate-950/70 space-y-2">
          {events.map((ev, i) => (
            <div key={i} className="flex items-start gap-2 text-slate-300">
              <span className="text-[10px] text-slate-500 font-mono mt-0.5">{ev.timestamp}</span>
              <div>
                {ev.type === "handoff" ? (
                  <p className="font-semibold text-indigo-300">
                    🔄 Handoff: <span className="text-white">{ev.agent}</span> ➔{" "}
                    <span className="text-indigo-200">{ev.to_agent}</span>
                  </p>
                ) : (
                  <p className="font-semibold text-slate-200">
                    ⚡ {ev.agent}:
                  </p>
                )}
                {ev.thought && <p className="text-slate-400 text-[11px] mt-0.5">{ev.thought}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

