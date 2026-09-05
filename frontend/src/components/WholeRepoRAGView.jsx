import React, { useState } from 'react';
import {
  Database,
  Sparkles,
  FileCode,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Bot,
  RefreshCw,
  Search,
  Network,
  Key,
  Github,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { indexRepoRAG, reviewWithRAG, inspectGitHubTarget, fetchGitHubFile } from '../services/api';
import FindingCard from './FindingCard';
import SecurityFindingCard from './SecurityFindingCard';
import ReviewSummaryBanner from './ReviewSummaryBanner';
import FullCodeModal from './FullCodeModal';

export default function WholeRepoRAGView({
  apiKey,
  model,
  onNavigateToAgent,
}) {
  const [repoUrl, setRepoUrl] = useState('https://github.com/tiangolo/fastapi');
  const [githubToken, setGithubToken] = useState(() => localStorage.getItem('github_token') || '');
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [repoFiles, setRepoFiles] = useState([]);
  const [repoName, setRepoName] = useState('');
  const [activeFileIndex, setActiveFileIndex] = useState(0);
  const [loadingRepo, setLoadingRepo] = useState(false);
  const [repoError, setRepoError] = useState(null);

  const [indexing, setIndexing] = useState(false);
  const [indexData, setIndexData] = useState(null);
  const [indexError, setIndexError] = useState(null);

  const [reviewing, setReviewing] = useState(false);
  const [reviewResult, setReviewResult] = useState(null);
  const [crossContext, setCrossContext] = useState([]);
  const [reviewError, setReviewError] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');
  const [activeReviewTab, setActiveReviewTab] = useState('general'); // 'general' | 'security'
  const [isFullFixModalOpen, setIsFullFixModalOpen] = useState(false);

  const currentFile = repoFiles[activeFileIndex] || null;

  const handleSaveToken = (val) => {
    setGithubToken(val);
    localStorage.setItem('github_token', val);
  };

  const handleIndexProject = async (projectFiles = repoFiles, projectRepoName = repoName) => {
    if (!projectRepoName || !projectFiles.length) return;

    setIndexing(true);
    setIndexError(null);
    setIndexData(null);
    setReviewResult(null);
    setCrossContext([]);

    const result = await indexRepoRAG(projectRepoName, projectFiles);
    if (result.success) {
      setIndexData(result.data);
    } else {
      setIndexError(result.error);
    }
    setIndexing(false);
  };

  const handleLoadRepo = async (targetUrl = repoUrl) => {
    if (!targetUrl.trim()) return;

    setLoadingRepo(true);
    setRepoError(null);
    setReviewResult(null);
    setCrossContext([]);

    const inspectResult = await inspectGitHubTarget(targetUrl.trim(), githubToken);
    if (!inspectResult.success) {
      setRepoError(inspectResult.error);
      setLoadingRepo(false);
      return;
    }

    const inspectData = inspectResult.data;
    const reviewableFiles = inspectData.reviewable_files || [];

    if (!reviewableFiles.length) {
      setRepoError('No supported Python/JS/TS files were found in this repository.');
      setLoadingRepo(false);
      return;
    }

    const fetchedFiles = [];
    for (const fileItem of reviewableFiles) {
      const fileResult = await fetchGitHubFile({
        owner: inspectData.owner,
        repo: inspectData.repo,
        path: fileItem.path,
        ref: fileItem.sha || inspectData.default_branch || inspectData.head_sha,
        githubToken,
      });

      if (fileResult.success) {
        fetchedFiles.push({
          path: fileItem.path,
          filename: fileItem.filename,
          language: fileItem.language,
          content: fileResult.data.content,
        });
      }
    }

    if (!fetchedFiles.length) {
      setRepoError('The repo was discovered, but none of its supported files could be fetched.');
      setLoadingRepo(false);
      return;
    }

    const nextRepoName = `${inspectData.owner}/${inspectData.repo}`;
    setRepoName(nextRepoName);
    setRepoFiles(fetchedFiles);
    setActiveFileIndex(fetchedFiles.length - 1);
    setLoadingRepo(false);

    await handleIndexProject(fetchedFiles, nextRepoName);
  };

  const handleRunRAGReview = async () => {
    if (!currentFile || !repoName) {
      return;
    }

    if (!indexData) {
      await handleIndexProject(repoFiles, repoName);
    }

    setReviewing(true);
    setReviewError(null);
    setReviewResult(null);
    setCrossContext([]);

    const result = await reviewWithRAG({
      repoName,
      targetFilePath: currentFile.path,
      code: currentFile.content,
      language: currentFile.language,
      apiKey,
      model,
      runStaticAnalysis: true,
      runSecurityPass: true,
      topKContext: 4,
    });

    if (result.success) {
      setReviewResult(result.data.review);
      setCrossContext(result.data.cross_file_context || []);
      setSelectedCategory('all');
      setSelectedSeverity('all');
      if (result.data.review?.security_findings?.length > 0) {
        const hasCritical = result.data.review.security_findings.some(f => f.severity === 'critical' || f.severity === 'high');
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
    if (!onNavigateToAgent || !currentFile) return;
    const [owner, repo] = (repoName || '').split('/');
    onNavigateToAgent({
      code: currentFile.content,
      language: currentFile.language,
      filename: currentFile.path.split('/').pop(),
      bugDescription: `[${(secFinding.severity || 'HIGH').toUpperCase()} Security Vulnerability: ${secFinding.vulnerability_type}] ${secFinding.explanation}. Exploitability: ${secFinding.exploitability}. Suggested fix: ${secFinding.suggested_fix || ''}`,
      githubContext: {
        owner: owner || 'repo-owner',
        repo: repo || 'repo-name',
        branch: 'main',
        baseBranch: 'main',
        filePath: currentFile.path,
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

  const filteredFindings = (reviewResult?.findings || []).filter((f) => {
    const matchesCategory = selectedCategory === 'all' || f.category === selectedCategory;
    const matchesSeverity = selectedSeverity === 'all' || f.severity === selectedSeverity;
    return matchesCategory && matchesSeverity;
  });

  return (
    <div className="space-y-6">
      <div className="p-6 rounded-2xl border border-amber-500/30 bg-gradient-to-r from-amber-950/40 via-slate-900 to-slate-900 shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Database className="w-6 h-6 text-amber-400" />
              <h2 className="text-xl font-bold text-white tracking-tight">
                Whole-Repository RAG Mode
              </h2>
              <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold uppercase tracking-wider">
                Advanced Mode
              </span>
            </div>
            <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">
              Paste a GitHub repository URL, fetch the supported Python/JS/TS files, index them into ChromaDB, and review one file with cross-file symbol context from the rest of the repo.
            </p>
          </div>

          <button
            onClick={() => setShowTokenInput(!showTokenInput)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 border border-slate-700 text-xs text-slate-300 hover:text-white transition self-start md:self-auto"
          >
            <Key className="w-3.5 h-3.5 text-amber-400" />
            <span>{githubToken ? 'GitHub Token Configured' : 'Add GitHub Token (Optional)'}</span>
          </button>
        </div>

        {showTokenInput && (
          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-center gap-3 animate-fadeIn text-xs">
            <Key className="w-4 h-4 text-amber-400 flex-shrink-0" />
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

        <div className="flex flex-col sm:flex-row items-center gap-2.5">
          <div className="relative flex-1 w-full">
            <Github className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLoadRepo()}
              placeholder="https://github.com/owner/repo"
              className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-xl focus:outline-none focus:border-amber-500 font-mono"
            />
          </div>

          <button
            onClick={() => handleLoadRepo()}
            disabled={loadingRepo || !repoUrl.trim()}
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-bold shadow-lg shadow-amber-500/25 transition disabled:shadow-none"
          >
            {loadingRepo ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Loading Repo...</span>
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                <span>Load Repo & Index for RAG</span>
              </>
            )}
          </button>
        </div>
      </div>

      {repoError && (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800/50 flex items-start gap-3 text-rose-300">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-rose-200">Repository Load Failed</p>
            <p className="text-rose-300/90">{repoError}</p>
          </div>
        </div>
      )}

      {indexError && (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800/50 flex items-start gap-3 text-rose-300">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-rose-200">Chroma Index Failed</p>
            <p className="text-rose-300/90">{indexError}</p>
          </div>
        </div>
      )}

      {indexData && (
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-3">
            <div className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-4 h-4" />
            </div>
            <div>
              <span className="font-semibold text-white font-mono">{indexData.repo_name}</span>
              <span className="text-slate-400 ml-2">
                Indexed <strong className="text-white">{indexData.total_files}</strong> files into <strong className="text-white">{indexData.total_chunks}</strong> AST symbol chunks in {indexData.duration_ms}ms
              </span>
            </div>
          </div>
        </div>
      )}

      {repoFiles.length > 0 && currentFile && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 space-y-4 flex flex-col">
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden flex flex-col flex-1">
              <div className="p-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
                <div className="flex space-x-1 overflow-x-auto">
                  {repoFiles.map((file, idx) => (
                    <button
                      key={file.path}
                      onClick={() => setActiveFileIndex(idx)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                        activeFileIndex === idx
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : 'text-slate-400 hover:text-white bg-slate-800/60'
                      }`}
                    >
                      <FileCode className="w-3.5 h-3.5" />
                      <span>{file.path}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="p-3 bg-slate-950 font-mono text-xs text-slate-200 overflow-y-auto flex-1 min-h-[320px]">
                <pre className="whitespace-pre leading-relaxed">{currentFile.content}</pre>
              </div>

              <div className="p-3 bg-slate-900 border-t border-slate-800 flex items-center justify-between">
                <span className="text-[11px] text-slate-400 font-mono">
                  Target: {currentFile.path}
                </span>

                <button
                  onClick={handleRunRAGReview}
                  disabled={reviewing || indexing}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-bold shadow-lg shadow-amber-500/20 transition disabled:shadow-none"
                >
                  {reviewing ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Querying Chroma & Reviewing...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Review Target File with RAG</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          <div className="lg:col-span-7 space-y-4">
            {crossContext.length > 0 && (
              <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-950/10 space-y-3 animate-fadeIn">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Network className="w-4 h-4 text-amber-400" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-amber-300">
                      ChromaDB Retrieved Cross-File Context ({crossContext.length} chunks)
                    </h4>
                  </div>
                  <span className="text-[10px] text-amber-400 font-mono">
                    Queried at review-time
                  </span>
                </div>

                <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                  {crossContext.map((ctx, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-slate-950/80 border border-amber-800/40 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between text-[11px] font-mono">
                        <span className="text-amber-300 font-semibold">
                          [{ctx.symbol_type.toUpperCase()}] {ctx.symbol_name} in `{ctx.file_path}`
                        </span>
                        <span className="text-slate-400 text-[10px]">{ctx.relevance_reason}</span>
                      </div>
                      <pre className="text-[11px] text-slate-300 font-mono overflow-x-auto bg-slate-900/60 p-2 rounded max-h-20 whitespace-pre">
                        {ctx.code_chunk}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {reviewing ? (
              <div className="p-16 rounded-2xl border border-slate-800 bg-slate-900/50 text-center space-y-3">
                <div className="w-8 h-8 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin mx-auto" />
                <h4 className="text-sm font-semibold text-white">
                  Retrieving dependencies from ChromaDB & conducting cross-file review...
                </h4>
                <p className="text-xs text-slate-400 font-mono">{currentFile.path}</p>
              </div>
            ) : reviewResult ? (
              <div className="space-y-5 animate-fadeIn">
                <ReviewSummaryBanner
                  summary={reviewResult.summary}
                  executionTimeMs={reviewResult.execution_time_ms}
                  tokenUsage={reviewResult.token_usage}
                  selectedCategory={selectedCategory}
                  onSelectCategory={setSelectedCategory}
                  selectedSeverity={selectedSeverity}
                  onSelectSeverity={setSelectedSeverity}
                  onViewFullFix={() => setIsFullFixModalOpen(true)}
                  hasFullFix={Boolean(reviewResult.raw_fixed_code && reviewResult.raw_fixed_code !== currentFile.content)}
                />

                {/* Review Tab Switcher: General vs Dedicated Security */}
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setActiveReviewTab('general')}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                        activeReviewTab === 'general'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
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
                  <div className="space-y-3">
                    {filteredFindings.length > 0 ? (
                      filteredFindings.map((finding) => (
                        <FindingCard
                          key={finding.id || `${finding.line}-${finding.title}`}
                          finding={finding}
                        />
                      ))
                    ) : (
                      <div className="p-8 text-center rounded-xl border border-slate-800 bg-slate-900/40 space-y-2">
                        <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                        <p className="text-xs font-semibold text-white">No Issues Matching Filter</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {reviewResult.security_findings && reviewResult.security_findings.length > 0 ? (
                      reviewResult.security_findings.map((secFinding) => (
                        <SecurityFindingCard
                          key={secFinding.id || `${secFinding.line}-${secFinding.title}`}
                          finding={secFinding}
                          onFixInSandbox={handleFixSecurityInSandbox}
                        />
                      ))
                    ) : (
                      <div className="p-8 text-center rounded-xl border border-slate-800 bg-slate-900/40 space-y-2">
                        <ShieldCheck className="w-8 h-8 text-emerald-400 mx-auto" />
                        <p className="text-xs font-semibold text-white">No Security Vulnerabilities Detected</p>
                        <p className="text-xs text-slate-400">
                          Cross-file RAG audit and deterministic rules found no exploitable security flaws.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                <div className="p-4 rounded-xl border border-sky-500/30 bg-sky-950/20 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-sky-500/20 text-sky-300">
                      <Bot className="w-5 h-5" />
                    </div>
                    <div>
                      <h5 className="text-xs font-bold text-white">Autonomous Sandbox Verification</h5>
                      <p className="text-[11px] text-slate-400">
                        Launch this repaired file in the isolated sandbox to execute tests against dependencies.
                      </p>
                    </div>
                  </div>
                  {onNavigateToAgent && (
                    <button
                      onClick={() => {
                        const [owner, repo] = (repoName || '').split('/');
                        onNavigateToAgent({
                          code: currentFile.content,
                          language: currentFile.language,
                          filename: currentFile.path.split('/').pop(),
                          bugDescription: reviewResult.findings[0]?.explanation || 'Fix cross-file vulnerability',
                          githubContext: {
                            owner: owner || 'repo-owner',
                            repo: repo || 'repo-name',
                            branch: 'main',
                            baseBranch: 'main',
                            filePath: currentFile.path,
                            finding: {
                              title: reviewResult.findings[0]?.title || 'Cross-File Finding',
                              severity: reviewResult.findings[0]?.severity || 'medium',
                              category: reviewResult.findings[0]?.category || 'bug',
                              explanation: reviewResult.findings[0]?.explanation || 'Fix issues found in review',
                            },
                          },
                        });
                      }}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold shadow transition flex-shrink-0"
                    >
                      <span>Fix in Sandbox</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-16 rounded-2xl border border-slate-800 bg-slate-900/40 text-center space-y-2 text-slate-400">
                <Database className="w-10 h-10 text-slate-600 mx-auto mb-2" />
                <p className="text-xs font-semibold text-white">Ready for RAG Cross-File Analysis</p>
                <p className="text-xs text-slate-500">
                  Load a GitHub repo, index the supported files, then review a selected file with Chroma-based cross-file context.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {reviewError && (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800/50 flex items-start gap-3 text-rose-300">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-semibold text-rose-200">RAG Review Failed</p>
            <p className="text-rose-300/90">{reviewError}</p>
          </div>
        </div>
      )}

      {currentFile && (
        <FullCodeModal
          isOpen={isFullFixModalOpen}
          onClose={() => setIsFullFixModalOpen(false)}
          originalCode={currentFile.content}
          fixedCode={reviewResult?.raw_fixed_code}
          filename={currentFile.path.split('/').pop()}
          language={currentFile.language}
        />
      )}
    </div>
  );
}
