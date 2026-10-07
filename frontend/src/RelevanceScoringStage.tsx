import { useEffect, useState } from 'react'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import type { Job } from './JobQueue'
import { ChangeModelIcon, HelpTooltip, SectionTitle } from './ProjectElements'

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
  scored_count: number
  batch_count: number
  completed_batches: number
  remaining_batches: number
  batch_sizes: number[]
  by_score: Record<string, { count: number; sources: Record<string, number>; samples?: { source: string; source_record_id: string; title: string }[] }>
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

const scoreLabels: [string, string][] = [
  ['5', '5 · Central'], ['4', '4 · Direct'], ['3', '3 · Potentially useful'],
  ['2', '2 · Tangential'], ['1', '1 · Remote background'], ['0', '0 · Unrelated'],
  ['not_assessable', 'Not assessable'],
]

function price(value: Cost): string {
  if (value.status !== 'estimated' || value.usd === null) return 'Cost unavailable for this exact model'
  return `Est. $${value.usd < 0.01 ? value.usd.toFixed(4) : value.usd.toFixed(2)}`
}

export function RelevanceScoringStage({ projectId, retrievalJob, promptJob, setupToken, llmSettings, onJobsChanged, onOpenSettings }: Props) {
  const [count, setCount] = useState(100)
  const [seed, setSeed] = useState(12345)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [runsState, setRunsState] = useState<{ projectId: string; runs: Run[] } | null>(null)
  const [error, setError] = useState('')
  const [working, setWorking] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const runsLoaded = runsState?.projectId === projectId
  const runs = runsLoaded ? runsState.runs : []
  const firstRun = runs[0]
  const hasRun = runs.length > 0
  const selectedProvider = llmSettings.providers.find(item => item.id === llmSettings.selected_provider)
  const readyPreview = runsLoaded && !hasRun && preview?.requested_count === count && preview.seed === seed
    && preview.provider === llmSettings.selected_provider && preview.model === llmSettings.selected_model
    ? preview : null

  useEffect(() => {
    let mounted = true
    const refresh = async () => {
      try {
        const response = await fetch(`/api/projects/${projectId}/relevance/scoring/runs`)
        if (response.ok && mounted) setRunsState({ projectId, runs: await response.json() as Run[] })
      } catch { /* Keep the last saved progress visible during a transient disconnect. */ }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 2000)
    return () => { mounted = false; window.clearInterval(timer) }
  }, [projectId])

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
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: body ? JSON.stringify(body) : undefined,
      })
      if (!response.ok) throw new Error(await readApiError(response))
      setPreview(null)
      setConfirming(false)
      const refreshed = await fetch(`/api/projects/${projectId}/relevance/scoring/runs`)
      if (refreshed.ok) setRunsState({ projectId, runs: await refreshed.json() as Run[] })
      await onJobsChanged()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'The scoring action failed.') }
    finally { setWorking(false) }
  }

  return <section className="project-section relevance-scoring">
    <SectionTitle help="Score distinct saved source records for relevance only, in bounded API batches. Choose a record count to control expense; the seed makes the query-and-collection-balanced selection repeatable. You can pause between requests and resume saved progress. This is not study-quality assessment.">Score retrieved records</SectionTitle>
    {!runsLoaded && <p className="evidence-themes-helper">Loading scoring status…</p>}
    {runsLoaded && <>
      <div className="relevance-controls">
        <label><span className="relevance-control-label">Records to score <HelpTooltip label="Records to score help">Choose how many distinct source records the single scoring run will include. This selection is locked once scoring starts.</HelpTooltip></span><input type="number" min={1} max={100000} value={firstRun?.selected_count ?? count} disabled={hasRun} onChange={event => { setPreview(null); setCount(Number(event.target.value)) }} /></label>
        <label><span className="relevance-control-label">Selection seed <HelpTooltip label="Scoring selection seed help">Makes the balanced selection reproducible. The exact selected records and algorithm version are saved when the run starts.</HelpTooltip></span><input type="number" min={0} max={2147483647} value={firstRun?.seed ?? seed} disabled={hasRun} onChange={event => { setPreview(null); setSeed(Number(event.target.value)) }} /></label>
        {!hasRun && <button className="text-button" type="button" onClick={() => { setPreview(null); setSeed(Math.floor(Math.random() * 2147483647)) }}>Generate seed</button>}
      </div>
      {!hasRun && <>{readyPreview && <div className="relevance-preview"><strong>{readyPreview.selected_count.toLocaleString()} of {readyPreview.available_unscored.toLocaleString()} unscored source records selected</strong><p>{readyPreview.batch_sizes.length} batches · up to {Math.max(...readyPreview.batch_sizes)} records per batch</p></div>}
      <div className={`llm-job-provider ${confirming ? 'llm-job-provider--confirming' : ''}`}>
        <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span><button className="model-change-button" type="button" onClick={onOpenSettings} title="Change model" aria-label="Change model for this job"><ChangeModelIcon /></button></div><strong>{llmSettings.configured ? `${selectedProvider?.display_name} · ${llmSettings.selected_model}` : 'Not configured'}</strong></div>
        {confirming && readyPreview ? <div className="job-confirmation job-confirmation--inline"><p>Start scoring {readyPreview.selected_count.toLocaleString()} selected records in {readyPreview.batch_sizes.length} batches? The prompt, selection, provider, and model will be saved with the run.</p><div><button className="primary-button" type="button" disabled={working} onClick={() => void action(`/api/projects/${projectId}/relevance/scoring/runs`, { retrieval_job_id: retrievalJob.id, prompt_job_id: promptJob.id, count, seed, expected_manifest_sha256: readyPreview.manifest_sha256, expected_prompt_artifact_id: readyPreview.prompt_artifact_id, expected_provider: readyPreview.provider, expected_model: readyPreview.model })}>{working ? 'Starting…' : 'Confirm and start'}</button><button className="text-button" type="button" onClick={() => setConfirming(false)}>Cancel</button></div></div> : <button className="primary-button model-job-start" type="button" disabled={working || !llmSettings.configured || !readyPreview?.provider || !readyPreview.model} onClick={() => setConfirming(true)}>Start relevance scoring</button>}
      </div>
      </>}
    </>}
    {runs.map(run => <div className="relevance-scoring-run" key={run.id}>
      {run.jobs.map(job => <span id={`job-output-${job.id}`} key={job.id} />)}
      <div className="active-job-heading"><strong>{run.status === 'completed' ? 'Scoring completed' : run.status === 'paused' ? 'Scoring paused' : run.status === 'failed' ? 'Scoring stopped on an error' : run.stop_requested ? 'Pausing after the current request' : 'Scoring in progress'}</strong><span>{run.provider === 'openai' ? 'OpenAI' : 'Anthropic'} · {run.model}</span></div>
      <p>{run.scored_count.toLocaleString()} of {run.selected_count.toLocaleString()} records scored · {run.completed_batches} of {run.batch_count} batches completed</p>
      <div className="relevance-progress-track" role="progressbar" aria-label="Records scored" aria-valuemin={0} aria-valuemax={run.selected_count} aria-valuenow={run.scored_count}><div style={{ width: `${100 * run.scored_count / run.selected_count}%` }} /></div>
      <p>{(run.selected_count - run.scored_count).toLocaleString()} records and {run.remaining_batches} batches remaining · {run.total_tokens.toLocaleString()} reported tokens{run.estimated_cost_usd > 0 ? ` · Est. $${run.estimated_cost_usd.toFixed(4)} so far` : ''}</p>
      {run.completed_batches >= 1 && run.remaining_batches > 0 && (run.total_tokens > 0
        ? <p>Estimated remaining usage: ~{run.remaining_token_estimate.toLocaleString()} tokens · {price(run.remaining_cost)} remaining</p>
        : <p>Remaining usage estimate unavailable: the provider has not reported token usage.</p>)}
      <div className="relevance-batch-status" role="status">{run.status === 'running' && <span className="relevance-spinner" aria-hidden="true" />}{run.status === 'completed' ? 'All batches complete' : run.status === 'failed' ? `Batch ${run.completed_batches + 1}/${run.batch_count} failed` : run.status === 'paused' ? `Paused before batch ${run.completed_batches + 1}/${run.batch_count}` : run.stop_requested ? `Finishing batch ${run.completed_batches + 1}/${run.batch_count}, then pausing` : `Waiting for batch ${run.completed_batches + 1}/${run.batch_count}`}</div>
      {run.status === 'failed' && <p className="setup-error">{[...run.jobs].reverse().find(job => job.batch_index === run.completed_batches && job.status === 'failed')?.error ?? 'The batch did not complete.'}</p>}
      <div className="relevance-score-list">{scoreLabels.map(([key, label]) => { const item = run.by_score[key]; return <div className="relevance-score-row retrieval-tooltip-target" key={key} tabIndex={0} aria-label={`${label}, ${item?.count ?? 0} records; focus for sample records`}><strong>{label}</strong><span className="relevance-score-sources">{item && Object.entries(item.sources).sort().map(([source, amount]) => `${source} ${amount}`).join(' · ')}</span><span className="relevance-score-count">{item?.count ?? 0}</span><div className="retrieval-data-tooltip relevance-score-tooltip" role="tooltip"><strong>Sample records</strong>{item?.samples?.length ? <ul>{item.samples.map(sample => <li key={`${sample.source}:${sample.source_record_id}`}>{sample.title} <small>({sample.source}:{sample.source_record_id})</small></li>)}</ul> : <p>No records scored here yet.</p>}</div></div> })}</div>
      {run.status === 'running' && !run.stop_requested && <button className="text-button" type="button" disabled={working} onClick={() => void action(`/api/projects/${projectId}/relevance/scoring/runs/${run.id}/pause`)}>Pause after current request</button>}
      {(run.status === 'paused' || run.status === 'failed') && <button className="primary-button" type="button" disabled={working} onClick={() => void action(`/api/projects/${projectId}/relevance/scoring/runs/${run.id}/resume`)}>Resume remaining records</button>}
    </div>)}
    {error && <p className={error.includes('already been scored') ? 'evidence-themes-helper' : 'setup-error'} role={error.includes('already been scored') ? undefined : 'alert'}>{error}</p>}
  </section>
}
