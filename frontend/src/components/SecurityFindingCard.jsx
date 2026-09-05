import React, { useState } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  Zap,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Copy,
  Check,
  Bot,
  ArrowRight,
  Flame,
  KeyRound,
  Terminal,
  FileSearch,
  ExternalLink
} from 'lucide-react';
import DiffViewer from './DiffViewer';

const SEVERITY_CONFIG = {
  critical: {
    bg: 'bg-red-500/10 text-red-400 border-red-500/40',
    badge: 'bg-red-500/20 text-red-300 border-red-500/50',
    label: 'Critical Exploit',
    ring: 'ring-red-500/20',
  },
  high: {
    bg: 'bg-orange-500/10 text-orange-400 border-orange-500/40',
    badge: 'bg-orange-500/20 text-orange-300 border-orange-500/50',
    label: 'High Severity',
    ring: 'ring-orange-500/20',
  },
  medium: {
    bg: 'bg-amber-500/10 text-amber-400 border-amber-500/40',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/50',
    label: 'Medium Severity',
    ring: 'ring-amber-500/20',
  },
  low: {
    bg: 'bg-blue-500/10 text-blue-400 border-blue-500/40',
    badge: 'bg-blue-500/20 text-blue-300 border-blue-500/50',
    label: 'Low / Informational',
    ring: 'ring-blue-500/20',
  },
};

export default function SecurityFindingCard({ finding, onFixInSandbox }) {
  const [expanded, setExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const sevMeta = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.medium;
  const isDualVerified = finding.rules_confirmed || finding.confidence === 'high';

  const handleCopyFix = () => {
    const textToCopy = finding.fixed_code_snippet || finding.suggested_fix;
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className={`rounded-xl border border-slate-800 bg-slate-900/80 overflow-hidden shadow-lg transition hover:border-slate-700 ${isDualVerified ? 'ring-1 ring-amber-500/30' : ''}`}>
      {/* Header Bar */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="p-4 cursor-pointer flex items-center justify-between gap-3 bg-slate-900/90 border-b border-slate-800/80 hover:bg-slate-850"
      >
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className={`p-2.5 rounded-xl border ${sevMeta.bg}`}>
            <ShieldAlert className="w-5 h-5" />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              {/* Severity Badge */}
              <span className={`text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${sevMeta.badge}`}>
                {finding.severity}
              </span>

              {/* Vulnerability Type Badge */}
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                {finding.vulnerability_type || 'Vulnerability'}
              </span>

              {/* Dual-Verified Confidence Flag */}
              {isDualVerified ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                  <Zap className="w-3 h-3 text-emerald-400 fill-current" />
                  High Confidence (Dual Verified: Static + AI)
                </span>
              ) : (
                <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                  AI Inferred Finding
                </span>
              )}

              {/* Line indicator */}
              <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                Line {finding.line}
              </span>
            </div>

            <h4 className="text-sm font-semibold text-white mt-1.5 truncate">
              {finding.title}
            </h4>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {onFixInSandbox && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onFixInSandbox(finding);
              }}
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold shadow transition"
            >
              <Bot className="w-3.5 h-3.5" />
              <span>Fix in Sandbox</span>
            </button>
          )}

          <button className="text-slate-400 hover:text-white p-1">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Security Details Body */}
      {expanded && (
        <div className="p-4 space-y-4 text-xs text-slate-300">
          {/* Exploitability Analysis Section (Prominent) */}
          <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-500/30 space-y-1.5">
            <div className="flex items-center gap-2 text-amber-400 font-bold uppercase tracking-wider text-[11px]">
              <Flame className="w-4 h-4 text-amber-400" />
              <span>Real-World Exploitability &amp; Attack Vector</span>
            </div>
            <p className="text-xs leading-relaxed text-amber-200/90 pl-6">
              {finding.exploitability}
            </p>
          </div>

          {/* Explanation & Technical Description */}
          <div>
            <h5 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">
              Vulnerability Description
            </h5>
            <p className="text-xs leading-relaxed text-slate-200 bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
              {finding.explanation}
            </p>
          </div>

          {/* Proposed Secure Fix / Code Diff */}
          {(finding.diff || finding.suggested_fix || finding.original_code_snippet) && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h5 className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Secure Remediation</span>
                </h5>
                <button
                  onClick={handleCopyFix}
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-white px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 transition"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copied ? 'Copied' : 'Copy Fix Snippet'}</span>
                </button>
              </div>

              {finding.diff ? (
                <DiffViewer diffText={finding.diff} />
              ) : finding.original_code_snippet && finding.fixed_code_snippet ? (
                <DiffViewer
                  original={finding.original_code_snippet}
                  modified={finding.fixed_code_snippet}
                />
              ) : (
                <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-900/40 text-xs font-mono text-emerald-300 whitespace-pre-wrap">
                  {finding.suggested_fix}
                </div>
              )}
            </div>
          )}

          {/* Bottom Action Footer */}
          {onFixInSandbox && (
            <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
              <span className="text-[11px] text-slate-400">
                Send this vulnerability to the isolated Sandbox Fix Agent to synthesize tests and verify the fix.
              </span>
              <button
                onClick={() => onFixInSandbox(finding)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold shadow transition"
              >
                <Bot className="w-3.5 h-3.5" />
                <span>Launch in Sandbox Fix Agent</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
