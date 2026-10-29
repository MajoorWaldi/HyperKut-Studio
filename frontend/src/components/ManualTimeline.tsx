import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import { useI18n } from '../i18n'
import { Icon } from './Icon'
import type { JobState, ManualTimelinePayload, TimelineDocument } from '../types'

interface Props { job: JobState; onState: (state: JobState) => void }
interface Draft { expected: string | null; document: TimelineDocument }

export function ManualTimeline({ job, onState }: Props) {
  const { t } = useI18n()
  const [payload, setPayload] = useState<ManualTimelinePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [revision, setRevision] = useState(0)
  const closeEditor = useRef<(() => void) | null>(null)
  const pending = useRef(false)
  const mounted = useRef(true)
  const activeOperation = useRef(false)
  const key = `secator.timeline.${job.id}`
  const running = job.status === 'running' || job.status === 'queued'
  const disabled = busy || running
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; closeEditor.current?.() }
  }, [])
  useEffect(() => {
    activeOperation.current = running
    if (running) { closeEditor.current?.(); return }
    let current = true
    api.manualTimeline(job.id).then(result => {
      if (!current) return
      if (!result?.initial || !Array.isArray(result.library)) throw new Error(t.manualUnavailable)
      setPayload(result)
    }).catch(reason => { if (current) setError((reason as Error).message) })
    return () => { current = false }
  }, [job.id, running, job.operation, revision, t.manualUnavailable])

  const action = async (work: () => Promise<void>) => {
    if (pending.current || running) return
    pending.current = true; setBusy(true); setError(null)
    try { await work() }
    catch (reason) { if (mounted.current) setError((reason as Error).message) }
    finally { pending.current = false; if (mounted.current) setBusy(false) }
  }
  const remember = (document: TimelineDocument, expected: string | null) => {
    localStorage.setItem(key, JSON.stringify({ document, expected }))
  }
  const open = () => void action(async () => {
    const fresh = await api.manualTimeline(job.id)
    if (fresh.stale) { setPayload(fresh); throw new Error(t.manualStale) }
    const raw = localStorage.getItem(key)
    let document = fresh.document
    if (raw) {
      const draft: Draft = JSON.parse(raw)
      if (draft.expected !== fresh.etag || draft.document.source_signature !== fresh.initial.source_signature) {
        throw new Error(t.manualDraftConflict)
      }
      document = draft.document
    }
    const editor = await api.loadTimelineEditor()
    if (!mounted.current || activeOperation.current) return
    setPayload(fresh)
    let expected = fresh.etag
    const save = async (next: TimelineDocument) => {
      const result = await api.saveManualTimeline(job.id, next, expected, true)
      expected = result.etag
      localStorage.removeItem(key)
      if (mounted.current) {
        setPayload({ ...fresh, document: next, etag: expected, enabled: true })
        setNotice(t.manualSaved)
      }
      return result
    }
    closeEditor.current?.()
    const mediaSelector = '.preview video, .preview audio, .shot-panel video, .shot-panel audio'
    const pauseStudioPlayback = (event: Event) => {
      const target = event.target
      if (target instanceof HTMLMediaElement && target.matches(mediaSelector)) target.pause()
    }
    window.document.querySelectorAll<HTMLMediaElement>(mediaSelector).forEach(media => media.pause())
    closeEditor.current = editor.openTimelineEditor(fresh, document, {
      theme: 'studio',
      urlFor: file => api.timelineMediaURL(job.id, file),
      onChange: next => remember(next, expected),
      onClose: () => {
        window.document.removeEventListener('play', pauseStudioPlayback, true)
        closeEditor.current = null
        if (mounted.current) setRevision(value => value + 1)
      },
      onSave: async next => { await save(next) },
      onRender: async next => {
        const saved = await save(next)
        const state = await api.renderManualTimeline(job.id, saved.etag)
        closeEditor.current?.()
        onState(state)
      },
      labels: { save: t.manualSave, render: t.manualRender, saving: t.manualSaving, saved: t.manualSaved },
    })
    window.document.addEventListener('play', pauseStudioPlayback, true)
  })

  const reset = () => void action(async () => {
    if (!window.confirm(t.manualResetConfirm)) return
    const fresh = await api.manualTimeline(job.id)
    await api.saveManualTimeline(job.id, fresh.initial, fresh.etag, true)
    localStorage.removeItem(key)
    setNotice(t.manualSaved); setRevision(value => value + 1)
  })

  const download = () => void action(async () => {
    const raw = localStorage.getItem(key)
    const savedDocument = raw ? JSON.parse(raw).document : payload?.document
    if (!savedDocument) throw new Error(t.manualUnavailable)
    const url = URL.createObjectURL(new Blob([JSON.stringify(savedDocument, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url; link.download = `timeline-${job.id}.json`; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  })

  return <section className="manual-timeline" aria-label={t.manualTitle}>
    <div className="manual-heading">
      <span className="manual-mark"><Icon name="scissors" size={19} /></span>
      <h3>{t.manualTitle}</h3>
      {payload && <span className={`manual-badge ${payload.enabled ? 'on' : ''}`}>{payload.enabled ? t.manualActive : t.manualInactive}</span>}
    </div>
    <div className="manual-actions">
      <button type="button" className="primary" disabled={disabled || !payload || payload.stale} onClick={open}><Icon name="scissors" size={15} />{t.manualOpen}</button>
      <button type="button" className="secondary" disabled={disabled || !payload?.etag} onClick={() => void action(async () => {
        if (!payload) return
        await api.saveManualTimeline(job.id, payload.document, payload.etag, !payload.enabled)
        setRevision(value => value + 1)
      })}><Icon name="sliders" size={14} />{payload?.enabled ? t.manualDisable : t.manualEnable}</button>
      <button type="button" className="secondary" disabled={disabled || !payload?.stale} onClick={() => void action(async () => {
        if (!payload) return
        await api.rebaseManualTimeline(job.id, payload.etag)
        setNotice(t.manualRebased); setRevision(value => value + 1)
      })}><Icon name="refresh" size={14} />{t.manualRebase}</button>
      <button type="button" className="secondary" disabled={disabled || !payload} onClick={reset}><Icon name="film" size={14} />{t.manualReset}</button>
      <button type="button" className="secondary" disabled={disabled || !payload} onClick={download}><Icon name="download" size={14} />{t.manualDownload}</button>
      <button type="button" className="secondary manual-discard" disabled={disabled || !payload} onClick={() => void action(async () => {
        if (!window.confirm(t.manualDiscardDraft)) return
        localStorage.removeItem(key); setRevision(value => value + 1); setNotice(''); setError(null)
      })}><Icon name="eraser" size={14} />{t.manualDiscard}</button>
    </div>
    {payload && <small className="manual-metrics"><Icon name="film" size={13} />{payload.document.clips.length} clips <span>·</span><Icon name="clock" size={13} />{(payload.document.clips.reduce((sum, clip) => sum + clip.out_frame - clip.in_frame, 0) * payload.document.fps_den / payload.document.fps_num).toFixed(2)} s</small>}
    {payload?.stale && <p role="alert">{t.manualStale}</p>}
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {job.manual_export && <small>{t.manualLastExport}: {job.manual_export.clips} clips · {job.manual_export.duration.toFixed(2)} s</small>}
  </section>
}
