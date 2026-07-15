export type ApiStatus = 'idle' | 'loading' | 'success' | 'error';
export type Sentiment = 'positive' | 'neutral' | 'negative';

export type InteractionPayload = {
  hcp_name: string;
  interaction_type: string;
  occurred_at: string;
  attendees: string[];
  topics_discussed: string;
  sentiment: Sentiment;
  outcomes: string;
  materials: Array<{ name: string; quantity: number }>;
  samples: Array<{ name: string; quantity: number }>;
  follow_ups: Array<{ task: string }>;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? 'Unable to reach the backend.');
  }
  return response.json() as Promise<T>;
}

export function createInteraction(payload: InteractionPayload) {
  return request<{ id: string }>('/interactions', { method: 'POST', body: JSON.stringify(payload) });
}

export type FormContext = {
  hcp_name?: string;
  interaction_type?: string;
  topics_discussed?: string;
  sentiment?: string;
  outcomes?: string;
};

export function getAssistantDraft(message: string, interactionId?: string | null, formContext?: FormContext) {
  return request<{ message: string; draft: { hcp_name: string; interaction_type: string; occurred_at: string; topics_discussed: string; sentiment: Sentiment; follow_up_suggestions: string[]; attendees?: string[]; outcomes?: string; materials?: string[]; samples?: string[]; follow_ups?: string[] } }>('/assistant/log', { 
    method: 'POST', 
    body: JSON.stringify({ 
      message, 
      interaction_id: interactionId,
      ...formContext
    }) 
  });
}
