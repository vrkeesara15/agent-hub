const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function searchTables(query: string) {
  return fetchAPI<import('./types').SearchResponse>('/api/agents/source-of-truth/search', {
    method: 'POST',
    body: JSON.stringify({ query }),
  });
}

export async function convertCode(mode: string, inputCode: string) {
  return fetchAPI<import('./types').ConvertResponse>('/api/agents/code-accelerator/convert', {
    method: 'POST',
    body: JSON.stringify({ mode, input_code: inputCode }),
  });
}

export async function scanCode(fileContent: string, filename: string) {
  return fetchAPI<import('./types').ScanResponse>('/api/agents/data-triage/scan', {
    method: 'POST',
    body: JSON.stringify({ file_content: fileContent, filename }),
  });
}

export async function fixTable(table: string, originalCode: string) {
  return fetchAPI<import('./types').FixResponse>('/api/agents/data-triage/fix', {
    method: 'POST',
    body: JSON.stringify({ table, original_code: originalCode }),
  });
}

export async function getAgents() {
  return fetchAPI<import('./types').AgentInfo[]>('/api/agents');
}

export async function getActivity() {
  return fetchAPI<import('./types').ActivityItem[]>('/api/activity');
}

export async function getHealth() {
  return fetchAPI<{ status: string }>('/api/health');
}

export async function getNotifications() {
  return fetchAPI<import('./types').NotificationItem[]>('/api/notifications');
}

export async function markNotificationRead(id: string) {
  return fetchAPI<{ success: boolean }>(`/api/notifications/${id}/read`, {
    method: 'POST',
  });
}

export async function markAllNotificationsRead() {
  return fetchAPI<{ success: boolean }>('/api/notifications/read-all', {
    method: 'POST',
  });
}

// --- Chat endpoints ---

export async function chatSourceOfTruth(message: string, history: { role: string; content: string }[]) {
  return fetchAPI<import('./types').ChatResponse>('/api/agents/source-of-truth/chat', {
    method: 'POST',
    body: JSON.stringify({ message, history }),
  });
}

export async function chatDataTriage(message: string, history: { role: string; content: string }[]) {
  return fetchAPI<import('./types').ChatResponse>('/api/agents/data-triage/chat', {
    method: 'POST',
    body: JSON.stringify({ message, history }),
  });
}

// --- SQL Optimizer ---

export async function optimizeSQL(inputCode: string) {
  return fetchAPI<import('./types').OptimizeResponse>('/api/agents/code-accelerator/optimize', {
    method: 'POST',
    body: JSON.stringify({ input_code: inputCode }),
  });
}

// --- Informatica Migration ---

export async function migrateInformatica(xmlContent: string, filename: string) {
  return fetchAPI<import('./types').InformaticaMigrationResponse>('/api/agents/informatica-migration/migrate', {
    method: 'POST',
    body: JSON.stringify({ xml_content: xmlContent, filename }),
  });
}

// --- Informatica Migration Advanced (polling) ---

export async function migrateInformaticaAdvanced(
  xmlContent: string,
  filename: string,
  onProgress?: (message: string, current: number, total: number) => void,
) {
  // Step 1: Start the job — returns immediately with a job ID
  const startRes = await fetchAPI<{ job_id: string; status: string }>(
    '/api/agents/informatica-migration/migrate-advanced',
    {
      method: 'POST',
      body: JSON.stringify({ xml_content: xmlContent, filename }),
    },
  );

  const jobId = startRes.job_id;

  // Step 2: Poll for progress/result every 3 seconds
  const POLL_INTERVAL = 3000;
  const MAX_POLL_TIME = 45 * 60 * 1000; // 45 min safety net
  const startTime = Date.now();

  while (Date.now() - startTime < MAX_POLL_TIME) {
    await new Promise((r) => setTimeout(r, POLL_INTERVAL));

    const status = await fetchAPI<{
      status: string;
      progress_message?: string;
      progress_current?: number;
      progress_total?: number;
      result?: import('./types').InformaticaAdvancedMigrationResponse;
      error?: string;
    }>(`/api/agents/informatica-migration/migrate-advanced/${jobId}`);

    if (status.status === 'running') {
      if (onProgress && status.progress_message) {
        onProgress(
          status.progress_message,
          status.progress_current ?? 0,
          status.progress_total ?? 0,
        );
      }
      continue;
    }

    if (status.status === 'done' && status.result) {
      return status.result;
    }

    if (status.status === 'error') {
      return { error: status.error || 'Migration failed' } as import('./types').InformaticaAdvancedMigrationResponse;
    }

    // not_found or unexpected status
    return { error: `Unexpected job status: ${status.status}` } as import('./types').InformaticaAdvancedMigrationResponse;
  }

  return { error: 'Migration timed out after 45 minutes' } as import('./types').InformaticaAdvancedMigrationResponse;
}

// --- NL to DAG ---

export async function generateDAG(description: string) {
  return fetchAPI<import('./types').NLToDAGResponse>('/api/agents/nl-to-dag/generate', {
    method: 'POST',
    body: JSON.stringify({ description }),
  });
}

// --- Message Code Builder ---

export async function generateMessageCodeERules(
  requirements: import('./types').MessageCodeRequirements,
) {
  return fetchAPI<import('./types').ERuleResponse>(
    '/api/agents/message-code-builder/erules',
    {
      method: 'POST',
      body: JSON.stringify(requirements),
    },
  );
}

export async function getMessageCodeDemoPresets() {
  return fetchAPI<{ presets: Record<string, Partial<import('./types').MessageCodeRequirements>> }>(
    '/api/agents/message-code-builder/demo-presets',
  );
}

export async function getMessageCodeTemplates() {
  return fetchAPI<{ templates: import('./types').MessageCodeTemplate[] }>(
    '/api/agents/message-code-builder/templates',
  );
}

export async function analyzeMessageCodeRequirements(
  requirements: import('./types').MessageCodeRequirements,
) {
  return fetchAPI<import('./types').MessageCodeAnalyzeResponse>(
    '/api/agents/message-code-builder/analyze',
    {
      method: 'POST',
      body: JSON.stringify(requirements),
    },
  );
}

export async function generateMessageCode(
  requirements: import('./types').MessageCodeRequirements,
  templateId?: string,
) {
  return fetchAPI<import('./types').MessageCodeGenerateResponse>(
    '/api/agents/message-code-builder/generate',
    {
      method: 'POST',
      body: JSON.stringify({ requirements, template_id: templateId }),
    },
  );
}

export async function generateMessageCodeDAG(
  requirements: import('./types').MessageCodeRequirements,
) {
  return fetchAPI<import('./types').MessageCodeDAGResponse>(
    '/api/agents/message-code-builder/dag',
    {
      method: 'POST',
      body: JSON.stringify(requirements),
    },
  );
}

export async function saveMessageCodeToKnowledge(data: {
  message_code: string;
  name: string;
  description: string;
  channel: string;
  category: string;
  owner: string;
  schedule: string;
  sql: string;
  logic_summary: string;
  tags: string[];
}) {
  return fetchAPI<import('./types').MessageCodeSaveResponse>(
    '/api/agents/message-code-builder/save',
    {
      method: 'POST',
      body: JSON.stringify(data),
    },
  );
}
