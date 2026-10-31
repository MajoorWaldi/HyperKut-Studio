import { useEffect, useState } from 'react'
import { useI18n } from '../i18n'
import { Icon } from './Icon'
import { MotionGallery } from './MotionGallery'
import type { EditStyle as Style, JobState } from '../types'

const prettyJson = (value: string | undefined, fallback = '[]') => {
  try { return JSON.stringify(JSON.parse(value || fallback), null, 2) } catch { return value || fallback }
}

const DIRECTIONS = ['minimal', 'editorial', 'energetic'] as const

interface Props { job: JobState | null; onApply: (style: Style) => void }

/** The edit can be made again once every shot has its take and nothing runs. */
export const canEditAgain = (job: JobState | null) => job !== null && job.status !== 'queued' && job.status !== 'running' && job.shots.length > 0 && job.shots.every(s => s.done)

type Toggle = 'effects' | 'text' | 'sub_cuts' | 'auto_sfx'
type Slider = 'shot_volume' | 'duck' | 'music_volume'

/** The style of the edit: it is made again from the takes that exist, so it takes seconds and no shot is generated again. Only what was touched is sent. */
export function EditStyle({ job, onApply }: Props) {
  const { t, lang } = useI18n()
  const fr = lang === 'fr'
  const [changes, setChanges] = useState<Style>({})
  useEffect(() => setChanges({}), [job?.output_url])  // the changes stay until the edit that used them succeeded
  if (!canEditAgain(job) || !job) return null
  const set = (change: Style) => setChanges(current => ({ ...current, ...change }))
  const flag = (key: Toggle) => changes[key] ?? job.style[key] ?? false
  const level = (key: Slider, fallback: number) => changes[key] ?? job.style[key] ?? fallback
  const toggle = (key: Toggle, label: string, tip: string) => (
    <label key={key} title={tip} className={`chip-toggle ${flag(key) ? 'on' : ''}`}>
      <input type="checkbox" checked={flag(key)} onChange={e => set({ [key]: e.target.checked })} />
      <span className="switch" aria-hidden /> {label}
    </label>
  )
  const slider = (key: Slider, label: string, tip: string, fallback: number, max: number) => (
    <label key={key} className="es-slider" title={tip}>
      <span className="es-slider-head"><span>{label}</span><span className="es-value">{Math.round(level(key, fallback) * 100)}%</span></span>
      <input type="range" min={0} max={max} step={0.05} value={level(key, fallback)} onChange={e => set({ [key]: Number(e.target.value) })} />
    </label>
  )
  const count = Object.keys(changes).length
  const designOn = changes.motion_design ?? job.style.motion_design ?? false
  const direction = changes.motion_direction ?? job.style.motion_direction ?? 'editorial'
  const custom = direction.trim().startsWith('{')
  const layers = changes.motion_layers ?? job.style.motion_layers ?? '[]'
  const directionLabel: Record<(typeof DIRECTIONS)[number], string> = fr ? { minimal: 'Sobre', editorial: 'Éditorial', energetic: 'Énergique' } : { minimal: 'Minimal', editorial: 'Editorial', energetic: 'Energetic' }
  const directionTip: Record<(typeof DIRECTIONS)[number], string> = fr
    ? { minimal: 'Peu de graphismes, discrets.', editorial: 'Titres posés, rythme calme.', energetic: 'Titres qui réagissent à la musique, rythme vif.' }
    : { minimal: 'Few graphics, kept discreet.', editorial: 'Set titles at a calm pace.', energetic: 'Titles that react to the music, at a quick pace.' }
  return (
    <section className="edit-style" title={t.tip.editStyle}>
      <header className="es-head">
        <div className="tl-heading"><span className="tl-icon"><Icon name="scissors" size={19} /></span><span className="tl-title">{t.editStyle}</span><small>{t.editStyleHint}</small></div>
        <div className="es-actions">
          {count > 0 && <span className="es-count" role="status">{fr ? `${count} modification${count > 1 ? 's' : ''}` : `${count} change${count > 1 ? 's' : ''}`}</span>}
          <button type="button" className="secondary" disabled={!count} onClick={() => setChanges({})}>{t.reset}</button>
          <button type="button" className="primary" disabled={!count} title={t.tip.reEdit} onClick={() => onApply(changes)}><Icon name="scissors" size={15} /> {t.reEdit}</button>
        </div>
      </header>
      <div className="es-groups">
        <section className="es-group">
          <h4>{fr ? 'Montage' : 'Editing'}</h4>
          <div className="adv-toggles">
            {toggle('sub_cuts', t.subCuts, t.tip.subCuts)}
            {toggle('effects', t.effects, t.tip.editEffects)}
            {toggle('text', t.textOverlays, t.tip.editText)}
          </div>
        </section>
        <section className="es-group">
          <h4>{fr ? 'Son' : 'Sound'}</h4>
          <div className="adv-toggles">{toggle('auto_sfx', t.soundEffects, t.tip.editSfx)}</div>
          <div className="es-sliders">
            {slider('shot_volume', t.shotVolume, t.tip.shotVolume, 1, 2)}
            {slider('duck', t.duck, t.tip.duck, 0.5, 1)}
            {slider('music_volume', t.musicVolume, t.tip.musicVolume, 0, 2)}
          </div>
        </section>
        <section className="es-group wide">
          <h4>{fr ? 'Habillage animé' : 'Animated design'}</h4>
          <div className="es-design">
            <label className={`chip-toggle ${designOn ? 'on' : ''}`} title={t.tip.designToggle}>
              <input type="checkbox" checked={designOn} onChange={e => set({ motion_design: e.target.checked })} />
              <span className="switch" aria-hidden /> {fr ? 'Activer l’habillage' : 'Enable animated design'}
            </label>
            {designOn && <>
              <div className="segmented" role="group" aria-label={fr ? 'Style graphique' : 'Graphic style'}>
                {DIRECTIONS.map(id => <button type="button" key={id} aria-pressed={direction === id} title={directionTip[id]} onClick={() => set({ motion_direction: id })}>{directionLabel[id]}</button>)}
                {custom && <button type="button" aria-pressed disabled>{fr ? 'Personnalisé' : 'Custom'}</button>}
              </div>
              <label className="es-title"><span>{fr ? 'Titre (facultatif)' : 'Title (optional)'}</span><input maxLength={120} value={changes.motion_title ?? job.style.motion_title ?? ''} onChange={e => set({ motion_title: e.target.value })} /></label>
            </>}
          </div>
          <MotionGallery layers={layers} duration={job.shots.reduce((total, shot) => total + shot.duration, 0)} busy={false} onLayers={value => set({ motion_layers: value })} />
          <details className="advanced-technical">
            <summary>{fr ? 'JSON avancé' : 'Advanced JSON'}</summary>
            <div className="advanced-technical-body">
              <label className="field wide" title={t.tip.motionLayers}><span>{t.motionLayers}</span>
                <textarea rows={6} spellCheck={false} value={prettyJson(layers)} onChange={e => set({ motion_layers: e.target.value })} /></label>
              <label className="field wide"><span>{fr ? 'Consignes par plan' : 'Per-shot cues'}</span><textarea rows={5} spellCheck={false} value={changes.motion_cues ?? prettyJson(job.style.motion_cues)} onChange={e => set({ motion_cues: e.target.value })} /></label>
              <label className="field wide"><span>{fr ? 'Direction globale' : 'Global direction'}</span><textarea rows={4} spellCheck={false} value={changes.motion_direction ?? prettyJson(custom ? direction : JSON.stringify({ preset: direction, title: job.style.motion_title ?? '' }), '{}')} onChange={e => set({ motion_direction: e.target.value })} /></label>
              {job.style.rendered_layers && <label className="field wide"><span>{fr ? 'Calques effectivement rendus' : 'Rendered layers'}</span><textarea rows={6} readOnly value={prettyJson(job.style.rendered_layers)} /></label>}
            </div>
          </details>
        </section>
      </div>
    </section>
  )
}
