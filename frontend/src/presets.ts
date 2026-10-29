import type { Lang } from './i18n'
import type { Preset, Settings } from './types'

export function localizePreset(preset: Preset, lang: Lang): Preset {
  const text = preset.translations?.[lang]
  return text ? {...preset, ...text, settings: {...preset.settings, ...text.settings}} : preset
}

// Only translate untouched preset fields; a user's edits always take precedence.
export function translatePresetSettings(current: Settings, preset: Preset, lang: Lang): Settings {
  const target = localizePreset(preset, lang)
  const variants = [preset, localizePreset(preset, 'en'), localizePreset(preset, 'fr')]
  const patch: Partial<Settings> = {}
  if (variants.some(p => p.prompt === current.prompt)) patch.prompt = target.prompt
  for (const key of ['mood', 'camera'] as const) {
    if (variants.some(p => p.settings?.[key] === current[key])) patch[key] = target.settings?.[key] ?? ''
  }
  return {...current, ...patch, approved_brief: '', approved_brief_context: ''}
}
