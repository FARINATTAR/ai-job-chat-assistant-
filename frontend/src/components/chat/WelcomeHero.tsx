"use client";

import React from "react";
import { Sparkles, FileText, Globe, Zap, ArrowRight, Compass } from "lucide-react";

interface WelcomeHeroProps {
  onSelectPrompt: (prompt: string) => void;
  hasResume: boolean;
  totalJobs: number;
}

export const WelcomeHero: React.FC<WelcomeHeroProps> = ({
  onSelectPrompt,
  hasResume,
  totalJobs,
}) => {
  const suggestions = [
    {
      title: hasResume ? "Recommend Top Matches" : "Find Fresher & Intern Roles",
      desc: hasResume ? "Score against your uploaded resume" : "Zero to 1 year experience roles",
      prompt: hasResume ? "recommend top matching jobs for my resume" : "show fresher and internship roles",
      icon: "🎯",
    },
    {
      title: "Remote Developer Roles",
      desc: "Work-from-anywhere software opportunities",
      prompt: "show remote software developer roles",
      icon: "🌐",
    },
    {
      title: "Arbeitnow European Openings",
      desc: "Verified European tech postings with visa info",
      prompt: "show Arbeitnow jobs",
      icon: "🇩🇪",
    },
    {
      title: "Python & AI Engineering",
      desc: "Machine Learning, Backend & AI roles",
      prompt: "find jobs needing Python and Machine Learning",
      icon: "⚡",
    },
  ];

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-7 shadow-xs space-y-6">
      {/* Top Banner */}
      <div className="space-y-2">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-50 border border-indigo-200/80 text-indigo-700 text-[11px] font-semibold tracking-wide uppercase">
          <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
          <span>AI Multi-Agent Job Assistant</span>
        </div>
        <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
          Find Your Next Engineering Opportunity
        </h2>
        <p className="text-xs sm:text-sm text-slate-600 max-w-2xl leading-relaxed">
          Upload your resume on the left sidebar to automatically extract your skills, or explore over{" "}
          <span className="font-semibold text-slate-900">
            {totalJobs > 0 ? totalJobs.toLocaleString() : "2,000+"} verified active jobs
          </span>{" "}
          from LinkedIn, Arbeitnow, and Remotive with transparent match reasoning.
        </p>
      </div>

      {/* 3 Step Walkthrough Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
        <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1.5 transition-all hover:border-indigo-200 hover:bg-indigo-50/20">
          <div className="w-8 h-8 rounded-lg bg-indigo-100/80 text-indigo-700 flex items-center justify-center font-bold text-xs">
            <FileText className="w-4 h-4" />
          </div>
          <h3 className="text-xs font-bold text-slate-900">1. Upload Resume</h3>
          <p className="text-[11px] text-slate-500 leading-normal">
            Drop your PDF or DOCX. Extract 25+ technical skills, years of experience, and role.
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1.5 transition-all hover:border-indigo-200 hover:bg-indigo-50/20">
          <div className="w-8 h-8 rounded-lg bg-emerald-100/80 text-emerald-700 flex items-center justify-center font-bold text-xs">
            <Globe className="w-4 h-4" />
          </div>
          <h3 className="text-xs font-bold text-slate-900">2. Real Dataset</h3>
          <p className="text-[11px] text-slate-500 leading-normal">
            Search live postings with experience filters (Fresher, Mid, Senior) & source pills.
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1.5 transition-all hover:border-indigo-200 hover:bg-indigo-50/20">
          <div className="w-8 h-8 rounded-lg bg-violet-100/80 text-violet-700 flex items-center justify-center font-bold text-xs">
            <Zap className="w-4 h-4" />
          </div>
          <h3 className="text-xs font-bold text-slate-900">3. Quick Apply</h3>
          <p className="text-[11px] text-slate-500 leading-normal">
            One-click apply or chat naturally to refine results and view agent reasoning traces.
          </p>
        </div>
      </div>

      {/* Suggested Prompts / Starters */}
      <div className="pt-2 border-t border-slate-100 space-y-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
          <Compass className="w-3.5 h-3.5 text-indigo-600" />
          <span>Try a quick search prompt:</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {suggestions.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectPrompt(item.prompt)}
              className="group text-left p-3 rounded-xl border border-slate-200/90 bg-white hover:border-indigo-300 hover:bg-indigo-50/30 hover:shadow-xs transition-all flex items-center justify-between"
            >
              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-900 group-hover:text-indigo-700 transition-colors">
                  <span>{item.icon}</span>
                  <span>{item.title}</span>
                </div>
                <p className="text-[11px] text-slate-500 group-hover:text-slate-600">
                  {item.desc}
                </p>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition-all shrink-0 ml-2" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

