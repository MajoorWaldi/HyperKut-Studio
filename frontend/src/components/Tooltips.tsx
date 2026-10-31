import { useEffect, useRef, useState } from 'react'

interface Tip { text: string; x: number; y: number; below: boolean }

/** What is already chosen or already there needs no explanation: the pressed, selected and active buttons, and an upload slot that holds a file. */
const settled = (element: Element) => element.matches('[aria-pressed="true"], [aria-selected="true"], [aria-current], .selected, .active, .on:not(.chip-toggle)') || (element.matches('.upload') && element.querySelector('img, video, .file-name') !== null)

/** Replaces the browser tooltips: on hover or focus the `title` of the element is taken (so the native one never shows) and drawn in the style of the app; it is given back on leave. */
export function Tooltips() {
  const [tip, setTip] = useState<Tip | null>(null)
  const current = useRef<{ element: Element; title: string } | null>(null)
  const timer = useRef<number>(0)

  useEffect(() => {
    const hide = () => {
      window.clearTimeout(timer.current)
      if (current.current) current.current.element.setAttribute('title', current.current.title)
      current.current = null
      setTip(null)
    }
    const show = (target: EventTarget | null) => {
      const element = target instanceof Element ? target.closest('[title]') : null
      if (!element || element === current.current?.element) return
      hide()
      const title = element.getAttribute('title') ?? ''
      if (!title) return
      element.removeAttribute('title')
      current.current = { element, title }
      if (settled(element)) return
      timer.current = window.setTimeout(() => {
        const box = element.getBoundingClientRect()
        const below = box.top < 90
        const zoom = Number(getComputedStyle(document.documentElement).getPropertyValue('--ui-zoom')) || 1  // the rectangles are in window pixels, the bubble is placed in zoomed ones
        setTip({ text: title, x: Math.min(Math.max(box.left + box.width / 2, 170 * zoom), window.innerWidth - 170 * zoom) / zoom, y: (below ? box.bottom + 8 : box.top - 8) / zoom, below })
      }, 500)
    }
    const press = () => { window.clearTimeout(timer.current); setTip(null) }  // a press ends the tip, and it stays quiet until the pointer has left (the native one stays off: the title is not given back before)
    const over = (event: Event) => show(event.target)
    const out = (event: Event) => { if (current.current && !current.current.element.contains((event as MouseEvent).relatedTarget as Node | null)) hide() }
    document.addEventListener('mouseover', over)
    document.addEventListener('mouseout', out)
    document.addEventListener('focusin', over)
    document.addEventListener('focusout', hide)
    document.addEventListener('scroll', hide, true)
    document.addEventListener('mousedown', press)
    return () => {
      hide()
      document.removeEventListener('mouseover', over)
      document.removeEventListener('mouseout', out)
      document.removeEventListener('focusin', over)
      document.removeEventListener('focusout', hide)
      document.removeEventListener('scroll', hide, true)
      document.removeEventListener('mousedown', press)
    }
  }, [])

  if (!tip) return null
  return <div className={`tooltip ${tip.below ? 'below' : ''}`} role="tooltip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>
}
