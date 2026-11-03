"use client";

import React, { useState, useRef } from "react";
import { UploadCloud, FileText, CheckCircle, AlertCircle, Loader2, Sparkles, User } from "lucide-react";
import { uploadResume, ResumeProfile } from "@/lib/api";

interface ResumeUploaderProps {
  sessionId: string;
  onProfileLoaded: (profile: ResumeProfile) => void;
  currentProfile: ResumeProfile | null;
}

export const ResumeUploader: React.FC<ResumeUploaderProps> = ({
  sessionId,
  onProfileLoaded,
  currentProfile,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileProcess = async (file: File) => {
    setError(null);
    setLoading(true);

    try {
      const data = await uploadResume(file, sessionId);
      if (data?.profile) {
        onProfileLoaded(data.profile);
      }
    } catch (err: any) {
      setError(err.message || "Failed to parse resume.");
    } finally {
      setLoading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileProcess(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl text-slate-100">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold flex items-center gap-2 text-white">
          <FileText className="w-4 h-4 text-indigo-400" /> Candidate Resume
        </h2>
        {currentProfile && (
          <span className="text-[11px] font-medium text-emerald-400 flex items-center gap-1 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
            <CheckCircle className="w-3 h-3" /> Auto-Parsed
          </span>
        )}
      </div>

      {/* Upload Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-all ${
          isDragging
            ? "border-indigo-400 bg-indigo-950/40"
            : "border-slate-700 hover:border-slate-600 bg-slate-950/50 hover:bg-slate-950/80"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc"
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleFileProcess(e.target.files[0]);
            }
          }}
        />

        {loading ? (
          <div className="py-3 flex flex-col items-center gap-2">
            <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
            <p className="text-xs text-indigo-300 font-medium">Extracting skills & experience...</p>
          </div>
        ) : (
          <div className="py-2 flex flex-col items-center gap-1.5">
            <UploadCloud className="w-6 h-6 text-indigo-400" />
            <p className="text-xs font-semibold text-slate-200">
              {currentProfile ? "Upload updated resume" : "Drop your resume here (PDF / DOCX)"}
            </p>
            <p className="text-[10px] text-slate-500">Supports text PDFs and Word documents</p>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="mt-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Parsed Profile Summary Card */}
      {currentProfile && (
        <div className="mt-4 pt-3 border-t border-slate-800 space-y-2.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-bold text-white text-sm flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-indigo-400" /> {currentProfile.name}
            </span>
            <span className="text-[11px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 border border-slate-700">
              {currentProfile.years_of_experience === 0
                ? "Fresher"
                : `${currentProfile.years_of_experience} yrs exp`}
            </span>
          </div>

          <p className="text-indigo-300 font-medium">{currentProfile.designation}</p>

          {currentProfile.contact?.email && (
            <p className="text-slate-400 text-[11px] truncate">✉️ {currentProfile.contact.email}</p>
          )}

          {/* Extracted Skills Badges */}
          {currentProfile.skills && currentProfile.skills.length > 0 && (
            <div>
              <p className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-1.5">
                Extracted Skills ({currentProfile.skills.length})
              </p>
              <div className="flex flex-wrap gap-1">
                {currentProfile.skills.map((skill, i) => (
                  <span
                    key={i}
                    className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

