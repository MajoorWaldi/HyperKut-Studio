import { useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'
import type { Take } from '../types'
import { useI18n } from '../i18n'
import { VideoFilmstrip } from './VideoFilmstrip'

interface Props {
  take: Take
  video: RefObject<HTMLVideoElement | null>
  disabled: boolean
  onApply: (start: number) => Promise<void>
}

/** Imperative media seek; this changes a DOM player, never React-owned data. */
function seekMedia(video: RefObject<HTMLVideoElement | null>, seconds: number) {
  const element = video.current
  if (element?.readyState) element.currentTime = seconds
}

/** Slip the source window without changing the shot's place or length in the edit. */
export function TakeTrim({ take, video, disabled, onApply }: Props) {
  const { lang } = useI18n()
  const fr = lang === 'fr'
  const [start, setStart] = useState(take.start ?? 0)
  const [saving, setSaving] = useState(false)
  const track = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; start: number } | null>(null)
  const length = take.duration ?? 0
  const window = take.window ?? 0
  const maximum = take.max_start ?? 0
  const step = take.step ?? 1 / 24
  const blocked = disabled || saving || !take.active
  const changed = Math.abs(start - (take.start ?? 0)) > step / 2
  const format = (value: number) => value.toLocaleString(fr ? 'fr' : 'en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const change = (value: number) => {
    const next = Math.max(0, Math.min(maximum, Math.round(value / step) * step))
    setStart(next)
    seekMedia(video, next)
  }

  useEffect(() => {
    const element = video.current
    if (!element || window <= 0) return
    const seek = () => seekMedia(video, start)
    const loop = () => {
      if (element.currentTime >= start + window - .015 || element.currentTime < start - .02) seek()
    }
    element.addEventListener('loadedmetadata', seek)
    element.addEventListener('timeupdate', loop)
    if (element.readyState) seek()
    return () => { element.removeEventListener('loadedmetadata', seek); element.removeEventListener('timeupdate', loop) }
  }, [video, start, window])

  if (!(length > 0) || !(window > 0)) return null
  return <section className="take-trim" aria-label={fr ? 'Portion conservée' : 'Selected portion'}>
    <div className="trim-heading"><span>{fr ? 'Portion conservée' : 'Selected portion'}</span><output>{format(start)} – {format(start + window)} s <small>/ {format(length)} s</small></output></div>
    <div className="trim-track" ref={track}>
      <VideoFilmstrip url={take.url} duration={length} />
      <button type="button" role="slider" className="trim-window"
        aria-label={fr ? 'Déplacer la portion' : 'Move selected portion'} aria-valuemin={0} aria-valuemax={maximum} aria-valuenow={start}
        aria-valuetext={`${format(start)} – ${format(start + window)} s`} disabled={blocked || maximum <= 0}
        style={{ left: `${100 * start / length}%`, width: `${Math.min(100, 100 * window / length)}%` }}
        onKeyDown={event => {
          const values: Record<string, number> = { ArrowLeft:start-step, ArrowRight:start+step, ArrowDown:start-step, ArrowUp:start+step, Home:0, End:maximum, PageDown:start-10*step, PageUp:start+10*step }
          if (event.key in values) { event.preventDefault(); event.stopPropagation(); change(values[event.key]) }
        }}
        onPointerDown={event => {
          if (blocked) return
          drag.current = { x:event.clientX, start }
          event.currentTarget.setPointerCapture(event.pointerId)
        }}
        onPointerMove={event => {
          if (!drag.current || blocked || !track.current) return
          const width = track.current.getBoundingClientRect().width
          if (width > 0) change(drag.current.start + (event.clientX-drag.current.x) / width * length)
        }}
        onPointerUp={() => { drag.current = null }} onPointerCancel={() => { drag.current = null }} onLostPointerCapture={() => { drag.current = null }}
      ><span aria-hidden="true">Ⅱ</span><span aria-hidden="true">Ⅱ</span></button>
    </div>
    <small>{!take.active ? (fr ? 'Choisis cette version pour ajuster sa portion.' : 'Choose this take to adjust its portion.') : maximum <= 0 ? (fr ? 'Toute la prise est nécessaire à ce montage.' : 'This edit uses the full take.') : (fr ? 'Glisse la fenêtre pour choisir le passage. La durée du plan reste identique.' : 'Drag the window to choose the moment. The shot length stays the same.')}</small>
    {take.active && (maximum > 0 || (take.start ?? 0) > 0) && <div className="trim-actions">
      <button type="button" className="secondary" disabled={blocked || start === 0} onClick={() => change(0)}>{fr ? 'Au début' : 'Reset start'}</button>
      <button type="button" className="primary-soft" disabled={blocked || !changed} onClick={async () => { setSaving(true); try { await onApply(start) } finally { setSaving(false) } }}>{saving ? (fr ? 'Application…' : 'Applying…') : (fr ? 'Appliquer au montage' : 'Apply to edit')}</button>
    </div>}
  </section>
}
