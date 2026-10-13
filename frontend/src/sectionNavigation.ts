/** Last heading passed by the viewport reading line, including short final sections. */
export function sectionAtFocus(tops: number[], readingLine: number, atBottom: boolean): number {
  if (tops.length === 0) return -1
  if (atBottom) return tops.length - 1
  let active = 0
  for (let index = 0; index < tops.length; index++) {
    if (tops[index] <= readingLine) active = index
  }
  return active
}

/** Convert viewport coordinates to the actual scrolling container's coordinates. */
export function sectionScrollTop(scrollTop: number, targetTop: number, viewportTop: number, gap = 20): number {
  return Math.max(0, scrollTop + targetTop - viewportTop - gap)
}

export function scrolledToBottom(scrollTop: number, viewportHeight: number, scrollHeight: number): boolean {
  return scrollTop > 0 && scrollTop + viewportHeight >= scrollHeight - 2
}
