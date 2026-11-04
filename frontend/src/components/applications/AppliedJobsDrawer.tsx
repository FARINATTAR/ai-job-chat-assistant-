"use client";

import React, { useEffect, useState } from "react";
import { X, Briefcase, Calendar, CheckCircle2, RefreshCw, ExternalLink } from "lucide-react";
import { ApplicationRecord, fetchApplications } from "@/lib/api";

interface AppliedJobsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
}

export const AppliedJobsDrawer: React.FC<AppliedJobsDrawerProps> = ({
  isOpen,
  onClose,
  sessionId,
}) => {
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await fetchApplications(sessionId);
      setApplications(data);
    } catch (e) {
      console.error("Error fetching applications:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen, sessionId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-sm transition-opacity">
      <div className="w-full max-w-md bg-white border-l border-slate-200 h-full flex flex-col shadow-2xl">
        {/* Drawer Header */}
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Applied Jobs ({applications.length})</h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={loadData}
              disabled={loading}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-3">
          {loading ? (
            <div className="py-12 text-center text-slate-400 text-xs">Loading applications...</div>
          ) : applications.length === 0 ? (
            <div className="py-12 text-center text-slate-400 text-xs">
              <p className="font-semibold text-slate-700 mb-1">No applications submitted yet.</p>
              <p className="text-slate-500">Ask the assistant to recommend roles or click 'Quick Apply' on any job card.</p>
            </div>
          ) : (
            applications.map((app) => (
              <div
                key={app.id}
                className="p-4 rounded-xl bg-slate-50 border border-slate-200 hover:border-indigo-300 transition-all text-xs"
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <h4 className="font-bold text-slate-900 text-sm">{app.job_title}</h4>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    {app.status}
                  </span>
                </div>
                <p className="text-slate-600 font-medium mb-2">{app.company}</p>

                <div className="flex items-center justify-between text-slate-400 text-[11px] pt-2 border-t border-slate-200/60">
                  <div className="flex items-center gap-1 text-slate-500">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>{app.applied_at ? app.applied_at.slice(0, 10) : "Today"}</span>
                  </div>
                  {app.source_url && (
                    <a
                      href={app.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1"
                    >
                      View Role <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

