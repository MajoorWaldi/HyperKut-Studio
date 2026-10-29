import { useI18n } from '../i18n'
import type { Mode, Preset } from '../types'
import { Icon, type IconName } from './Icon'
import { Media, presetChips } from './Library'

const MODE_ICON: Record<Mode, IconName> = { remix: 'sparkles', text: 'type', music: 'music' }

interface Props {
  presets: Preset[]
  /** The preset that was applied from here, shown as chosen. */
  applied: string | null
  onApply: (id: string) => void
}

/** The first screen, until something is added: a few presets as cards (a picture or a loop when the preset has one, and the picture it starts from in the corner). A click applies the preset. */
export function Examples({ presets, applied, onApply }: Props) {
  const { t, lang } = useI18n()
  const name = { remix: t.modeRemix, text: t.modeText, music: t.modeMusic }
  const chosen = presets.find(p => p.id === applied)
  return (
    <section className="examples" aria-label={t.startTitle}>
      <h2>{t.startTitle}</h2>
      <p>{chosen ? (chosen.mode === 'remix' ? t.startNextRemix : chosen.mode === 'music' ? t.startNextMusic : t.startNextText) : t.startHint}</p>
      <div className={`example-grid ${presets.length > 4 ? 'three' : ''}`}>
        {presets.map(preset => (
          <button key={preset.id} type="button" className={`example-card ${preset.preview ? 'has-preview' : ''} ${preset.id === applied ? 'selected' : ''}`} title={preset.prompt} onClick={() => onApply(preset.id)} aria-pressed={preset.id === applied}>
            {preset.preview && <span className="example-backdrop" aria-hidden="true"><Media url={`/api/presets/media/${preset.preview}`} playing /></span>}
            <span className={`example-media ${preset.mode}`}>
              {!preset.preview && <Icon name={MODE_ICON[preset.mode]} size={34} />}
              {preset.reference && <img className="example-reference" src={`/api/presets/media/${preset.reference}`} alt="" />}
              <span className="lib-mode">{name[preset.mode]}</span>
              {preset.id === applied && <span className="example-check" aria-hidden><Icon name="check" size={14} /></span>}
            </span>
            <b>{preset.name}</b>
            <small>{preset.description}</small>
            <span className="chips">{presetChips(preset, lang).slice(0, 4).map(chip => <i key={chip}>{chip}</i>)}</span>
          </button>
        ))}
      </div>
      <p className="examples-note rights">{t.rightsStart}</p>
    </section>
  )
}
