import React, { useState } from 'react';
import { 
  Code2, 
  Bot, 
  GitPullRequest, 
  Database, 
  ShieldCheck
} from 'lucide-react';
import SingleFileReview from './components/SingleFileReview';
import AgentLoopView from './components/AgentLoopView';
import GitHubReviewView from './components/GitHubReviewView';
import WholeRepoRAGView from './components/WholeRepoRAGView';
import BenchmarkView from './components/BenchmarkView';

const VALID_GROQ_MODELS = ['openai/gpt-oss-120b', 'llama-3.1-8b-instant', 'llama-3.3-70b-versatile', 'mixtral-8x7b-32768'];
const DEFAULT_GROQ_MODEL = 'openai/gpt-oss-120b';

const getSafeGroqModel = () => {
  const stored = localStorage.getItem('groq_model');
  if (stored && VALID_GROQ_MODELS.includes(stored)) return stored;
  localStorage.setItem('groq_model', DEFAULT_GROQ_MODEL);
  return DEFAULT_GROQ_MODEL;
};

export default function App() {
  const [activeTab, setActiveTab] = useState('single-file');

  // LLM Config state from localStorage
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('groq_api_key') || '');
  const [model, setModel] = useState(() => getSafeGroqModel());

  // Cross-tab transfer payload for Phase 2 Agent Loop
  const [agentPayload, setAgentPayload] = useState(null);

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

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-900/50 py-4 text-center text-xs text-slate-500">
        AI Code Reviewer &amp; Bug Fixing Agent &bull; Powered by Groq, Isolated Sandboxes, GitHub API &amp; ChromaDB RAG
      </footer>
    </div>
  );
}
