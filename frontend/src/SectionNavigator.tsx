import { useEffect, useId, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { scrolledToBottom, sectionAtFocus, sectionScrollTop } from './sectionNavigation'

type Section = { id: string; title: string }
type NavigationState = { projectId: string; sections: Section[]; activeId: string | null }

/** Uses shared section headings, not a parallel list of workflow-stage names. */
export function SectionNavigator({ contentRef, scrollRef, projectId, projectTag }: {
  contentRef: RefObject<HTMLElement | null>; scrollRef: RefObject<HTMLElement | null>
  projectId: string; projectTag: string
}) {
  const [expanded, setExpanded] = useState(() => window.innerWidth >= 1440)
  const [navigation, setNavigation] = useState<NavigationState | null>(null)
  const listId = useId()
  const navigationRef = useRef<HTMLElement | null>(null)
  const current = navigation?.projectId === projectId ? navigation : null

  useLayoutEffect(() => {
    const nav = navigationRef.current
    if (!expanded || !nav) return
    const fitTitles = () => {
      const links = Array.from(nav.querySelectorAll<HTMLElement>('.section-navigator-list a'))
      const titleWidth = Math.max(0, ...links.map(link => {
        const text = link.querySelector<HTMLElement>('.section-navigator-label')
        const style = getComputedStyle(link)
        return (text?.getBoundingClientRect().width ?? 0) + parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + 2
      }))
      const tag = nav.querySelector<HTMLElement>('.section-navigator-header .step-label')
      const navStyle = getComputedStyle(nav)
      const outerPadding = parseFloat(navStyle.paddingLeft) + parseFloat(navStyle.paddingRight)
      // Reserve scrollbar/header controls too, so the final width exposes every title.
      const width = Math.ceil(Math.max(titleWidth + 16, (tag?.scrollWidth ?? 0) + 44) + outerPadding)
      nav.style.setProperty('--section-navigation-width', `${width}px`)
    }
    fitTitles()
    window.addEventListener('resize', fitTitles)
    return () => window.removeEventListener('resize', fitTitles)
  }, [current?.sections, expanded, projectTag])

  useEffect(() => {
    const root = contentRef.current
    const scroller = scrollRef.current
    if (!root || !scroller) return
    let frame = 0
    const refresh = () => {
      frame = 0
      const headings = Array.from(root.querySelectorAll<HTMLElement>('[data-project-section-title]'))
        .filter(heading => heading.getClientRects().length > 0)
      const sections = headings.map(heading => ({ id: heading.id, title: heading.dataset.projectSectionTitle ?? '' }))
      const viewportTop = scroller.getBoundingClientRect().top
      const atBottom = scrolledToBottom(scroller.scrollTop, scroller.clientHeight, scroller.scrollHeight)
      const index = sectionAtFocus(headings.map(heading => heading.getBoundingClientRect().top - viewportTop), Math.min(180, scroller.clientHeight * .28), atBottom)
      const activeId = sections[index]?.id ?? null
      setNavigation(previous => {
        if (previous?.projectId === projectId && previous.activeId === activeId
          && previous.sections.length === sections.length
          && previous.sections.every((section, index) => section.id === sections[index].id && section.title === sections[index].title)) return previous
        return { projectId, sections, activeId }
      })
    }
    const scheduleRefresh = () => { if (!frame) frame = window.requestAnimationFrame(refresh) }
    const changes = new MutationObserver(scheduleRefresh)
    changes.observe(root, { subtree: true, childList: true, characterData: true })
    const sizes = new ResizeObserver(scheduleRefresh)
    sizes.observe(root)
    sizes.observe(scroller)
    scroller.addEventListener('scroll', scheduleRefresh, { passive: true })
    window.addEventListener('resize', scheduleRefresh)
    scheduleRefresh()
    return () => {
      changes.disconnect()
      sizes.disconnect()
      scroller.removeEventListener('scroll', scheduleRefresh)
      window.removeEventListener('resize', scheduleRefresh)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [contentRef, scrollRef, projectId])

  useEffect(() => {
    if (!expanded) return
    const list = document.getElementById(listId)
    const active = list?.querySelector<HTMLElement>('[aria-current="location"]')
    if (!list || !active) return
    const bounds = list.getBoundingClientRect()
    const item = active.getBoundingClientRect()
    if (item.top < bounds.top) list.scrollTop -= bounds.top - item.top
    else if (item.bottom > bounds.bottom) list.scrollTop += item.bottom - bounds.bottom
  }, [navigation?.activeId, expanded, listId])

  function goToSection(id: string) {
    const heading = document.getElementById(id)
    const scroller = scrollRef.current
    if (!heading || !scroller) return
    const target = heading.closest<HTMLElement>('.project-section') ?? heading
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    scroller.scrollTo({ top: sectionScrollTop(scroller.scrollTop, target.getBoundingClientRect().top, scroller.getBoundingClientRect().top), behavior: reduceMotion ? 'instant' : 'smooth' })
  }

  if (!current?.sections.length) return null
  return <nav ref={navigationRef} className={`section-navigator ${expanded ? 'section-navigator--expanded' : ''}`} aria-label={`${projectTag} project sections`}>
    <div className="section-navigator-header">
      {expanded && <span className="step-label">{projectTag}</span>}
      <button className="section-navigator-toggle" type="button" aria-expanded={expanded} aria-controls={listId} aria-label={expanded ? 'Collapse section navigation' : 'Expand section navigation'} title={expanded ? 'Collapse section navigation' : 'Expand section navigation'} onClick={() => setExpanded(value => !value)}>
        <svg viewBox="0 0 20 20" aria-hidden="true">{expanded ? <path d="m7 4 6 6-6 6" /> : <><path d="M7 5h10M7 10h10M7 15h10" /><path d="M3 5h.1M3 10h.1M3 15h.1" /></>}</svg>
      </button>
    </div>
    <ol className="section-navigator-list" id={listId} hidden={!expanded}>{current.sections.map(section => <li key={section.id}>
      <a href={`#${section.id}`} title={section.title} aria-current={section.id === current.activeId ? 'location' : undefined} onClick={event => { event.preventDefault(); goToSection(section.id) }}><span className="section-navigator-label">{section.title}</span></a>
    </li>)}</ol>
  </nav>
}
