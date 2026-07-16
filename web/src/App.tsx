import {
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

import { api, errorMessage } from './api'
import { Icon } from './Icon'
import type {
  Health,
  Job,
  JobInput,
  JobRun,
  Process,
  ProcessInput,
  RunStatus,
} from './types'

type View = 'overview' | 'processes' | 'schedules' | 'activity'
type JobMode = 'immediate' | 'scheduled' | 'recurring'

interface DashboardData {
  health: Health | null
  processes: Process[]
  jobs: Job[]
  runs: JobRun[]
}

const initialData: DashboardData = {
  health: null,
  processes: [],
  jobs: [],
  runs: [],
}

const navigation: Array<{
  id: View
  label: string
  icon: 'grid' | 'workflow' | 'calendar' | 'activity'
}> = [
  { id: 'overview', label: 'Overview', icon: 'grid' },
  { id: 'processes', label: 'Processes', icon: 'workflow' },
  { id: 'schedules', label: 'Schedules', icon: 'calendar' },
  { id: 'activity', label: 'Activity', icon: 'activity' },
]

const viewCopy: Record<View, { eyebrow: string; title: string; description: string }> = {
  overview: {
    eyebrow: 'Mission control',
    title: 'The business, in motion.',
    description: 'Schedule, observe, and steer every autonomous operation.',
  },
  processes: {
    eyebrow: 'Process library',
    title: 'Your operational building blocks.',
    description: 'Scripts and agents ready to become scheduled work.',
  },
  schedules: {
    eyebrow: 'Job schedules',
    title: 'Put the work on autopilot.',
    description: 'Control one-off and recurring execution from one timeline.',
  },
  activity: {
    eyebrow: 'Run history',
    title: 'Every signal. Nothing hidden.',
    description: 'Inspect output, timing, and failures across all operations.',
  },
}

function App() {
  const [data, setData] = useState<DashboardData>(initialData)
  const [view, setView] = useState<View>('overview')
  const [initialLoading, setInitialLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [processDialog, setProcessDialog] = useState<Process | 'new' | null>(null)
  const [jobProcess, setJobProcess] = useState<Process | null>(null)
  const [selectedRun, setSelectedRun] = useState<JobRun | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const loadDashboard = useCallback(async (signal?: AbortSignal) => {
    const [health, processes, jobs, runs] = await Promise.all([
      api.health(signal),
      api.processes(signal),
      api.jobs(signal),
      api.runs(signal),
    ])
    setData({ health, processes, jobs, runs })
    setLastUpdated(new Date())
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    let requestActive = false

    async function refresh() {
      if (requestActive) return
      requestActive = true
      try {
        await loadDashboard(controller.signal)
      } catch (refreshError) {
        if (!controller.signal.aborted) {
          setError(errorMessage(refreshError))
        }
      } finally {
        requestActive = false
        setInitialLoading(false)
      }
    }

    void refresh()
    const interval = window.setInterval(refresh, 750)
    return () => {
      controller.abort()
      window.clearInterval(interval)
    }
  }, [loadDashboard])

  async function perform(action: () => Promise<unknown>): Promise<boolean> {
    setBusy(true)
    setError(null)
    try {
      await action()
      await loadDashboard()
      return true
    } catch (actionError) {
      setError(errorMessage(actionError))
      return false
    } finally {
      setBusy(false)
    }
  }

  async function saveProcess(input: ProcessInput): Promise<void> {
    const current = processDialog
    const succeeded = await perform(() => {
      if (current === 'new' || current === null) {
        return api.createProcess(input)
      }
      return api.updateProcess(current.process_id, input)
    })
    if (succeeded) setProcessDialog(null)
  }

  async function createJob(input: JobInput): Promise<void> {
    const succeeded = await perform(() => api.createJob(input))
    if (succeeded) setJobProcess(null)
  }

  const completedRuns = data.runs.filter((run) => run.status === 'completed')
  const failedRuns = data.runs.filter((run) => run.status === 'error')
  const terminalRuns = completedRuns.length + failedRuns.length
  const successRate = terminalRuns
    ? Math.round((completedRuns.length / terminalRuns) * 100)
    : 100

  const metrics = useMemo(() => [
    {
      label: 'Enabled processes',
      value: data.processes.filter((process) => process.enabled).length,
      detail: `${data.processes.length} total`,
      icon: 'workflow' as const,
      tone: 'violet',
    },
    {
      label: 'Active schedules',
      value: data.jobs.filter((job) => job.active).length,
      detail: `${data.jobs.length} configured`,
      icon: 'calendar' as const,
      tone: 'blue',
    },
    {
      label: 'Successful runs',
      value: `${successRate}%`,
      detail: `${terminalRuns} completed`,
      icon: 'check' as const,
      tone: 'green',
    },
    {
      label: 'Runs recorded',
      value: data.runs.length,
      detail: failedRuns.length ? `${failedRuns.length} need attention` : 'No failures',
      icon: 'activity' as const,
      tone: failedRuns.length ? 'amber' : 'cyan',
    },
  ], [data.jobs, data.processes, data.runs, failedRuns.length, successRate, terminalRuns])

  const copy = viewCopy[view]
  const status = data.health?.status ?? 'initialised'

  if (initialLoading) {
    return <LoadingScreen />
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <Sidebar view={view} onNavigate={setView} />

      <main className="main-stage">
        <header className="topbar">
          <div>
            <p className="eyebrow">{copy.eyebrow}</p>
            <h1>{copy.title}</h1>
            <p className="page-description">{copy.description}</p>
          </div>
          <div className="topbar-actions">
            <OrchestratorPill
              database={data.health?.database ?? 'down'}
              status={status}
            />
            <button
              className="button button-primary"
              disabled={busy}
              onClick={() => setProcessDialog('new')}
              type="button"
            >
              <Icon name="plus" size={17} />
              New process
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner" role="alert">
            <span className="error-icon">!</span>
            <span>{error}</span>
            <button aria-label="Dismiss error" onClick={() => setError(null)}>
              <Icon name="x" size={16} />
            </button>
          </div>
        )}

        {view === 'overview' && (
          <Overview
            data={data}
            metrics={metrics}
            busy={busy}
            onControl={(action) => perform(() => api.setOrchestrator(action))}
            onEditProcess={setProcessDialog}
            onSchedule={setJobProcess}
            onSelectRun={setSelectedRun}
            onToggleProcess={(process) => perform(() => (
              api.setProcessEnabled(process.process_id, !process.enabled)
            ))}
          />
        )}

        {view === 'processes' && (
          <ProcessesView
            processes={data.processes}
            busy={busy}
            onDelete={(process) => {
              if (window.confirm(`Delete ${process.name}?`)) {
                void perform(() => api.deleteProcess(process.process_id))
              }
            }}
            onEdit={setProcessDialog}
            onNew={() => setProcessDialog('new')}
            onSchedule={setJobProcess}
            onToggle={(process) => perform(() => (
              api.setProcessEnabled(process.process_id, !process.enabled)
            ))}
          />
        )}

        {view === 'schedules' && (
          <SchedulesView
            jobs={data.jobs}
            busy={busy}
            onDelete={(job) => {
              if (window.confirm(`Delete the schedule for ${job.process.name}?`)) {
                void perform(() => api.deleteJob(job.job_id))
              }
            }}
            onRunNow={(job) => perform(() => api.runJobNow(job.job_id))}
            onToggle={(job) => perform(() => (
              api.updateJob(job.job_id, { active: !job.active })
            ))}
          />
        )}

        {view === 'activity' && (
          <ActivityView runs={data.runs} onSelectRun={setSelectedRun} />
        )}

        <footer className="stage-footer">
          <span>
            Last synced {lastUpdated ? formatTime(lastUpdated.toISOString()) : '—'}
          </span>
          <span className="footer-mark">DARK / ORCHESTRATOR</span>
        </footer>
      </main>

      {processDialog && (
        <ProcessDialog
          busy={busy}
          process={processDialog === 'new' ? null : processDialog}
          onClose={() => setProcessDialog(null)}
          onSave={saveProcess}
        />
      )}

      {jobProcess && (
        <JobDialog
          busy={busy}
          process={jobProcess}
          onClose={() => setJobProcess(null)}
          onSave={createJob}
        />
      )}

      {selectedRun && (
        <RunDrawer run={selectedRun} onClose={() => setSelectedRun(null)} />
      )}
    </div>
  )
}

function Sidebar({ view, onNavigate }: { view: View; onNavigate: (view: View) => void }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-glyph">
          <span>D</span>
          <i />
        </div>
        <div>
          <strong>Dark</strong>
          <span>Orchestrator</span>
        </div>
      </div>

      <nav aria-label="Main navigation">
        <p className="nav-label">Control room</p>
        {navigation.map((item) => (
          <button
            className={`nav-item ${view === item.id ? 'active' : ''}`}
            key={item.id}
            onClick={() => onNavigate(item.id)}
            type="button"
          >
            <Icon name={item.icon} />
            <span>{item.label}</span>
            {view === item.id && <i className="nav-active-dot" />}
          </button>
        ))}
      </nav>

      <div className="sidebar-card">
        <div className="sidebar-card-icon">
          <Icon name="spark" size={16} />
        </div>
        <p>Agent ready</p>
        <span>AgentShell processes can be scheduled as ordinary scripts.</span>
      </div>

      <div className="sidebar-foot">
        <span className="avatar">SC</span>
        <div>
          <strong>Operator</strong>
          <span>System owner</span>
        </div>
        <Icon name="chevron" size={15} />
      </div>
    </aside>
  )
}

interface OverviewProps {
  data: DashboardData
  metrics: Array<{
    label: string
    value: number | string
    detail: string
    icon: 'workflow' | 'calendar' | 'check' | 'activity'
    tone: string
  }>
  busy: boolean
  onControl: (action: 'start' | 'pause' | 'stop') => Promise<boolean>
  onEditProcess: (process: Process) => void
  onSchedule: (process: Process) => void
  onSelectRun: (run: JobRun) => void
  onToggleProcess: (process: Process) => Promise<boolean>
}

function Overview({
  data,
  metrics,
  busy,
  onControl,
  onEditProcess,
  onSchedule,
  onSelectRun,
  onToggleProcess,
}: OverviewProps) {
  const status = data.health?.status ?? 'initialised'
  const isRunning = status === 'running'

  return (
    <div className="view-stack">
      <section className="pulse-panel">
        <div className="pulse-copy">
          <span className="section-kicker">
            <Icon name="spark" size={15} />
            Orchestration layer
          </span>
          <h2>
            {isRunning ? 'Everything is moving.' : 'The system is standing by.'}
          </h2>
          <p>
            {isRunning
              ? 'The scheduler is watching for due work and dispatching processes.'
              : 'Resume orchestration when you are ready to dispatch scheduled work.'}
          </p>
          <div className="control-row">
            {isRunning ? (
              <button
                className="button button-secondary"
                disabled={busy}
                onClick={() => void onControl('pause')}
                type="button"
              >
                <Icon name="pause" size={16} />
                Pause scheduler
              </button>
            ) : (
              <button
                className="button button-primary"
                disabled={busy}
                onClick={() => void onControl('start')}
                type="button"
              >
                <Icon name="play" size={16} />
                Start scheduler
              </button>
            )}
            <button
              aria-label="Stop scheduler"
              className="icon-button control-stop"
              disabled={busy || status === 'stopped'}
              onClick={() => void onControl('stop')}
              type="button"
            >
              <Icon name="stop" size={15} />
            </button>
          </div>
        </div>
        <PulseVisual running={isRunning} />
      </section>

      <section className="metric-grid" aria-label="System metrics">
        {metrics.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <div className={`metric-icon ${metric.tone}`}>
              <Icon name={metric.icon} size={18} />
            </div>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        ))}
      </section>

      <SectionHeading
        subtitle="Reusable scripts and agent entry points"
        title="Process library"
      />
      {data.processes.length ? (
        <ProcessGrid
          processes={data.processes.slice(0, 6)}
          busy={busy}
          onEdit={onEditProcess}
          onSchedule={onSchedule}
          onToggle={onToggleProcess}
        />
      ) : (
        <EmptyState
          icon="workflow"
          title="No processes yet"
          text="Create your first process to give the orchestrator something to run."
        />
      )}

      <SectionHeading
        subtitle="Live and historical execution signals"
        title="Recent activity"
      />
      <RunList runs={data.runs.slice(0, 8)} onSelectRun={onSelectRun} />
    </div>
  )
}

function PulseVisual({ running }: { running: boolean }) {
  return (
    <div className={`pulse-visual ${running ? 'running' : ''}`} aria-hidden="true">
      <span className="orbit orbit-one"><i /></span>
      <span className="orbit orbit-two"><i /></span>
      <span className="pulse-core">
        <Icon name={running ? 'activity' : 'pause'} size={30} />
      </span>
      <span className="pulse-label">
        <i />
        {running ? 'Live' : 'Paused'}
      </span>
    </div>
  )
}

interface ProcessGridProps {
  processes: Process[]
  busy: boolean
  onEdit: (process: Process) => void
  onSchedule: (process: Process) => void
  onToggle: (process: Process) => Promise<unknown>
  onDelete?: (process: Process) => void
}

function ProcessGrid({
  processes,
  busy,
  onEdit,
  onSchedule,
  onToggle,
  onDelete,
}: ProcessGridProps) {
  return (
    <div className="process-grid">
      {processes.map((process) => (
        <article className="process-card" data-testid="process-card" key={process.process_id}>
          <div className="process-card-head">
            <div className="process-identifiers">
              <div className={`process-type ${process.type}`}>
                <Icon name={process.type === 'python' ? 'code' : 'terminal'} size={18} />
              </div>
              <span className={`source-chip ${process.source.kind}`}>
                <Icon
                  name={process.source.kind === 'inline' ? 'database' : 'file'}
                  size={12}
                />
                {process.source.kind === 'inline' ? 'Inline' : 'Host file'}
              </span>
            </div>
            <div className="process-state">
              <i className={process.enabled ? 'enabled' : ''} />
              {process.enabled ? 'Enabled' : 'Disabled'}
            </div>
          </div>
          <h3>{process.name}</h3>
          <p className="script-preview">{processSourcePreview(process)}</p>
          <div className="process-meta">
            <span>
              <Icon name="clock" size={14} />
              {process.last_run_at
                ? `Ran ${relativeTime(process.last_run_at)}`
                : 'Never run'}
            </span>
            <span className="type-chip">{process.type}</span>
          </div>
          <div className="process-actions">
            <button
              className="button button-quiet schedule-button"
              disabled={busy || !process.enabled}
              onClick={() => onSchedule(process)}
              type="button"
            >
              <Icon name="calendar" size={15} />
              Schedule
            </button>
            <button
              aria-label={`${process.enabled ? 'Disable' : 'Enable'} ${process.name}`}
              className="icon-button"
              disabled={busy}
              onClick={() => void onToggle(process)}
              type="button"
            >
              <Icon name="power" size={15} />
            </button>
            <button
              aria-label={`Edit ${process.name}`}
              className="icon-button"
              disabled={busy}
              onClick={() => onEdit(process)}
              type="button"
            >
              <Icon name="code" size={15} />
            </button>
            {onDelete && (
              <button
                aria-label={`Delete ${process.name}`}
                className="icon-button danger"
                disabled={busy}
                onClick={() => onDelete(process)}
                type="button"
              >
                <Icon name="trash" size={15} />
              </button>
            )}
          </div>
        </article>
      ))}
    </div>
  )
}

function ProcessesView({
  processes,
  busy,
  onDelete,
  onEdit,
  onNew,
  onSchedule,
  onToggle,
}: {
  processes: Process[]
  busy: boolean
  onDelete: (process: Process) => void
  onEdit: (process: Process) => void
  onNew: () => void
  onSchedule: (process: Process) => void
  onToggle: (process: Process) => Promise<unknown>
}) {
  return (
    <div className="view-stack">
      <div className="collection-toolbar">
        <div>
          <span>{processes.length} processes</span>
          <small>{processes.filter((process) => process.enabled).length} enabled</small>
        </div>
        <button className="button button-secondary" onClick={onNew} type="button">
          <Icon name="plus" size={16} />
          Add process
        </button>
      </div>
      {processes.length ? (
        <ProcessGrid
          processes={processes}
          busy={busy}
          onDelete={onDelete}
          onEdit={onEdit}
          onSchedule={onSchedule}
          onToggle={onToggle}
        />
      ) : (
        <EmptyState
          icon="workflow"
          title="Build your process library"
          text="Processes wrap Bash scripts, Python scripts, and AgentShell commands."
        />
      )}
    </div>
  )
}

function SchedulesView({
  jobs,
  busy,
  onDelete,
  onRunNow,
  onToggle,
}: {
  jobs: Job[]
  busy: boolean
  onDelete: (job: Job) => void
  onRunNow: (job: Job) => Promise<unknown>
  onToggle: (job: Job) => Promise<unknown>
}) {
  if (!jobs.length) {
    return (
      <EmptyState
        icon="calendar"
        title="No jobs scheduled"
        text="Open a process and schedule it when you are ready."
      />
    )
  }

  return (
    <section className="table-panel">
      <div className="table-head schedule-columns">
        <span>Process</span>
        <span>Schedule</span>
        <span>Next run</span>
        <span>Status</span>
        <span />
      </div>
      {jobs.map((job) => (
        <div className="schedule-row schedule-columns" key={job.job_id}>
          <div className="name-cell">
            <span className={`mini-type ${job.process.type}`}>
              <Icon
                name={job.process.type === 'python' ? 'code' : 'terminal'}
                size={14}
              />
            </span>
            <div>
              <strong>{job.process.name}</strong>
              <small>{shortId(job.job_id)}</small>
            </div>
          </div>
          <span>{job.recurring ? job.cron : 'One-off'}</span>
          <span>{job.next_run_at ? formatDate(job.next_run_at) : 'Complete'}</span>
          <button
            className={`state-toggle ${job.active ? 'active' : ''}`}
            disabled={busy}
            onClick={() => void onToggle(job)}
            type="button"
          >
            <i />
            {job.active ? 'Active' : 'Inactive'}
          </button>
          <div className="row-actions">
            <button
              aria-label={`Run ${job.process.name} now`}
              className="icon-button"
              disabled={busy || !job.process.enabled}
              onClick={() => void onRunNow(job)}
              type="button"
            >
              <Icon name="play" size={14} />
            </button>
            <button
              aria-label={`Delete job for ${job.process.name}`}
              className="icon-button danger"
              disabled={busy}
              onClick={() => onDelete(job)}
              type="button"
            >
              <Icon name="trash" size={14} />
            </button>
          </div>
        </div>
      ))}
    </section>
  )
}

function ActivityView({
  runs,
  onSelectRun,
}: {
  runs: JobRun[]
  onSelectRun: (run: JobRun) => void
}) {
  return (
    <div className="view-stack">
      <div className="collection-toolbar">
        <div>
          <span>{runs.length} recorded runs</span>
          <small>Newest activity appears first</small>
        </div>
        <div className="legend">
          <span><i className="success" /> Completed</span>
          <span><i className="failed" /> Error</span>
          <span><i className="working" /> Active</span>
        </div>
      </div>
      <RunList runs={runs} onSelectRun={onSelectRun} />
    </div>
  )
}

function RunList({
  runs,
  onSelectRun,
}: {
  runs: JobRun[]
  onSelectRun: (run: JobRun) => void
}) {
  if (!runs.length) {
    return (
      <EmptyState
        compact
        icon="activity"
        title="Waiting for the first signal"
        text="Run activity and captured output will appear here."
      />
    )
  }

  return (
    <section className="run-list">
      <div className="table-head run-columns">
        <span>Process</span>
        <span>Status</span>
        <span>Started</span>
        <span>Duration</span>
        <span />
      </div>
      {runs.map((run) => (
        <button
          className="run-row run-columns"
          data-testid="run-row"
          key={run.job_run_id}
          onClick={() => onSelectRun(run)}
          type="button"
        >
          <div className="name-cell">
            <span className={`mini-type ${run.job.process.type}`}>
              <Icon
                name={run.job.process.type === 'python' ? 'code' : 'terminal'}
                size={14}
              />
            </span>
            <div>
              <strong>{run.job.process.name}</strong>
              <small>{shortId(run.job_run_id)}</small>
            </div>
          </div>
          <RunBadge status={run.status} />
          <span>{run.started_at ? formatDate(run.started_at) : 'Queued'}</span>
          <span>{duration(run)}</span>
          <span className="row-chevron"><Icon name="chevron" size={14} /></span>
        </button>
      ))}
    </section>
  )
}

function RunBadge({ status }: { status: RunStatus }) {
  return (
    <span className={`run-badge ${status}`}>
      <i />
      {titleCase(status)}
    </span>
  )
}

function OrchestratorPill({
  database,
  status,
}: {
  database: 'up' | 'down'
  status: string
}) {
  const healthy = database === 'up' && status === 'running'
  return (
    <div className={`orchestrator-pill ${healthy ? 'healthy' : ''}`}>
      <span className="status-rings"><i /></span>
      <div>
        <strong>{titleCase(status)}</strong>
        <span>Database {database}</span>
      </div>
    </div>
  )
}

function SectionHeading({
  title,
  subtitle,
}: {
  title: string
  subtitle: string
}) {
  return (
    <div className="section-heading">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
    </div>
  )
}

function EmptyState({
  icon,
  title,
  text,
  compact = false,
}: {
  icon: 'workflow' | 'calendar' | 'activity'
  title: string
  text: string
  compact?: boolean
}) {
  return (
    <div className={`empty-state ${compact ? 'compact' : ''}`}>
      <span><Icon name={icon} size={22} /></span>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  )
}

function Modal({
  children,
  eyebrow,
  title,
  onClose,
}: {
  children: ReactNode
  eyebrow: string
  title: string
  onClose: () => void
}) {
  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div className="modal-backdrop" role="presentation">
      <section aria-label={title} aria-modal="true" className="modal" role="dialog">
        <header>
          <div>
            <p className="eyebrow">{eyebrow}</p>
            <h2>{title}</h2>
          </div>
          <button aria-label="Close" className="icon-button" onClick={onClose}>
            <Icon name="x" size={17} />
          </button>
        </header>
        {children}
      </section>
    </div>
  )
}

function ProcessDialog({
  process,
  busy,
  onClose,
  onSave,
}: {
  process: Process | null
  busy: boolean
  onClose: () => void
  onSave: (input: ProcessInput) => Promise<void>
}) {
  const [name, setName] = useState(process?.name ?? '')
  const [type, setType] = useState<'python' | 'bash'>(process?.type ?? 'python')
  const [sourceKind, setSourceKind] = useState<'inline' | 'file'>(
    process?.source.kind ?? 'inline',
  )
  const [script, setScript] = useState(
    process?.source.kind === 'inline' ? process.source.content : '',
  )
  const [scriptPath, setScriptPath] = useState(
    process?.source.kind === 'file' ? process.source.path : '',
  )

  function submit(event: FormEvent) {
    event.preventDefault()
    const source = sourceKind === 'inline'
      ? { kind: 'inline' as const, content: script }
      : { kind: 'file' as const, path: scriptPath }
    void onSave({ name, type, source })
  }

  return (
    <Modal
      eyebrow={process ? 'Edit process' : 'New building block'}
      title={process ? 'Refine the process' : 'Create a process'}
      onClose={onClose}
    >
      <form className="modal-form" onSubmit={submit}>
        <label>
          <span>Process name</span>
          <input
            autoFocus
            maxLength={120}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Sample website builder"
            required
            value={name}
          />
        </label>
        <label>
          <span>Process type</span>
          <select
            onChange={(event) => setType(event.target.value as 'python' | 'bash')}
            value={type}
          >
            <option value="python">Python</option>
            <option value="bash">Bash</option>
          </select>
        </label>
        <fieldset className="source-picker">
          <legend>Script source</legend>
          <button
            aria-label="Inline source"
            className={sourceKind === 'inline' ? 'active' : ''}
            onClick={() => setSourceKind('inline')}
            type="button"
          >
            <Icon name="database" size={16} />
            <span>
              <strong>Inline</strong>
              <small>Stored in Dark</small>
            </span>
          </button>
          <button
            aria-label="Host file"
            className={sourceKind === 'file' ? 'active' : ''}
            onClick={() => setSourceKind('file')}
            type="button"
          >
            <Icon name="file" size={16} />
            <span>
              <strong>Host file</strong>
              <small>Managed externally</small>
            </span>
          </button>
        </fieldset>
        {sourceKind === 'inline' ? (
          <label>
            <span>Script</span>
            <textarea
              maxLength={100_000}
              onChange={(event) => setScript(event.target.value)}
              placeholder={type === 'python'
                ? "print('agent online')"
                : 'agent-shell run ...'}
              required
              rows={9}
              spellCheck={false}
              value={script}
            />
            <small>Stored in PostgreSQL and editable from Dark.</small>
          </label>
        ) : (
          <label>
            <span>Script path</span>
            <input
              maxLength={1_000}
              onChange={(event) => setScriptPath(event.target.value)}
              placeholder="workflows/customer_onboarding.py"
              required
              spellCheck={false}
              value={scriptPath}
            />
            <small>
              Relative to the configured script root and managed outside Dark.
            </small>
          </label>
        )}
        <div className="modal-actions">
          <button className="button button-quiet" onClick={onClose} type="button">
            Cancel
          </button>
          <button className="button button-primary" disabled={busy} type="submit">
            {busy ? <span className="spinner" /> : <Icon name="plus" size={16} />}
            {process ? 'Save changes' : 'Create process'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function JobDialog({
  process,
  busy,
  onClose,
  onSave,
}: {
  process: Process
  busy: boolean
  onClose: () => void
  onSave: (input: JobInput) => Promise<void>
}) {
  const [mode, setMode] = useState<JobMode>('immediate')
  const [scheduledFor, setScheduledFor] = useState('')
  const [cron, setCron] = useState('0 9 * * *')
  const [processArguments, setProcessArguments] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    const input: JobInput = {
      process_id: process.process_id,
      arguments: processArguments.split('\n').filter((argument) => argument.length > 0),
    }
    if (mode === 'scheduled') {
      input.next_run_at = new Date(scheduledFor).toISOString()
    }
    if (mode === 'recurring') {
      input.recurring = true
      input.cron = cron
    }
    void onSave(input)
  }

  return (
    <Modal eyebrow="Schedule process" title="Create a job" onClose={onClose}>
      <form className="modal-form" onSubmit={submit}>
        <div className="selected-process">
          <span className={`process-type ${process.type}`}>
            <Icon name={process.type === 'python' ? 'code' : 'terminal'} size={17} />
          </span>
          <div>
            <strong>{process.name}</strong>
            <small>{process.type} process</small>
          </div>
          <Icon name="check" size={17} />
        </div>

        <fieldset className="mode-picker">
          <legend>Run mode</legend>
          {(['immediate', 'scheduled', 'recurring'] as JobMode[]).map((option) => (
            <button
              className={mode === option ? 'active' : ''}
              key={option}
              onClick={() => setMode(option)}
              type="button"
            >
              <Icon
                name={option === 'immediate' ? 'play' : option === 'scheduled'
                  ? 'clock'
                  : 'calendar'}
                size={15}
              />
              {titleCase(option)}
            </button>
          ))}
        </fieldset>

        {mode === 'scheduled' && (
          <label>
            <span>Run at</span>
            <input
              onChange={(event) => setScheduledFor(event.target.value)}
              required
              type="datetime-local"
              value={scheduledFor}
            />
          </label>
        )}

        {mode === 'recurring' && (
          <label>
            <span>Cron expression</span>
            <input
              onChange={(event) => setCron(event.target.value)}
              placeholder="0 9 * * *"
              required
              value={cron}
            />
            <small>Five fields: minute, hour, day, month, weekday.</small>
          </label>
        )}

        <label>
          <span>Process arguments</span>
          <textarea
            maxLength={50_000}
            onChange={(event) => setProcessArguments(event.target.value)}
            placeholder={'--campaign-location\nLeeds, England'}
            rows={4}
            spellCheck={false}
            value={processArguments}
          />
          <small>Enter one argument per line.</small>
        </label>

        <div className="schedule-summary">
          <Icon name="spark" size={17} />
          <span>
            {mode === 'immediate' && 'This job will enter the queue immediately.'}
            {mode === 'scheduled' && 'This job will run once at the selected time.'}
            {mode === 'recurring' && 'The next run is calculated from the cron schedule.'}
          </span>
        </div>

        <div className="modal-actions">
          <button className="button button-quiet" onClick={onClose} type="button">
            Cancel
          </button>
          <button className="button button-primary" disabled={busy} type="submit">
            {busy ? <span className="spinner" /> : <Icon name="calendar" size={16} />}
            Create job
          </button>
        </div>
      </form>
    </Modal>
  )
}

function RunDrawer({ run, onClose }: { run: JobRun; onClose: () => void }) {
  return (
    <div className="drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        aria-label="Run details"
        aria-modal="true"
        className="run-drawer"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <header>
          <div>
            <p className="eyebrow">Run details</p>
            <h2>{run.job.process.name}</h2>
          </div>
          <button aria-label="Close" className="icon-button" onClick={onClose}>
            <Icon name="x" size={17} />
          </button>
        </header>

        <div className="run-detail-grid">
          <div><span>Status</span><RunBadge status={run.status} /></div>
          <div><span>Type</span><strong>{run.job.process.type}</strong></div>
          <div><span>Started</span><strong>{formatDate(run.started_at)}</strong></div>
          <div><span>Duration</span><strong>{duration(run)}</strong></div>
        </div>

        {run.exception && (
          <div className="exception-box">
            <strong>Execution error</strong>
            <p>{run.exception}</p>
          </div>
        )}

        <div className="output-heading">
          <div>
            <Icon name="terminal" size={16} />
            <strong>Captured output</strong>
          </div>
          <span>{run.captured_output.length} characters</span>
        </div>
        <pre className="output-console">
          <code>{run.captured_output || 'No output was captured.'}</code>
        </pre>

        <div className="drawer-meta">
          <span>Run ID</span>
          <code>{run.job_run_id}</code>
          <span>Job ID</span>
          <code>{run.job.job_id}</code>
        </div>
      </aside>
    </div>
  )
}

function LoadingScreen() {
  return (
    <div className="loading-screen">
      <div className="loading-mark">
        <span>D</span>
        <i />
      </div>
      <p>Waking mission control</p>
      <span className="loading-line"><i /></span>
    </div>
  )
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).replaceAll('_', ' ')
}

function shortId(value: string): string {
  return `#${value.slice(0, 8).toUpperCase()}`
}

function processSourcePreview(process: Process): string {
  if (process.source.kind === 'file') return process.source.path
  const first = process.source.content.split('\n')[0].trim()
  return first.length > 74 ? `${first.slice(0, 74)}…` : first
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: 'short',
  }).format(new Date(value))
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value))
}

function relativeTime(value: string): string {
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000)
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  if (Math.abs(seconds) < 60) return formatter.format(seconds, 'second')
  const minutes = Math.round(seconds / 60)
  if (Math.abs(minutes) < 60) return formatter.format(minutes, 'minute')
  const hours = Math.round(minutes / 60)
  if (Math.abs(hours) < 24) return formatter.format(hours, 'hour')
  return formatter.format(Math.round(hours / 24), 'day')
}

function duration(run: JobRun): string {
  if (!run.started_at) return '—'
  const end = run.finished_at ? new Date(run.finished_at).getTime() : Date.now()
  const milliseconds = Math.max(0, end - new Date(run.started_at).getTime())
  if (milliseconds < 1000) return `${milliseconds} ms`
  if (milliseconds < 60_000) return `${(milliseconds / 1000).toFixed(1)} s`
  return `${Math.floor(milliseconds / 60_000)}m ${Math.round(
    (milliseconds % 60_000) / 1000,
  )}s`
}

export default App
