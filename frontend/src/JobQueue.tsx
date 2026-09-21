export type JobStatus = 'pending' | 'awaiting_response' | 'completed' | 'failed' | 'cancelled'

export type IntentOption = { id: string; label: string; description: string }
export type IntentQuestions = {
  schema_version: 1
  question: string
  explanation: string
  options: IntentOption[]
}
export type IntentSelection = {
  schema_version: 1
  questions_artifact_id: string
  primary_intent_id: string
  secondary_intent_ids: string[]
  note: string
}
export type ScopeOption = { id: string; label: string; description: string }
export type ScopeQuestion = {
  id: string
  question: string
  why_it_matters: string
  selection_mode: 'single_choice' | 'multiple_choice'
  option_structure?: 'independent' | 'cumulative' | null
  options: ScopeOption[]
}
export type ScopeQuestions = { schema_version: 1 | 2 | 3; introduction: string; questions: ScopeQuestion[] }
export type ScopeAnswer = {
  question_id: string
  selected_option_ids: string[]
  note: string
  is_unsure: boolean
}
export type ScopeAnswers = {
  schema_version: 1
  questions_artifact_id: string
  answers: ScopeAnswer[]
}
export type ScopeReadinessReview = {
  schema_version: 1 | 2
  ready_for_charter: boolean
  assessment: string
  remaining_uncertainties: string[]
  follow_up_questions: ScopeQuestion[]
}

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
  workflow_input_snapshot_json: string | null
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
  intent_questions: IntentQuestions | null
  intent_selection: IntentSelection | null
  intent_selection_version: number | null
  intent_selection_is_editable: boolean
  scope_questions: ScopeQuestions | null
  scope_answers: ScopeAnswers | null
  scope_answers_version: number | null
  scope_answers_is_editable: boolean
  scope_readiness_review: ScopeReadinessReview | null
  scope_follow_up_answers: ScopeAnswers | null
  scope_follow_up_answers_version: number | null
  scope_follow_up_answers_is_editable: boolean
  charter_approved_at: string | null
  charter_is_editable: boolean
  charter_can_regenerate: boolean
}

function jobKindLabel(job: Job) {
  const promptVersion = promptVersionNumber(job.prompt_template_version)
  if (job.kind === 'intent_clarification') return promptVersion >= 3 ? 'Research goal questionnaire' : promptVersion === 2 ? 'Research direction' : 'Intent clarification'
  if (job.kind === 'scope_clarification_round_1') return promptVersion >= 5 ? 'Assumptions and boundaries' : promptVersion >= 3 ? 'Project framing' : 'Scope clarification'
  if (job.kind === 'scope_readiness') return promptVersion >= 5 ? 'Framing check' : promptVersion >= 3 ? 'Framing readiness review' : 'Scope readiness review'
  if (job.kind === 'research_charter') return promptVersion >= 2 ? 'Peptide-discovery charter' : 'Research charter'
  return 'Question detailing'
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
        <button className="queue-job-open" type="button" onClick={() => onOpenJob(job)} aria-label={`Open ${job.project_tag} ${jobKindLabel(job)} job`}>
          <div className="queue-job-heading"><strong>{job.project_tag}</strong><JobStatusLabel status={job.status} /></div>
          <p>{jobKindLabel(job)}</p>
          <div className="queue-job-details"><small>{job.provider === 'openai' ? 'OpenAI' : 'Anthropic'} · {job.model}</small><JobElapsedTime job={job} nowMilliseconds={nowMilliseconds} /></div>
          {job.error && <p className="setup-error">{job.error}</p>}
        </button>
        {job.status === 'pending' && <button className="text-button" type="button" onClick={() => onCancel(job.id)}>Cancel queued job</button>}
      </article>)}
    </div>}
  </aside>
}
import { promptVersionNumber } from './promptVersion'
