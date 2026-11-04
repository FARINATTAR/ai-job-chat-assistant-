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
    <div className="bg-white border border-slate-200/90 rounded-2xl p-4 sm:p-5 shadow-sm text-slate-800">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold flex items-center gap-2 text-slate-900">
          <FileText className="w-4 h-4 text-indigo-600" /> Candidate Resume
        </h2>
        {currentProfile && (
          <span className="text-[11px] font-semibold text-emerald-700 flex items-center gap-1 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
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
            ? "border-indigo-500 bg-indigo-50/60"
            : "border-slate-300 hover:border-indigo-400 bg-slate-50/70 hover:bg-indigo-50/20"
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
            <Loader2 className="w-6 h-6 text-indigo-600 animate-spin" />
            <p className="text-xs text-indigo-600 font-semibold">Extracting skills & experience...</p>
          </div>
        ) : (
          <div className="py-2 flex flex-col items-center gap-1.5">
            <UploadCloud className="w-6 h-6 text-indigo-600" />
            <p className="text-xs font-semibold text-slate-800">
              {currentProfile ? "Upload updated resume" : "Drop your resume here (PDF / DOCX)"}
            </p>
            <p className="text-[10px] text-slate-500">Supports text PDFs and Word documents</p>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="mt-3 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Parsed Profile Summary Card */}
      {currentProfile && (
        <div className="mt-4 pt-3.5 border-t border-slate-100 space-y-2.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-indigo-600" /> {currentProfile.name}
            </span>
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200/80">
              {currentProfile.years_of_experience === 0
                ? "Fresher"
                : `${currentProfile.years_of_experience} yrs exp`}
            </span>
          </div>

          <p className="text-indigo-600 font-semibold">{currentProfile.designation}</p>

          {currentProfile.contact?.email && (
            <p className="text-slate-500 text-[11px] truncate">{currentProfile.contact.email}</p>
          )}

          {/* Extracted Skills Badges */}
          {currentProfile.skills && currentProfile.skills.length > 0 && (
            <div>
              <p className="text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-1.5">
                Extracted Skills ({currentProfile.skills.length})
              </p>
              <div className="flex flex-wrap gap-1">
                {currentProfile.skills.map((skill, i) => (
                  <span
                    key={i}
                    className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200/80"
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

