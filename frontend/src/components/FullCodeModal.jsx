import React, { useState } from 'react';
import { X, Check, Copy, Sparkles, FileCode, ArrowRight } from 'lucide-react';
import DiffViewer from './DiffViewer';
import { openGitHubPR } from '../services/api';

export default function FullCodeModal({
  isOpen,
  onClose,
  originalCode,
  fixedCode,
  filename,
  language,
  githubContext,
  selectedFile,
  githubToken,
  onApplySuccess,
}) {
  const [applying, setApplying] = useState(false);

  const handleApplyChange = async () => {
    if (!githubContext || !selectedFile) return;
    setApplying(true);
    const payload = {
      owner: githubContext.owner,
      repo: githubContext.repo,
      base_branch: githubContext.branch,
      file_path: selectedFile.path,
      fixed_code: fixedCode,
      fix_summary: `Automated fix for ${filename}`,
      finding_details: githubContext.finding || {},
      test_verification_type: 'smoke_test',
      github_token: githubToken,
    };
    const resp = await openGitHubPR(payload);
    setApplying(false);
    if (resp.success) {
      alert(`✅ PR created: ${resp.data.pr_url}`);
      onApplySuccess?.();
    } else {
      alert(`⚠️ Failed to create PR: ${resp.error}`);
    }
  };

  // Existing copy handler remains unchanged

  if (!isOpen) return null;

  const handleCopyRepaired = () => {
    navigator.clipboard.writeText(fixedCode || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-5xl max-h-[90vh] bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Full Patched File: {filename}</h3>
              <p className="text-xs text-slate-400">All suggested fixes applied to whole file</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* View Switcher */}
            <div className="flex bg-slate-800 p-0.5 rounded-lg border border-slate-700 text-xs">
              <button
                onClick={() => setActiveView('diff')}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  activeView === 'diff' ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                Diff
              </button>
              <button
                onClick={() => setActiveView('repaired')}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  activeView === 'repaired' ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                Fixed Code
              </button>
              <button
                onClick={() => setActiveView('side-by-side')}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  activeView === 'side-by-side' ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                Side-by-Side
              </button>
            </div>

            <button
                onClick={handleCopyRepaired}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow transition"
              >
                {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied Full File' : 'Copy Fixed Code'}</span>
              </button>

            {/* Apply Change Button */}
            <button
                onClick={handleApplyChange}
                disabled={applying}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow transition ${applying ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
                {applying ? 'Applying…' : <><ArrowRight className="w-3.5 h-3.5" /> Apply Change</>}
            </button>

            <button
                onClick={onClose}
                className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
              >
                <X className="w-5 h-5" />
              </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 p-4 overflow-y-auto font-mono text-xs bg-slate-950">
          {activeView === 'diff' && (
            <DiffViewer
              original={originalCode}
              modified={fixedCode}
              diffText={undefined}
            />
          )}

          {activeView === 'repaired' && (
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-slate-200">
              <pre className="overflow-x-auto whitespace-pre leading-relaxed">{fixedCode}</pre>
            </div>
          )}

          {activeView === 'side-by-side' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-900/40">
                <h4 className="text-rose-400 font-semibold text-xs mb-2">Original Source ({originalCode.split('\n').length} lines)</h4>
                <pre className="text-rose-200 overflow-x-auto whitespace-pre leading-relaxed">{originalCode}</pre>
              </div>
              <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-900/40">
                <h4 className="text-emerald-400 font-semibold text-xs mb-2">Patched Source ({fixedCode?.split('\n').length || 0} lines)</h4>
                <pre className="text-emerald-200 overflow-x-auto whitespace-pre leading-relaxed">{fixedCode}</pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
