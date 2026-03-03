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

// --- Informatica Migration Advanced ---

export async function migrateInformaticaAdvanced(xmlContent: string, filename: string) {
  return fetchAPI<import('./types').InformaticaAdvancedMigrationResponse>('/api/agents/informatica-migration/migrate-advanced', {
    method: 'POST',
    body: JSON.stringify({ xml_content: xmlContent, filename }),
  });
}

// --- NL to DAG ---

export async function generateDAG(description: string) {
  return fetchAPI<import('./types').NLToDAGResponse>('/api/agents/nl-to-dag/generate', {
    method: 'POST',
    body: JSON.stringify({ description }),
  });
}
