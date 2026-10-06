import { useEffect, useState } from 'react'
import { readApiError } from './apiClient'
import type { LLMSettings } from './LLMConfiguration'
import { JobElapsedTime, JobStatusLabel, type Job } from './JobQueue'
import { jobCostLabel } from './jobCost'
import { ChangeModelIcon, EditableField, HelpTooltip, JobPromptDisclosure, PromptToggleButton, SectionTitle } from './ProjectElements'

type RecordSample = {
  source: string
  source_record_id: string
  title: string | null
  abstract: string | null
  author_string: string | null
  journal_title: string | null
  publication_date: string | null
  queries: { id: string; title: string }[]
}
type Cost = { status: string; usd: number | null; source_url: string | null; captured_on: string | null }
type Preview = {
  provider: 'openai' | 'anthropic' | null
  model: string | null
  algorithm_version: string
  available_distinct_source_records: number
  scoring_limit: number | null
  calibration_count: number
  seed: number
  selected_manifest_sha256: string
  calibration_records: RecordSample[]
  selected_by_collection: { source: string; count: number }[]
  selected_by_query: { id: string; title: string; count: number }[]
  calibration_input_tokens_estimate: number
  compact_calibration_input_tokens_estimate: number
  estimated_calibration_output_tokens: number
  prompt_generation_input_tokens_estimate: number
  estimated_prompt_generation_output_tokens: number
  estimated_scoring_input_tokens: number
  estimated_scoring_output_tokens: number
  calibration_cost: Cost
  compact_calibration_cost: Cost
  prompt_generation_cost: Cost
  scoring_cost: Cost
  per_1000_input_tokens_estimate: number
  per_1000_output_tokens_estimate: number
  per_1000_cost: Cost
}
type Decision = { source: string; source_record_id: string; outcome: number | 'not_assessable'; reason: string }
type GeneratedPrompt = { schema_version: 1; scoring_prompt: string; sample_observations: string[] }

type Props = {
  projectId: string
  retrievalJob: Job
  promptJob: Job | null
  calibrationJob: Job | null
  setupToken: string
  llmSettings: LLMSettings
  nowMilliseconds: number
  onJobsChanged: () => Promise<void>
  onOpenSettings: () => void
}

function costLabel(cost: Cost) {
  if (cost.status !== 'estimated' || cost.usd === null) return 'Cost unavailable for this exact model'
  if (cost.usd > 0 && cost.usd < 0.0001) return '<$0.0001 USD (estimate)'
  return `~$${cost.usd < 0.01 ? cost.usd.toFixed(4) : cost.usd.toFixed(2)} USD`
}

export function RelevancePreparationStage({ projectId, retrievalJob, promptJob, calibrationJob, setupToken, llmSettings, nowMilliseconds, onJobsChanged, onOpenSettings }: Props) {
  const [instructions, setInstructions] = useState('')
  const [editedInstructions, setEditedInstructions] = useState('')
  const [isPromptVisible, setIsPromptVisible] = useState(false)
  const [isEditingInstructions, setIsEditingInstructions] = useState(false)
  const [isConfirmingJob, setIsConfirmingJob] = useState(false)
  const [generatedPrompt, setGeneratedPrompt] = useState<GeneratedPrompt | null>(null)
  const [isEditingOutput, setIsEditingOutput] = useState(false)
  const [isShowingOriginal, setIsShowingOriginal] = useState(false)
  const [editedOutput, setEditedOutput] = useState('')
  const [isSavingOutput, setIsSavingOutput] = useState(false)
  const [legacyScoringLimit, setLegacyScoringLimit] = useState<number | null>(null)
  const [calibrationCount, setCalibrationCount] = useState(12)
  const [seed, setSeed] = useState(12345)
  const [preparedPreview, setPreview] = useState<{ requestKey: string; value: Preview } | null>(null)
  const [decisions, setDecisions] = useState<Decision[] | null>(null)
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const requestHeaders = { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken }
  const calibrationSource = (() => {
    try { return calibrationJob?.workflow_input_snapshot_json ? JSON.parse(calibrationJob.workflow_input_snapshot_json) as { generated_prompt_source?: { job_id: string } | null } : null }
    catch { return null }
  })()
  const currentCalibrationJob = promptJob === null || calibrationSource?.generated_prompt_source?.job_id === promptJob.id ? calibrationJob : null

  useEffect(() => {
    const controller = new AbortController()
    const saved = (() => {
      try { return promptJob?.workflow_input_snapshot_json ? JSON.parse(promptJob.workflow_input_snapshot_json) as { generation_prompt: string; scoring_limit: number | null; calibration_records: RecordSample[]; seed: number } : null }
      catch { return null }
    })()
    void fetch('/api/relevance/defaults', { signal: controller.signal })
      .then(response => response.json() as Promise<{ relevance_prompt_generation_prompt: string }>)
      .then(value => {
        setInstructions(saved?.generation_prompt ?? value.relevance_prompt_generation_prompt)
        if (saved) { setLegacyScoringLimit(saved.scoring_limit); setCalibrationCount(saved.calibration_records.length); setSeed(saved.seed) }
        else setLegacyScoringLimit(null)
      })
      .catch(() => setError('The default relevance instructions could not be loaded.'))
    return () => controller.abort()
  }, [promptJob?.id, promptJob?.workflow_input_snapshot_json])

  useEffect(() => {
    if (promptJob?.status !== 'completed') return
    const controller = new AbortController()
    void fetch(`/api/jobs/${promptJob.id}/relevance-prompt-generation`, { signal: controller.signal })
      .then(response => response.ok ? response.json() as Promise<GeneratedPrompt> : Promise.reject(new Error('Generated prompt unavailable.')))
      .then(value => { setGeneratedPrompt(value); setPreview(null) })
      .catch(() => { if (!controller.signal.aborted) setError('The generated scoring prompt could not be loaded.') })
    return () => controller.abort()
  }, [promptJob?.id, promptJob?.status, promptJob?.effective_output_version])

  useEffect(() => {
    if (currentCalibrationJob?.status !== 'completed') return
    const controller = new AbortController()
    void fetch(`/api/jobs/${currentCalibrationJob.id}/relevance-calibration`, { signal: controller.signal })
      .then(response => response.ok ? response.json() as Promise<{ calibration: Decision[] }> : Promise.reject(new Error('Calibration output unavailable.')))
      .then(value => setDecisions(value.calibration))
      .catch(() => { if (!controller.signal.aborted) setError('The calibration output could not be loaded.') })
    return () => controller.abort()
  }, [currentCalibrationJob?.id, currentCalibrationJob?.status])

  const effectiveInstructions = promptJob?.status === 'completed' ? generatedPrompt?.scoring_prompt ?? '' : instructions
  const previewKey = JSON.stringify([projectId, retrievalJob.id, legacyScoringLimit, calibrationCount,
    seed, effectiveInstructions, llmSettings.selected_provider, llmSettings.selected_model])
  const preview = preparedPreview?.requestKey === previewKey ? preparedPreview.value : null

  const changeInstructions = (value: string) => { setInstructions(value); setPreview(null); setIsConfirmingJob(false) }
  const changeCount = (value: number) => { setCalibrationCount(value); setPreview(null); setIsConfirmingJob(false) }
  const changeSeed = (value: number) => { setSeed(value); setPreview(null); setIsConfirmingJob(false) }
  const active = promptJob?.status === 'pending' || promptJob?.status === 'awaiting_response'
  const canGenerate = promptJob === null || promptJob.status === 'failed' || promptJob.status === 'cancelled'
  const calibrationActive = currentCalibrationJob?.status === 'pending' || currentCalibrationJob?.status === 'awaiting_response'
  const canCalibrate = currentCalibrationJob === null || currentCalibrationJob.status === 'failed' || currentCalibrationJob.status === 'cancelled'
  useEffect(() => {
    if (active || calibrationActive || isEditingInstructions || isEditingOutput
      || effectiveInstructions.length < 40 || !Number.isInteger(calibrationCount)
      || calibrationCount < 1 || calibrationCount > 30 || !Number.isInteger(seed)
      || seed < 0 || seed > 2147483647) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void fetch(`/api/projects/${projectId}/relevance/preview`, {
        method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-Jeromes-Lab-Setup-Token': setupToken },
        body: JSON.stringify({ retrieval_job_id: retrievalJob.id, scoring_limit: legacyScoringLimit, calibration_count: calibrationCount, seed, instructions: effectiveInstructions }),
      })
        .then(async response => {
          if (!response.ok) throw new Error(await readApiError(response))
          return response.json() as Promise<Preview>
        })
        .then(value => { if (!controller.signal.aborted) { setPreview({ requestKey: previewKey, value }); setError(null) } })
        .catch(previewError => {
          if (!controller.signal.aborted) setError(previewError instanceof Error ? previewError.message : 'The sample could not be prepared.')
        })
    }, 350)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [projectId, retrievalJob.id, setupToken, legacyScoringLimit, calibrationCount, seed, effectiveInstructions, previewKey,
    llmSettings.selected_provider, llmSettings.selected_model, active, calibrationActive,
    isEditingInstructions, isEditingOutput])

  const generatePrompt = async () => {
    if (preview?.provider == null || preview.model == null || !canGenerate) return
    setIsStarting(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${projectId}/relevance/prompt-generation/jobs`, {
        method: 'POST', headers: requestHeaders,
        body: JSON.stringify({ retrieval_job_id: retrievalJob.id, scoring_limit: preview.scoring_limit, calibration_count: preview.calibration_count, seed: preview.seed, instructions, expected_manifest_sha256: preview.selected_manifest_sha256, expected_provider: preview.provider, expected_model: preview.model }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
    } catch (startError: unknown) {
      setError(startError instanceof Error ? startError.message : 'Scoring-prompt generation could not be queued.')
    } finally { setIsStarting(false) }
  }

  const saveGeneratedPrompt = async () => {
    if (!promptJob?.effective_output_version) return
    setIsSavingOutput(true); setError(null)
    try {
      const response = await fetch(`/api/jobs/${promptJob.id}/relevance-prompt-generation`, {
        method: 'PATCH', headers: requestHeaders,
        body: JSON.stringify({ scoring_prompt: editedOutput, base_version: promptJob.effective_output_version }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      setIsEditingOutput(false); setPreview(null)
      await onJobsChanged()
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The scoring prompt could not be saved.')
    } finally { setIsSavingOutput(false) }
  }

  const calibrate = async () => {
    if (preview?.provider == null || preview.model == null) return
    setIsStarting(true); setError(null)
    try {
      const response = await fetch(`/api/projects/${projectId}/relevance/calibration/jobs`, {
        method: 'POST', headers: requestHeaders,
        body: JSON.stringify({ retrieval_job_id: retrievalJob.id, scoring_limit: preview.scoring_limit, calibration_count: preview.calibration_count, seed: preview.seed, instructions: effectiveInstructions, expected_manifest_sha256: preview.selected_manifest_sha256, expected_provider: preview.provider, expected_model: preview.model, prompt_generation_job_id: promptJob?.id }),
      })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
    } catch (startError: unknown) {
      setError(startError instanceof Error ? startError.message : 'Calibration could not be queued.')
    } finally { setIsStarting(false) }
  }

  const cancel = async () => {
    if (!promptJob) return
    setError(null)
    try {
      const response = await fetch(`/api/jobs/${promptJob.id}/cancel`, { method: 'POST', headers: { 'X-Jeromes-Lab-Setup-Token': setupToken } })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
    } catch (cancelError: unknown) { setError(cancelError instanceof Error ? cancelError.message : 'The queued generation job could not be cancelled.') }
  }

  const cancelCalibration = async () => {
    if (!currentCalibrationJob) return
    setError(null)
    try {
      const response = await fetch(`/api/jobs/${currentCalibrationJob.id}/cancel`, { method: 'POST', headers: { 'X-Jeromes-Lab-Setup-Token': setupToken } })
      if (!response.ok) throw new Error(await readApiError(response))
      await onJobsChanged()
    } catch (cancelError: unknown) { setError(cancelError instanceof Error ? cancelError.message : 'The queued calibration could not be cancelled.') }
  }

  return <section className="project-section relevance-preparation">
    <SectionTitle help="Generate a compact relevance-scoring prompt from the approved investigation and a seeded sample of retrieved titles and abstracts. Review the generated prompt before optional calibration or later batch scoring. This step does not score the full record set or judge study quality. Not assessable is separate from zero.">Prepare relevance scoring</SectionTitle>
    <div className="relevance-controls">
      <label><span className="relevance-control-label">Prompt-design sample <HelpTooltip label="Prompt-design sample help">How many distinct source records the model examines to tailor the prompt. This same sample is used for the per-1,000-report cost estimate and optional calibration.</HelpTooltip></span><input type="number" min={1} max={30} value={calibrationCount} disabled={!canGenerate} onChange={event => changeCount(Number(event.target.value))} /></label>
      <label><span className="relevance-control-label">Reproducible selection seed <HelpTooltip label="Selection seed help">This number makes the balanced prompt-design sample repeatable. Changing it can select different records.</HelpTooltip></span><input type="number" min={0} max={2147483647} value={seed} disabled={!canGenerate} onChange={event => changeSeed(Number(event.target.value))} /></label>
      {canGenerate && <button className="text-button" type="button" onClick={() => changeSeed(Math.floor(Math.random() * 2147483647))}>Generate seed</button>}
    </div>
    {preview && <div className="relevance-preview">
      <strong>{preview.calibration_count.toLocaleString()} of {preview.available_distinct_source_records.toLocaleString()} distinct source records in the prompt-design sample</strong>
      <p>Seed {preview.seed} · {preview.algorithm_version}</p>
      <p>Selected model: {preview.provider ?? 'Not configured'} · {preview.model ?? 'No model selected'}</p>
      <details className="relevance-coverage"><summary>Inspect selection coverage</summary><ol>{preview.calibration_records.map(record => <li key={`${record.source}:${record.source_record_id}`}><span className="relevance-sample-title retrieval-tooltip-target" tabIndex={0}>{record.title || 'Untitled record'}<span className="retrieval-data-tooltip" role="tooltip">Date: {record.publication_date || 'Not recorded'}<br />Author: {record.author_string || 'Not recorded'}<br />Journal: {record.journal_title || 'Not recorded'}<br />Abstract: {record.abstract ? 'Available' : 'Not saved'}<br />Source collection: {record.source}<br />Found by: {record.queries.map(query => query.title).join(', ') || 'No query recorded'}</span></span></li>)}</ol></details>
      <p>Sample-ID manifest SHA-256: <code>{preview.selected_manifest_sha256}</code></p>
    </div>}
    <div id={promptJob ? `job-card-${promptJob.id}` : undefined} className={`llm-job-provider ${isConfirmingJob ? 'llm-job-provider--confirming' : ''} ${active ? 'llm-job-provider--active' : ''}`}>
      {promptJob?.status === 'completed' ? <div className="completed-job-card"><span>Scoring-prompt generation</span><JobStatusLabel status="completed" /></div> : <>
        <div className="llm-job-model"><div className="llm-job-model-label"><span>Model for this job</span>{!active && <button className="model-change-button" type="button" onClick={onOpenSettings} title="Change model" aria-label="Change model for future jobs"><ChangeModelIcon /></button>}</div><strong>{active ? `${promptJob?.provider} · ${promptJob?.model}` : llmSettings.configured ? `${llmSettings.providers.find(provider => provider.id === llmSettings.selected_provider)?.display_name} · ${llmSettings.selected_model}` : 'Not configured'}</strong></div>
        {canGenerate && !isConfirmingJob && <button className="primary-button model-job-start" type="button" disabled={!preview || !llmSettings.configured || isEditingInstructions} onClick={() => setIsConfirmingJob(true)}>{promptJob ? 'Retry prompt generation' : 'Generate scoring prompt'}</button>}
        {canGenerate && isConfirmingJob && <div className="job-confirmation job-confirmation--inline"><p>This snapshots the approved investigation, seeded sample, instructions, provider, and model. Only prompt generation starts; no records are scored in bulk.</p><div><button className="primary-button" type="button" disabled={isStarting || !preview} onClick={() => void generatePrompt()}>{isStarting ? 'Queueing…' : 'Confirm and start'}</button><button className="text-button" type="button" onClick={() => setIsConfirmingJob(false)}>Cancel</button></div></div>}
        {active && promptJob && <div className="active-job-summary"><div className="active-job-heading"><strong>Scoring-prompt generation</strong><div><JobStatusLabel status={promptJob.status} /><JobElapsedTime job={promptJob} nowMilliseconds={nowMilliseconds} /></div></div>{promptJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancel()}>Cancel queued job</button>}</div>}
        {promptJob && !active && <JobStatusLabel status={promptJob.status} />}
      </>}
      <PromptToggleButton isVisible={isPromptVisible} onToggle={() => { if (isPromptVisible) setIsEditingInstructions(false); setIsPromptVisible(!isPromptVisible) }} />
    </div>
    <JobPromptDisclosure visible={isPromptVisible} isEditing={isEditingInstructions} canEdit={canGenerate} prompt={canGenerate ? instructions : promptJob?.prompt_snapshot ?? instructions} editedPrompt={editedInstructions} isSaving={false} ariaLabel="Relevance-prompt generation instructions" editLabel="Edit scoring-prompt generation instructions" onEditedPromptChange={setEditedInstructions} onEdit={() => { setEditedInstructions(instructions); setIsEditingInstructions(true) }} onCancel={() => setIsEditingInstructions(false)} onSave={() => { changeInstructions(editedInstructions); setIsEditingInstructions(false) }} />
    {promptJob?.error && <p className="setup-error">{promptJob.error}</p>}
    {generatedPrompt && promptJob?.status === 'completed' && <div id={`job-output-${promptJob.id}`} className="job-output-section relevance-generated-output"><h3>Generated relevance-scoring prompt</h3><p className="evidence-themes-helper">Review these standalone rules before calibrating them on the seeded sample. The full charter and plan were used to generate this prompt, but will not be repeated in each future scoring batch.</p>{promptJob.output_was_edited && <button className="text-button" type="button" onClick={() => setIsShowingOriginal(!isShowingOriginal)}>{isShowingOriginal ? 'Show edited version' : 'Show original output'}</button>}<EditableField variant="multiline" isEditing={isEditingOutput} canEdit={!currentCalibrationJob && !isShowingOriginal && promptJob.effective_output_version !== null} display={<pre className="question-detailing-prompt">{isShowingOriginal ? promptJob.original_output_markdown : generatedPrompt.scoring_prompt}</pre>} editor={<textarea value={editedOutput} onChange={event => setEditedOutput(event.target.value)} aria-label="Edit generated relevance-scoring prompt" maxLength={12000} />} onEdit={() => { setEditedOutput(generatedPrompt.scoring_prompt); setIsEditingOutput(true) }} editLabel="Edit generated scoring prompt" actions={<><button className="primary-button" type="button" disabled={isSavingOutput || editedOutput.trim().length < 100} onClick={() => void saveGeneratedPrompt()}>{isSavingOutput ? 'Saving…' : 'Save edited version'}</button><button className="text-button" type="button" disabled={isSavingOutput} onClick={() => setIsEditingOutput(false)}>Cancel</button></>} /><details><summary>How the sample informed the original draft</summary><ul>{generatedPrompt.sample_observations.map((observation, index) => <li key={index}>{observation}</li>)}</ul></details><p>{promptJob.total_tokens !== null ? `${promptJob.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {promptJob.duration_ms !== null ? `${(promptJob.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · {jobCostLabel(promptJob)}</p></div>}
    {generatedPrompt && promptJob?.status === 'completed' && preview && <div className="relevance-per-1000-estimate"><strong>Estimated scoring cost per 1,000 reports</strong><p>~{(preview.per_1000_input_tokens_estimate + preview.per_1000_output_tokens_estimate).toLocaleString()} tokens ({preview.per_1000_input_tokens_estimate.toLocaleString()} input + {preview.per_1000_output_tokens_estimate.toLocaleString()} output) · {costLabel(preview.per_1000_cost)}</p><small>Projected from the same {preview.calibration_count} sampled reports and the current scoring prompt, assuming 10 reports per request and 100 output tokens per report. Actual usage and charges may differ.</small>{preview.per_1000_cost.source_url && <p><a href={preview.per_1000_cost.source_url} target="_blank" rel="noreferrer">OpenAI Standard API rate</a> checked {preview.per_1000_cost.captured_on}.</p>}</div>}
    {generatedPrompt && canCalibrate && <div className="query-actions"><button className="primary-button" type="button" disabled={!preview || isStarting || isEditingOutput || !llmSettings.configured} onClick={() => void calibrate()}>{isStarting ? 'Queueing…' : currentCalibrationJob ? 'Retry sample calibration' : 'Calibrate generated prompt on sample'}</button>{isShowingOriginal && <small>Calibration uses the active edited version shown above when you switch back.</small>}</div>}
    {currentCalibrationJob && <div id={`job-card-${currentCalibrationJob.id}`} className="llm-job-provider relevance-calibration-status"><strong>Sample calibration · {currentCalibrationJob.provider} · {currentCalibrationJob.model}</strong><JobStatusLabel status={currentCalibrationJob.status} />{calibrationActive && <JobElapsedTime job={currentCalibrationJob} nowMilliseconds={nowMilliseconds} />}{currentCalibrationJob.status === 'pending' && <button className="text-button" type="button" onClick={() => void cancelCalibration()}>Cancel queued calibration</button>}</div>}
    {currentCalibrationJob?.error && <p className="setup-error">{currentCalibrationJob.error}</p>}
    {decisions && <div id={currentCalibrationJob ? `job-output-${currentCalibrationJob.id}` : undefined} className="relevance-calibration-output"><h3>Calibration results</h3><p>This pilot tests how the model interprets the rubric. These records are not a completed full screening run.</p>{decisions.map(decision => <article key={`${decision.source}:${decision.source_record_id}`}><strong>{decision.source}:{decision.source_record_id} — {decision.outcome === 'not_assessable' ? 'Not assessable' : `Relevance ${decision.outcome}/5`}</strong><p>{decision.reason}</p></article>)}{currentCalibrationJob && <p>{currentCalibrationJob.total_tokens !== null ? `${currentCalibrationJob.total_tokens.toLocaleString()} tokens` : 'Tokens unavailable'} · {currentCalibrationJob.duration_ms !== null ? `${(currentCalibrationJob.duration_ms / 1000).toFixed(1)} s` : 'Time unavailable'} · {jobCostLabel(currentCalibrationJob)}</p>}</div>}
    {error && <p className="setup-error" role="alert">{error}</p>}
  </section>
}
