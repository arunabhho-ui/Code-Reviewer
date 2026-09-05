import React, { useState, useEffect } from 'react';
import { X, Key, Cpu, ShieldCheck, Check } from 'lucide-react';

export default function ApiConfigModal({
  isOpen,
  onClose,
  apiKey,
  setApiKey,
  model,
  setModel,
}) {
  const [tempKey, setTempKey] = useState(apiKey || '');
  const [tempModel, setTempModel] = useState(model || 'llama-3.1-8b-instant');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setTempKey(apiKey || '');
    setTempModel(model || 'llama-3.1-8b-instant');
  }, [apiKey, model, isOpen]);

  if (!isOpen) return null;

  const handleSave = () => {
    setApiKey(tempKey.trim());
    setModel(tempModel);
    localStorage.setItem('groq_api_key', tempKey.trim());
    localStorage.setItem('groq_model', tempModel);
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 800);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden space-y-4 p-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <Key className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">LLM Configuration</h3>
              <p className="text-xs text-slate-400">Configure Groq Cloud API</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <div className="space-y-4 text-xs">
          {/* API Key */}
          <div className="space-y-1.5">
            <label className="font-semibold text-slate-300 flex items-center gap-1.5">
              <span>Groq API Key</span>
              <span className="text-[10px] text-slate-500">(xai-...)</span>
            </label>
            <input
              type="password"
              value={tempKey}
              onChange={(e) => setTempKey(e.target.value)}
              placeholder="Leave empty to use server .env key"
              className="w-full bg-slate-950 border border-slate-700 text-slate-200 px-3 py-2 rounded-lg focus:outline-none focus:border-sky-500 font-mono"
            />
            <p className="text-[11px] text-slate-400">
              Stored locally in your browser session. If left empty, uses server default.
            </p>
          </div>

          {/* Model selection */}
          <div className="space-y-1.5">
            <label className="font-semibold text-slate-300 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-sky-400" />
              <span>Groq Model</span>
            </label>
            <select
              value={tempModel}
              onChange={(e) => setTempModel(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-slate-200 px-3 py-2 rounded-lg focus:outline-none focus:border-sky-500 font-mono text-xs cursor-pointer"
            >
              <option value="openai/gpt-oss-120b">GPT-OSS 120B (Recommended)</option>
              <option value="llama-3.1-8b-instant">Llama 3.1 8B Instant</option>
              <option value="llama-3.3-70b-versatile">Llama 3.3 70B Versatile</option>
              <option value="mixtral-8x7b-32768">Mixtral 8x7B</option>
            </select>
          </div>

          {/* Privacy Note */}
          <div className="p-3 rounded-lg bg-sky-950/20 border border-sky-800/30 flex items-start gap-2.5 text-sky-300">
            <ShieldCheck className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <p className="text-[11px] leading-relaxed">
              Zero telemetry logged externally. Code review requests are processed via Groq function calling and deterministic linters.
            </p>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold transition shadow-md"
          >
            {saved ? <Check className="w-4 h-4" /> : null}
            <span>{saved ? 'Saved!' : 'Save Settings'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
