"use client";

import React, { useState } from "react";
import { CheckCircle2, ExternalLink, MapPin, Briefcase, Sparkles, Send, Check } from "lucide-react";
import { JobMatch } from "@/lib/api";

interface JobCardProps {
  match: JobMatch;
  onApply: (reference: string) => Promise<void>;
  isApplied?: boolean;
}

export const JobCard: React.FC<JobCardProps> = ({ match, onApply, isApplied = false }) => {
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(isApplied);

  const { job, match_score, match_reasons, matched_skills, missing_skills, index } = match;

  const handleApply = async () => {
    if (applied || applying) return;
    setApplying(true);
    try {
      await onApply(String(index));
      setApplied(true);
    } finally {
      setApplying(false);
    }
  };

  // Color coding by score
  const scoreColor =
    match_score >= 80
      ? "text-emerald-400 border-emerald-500/40 bg-emerald-500/10"
      : match_score >= 60
      ? "text-indigo-400 border-indigo-500/40 bg-indigo-500/10"
      : "text-amber-400 border-amber-500/40 bg-amber-500/10";

  return (
    <div className="border border-slate-800 bg-slate-900/90 rounded-2xl p-4 sm:p-5 shadow-lg hover:border-slate-700 transition-all text-slate-100 flex flex-col justify-between group">
      <div>
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-2">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 border border-slate-700">
                Job #{index}
              </span>
              {job.remote && (
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  Remote
                </span>
              )}
            </div>
            <h3 className="text-base sm:text-lg font-bold text-white group-hover:text-indigo-400 transition-colors">
              {job.title}
            </h3>
            <p className="text-sm text-slate-400 font-medium">{job.company}</p>
          </div>

          {/* Match Score Badge */}
          <div className={`px-2.5 py-1 rounded-xl border flex flex-col items-center ${scoreColor}`}>
            <span className="text-base font-extrabold">{match_score}%</span>
            <span className="text-[9px] uppercase tracking-wider font-semibold opacity-80">Match</span>
          </div>
        </div>

        {/* Location & Experience details */}
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 my-3">
          <div className="flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5 text-slate-500" />
            <span>{job.location || "Global"}</span>
          </div>
          <div className="flex items-center gap-1">
            <Briefcase className="w-3.5 h-3.5 text-slate-500" />
            <span>
              {job.experience_required === 0
                ? "Fresher / Entry"
                : `${job.experience_required}+ yrs exp`}
            </span>
          </div>
        </div>

        {/* Grounded Match Reasons */}
        <div className="my-3 p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
          <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1.5 flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-amber-400" /> Why this matches:
          </p>
          <ul className="space-y-1">
            {match_reasons.map((reason, i) => (
              <li key={i} className="text-xs text-slate-300 flex items-start gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Matched Skills Tags */}
        {matched_skills && matched_skills.length > 0 && (
          <div className="mb-4">
            <div className="flex flex-wrap gap-1.5 mt-1">
              {matched_skills.slice(0, 5).map((skill, i) => (
                <span
                  key={i}
                  className="text-[11px] px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/20"
                >
                  ✓ {skill}
                </span>
              ))}
              {matched_skills.length > 5 && (
                <span className="text-[10px] text-slate-500 self-center">
                  +{matched_skills.length - 5} more
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="pt-3 border-t border-slate-800 flex items-center justify-between gap-2 mt-auto">
        {job.source_url ? (
          <a
            href={job.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors"
          >
            Original Job <ExternalLink className="w-3 h-3" />
          </a>
        ) : (
          <div />
        )}

        <button
          onClick={handleApply}
          disabled={applied || applying}
          className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md ${
            applied
              ? "bg-emerald-600 text-white cursor-default"
              : "bg-indigo-600 hover:bg-indigo-500 text-white hover:shadow-indigo-500/20"
          }`}
        >
          {applied ? (
            <>
              <Check className="w-3.5 h-3.5" /> Applied
            </>
          ) : applying ? (
            <>Submitting...</>
          ) : (
            <>
              <Send className="w-3.5 h-3.5" /> Quick Apply
            </>
          )}
        </button>
      </div>
    </div>
  );
};

