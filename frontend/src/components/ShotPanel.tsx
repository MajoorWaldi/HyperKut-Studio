import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import { useI18n } from '../i18n'
import { Icon } from './Icon'
import { TakeTrim } from './TakeTrim'
import { AICandidatePanel } from './AICandidatePanel'
import { workingShots } from '../activity'
import type { JobState, Quality, Take } from '../types'


interface Props {
  job: JobState | null
  /** The selected shot is `shots[primary]`; `selection` is every shot the buttons act on. */
  primary: number
  selection: string[]
  edits: Record<string, string>
  quality: Quality
  onEdit: (shot: string, text: string) => void
  onStep: (delta: number) => void
  onRegenerate: (shots: string[], withEdits: boolean) => void
  onLock: (shots: string[], locked: boolean) => void
  onChooseTake: (shot: string, take: string) => void
  onTrimTake: (shot: string, take: string, start: number) => Promise<void>
  onAIState?: (job: JobState) => void
  activeShots?: string[]
}

const duration = (seconds: number) => (seconds < 90 ? `${Math.round(seconds)} s` : `${Math.round(seconds / 60)} min`)

/** The shot that is selected: its picture, its prompt, its versions, and the buttons that make it again. It sits beside the player. */
export function ShotPanel({ job, primary, selection, edits, onEdit, onStep, onRegenerate, onLock, onChooseTake, onTrimTake, onAIState, activeShots=[] }: Props) {
  const { t, lang } = useI18n()
  const [takes, setTakes] = useState<Take[]>([])
  const [viewing, setViewing] = useState<Take | null>(null)
  const takeVideo = useRef<HTMLVideoElement>(null)
  const shots = job?.shots ?? []
  const index = Math.min(primary, shots.length - 1)
  const shot = shots[index]
  const over = job !== null && job.status !== 'queued' && job.status !== 'running'
  const chosen = shots.filter(s => (selection.length ? selection.includes(s.id) : s === shot))
  const regenerable = chosen.filter(s => !s.locked)
  const allLocked = chosen.length > 0 && chosen.every(s => s.locked)
  const text = shot ? edits[shot.id] ?? shot.prompt : ''
  const edited = shot !== undefined && text !== shot.prompt
  const active = takes.find(take => take.active)
  const shown = viewing ?? active
  const generationPrompt = shown ? shown.generation_prompt ?? '' : shot?.generation_prompt ?? ''
  const promptLabel = job?.mode === 'remix' ? t.shotCorrection : t.shotPrompt
  const editedIds = regenerable.filter(s => edits[s.id] !== undefined && edits[s.id] !== s.prompt).length
  const generated = regenerable.reduce((sum,s) => sum + (s.generation_frames ?? 0)/24,0)

  useEffect(() => {
    setViewing(null)
    if (!job || !over || !shot) { setTakes([]); return }
    let current = true
    api.takes(job.id, shot.id).then(list => { if (current) setTakes(Array.isArray(list) ? list : []) }).catch(() => { if (current) setTakes([]) })
    return () => { current = false }
  }, [job?.id, shot?.id, shot?.takes, shot?.version, over, job?.output_url]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const keys = (event: KeyboardEvent) => {
      if (document.querySelector('dialog.mjr-edit[open]')) return
      const target = event.target as HTMLElement
      if (target.closest('input, textarea, select, [contenteditable], [role="slider"]') || event.ctrlKey || event.metaKey || event.altKey) return
      if (event.key === 'ArrowLeft') onStep(-1)
      else if (event.key === 'ArrowRight') onStep(1)
      else if (event.key.toLowerCase() === 'l' && over && chosen.length) onLock(chosen.map(s => s.id), !allLocked)
    }
    document.addEventListener('keydown', keys)
    return () => document.removeEventListener('keydown', keys)
  }, [onStep, onLock, over, chosen.map(s => s.id).join(), allLocked]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!shot) return <aside className="shot-panel empty" title={t.tip.shotPanel}><p>{t.emptyShot}</p></aside>
  const remake = () => onRegenerate(regenerable.map(s => s.id), true)
  return (
    <aside className="shot-panel" title={t.tip.shotPanel}>
      <header>
        <button type="button" aria-label={t.prevShot} title={t.prevShot} disabled={index <= 0} onClick={() => onStep(-1)}><Icon name="chevron-left" size={16} /></button>
        <b>{t.shot} {index + 1} <small>/ {shots.length}</small></b>
        <button type="button" aria-label={t.nextShot} title={t.nextShot} disabled={index >= shots.length - 1} onClick={() => onStep(1)}><Icon name="chevron-right" size={16} /></button>
        <span className="v" title={t.tip.version}>{shot.takes} {t.take}</span>
      </header>

      <div className={`shot-view ${workingShots(job,activeShots).includes(shot.id) ? 'is-working' : ''}`}>
        {shown ? <video ref={takeVideo} key={shown.url} src={shown.url} muted loop autoPlay playsInline /> : shot.thumb && shot.done ? <img src={`${shot.thumb}?v=${shot.takes}-${shot.version}-${job?.operation ?? 0}`} alt="" /> : <span className="shot-wait">{shot.done ? '' : '…'}</span>}
        {shot.locked && <span className="shot-lock"><Icon name="lock" size={11} /> {t.locked}</span>}
      </div>

      {shown && <TakeTrim key={`${job?.id}-${shot.id}-${shown.id}-${shown.start ?? 0}`} take={shown} video={takeVideo} disabled={!over || shot.locked} onApply={start => onTrimTake(shot.id,shown.id,start)} />}

      <section className="shot-details">
        <h3 className="shot-section-title">{lang === 'fr' ? 'Versions' : 'Takes'} <small>· {takes.length || shot.takes}</small></h3>
      {takes.length > 1 && (
        <div className="takes" title={t.tip.takes}>
          {takes.map(take => (
            <button key={take.id} type="button" className={`take ${take.active ? 'active' : ''} ${shown?.id === take.id ? 'viewing' : ''}`} onClick={() => setViewing(take.active ? null : take)}>
              <video src={`${take.url}#t=0.1`} preload="metadata" muted playsInline />{take.active && <i><Icon name="check" size={11} /></i>}
            </button>
          ))}
        </div>
      )}
      {viewing && !viewing.active && <button type="button" className="take-use" disabled={!over} title={t.tip.useTake} onClick={() => onChooseTake(shot.id, viewing.id)}>{t.useTake}</button>}

      {takes.length <= 1 && <small className="single-take">{lang === 'fr' ? 'La version actuelle est affichée.' : 'Showing the current take.'}</small>}
      </section>

      <section className="shot-details shot-prompts">

      {job?.mode === 'remix' && <label className="shot-prompt-box">
        <span>{t.generationPrompt}</span>
        <textarea value={generationPrompt} readOnly aria-label={t.generationPrompt} placeholder={t.missingGenerationPrompt} />
      </label>}

      <label className="shot-prompt-box" title={t.tip.shotPrompt}>
        <span>{promptLabel}{edited && <em>{t.edited}</em>}</span>
        {shot.render_source && shot.render_source !== 'generated' && <small>{lang === 'fr' ? 'Source locale : modifier render_source dans le plan pour changer ce rendu.' : 'Local source: edit render_source in the plan to change this render.'}</small>}
        <textarea value={text} disabled={shot.locked || (!!shot.render_source && shot.render_source !== 'generated')} placeholder={promptLabel} aria-label={promptLabel} onChange={e => onEdit(shot.id, e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && over && regenerable.length) remake() }} />
        <small>{text.length} {t.characters}{edited && <button type="button" className="link" onClick={() => onEdit(shot.id, shot.prompt)}>{t.revert}</button>}</small>
      </label>

      </section>

      {job?.project_id && onAIState && (!shot.render_source || shot.render_source === 'generated') && <AICandidatePanel key={`${job.id}-${shot.id}`} job={job} shot={shot} take={shown ?? null}
        prompt={job.mode === 'remix' ? [generationPrompt, text.trim() ? `Requested changes: ${text}` : ''].filter(Boolean).join('\n\n') : text} onState={onAIState} />}

      <footer>
        {over && generated > 0 && <small className="estimate">{t.generatedBudget} : {duration(generated)}</small>}
        <button type="button" className="primary" disabled={!over || regenerable.length === 0} title={chosen.length && !regenerable.length ? t.locked : over ? t.tip.regenerate : t.needsJob} onClick={remake}>
          <Icon name="refresh" size={15} /> {editedIds > 0 ? t.regenerateEdit : t.regenerate}{regenerable.length > 1 ? ` (${regenerable.length})` : ''}
        </button>
        {editedIds > 0 && <button type="button" disabled={!over} title={t.tip.newTake} onClick={() => onRegenerate(regenerable.map(s => s.id), false)}>{t.newTake}</button>}
      </footer>
    </aside>
  )
}
