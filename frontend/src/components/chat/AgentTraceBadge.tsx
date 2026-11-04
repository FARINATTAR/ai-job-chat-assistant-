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
    <div className="my-2 border border-indigo-200/90 bg-indigo-50/60 rounded-xl overflow-hidden backdrop-blur-sm transition-all text-xs shadow-sm">
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-indigo-100/60 transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className="relative">
            <Cpu className="w-3.5 h-3.5 text-indigo-600" />
            {isStreaming && (
              <span className="absolute -top-1 -right-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-600"></span>
              </span>
            )}
          </div>

          <span className="font-semibold text-indigo-900">
            {latestEvent?.type === "handoff"
              ? `Handoff: ${latestEvent.agent} ➔ ${latestEvent.to_agent}`
              : isStreaming
              ? "Multi-Agent Orchestrator Active"
              : "Agent Trace Completed"}
          </span>

          {latestEvent?.thought && (
            <span className="text-slate-500 truncate max-w-[280px] hidden sm:inline">
              — {latestEvent.thought}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 text-indigo-600">
          <span className="text-[10px] bg-white px-2 py-0.5 rounded border border-indigo-200 font-mono font-semibold">
            {events.length} step{events.length === 1 ? "" : "s"}
          </span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </div>
      </div>

      {isOpen && (
        <div className="px-3.5 py-3 border-t border-indigo-100 bg-white space-y-2">
          {events.map((ev, i) => (
            <div key={i} className="flex items-start gap-2 text-slate-700">
              <span className="text-[10px] text-slate-400 font-mono mt-0.5">{ev.timestamp}</span>
              <div>
                {ev.type === "handoff" ? (
                  <p className="font-semibold text-indigo-900">
                    🔄 Handoff: <span className="text-slate-900">{ev.agent}</span> ➔{" "}
                    <span className="text-indigo-600">{ev.to_agent}</span>
                  </p>
                ) : (
                  <p className="font-semibold text-slate-800">
                    ⚡ {ev.agent}:
                  </p>
                )}
                {ev.thought && <p className="text-slate-600 text-[11px] mt-0.5">{ev.thought}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

