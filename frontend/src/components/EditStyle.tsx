import { useEffect, useState } from 'react'
import { useI18n } from '../i18n'
import { Icon } from './Icon'
import type { EditStyle as Style, JobState } from '../types'

const prettyJson = (value: string | undefined, fallback = '[]') => {
  try { return JSON.stringify(JSON.parse(value || fallback), null, 2) } catch { return value || fallback }
}


interface Props { job: JobState | null; onApply: (style: Style) => void }

/** The edit can be made again once every shot has its take and nothing runs. */
export const canEditAgain = (job: JobState | null) => job !== null && job.status !== 'queued' && job.status !== 'running' && job.shots.length > 0 && job.shots.every(s => s.done)

type Toggle = 'effects' | 'text' | 'sub_cuts' | 'auto_sfx'
type Slider = 'shot_volume' | 'duck' | 'music_volume'

/** The style of the edit: it is made again from the takes that exist, so it takes seconds and no shot is generated again. Only what was touched is sent. */
export function EditStyle({ job, onApply }: Props) {
  const { t, lang } = useI18n()
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
    <label key={key} className="tool range" title={tip}><span className="slider-label">{label} · {Math.round(level(key, fallback) * 100)}%</span>
      <input type="range" min={0} max={max} step={0.05} value={level(key, fallback)} onChange={e => set({ [key]: Number(e.target.value) })} /></label>
  )
  const touched = Object.keys(changes).length > 0
  return (
    <section className="edit-style" title={t.tip.editStyle}>
      <div className="tl-heading"><span className="tl-icon"><Icon name="scissors" size={19} /></span><span className="tl-title">{t.editStyle}</span><small>{t.editStyleHint}</small></div>
      <div className="adv-toggles">
        {toggle('sub_cuts', t.subCuts, t.tip.subCuts)}
        {toggle('effects', t.effects, t.tip.editEffects)}
        {toggle('text', t.textOverlays, t.tip.editText)}
        {toggle('auto_sfx', t.soundEffects, t.tip.editSfx)}
      </div>
      <div className="adv-fields">
        {slider('shot_volume', t.shotVolume, t.tip.shotVolume, 1, 2)}
        {slider('duck', t.duck, t.tip.duck, 0.5, 1)}
        {slider('music_volume', t.musicVolume, t.tip.musicVolume, 0, 2)}
      </div>
      <details className="advanced-technical">
        <summary>{t.motionLayers}</summary>
        <div className="advanced-technical-body">
          <label className="field wide" title={t.tip.motionLayers}><span>{t.motionLayers}</span>
            <textarea rows={6} spellCheck={false} value={changes.motion_layers ?? prettyJson(job.style.motion_layers)} onChange={e => set({ motion_layers: e.target.value })} /></label>
        </div>
      </details>
      <details className="advanced-technical">
        <summary>{lang === 'fr' ? 'Habillage animé' : 'Animated design'}</summary>
        <div className="advanced-technical-body">
          <label className="field"><span>{lang === 'fr' ? 'Activer l’habillage' : 'Enable animated design'}</span><input type="checkbox" checked={changes.motion_design ?? job.style.motion_design ?? false} onChange={e=>set({motion_design:e.target.checked})}/></label>
          <label className="field"><span>{lang === 'fr' ? 'Style graphique' : 'Graphic style'}</span><select value={changes.motion_direction ?? job.style.motion_direction ?? 'editorial'} onChange={e=>set({motion_direction:e.target.value})}>{(changes.motion_direction ?? job.style.motion_direction ?? '').startsWith('{') && <option value={changes.motion_direction ?? job.style.motion_direction}>{lang === 'fr' ? 'Personnalisé (JSON)' : 'Custom (JSON)'}</option>}<option value="minimal">{lang === 'fr' ? 'Sobre' : 'Minimal'}</option><option value="editorial">{lang === 'fr' ? 'Éditorial' : 'Editorial'}</option><option value="energetic">{lang === 'fr' ? 'Énergique' : 'Energetic'}</option></select></label>
          <details className="advanced-technical">
            <summary>{lang === 'fr' ? 'Calques HyperFrames (JSON)' : 'HyperFrames layers (JSON)'}</summary>
            <div className="advanced-technical-body">
              <label className="field"><span>{lang === 'fr' ? 'Consignes par plan' : 'Per-shot cues'}</span><textarea rows={6} spellCheck={false} value={changes.motion_cues ?? prettyJson(job.style.motion_cues)} onChange={e=>set({motion_cues:e.target.value})}/></label>
              <label className="field"><span>{lang === 'fr' ? 'Direction globale' : 'Global direction'}</span><textarea rows={5} spellCheck={false} value={changes.motion_direction ?? prettyJson(job.style.motion_direction?.startsWith('{') ? job.style.motion_direction : JSON.stringify({preset:job.style.motion_direction ?? 'editorial',title:job.style.motion_title ?? ''}), '{}')} onChange={e=>set({motion_direction:e.target.value})}/></label>
            </div>
          </details>
          <label className="field"><span>{lang === 'fr' ? 'Titre (facultatif)'  : 'Title (optional)'}</span><input maxLength={120} value={changes.motion_title ?? job.style.motion_title ?? ''} onChange={e=>set({motion_title:e.target.value})}/></label>
        </div>
      </details>
      {job.style.rendered_layers && <details className="advanced-technical"><summary>{lang === 'fr' ? 'Calques effectivement rendus (JSON)' : 'Rendered layers (JSON)'}</summary><textarea className="field" rows={8} readOnly value={prettyJson(job.style.rendered_layers)} /></details>}
      <div className="insp-actions">
        <button type="button" className="primary" disabled={!touched} title={t.tip.reEdit} onClick={() => onApply(changes)}><Icon name="scissors" size={15} /> {t.reEdit}</button>
        <button type="button" className="secondary" disabled={!touched} onClick={() => setChanges({})}>{t.reset}</button>
      </div>
    </section>
  )
}
