import { useState } from 'react'
import { routeFiles } from '../drop'
import { useI18n } from '../i18n'
import type { AudioChoice, Inputs, Mode, Settings } from '../types'
import { Options } from './Options'
import { ArtDirection } from './ArtDirection'
import { CountBadge } from './CountBadge'
import { Icon } from './Icon'
import { Slot } from './Slot'
import { VideoModel } from './VideoModel'

export type SlotName = 'source' | 'refVideo' | 'music' | 'voice' | 'place' | { ref: number }

interface Props {
  mode: Mode
  inputs: Inputs
  settings: Settings
  busy: boolean
  onUpload: (slot: SlotName, file: File) => void
  onClear: (slot: SlotName) => void
  onRejected?: (files: File[]) => void  // dropped files that have no slot of their kind (free) here
  onPreparing?: (value: boolean) => void
  onSettings: (changes: Partial<Settings>) => void
  onReviewPlan?: () => void  // make the plan only, and approve it before any shot is generated
}

const AUDIO: AudioChoice[] = ['original', 'new', 'voice']

/** The ways to cut on a music that the Music tab offers; the other modes stay in the options of Remix and Text. */
const RHYTHMS = [
  { id: 'adaptive', en: 'Adaptive', fr: 'Adaptatif' },
  { id: 'regular', en: 'Regular', fr: 'Régulier' },
  { id: 'phrases', en: 'Vocal phrases', fr: 'Phrases vocales' },
  { id: 'hits', en: 'Hit sync', fr: 'Hit sync' },
] as const

export function InputsPanel({ mode, inputs, settings, busy, onUpload, onClear, onRejected, onSettings, onPreparing, onReviewPlan }: Props) {
  const { t, lang } = useI18n()
  const [dragging, setDragging] = useState(false)
  const place = (files: File[], first?: number) => {
    const { placed, refused } = routeFiles(files, { mode, audio: settings.audio, inputs }, first)
    placed.forEach(({ slot, file }) => onUpload(slot, file))
    if (refused.length) onRejected?.(refused)
  }
  const dropOnPanel = (event: React.DragEvent) => {  // a file dropped beside the slots goes to the first free one of its kind
    event.preventDefault()
    setDragging(false)
    if (!busy && event.dataTransfer.files.length) place(Array.from(event.dataTransfer.files))
  }
  const fr = lang === 'fr'
  // Keep original slot indices when a reference is removed or restored from a project.
  const nextRef = inputs.refs.findIndex(ref => ref === null)
  const visibleRefs: { ref: Inputs['refs'][number]; index: number }[] = inputs.refs.flatMap((ref, index) => ref ? [{ ref, index }] : [])
  if (nextRef >= 0) visibleRefs.push({ ref: null, index: nextRef })
  const audioLabel = { original: t.audioOriginal, new: t.audioNew, voice: t.audioVoice }
  const audioInfo = { original: t.audioOriginalInfo, new: t.audioNewInfo, voice: t.audioVoiceInfo }
  return (
    <aside className={`side ${dragging ? 'drop-ready' : ''}`} data-drop-hint={t.dropHere}
      onDragOver={event => { if (event.dataTransfer.types.includes('Files') && !busy) { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; setDragging(true) } }}
      onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false) }}
      onDropCapture={() => setDragging(false)} onDrop={dropOnPanel}>  {/* capture: a slot that takes the drop stops it before the panel */}
      {mode === 'remix' && (
        <section className="section">
          <h3 className="section-head">{t.stepSource} <span className="hint">{t.stepSourceHint}</span></h3>
          <Slot value={inputs.source} accept="video/*" icon="video" label={t.addVideo} tip={t.tip.source} busy={busy} onFile={f => onUpload('source', f)} onRejected={onRejected} onClear={() => onClear('source')} />
          <p className="tiny-label rights">{t.rightsVideo}</p>
        </section>
      )}
      <VideoModel mode={mode} settings={settings} busy={busy} refs={inputs.refs.filter(Boolean).length} refVideo={!!inputs.refVideo} music={!!inputs.music || settings.audio === 'voice'} onSettings={onSettings} />
      <section className="section">
        <h3 className="section-head">{t.stepRefs} <span className="hint">{t.stepRefsHint}</span></h3>
        <div className="ref-grid">
          {visibleRefs.map(({ ref, index: i }) => (
            <Slot key={i} value={ref} accept="image/*" icon={ref ? "person" : "plus"} label={ref ? `${t.reference} ${i + 1}` : t.addReference} tip={t.tip.refs} compact busy={busy} onFile={f => onUpload({ ref: i }, f)} onFiles={files => place(files, i)} onRejected={onRejected} onClear={() => onClear({ ref: i })} />
          ))}
        </div>
        <p className="tiny-label">{t.refsHint}</p>
      </section>
      <details className="secondary-settings" key={`ref-video-${mode}`}>
        <summary>{t.stepRefVideo}<CountBadge count={inputs.refVideo ? 1 : 0} label={fr ? 'actif(s)' : 'active'} /> <small>{inputs.refVideo?.name ?? t.stepOptional}</small></summary>
        <div className="secondary-settings-body">
          <Slot value={inputs.refVideo} accept="video/*" icon="video" label={t.addVideo} tip={t.tip.refVideo} compact busy={busy} onFile={f => onUpload('refVideo', f)} onRejected={onRejected} onClear={() => onClear('refVideo')} />
        </div>
      </details>
      <details className="secondary-settings" key={`place-${mode}`}>
        <summary>{t.stepPlace}<CountBadge count={inputs.place ? 1 : 0} label={fr ? 'actif(s)' : 'active'} /> <small>{inputs.place?.name ?? t.stepOptional}</small></summary>
        <div className="secondary-settings-body">
          <Slot value={inputs.place ?? null} accept="image/*" icon="globe" label={t.addPlace} tip={t.tip.place} compact busy={busy} onFile={f => onUpload('place', f)} onRejected={onRejected} onClear={() => onClear('place')} />
          <p className="tiny-label">{t.placeHint}</p>
        </div>
      </details>
      <section className="section">
        <h3 className="section-head">{t.stepPrompt}</h3>
        <textarea className="prompt" title={t.tip.prompt} maxLength={8000} value={settings.prompt} placeholder={mode === 'remix' ? t.promptRemix : t.promptPlaceholder} onChange={e => onSettings({ prompt: e.target.value })} disabled={busy} />
        <p className="tiny-label">{settings.prompt.length} / 8000</p>
      </section>
      <ArtDirection mode={mode} inputs={inputs} settings={settings} busy={busy} onSettings={onSettings} onPreparing={onPreparing} />
      {mode === 'music' && (
        <section className="section">
          <h3 className="section-head">{t.stepMusic}</h3>
          <Slot value={inputs.music} accept="audio/*" icon="music" label={t.addMusic} tip={t.tip.music} compact busy={busy} onFile={f => onUpload('music', f)} onRejected={onRejected} onClear={() => onClear('music')} />
          <div className="rhythm-choice">
            <span className="rhythm-label" title={t.tip.rhythmHeading}>{fr ? 'Rythme de montage' : 'Editing rhythm'}</span>
            <div className="segmented" role="group" aria-label={fr ? 'Rythme de montage' : 'Editing rhythm'}>
              {RHYTHMS.map(rhythm => <button type="button" key={rhythm.id} aria-pressed={settings.music_edit_mode === rhythm.id} disabled={busy} title={{ adaptive: t.tip.rhythmAdaptive, regular: t.tip.rhythmRegular, phrases: t.tip.rhythmPhrases, hits: t.tip.rhythmHits }[rhythm.id]} onClick={() => onSettings({ music_edit_mode: rhythm.id })}>{fr ? rhythm.fr : rhythm.en}</button>)}
              {!RHYTHMS.some(rhythm => rhythm.id === settings.music_edit_mode) && <button type="button" aria-pressed disabled title={t.tip.rhythmMode}>{fr ? 'Personnalisé' : 'Custom'}</button>}
            </div>
          </div>
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
              <Slot value={inputs.voice} accept="audio/*" icon="voice" label={t.addVoice} tip={t.tip.voice} compact busy={busy} onFile={f => onUpload('voice', f)} onRejected={onRejected} onClear={() => onClear('voice')} />
              <textarea className="prompt" title={t.tip.dialogue} maxLength={500} value={settings.dialogue} placeholder={t.dialogueHint} aria-label={t.dialogue} onChange={e => onSettings({ dialogue: e.target.value })} disabled={busy} />
            </>
          )}
        </section>
      )}
      <Options mode={mode} settings={settings} busy={busy} onSettings={onSettings} />
      {onReviewPlan && <button type="button" className="secondary review-plan" title={t.tip.reviewPlan} disabled={busy} onClick={onReviewPlan}><Icon name="film" size={14} /> {t.reviewPlan}</button>}
    </aside>
  )
}
