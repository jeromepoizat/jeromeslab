import { useRef, type PointerEvent } from 'react'
import { thresholdFromKey, thresholdFromPointer } from './scoreThreshold'

/** Discrete accessible scale aligned with the six score rows, independent of browser range styling. */
export function ScoreThresholdControl({ value, disabled, onChange }: {
  value: number; disabled: boolean; onChange: (value: number) => void
}) {
  const railRef = useRef<HTMLDivElement | null>(null)
  const position = (5 - value) * 20
  function selectAtPointer(event: PointerEvent<HTMLDivElement>) {
    if (disabled || !railRef.current) return
    const rail = railRef.current.getBoundingClientRect()
    onChange(thresholdFromPointer(event.clientY, rail.top, rail.height))
  }
  return <div className={`score-threshold-control ${disabled ? 'score-threshold-control--disabled' : ''}`}
    role="slider" aria-label="Minimum inclusion score" aria-orientation="vertical"
    aria-valuemin={0} aria-valuemax={5} aria-valuenow={value} aria-valuetext={`Include scores ${value} to 5`}
    aria-disabled={disabled} tabIndex={disabled ? -1 : 0}
    onPointerDown={event => {
      if (disabled || event.button !== 0 || !event.isPrimary) return
      event.currentTarget.focus()
      event.currentTarget.setPointerCapture(event.pointerId)
      selectAtPointer(event)
    }}
    onPointerMove={event => { if (event.currentTarget.hasPointerCapture(event.pointerId)) selectAtPointer(event) }}
    onPointerUp={event => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId) }}
    onKeyDown={event => {
      if (disabled) return
      const next = thresholdFromKey(value, event.key)
      if (next !== null) { event.preventDefault(); onChange(next) }
    }}>
    <div className="score-threshold-rail" ref={railRef} aria-hidden="true">
      <div className="score-threshold-included" style={{ height: `${position}%` }} />
      {[5, 4, 3, 2, 1, 0].map(score => <span key={score} className={`score-threshold-point ${score >= value ? 'score-threshold-point--included' : ''}`} style={{ top: `${(5 - score) * 20}%` }} />)}
      <span className="score-threshold-arrow" style={{ top: `${position}%` }}>{value}</span>
    </div>
  </div>
}
