import { useState } from 'react'
import { type ScopeAnswer, type ScopeAnswers, type ScopeQuestion } from './JobQueue'

type Props = {
  questions: ScopeQuestion[]
  savedAnswers: ScopeAnswers | null
  canEdit: boolean
  confirmLabel: string
  editLabel: string
  idPrefix: string
  onSave: (answers: ScopeAnswer[], isEditing: boolean) => Promise<void>
}

function initialAnswers(savedAnswers: ScopeAnswers | null): Record<string, ScopeAnswer> {
  return Object.fromEntries((savedAnswers?.answers ?? []).map(answer => [
    answer.question_id,
    { ...answer, selected_option_ids: [...answer.selected_option_ids] },
  ]))
}

export function ScopeQuestionnaire({ questions, savedAnswers, canEdit, confirmLabel, editLabel, idPrefix, onSave }: Props) {
  const [answers, setAnswers] = useState<Record<string, ScopeAnswer>>(() => initialAnswers(savedAnswers))
  const [isEditing, setIsEditing] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const answerFor = (questionId: string): ScopeAnswer => answers[questionId] ?? {
    question_id: questionId,
    selected_option_ids: [],
    note: '',
    is_unsure: false,
  }
  const replaceAnswer = (answer: ScopeAnswer) => setAnswers(current => ({ ...current, [answer.question_id]: answer }))

  const submit = async () => {
    const ordered = questions.map(question => answerFor(question.id))
    if (ordered.some(answer => !answer.is_unsure && answer.selected_option_ids.length === 0 && answer.note.trim() === '')) {
      setError('Answer every scope question, add a manual note, or choose Not sure.')
      return
    }
    setIsSubmitting(true); setError(null)
    try {
      await onSave(ordered, isEditing)
      setIsEditing(false)
    } catch (saveError: unknown) {
      setError(saveError instanceof Error ? saveError.message : 'The answers could not be saved.')
    } finally { setIsSubmitting(false) }
  }

  if (savedAnswers !== null && !isEditing) {
    return <div className="confirmed-intent confirmed-scope">
      {canEdit && <button className="intent-edit-button" type="button" title={editLabel} aria-label={editLabel} onClick={() => { setAnswers(initialAnswers(savedAnswers)); setIsEditing(true) }}>✎</button>}
      {questions.map((question, index) => {
        const answer = savedAnswers.answers.find(item => item.question_id === question.id)
        const selected = question.options.filter(option => answer?.selected_option_ids.includes(option.id))
        return <div className="confirmed-scope-answer" key={question.id}><p className="step-label">Question {index + 1}</p><h3>{question.question}</h3>{answer?.is_unsure && <p>Not sure</p>}{!answer?.is_unsure && selected.length > 0 && <ul>{selected.map(option => <li key={option.id}><strong>{option.label}</strong> — {option.description}</li>)}</ul>}{answer?.note && <p className="intent-saved-note">{answer.note}</p>}</div>
      })}
    </div>
  }

  return <form className="scope-form" onSubmit={event => { event.preventDefault(); void submit() }}>
    {questions.map((question, index) => {
      const answer = answerFor(question.id)
      const headingId = `${idPrefix}-question-${question.id}`
      return <div className="scope-question" role="group" aria-labelledby={headingId} key={question.id}><div className="scope-question-heading"><span>{index + 1}</span><h3 id={headingId}>{question.question}</h3></div><p>{question.why_it_matters}</p><div className="scope-options">
        {question.options.map(option => <label className="scope-option" key={option.id}><input type={question.selection_mode === 'single_choice' ? 'radio' : 'checkbox'} name={`scope-${question.id}`} checked={answer.selected_option_ids.includes(option.id)} disabled={answer.is_unsure} onChange={event => {
          const selected = question.selection_mode === 'single_choice' ? (event.target.checked ? [option.id] : []) : event.target.checked ? [...answer.selected_option_ids, option.id] : answer.selected_option_ids.filter(id => id !== option.id)
          replaceAnswer({ ...answer, selected_option_ids: selected, is_unsure: false })
        }} /><span><strong>{option.label}{question.recommended_option_ids?.includes(option.id) && <em className="recommended-option">Recommended</em>}</strong><small>{option.description}</small></span></label>)}
        {question.recommendation_reason && <p className="scope-recommendation"><strong>Recommendation:</strong> {question.recommendation_reason}</p>}
        <label className="scope-option scope-option--unsure"><input type="checkbox" checked={answer.is_unsure} onChange={event => replaceAnswer({ ...answer, selected_option_ids: [], is_unsure: event.target.checked })} /><span><strong>Not sure</strong><small>Preserve this uncertainty explicitly; use the note below to explain it if helpful.</small></span></label>
      </div>{answer.selected_option_ids.length > 0 && <button className="text-button scope-clear-options" type="button" onClick={() => replaceAnswer({ ...answer, selected_option_ids: [] })}>{question.selection_mode === 'single_choice' ? 'Clear selected answer' : 'Clear selected answers'}</button>}<label className="scope-note"><span>Manual answer or note</span><textarea value={answer.note} onChange={event => replaceAnswer({ ...answer, note: event.target.value })} placeholder="Add, replace, qualify, or explain uncertainty in the answer…" /></label></div>
    })}
    <div className="intent-submit"><button className="primary-button" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Saving…' : isEditing ? 'Save edited answers' : confirmLabel}</button>{isEditing && <button className="text-button" type="button" disabled={isSubmitting} onClick={() => { setAnswers(initialAnswers(savedAnswers)); setIsEditing(false); setError(null) }}>Cancel</button>}<span>{isEditing ? 'The previous answer version remains preserved.' : 'The complete answer set will be preserved as workflow input.'}</span></div>
    {error !== null && <p className="setup-error" role="alert">{error}</p>}
  </form>
}
