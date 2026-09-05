import React, { useRef, useEffect } from 'react';
import { Terminal as TerminalIcon, Trash2, Copy, Check } from 'lucide-react';

export default function AgentTerminal({ logs = [], isRunning }) {
  const terminalEndRef = useRef(null);
  const [copied, setCopied] = React.useState(false);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleCopyLogs = () => {
    const text = logs.map((l) => `[${l.timestamp || ''}] ${l.type?.toUpperCase() || 'LOG'}: ${l.text || l.message || ''}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 font-mono text-xs overflow-hidden shadow-xl flex flex-col h-[320px]">
      {/* Terminal Topbar */}
      <div className="px-3.5 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 mr-2">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
          </div>
          <TerminalIcon className="w-3.5 h-3.5 text-sky-400" />
          <span className="text-slate-300 font-semibold text-[11px]">Agent Sandbox Console</span>
          {isRunning && (
            <span className="flex items-center gap-1 text-[10px] text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded border border-sky-500/20 font-medium animate-pulse">
              Running
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopyLogs}
            disabled={logs.length === 0}
            className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 transition disabled:opacity-40"
          >
            {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* Terminal Log Stream Body */}
      <div className="flex-1 p-3 overflow-y-auto space-y-1.5 select-text text-slate-300 bg-slate-950">
        {logs.length === 0 ? (
          <div className="text-slate-600 italic">
            // Sandbox execution logs and agent reasoning will appear here in real-time...
          </div>
        ) : (
          logs.map((log, idx) => {
            let prefixColor = 'text-slate-500';
            let textColor = 'text-slate-300';
            let bgClass = '';

            if (log.type === 'error' || log.type === 'fail') {
              prefixColor = 'text-rose-500 font-bold';
              textColor = 'text-rose-300';
              bgClass = 'bg-rose-950/20 px-1 py-0.5 rounded';
            } else if (log.type === 'success' || log.type === 'pass') {
              prefixColor = 'text-emerald-400 font-bold';
              textColor = 'text-emerald-300 font-semibold';
              bgClass = 'bg-emerald-950/20 px-1 py-0.5 rounded';
            } else if (log.type === 'attempt') {
              prefixColor = 'text-sky-400 font-bold';
              textColor = 'text-sky-200';
            } else if (log.type === 'sandbox') {
              prefixColor = 'text-purple-400';
              textColor = 'text-slate-300';
            }

            return (
              <div key={idx} className={`leading-relaxed whitespace-pre-wrap ${bgClass}`}>
                <span className={`mr-2 select-none text-[10px] ${prefixColor}`}>
                  [{log.timestamp || 'LOG'}]
                </span>
                <span className={textColor}>{log.text || log.message}</span>
              </div>
            );
          })
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}
