import React, { useState } from 'react';
import { 
  Bug, 
  ShieldAlert, 
  Zap, 
  Paintbrush, 
  ChevronDown, 
  ChevronUp, 
  Sparkles,
  Copy,
  Check
} from 'lucide-react';
import DiffViewer from './DiffViewer';

const CATEGORY_CONFIG = {
  bug: {
    label: 'Bug / Flaw',
    icon: Bug,
    bg: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    badgeBg: 'bg-rose-500/20 text-rose-300'
  },
  security: {
    label: 'Security',
    icon: ShieldAlert,
    bg: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    badgeBg: 'bg-amber-500/20 text-amber-300'
  },
  performance: {
    label: 'Performance',
    icon: Zap,
    bg: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
    badgeBg: 'bg-sky-500/20 text-sky-300'
  },
  style: {
    label: 'Style / Best Practice',
    icon: Paintbrush,
    bg: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    badgeBg: 'bg-purple-500/20 text-purple-300'
  }
};

const SEVERITY_CONFIG = {
  critical: 'bg-red-500/20 text-red-300 border-red-500/40',
  high: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
  medium: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  low: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  info: 'bg-slate-500/20 text-slate-300 border-slate-500/40'
};

export default function FindingCard({ finding, onApplyFix }) {
  const [expanded, setExpanded] = useState(true);
  const [showDiff, setShowDiff] = useState(true);
  const [copied, setCopied] = useState(false);

  const catMeta = CATEGORY_CONFIG[finding.category] || CATEGORY_CONFIG.bug;
  const Icon = catMeta.icon;
  const sevStyle = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.medium;

  const handleCopyFix = () => {
    if (finding.fixed_code_snippet || finding.suggested_fix) {
      navigator.clipboard.writeText(finding.fixed_code_snippet || finding.suggested_fix);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-md transition-all hover:border-slate-700">
      {/* Header Bar */}
      <div 
        onClick={() => setExpanded(!expanded)}
        className="p-4 cursor-pointer flex items-center justify-between gap-3 bg-slate-900/90 border-b border-slate-800/80 hover:bg-slate-850"
      >
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className={`p-2 rounded-lg border ${catMeta.bg}`}>
            <Icon className="w-4 h-4" />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-[11px] font-semibold uppercase px-2 py-0.5 rounded border ${sevStyle}`}>
                {finding.severity}
              </span>
              <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${catMeta.badgeBg}`}>
                {catMeta.label}
              </span>
              <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                Line {finding.line}
              </span>
            </div>
            <h4 className="text-sm font-semibold text-white mt-1 truncate">
              {finding.title}
            </h4>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {finding.suggested_fix && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/20 font-medium">
              <Sparkles className="w-3 h-3" />
              Fix Available
            </span>
          )}
          <button className="text-slate-400 hover:text-white p-1">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Details Body */}
      {expanded && (
        <div className="p-4 space-y-4 text-sm text-slate-300">
          {/* Explanation */}
          <div>
            <h5 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Explanation & Rationale
            </h5>
            <p className="text-xs leading-relaxed text-slate-300 bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
              {finding.explanation}
            </p>
          </div>

          {/* Suggested Fix / Diff View */}
          {(finding.diff || finding.suggested_fix || finding.original_code_snippet) && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h5 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Proposed Solution
                </h5>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCopyFix}
                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 transition"
                  >
                    {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{copied ? 'Copied' : 'Copy Snippet'}</span>
                  </button>
                </div>
              </div>

              {finding.diff ? (
                <DiffViewer diffText={finding.diff} />
              ) : finding.original_code_snippet && finding.fixed_code_snippet ? (
                <DiffViewer 
                  original={finding.original_code_snippet} 
                  modified={finding.fixed_code_snippet} 
                />
              ) : (
                <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-900/30 text-xs font-mono text-emerald-300">
                  {finding.suggested_fix}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
