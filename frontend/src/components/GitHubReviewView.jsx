import React, { useState } from 'react';
import { 
  GitPullRequest, 
  Github, 
  Search, 
  FileCode, 
  ExternalLink, 
  CheckCircle2, 
  AlertTriangle, 
  Sparkles, 
  ArrowRight, 
  Bot, 
  Key, 
  RefreshCw,
  FolderGit2,
  FilePlus,
  FileMinus,
  FileDiff,
  ShieldAlert,
  ShieldCheck,
  Zap
} from 'lucide-react';
import { inspectGitHubTarget, fetchGitHubFile, submitCodeReview } from '../services/api';
import ReviewSummaryBanner from './ReviewSummaryBanner';
import FindingCard from './FindingCard';
import SecurityFindingCard from './SecurityFindingCard';
import FullCodeModal from './FullCodeModal';

const GITHUB_PRESETS = [
  {
    label: 'FastAPI Repository',
    url: 'https://github.com/tiangolo/fastapi',
    type: 'repo',
  },
  {
    label: 'Express.js Repository',
    url: 'https://github.com/expressjs/express',
    type: 'repo',
  },
];

export default function GitHubReviewView({
  apiKey,
  model,
  onNavigateToAgent,
}) {
  const [url, setUrl] = useState('');
  const [githubToken, setGithubToken] = useState(() => localStorage.getItem('github_token') || '');
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [inspecting, setInspecting] = useState(false);
  const [inspectResult, setInspectResult] = useState(null);
  const [inspectError, setInspectError] = useState(null);

  // File search & selection
  const [fileSearch, setFileSearch] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [fetchingFile, setFetchingFile] = useState(false);

  // Review state
  const [reviewing, setReviewing] = useState(false);
  const [reviewResult, setReviewResult] = useState(null);
  const [reviewError, setReviewError] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');
  const [activeReviewTab, setActiveReviewTab] = useState('general'); // 'general' | 'security'
  const [isFullFixModalOpen, setIsFullFixModalOpen] = useState(false);
  const [sandboxDisabled, setSandboxDisabled] = useState(false);

  const handleInspect = async (targetUrl = url) => {
    if (!targetUrl.trim()) return;
    setInspecting(true);
    setInspectError(null);
    setInspectResult(null);
    setSelectedFile(null);
    setFileContent('');
    setReviewResult(null);

    const result = await inspectGitHubTarget(targetUrl.trim(), githubToken);
    if (result.success) {
      setInspectResult(result.data);
      // Auto-select first file if available
      if (result.data.reviewable_files?.length > 0) {
        handleSelectFile(result.data.reviewable_files[0], result.data);
      }
    } else {
      setInspectError(result.error);
    }
    setInspecting(false);
  };

  const handleSelectFile = async (fileItem, currentInspectResult = inspectResult) => {
    if (!currentInspectResult) return;
    setSelectedFile(fileItem);
    setFetchingFile(true);
    setReviewResult(null);
    setReviewError(null);

    const result = await fetchGitHubFile({
      owner: currentInspectResult.owner,
      repo: currentInspectResult.repo,
      path: fileItem.path,
      ref: fileItem.sha || currentInspectResult.default_branch || currentInspectResult.head_sha,
      githubToken,
    });

    if (result.success) {
      setFileContent(result.data.content);
      // Automatically trigger code review for the selected file with dedicated security pass
      handleRunFileReview(result.data.content, fileItem.language, fileItem.filename, currentInspectResult, fileItem);
    } else {
      setReviewError(result.error);
    }
    setFetchingFile(false);
  };

  const handleRunFileReview = async (content, language, filename) => {
    // Ensure TypeScript runner for TypeScript files (including .d.ts)
    let effectiveLanguage = language;
    if (filename && filename.toLowerCase().endsWith('.ts')) {
      effectiveLanguage = 'typescript';
    } else if (filename && filename.toLowerCase().endsWith('.tsx')) {
      effectiveLanguage = 'typescript';
    } else if (filename && filename.toLowerCase().endsWith('.d.ts')) {
      effectiveLanguage = 'typescript';
    }
    setReviewing(true);
    setReviewError(null);

    const result = await submitCodeReview({
      code: content,
      language: effectiveLanguage,
      filename,
      apiKey,
      model,
      runStaticAnalysis: true,
      runSecurityPass: true,
    });

    if (result.success) {
      setReviewResult(result.data);
      setSelectedCategory('all');
      setSelectedSeverity('all');
      // If critical/high security issues exist, default or notify
      if (result.data.security_findings?.length > 0) {
        const hasCritical = result.data.security_findings.some(f => f.severity === 'critical' || f.severity === 'high');
        if (hasCritical) {
          setActiveReviewTab('security');
        }
      }
    } else {
      setReviewError(result.error);
    }
    setReviewing(false);
  };

  const handleFixSecurityInSandbox = (secFinding) => {
    if (!onNavigateToAgent || !inspectResult || !selectedFile) return;
    onNavigateToAgent({
      code: fileContent,
      language: selectedFile.language,
      filename: selectedFile.filename,
      bugDescription: `[${(secFinding.severity || 'HIGH').toUpperCase()} Security Vulnerability: ${secFinding.vulnerability_type}] ${secFinding.explanation}. Exploitability: ${secFinding.exploitability}. Suggested fix: ${secFinding.suggested_fix || ''}`,
      githubContext: {
        owner: inspectResult.owner,
        repo: inspectResult.repo,
        branch: selectedFile.sha || inspectResult.default_branch || inspectResult.head_sha || 'main',
        baseBranch: inspectResult.base_branch || inspectResult.default_branch || 'main',
        filePath: selectedFile.path,
        finding: {
          title: secFinding.title || secFinding.vulnerability_type,
          severity: secFinding.severity,
          category: 'security',
          vulnerabilityType: secFinding.vulnerability_type,
          explanation: secFinding.explanation,
        },
      },
    });
  };

  const handleSaveToken = (val) => {
    setGithubToken(val);
    localStorage.setItem('github_token', val);
  };

  const filteredFiles = (inspectResult?.reviewable_files || []).filter((f) =>
    f.path.toLowerCase().includes(fileSearch.toLowerCase())
  );

  const filteredFindings = (reviewResult?.findings || []).filter((f) => {
    const matchesCategory = selectedCategory === 'all' || f.category === selectedCategory;
    const matchesSeverity = selectedSeverity === 'all' || f.severity === selectedSeverity;
    return matchesCategory && matchesSeverity;
  });

  return (
    <div className="space-y-6">
      {/* Top GitHub URL Input Banner */}
      <div className="p-6 rounded-2xl border border-purple-500/30 bg-gradient-to-r from-purple-950/40 via-slate-900 to-slate-900 shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <GitPullRequest className="w-6 h-6 text-purple-400" />
              <h2 className="text-xl font-bold text-white tracking-tight">
                GitHub Repository & PR Review
              </h2>
            </div>
            <p className="text-xs text-slate-300 max-w-2xl">
              Inspect any public GitHub repository or Pull Request diff, automatically discover reviewable Python & JS/TS files, and run the static + Grok AI review pipeline on selected files.
            </p>
          </div>

          {/* Optional GitHub Token Toggle */}
          <button
            onClick={() => setShowTokenInput(!showTokenInput)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 border border-slate-700 text-xs text-slate-300 hover:text-white transition self-start md:self-auto"
          >
            <Key className="w-3.5 h-3.5 text-purple-400" />
            <span>{githubToken ? 'GitHub Token Configured' : 'Add GitHub Token (Optional)'}</span>
          </button>
        </div>

        {/* GitHub Token Input */}
        {showTokenInput && (
          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-center gap-3 animate-fadeIn text-xs">
            <Key className="w-4 h-4 text-purple-400 flex-shrink-0" />
            <input
              type="password"
              value={githubToken}
              onChange={(e) => handleSaveToken(e.target.value)}
              placeholder="Paste GitHub Personal Access Token (for private repos or rate limit lift)"
              className="flex-1 bg-transparent text-slate-200 focus:outline-none font-mono"
            />
            <span className="text-[10px] text-slate-500">Stored in browser localStorage</span>
          </div>
        )}

        {/* URL Input Bar */}
        <div className="flex flex-col sm:flex-row items-center gap-2.5">
          <div className="relative flex-1 w-full">
            <Github className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleInspect()}
              placeholder="https://github.com/owner/repo or https://github.com/owner/repo/pull/123"
              className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-xl focus:outline-none focus:border-purple-500 font-mono"
            />
          </div>

          <button
            onClick={() => handleInspect()}
            disabled={inspecting || !url.trim()}
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-bold shadow-lg shadow-purple-600/25 transition disabled:shadow-none"
          >
            {inspecting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Inspecting...</span>
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                <span>Inspect Repository / PR</span>
              </>
            )}
          </button>
        </div>

        {/* Preset Quick Links */}
        <div className="flex items-center gap-2 flex-wrap text-xs text-slate-400">
          <span className="text-[11px] font-medium">Quick Demo Presets:</span>
          {GITHUB_PRESETS.map((p, idx) => (
            <button
              key={idx}
              onClick={() => {
                setUrl(p.url);
                handleInspect(p.url);
              }}
              className="px-2.5 py-1 rounded-md bg-slate-800/80 hover:bg-slate-750 text-purple-300 border border-slate-700 text-[11px] transition"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Inspect Error Display */}
      {inspectError && (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800/50 flex items-start gap-3 text-rose-300">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-rose-200">GitHub Inspection Failed</p>
            <p className="text-rose-300/90">{inspectError}</p>
          </div>
        </div>
      )}

      {/* Inspected Content Grid */}
      {inspectResult && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fadeIn">
          {/* Left Column: Repository / PR Metadata & File Selector (4 Cols) */}
          <div className="lg:col-span-4 space-y-4">
            {/* Repo / PR Info Card */}
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/80 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {inspectResult.type === 'pr' ? (
                    <GitPullRequest className="w-4 h-4 text-purple-400" />
                  ) : (
                    <FolderGit2 className="w-4 h-4 text-sky-400" />
                  )}
                  <span className="font-bold text-xs text-white">
                    {inspectResult.owner}/{inspectResult.repo}
                  </span>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 font-mono text-purple-300">
                  {inspectResult.type === 'pr' ? `PR #${inspectResult.pr_number}` : inspectResult.default_branch}
                </span>
              </div>

              <p className="text-xs text-slate-300 line-clamp-2">
                {inspectResult.title}
              </p>

              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-2 border-t border-slate-800">
                <span>Reviewable Files: {inspectResult.reviewable_files?.length || 0}</span>
                <a
                  href={`https://github.com/${inspectResult.owner}/${inspectResult.repo}${inspectResult.type === 'pr' ? `/pull/${inspectResult.pr_number}` : ''}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-purple-400 hover:underline"
                >
                  <span>View on GitHub</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>

            {/* File List & Search */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/80 overflow-hidden flex flex-col max-h-[500px]">
              <div className="p-2.5 bg-slate-900 border-b border-slate-800">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={fileSearch}
                    onChange={(e) => setFileSearch(e.target.value)}
                    placeholder="Search files..."
                    className="w-full pl-8 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-purple-500 font-mono"
                  />
                </div>
              </div>

              <div className="p-2 overflow-y-auto space-y-1 flex-1">
                {filteredFiles.length > 0 ? (
                  filteredFiles.map((fileItem, idx) => {
                    const isSelected = selectedFile?.path === fileItem.path;
                    return (
                      <button
                        key={idx}
                        onClick={() => handleSelectFile(fileItem)}
                        className={`w-full text-left p-2.5 rounded-lg border transition text-xs flex items-center justify-between ${
                          isSelected
                            ? 'bg-purple-950/40 border-purple-500/60 text-purple-200 shadow-sm'
                            : 'bg-slate-950/40 border-slate-800/80 text-slate-300 hover:bg-slate-800/60 hover:border-slate-700'
                        }`}
                      >
                        <div className="min-w-0 flex items-center gap-2 flex-1 mr-2">
                          <FileCode className={`w-3.5 h-3.5 flex-shrink-0 ${isSelected ? 'text-purple-400' : 'text-slate-500'}`} />
                          <div className="min-w-0">
                            <p className="font-semibold truncate text-xs">{fileItem.filename}</p>
                            <p className="text-[10px] text-slate-500 font-mono truncate">{fileItem.path}</p>
                          </div>
                        </div>

                        {inspectResult.type === 'pr' ? (
                          <div className="flex items-center gap-1 font-mono text-[10px] flex-shrink-0">
                            {fileItem.additions > 0 && <span className="text-emerald-400">+{fileItem.additions}</span>}
                            {fileItem.deletions > 0 && <span className="text-rose-400">-{fileItem.deletions}</span>}
                          </div>
                        ) : (
                          <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 flex-shrink-0">
                            {fileItem.language}
                          </span>
                        )}
                      </button>
                    );
                  })
                ) : (
                  <div className="p-6 text-center text-xs text-slate-500">
                    No files found matching search.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: File Review & Results Workspace (8 Cols) */}
          <div className="lg:col-span-8 space-y-4">
            {fetchingFile || reviewing ? (
              <div className="p-16 rounded-2xl border border-slate-800 bg-slate-900/50 text-center space-y-3">
                <div className="w-8 h-8 border-2 border-purple-400/30 border-t-purple-400 rounded-full animate-spin mx-auto" />
                <h4 className="text-sm font-semibold text-white">
                  {fetchingFile ? 'Fetching file content from GitHub...' : 'Analyzing code with Static Linters & Grok...'}
                </h4>
                <p className="text-xs text-slate-400 font-mono">{selectedFile?.path}</p>
              </div>
            ) : reviewResult ? (
              <div className="space-y-6">
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
                  hasFullFix={Boolean(reviewResult.raw_fixed_code && reviewResult.raw_fixed_code !== fileContent)}
                />

                {/* Review Tab Switcher: General vs Dedicated Security */}
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setActiveReviewTab('general')}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                        activeReviewTab === 'general'
                          ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                          : 'text-slate-400 hover:text-white bg-slate-900'
                      }`}
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>General Findings ({reviewResult.findings?.length || 0})</span>
                    </button>

                    <button
                      onClick={() => setActiveReviewTab('security')}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                        activeReviewTab === 'security'
                          ? 'bg-red-500/20 text-red-300 border border-red-500/50 shadow-sm'
                          : 'text-slate-400 hover:text-white bg-slate-900'
                      }`}
                    >
                      <ShieldAlert className="w-3.5 h-3.5 text-red-400" />
                      <span>Security Audit</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                        (reviewResult.security_findings?.length || 0) > 0 ? 'bg-red-500 text-white' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {reviewResult.security_findings?.length || 0}
                      </span>
                    </button>
                  </div>

                  <span className="text-xs font-mono text-slate-400">
                    {activeReviewTab === 'general'
                      ? `${filteredFindings.length} issue(s)`
                      : `${reviewResult.security_findings?.length || 0} vulnerability(ies)`}
                  </span>
                </div>

                {/* Content View Based on Active Tab */}
                {activeReviewTab === 'general' ? (
                  <div className="space-y-4">
                    {filteredFindings.length > 0 ? (
                      filteredFindings.map((finding) => (
                        <FindingCard
                          key={finding.id || finding.line + finding.title}
                          finding={finding}
                        />
                      ))
                    ) : (
                      <div className="p-10 text-center rounded-xl border border-slate-800 bg-slate-900/40 space-y-2">
                        <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                        <p className="text-xs font-semibold text-white">No Issues Matching Filter</p>
                        <p className="text-xs text-slate-400">All checks passed cleanly for this file filter.</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {reviewResult.security_findings && reviewResult.security_findings.length > 0 ? (
                      reviewResult.security_findings.map((secFinding) => (
                        <SecurityFindingCard
                          key={secFinding.id || secFinding.line + secFinding.title}
                          finding={secFinding}
                          onFixInSandbox={handleFixSecurityInSandbox}
                        />
                      ))
                    ) : (
                      <div className="p-10 text-center rounded-xl border border-slate-800 bg-slate-900/40 space-y-2">
                        <ShieldCheck className="w-8 h-8 text-emerald-400 mx-auto" />
                        <p className="text-xs font-semibold text-white">No Security Vulnerabilities Detected</p>
                        <p className="text-xs text-slate-400">
                          Deterministic security rules and AppSec review found no exploitable security vectors in this file.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Send to Sandbox Agent CTA */}
                <div className="p-4 rounded-xl border border-sky-500/30 bg-sky-950/20 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-sky-500/20 text-sky-300">
                      <Bot className="w-5 h-5" />
                    </div>
                    <div>
                      <h5 className="text-xs font-bold text-white">Autonomous Sandbox Repair</h5>
                      <p className="text-[11px] text-slate-400">
                        Launch this file in the Sandbox Fix Agent to automatically synthesize tests and verify fixes.
                      </p>
                    </div>
                  </div>
                  {onNavigateToAgent && (
                    <button
                      onClick={() =>
                        onNavigateToAgent({
                          code: fileContent,
                          language: selectedFile.language,
                          filename: selectedFile.filename,
                          bugDescription: reviewResult.findings[0]?.explanation || 'Fix issues found in review',
                          githubContext: {
                            owner: inspectResult.owner,
                            repo: inspectResult.repo,
                            branch: selectedFile.sha || inspectResult.default_branch || inspectResult.head_sha || 'main',
                            baseBranch: inspectResult.base_branch || inspectResult.default_branch || 'main',
                            filePath: selectedFile.path,
                            finding: {
                              title: reviewResult.findings[0]?.title || 'Code Review Findings',
                              severity: reviewResult.findings[0]?.severity || 'medium',
                              category: reviewResult.findings[0]?.category || 'bug',
                              explanation: reviewResult.findings[0]?.explanation || 'Fix issues found in review',
                            },
                          },
                        })
                      }
                      disabled={sandboxDisabled}
                      className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold shadow transition flex-shrink-0 ${sandboxDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      <span>{sandboxDisabled ? 'Sandbox Disabled' : 'Fix in Sandbox'}</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-16 rounded-2xl border border-slate-800 bg-slate-900/40 text-center space-y-2 text-slate-400">
                <FileCode className="w-10 h-10 text-slate-600 mx-auto mb-2" />
                <p className="text-xs font-semibold text-white">Select a file from the repository to review</p>
                <p className="text-xs text-slate-500">Pick any Python or JavaScript file from the left sidebar to run the review.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Full Patched Code Modal */}
      <FullCodeModal
        isOpen={isFullFixModalOpen}
        onClose={() => setIsFullFixModalOpen(false)}
        originalCode={fileContent}
        fixedCode={reviewResult?.raw_fixed_code}
        filename={selectedFile?.filename || 'solution'}
        language={selectedFile?.language || 'python'}
        githubContext={inspectResult}
        selectedFile={selectedFile}
        githubToken={githubToken}
        onApplySuccess={() => setSandboxDisabled(true)}
      />
    </div>
  );
}
