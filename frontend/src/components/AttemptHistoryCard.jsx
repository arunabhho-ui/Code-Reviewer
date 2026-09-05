import React, { useState } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  ChevronDown, 
  ChevronUp, 
  Timer, 
  Cpu, 
  Code2, 
  Sparkles 
} from 'lucide-react';
import DiffViewer from './DiffViewer';

export default function AttemptHistoryCard({ attemptData }) {
  const [expanded, setExpanded] = useState(true);
  const [showStdout, setShowStdout] = useState(false);

  const {
    attempt,
    explanation,
    diff,
    passed,
    exit_code,
    stdout,
    stderr,
    duration_ms,
    sandbox_mode,
  } = attemptData;

  const isSuccess = passed === true;

  return (
    <div className={`rounded-xl border overflow-hidden shadow-md transition ${
      isSuccess
        ? 'border-emerald-500/40 bg-slate-900/80 ring-1 ring-emerald-500/20'
        : 'border-slate-800 bg-slate-900/60'
    }`}>
      {/* Header */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="p-3.5 cursor-pointer flex items-center justify-between gap-3 bg-slate-900/90 border-b border-slate-800/80 hover:bg-slate-850"
      >
        <div className="flex items-center gap-3">
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold font-mono border ${
            isSuccess
              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
              : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
          }`}>
            Attempt {attempt}
          </span>

          <div className="flex items-center gap-2">
            {isSuccess ? (
              <span className="flex items-center gap-1 text-xs font-semibold text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                Tests Passed in Sandbox
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs font-semibold text-rose-400">
                <XCircle className="w-4 h-4" />
                Tests Failed (Exit Code: {exit_code})
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
          {duration_ms && (
            <span className="hidden sm:inline-flex items-center gap-1">
              <Timer className="w-3.5 h-3.5 text-sky-400" />
              {duration_ms}ms
            </span>
          )}
          {sandbox_mode && (
            <span className="hidden md:inline-flex items-center gap-1 text-slate-500">
              <Cpu className="w-3.5 h-3.5" />
              {sandbox_mode === 'docker' ? 'Docker Sandbox' : 'Local Sandbox'}
            </span>
          )}
          <button className="p-1 hover:text-white">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="p-4 space-y-3.5 text-xs text-slate-300">
          {/* Rationale */}
          {explanation && (
            <div>
              <span className="font-semibold text-slate-400 text-[11px] uppercase tracking-wider block mb-1">
                Patch Rationale:
              </span>
              <p className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-slate-200 leading-relaxed">
                {explanation}
              </p>
            </div>
          )}

          {/* Patch Diff */}
          {diff && (
            <div>
              <span className="font-semibold text-slate-400 text-[11px] uppercase tracking-wider block mb-1.5">
                Applied Code Patch:
              </span>
              <DiffViewer diffText={diff} title={`Patch Diff (Attempt ${attempt})`} />
            </div>
          )}

          {/* Sandbox execution output */}
          {(stderr || stdout) && (
            <div className="pt-2 border-t border-slate-800">
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-semibold text-slate-400 text-[11px] uppercase tracking-wider">
                  Sandbox Test Execution Output:
                </span>
                {stdout && (
                  <button
                    onClick={() => setShowStdout(!showStdout)}
                    className="text-[11px] text-sky-400 hover:underline"
                  >
                    {showStdout ? 'Hide stdout' : 'Show full stdout'}
                  </button>
                )}
              </div>

              {stderr && (
                <pre className="p-3 rounded-lg bg-rose-950/30 border border-rose-900/40 text-rose-300 font-mono overflow-x-auto whitespace-pre-wrap">
                  {stderr}
                </pre>
              )}

              {stdout && showStdout && (
                <pre className="mt-2 p-3 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap">
                  {stdout}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
