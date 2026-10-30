import { useEffect, useMemo, useRef, useState } from 'react'
import { useI18n } from '../i18n'
import { Icon, type IconName } from './Icon'
import type { JobState, Mode, Preset } from '../types'
import { controlCopy, levelIndex, poseStrength } from '../creativeControls'

type Tab = 'projects' | 'presets'

interface Props {
  open: boolean
  onClose: () => void
  jobs: JobState[]
  sizes: Record<string, number>
  presets: Preset[]
  mode: Mode
  currentJob: string | null
  onOpenJob: (id: string) => void
  onDuplicateJob: (id: string) => void
  onPatchJob: (id: string, patch: { title?: string; pinned?: boolean }) => void
  onDeleteJob: (id: string, withFiles: boolean) => void
  onFree: (id: string) => void
  onApplyPreset: (id: string) => void
  onSavePreset: (name: string, description: string) => void
  onDeletePreset: (id: string) => void
  onImportPreset: (file: File) => void
  onImportProject: (file: File) => void
}

const MODES: Mode[] = ['remix', 'text', 'music']
const MODE_ICON: Record<Mode, IconName> = { remix: 'sparkles', text: 'type', music: 'music' }
const isVideo = (url: string) => /\.(mp4|webm|mov)$/i.test(url)

export const megabytes = (bytes: number) => (bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(bytes / 1e6))} MB`)

/** The chips that say what a preset sets, in a few words. */
export function presetChips(preset: Preset, lang: 'en' | 'fr' = 'en'): string[] {
  const s = preset.settings ?? {}
  return [s.ratio, s.duration !== undefined ? `${s.duration} s` : undefined, s.quality ? ({draft: lang === 'fr' ? 'Brouillon' : 'Draft', standard: 'Standard', max: lang === 'fr' ? 'Maximale' : 'Maximum', xhigh: 'XHigh'})[s.quality] : undefined, s.structure !== undefined ? preset.mode==='remix' ? `Pose ${poseStrength(s.structure).toFixed(2)}` : controlCopy(lang==='fr').fidelityLevels[levelIndex(s.structure)] : undefined, preset.mode !== 'music' && s.bpm !== undefined ? `${s.bpm} BPM` : undefined, s.camera]
    .filter((chip): chip is string => typeof chip === 'string' && chip !== '')
}

/** A picture or a short loop: a video plays while the pointer is over the card, a picture (a gif included) is always shown. */
export function Media({ url, playing }: { url: string; playing: boolean }) {
  return isVideo(url)
    ? (playing ? <video src={url} muted loop autoPlay playsInline /> : null)
    : <img src={url} alt="" loading="lazy" />
}

/** What a preset loads as inputs, over its card: the source video, the reference pictures and the waveform of the music. The video plays while `playing`. */
export function PresetInputs({ preset, playing }: { preset: Preset; playing: boolean }) {
  const { t } = useI18n()
  const inputs = preset.inputs
  const musicId = inputs?.music?.id
  const [peaks, setPeaks] = useState<{ id: string; values: number[] } | null>(null)
  useEffect(() => {
    if (!musicId) return
    const controller = new AbortController()
    fetch(`/api/uploads/${musicId}/waveform`, { signal: controller.signal })
      .then(response => response.ok ? response.json() : Promise.reject())
      .then((values: number[]) => setPeaks({ id: musicId, values }))
      .catch(() => {})
    return () => controller.abort()
  }, [musicId])
  const wave = peaks && peaks.id === musicId ? peaks.values : undefined
  const refs = (inputs?.refs ?? []).filter(ref => ref !== null)
  if (!inputs?.source && !refs.length && !wave) return null
  return (
    <>
      {wave && <svg className="preset-wave" viewBox={`0 0 ${wave.length} 100`} preserveAspectRatio="none" role="img" aria-label={t.waveform}>
        <path d={wave.map((peak, i) => `M${i + .5} ${50 - peak * 46}V${50 + peak * 46}`).join(' ')} stroke="currentColor" strokeWidth=".65" fill="none" />
      </svg>}
      <span className="preset-inputs">
        {inputs?.source && <video key={playing ? 'on' : 'off'} src={`${inputs.source.url}#t=0.1`} muted loop playsInline preload="metadata" autoPlay={playing} />}
        {refs.slice(0, 4).map(ref => <img key={ref.id} src={ref.url} alt="" loading="lazy" />)}
      </span>
    </>
  )
}

/** The library: the projects as cards with a preview of their result, and the presets as cards with what they set. It lies over the side column and goes wider than it; the button above the loaders opens and closes it; a press outside closes it too. */
export function Library(props: Props) {
  const { open, onClose, jobs, sizes, presets, mode, currentJob } = props
  const { t, lang } = useI18n()
  const [tab, setTab] = useState<Tab>('projects')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<Mode | 'all'>('all')
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const block = useRef<HTMLElement>(null)
  const projectFile = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    setTab('projects')
    const previous = document.activeElement as HTMLElement | null
    const panel = block.current
    panel?.querySelector<HTMLButtonElement>('button')?.focus()
    return () => {
      if (panel?.contains(document.activeElement) || document.activeElement === document.body) previous?.focus()
    }
  }, [open])

  // light dismiss: a press outside the library closes it, and so does Escape (the button that opens it toggles it by itself)
  useEffect(() => {
    if (!open) return
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    const outside = (event: PointerEvent) => {
      const target = event.target as Element
      if (!block.current?.contains(target) && !target.closest('.library-toggle')) onClose()
    }
    document.addEventListener('keydown', escape)
    document.addEventListener('pointerdown', outside)
    return () => { document.removeEventListener('keydown', escape); document.removeEventListener('pointerdown', outside) }
  }, [open, onClose])

  const shown = useMemo(() => jobs
    .filter(j => (filter === 'all' || j.mode === filter) && (j.title || j.id).toLowerCase().includes(search.trim().toLowerCase()))
    .sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.created_at - a.created_at), [jobs, filter, search])
  const ordered = useMemo(() => [...presets].sort((a, b) => Number(b.mode === mode) - Number(a.mode === mode)), [presets, mode])
  const statusName = { queued: t.statusQueued, running: t.statusRunning, succeeded: t.statusDone, failed: t.statusFailed, cancelled: t.statusCancelled }
  const modeName = { remix: t.modeRemix, text: t.modeText, music: t.modeMusic }
  const date = (seconds: number) => new Date(seconds * 1000).toLocaleString(lang, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

  const exportPreset = (preset: Preset) => {
    const { id: _id, user: _user, ...clean } = preset
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([JSON.stringify(clean, null, 1)], { type: 'application/json' }))
    link.download = `${preset.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.json`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  if (!open) return null
  return (
    <section ref={block} className="library-block" aria-label={t.library}>
      <header>
        <div className="lib-tabs">
          <button type="button" className={tab === 'projects' ? 'on' : ''} onClick={() => setTab('projects')}>{t.projects} <small>{jobs.length}</small></button>
          <button type="button" className={tab === 'presets' ? 'on' : ''} onClick={() => setTab('presets')}>{t.presets} <small>{presets.length}</small></button>
        </div>
        {tab === 'projects' && (
          <div className="lib-tools">
            <input type="search" placeholder={t.search} aria-label={t.search} value={search} onChange={e => setSearch(e.target.value)} />
            <button type="button" onClick={() => projectFile.current?.click()}>{t.importProject}</button>
            <input ref={projectFile} type="file" accept=".zip,application/zip" hidden onChange={event => {
              const file = event.currentTarget.files?.[0]
              event.currentTarget.value = ''
              if (file) props.onImportProject(file)
            }} />
            <div className="lib-filter">
              {(['all', ...MODES] as const).map(m => <button key={m} type="button" className={filter === m ? 'on' : ''} onClick={() => setFilter(m)}>{m === 'all' ? t.all : modeName[m]}</button>)}
            </div>
          </div>
        )}
        <button type="button" className="lib-close" aria-label={t.close} onClick={onClose}><Icon name="x" size={18} /></button>
      </header>

      {tab === 'projects' && (
        <>
          {shown.length === 0 && <p className="lib-empty">{jobs.length === 0 ? <strong>{lang === 'fr' ? 'Commence avec un preset dans l’onglet Presets.' : 'Start with a preset in the Presets tab.'}</strong> : t.noMatch}</p>}
          <div className="lib-grid">
            {shown.map(job => {
              const size = sizes[job.id]
              const seconds = job.shots.reduce((sum, s) => sum + s.duration, 0)
              return (
                <article key={job.id} className={`lib-card ${job.id === currentJob ? 'current' : ''}`} onMouseEnter={() => setHover(job.id)} onMouseLeave={() => setHover(null)}>
                  <div className="lib-thumb">
                    <button type="button" className="lib-cover" title={`${t.tip.openProject}\n${date(job.created_at)}`} onClick={() => props.onOpenJob(job.id)}>
                      {job.output_url ? <img src={`/api/jobs/${job.id}/cover?v=${job.output_url.split('v=')[1] ?? 0}`} alt="" loading="lazy" /> : <span className="lib-nocover"><Icon name={MODE_ICON[job.mode]} size={34} /></span>}
                      {hover === job.id && job.output_url && <video src={job.output_url} muted loop autoPlay playsInline />}
                      <span className="lib-mode">{modeName[job.mode]}</span>
                      <span className={`lib-status ${job.status}`}>{statusName[job.status]}</span>
                    </button>
                    {deleting === job.id ? (
                      <div className="lib-confirm over">
                        <button type="button" className="danger" title={t.tip.deleteFiles} onClick={() => { props.onDeleteJob(job.id, true); setDeleting(null) }}>{t.deleteFiles}</button>
                        <button type="button" title={t.tip.forget} onClick={() => { props.onDeleteJob(job.id, false); setDeleting(null) }}>{t.forget}</button>
                        <button type="button" onClick={() => setDeleting(null)}>{t.cancelShort}</button>
                      </div>
                    ) : (
                      <div className="lib-actions over">
                        <button type="button" className={job.pinned ? 'on' : ''} aria-pressed={job.pinned} title={t.pin} onClick={() => props.onPatchJob(job.id, { pinned: !job.pinned })}><Icon name="star" size={14} fill={job.pinned} /></button>
                        <button type="button" title={t.rename} onClick={() => setRenaming({ id: job.id, title: job.title })}><Icon name="pencil" size={14} /></button>
                        <button type="button" title={t.tip.duplicate} onClick={() => props.onDuplicateJob(job.id)}><Icon name="copy" size={14} /></button>
                        {job.project_id && (job.status === 'succeeded' || job.status === 'failed' || job.status === 'cancelled') && <button type="button" title={t.tip.free} onClick={() => props.onFree(job.id)}><Icon name="eraser" size={14} /></button>}
                        <button type="button" title={t.delete} disabled={job.status === 'running' || job.status === 'queued'} onClick={() => setDeleting(job.id)}><Icon name="trash" size={14} /></button>
                      </div>
                    )}
                  </div>
                  <div className="lib-body">
                    {renaming?.id === job.id ? (
                      <input className="lib-rename" autoFocus value={renaming.title} aria-label={t.rename} onChange={e => setRenaming({ id: job.id, title: e.target.value })}
                        onBlur={() => setRenaming(null)} onKeyDown={e => { if (e.key === 'Enter') { props.onPatchJob(job.id, { title: renaming.title }); setRenaming(null) } if (e.key === 'Escape') setRenaming(null) }} />
                    ) : <b className="lib-title" onClick={() => props.onOpenJob(job.id)}>{job.title || job.id}</b>}
                    <small title={date(job.created_at)}>{job.shots.length} {t.shots} · {seconds.toFixed(0)} {t.seconds}{size ? ` · ${megabytes(size)}` : ''}</small>
                  </div>
                </article>
              )
            })}
          </div>
        </>
      )}

      {tab === 'presets' && (
        <>
          <form className="lib-save" onSubmit={event => { event.preventDefault(); if (name.trim()) { props.onSavePreset(name.trim(), description.trim()); setName(''); setDescription('') } }}>
            <b>{t.saveAsPreset}</b>
            <input value={name} maxLength={60} placeholder={t.presetName} aria-label={t.presetName} onChange={e => setName(e.target.value)} />
            <input value={description} maxLength={200} placeholder={t.presetDescription} aria-label={t.presetDescription} onChange={e => setDescription(e.target.value)} />
            <div>
              <button type="submit" className="primary-soft" disabled={!name.trim()} title={t.tip.savePreset}>{t.save}</button>
              <label className="lib-import" title={t.tip.importPreset}>{t.importPreset}<input type="file" accept="application/json,.json" hidden onChange={e => { const file = e.target.files?.[0]; if (file) props.onImportPreset(file); e.target.value = '' }} /></label>
            </div>
          </form>
          <div className="lib-grid presets">
            {ordered.map(preset => (
              <article key={preset.id} className={`lib-preset ${preset.mode === mode ? '' : 'dim'}`} onMouseEnter={() => setHover(preset.id)} onMouseLeave={() => setHover(null)}>
                <button type="button" className="lib-preset-main" title={`${preset.prompt}\n\n${t.tip.applyPreset}`} onClick={() => props.onApplyPreset(preset.id)}>
                  <span className={`lib-preview ${preset.mode}`}>
                    {preset.preview ? <Media url={`/api/presets/media/${preset.preview}`} playing={hover === preset.id} /> : <span className="lib-nocover"><Icon name={MODE_ICON[preset.mode]} size={34} /></span>}
                    <PresetInputs preset={preset} playing={hover === preset.id} />
                    <span className="lib-mode">{modeName[preset.mode]}</span>
                  </span>
                  <span className="lib-preset-top"><b>{preset.name}</b></span>
                  <small>{preset.description}</small>
                  <span className="chips">{presetChips(preset, lang).map(chip => <i key={chip}>{chip}</i>)}</span>
                </button>
                <div className="lib-actions">
                  <button type="button" title={t.tip.exportPreset} onClick={() => exportPreset(preset)}><Icon name="download" size={14} /></button>
                  {preset.user && <button type="button" title={t.delete} onClick={() => props.onDeletePreset(preset.id)}><Icon name="trash" size={14} /></button>}
                  {preset.user && <span className="lib-user">{t.mine}</span>}
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
