import { useI18n } from '../i18n'
import type { AudioChoice, Inputs, Mode, Settings } from '../types'
import { Options } from './Options'
import { ArtDirection } from './ArtDirection'
import { Slot } from './Slot'

export type SlotName = 'source' | 'refVideo' | 'music' | 'voice' | { ref: number }

interface Props {
  mode: Mode
  inputs: Inputs
  settings: Settings
  busy: boolean
  onUpload: (slot: SlotName, file: File) => void
  onClear: (slot: SlotName) => void
  onPreparing?: (value: boolean) => void
  onSettings: (changes: Partial<Settings>) => void
}

const AUDIO: AudioChoice[] = ['original', 'new', 'voice']

export function InputsPanel({ mode, inputs, settings, busy, onUpload, onClear, onSettings, onPreparing }: Props) {
  const { t } = useI18n()
  // Keep original slot indices when a reference is removed or restored from a project.
  const nextRef = inputs.refs.findIndex(ref => ref === null)
  const visibleRefs: { ref: Inputs['refs'][number]; index: number }[] = inputs.refs.flatMap((ref, index) => ref ? [{ ref, index }] : [])
  if (nextRef >= 0) visibleRefs.push({ ref: null, index: nextRef })
  const audioLabel = { original: t.audioOriginal, new: t.audioNew, voice: t.audioVoice }
  const audioInfo = { original: t.audioOriginalInfo, new: t.audioNewInfo, voice: t.audioVoiceInfo }
  return (
    <aside className="side">
      {mode === 'remix' && (
        <section className="section">
          <h3 className="section-head">{t.stepSource} <span className="hint">{t.stepSourceHint}</span></h3>
          <Slot value={inputs.source} accept="video/*" icon="video" label={t.addVideo} tip={t.tip.source} busy={busy} onFile={f => onUpload('source', f)} onClear={() => onClear('source')} />
          <p className="tiny-label rights">{t.rightsVideo}</p>
        </section>
      )}
      <section className="section">
        <h3 className="section-head">{t.stepRefs} <span className="hint">{t.stepRefsHint}</span></h3>
        <div className="ref-grid">
          {visibleRefs.map(({ ref, index: i }) => (
            <Slot key={i} value={ref} accept="image/*" icon={ref ? "person" : "plus"} label={ref ? `${t.reference} ${i + 1}` : t.addReference} tip={t.tip.refs} compact busy={busy} onFile={f => onUpload({ ref: i }, f)} onClear={() => onClear({ ref: i })} />
          ))}
        </div>
        <p className="tiny-label">{t.refsHint}</p>
      </section>
      <details className="secondary-settings" key={`ref-video-${mode}`}>
        <summary>{t.stepRefVideo} <small>{inputs.refVideo?.name ?? t.stepOptional}</small></summary>
        <div className="secondary-settings-body">
          <Slot value={inputs.refVideo} accept="video/*" icon="video" label={t.addVideo} tip={t.tip.refVideo} compact busy={busy} onFile={f => onUpload('refVideo', f)} onClear={() => onClear('refVideo')} />
        </div>
      </details>
      <section className="section">
        <h3 className="section-head">{t.stepPrompt}</h3>
        <textarea className="prompt" title={t.tip.prompt} maxLength={1000} value={settings.prompt} placeholder={mode === 'remix' ? t.promptRemix : t.promptPlaceholder} onChange={e => onSettings({ prompt: e.target.value })} disabled={busy} />
        <p className="tiny-label">{settings.prompt.length} / 1000</p>
      </section>
      <ArtDirection mode={mode} inputs={inputs} settings={settings} busy={busy} onSettings={onSettings} onPreparing={onPreparing} />
      {mode === 'music' && (
        <section className="section">
          <h3 className="section-head">{t.stepMusic}</h3>
          <Slot value={inputs.music} accept="audio/*" icon="music" label={t.addMusic} tip={t.tip.music} compact busy={busy} onFile={f => onUpload('music', f)} onClear={() => onClear('music')} />
          {!inputs.music && <p className="tiny-label">{t.noMusic}</p>}
          <p className="tiny-label rights">{t.rightsMusic}</p>
        </section>
      )}
      {mode !== 'music' && (
        <section className="section" key={`audio-${mode}`}>
          <h3 className="section-head">{t.stepAudio}</h3>
          <div className="audio-options">
            {AUDIO.filter(choice => mode === 'remix' || choice !== 'original').map(choice => (
              <button key={choice} type="button" title={{ original: t.tip.audioOriginal, new: t.tip.audioNew, voice: t.tip.audioVoice }[choice]} className={`audio-opt ${settings.audio === choice ? 'selected' : ''}`} onClick={() => onSettings({ audio: choice })} disabled={busy}>{audioLabel[choice]}</button>
            ))}
          </div>
          <p className="small-info">{audioInfo[settings.audio]}</p>
          {settings.audio === 'voice' && (
            <>
              <h3 className="section-head">{t.stepVoice}</h3>
              <Slot value={inputs.voice} accept="audio/*" icon="voice" label={t.addVoice} tip={t.tip.voice} compact busy={busy} onFile={f => onUpload('voice', f)} onClear={() => onClear('voice')} />
              <textarea className="prompt" title={t.tip.dialogue} maxLength={500} value={settings.dialogue} placeholder={t.dialogueHint} aria-label={t.dialogue} onChange={e => onSettings({ dialogue: e.target.value })} disabled={busy} />
            </>
          )}
        </section>
      )}
      <Options mode={mode} settings={settings} busy={busy} onSettings={onSettings} />
    </aside>
  )
}
