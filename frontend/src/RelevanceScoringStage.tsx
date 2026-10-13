import { useEffect, useState } from 'react'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import type { Job } from './JobQueue'
import { ChangeModelIcon, HelpTooltip, SectionTitle } from './ProjectElements'
import { RelevanceScoreFilter } from './RelevanceScoreFilter'
import { relevanceScoreLabels as scoreLabels } from './relevanceScoreLabels'

type Cost = { status: string; usd: number | null }
type Preview = {
  requested_count: number
  available_unscored: number
  selected_count: number
  seed: number
  algorithm_version: string
  manifest_sha256: string
  prompt_artifact_id: string
  batch_sizes: number[]
  provider: 'openai' | 'anthropic' | null
  model: string | null
}
type Run = {
  id: string
  status: 'running' | 'paused' | 'failed' | 'completed'
  stop_requested: boolean
  provider: string
  model: string
  seed: number
  selected_count: number
  parallel_batches: number
  active_batch_indices: number[]
  pause_error: string | null
  scored_count: number
  available_unscored: number
  confirmed_at: string | null
  batch_count: number
  completed_batches: number
  remaining_batches: number
  batch_sizes: number[]
  by_score: Record<string, { count: number; samples?: { source: string; source_record_id: string; title: string }[] }>
  jobs: { id: string; status: string; batch_index: number; error: string | null }[]
  total_tokens: number
  estimated_cost_usd: number
  remaining_token_estimate: number
  remaining_cost: Cost
}

type Props = {
  projectId: string
  retrievalJob: Job
  promptJob: Job
  setupToken: string
  llmSettings: LLMSettings
  onJobsChanged: () => Promise<void>
  onOpenSettings: () => void
}

function price(value: Cost): string {
  if (value.status !== 'estimated' || value.usd === null) return 'Cost unavailable for this exact model'
  return `Est. $${value.usd < 0.01 ? value.usd.toFixed(4) : value.usd.toFixed(2)}`
}

function ExtensionCard({ run, working, onExtend }: { run: Run; working: boolean; onExtend: (count: number) => void }) {
  const [additionalCount, setAdditionalCount] = useState(Math.min(100, run.available_unscored))
  const maximum = Math.min(100000, run.available_unscored)
  const valid = Number.isInteger(additionalCount) && additionalCount >= 1 && additionalCount <= maximum
  return <div className="llm-job-provider relevance-extension-card">
    <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span></div><strong>{run.provider === 'openai' ? 'OpenAI' : 'Anthropic'} · {run.model}</strong></div>
    <div className="relevance-extension-controls">
      <label><span className="relevance-control-label">Additional records to score <HelpTooltip label="Additional records help">Continue the same scoring run with this many previously unscored source records. The saved seed, prompt and model stay the same.</HelpTooltip></span><input type="number" min={1} max={maximum} value={additionalCount} onChange={event => setAdditionalCount(Math.min(maximum, Number(event.target.value)))} /><small>{run.available_unscored.toLocaleString()} remain unscored</small></label>
      <button className="primary-button" type="button" disabled={working || !valid} onClick={() => onExtend(additionalCount)}>Score more records</button>
    </div>
  </div>
}

export function RelevanceScoringStage({ projectId, retrievalJob, promptJob, setupToken, llmSettings, onJobsChanged, onOpenSettings }: Props) {
  const [count, setCount] = useState(100)
  const [seed, setSeed] = useState(12345)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [runsState, setRunsState] = useState<{ projectId: string; runs: Run[] } | null>(null)
  const [statusError, setStatusError] = useState<{ projectId: string; message: string } | null>(null)
  const [retryStatus, setRetryStatus] = useState(0)
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const [parallelChoice, setParallelChoice] = useState<{ scope: string; value: number } | null>(null)
  const [confirming, setConfirming] = useState(false)
  const runsLoaded = runsState?.projectId === projectId
  const runs = runsLoaded ? runsState.runs : []
  const firstRun = runs[0]
  const parallelScope = `${projectId}:${firstRun?.id ?? 'new'}`
  const parallelBatches = parallelChoice?.scope === parallelScope ? parallelChoice.value : firstRun?.parallel_batches ?? 1
  const hasRun = runs.length > 0
  const selectedProvider = llmSettings.providers.find(item => item.id === llmSettings.selected_provider)
  const readyPreview = runsLoaded && !hasRun && preview?.requested_count === count && preview.seed === seed
    && preview.provider === llmSettings.selected_provider && preview.model === llmSettings.selected_model
    ? preview : null

  useEffect(() => {
    let mounted = true
    let refreshing = false
    const refresh = async () => {
      if (refreshing) return
      refreshing = true
      try {
        const response = await fetch(`/api/projects/${projectId}/relevance/scoring/runs`, { signal: AbortSignal.timeout(10000) })
        if (!response.ok) throw new Error(await readApiError(response))
        const updated = await response.json() as Run[]
        if (mounted) { setRunsState({ projectId, runs: updated }); setStatusError(null) }
      } catch (cause) {
        if (mounted) setStatusError({ projectId, message: cause instanceof DOMException && cause.name === 'TimeoutError' ? 'Scoring status took too long to load. The database may be busy. Your saved scores have not been changed.' : cause instanceof Error ? cause.message : 'Could not load scoring status.' })
      }
      finally { refreshing = false }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 2000)
    return () => { mounted = false; window.clearInterval(timer) }
  }, [projectId, retryStatus])

  useEffect(() => {
    if (!runsLoaded || hasRun || !Number.isInteger(count) || count < 1 || !Number.isInteger(seed) || seed < 0) {
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/projects/${projectId}/relevance/scoring/preview`, {
          method: 'POST', signal: controller.signal,
          headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
          body: JSON.stringify({ retrieval_job_id: retrievalJob.id, prompt_job_id: promptJob.id, count, seed }),
        })
        if (!response.ok) throw new Error(await readApiError(response))
        setPreview({ ...(await response.json() as Preview), requested_count: count })
        setError('')
      } catch (cause) {
        if (!controller.signal.aborted) { setPreview(null); setError(cause instanceof Error ? cause.message : 'Could not prepare the scoring selection.') }
      }
    }, 300)
    return () => { controller.abort(); window.clearTimeout(timer) }
  }, [projectId, retrievalJob.id, promptJob.id, count, seed, setupToken, runsLoaded, hasRun,
    llmSettings.selected_provider, llmSettings.selected_model])

  async function action(path: string, body?: object) {
    setWorking(true)
    setError('')
    try {
      const response = await fetch(path, {
        signal: AbortSignal.timeout(20000),
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: body ? JSON.stringify(body) : undefined,
      })
      if (!response.ok) throw new Error(await readApiError(response))
      setPreview(null)
      setConfirming(false)
      // Refreshes must not keep action buttons disabled after the mutation finishes.
      void fetch(`/api/projects/${projectId}/relevance/scoring/runs`, { signal: AbortSignal.timeout(10000) })
        .then(async refreshed => { if (refreshed.ok) setRunsState({ projectId, runs: await refreshed.json() as Run[] }) })
        .catch(() => { /* Polling will recover saved progress. */ })
      void onJobsChanged().catch(() => { /* Do not block scoring controls on the global queue refresh. */ })
    } catch (cause) { setError(cause instanceof DOMException && (cause.name === 'TimeoutError' || cause.name === 'AbortError') ? 'The request timed out. It may have succeeded; saved progress will refresh. Check its status before trying again.' : cause instanceof Error ? cause.message : 'The scoring action failed.') }
    finally { setWorking(false) }
  }

  return <><section className="project-section relevance-scoring">
    <SectionTitle help="Score distinct saved source records for relevance only, in bounded API batches. Choose a record count to control expense; the seed makes the query-and-collection-balanced selection repeatable. You can pause between requests and resume saved progress. This is not study-quality assessment.">Score retrieved records for relevance</SectionTitle>
    {statusError?.projectId === projectId ? <div role="alert"><p className="setup-error">{runsLoaded ? 'Showing last saved status. ' : ''}{statusError.message}</p><button type="button" className="text-button" onClick={() => { setStatusError(null); setRetryStatus(value => value + 1) }}>Retry status</button></div> : !runsLoaded && <p className="evidence-themes-helper">Loading scoring status…</p>}
    {runsLoaded && <>
      <div className="relevance-controls">
        <label><span className="relevance-control-label">Records to score <HelpTooltip label="Records to score help">Choose how many distinct source records the single scoring run will include. This selection is locked once scoring starts.</HelpTooltip></span><input type="number" min={1} max={100000} value={firstRun?.selected_count ?? count} disabled={hasRun} onChange={event => { setPreview(null); setCount(Number(event.target.value)) }} /></label>
        <label><span className="relevance-control-label">Selection seed <HelpTooltip label="Scoring selection seed help">Makes the balanced selection reproducible. The exact selected records and algorithm version are saved when the run starts.</HelpTooltip></span><input type="number" min={0} max={2147483647} value={firstRun?.seed ?? seed} disabled={hasRun} onChange={event => { setPreview(null); setSeed(Number(event.target.value)) }} /></label>
        <label><span className="relevance-control-label">Parallel batches <HelpTooltip label="Parallel batches help">Send 1–8 scoring batches simultaneously. Higher values can finish faster but increase concurrent API usage and may reach provider rate limits. Pause before changing this setting; already-sent requests finish first.</HelpTooltip></span><input type="number" min={1} max={8} value={parallelBatches} disabled={working || firstRun?.status === 'running' || Boolean(firstRun?.confirmed_at)} onChange={event => setParallelChoice({ scope: parallelScope, value: Math.max(1, Math.min(8, Math.trunc(Number(event.target.value)))) })} /></label>
        {!hasRun && <button className="text-button" type="button" onClick={() => { setPreview(null); setSeed(Math.floor(Math.random() * 2147483647)) }}>Generate seed</button>}
      </div>
      {!hasRun && <>{readyPreview && <div className="relevance-preview"><strong>{readyPreview.selected_count.toLocaleString()} of {readyPreview.available_unscored.toLocaleString()} unscored source records selected</strong><p>{readyPreview.batch_sizes.length} batches · up to {Math.max(...readyPreview.batch_sizes)} records per batch</p></div>}
      <div className={`llm-job-provider ${confirming ? 'llm-job-provider--confirming' : ''}`}>
        <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span><button className="model-change-button" type="button" onClick={onOpenSettings} title="Change model" aria-label="Change model for this job"><ChangeModelIcon /></button></div><strong>{llmSettings.configured ? `${selectedProvider?.display_name} · ${llmSettings.selected_model}` : 'Not configured'}</strong></div>
        {confirming && readyPreview ? <div className="job-confirmation job-confirmation--inline"><p>Start scoring {readyPreview.selected_count.toLocaleString()} selected records in {readyPreview.batch_sizes.length} batches, with up to {parallelBatches} in parallel? The prompt, selection, provider, and model will be saved with the run.</p><div><button className="primary-button" type="button" disabled={working} onClick={() => void action(`/api/projects/${projectId}/relevance/scoring/runs`, { retrieval_job_id: retrievalJob.id, prompt_job_id: promptJob.id, count, seed, parallel_batches: parallelBatches, expected_manifest_sha256: readyPreview.manifest_sha256, expected_prompt_artifact_id: readyPreview.prompt_artifact_id, expected_provider: readyPreview.provider, expected_model: readyPreview.model })}>{working ? 'Starting…' : 'Confirm and start'}</button><button className="text-button" type="button" onClick={() => setConfirming(false)}>Cancel</button></div></div> : <button className="primary-button model-job-start" type="button" disabled={working || !llmSettings.configured || !readyPreview?.provider || !readyPreview.model} onClick={() => setConfirming(true)}>Start relevance scoring</button>}
      </div>
      </>}
    </>}
    {runs.map(run => <div className="relevance-scoring-run" key={run.id}>
      {run.jobs.map(job => <span id={`job-output-${job.id}`} key={job.id} />)}
      <div className="active-job-heading"><strong>{run.confirmed_at ? 'Scoring validated' : run.status === 'completed' ? 'Scoring completed' : run.status === 'paused' ? 'Scoring paused' : run.status === 'failed' ? 'Scoring stopped on an error' : run.stop_requested ? 'Pausing after the current request' : 'Scoring in progress'}</strong><span>{run.provider === 'openai' ? 'OpenAI' : 'Anthropic'} · {run.model}</span></div>
      <p>{run.scored_count.toLocaleString()} of {run.selected_count.toLocaleString()} records scored · {run.completed_batches} of {run.batch_count} batches completed</p>
      <div className="relevance-progress-track" role="progressbar" aria-label="Records scored" aria-valuemin={0} aria-valuemax={run.selected_count} aria-valuenow={run.scored_count}><div style={{ width: `${100 * run.scored_count / run.selected_count}%` }} /></div>
      <p>{run.confirmed_at ? `${(run.selected_count - run.scored_count).toLocaleString()} planned records remain outside the validated pool` : `${(run.selected_count - run.scored_count).toLocaleString()} records and ${run.remaining_batches} batches remaining`} · {run.total_tokens.toLocaleString()} reported tokens{run.estimated_cost_usd > 0 ? ` · Est. $${run.estimated_cost_usd.toFixed(4)} so far` : ''}</p>
      {!run.confirmed_at && run.completed_batches >= 1 && run.remaining_batches > 0 && (run.total_tokens > 0
        ? <p>Estimated remaining usage: ~{run.remaining_token_estimate.toLocaleString()} tokens · {price(run.remaining_cost)} remaining</p>
        : <p>Remaining usage estimate unavailable: the provider has not reported token usage.</p>)}
      <div className="relevance-batch-status" role="status">{!run.confirmed_at && run.status === 'running' && <span className="relevance-spinner" aria-hidden="true" />}{run.confirmed_at ? 'Scored pool locked for the next step' : run.status === 'completed' ? 'All batches complete' : run.status === 'failed' ? 'Scoring stopped on an error' : run.status === 'paused' ? 'Scoring paused' : run.stop_requested ? `Finishing ${run.active_batch_indices.length} in-flight batch(es), then pausing` : run.active_batch_indices.length ? `Waiting for ${run.active_batch_indices.length} batch(es): ${run.active_batch_indices.map(index => index + 1).join(', ')} / ${run.batch_count}` : 'Waiting for batch dispatch'}</div>
      {!run.confirmed_at && (run.status === 'failed' || (run.status === 'paused' && run.pause_error)) && <p className="setup-error">{run.pause_error ? `Paused after two consecutive failures of a batch. ${run.pause_error}` : 'A batch did not complete.'}</p>}
      <div className="relevance-score-list">{scoreLabels.map(([key, label]) => { const item = run.by_score[key]; return <div className="relevance-score-row retrieval-tooltip-target" key={key} tabIndex={0} aria-label={`${label}, ${item?.count ?? 0} records; focus for sample records`}><strong>{label}</strong><span className="relevance-score-count">{item?.count ?? 0}</span><div className="retrieval-data-tooltip relevance-score-tooltip" role="tooltip"><strong>Sample records</strong>{item?.samples?.length ? <ul>{item.samples.map(sample => <li key={`${sample.source}:${sample.source_record_id}`}>{sample.title} <small>({sample.source}:{sample.source_record_id})</small></li>)}</ul> : <p>No records scored here yet.</p>}</div></div> })}</div>
      {run.status === 'running' && !run.stop_requested && <button className="text-button" type="button" disabled={working} onClick={() => void action(`/api/projects/${projectId}/relevance/scoring/runs/${run.id}/pause`)}>Pause after current request</button>}
      {!run.confirmed_at && (run.status === 'paused' || run.status === 'failed') && <button className="primary-button" type="button" disabled={working} onClick={() => void action(`/api/projects/${projectId}/relevance/scoring/runs/${run.id}/resume`, { parallel_batches: parallelBatches })}>Resume remaining records</button>}
    </div>)}
    {firstRun && (firstRun.status === 'completed' || firstRun.status === 'paused') && !firstRun.confirmed_at && <>
      {firstRun.status === 'completed' && firstRun.available_unscored > 0 && <ExtensionCard key={`${firstRun.id}:${firstRun.selected_count}`} run={firstRun} working={working} onExtend={additionalCount => void action(`/api/projects/${projectId}/relevance/scoring/runs/${firstRun.id}/extend`, { additional_count: additionalCount, parallel_batches: parallelBatches })} />}
      <div className="relevance-confirm-card">
        <button className="primary-button" type="button" disabled={working || firstRun.scored_count === 0} onClick={() => void action(`/api/projects/${projectId}/relevance/scoring/runs/${firstRun.id}/confirm`)}>Validate scoring</button>
        <HelpTooltip label="Scoring validation warning" variant="warning">{`Validation locks the ${firstRun.scored_count.toLocaleString()} currently scored records for the next step. After validation, more records cannot be added to this scored pool, and scoring cannot be resumed in this project.`}</HelpTooltip>
      </div>
    </>}
    {error && <p className={error.includes('already been scored') ? 'evidence-themes-helper' : 'setup-error'} role={error.includes('already been scored') ? undefined : 'alert'}>{error}</p>}
  </section>
    {firstRun?.confirmed_at && <RelevanceScoreFilter key={`${projectId}:${firstRun.id}`} projectId={projectId} runId={firstRun.id} setupToken={setupToken} />}
  </>
}
