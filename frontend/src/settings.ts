import type { Settings } from './types'
import { levelValue } from './creativeControls'

export function applySettingsChanges(current: Settings, changes: Partial<Settings>): Settings {
  const keys = Object.keys(changes)
  const controlsOnly = keys.length > 0 && keys.every(key => key === 'structure' || key === 'creativity')
  const changedLevel = controlsOnly && (['structure','creativity'] as const).some(key => key in changes && levelValue(changes[key]!) !== levelValue(current[key]))
  const invalidate = keys.some(key => !['approved_brief','approved_brief_context'].includes(key))
  return { ...current, ...(controlsOnly ? (changedLevel ? {approved_brief_context:''} : {}) : invalidate ? {approved_brief:'',approved_brief_context:''} : {}), ...changes }
}

export const DEFAULTS: Settings = {
  music_volume: 1, motion_design: false, motion_direction: 'editorial', motion_title: '', motion_cues: '[]',
  efficient_sources: false, reference_style: 'camera', sfx_library: '',
  prompt: '', duration: 15, ratio: '9:16', quality: 'draft', structure: 85, creativity: 50, seed: null, audio: 'original', mood: '', bpm: 120,
  effects: false, text: false, sound_design: false, sound_effects: false, sub_cuts: false, music_sync: false, retry_bad_takes: true,
  dialogue: '', places: true, casting: false, camera: '', motion_layers: '[]', subject_mask: false, redraw_text: false, pose_only: false, quality_check: false, music_start: -1,
  style: 'none', cut_density: 'auto', transition_intensity: 'auto', cut_every: '2_beats', text_allowed: '',
  music_edit_mode: 'adaptive', music_cut_variation: 1, music_cut_sync: 1,
}

export function restoreSettings(saved: Partial<Settings>): Settings {
  return { ...DEFAULTS, ...saved, music_edit_mode: saved.music_edit_mode ?? 'legacy', cut_density: saved.cut_density ?? 'auto', music_cut_variation: saved.music_cut_variation ?? .5 }
}

export const STYLES = ['viral_aura_farming', 'hype_beat_drop', 'micro_emotion_pov', 'slowed_dream', 'glow_up', 'outfit_change', 'beauty_premium', 'product_advertising', 'narrative_cinematic', 'music_video'] as const

export type Option = 'effects' | 'text' | 'subject_mask' | 'redraw_text' | 'pose_only' | 'places' | 'casting' | 'sound_design' | 'sound_effects' | 'music_sync' | 'retry_bad_takes' | 'quality_check'

/** The on/off options each preset of quality sets: the quick settings. The options that only one mode has (mask, text redrawing, pose) are left as they are. */
export const QUICK: Record<'light' | 'balanced' | 'full', Partial<Record<Option, boolean>>> = {
  light: { effects: false, text: false, places: false, sound_design: false, sound_effects: false, retry_bad_takes: false, quality_check: false },
  balanced: { effects: true, text: true, places: true, sound_design: true, sound_effects: true, retry_bad_takes: true, quality_check: false },
  full: { effects: true, text: true, places: true, sound_design: true, sound_effects: true, retry_bad_takes: true, quality_check: true },
}

/** Every setting that the Options section holds: the ones it puts back to their default. */
export const OPTION_KEYS = ['music_volume', 'motion_design', 'motion_direction', 'motion_title', 'motion_cues', 'efficient_sources', 'reference_style', 'sfx_library', 'effects', 'text', 'sub_cuts', 'subject_mask', 'redraw_text', 'pose_only', 'places', 'casting', 'camera', 'sound_design', 'sound_effects', 'music_sync', 'bpm', 'mood', 'music_start', 'seed', 'motion_layers', 'retry_bad_takes', 'quality_check', 'style', 'cut_density', 'transition_intensity', 'cut_every', 'text_allowed', 'music_edit_mode', 'music_cut_variation', 'music_cut_sync'] as const

export const optionDefaults = (): Partial<Settings> => Object.fromEntries(OPTION_KEYS.map(key => [key, DEFAULTS[key]]))
