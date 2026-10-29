import { useState } from 'react'
import { useI18n } from '../i18n'
import { Icon } from './Icon'
import { DEFAULTS, optionDefaults, QUICK, STYLES, type Option } from '../settings'
import type { Mode, Settings } from '../types'

interface Props { mode: Mode; settings: Settings; busy: boolean; onSettings: (changes: Partial<Settings>) => void }

type Group = 'look' | 'sound' | 'expert'

const dirty = (settings: Settings, key: keyof Settings) => settings[key] !== DEFAULTS[key]

/** The options of the edit, folded under the loaders: one line when closed, three groups when open (one open at a time). */
export function Options({ mode, settings, busy, onSettings }: Props) {
  const { t, lang } = useI18n()
  const [open, setOpen] = useState(false)
  const [group, setGroup] = useState<Group | null>(null)
  const remix = mode === 'remix'
  const musicalEditing = !remix || settings.audio === 'new'
  const label: Record<Option, string> = { effects: t.effects, text: t.textOverlays, subject_mask: t.subjectMask, redraw_text: t.redrawText, pose_only: t.poseOnly, places: t.places, sound_design: t.soundDesign, sound_effects: t.soundEffects, music_sync: t.musicSync, retry_bad_takes: t.retryBad, quality_check: t.qualityCheck }
  const tip: Record<Option, string> = { effects: t.tip.effects, text: t.tip.text, subject_mask: t.tip.subjectMask, redraw_text: t.tip.redrawText, pose_only: t.tip.poseOnly, places: t.tip.places, sound_design: t.tip.soundDesign, sound_effects: t.tip.soundEffects, music_sync: t.tip.musicSync, retry_bad_takes: t.tip.retryBad, quality_check: t.tip.qualityCheck }
  const toggles: Record<Group, Option[]> = {
    look: remix ? ['effects', 'text', 'redraw_text', 'pose_only'] : ['effects', 'text', 'places'],
    sound: remix ? ['sound_design', 'sound_effects'] : ['sound_design', 'sound_effects', 'music_sync'],
    expert: ['retry_bad_takes', 'quality_check'],
  }
  const names: Record<Group, string> = { look: t.groupLook, sound: t.groupSound, expert: t.groupExpert }
  const descriptions: Record<Group, string> = lang === 'fr'
    ? { look: 'Montage, effets et détourage du sujet.', sound: 'Ambiance musicale, synchronisation et bruitages.', expert: 'Vérifications, variations et outils spécifiques.' }
    : { look: 'Editing, effects and subject separation.', sound: 'Music mood, synchronization and sound effects.', expert: 'Checks, variations and specific tools.' }
  const all = Object.values(toggles).flat()
  const changed = ['efficient_sources', 'reference_style', 'sfx_library', 'camera', 'bpm', 'mood', 'music_start', 'seed', 'motion_layers', 'motion_design', 'motion_direction', 'motion_title', ...(remix ? [] : ['style', 'transition_intensity', 'text_allowed']), ...(musicalEditing ? ['cut_density', 'cut_every', 'music_edit_mode', 'music_cut_variation', 'music_cut_sync'] : []), ...all].filter(key => dirty(settings, key as keyof Settings)).length

  const toggle = (key: Option) => (
    <label key={key} title={tip[key]} className={`chip-toggle ${settings[key] ? 'on' : ''} ${busy ? 'disabled' : ''}`}>
      <input type="checkbox" checked={settings[key]} disabled={busy} onChange={e => onSettings({ [key]: e.target.checked })} />
      <span className="switch" aria-hidden /><span className="advanced-toggle-copy"><strong>{label[key]}</strong><small>{tip[key]}</small></span>{dirty(settings, key) && <i className="changed" aria-label={t.changed} />}
    </label>
  )
  const field = (key: 'camera' | 'mood', text: string, hint: string, placeholder?: string) => (
    <label className="field" key={key} title={hint}><span>{text}</span><input type="text" placeholder={placeholder} value={settings[key]} disabled={busy} onChange={e => onSettings({ [key]: e.target.value })} /></label>
  )
  const number = (key: 'bpm' | 'music_start', text: string, hint: string, extra: { min: number; max?: number; step?: number }) => (
    <label className="field" key={key} title={hint}><span>{text}</span><input type="number" {...extra} value={settings[key]} disabled={busy} onChange={e => onSettings({ [key]: Number(e.target.value) })} /></label>
  )

  const select = <K extends 'style' | 'cut_density' | 'transition_intensity' | 'cut_every' | 'music_edit_mode'>(key: K, text: string, hint: string, choices: [Settings[K], string][]) => (
    <label className="field" key={key} title={hint}><span>{text}</span>
      <select value={settings[key]} disabled={busy} onChange={e => onSettings({ [key]: e.target.value } as Partial<Settings>)}>{choices.map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select>
    </label>
  )

  return (
    <details className="options advanced-options" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
      <summary className="advanced-options-summary" title={t.tip.options}>
        <span>{t.options}</span>
        <small>{changed > 0 ? `${changed} ${t.changed}` : (lang === 'fr' ? 'facultatif' : 'optional')}</small>
      </summary>
      {open && (
        <div className="options-body">
          <div className="quick" title={t.tip.quick}>
            <span>{t.quick}</span>
            {(['light', 'balanced', 'full'] as const).map(name => (
              <button key={name} type="button" disabled={busy} onClick={() => onSettings(QUICK[name])}>{{ light: t.quickLight, balanced: t.quickBalanced, full: t.quickFull }[name]}</button>
            ))}
          </div>
          {(['look', 'sound', 'expert'] as const).map(g => (
            <div key={g} className={`group ${group === g ? 'open' : ''}`}>
              <button type="button" className="group-head" aria-expanded={group === g} onClick={() => setGroup(group === g ? null : g)}>
                <span className="advanced-group-copy"><b>{names[g]}</b><small>{descriptions[g]}</small></span><Icon name={group === g ? 'chevron-up' : 'chevron-down'} size={14} />
              </button>
              {group === g && (
                <div className="group-body">
                  <div className="adv-toggles">{toggles[g].map(toggle)}</div>
                  {g === 'look' && !remix && select('style', t.style, t.tip.style, [['none', t.auto], ...STYLES.map(id => [id, t.styles[id]] as [string, string])])}
                  {g === 'look' && !remix && select('transition_intensity', t.transitions, t.tip.transitions, [['auto', t.auto], ['subtle', t.subtle], ['moderate', t.moderate], ['bold', t.bold]])}
                  {g === 'look' && !remix && settings.text && (
                    <label className="field" title={t.tip.textAllowed}><span>{t.textAllowed}</span><input type="text" placeholder={t.textAllowedHint} value={settings.text_allowed} disabled={busy} onChange={e => onSettings({ text_allowed: e.target.value })} /></label>
                  )}
                  {g === 'look' && !remix && <>
                    <label className="chip-toggle"><input type="checkbox" checked={settings.efficient_sources ?? false} disabled={busy} onChange={e => onSettings({ efficient_sources: e.target.checked })} />{lang === 'fr' ? 'Économiser les générations pour les images fixes' : 'Save generations for still images'}</label>
                    <label className="field"><span>{lang === 'fr' ? 'Utiliser la vidéo de référence pour' : 'Use reference video for'}</span><select value={settings.reference_style ?? 'camera'} disabled={busy} onChange={e => onSettings({reference_style:e.target.value as 'camera'|'montage'})}><option value="camera">{lang === 'fr' ? 'Le regard caméra' : 'Camera look'}</option><option value="montage">{lang === 'fr' ? 'Le style de montage' : 'Editing style'}</option></select></label>
                  </>}
                  {g === 'sound' && musicalEditing && <>
                    {select('music_edit_mode', lang === 'fr' ? 'Rythme de montage' : 'Editing rhythm',
                      lang === 'fr' ? 'Énergie et accents mesurés, pas une reconnaissance automatique des émotions. Les coupes peuvent réutiliser les prises générées.' : 'Measured energy and accents, not automatic emotion recognition. Cuts can reuse generated takes.',
                      [...(settings.music_edit_mode === 'legacy' ? [['legacy', lang === 'fr' ? 'Ancien projet' : 'Legacy project'] as [Settings['music_edit_mode'], string]] : []),
                        ['adaptive', lang === 'fr' ? 'Adaptatif musical' : 'Adaptive musical'],
                        ['random', lang === 'fr' ? 'Aléatoire musical' : 'Random musical'],
                        ['regular', lang === 'fr' ? 'Régulier' : 'Regular'],
                        ['free', lang === 'fr' ? 'Libre' : 'Free']])}
                    {(settings.music_edit_mode === 'regular' || settings.music_edit_mode === 'legacy') &&
                      select('cut_every', t.cutEvery, t.tip.cutEvery, [['half_beat', t.halfBeat], ['beat', t.beat], ['2_beats', t.twoBeats], ['bar', t.bar], ['2_bars', t.twoBars], ['4_bars', t.fourBars]])}
                    {settings.music_edit_mode !== 'regular' && select('cut_density', t.cutDensity, t.tip.cutDensity, [['auto', t.auto], ['low', t.low], ['medium', t.medium], ['high', t.high]])}
                    {(settings.music_edit_mode === 'adaptive' || settings.music_edit_mode === 'random') &&
                      (['music_cut_variation', 'music_cut_sync'] as const).map(key => (
                        <label className="field" key={key}><span>{key === 'music_cut_variation'
                          ? (lang === 'fr' ? 'Variation des durées' : 'Duration variation')
                          : (lang === 'fr' ? 'Synchronisation musicale' : 'Musical synchronization')} · {Math.round(settings[key] * 100)}%</span>
                          <input type="range" min="0" max="1" step="0.05" disabled={busy} value={settings[key]}
                            onChange={event => onSettings({ [key]: Number(event.target.value) })} />
                        </label>
                      ))}
                    <small>{lang === 'fr'
                      ? 'La seed des options avancées reproduit les variations. Les changements de rythme concernent les prochaines analyses, pas le montage manuel. Le nombre de prises reste une contrainte minimale de coupes.'
                      : 'The advanced seed reproduces variations. Rhythm changes apply to the next analysis, not the manual montage. Take count sets a minimum number of cuts.'}</small>
                    {(settings.audio === 'voice' || settings.dialogue.trim()) && <small>{lang === 'fr'
                      ? 'Protection dialogue : le montage conserve son rythme narratif, sans recoupes musicales automatiques. Une voix qui dépasse la vidéo bloque l’export au lieu d’être tronquée.'
                      : 'Dialogue protection: the edit keeps narrative timing without automatic musical recuts. Audio beyond the picture blocks export instead of being truncated.'}</small>}
                  </>}
                  {g === 'sound' && !remix && settings.audio !== 'original' && number('bpm', t.bpm, t.tip.bpm, { min: 60, max: 200 })}
                  {g === 'sound' && settings.audio === 'new' && field('mood', t.mood, t.tip.mood)}
                  {g === 'sound' && mode === 'music' && number('music_start', t.musicStart, t.tip.musicStart, { min: -1, step: 0.5 })}
                  {g === 'look' && <details className="advanced-technical">
                    <summary>{lang === 'fr' ? 'Habillage animé' : 'Animated design'} <small>{lang === 'fr' ? 'facultatif' : 'optional'}</small></summary>
                    <div className="advanced-technical-body">
                      <small>{lang === 'fr' ? 'Les masques sont calculés automatiquement pour les contours et les effets ciblant le sujet.' : 'Masks are computed automatically for outlines and subject-aware effects.'}</small>
                      <label className="field"><span>{lang === 'fr' ? 'Activer l’habillage' : 'Enable animated design'}</span><input type="checkbox" checked={settings.motion_design ?? true} disabled={busy} onChange={e => onSettings({motion_design:e.target.checked})}/></label>
                      {settings.motion_design && <>
                        <label className="field"><span>{lang === 'fr' ? 'Style graphique' : 'Graphic style'}</span><select value={settings.motion_direction ?? 'editorial'} disabled={busy} onChange={e=>onSettings({motion_direction:e.target.value})}>{settings.motion_direction?.trim().startsWith('{') && <option value={settings.motion_direction}>{lang === 'fr' ? 'Personnalisé' : 'Custom'}</option>}<option value="minimal">{lang === 'fr' ? 'Sobre' : 'Minimal'}</option><option value="editorial">{lang === 'fr' ? 'Éditorial' : 'Editorial'}</option><option value="energetic">{lang === 'fr' ? 'Énergique' : 'Energetic'}</option></select></label>
                        <label className="field"><span>{lang === 'fr' ? 'Titre à afficher (facultatif)' : 'Title to display (optional)'}</span><input maxLength={120} value={settings.motion_title ?? ''} disabled={busy} onChange={e=>onSettings({motion_title:e.target.value})}/></label>
                      </>}
                    </div>
                  </details>}
                  {g === 'expert' && (
                    <>
                      <div className="field" title={t.tip.seed}><span>{t.seed}</span>
                        <div className="seed-field">
                          <input type="number" min={0} step={1} value={settings.seed ?? ''} placeholder={t.seedRandom} aria-label={t.seed} disabled={busy} onChange={e => onSettings({ seed: e.target.value === '' ? null : Math.max(0, Math.floor(Number(e.target.value))) })} />
                          {settings.seed !== null && <button type="button" className="seed-button" title={t.seedClear} aria-label={t.seedClear} disabled={busy} onClick={() => onSettings({ seed: null })}><Icon name="x" size={14} /></button>}
                          <button type="button" className="seed-button" title={t.seedPick} aria-label={t.seedPick} disabled={busy} onClick={() => onSettings({ seed: Math.floor(Math.random() * 2 ** 31) })}>
                            <Icon name="dice" size={14} />
                          </button>
                        </div>
                      </div>
                      <details className="advanced-technical">
                        <summary>{lang === 'fr' ? 'Réglages spécifiques' : 'Specific settings'}</summary>
                        <div className="advanced-technical-body">
                          {!remix && field('camera', t.camera, t.tip.camera, t.cameraHint)}
                          <label className="field"><span>{lang === 'fr' ? 'Dossier de sons personnels' : 'Personal sound library'}</span><input value={settings.sfx_library ?? ''} disabled={busy} onChange={e => onSettings({sfx_library:e.target.value})} placeholder="F:\\Audio\\SFX" /></label>
                          <label className="field" title={t.tip.motionLayers}><span>{t.motionLayers}</span><textarea rows={3} spellCheck={false} value={settings.motion_layers} disabled={busy} onChange={e => onSettings({ motion_layers: e.target.value })} /></label>
                        </div>
                      </details>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
          {changed > 0 && <button type="button" className="options-reset" disabled={busy} onClick={() => onSettings(optionDefaults())}>{t.resetOptions}</button>}
        </div>
      )}
    </details>
  )
}
