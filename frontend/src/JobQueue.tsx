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

export function QueueIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 7h14M5 12h14M5 17h14" /><circle cx="3" cy="7" r=".7" /><circle cx="3" cy="12" r=".7" /><circle cx="3" cy="17" r=".7" /></svg>
}

type DrawerProps = {
  jobs: Job[]
  onClose: () => void
  onCancel: (jobId: string) => void
}

export function JobQueueDrawer({ jobs, onClose, onCancel }: DrawerProps) {
  return <aside className="settings-drawer queue-drawer" id="queue-drawer" aria-labelledby="queue-title">
    <div className="settings-drawer-header"><div><p className="step-label">Research queue</p><h2 id="queue-title">Jobs</h2></div><button className="settings-close" type="button" aria-label="Close job queue" onClick={onClose}>×</button></div>
    {jobs.length === 0 ? <p className="queue-empty">No jobs have been started yet.</p> : <div className="queue-list">
      {jobs.map(job => <article className="queue-job" key={job.id}>
        <div className="queue-job-heading"><strong>{job.project_tag}</strong><JobStatusLabel status={job.status} /></div>
        <p>Question detailing</p>
        <small>{job.provider === 'openai' ? 'OpenAI' : 'Anthropic'} · {job.model}</small>
        {job.error && <p className="setup-error">{job.error}</p>}
        {job.status === 'pending' && <button className="text-button" type="button" onClick={() => onCancel(job.id)}>Cancel queued job</button>}
      </article>)}
    </div>}
  </aside>
}
