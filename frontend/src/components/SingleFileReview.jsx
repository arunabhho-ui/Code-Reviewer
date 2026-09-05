import React, { useState } from 'react';
import { 
  Sparkles, 
  AlertTriangle, 
  CheckCircle2, 
  Layers, 
  Code2, 
  Filter,
  ArrowRight,
  Bot
} from 'lucide-react';
import CodeEditor from './CodeEditor';
import FindingCard from './FindingCard';
import ReviewSummaryBanner from './ReviewSummaryBanner';
import FullCodeModal from './FullCodeModal';
import { submitCodeReview } from '../services/api';
import { CODE_SAMPLES } from '../constants/samples';

export default function SingleFileReview({
  apiKey,
  model,
  onNavigateToAgent,
}) {
  // Editor state
  const defaultSample = CODE_SAMPLES[0];
  const [code, setCode] = useState(defaultSample.code);
  const [language, setLanguage] = useState(defaultSample.language);
  const [filename, setFilename] = useState(defaultSample.filename);
  const [runStaticAnalysis, setRunStaticAnalysis] = useState(true);

  // Review status & results
  const [loading, setLoading] = useState(false);
  const [reviewResult, setReviewResult] = useState(null);
  const [error, setError] = useState(null);

  // Filtering state
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');
  const [activeTab, setActiveTab] = useState('all-findings'); // 'all-findings' | 'static-only'

  // Full fix modal state
  const [isFullFixModalOpen, setIsFullFixModalOpen] = useState(false);

  const handleRunReview = async () => {
    if (!code.trim()) return;
    setLoading(true);
    setError(null);

    const result = await submitCodeReview({
      code,
      language,
      filename,
      apiKey,
      model,
      runStaticAnalysis,
    });

    if (result.success) {
      setReviewResult(result.data);
      setSelectedCategory('all');
      setSelectedSeverity('all');
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  // Filter findings based on user category and severity filter choices
  const filteredFindings = (reviewResult?.findings || []).filter((f) => {
    const matchesCategory = selectedCategory === 'all' || f.category === selectedCategory;
    const matchesSeverity = selectedSeverity === 'all' || f.severity === selectedSeverity;
    return matchesCategory && matchesSeverity;
  });

  return (
    <div className="space-y-6">
      {/* Code Input & Editor */}
      <CodeEditor
        code={code}
        setCode={setCode}
        language={language}
        setLanguage={setLanguage}
        filename={filename}
        setFilename={setFilename}
        onRunReview={handleRunReview}
        loading={loading}
        runStaticAnalysis={runStaticAnalysis}
        setRunStaticAnalysis={setRunStaticAnalysis}
      />

      {/* Error Display */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800/50 flex items-start gap-3 text-rose-300">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-rose-200">Code Review Failed</p>
            <p className="text-rose-300/90">{error}</p>
          </div>
        </div>
      )}

      {/* Warning / Fallback Notice */}
      {reviewResult?.warning && (
        <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-800/50 flex items-center gap-3 text-amber-300 text-xs">
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
          <span>{reviewResult.warning}</span>
        </div>
      )}

      {/* Review Results Section */}
      {reviewResult && (
        <div className="space-y-6 animate-fadeIn">
          {/* Summary Banner */}
          <ReviewSummaryBanner
            summary={reviewResult.summary}
            executionTimeMs={reviewResult.execution_time_ms}
            tokenUsage={reviewResult.token_usage}
            selectedCategory={selectedCategory}
            onSelectCategory={setSelectedCategory}
            selectedSeverity={selectedSeverity}
            onSelectSeverity={setSelectedSeverity}
            onViewFullFix={() => setIsFullFixModalOpen(true)}
            hasFullFix={Boolean(reviewResult.raw_fixed_code && reviewResult.raw_fixed_code !== code)}
          />

          {/* Review Tabs (All Findings vs Static Linters) */}
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex space-x-2">
              <button
                onClick={() => setActiveTab('all-findings')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition ${
                  activeTab === 'all-findings'
                    ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40'
                    : 'text-slate-400 hover:text-white bg-slate-900'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>AI Review Findings ({reviewResult.findings.length})</span>
              </button>

              <button
                onClick={() => setActiveTab('static-only')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition ${
                  activeTab === 'static-only'
                    ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40'
                    : 'text-slate-400 hover:text-white bg-slate-900'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Static Linter Pre-Pass ({reviewResult.static_findings.length})</span>
              </button>
            </div>

            {/* Findings count indicator */}
            <span className="text-xs font-mono text-slate-400">
              Showing {filteredFindings.length} of {reviewResult.findings.length} findings
            </span>
          </div>

          {/* Content view based on active tab */}
          {activeTab === 'all-findings' ? (
            <div className="space-y-4">
              {filteredFindings.length > 0 ? (
                filteredFindings.map((finding) => (
                  <FindingCard
                    key={finding.id || finding.line + finding.title}
                    finding={finding}
                  />
                ))
              ) : (
                <div className="p-12 text-center rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
                  <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
                  <h4 className="text-base font-semibold text-white">No Issues Matching Selected Filters</h4>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto">
                    Try adjusting your category or severity filters to view other review findings.
                  </p>
                </div>
              )}
            </div>
          ) : (
            /* Static Linter Details */
            <div className="space-y-3">
              {reviewResult.static_findings.length > 0 ? (
                reviewResult.static_findings.map((sf, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between text-xs font-mono"
                  >
                    <div className="flex items-center gap-3">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-sky-300 font-bold border border-slate-700">
                        Line {sf.line}
                      </span>
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 uppercase">
                        {sf.rule}
                      </span>
                      <span className="text-slate-200">{sf.message}</span>
                    </div>
                    <span className="text-[11px] uppercase font-bold text-amber-400 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
                      {sf.severity}
                    </span>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center rounded-xl border border-slate-800 bg-slate-900/40 space-y-2">
                  <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                  <p className="text-xs font-semibold text-white">Static Linter Passed Cleanly</p>
                  <p className="text-xs text-slate-400">No syntax errors or static rule violations detected.</p>
                </div>
              )}
            </div>
          )}

          {/* Phase 2 Teaser Banner */}
          <div className="p-4 rounded-xl border border-sky-500/20 bg-sky-950/10 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-sky-500/20 text-sky-300">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <h5 className="text-xs font-bold text-white">Want autonomous verification?</h5>
                <p className="text-[11px] text-slate-400">
                  Switch to the Sandbox Fix Agent (Phase 2) to run automated test suites and verify patches inside isolated Docker containers.
                </p>
              </div>
            </div>
            {onNavigateToAgent && (
              <button
                onClick={() => onNavigateToAgent({ code, language, filename })}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold transition flex-shrink-0"
              >
                <span>Launch in Sandbox Agent</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Full Patched Code Modal */}
      <FullCodeModal
        isOpen={isFullFixModalOpen}
        onClose={() => setIsFullFixModalOpen(false)}
        originalCode={code}
        fixedCode={reviewResult?.raw_fixed_code}
        filename={filename}
        language={language}
      />
    </div>
  );
}
