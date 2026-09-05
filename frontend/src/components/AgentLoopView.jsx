import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, 
  Play, 
  Square, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Sparkles, 
  FileCode, 
  Terminal as TerminalIcon, 
  Coins, 
  RefreshCw, 
  Copy, 
  Check, 
  Layers, 
  Cpu,
  ArrowRight,
  GitPullRequest,
  ExternalLink,
  Key,
  Github
} from 'lucide-react';
import { streamAgentFix, openGitHubPR } from '../services/api';
import AgentTerminal from './AgentTerminal';
import AttemptHistoryCard from './AttemptHistoryCard';
import DiffViewer from './DiffViewer';
import { CODE_SAMPLES } from '../constants/samples';

export default function AgentLoopView({
  apiKey,
  model,
  initialPayload,
}) {
  // Source Code & Language state
  const defaultSample = CODE_SAMPLES[1]; // Python zero-division & off-by-one
  const [code, setCode] = useState(initialPayload?.code || defaultSample.code);
  const [language, setLanguage] = useState(initialPayload?.language || defaultSample.language);
  const [filename, setFilename] = useState(initialPayload?.filename || defaultSample.filename);
  const [bugDescription, setBugDescription] = useState(
    initialPayload?.bugDescription || 'ZeroDivisionError on empty list and off-by-one IndexError in metric calculation loop'
  );
  const [testCode, setTestCode] = useState('');
  const [maxRetries, setMaxRetries] = useState(3);
  const [activeCodeTab, setActiveCodeTab] = useState('code'); // 'code' | 'test'

  // GitHub Context & PR creation state
  const [githubContext, setGithubContext] = useState(initialPayload?.githubContext || null);
  const [githubToken, setGithubToken] = useState(() => localStorage.getItem('github_token') || '');
  const [isPrModalOpen, setIsPrModalOpen] = useState(false);
  const [isOpeningPr, setIsOpeningPr] = useState(false);
  const [prResult, setPrResult] = useState(null);
  const [prError, setPrError] = useState(null);

  // Agent execution state
  const [isRunning, setIsRunning] = useState(false);
  const [statusMessage, setStatusMessage] = useState('Ready to launch autonomous repair loop.');
  const [agentPhase, setAgentPhase] = useState('idle'); // 'idle' | 'generating_tests' | 'baseline' | 'fixing' | 'verified' | 'failed'
  const [logs, setLogs] = useState([]);
  const [attempts, setAttempts] = useState([]);
  const [finalResult, setFinalResult] = useState(null);
  const [error, setError] = useState(null);
  const [tokenUsage, setTokenUsage] = useState(null);
  const [copied, setCopied] = useState(false);

  const abortControllerRef = useRef(null);

  // Sync if initialPayload changes
  useEffect(() => {
    if (initialPayload) {
      if (initialPayload.code) setCode(initialPayload.code);
      if (initialPayload.language) setLanguage(initialPayload.language);
      if (initialPayload.filename) setFilename(initialPayload.filename);
      if (initialPayload.bugDescription) setBugDescription(initialPayload.bugDescription);
      if (initialPayload.githubContext) setGithubContext(initialPayload.githubContext);
      setPrResult(null);
      setPrError(null);
    }
  }, [initialPayload]);

  const addLog = (text, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { text, type, timestamp }]);
  };

  const handleStartFix = async () => {
    if (!code.trim() || isRunning) return;

    // Reset previous run state
    setIsRunning(true);
    setError(null);
    setFinalResult(null);
    setAttempts([]);
    setLogs([]);
    setTokenUsage(null);
    setAgentPhase('starting');
    setStatusMessage('Connecting to agent stream...');

    addLog(`Starting Autonomous Sandbox Fix Agent for ${filename} (${language})`, 'attempt');

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let currentAttemptObj = null;

    await streamAgentFix({
      code,
      language,
      filename,
      bugDescription,
      testCode: testCode.trim() ? testCode : undefined,
      apiKey,
      model,
      maxRetries,
      signal: controller.signal,
      onEvent: (eventType, data) => {
        const timestamp = new Date().toLocaleTimeString();

        if (eventType === 'agent_step') {
          setStatusMessage(data.message || 'Processing...');
          addLog(data.message, 'info');
          if (data.step === 'generating_tests') setAgentPhase('generating_tests');
        } else if (eventType === 'tests_ready') {
          setTestCode(data.test_code);
          addLog('Unit test suite synthesized by agent.', 'success');
        } else if (eventType === 'sandbox_executing') {
          setStatusMessage(data.message || 'Running tests in sandbox...');
          addLog(data.message, 'sandbox');
        } else if (eventType === 'baseline_result') {
          setAgentPhase('baseline');
          setStatusMessage(data.message);
          addLog(`[Baseline Sandbox] Exit Code: ${data.exit_code} | Duration: ${data.duration_ms}ms`, data.passed ? 'success' : 'fail');
          if (data.stderr) addLog(data.stderr, 'fail');
        } else if (eventType === 'attempt_start') {
          setAgentPhase('fixing');
          setStatusMessage(data.message);
          addLog(`--- Starting Attempt ${data.attempt}/${data.max_attempts} ---`, 'attempt');
          currentAttemptObj = {
            attempt: data.attempt,
            explanation: '',
            diff: '',
            passed: false,
            exit_code: 0,
            stdout: '',
            stderr: '',
            duration_ms: 0,
            sandbox_mode: 'local_sandbox',
          };
          setAttempts((prev) => [...prev, currentAttemptObj]);
        } else if (eventType === 'patch_proposed') {
          setStatusMessage(data.message);
          addLog(`Patch proposed for Attempt ${data.attempt}: ${data.explanation}`, 'info');
          setAttempts((prev) =>
            prev.map((att) =>
              att.attempt === data.attempt
                ? { ...att, explanation: data.explanation, diff: data.diff }
                : att
            )
          );
        } else if (eventType === 'sandbox_result') {
          const pass = data.passed;
          addLog(`[Sandbox Run Attempt ${data.attempt}] Result: ${pass ? 'PASSED' : 'FAILED'} (Exit: ${data.exit_code}, ${data.duration_ms}ms)`, pass ? 'success' : 'fail');
          if (data.stderr) addLog(data.stderr, 'fail');
          if (data.stdout && !pass) addLog(data.stdout, 'fail');

          setAttempts((prev) =>
            prev.map((att) =>
              att.attempt === data.attempt
                ? {
                    ...att,
                    passed: data.passed,
                    exit_code: data.exit_code,
                    stdout: data.stdout,
                    stderr: data.stderr,
                    duration_ms: data.duration_ms,
                    sandbox_mode: data.sandbox_mode,
                  }
                : att
            )
          );
        } else if (eventType === 'agent_completed') {
          setFinalResult(data);
          setTokenUsage(data.tokens);
          if (data.success) {
            setAgentPhase('verified');
            setStatusMessage('Fix Verified in Sandbox Container!');
            addLog(`Fix successfully verified inside sandbox in ${data.total_attempts} attempt(s)!`, 'success');
          } else {
            setAgentPhase('failed');
            setStatusMessage(`Fix unverified after ${data.total_attempts} attempts.`);
            addLog(`Repair loop finished without verifying all tests.`, 'fail');
          }
        } else if (eventType === 'error') {
          setError(data.message);
          addLog(`Error: ${data.message}`, 'fail');
          if (data.fatal) {
            setAgentPhase('failed');
          }
        }
      },
      onError: (err) => {
        setError(err);
        addLog(`Stream error: ${err}`, 'fail');
        setAgentPhase('failed');
      },
      onFinish: () => {
        setIsRunning(false);
      },
    });
  };

  const handleSaveToken = (val) => {
    setGithubToken(val);
    localStorage.setItem('github_token', val);
  };

  const handleOpenPR = async () => {
    if (!githubContext || !finalResult?.final_code) return;
    if (!githubToken.trim()) {
      setPrError('A GitHub Personal Access Token is required to open a pull request.');
      return;
    }
    setIsOpeningPr(true);
    setPrError(null);

    const testType = finalResult.test_type || (testCode.trim() ? 'pre_existing' : 'smoke_test');
    const finding = githubContext.finding || {};
    const findingTitle = finding.title || finding.vulnerabilityType || bugDescription;

    const result = await openGitHubPR({
      owner: githubContext.owner,
      repo: githubContext.repo,
      baseBranch: githubContext.baseBranch,
      filePath: githubContext.filePath || filename,
      fixedCode: finalResult.final_code,
      fixSummary: `Sandbox-verified patch for: ${findingTitle}.\nPassed ${testType === 'pre_existing' ? 'pre-existing test suite' : 'autonomous smoke test suite'} inside isolated execution container.`,
      findingDetails: {
        title: findingTitle,
        severity: finding.severity || 'medium',
        category: finding.category || 'bug',
        vulnerability_type: finding.vulnerabilityType,
      },
      testVerificationType: testType,
      githubToken: githubToken.trim(),
    });

    if (result.success) {
      setPrResult(result.data);
      setIsPrModalOpen(false);
      addLog(`Pull Request opened successfully: ${result.data.pr_url}`, 'success');
    } else {
      setPrError(result.error);
      addLog(`Failed to open Pull Request: ${result.error}`, 'fail');
    }
    setIsOpeningPr(false);
  };

  const handleStopFix = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsRunning(false);
      setStatusMessage('Agent execution halted by user.');
      addLog('Agent execution aborted by user.', 'fail');
    }
  };

  const handleCopyFinalCode = () => {
    if (finalResult?.final_code) {
      navigator.clipboard.writeText(finalResult.final_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl border border-sky-500/30 bg-gradient-to-r from-sky-950/40 via-slate-900 to-slate-900 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Bot className="w-6 h-6 text-sky-400" />
            <h2 className="text-xl font-bold text-white tracking-tight">
              Autonomous Sandboxed Fix Agent
            </h2>
          </div>
          <p className="text-xs text-slate-300 max-w-2xl">
            Multi-turn repair loop: Grok analyzes bug findings, synthesizes test suites, proposes code patches, and validates them inside an isolated sandbox until tests pass or the retry cap is reached.
          </p>
        </div>

        {/* Action Controls & Token metrics */}
        <div className="flex items-center gap-3 flex-wrap">
          {tokenUsage && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-xs text-slate-300 font-mono">
              <Coins className="w-3.5 h-3.5 text-amber-400" />
              <span>{tokenUsage.total_tokens} tokens (${tokenUsage.cost_usd})</span>
            </div>
          )}

          {isRunning ? (
            <button
              onClick={handleStopFix}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg transition"
            >
              <Square className="w-4 h-4 fill-current" />
              <span>Stop Agent</span>
            </button>
          ) : (
            <button
              onClick={handleStartFix}
              disabled={!code.trim()}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-600 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-bold shadow-lg shadow-sky-500/25 transition disabled:shadow-none"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>Start Autonomous Fix</span>
            </button>
          )}
        </div>
      </div>

      {/* Target GitHub Repository Context Header */}
      {githubContext && (
        <div className="p-3.5 rounded-xl bg-purple-950/30 border border-purple-500/40 flex flex-wrap items-center justify-between gap-3 text-xs animate-fadeIn">
          <div className="flex items-center gap-2.5 min-w-0">
            <Github className="w-4 h-4 text-purple-400 flex-shrink-0" />
            <div className="truncate">
              <span className="text-slate-400">Target Repo:</span>{' '}
              <span className="font-bold text-white font-mono">{githubContext.owner}/{githubContext.repo}</span>
              <span className="text-purple-300 font-mono ml-2">({githubContext.filePath || filename})</span>
              <span className="text-slate-500 text-[10px] ml-2">Base Branch: {githubContext.baseBranch || 'main'}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Key className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
            <input
              type="password"
              value={githubToken}
              onChange={(e) => handleSaveToken(e.target.value)}
              placeholder="GitHub PAT for PR creation..."
              className="bg-slate-950 border border-slate-700 text-slate-200 px-2.5 py-1 rounded text-xs font-mono w-56 focus:outline-none focus:border-purple-500"
            />
          </div>
        </div>
      )}

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Code, Bug Details, Tests (5 Cols) */}
        <div className="lg:col-span-5 space-y-4 flex flex-col">
          {/* Target Bug Description Box */}
          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/70 space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
              Bug Description & Target Goal
            </label>
            <input
              type="text"
              value={bugDescription}
              onChange={(e) => setBugDescription(e.target.value)}
              placeholder="e.g. ZeroDivisionError when array is empty..."
              className="w-full bg-slate-950 border border-slate-700 text-slate-200 px-3 py-2 rounded-lg text-xs focus:outline-none focus:border-sky-500 font-sans"
            />
          </div>

          {/* Code & Test Tabs */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden flex-1 flex flex-col min-h-[380px]">
            <div className="px-3 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
              <div className="flex bg-slate-800 p-0.5 rounded-lg border border-slate-700 text-xs">
                <button
                  onClick={() => setActiveCodeTab('code')}
                  className={`px-3 py-1 rounded-md font-medium transition ${
                    activeCodeTab === 'code' ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Source Code ({filename})
                </button>
                <button
                  onClick={() => setActiveCodeTab('test')}
                  className={`px-3 py-1 rounded-md font-medium transition ${
                    activeCodeTab === 'test' ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Unit Tests {testCode ? '(Loaded)' : '(Auto-generated)'}
                </button>
              </div>

              <div className="text-[11px] text-slate-400 font-mono">
                {language.toUpperCase()}
              </div>
            </div>

            {/* Editor Body */}
            {activeCodeTab === 'code' ? (
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Paste code containing bugs here..."
                spellCheck={false}
                className="flex-1 p-3 bg-slate-950 text-slate-200 resize-y focus:outline-none font-mono text-xs leading-relaxed min-h-[300px]"
              />
            ) : (
              <div className="flex-1 flex flex-col bg-slate-950">
                <textarea
                  value={testCode}
                  onChange={(e) => setTestCode(e.target.value)}
                  placeholder="// Leave empty for agent to auto-generate unit tests, or provide your own test suite..."
                  spellCheck={false}
                  className="flex-1 p-3 bg-slate-950 text-sky-200 resize-y focus:outline-none font-mono text-xs leading-relaxed min-h-[300px]"
                />
                {!testCode && (
                  <div className="p-2.5 bg-slate-900/80 border-t border-slate-800 text-[11px] text-slate-400 flex items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                    <span>Agent will auto-synthesize pytest/node:test assertions before repair.</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Live Agent Dashboard, Timeline, Terminal, Diffs (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Status Header Bar */}
          <div className={`p-4 rounded-xl border flex items-center justify-between gap-3 ${
            agentPhase === 'verified'
              ? 'bg-emerald-950/20 border-emerald-500/40 text-emerald-300'
              : agentPhase === 'failed'
              ? 'bg-rose-950/20 border-rose-500/40 text-rose-300'
              : isRunning
              ? 'bg-sky-950/20 border-sky-500/40 text-sky-300'
              : 'bg-slate-900/60 border-slate-800 text-slate-300'
          }`}>
            <div className="flex items-center gap-3 min-w-0">
              {isRunning ? (
                <div className="w-5 h-5 border-2 border-sky-400/30 border-t-sky-400 rounded-full animate-spin flex-shrink-0" />
              ) : agentPhase === 'verified' ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
              ) : agentPhase === 'failed' ? (
                <XCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
              ) : (
                <Bot className="w-5 h-5 text-slate-400 flex-shrink-0" />
              )}
              <div className="min-w-0">
                <p className="font-semibold text-xs text-white truncate">{statusMessage}</p>
                <p className="text-[11px] opacity-80 truncate">
                  {isRunning ? 'Streaming real-time execution steps...' : 'Sandbox timeout: 10s &bull; Network: Disabled'}
                </p>
              </div>
            </div>

            <div className="text-[11px] font-mono font-semibold px-2.5 py-1 rounded bg-slate-900 border border-slate-700">
              Retries: {attempts.length} / {maxRetries}
            </div>
          </div>

          {/* Live Agent Terminal Console */}
          <AgentTerminal logs={logs} isRunning={isRunning} />

          {/* Attempt Progression Cards */}
          {attempts.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Repair Attempts & Verification Trail
              </h4>
              {attempts.map((att) => (
                <AttemptHistoryCard key={att.attempt} attemptData={att} />
              ))}
            </div>
          )}

          {/* Final Patched Code Result Box */}
          {finalResult && (
            <div className={`p-5 rounded-2xl border space-y-4 shadow-xl ${
              finalResult.success
                ? 'bg-slate-900/90 border-emerald-500/40 ring-1 ring-emerald-500/20'
                : 'bg-slate-900/90 border-slate-800'
            }`}>
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2.5">
                  <div className={`p-2 rounded-lg ${finalResult.success ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800 text-slate-400'}`}>
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-sm">
                      {finalResult.success ? 'Final Verified Solution' : 'Latest Unverified Revision'}
                    </h3>
                    <p className="text-xs text-slate-400">
                      {finalResult.success
                        ? `Tested and passed all sandbox assertions in ${finalResult.total_attempts} attempt(s)`
                        : 'Review output and retry with updated test cases or instructions'}
                    </p>
                  </div>
                </div>

                <button
                  onClick={handleCopyFinalCode}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition shadow"
                >
                  {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy Fixed Code'}</span>
                </button>
              </div>

              {/* Code Preview */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-emerald-300 overflow-x-auto max-h-[300px]">
                <pre className="whitespace-pre leading-relaxed">{finalResult.final_code}</pre>
              </div>

              {/* Feature 2: Auto-Open GitHub PR with Verified Fix */}
              {githubContext && (
                <div className="pt-3 border-t border-slate-800 space-y-3">
                  {finalResult.success || attempts.length >= maxRetries ? (
                    <>
                      {prResult ? (
                        /* Celebratory Confirmation State after PR opened */
                        <div className="p-4 rounded-xl border border-emerald-500/50 bg-gradient-to-r from-emerald-950/50 via-slate-900 to-slate-900 shadow-xl space-y-2.5 animate-fadeIn">
                          <div className="flex items-center justify-between flex-wrap gap-2">
                            <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                              <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                              <span>Pull Request Successfully Created on GitHub!</span>
                            </div>
                            <a
                              href={prResult.pr_url}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg transition"
                            >
                              <span>View PR #{prResult.pr_number} on GitHub</span>
                              <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                          </div>
                          <div className="text-xs text-slate-300 pl-7 space-y-1">
                            <p>
                              Branch: <code className="text-purple-300 font-mono bg-slate-950 px-2 py-0.5 rounded border border-purple-500/30">{prResult.branch}</code>
                            </p>
                            <p className="text-[11px] text-slate-400">
                              Verified by isolated sandbox container ({finalResult.test_type === 'pre_existing' ? 'pre-existing test suite' : 'autonomous smoke test suite'}). Autonomous merging is disabled; human code review is required.
                            </p>
                          </div>
                        </div>
                      ) : (
                        /* Button to trigger PR opening confirmation modal */
                        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-purple-950/20 border border-purple-500/30">
                          <div className="space-y-0.5">
                            <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
                              <GitPullRequest className="w-4 h-4 text-purple-400" />
                              <span>Ready to Open GitHub Pull Request</span>
                            </h4>
                            <p className="text-[11px] text-slate-400">
                              Create branch <code className="text-purple-300 font-mono">ai-review-fix/...</code> and open a PR against {githubContext.baseBranch || 'main'}
                            </p>
                          </div>

                          <button
                            onClick={() => setIsPrModalOpen(true)}
                            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold shadow-lg shadow-purple-600/25 transition"
                          >
                            <GitPullRequest className="w-4 h-4" />
                            <span>Open PR with this fix</span>
                          </button>
                        </div>
                      )}

                      {prError && (
                        <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/50 flex items-start gap-2 text-rose-300 text-xs">
                          <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                          <div>
                            <p className="font-semibold text-rose-200">GitHub PR Creation Failed</p>
                            <p className="text-rose-300/90">{prError}</p>
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    /* Unverified Fix notice */
                    <div className="p-3 rounded-lg bg-amber-950/20 border border-amber-800/40 flex items-center gap-2 text-amber-300 text-xs">
                      <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                      <span>Fix attempted, verification failed. Pull Request creation is disabled for unverified fixes.</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* PR Confirmation Modal */}
      {isPrModalOpen && githubContext && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-purple-500/40 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 animate-scaleUp">
            <div className="flex items-center gap-2.5 text-purple-400 border-b border-slate-800 pb-3">
              <GitPullRequest className="w-5 h-5" />
              <h3 className="text-base font-bold text-white">Confirm &amp; Open GitHub Pull Request</h3>
            </div>

            <div className="space-y-3 text-xs text-slate-300">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 font-mono text-[11px]">
                <div><span className="text-slate-500">Repository:</span> <strong className="text-white">{githubContext.owner}/{githubContext.repo}</strong></div>
                <div><span className="text-slate-500">File Path:</span> <span className="text-purple-300">{githubContext.filePath || filename}</span></div>
                <div><span className="text-slate-500">Base Branch:</span> <span className="text-slate-300">{githubContext.baseBranch || 'main'}</span></div>
                <div>
                  <span className="text-slate-500">Verification Proof:</span>{' '}
                  <span className="text-emerald-300 font-semibold">
                    {finalResult?.test_type === 'pre_existing' ? 'Pre-Existing Test Suite' : 'Autonomous Smoke Test Suite'}
                  </span>
                </div>
              </div>

              <div>
                <label className="text-slate-400 font-semibold block mb-1">GitHub Personal Access Token (PAT)</label>
                <input
                  type="password"
                  value={githubToken}
                  onChange={(e) => handleSaveToken(e.target.value)}
                  placeholder="ghp_... or github_pat_..."
                  className="w-full bg-slate-950 border border-slate-700 text-slate-200 px-3 py-2 rounded-lg text-xs font-mono focus:outline-none focus:border-purple-500"
                />
                <span className="text-[10px] text-slate-500">Token must have 'repo' or 'contents:write' and 'pull_requests:write' scope.</span>
              </div>

              <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-800/30 text-[11px] text-amber-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                <span>
                  This pushes a commit to a new branch and opens a Pull Request. <strong>Auto-merging is strictly disabled</strong>; human review is required.
                </span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800">
              <button
                onClick={() => setIsPrModalOpen(false)}
                disabled={isOpeningPr}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
              >
                Cancel
              </button>
              <button
                onClick={handleOpenPR}
                disabled={isOpeningPr || !githubToken.trim()}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-bold shadow-lg shadow-purple-600/25 transition disabled:shadow-none"
              >
                {isOpeningPr ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Opening PR on GitHub...</span>
                  </>
                ) : (
                  <>
                    <GitPullRequest className="w-4 h-4" />
                    <span>Confirm &amp; Open Pull Request</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
