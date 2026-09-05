import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Code2, 
  Bot, 
  GitPullRequest, 
  Database, 
  ShieldCheck, 
  Key,
  Layers,
  Sparkles
} from 'lucide-react';
import { checkHealth } from './services/api';
import SingleFileReview from './components/SingleFileReview';
import AgentLoopView from './components/AgentLoopView';
import GitHubReviewView from './components/GitHubReviewView';
import WholeRepoRAGView from './components/WholeRepoRAGView';
import BenchmarkView from './components/BenchmarkView';
import ApiConfigModal from './components/ApiConfigModal';

const VALID_GROQ_MODELS = ['openai/gpt-oss-120b', 'llama-3.1-8b-instant', 'llama-3.3-70b-versatile', 'mixtral-8x7b-32768'];
const DEFAULT_GROQ_MODEL = 'openai/gpt-oss-120b';

const getSafeGroqModel = () => {
  const stored = localStorage.getItem('groq_model');
  if (stored && VALID_GROQ_MODELS.includes(stored)) return stored;
  localStorage.setItem('groq_model', DEFAULT_GROQ_MODEL);
  return DEFAULT_GROQ_MODEL;
};

export default function App() {
  const [healthData, setHealthData] = useState(null);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [healthError, setHealthError] = useState(null);
  const [activeTab, setActiveTab] = useState('single-file');

  // LLM Config state from localStorage
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('groq_api_key') || '');
  const [model, setModel] = useState(() => getSafeGroqModel());
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);

  // Cross-tab transfer payload for Phase 2 Agent Loop
  const [agentPayload, setAgentPayload] = useState(null);

  const fetchHealth = async () => {
    setLoadingHealth(true);
    const result = await checkHealth();
    if (result.success) {
      setHealthData(result.data);
      setHealthError(null);
    } else {
      setHealthError(result.error);
      setHealthData(null);
    }
    setLoadingHealth(false);
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleNavigateToAgent = (payload) => {
    setAgentPayload(payload);
    setActiveTab('agent-loop');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="p-2 bg-sky-500/10 border border-sky-500/30 rounded-xl text-sky-400">
              <Code2 className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-base sm:text-lg text-white tracking-tight">AI Code Reviewer</h1>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">
                Autonomous Bug Fixing & Verification Agent &bull; Static Linters, Groq AI, Sandboxes & Chroma RAG
              </p>
            </div>
          </div>

          {/* Right Action Items */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* LLM Key / Model Config Button */}
            <button
              onClick={() => setIsConfigModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 border border-slate-700 text-xs text-slate-300 hover:text-white transition"
              title="Configure Groq API Key"
            >
              <Key className="w-3.5 h-3.5 text-sky-400" />
              <span className="hidden sm:inline">API Config</span>
              {apiKey && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />}
            </button>

            {/* Health Status Indicator */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/90 border border-slate-700 text-xs">
              <div className={`w-2 h-2 rounded-full ${healthData ? 'bg-emerald-400 animate-pulse' : healthError ? 'bg-rose-500' : 'bg-amber-400'}`} />
              <span className="text-slate-300 font-medium hidden sm:inline">
                {healthData ? 'Backend Live' : 'Backend Offline'}
              </span>
            </div>

            <button
              onClick={fetchHealth}
              disabled={loadingHealth}
              className="p-1.5 text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-755 border border-slate-700 rounded-lg transition disabled:opacity-50"
              title="Refresh Health"
            >
              <RefreshCw className={`w-4 h-4 ${loadingHealth ? 'animate-spin text-sky-400' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="border-b border-slate-800 bg-slate-900/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-2 py-2 overflow-x-auto">
            {[
              { id: 'single-file', label: 'Single-File Review', icon: Code2 },
              { id: 'agent-loop', label: 'Sandbox Fix Agent', icon: Bot },
              { id: 'github', label: 'GitHub PR Mode', icon: GitPullRequest },
              { id: 'rag-mode', label: 'Whole-Repo RAG', icon: Database },
              { id: 'benchmarks', label: 'Benchmarks', icon: ShieldCheck },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition whitespace-nowrap ${
                    isActive
                      ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Main Workspace */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'single-file' && (
          <SingleFileReview
            apiKey={apiKey}
            model={model}
            onNavigateToAgent={handleNavigateToAgent}
          />
        )}

        {activeTab === 'agent-loop' && (
          <AgentLoopView
            apiKey={apiKey}
            model={model}
            initialPayload={agentPayload}
          />
        )}

        {activeTab === 'github' && (
          <GitHubReviewView
            apiKey={apiKey}
            model={model}
            onNavigateToAgent={handleNavigateToAgent}
          />
        )}

        {activeTab === 'rag-mode' && (
          <WholeRepoRAGView
            apiKey={apiKey}
            model={model}
            onNavigateToAgent={handleNavigateToAgent}
          />
        )}

        {activeTab === 'benchmarks' && (
          <BenchmarkView
            apiKey={apiKey}
            onNavigateToAgent={handleNavigateToAgent}
          />
        )}
      </main>

      {/* API Config Modal */}
      <ApiConfigModal
        isOpen={isConfigModalOpen}
        onClose={() => setIsConfigModalOpen(false)}
        apiKey={apiKey}
        setApiKey={setApiKey}
        model={model}
        setModel={setModel}
      />

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-900/50 py-4 text-center text-xs text-slate-500">
        AI Code Reviewer &amp; Bug Fixing Agent &bull; Powered by Groq, Isolated Sandboxes, GitHub API &amp; ChromaDB RAG
      </footer>
    </div>
  );
}
