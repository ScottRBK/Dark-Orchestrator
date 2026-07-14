export type ProcessType = 'bash' | 'python'

export interface InlineProcessSource {
  kind: 'inline'
  content: string
}

export interface FileProcessSource {
  kind: 'file'
  path: string
}

export type ProcessSource = InlineProcessSource | FileProcessSource

export interface Process {
  process_id: string
  type: ProcessType
  name: string
  source: ProcessSource
  enabled: boolean
  created_at: string
  created_by: string
  modified_at: string
  modified_by: string
  last_run_at: string | null
}

export interface Job {
  job_id: string
  process: Process
  recurring: boolean
  cron: string | null
  last_run_at: string | null
  next_run_at: string | null
  created_at: string
  created_by: string
  modified_at: string
  modified_by: string
  active: boolean
}

export type RunStatus = 'pending' | 'active' | 'completed' | 'error'

export interface JobRun {
  job_run_id: string
  job: Job
  status: RunStatus
  captured_output: string
  started_at: string | null
  finished_at: string | null
  exception: string | null
}

export type OrchestratorStatus =
  | 'initialised'
  | 'starting'
  | 'running'
  | 'paused'
  | 'stopping'
  | 'stopped'

export interface OrchestratorState {
  status: OrchestratorStatus
}

export interface Health extends OrchestratorState {
  service: string
  database: 'up' | 'down'
}

export interface ProcessInput {
  name: string
  type: ProcessType
  source: ProcessSource
}

export interface JobInput {
  process_id: string
  recurring?: boolean
  cron?: string
  next_run_at?: string
}
