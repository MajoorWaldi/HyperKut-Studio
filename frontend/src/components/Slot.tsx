import { useEffect, useRef, useState } from 'react'
import type { Upload } from '../types'
import { Icon, type IconName } from './Icon'
import { useI18n } from '../i18n'

/** Whether a dropped file is of the kind this slot takes (`video/*`, `image/*`, `audio/*`, extensions, exact types). */
export function accepts(accept: string, file: { name: string; type: string }): boolean {
  return accept.split(',').map(part => part.trim().toLowerCase()).filter(Boolean).some(part =>
    part.startsWith('.') ? file.name.toLowerCase().endsWith(part) : part.endsWith('/*') ? file.type.toLowerCase().startsWith(part.slice(0, -1)) : file.type.toLowerCase() === part)
}

export type SlotIcon = 'video' | 'person' | 'music' | 'voice' | 'plus'

/** The audio being previewed: a second preview stops the first. */
let playing: HTMLAudioElement | null = null

const NAMES: Record<SlotIcon, IconName> = { video: 'video', person: 'user', music: 'music', voice: 'mic', plus: 'upload' }

interface Props {
  icon?: SlotIcon
  sub?: string
  value: Upload | null
  accept: string
  label: string
  hint?: string
  tip?: string
  compact?: boolean
  busy?: boolean
  onFile: (file: File) => void
  onFiles?: (files: File[]) => void  // several files of its kind dropped at once (pictures): the slot takes the first, the others go to the free slots
  onRejected?: (files: File[]) => void  // files dropped here that are not of its kind
  onClear?: () => void
}

/** Whether what is being dragged can land here: the types of the dragged items are known before the drop (not their names); none known, it may. */
function dragFits(accept: string, items: DataTransferItemList | undefined): boolean {
  const types = Array.from(items ?? []).filter(item => item.kind === 'file').map(item => item.type).filter(Boolean)
  return !types.length || types.some(type => accepts(accept, { name: '', type }))
}

/** An upload slot: shows the thumbnail of what was added, or invites to add something. A file can be dropped on it. */
export function Slot({ icon = 'plus', sub, value, accept, label, hint, tip, compact, busy, onFile, onFiles, onRejected, onClear }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const { t } = useI18n()
  const [over, setOver] = useState<false | 'fits' | 'refused'>(false)
  const drop = (event: React.DragEvent) => {
    event.preventDefault()
    event.stopPropagation()  // the panel does not route it again
    setOver(false)
    if (busy) return
    const files = Array.from(event.dataTransfer.files)
    const fitting = files.filter(candidate => accepts(accept, candidate))
    if (!fitting.length) { if (files.length) onRejected?.(files); return }
    if (fitting.length > 1 && onFiles) onFiles(fitting)
    else onFile(fitting[0])
    if (fitting.length < files.length) onRejected?.(files.filter(file => !fitting.includes(file)))
  }
  const dragOver = (event: React.DragEvent) => {
    if (!event.dataTransfer.types.includes('Files')) return
    event.preventDefault()
    event.stopPropagation()
    const fits = !busy && dragFits(accept, event.dataTransfer.items)
    event.dataTransfer.dropEffect = fits ? 'copy' : 'none'
    setOver(fits ? 'fits' : 'refused')
  }
  const [wave, setWave] = useState<{ id: string; peaks?: number[]; error?: boolean } | null>(null)
  const audioId = value?.kind === 'audio' ? value.id : null
  useEffect(() => {
    if (!audioId) return
    const controller = new AbortController()
    fetch(`/api/uploads/${audioId}/waveform`, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('Waveform request failed')
        const peaks: unknown = await response.json()
        if (!Array.isArray(peaks) || !peaks.length || !peaks.every(n => typeof n === 'number' && Number.isFinite(n) && n >= 0 && n <= 1)) throw new Error('Invalid waveform')
        if (!controller.signal.aborted) setWave({ id: audioId, peaks })
      })
      .catch(() => { if (!controller.signal.aborted) setWave({ id: audioId, error: true }) })
    return () => controller.abort()
  }, [audioId])
  const player = useRef<HTMLAudioElement | null>(null)
  const [preview, setPreview] = useState({ on: false, share: 0 })
  useEffect(() => () => {  // another file, a cleared slot or a closed panel ends the preview
    player.current?.pause()
    if (playing === player.current) playing = null
    player.current = null
    setPreview({ on: false, share: 0 })
  }, [audioId])
  const listen = () => {
    if (!value) return
    let audio = player.current
    if (audio && !audio.paused) { audio.pause(); return }
    if (!audio) {
      audio = new Audio(value.url)
      audio.addEventListener('timeupdate', () => setPreview(state => ({ ...state, share: audio!.duration ? audio!.currentTime / audio!.duration : 0 })))
      audio.addEventListener('pause', () => setPreview(state => ({ ...state, on: false })))
      audio.addEventListener('ended', () => setPreview({ on: false, share: 0 }))
      audio.addEventListener('error', () => setPreview({ on: false, share: 0 }))
      player.current = audio
    }
    if (playing && playing !== audio) playing.pause()
    playing = audio
    setPreview(state => ({ ...state, on: true }))
    audio.play().catch(() => setPreview(state => ({ ...state, on: false })))
  }
  const peaks = wave?.id === audioId ? wave.peaks : undefined
  const waveError = wave?.id === audioId && wave.error
  return (
    <div className={`slot-wrap ${over === 'fits' ? 'drag-over' : over === 'refused' ? 'drag-refused' : ''}`} onDragOver={dragOver}
      onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOver(false) }} onDrop={drop}>
      <button type="button" className={`upload ${compact ? 'compact' : ''}`} onClick={() => input.current?.click()} aria-label={label || tip} title={tip} disabled={busy}>
        {value?.kind === 'image' && <img src={value.url} alt={value.name} />}
        {value?.kind === 'video' && <video src={value.url} muted preload="metadata" />}
        {audioId && (peaks ? <svg className="upload-wave" viewBox={`0 0 ${peaks.length} 100`} preserveAspectRatio="none" role="img" aria-label={t.waveform}>
          <path d={peaks.map((peak, i) => `M${i + .5} ${50 - peak * 46}V${50 + peak * 46}`).join(' ')} stroke="currentColor" strokeWidth=".65" fill="none" />
          <path d={`M0 50H${peaks.length}`} stroke="currentColor" strokeWidth=".3" fill="none" />
        </svg> : <small role="status">{waveError ? t.waveformError : t.waveformLoading}</small>)}
        {audioId && preview.share > 0 && <span className="upload-progress" style={{ left: `calc(16px + (100% - 32px) * ${preview.share})` }} />}
        {value ? (value.kind === 'image' ? null : <span className="file-name">{value.name}</span>) : <><span className="up-icon" aria-hidden><Icon name={NAMES[icon]} size={18} /></span>{label && <strong>{label}</strong>}{(sub ?? hint) && <small>{sub ?? hint}</small>}</>}
      </button>
      {audioId && <button type="button" className="slot-play" onClick={listen} aria-label={preview.on ? t.listenPause : t.listen} title={preview.on ? t.listenPause : t.listen}><Icon name={preview.on ? 'pause' : 'play'} size={12} fill={!preview.on} /></button>}
      {value && onClear && <button type="button" className="slot-clear" onClick={onClear} aria-label="clear" title={tip ? `${value?.name ?? ''}` : undefined}><Icon name="x" size={12} /></button>}
      <input ref={input} type="file" accept={accept} multiple={!!onFiles} hidden onChange={event => {
        const files = Array.from(event.target.files ?? [])
        if (files.length > 1 && onFiles) onFiles(files)
        else if (files[0]) onFile(files[0])
        event.target.value = ''
      }} />
    </div>
  )
}
