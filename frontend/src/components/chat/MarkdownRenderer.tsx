"use client";

import React from "react";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = "" }) => {
  if (!content) return null;

  // Split by double newlines into blocks (paragraphs, lists, blockquotes, etc.)
  const blocks = content.split(/\n\s*\n/);

  return (
    <div className={`space-y-2.5 leading-relaxed text-slate-800 ${className}`}>
      {blocks.map((block, bIdx) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        // Check if block is a callout / suggestions block (e.g. starting with 💡, ⚠️, or >)
        if (trimmed.startsWith("💡") || trimmed.startsWith("⚠️") || trimmed.startsWith(">")) {
          const isWarning = trimmed.startsWith("⚠️");
          const cleanedText = trimmed.replace(/^[💡⚠️>]\s*/, "");
          return (
            <div
              key={bIdx}
              className={`p-3 rounded-xl border text-xs sm:text-[13px] my-2 flex gap-2.5 items-start ${
                isWarning
                  ? "bg-amber-50/70 border-amber-200/80 text-amber-900"
                  : "bg-indigo-50/60 border-indigo-100 text-indigo-950"
              }`}
            >
              <span className="text-base leading-none select-none shrink-0">
                {isWarning ? "⚠️" : "💡"}
              </span>
              <div className="space-y-1 flex-1">
                {cleanedText.split("\n").map((line, lIdx) => (
                  <p key={lIdx} className="leading-snug">
                    {renderInline(line)}
                  </p>
                ))}
              </div>
            </div>
          );
        }

        // Check if block is a numbered list
        if (/^\d+\.\s+/.test(trimmed)) {
          const lines = trimmed.split("\n");
          return (
            <ol key={bIdx} className="space-y-1.5 my-1.5 pl-1">
              {lines.map((line, lIdx) => {
                const numMatch = line.match(/^(\d+)\.\s+(.*)$/);
                if (numMatch) {
                  return (
                    <li key={lIdx} className="flex items-start gap-2 text-xs sm:text-sm">
                      <span className="w-5 h-5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 text-[11px] font-semibold flex items-center justify-center shrink-0 mt-0.5">
                        {numMatch[1]}
                      </span>
                      <span className="flex-1 pt-0.5">{renderInline(numMatch[2])}</span>
                    </li>
                  );
                }
                return (
                  <p key={lIdx} className="pl-7 text-xs sm:text-sm text-slate-600">
                    {renderInline(line)}
                  </p>
                );
              })}
            </ol>
          );
        }

        // Check if block is a bulleted list
        if (/^[-*•]\s+/.test(trimmed)) {
          const lines = trimmed.split("\n");
          return (
            <ul key={bIdx} className="space-y-1.5 my-1.5 pl-1">
              {lines.map((line, lIdx) => {
                const bulletMatch = line.match(/^[-*•]\s+(.*)$/);
                if (bulletMatch) {
                  return (
                    <li key={lIdx} className="flex items-start gap-2 text-xs sm:text-sm">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-600 shrink-0 mt-2" />
                      <span className="flex-1">{renderInline(bulletMatch[1])}</span>
                    </li>
                  );
                }
                return (
                  <p key={lIdx} className="pl-4 text-xs sm:text-sm text-slate-600">
                    {renderInline(line)}
                  </p>
                );
              })}
            </ul>
          );
        }

        // Standard paragraph
        return (
          <p key={bIdx} className="text-xs sm:text-sm">
            {trimmed.split("\n").map((line, lIdx, arr) => (
              <React.Fragment key={lIdx}>
                {renderInline(line)}
                {lIdx < arr.length - 1 && <br />}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
};

// Helper function to render bold, italic, inline code, and links
function renderInline(text: string): React.ReactNode {
  // Pattern matching:
  // 1. **bold**
  // 2. *italic*
  // 3. `code`
  // 4. [text](url)
  const regex = /(\*\*.*?\*\*|\*.*?\*|`.*?`|\[.*?\]\(.*?\))/g;
  const parts = text.split(regex);

  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
      return (
        <strong key={i} className="font-semibold text-slate-900">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
      return (
        <em key={i} className="italic text-slate-700">
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
      return (
        <code
          key={i}
          className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-indigo-700 text-[11px] font-mono mx-0.5"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    const linkMatch = part.match(/^\[(.*?)\]\((.*?)\)$/);
    if (linkMatch) {
      return (
        <a
          key={i}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-indigo-600 hover:text-indigo-700 underline font-medium"
        >
          {linkMatch[1]}
        </a>
      );
    }
    return part;
  });
}

