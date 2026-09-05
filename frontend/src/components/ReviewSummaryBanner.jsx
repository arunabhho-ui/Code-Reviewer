import React from 'react';
import { 
  Bug, 
  ShieldAlert, 
  Zap, 
  Paintbrush, 
  CheckCircle2, 
  Coins, 
  Timer,
  FileCode,
  Sparkles
} from 'lucide-react';

export default function ReviewSummaryBanner({
  summary,
  executionTimeMs,
  tokenUsage,
  selectedCategory,
  onSelectCategory,
  selectedSeverity,
  onSelectSeverity,
  onViewFullFix,
  hasFullFix,
}) {
  if (!summary) return null;

  // Determine score color
  const score = summary.overall_score ?? 100;
  let scoreColor = 'text-emerald-400 border-emerald-500/40 bg-emerald-950/20';
  if (score < 50) {
    scoreColor = 'text-rose-400 border-rose-500/40 bg-rose-950/20';
  } else if (score < 80) {
    scoreColor = 'text-amber-400 border-amber-500/40 bg-amber-950/20';
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 space-y-5 shadow-lg">
      {/* Top metrics header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        {/* Quality Score & Total Issues */}
        <div className="flex items-center gap-4">
          <div className={`w-16 h-16 rounded-2xl border-2 flex flex-col items-center justify-center font-bold ${scoreColor}`}>
            <span className="text-xl leading-none">{score}</span>
            <span className="text-[9px] uppercase tracking-wider text-slate-400">Score</span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-white">Review Summary</h3>
              {summary.static_analysis_passed ? (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-medium flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Static Linter Passed
                </span>
              ) : (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 font-medium">
                  Static Warnings Detected
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Found <span className="font-semibold text-white">{summary.total_issues}</span> potential improvements across your code.
            </p>
          </div>
        </div>

        {/* Telemetry info & View Full Fix CTA */}
        <div className="flex items-center gap-3 flex-wrap">
          {executionTimeMs && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-300">
              <Timer className="w-3.5 h-3.5 text-sky-400" />
              <span>{executionTimeMs}ms</span>
            </div>
          )}

          {tokenUsage && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-300">
              <Coins className="w-3.5 h-3.5 text-amber-400" />
              <span>
                {tokenUsage.input_tokens + tokenUsage.output_tokens} tokens (${tokenUsage.estimated_cost_usd})
              </span>
            </div>
          )}

          {hasFullFix && (
            <button
              onClick={onViewFullFix}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold shadow-md transition"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>View Patched File</span>
            </button>
          )}
        </div>
      </div>

      {/* Category breakdown filter tabs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {[
          { id: 'bug', label: 'Bugs / Flaws', count: summary.bugs, icon: Bug, color: 'text-rose-400', bg: 'hover:bg-rose-950/30' },
          { id: 'security', label: 'Security', count: summary.security, icon: ShieldAlert, color: 'text-amber-400', bg: 'hover:bg-amber-950/30' },
          { id: 'performance', label: 'Performance', count: summary.performance, icon: Zap, color: 'text-sky-400', bg: 'hover:bg-sky-950/30' },
          { id: 'style', label: 'Style & Cleanliness', count: summary.style, icon: Paintbrush, color: 'text-purple-400', bg: 'hover:bg-purple-950/30' },
        ].map((item) => {
          const Icon = item.icon;
          const isSelected = selectedCategory === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectCategory(isSelected ? 'all' : item.id)}
              className={`p-3 rounded-lg border text-left transition flex items-center justify-between ${item.bg} ${
                isSelected
                  ? 'bg-slate-800 border-sky-500 ring-1 ring-sky-500/50'
                  : 'bg-slate-900/60 border-slate-800'
              }`}
            >
              <div className="flex items-center gap-2">
                <Icon className={`w-4 h-4 ${item.color}`} />
                <span className="text-xs font-medium text-slate-300">{item.label}</span>
              </div>
              <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                item.count > 0 ? 'bg-slate-800 text-white' : 'text-slate-500'
              }`}>
                {item.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Severity filter bar */}
      <div className="flex items-center gap-2 flex-wrap pt-2 border-t border-slate-800 text-xs">
        <span className="text-slate-400 font-medium mr-1">Filter Severity:</span>
        {[
          { id: 'all', label: 'All', count: summary.total_issues },
          { id: 'critical', label: 'Critical', count: summary.critical, color: 'text-red-400' },
          { id: 'high', label: 'High', count: summary.high, color: 'text-orange-400' },
          { id: 'medium', label: 'Medium', count: summary.medium, color: 'text-amber-400' },
          { id: 'low', label: 'Low', count: summary.low, color: 'text-blue-400' },
          { id: 'info', label: 'Info', count: summary.info, color: 'text-slate-400' },
        ].map((sev) => (
          <button
            key={sev.id}
            onClick={() => onSelectSeverity(sev.id)}
            className={`px-2.5 py-1 rounded-md transition font-medium flex items-center gap-1.5 ${
              selectedSeverity === sev.id
                ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40'
                : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-slate-700/50'
            }`}
          >
            <span>{sev.label}</span>
            <span className={`text-[10px] font-bold ${sev.color || 'text-slate-300'}`}>
              {sev.count}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
