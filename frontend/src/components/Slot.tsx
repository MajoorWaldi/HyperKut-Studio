import { useEffect, useRef, useState } from 'react'
import type { Upload } from '../types'
import { Icon, type IconName } from './Icon'
import { useI18n } from '../i18n'

export type SlotIcon = 'video' | 'person' | 'music' | 'voice' | 'plus'

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
        {value ? (value.kind === 'image' ? null : <span className="file-name">{value.name}</span>) : <><span className="up-icon" aria-hidden><Icon name={NAMES[icon]} size={18} /></span>{label && <strong>{label}</strong>}{(sub ?? hint) && <small>{sub ?? hint}</small>}</>}
      </button>
      {value && onClear && <button type="button" className="slot-clear" onClick={onClear} aria-label="clear" title={tip ? `${value?.name ?? ''}` : undefined}><Icon name="x" size={12} /></button>}
      <input ref={input} type="file" accept={accept} hidden onChange={event => { const file = event.target.files?.[0]; if (file) onFile(file); event.target.value = '' }} />
    </div>
  )
}
