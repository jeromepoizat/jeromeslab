import { useState, type ReactNode } from 'react'

export function HelpTooltip({ children, label = 'Section help' }: { children: string; label?: string }) {
  return <span className="section-help" tabIndex={0} aria-label={label}>?<span className="section-help-tooltip" role="tooltip">{children}</span></span>
}

export function SectionTitle({ children, help }: { children: string; help: string }) {
  return <div className="section-title"><h2>{children}</h2><HelpTooltip>{help}</HelpTooltip></div>
}

export function ChangeModelIcon() {
  return <svg aria-hidden="true" viewBox="0 0 20 20"><path d="M4 5h12M4 10h12M4 15h12" /><circle cx="7" cy="5" r="1.7" /><circle cx="13" cy="10" r="1.7" /><circle cx="8" cy="15" r="1.7" /></svg>
}

export function PromptToggleButton({ isVisible, onToggle }: { isVisible: boolean; onToggle: () => void }) {
  return <button className="job-prompt-toggle" type="button" aria-expanded={isVisible} onClick={onToggle}>{isVisible ? 'Hide prompt' : 'Show prompt'}</button>
}

type JobPromptDisclosureProps = {
  visible: boolean
  isEditing: boolean
  canEdit: boolean
  prompt: string
  editedPrompt: string
  isSaving: boolean
  ariaLabel: string
  editLabel: string
  notice?: string
  onEditedPromptChange: (value: string) => void
  onEdit: () => void
  onCancel: () => void
  onSave: () => void
}

/** Shared advanced-prompt field used directly beneath every LLM job card. */
export function JobPromptDisclosure({ visible, isEditing, canEdit, prompt, editedPrompt, isSaving, ariaLabel, editLabel, notice, onEditedPromptChange, onEdit, onCancel, onSave }: JobPromptDisclosureProps) {
  if (!visible) return null
  return <div className="job-prompt-disclosure">
    {notice && <p className="charter-view-notice">{notice}</p>}
    <EditableField
      variant="multiline"
      isEditing={isEditing && canEdit}
      canEdit={canEdit}
      display={<pre className="question-detailing-prompt">{prompt}</pre>}
      editor={<textarea value={editedPrompt} onChange={event => onEditedPromptChange(event.target.value)} aria-label={ariaLabel} disabled={isSaving} />}
      onEdit={onEdit}
      editLabel={editLabel}
      actions={<>
        <button className="primary-button" type="button" disabled={isSaving || !editedPrompt.trim()} onClick={onSave}>{isSaving ? 'Saving…' : 'Save prompt'}</button>
        <button className="text-button" type="button" disabled={isSaving} onClick={onCancel}>Cancel</button>
      </>}
    />
  </div>
}

type EditableFieldProps = {
  variant: 'single-line' | 'adaptive' | 'multiline'
  isEditing: boolean
  canEdit?: boolean
  display: ReactNode
  editor: ReactNode
  actions: ReactNode
  footer?: ReactNode
  sideActions?: ReactNode
  onEdit: () => void
  editLabel: string
}

export function EditableField({ variant, isEditing, canEdit = true, display, editor, actions, footer, sideActions, onEdit, editLabel }: EditableFieldProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  return <div className={`editable-field editable-field--${variant} ${isExpanded ? 'editable-field--expanded' : ''}`}>
    <div className="editable-box-row">
      <div className={`project-input-box ${isEditing ? 'project-input-box--editing' : ''}`}>
        {isEditing ? editor : display}
      </div>
      {!isEditing && sideActions && <div className="editable-side-actions">{sideActions}</div>}
      {!isEditing && canEdit && <button className="edit-icon" type="button" title={editLabel} aria-label={editLabel} onClick={onEdit}>✎</button>}
      {variant === 'multiline' && <button className="expand-handle" type="button" title={isExpanded ? 'Collapse input' : 'Expand input to show all content'} aria-label={isExpanded ? 'Collapse input' : 'Expand input to show all content'} aria-expanded={isExpanded} onClick={() => setIsExpanded(!isExpanded)}><svg aria-hidden="true" viewBox="0 0 16 10"><path d={isExpanded ? 'M2 8 8 2l6 6' : 'm2 2 6 6 6-6'} /></svg></button>}
    </div>
    {footer && <div className="editable-footer">{footer}</div>}
    <div className="edit-controls">{isEditing ? actions : null}</div>
  </div>
}
