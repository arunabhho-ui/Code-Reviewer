import React, { useRef } from 'react';
import { 
  Upload, 
  Trash2, 
  Play, 
  Sparkles, 
  FileCode, 
  Settings2,
  CheckCircle2,
  FileText
} from 'lucide-react';
import { CODE_SAMPLES } from '../constants/samples';

export default function CodeEditor({
  code,
  setCode,
  language,
  setLanguage,
  filename,
  setFilename,
  onRunReview,
  loading,
  runStaticAnalysis,
  setRunStaticAnalysis,
}) {
  const fileInputRef = useRef(null);

  const handleSampleSelect = (sampleId) => {
    const sample = CODE_SAMPLES.find((s) => s.id === sampleId);
    if (sample) {
      setCode(sample.code);
      setLanguage(sample.language);
      setFilename(sample.filename);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFilename(file.name);
    if (file.name.endsWith('.py')) {
      setLanguage('python');
    } else if (file.name.endsWith('.js') || file.name.endsWith('.jsx')) {
      setLanguage('javascript');
    } else if (file.name.endsWith('.ts') || file.name.endsWith('.tsx')) {
      setLanguage('typescript');
    } else if (file.name.endsWith('.c') || file.name.endsWith('.h')) {
      setLanguage('c');
    } else if (file.name.endsWith('.java')) {
      setLanguage('java');
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      setCode(event.target?.result || '');
    };
    reader.readAsText(file);
  };

  const lineCount = code.split('\n').length;
  const charCount = code.length;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden shadow-lg flex flex-col">
      {/* Editor Controls Toolbar */}
      <div className="p-3.5 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
        {/* Left Toolbar Items: Language, Presets, Filename */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Language Selector */}
          <div className="flex items-center gap-1.5 bg-slate-800/90 border border-slate-700 px-2.5 py-1.5 rounded-lg">
            <FileCode className="w-4 h-4 text-sky-400" />
            <select
              value={language}
              onChange={(e) => {
                const lang = e.target.value;
                setLanguage(lang);
                if (lang === 'python' && !filename.endsWith('.py')) {
                  setFilename('snippet.py');
                } else if (lang === 'javascript' && !filename.endsWith('.js') && !filename.endsWith('.jsx')) {
                  setFilename('snippet.js');
                } else if (lang === 'typescript' && !filename.endsWith('.ts') && !filename.endsWith('.tsx')) {
                  setFilename('snippet.ts');
                } else if (lang === 'c' && !filename.endsWith('.c') && !filename.endsWith('.h')) {
                  setFilename('snippet.c');
                } else if (lang === 'java' && !filename.endsWith('.java')) {
                  setFilename('Snippet.java');
                }
              }}
              className="bg-transparent text-xs font-semibold text-white focus:outline-none cursor-pointer"
            >
              <option value="python" className="bg-slate-900 text-white">Python</option>
              <option value="javascript" className="bg-slate-900 text-white">JavaScript</option>
              <option value="typescript" className="bg-slate-900 text-white">TypeScript</option>
              <option value="c" className="bg-slate-900 text-white">C</option>
              <option value="java" className="bg-slate-900 text-white">Java</option>
            </select>
          </div>

          {/* Sample Preset Dropdown */}
          <select
            onChange={(e) => handleSampleSelect(e.target.value)}
            defaultValue=""
            className="bg-slate-800/90 border border-slate-700 text-xs text-slate-300 px-2.5 py-1.5 rounded-lg focus:outline-none cursor-pointer hover:border-slate-600"
          >
            <option value="" disabled>Load Buggy Preset Sample...</option>
            {CODE_SAMPLES.map((s) => (
              <option key={s.id} value={s.id} className="bg-slate-900 text-white">
                {s.label}
              </option>
            ))}
          </select>

          {/* Filename Input */}
          <input
            type="text"
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
            placeholder="filename.py"
            className="bg-slate-800/90 border border-slate-700 text-xs font-mono text-slate-300 px-2.5 py-1.5 rounded-lg focus:outline-none focus:border-sky-500 w-36 sm:w-44"
          />
        </div>

        {/* Right Toolbar Items: Upload, Clear */}
        <div className="flex items-center gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".py,.js,.jsx,.ts,.tsx,.c,.h,.java,.txt"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-750 border border-slate-700 rounded-lg transition"
            title="Upload source file"
          >
            <Upload className="w-3.5 h-3.5 text-sky-400" />
            <span className="hidden sm:inline">Upload File</span>
          </button>

          <button
            onClick={() => setCode('')}
            disabled={!code}
            className="p-1.5 text-slate-400 hover:text-rose-400 bg-slate-800 hover:bg-slate-750 border border-slate-700 rounded-lg transition disabled:opacity-40"
            title="Clear code"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Code Textarea Area with Line Numbers */}
      <div className="relative flex-1 min-h-[340px] flex bg-slate-950 font-mono text-xs">
        {/* Line Numbers column */}
        <div className="w-12 py-3 bg-slate-900/40 text-slate-600 select-none text-right pr-3 font-mono border-r border-slate-800/80">
          {Array.from({ length: Math.max(12, lineCount) }).map((_, i) => (
            <div key={i} className="leading-6">{i + 1}</div>
          ))}
        </div>

        {/* Textarea */}
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder={`// Paste your ${language} code snippet here or load a preset sample...`}
          spellCheck={false}
          className="flex-1 p-3 bg-transparent text-slate-200 resize-y focus:outline-none font-mono text-xs leading-6 selection:bg-sky-500/30 min-h-[340px]"
        />
      </div>

      {/* Bottom Footer: Stats, Linter Switch, Submit Action */}
      <div className="p-3.5 bg-slate-900 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-4 text-xs text-slate-400 font-mono">
          <span>{lineCount} lines</span>
          <span>{charCount} chars</span>
          <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 select-none">
            <input
              type="checkbox"
              checked={runStaticAnalysis}
              onChange={(e) => setRunStaticAnalysis(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-sky-500 focus:ring-0"
            />
            <span className="text-xs">Pre-pass Static Linter</span>
          </label>
        </div>

        <button
          onClick={onRunReview}
          disabled={loading || !code.trim()}
          className="flex items-center gap-2 px-5 py-2 rounded-lg bg-sky-500 hover:bg-sky-600 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-semibold shadow-lg shadow-sky-500/20 transition disabled:shadow-none"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Analyzing Code...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Run Code Review</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
