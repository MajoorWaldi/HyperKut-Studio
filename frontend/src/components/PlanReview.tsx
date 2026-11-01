import { useEffect, useMemo, useRef, useState } from 'react'
import * as api from '../api'
import { useI18n } from '../i18n'
import type { JobState, TimelineInfo } from '../types'

const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

/** The plan of a job that waits for approval, in a window: the shots on a timeline with the cuts inside them, the effects and the text the plan gives them, the prompt of the shot that is chosen, and what it will cost on the GPU. Nothing is generated before the button. */
/** A shot with no render_source is a generated one (older projects): only an explicit other source is local. */
const isLocal = (shot: { render_source?: string }) => !!shot.render_source && shot.render_source !== 'generated'

export function PlanReview({ job, hidden = false, busy, onApprove, onRefuse, onClose }: { job: JobState; hidden?: boolean; busy: boolean; onApprove: (prompts: Record<string, string>) => void; onRefuse: () => void; onClose: () => void }) {
  const { lang } = useI18n()
  const fr = lang === 'fr'
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [chosen, setChosen] = useState(job.shots[0]?.id ?? '')
  const [info, setInfo] = useState<TimelineInfo | null>(null)
  const panel = useRef<HTMLElement>(null)
  const close = useRef(onClose)
  useEffect(() => { close.current = onClose })
  // closing only hides the window: the prompts that were edited are kept until the plan is approved or refused
  useEffect(() => {
    if (hidden) return
    const previous = document.activeElement as HTMLElement | null
    panel.current?.querySelector<HTMLElement>('textarea, button')?.focus()
    const keys = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.stopPropagation(); close.current(); return }
      if (event.key !== 'Tab' || !panel.current) return
      const items = [...panel.current.querySelectorAll<HTMLElement>('button:not(:disabled), textarea:not(:disabled)')]
      if (!items.length) return
      const first = items[0], last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', keys)
    return () => { document.removeEventListener('keydown', keys); previous?.focus?.() }
  }, [hidden])
  useEffect(() => { api.timeline(job.id).then(setInfo).catch(() => setInfo(null)) }, [job.id])
  const budget = job.generation_budget
  const total = useMemo(() => job.shots.reduce((end, shot) => Math.max(end, shot.start + shot.duration), 0) || 1, [job.shots])
  const changed = Object.fromEntries(job.shots.filter(shot => edits[shot.id] !== undefined && edits[shot.id] !== shot.prompt).map(shot => [shot.id, edits[shot.id]]))
  const local = job.shots.filter(isLocal).length
  const shot = job.shots.find(item => item.id === chosen) ?? job.shots[0]
  const detail = (id: string) => info?.shots.find(item => item.id === id)
  const ticks = Array.from({ length: Math.floor(total / 5) + 1 }, (_, index) => index * 5)
  return (
    <div className="plan-backdrop" hidden={hidden}>
      <section ref={panel} className="plan-review" role="dialog" aria-modal="true" aria-label={fr ? 'Plan à valider' : 'Plan to approve'}>
        <header>
          <strong>{fr ? 'Plan à valider avant la génération' : 'Plan to approve before generating'}</strong>
          <span>{job.shots.length} {fr ? 'plans' : 'shots'}{local > 0 && ` (${local} ${fr ? 'sans génération' : 'not generated'})`}
            {budget && ` · ${fr ? 'vidéo finale' : 'final video'} ${budget.final_seconds}s · GPU ≈ ${budget.seconds}s${budget.with_retries > budget.seconds ? ` (${budget.with_retries}s ${fr ? 'avec refaits' : 'with retries'})` : ''}`}</span>
          <button type="button" className="plan-close" aria-label={fr ? 'Fermer, décider plus tard' : 'Close, decide later'} title={fr ? 'Fermer, décider plus tard' : 'Close, decide later'} onClick={onClose}>×</button>
        </header>
        <div className="plan-timeline" role="group" aria-label={fr ? 'Montage prévu' : 'Planned edit'}>
          <div className="plan-ruler">{ticks.map(second => <span key={second} style={{ left: `${second / total * 100}%` }}>{clock(second)}</span>)}</div>
          <div className="plan-track">
            {(info?.beat_times ?? []).filter(time => time <= total).map(time => <i key={time} className="plan-beat" style={{ left: `${time / total * 100}%` }} />)}
            {job.shots.map(item => {
              const extra = detail(item.id)
              return (
                <button type="button" key={item.id} className={`plan-block ${item.id === shot?.id ? 'on' : ''} ${isLocal(item) ? 'local' : ''}`}
                  style={{ left: `${item.start / total * 100}%`, width: `${item.duration / total * 100}%` }} aria-pressed={item.id === shot?.id} onClick={() => setChosen(item.id)}>
                  <b>{item.id.replace('SHOT_', '#')}</b><small>{item.duration.toFixed(1)}s</small>
                  {(extra?.cuts ?? []).map(cut => <i key={`${item.id}-${cut}`} className="plan-cut" style={{ left: `${cut / item.duration * 100}%` }} />)}
                  {changed[item.id] !== undefined && <u aria-label={fr ? 'prompt modifié' : 'prompt edited'} />}
                </button>
              )
            })}
          </div>
        </div>
        {shot && (
          <div className="plan-shot">
            <div className="plan-facts">
              <b>{shot.id}</b> · {clock(shot.start)}–{clock(shot.start + shot.duration)} · {shot.duration.toFixed(1)}s{isLocal(shot) && ` · ${shot.render_source}`}
              {(detail(shot.id)?.cuts.length ?? 0) > 0 && <span className="plan-chip">{detail(shot.id)!.cuts.length + 1} {fr ? 'coupes' : 'cuts'}</span>}
              {(detail(shot.id)?.effects ?? []).map(effect => <span className="plan-chip" key={effect}>{effect.replace('transition:', '→ ')}</span>)}
              {detail(shot.id)?.text && <span className="plan-chip text">“{detail(shot.id)!.text}”</span>}
            </div>
            <textarea rows={5} aria-label={`${fr ? 'Prompt du plan' : 'Prompt of shot'} ${shot.id}`} value={edits[shot.id] ?? shot.prompt} disabled={busy || isLocal(shot)}
              onChange={event => setEdits(current => ({ ...current, [shot.id]: event.target.value }))} />
          </div>
        )}
        <footer>
          <button type="button" className="primary" disabled={busy} onClick={() => onApprove(changed)}>{fr ? `Générer ${job.shots.length - local} plan(s)` : `Generate ${job.shots.length - local} shot(s)`}</button>
          <button type="button" className="secondary" disabled={busy} onClick={onRefuse}>{fr ? 'Annuler' : 'Cancel'}</button>
          <small>{fr ? 'Rien n’est généré avant le bouton.' : 'Nothing is generated before the button.'}</small>
        </footer>
      </section>
    </div>
  )
}
