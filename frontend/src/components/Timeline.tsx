import { useEffect, useMemo, useRef, useState, type MouseEvent, type PointerEvent } from 'react'
import * as api from '../api'
import { useI18n } from '../i18n'
import { beatGrid, rulerStep } from '../rhythm'
import { Icon, type IconName } from './Icon'
import { workingShots } from '../activity'
import type { JobState, TimelineInfo } from '../types'

const EFFECT_ICON: Record<string, IconName> = { zoom: 'zoom', speed: 'fast', speed_ramp: 'fast', flip: 'flip', look: 'contrast', text: 'type', transition: 'sparkles' }

interface Props {
  job: JobState | null
  /** Where the player is in the result, in the time of the plan (seconds), or null when there is no result to play. */
  position: number | null
  onSeek: (seconds: number) => void
  /** The shots that are selected, and the one the panel next to the player shows. */
  selection: string[]
  primary: number
  edits: Record<string, string>
  onSelect: (selection: string[], primary: number) => void
  onRegenerate: (shots: string[]) => void
  onLock: (shots: string[], locked: boolean) => void
  activeShots?: string[]
}

const mmss = (seconds: number) => `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

/** The shots on a time axis that follows the player: a ruler to scrub, the cuts and the beat grid, the sound; the shots can be selected together. */
export function Timeline({ job, position, onSeek, selection, primary, edits, onSelect, onRegenerate, onLock, activeShots=[] }: Props) {
  const { t } = useI18n()
  const [zoom, setZoom] = useState(1)
  const [info, setInfo] = useState<TimelineInfo | null>(null)
  const [wave, setWave] = useState<number[]>([])
  const inner = useRef<HTMLDivElement>(null)
  const shots = job?.shots ?? []
  const working=workingShots(job,activeShots)
  const total = shots.reduce((sum, shot) => sum + shot.duration, 0)
  const starts = shots.map((_, i) => shots.slice(0, i).reduce((sum, s) => sum + s.duration, 0))
  const shot = shots[Math.min(primary, shots.length - 1)]
  const over = job !== null && job.status !== 'queued' && job.status !== 'running'
  const chosen = shots.filter(s => selection.includes(s.id) || (selection.length === 0 && s === shot))
  const regenerable = chosen.filter(s => !s.locked)
  const playing = position !== null ? starts.reduce((found, start, i) => (start <= position ? i : found), 0) : -1
  const filled = (i: number) => (position === null ? 0 : Math.max(0, Math.min(1, (position - starts[i]) / shots[i].duration)))
  const edited = (id: string) => edits[id] !== undefined && edits[id] !== shots.find(s => s.id === id)?.prompt

  useEffect(() => {
    setInfo(null)
    setWave([])
    if (!job || !over || !job.output_url || job.manual_export) return
    let current = true
    api.timeline(job.id).then(found => { if (current && found && Array.isArray(found.shots)) setInfo(found) }).catch(() => undefined)
    api.waveform(job.id).then(found => { if (current && Array.isArray(found)) setWave(found) }).catch(() => undefined)
    return () => { current = false }
  }, [job?.id, over, job?.output_url]) // eslint-disable-line react-hooks/exhaustive-deps

  const rhythm = useMemo(() => {
    if (!info) return null
    const inside = job?.style.sub_cuts !== false
    const cuts = shots.flatMap((s, i) => [...(i > 0 ? [starts[i]] : []), ...(inside ? (info.shots.find(x => x.id === s.id)?.cuts ?? []).map(c => starts[i] + c) : [])])
    return { cuts, grid: info.bpm ? beatGrid(cuts, info.bpm, total, info.beat_times) : null }
  }, [info, job?.style.sub_cuts, shots.length, total]) // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (index: number, event: MouseEvent) => {
    const id = shots[index].id
    if (event.shiftKey) {
      const [from, to] = [Math.min(primary, index), Math.max(primary, index)]
      onSelect(shots.slice(from, to + 1).map(s => s.id), index)
    } else if (event.ctrlKey || event.metaKey) {
      const base = selection.length ? selection : shot ? [shot.id] : []
      onSelect(base.includes(id) ? base.filter(x => x !== id) : [...base, id], index)
    } else {
      onSelect([id], index)
      if (position !== null) onSeek(starts[index])
    }
  }

  const scrub = (event: PointerEvent<Element>) => {
    if (position === null || !inner.current || (event.type === 'pointermove' && event.buttons === 0)) return
    const box = inner.current.getBoundingClientRect()
    onSeek(Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)) * total)
  }
  const scrubbing = { onPointerDown: (event: PointerEvent<Element>) => { event.currentTarget.setPointerCapture(event.pointerId); scrub(event) }, onPointerMove: scrub }

  const allLocked = chosen.length > 0 && chosen.every(s => s.locked)
  const step = rulerStep(total, (inner.current?.clientWidth ?? 600))
  const marks = Array.from({ length: Math.ceil(total / step) }, (_, i) => i * step)
  const waveform = wave.length ? `M0 50 ${wave.map((v, i) => `M${i + 0.5} ${50 - v * 48} V${50 + v * 48}`).join(' ')}` : ''

  return (
    <section className="timeline-card" title={t.tip.timeline}>
      <div className="tl-heading">
        <span className="tl-icon"><Icon name="film" size={19} /></span><span className="tl-title">{t.timeline}</span>
        <small>{shots.length} {t.shots} · {total.toFixed(1)} {t.seconds}</small>
        <label className="tl-zoom" title={t.tip.zoom}>{t.zoom}<input type="range" min={1} max={8} step={0.5} value={zoom} onChange={e => setZoom(Number(e.target.value))} /></label>
      {shots.length > 1 && over && (
        <details className="timeline-actions" open={chosen.length>1 ? true : undefined}>
          <summary>Actions</summary>
        <div className="tl-select" title={t.tip.multiSelect}>
          <span>{chosen.length} {t.selected}</span>
          <button type="button" disabled={regenerable.length === 0} onClick={() => onRegenerate(regenerable.map(s => s.id))}>{t.regenerate} ({regenerable.length})</button>
          <button type="button" onClick={() => onLock(chosen.map(s => s.id), !allLocked)}>{allLocked ? t.unlock : t.lock}</button>
          <button type="button" title={t.tip.regenerateAll} onClick={() => onRegenerate(shots.filter(s => !s.locked).map(s => s.id))}>{t.regenerateAll}</button>
        </div>
        </details>
      )}
      </div>
      {job?.manual_export && <p className="tiny-label">{t.manualSourceTimeline}</p>}
      <div className="shots-panel">
        {shots.length === 0 ? <p className="tiny-label">{t.noShots}</p> : (
          <div className="tl-scroll">
            <div className="tl-inner" ref={inner} style={{ width: `${zoom * 100}%` }}>
              <div className="ruler" title={t.tip.ruler} {...scrubbing}>
                {marks.map(mark => <span key={mark} style={{ left: `${(mark / total) * 100}%` }}>{mmss(mark)}</span>)}
              </div>
              <div className="shots">
                {shots.map((s, i) => {
                  const effects = info?.shots.find(x => x.id === s.id)?.effects ?? []
                  const glyphs = [...new Set(effects.map(e => EFFECT_ICON[e.split(':')[0]]).filter(Boolean))]
                  return (
                    <button key={s.id} type="button" title={`${t.shot} ${i + 1} · ${starts[i].toFixed(1)}–${(starts[i] + s.duration).toFixed(1)} ${t.seconds}`}
                      className={`shot ${working.includes(s.id) ? 'is-working' : ''} ${i === primary ? 'active' : ''} ${selection.includes(s.id) ? 'selected' : ''} ${i === playing ? 'playing' : ''} ${s.done ? 'done' : ''}`} style={{ flexGrow: s.duration }} onClick={event => pick(i, event)}>
                      <span className="shot-image" aria-hidden>{s.thumb && s.done ? <img src={`${s.thumb}?v=${s.takes}-${s.version}-${job?.operation ?? 0}`} alt="" /> : null}</span>
                      <span className="badges" title={t.tip.badges}>
                        {s.locked && <b data-badge="lock"><Icon name="lock" size={10} /></b>}{edited(s.id) && <b data-badge="edited"><Icon name="pencil" size={10} /></b>}{s.takes > 1 && <b data-badge="takes">×{s.takes}</b>}{glyphs.map(g => <i key={g} data-badge={g}><Icon name={g} size={10} /></i>)}
                      </span>
                      <span className="shot-progress" style={{ transform: `scaleX(${filled(i)})` }} />
                      <span className="clip-caption"><b>{String(i+1).padStart(2,'0')} · {t.shot}</b><small>{s.duration.toFixed(2)} s</small></span>
                    </button>
                  )
                })}
              </div>
              {rhythm && (
                <div className="rhythm" title={t.tip.rhythm} {...scrubbing}>
                  {rhythm.grid?.ticks.map(tick => <span key={`b${tick}`} className="beat" style={{ left: `${(tick / total) * 100}%` }} />)}
                  {rhythm.cuts.map(cut => <span key={`c${cut}`} className="cut" style={{ left: `${(cut / total) * 100}%` }} />)}
                </div>
              )}
              {waveform && (
                <div className="wave-track"><span className="wave-label"><Icon name="volume" size={12} />{t.result}</span>
                <svg className="wave" viewBox={`0 0 ${wave.length} 100`} preserveAspectRatio="none" role="img" aria-label={t.waveform} {...scrubbing}>
                  <title>{t.tip.waveform}</title>
                  <path d={waveform} stroke="currentColor" strokeWidth={1} vectorEffect="non-scaling-stroke" fill="none" />
                </svg>
                </div>
              )}
              {position !== null && total > 0 && <div className="playhead" style={{ left: `${Math.max(0,Math.min(100,(position / total)*100))}%` }}><span>{position.toFixed(2)} s</span></div>}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
