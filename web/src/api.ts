import type {
  Health,
  Job,
  JobInput,
  JobRun,
  OrchestratorState,
  Process,
  ProcessInput,
} from './types'

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: options.body
      ? { 'Content-Type': 'application/json', ...options.headers }
      : options.headers,
  })

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    try {
      const body = await response.json() as { detail?: string | object }
      message = typeof body.detail === 'string'
        ? body.detail
        : JSON.stringify(body.detail ?? body)
    } catch {
      // The fallback message already contains the useful status.
    }
    throw new ApiError(message, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export const api = {
  health: (signal?: AbortSignal) =>
    request<Health>('/api/health', { signal }),
  orchestrator: (signal?: AbortSignal) =>
    request<OrchestratorState>('/api/orchestrator', { signal }),
  setOrchestrator: (action: 'start' | 'pause' | 'stop') =>
    request<OrchestratorState>(`/api/orchestrator/${action}`, {
      method: 'POST',
    }),
  processes: (signal?: AbortSignal) =>
    request<Process[]>('/api/processes', { signal }),
  createProcess: (input: ProcessInput) =>
    request<Process>('/api/processes', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  updateProcess: (processId: string, input: Partial<ProcessInput>) =>
    request<Process>(`/api/processes/${processId}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    }),
  setProcessEnabled: (processId: string, enabled: boolean) =>
    request<Process>(
      `/api/processes/${processId}/${enabled ? 'enable' : 'disable'}`,
      { method: 'POST' },
    ),
  deleteProcess: (processId: string) =>
    request<void>(`/api/processes/${processId}`, { method: 'DELETE' }),
  jobs: (signal?: AbortSignal) =>
    request<Job[]>('/api/jobs', { signal }),
  createJob: (input: JobInput) =>
    request<Job>('/api/jobs', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  updateJob: (jobId: string, input: { active: boolean }) =>
    request<Job>(`/api/jobs/${jobId}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    }),
  runJobNow: (jobId: string) =>
    request<Job>(`/api/jobs/${jobId}/run-now`, { method: 'POST' }),
  deleteJob: (jobId: string) =>
    request<void>(`/api/jobs/${jobId}`, { method: 'DELETE' }),
  runs: (signal?: AbortSignal) =>
    request<JobRun[]>('/api/runs?limit=100', { signal }),
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}
