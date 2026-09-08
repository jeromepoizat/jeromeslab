export type JobStatus = 'pending' | 'awaiting_response' | 'completed' | 'failed' | 'cancelled'

export type Job = {
  id: string
  project_id: string
  project_tag: string
  kind: string
  status: JobStatus
  created_at: string
  started_at: string | null
  completed_at: string | null
  provider: 'openai' | 'anthropic'
  model: string
  scientific_question_snapshot: string
  prompt_snapshot: string
  prompt_template_version: string
  error: string | null
  output_markdown: string | null
  original_output_markdown: string | null
  effective_output_markdown: string | null
  effective_output_version: number | null
  output_was_edited: boolean
  llm_call_id: string | null
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  duration_ms: number | null
  cost_status: string | null
}

const statusLabels: Record<JobStatus, string> = {
  pending: 'Queued',
  awaiting_response: 'Awaiting provider response',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

export function JobStatusLabel({ status }: { status: JobStatus }) {
  return <span className={`job-status job-status--${status}`}><span aria-hidden="true" />{statusLabels[status]}</span>
}

function timestampMilliseconds(value: string | null) {
  if (value === null) return null
  const milliseconds = Date.parse(value)
  return Number.isFinite(milliseconds) ? milliseconds : null
}

function jobElapsedMilliseconds(job: Job, nowMilliseconds: number) {
  const started = timestampMilliseconds(job.created_at)
  if (started === null) return job.duration_ms
  const finished = timestampMilliseconds(job.completed_at)
  return Math.max(0, (finished ?? nowMilliseconds) - started)
}

function formatElapsedTime(milliseconds: number) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1_000))
  const seconds = totalSeconds % 60
  const totalMinutes = Math.floor(totalSeconds / 60)
  const minutes = totalMinutes % 60
  const hours = Math.floor(totalMinutes / 60)
  return hours > 0
    ? `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
    : `${minutes}:${seconds.toString().padStart(2, '0')}`
}

export function JobElapsedTime({ job, nowMilliseconds }: { job: Job; nowMilliseconds: number }) {
  const elapsed = jobElapsedMilliseconds(job, nowMilliseconds)
  if (elapsed === null) return null
  const isActive = job.status === 'pending' || job.status === 'awaiting_response'
  const formatted = formatElapsedTime(elapsed)
  const label = isActive
    ? `Elapsed ${formatted}`
    : job.status === 'completed'
      ? `Completed in ${formatted}`
      : job.status === 'cancelled'
        ? `Cancelled after ${formatted}`
        : `Stopped after ${formatted}`
  return <span className={`job-time ${isActive ? 'job-time--active' : ''}`}>{label}</span>
}

export function QueueIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 7h14M5 12h14M5 17h14" /><circle cx="3" cy="7" r=".7" /><circle cx="3" cy="12" r=".7" /><circle cx="3" cy="17" r=".7" /></svg>
}

type DrawerProps = {
  jobs: Job[]
  nowMilliseconds: number
  onClose: () => void
  onCancel: (jobId: string) => void
  onOpenJob: (job: Job) => void
}

export function JobQueueDrawer({ jobs, nowMilliseconds, onClose, onCancel, onOpenJob }: DrawerProps) {
  return <aside className="settings-drawer queue-drawer" id="queue-drawer" aria-labelledby="queue-title">
    <div className="settings-drawer-header"><div><p className="step-label">Research queue</p><h2 id="queue-title">Jobs</h2></div><button className="settings-close" type="button" aria-label="Close job queue" onClick={onClose}>×</button></div>
    {jobs.length === 0 ? <p className="queue-empty">No jobs have been started yet.</p> : <div className="queue-list">
      {jobs.map(job => <article className="queue-job" key={job.id}>
        <button className="queue-job-open" type="button" onClick={() => onOpenJob(job)} aria-label={`Open ${job.project_tag} question-detailing job`}>
          <div className="queue-job-heading"><strong>{job.project_tag}</strong><JobStatusLabel status={job.status} /></div>
          <p>Question detailing</p>
          <div className="queue-job-details"><small>{job.provider === 'openai' ? 'OpenAI' : 'Anthropic'} · {job.model}</small><JobElapsedTime job={job} nowMilliseconds={nowMilliseconds} /></div>
          {job.error && <p className="setup-error">{job.error}</p>}
        </button>
        {job.status === 'pending' && <button className="text-button" type="button" onClick={() => onCancel(job.id)}>Cancel queued job</button>}
      </article>)}
    </div>}
  </aside>
}
