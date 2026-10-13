export function thresholdFromPointer(y: number, top: number, height: number): number {
  if (height <= 0) return 0
  return Math.max(0, Math.min(5, 5 - Math.round((y - top) * 5 / height)))
}

export function thresholdFromKey(value: number, key: string): number | null {
  switch (key) {
    case 'ArrowUp': case 'ArrowRight': return Math.min(5, value + 1)
    case 'ArrowDown': case 'ArrowLeft': return Math.max(0, value - 1)
    case 'PageUp': return Math.min(5, value + 2)
    case 'PageDown': return Math.max(0, value - 2)
    case 'Home': return 0
    case 'End': return 5
    default: return null
  }
}
