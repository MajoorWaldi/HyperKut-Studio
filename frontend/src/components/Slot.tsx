import { useEffect, useRef, useState } from 'react'
import type { Upload } from '../types'
import { Icon, type IconName } from './Icon'
import { useI18n } from '../i18n'

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
  onClear?: () => void
}

/** An upload slot: shows the thumbnail of what was added, or invites to add something. */
export function Slot({ icon = 'plus', sub, value, accept, label, hint, tip, compact, busy, onFile, onClear }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const { t } = useI18n()
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
    <div className="slot-wrap">
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
      <input ref={input} type="file" accept={accept} hidden onChange={event => { const file = event.target.files?.[0]; if (file) onFile(file); event.target.value = '' }} />
    </div>
  )
}
