import React from 'react';
import { Check, Copy } from 'lucide-react';

export default function DiffViewer({ original, modified, diffText, title }) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(modified || diffText || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // If diffText is provided in unified diff format:
  if (diffText) {
    const lines = diffText.split('\n');
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-950 font-mono text-xs overflow-hidden">
        {title && (
          <div className="px-3 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
            <span className="text-slate-300 font-semibold text-[11px]">{title}</span>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 transition"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              <span>{copied ? 'Copied' : 'Copy Fix'}</span>
            </button>
          </div>
        )}
        <div className="p-2.5 overflow-x-auto space-y-0.5">
          {lines.map((line, idx) => {
            let lineClass = 'text-slate-400';
            let bgClass = '';
            if (line.startsWith('+') && !line.startsWith('+++')) {
              lineClass = 'text-emerald-300 font-medium';
              bgClass = 'bg-emerald-950/40 border-l-2 border-emerald-500 pl-1.5';
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              lineClass = 'text-rose-300 font-medium line-through opacity-80';
              bgClass = 'bg-rose-950/40 border-l-2 border-rose-500 pl-1.5';
            } else if (line.startsWith('@@')) {
              lineClass = 'text-sky-400 font-bold';
              bgClass = 'bg-sky-950/20 py-0.5';
            }
            return (
              <div key={idx} className={`leading-relaxed whitespace-pre font-mono ${lineClass} ${bgClass}`}>
                {line || ' '}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Side-by-side fallback for original vs suggested snippet
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono">
      <div className="p-3 rounded-lg bg-rose-950/20 border border-rose-900/30">
        <div className="text-[11px] font-semibold text-rose-400 mb-1.5 flex items-center justify-between">
          <span>Original Code</span>
          <span className="text-rose-500/80 text-[10px]">BEFORE</span>
        </div>
        <pre className="text-rose-200 overflow-x-auto whitespace-pre-wrap">{original || '// No snippet'}</pre>
      </div>

      <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-900/30">
        <div className="text-[11px] font-semibold text-emerald-400 mb-1.5 flex items-center justify-between">
          <span>Suggested Fix</span>
          <div className="flex items-center gap-2">
            <span className="text-emerald-500/80 text-[10px]">AFTER</span>
            <button
              onClick={handleCopy}
              className="text-[10px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
            >
              {copied ? <Check className="w-2.5 h-2.5" /> : <Copy className="w-2.5 h-2.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
        <pre className="text-emerald-200 overflow-x-auto whitespace-pre-wrap">{modified || '// No snippet'}</pre>
      </div>
    </div>
  );
}
