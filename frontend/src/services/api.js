import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const checkHealth = async () => {
  try {
    const response = await api.get('/health');
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to connect to backend',
    };
  }
};

export const submitCodeReview = async ({
  code,
  language,
  filename,
  apiKey,
  model,
  runStaticAnalysis = true,
  runSecurityPass = false,
}) => {
  try {
    const response = await api.post('/api/review', {
      code,
      language,
      filename,
      api_key: apiKey || undefined,
      model: model || undefined,
      run_static_analysis: runStaticAnalysis,
      run_security_pass: runSecurityPass,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to perform code review',
    };
  }
};

export const inspectGitHubTarget = async (url, githubToken) => {
  try {
    const response = await api.post('/api/github/inspect', {
      url,
      github_token: githubToken || undefined,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to inspect GitHub target',
    };
  }
};

export const fetchGitHubFile = async ({
  owner,
  repo,
  path,
  ref,
  githubToken,
}) => {
  try {
    const response = await api.post('/api/github/fetch-file', {
      owner,
      repo,
      path,
      ref,
      github_token: githubToken || undefined,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to fetch GitHub file',
    };
  }
};

export const indexRepoRAG = async (repoName, files) => {
  try {
    const response = await api.post('/api/rag/index', {
      repo_name: repoName,
      files,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to index repository into ChromaDB',
    };
  }
};

export const queryRepoRAG = async ({
  repoName,
  targetFilePath,
  code,
  language,
  topK = 4,
}) => {
  try {
    const response = await api.post('/api/rag/query', {
      repo_name: repoName,
      target_file_path: targetFilePath,
      code,
      language,
      top_k: topK,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to query RAG context',
    };
  }
};

export const reviewWithRAG = async ({
  repoName,
  targetFilePath,
  code,
  language,
  apiKey,
  model,
  runStaticAnalysis = true,
  runSecurityPass = true,
  topKContext = 4,
}) => {
  try {
    const response = await api.post('/api/rag/review', {
      repo_name: repoName,
      target_file_path: targetFilePath,
      code,
      language,
      api_key: apiKey || undefined,
      model: model || undefined,
      run_static_analysis: runStaticAnalysis,
      run_security_pass: runSecurityPass,
      top_k_context: topKContext,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to run cross-file RAG review',
    };
  }
};

export const openGitHubPR = async ({
  owner,
  repo,
  baseBranch,
  filePath,
  fixedCode,
  fixSummary,
  findingDetails,
  testVerificationType = 'smoke_test',
  githubToken,
}) => {
  try {
    const response = await api.post('/api/github/open-pr', {
      owner,
      repo,
      base_branch: baseBranch || undefined,
      file_path: filePath,
      fixed_code: fixedCode,
      fix_summary: fixSummary || undefined,
      finding_details: findingDetails || {},
      test_verification_type: testVerificationType,
      github_token: githubToken,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to open GitHub Pull Request',
    };
  }
};

export const fetchBenchmarkList = async () => {
  try {
    const response = await api.get('/api/benchmarks/list');
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to list benchmarks',
    };
  }
};

export const runBenchmarkExecution = async (benchmarkId = null, apiKey = null) => {
  try {
    const response = await api.post('/api/benchmarks/run', {
      benchmark_id: benchmarkId || undefined,
      api_key: apiKey || undefined,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Failed to run benchmarks',
    };
  }
};

export const streamAgentFix = async ({
  code,
  language,
  filename,
  bugDescription,
  testCode,
  apiKey,
  model,
  maxRetries = 3,
  onEvent,
  onError,
  onFinish,
  signal,
}) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/agent/fix/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code,
        language,
        filename,
        bug_description: bugDescription,
        test_code: testCode || undefined,
        api_key: apiKey || undefined,
        model: model || undefined,
        max_retries: maxRetries,
      }),
      signal,
    });

    if (!response.ok) {
      const errText = await response.text();
      let errorMsg = `Server error ${response.status}`;
      try {
        const errJson = JSON.parse(errText);
        errorMsg = errJson.detail || errorMsg;
      } catch (e) {
        errorMsg = errText || errorMsg;
      }
      onError?.(errorMsg);
      onFinish?.();
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const block of lines) {
        if (!block.trim()) continue;

        let eventType = 'message';
        let eventData = null;

        const eventLines = block.split('\n');
        for (const line of eventLines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            try {
              eventData = JSON.parse(line.slice(6));
            } catch (e) {
              eventData = line.slice(6);
            }
          }
        }

        if (eventData !== null) {
          onEvent?.(eventType, eventData);
        }
      }
    }

    onFinish?.();
  } catch (err) {
    if (err.name !== 'AbortError') {
      onError?.(err.message || 'Stream connection error');
    }
    onFinish?.();
  }
};
