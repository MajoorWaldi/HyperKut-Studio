import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import { useI18n } from '../i18n'
import type { AICandidate, AIOperation, JobState, Shot, Take } from '../types'

interface Props {
  job: JobState
  shot: Shot
  take: Take | null
  prompt: string
  onState: (job: JobState) => void
}

export function AICandidatePanel({ job, shot, take, prompt, onState }: Props) {
  const { t } = useI18n()
  const [enabled, setEnabled] = useState(false)
  const [candidates, setCandidates] = useState<AICandidate[]>([])
  const [operation, setOperation] = useState<Exclude<AIOperation, 'regenerate'>>('extend_after')
  const [seconds, setSeconds] = useState(3)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refresh, setRefresh] = useState(0)
  const mounted = useRef(true)
  const running = job.status === 'running' || job.status === 'queued'
  const controlsDisabled = busy || running || shot.locked
  const ready = candidates.filter(row => row.status === 'ready')
  const latest = candidates.at(-1)
  const pending = candidates.find(row => row.status === 'queued' || row.status === 'running')

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  useEffect(() => {
    let current = true
    api.aiCandidates(job.id, shot.id).then(result => {
      // Older backends and generic test fixtures do not expose this capability.
      if (!current) return
      if (typeof result?.enabled !== 'boolean' || !Array.isArray(result.candidates)) {
        setError(t.aiEditUnavailable)
        return
      }
      setEnabled(result.enabled)
      setCandidates(result.candidates)
    }).catch(reason => { if (current) setError((reason as Error).message) })
    return () => { current = false }
  }, [job.id, shot.id, job.status, job.operation, refresh, t.aiEditUnavailable])

  const launch = async () => {
    if (controlsDisabled || !take?.active || !prompt.trim()) return
    setBusy(true); setError(null)
    try {
      const result = await api.startAICandidate(job.id, shot.id, { operation, take: take.id, prompt, seconds, seed: 42 })
      onState(result.job)
      if (mounted.current) setRefresh(value => value + 1)
    } catch (reason) { if (mounted.current) setError((reason as Error).message) }
    finally { if (mounted.current) setBusy(false) }
  }

  const decide = async (id: string, decision: 'accept' | 'reject') => {
    if (controlsDisabled) return
    if (decision === 'accept' && !window.confirm(t.aiEditConfirm)) return
    setBusy(true); setError(null)
    try {
      const state = await api.decideAICandidate(job.id, id, decision)
      onState(state)
      if (mounted.current) setRefresh(value => value + 1)
    } catch (reason) { if (mounted.current) setError((reason as Error).message) }
    finally { if (mounted.current) setBusy(false) }
  }

  if (!enabled) return error ? <small role="alert">{error}</small> : null
  return <section className="shot-details ai-candidate-panel">
    <h3>{t.aiEditTitle}</h3>
    <div className="ai-extend-direction" role="group" aria-label={t.aiEditOperation}>
      <button type="button" aria-pressed={operation === 'extend_before'} disabled={controlsDisabled} onClick={() => setOperation('extend_before')}>{t.aiEditBefore}</button>
      <button type="button" aria-pressed={operation === 'extend_after'} disabled={controlsDisabled} onClick={() => setOperation('extend_after')}>{t.aiEditAfter}</button>
    </div>
    <label>{t.aiEditSeconds}
      <input type="number" aria-label={t.aiEditSeconds} min={0.25} max={10} step={0.25} value={Number.isFinite(seconds) ? seconds : ''} disabled={controlsDisabled} onChange={event => setSeconds(event.target.valueAsNumber)} />
    </label>
    <small>{t.aiEditPromptReuse}</small>
    <button type="button" disabled={controlsDisabled || !take?.active || !prompt.trim() || !Number.isFinite(seconds) || seconds < .25 || seconds > 10} onClick={launch}>{t.aiEditGenerate}</button>
    <details><summary>{t.aiEditDetails}</summary><p>{t.aiEditScope}</p><small>{t.aiEditCost}</small></details>
    {!take?.active && <small>{t.aiEditChoose}</small>}
    {running && pending && <p role="status">{t.aiEditWorking}<button type="button" disabled={busy} onClick={async () => {
      setBusy(true)
      try { onState(await api.cancelJob(job.id)) }
      catch (reason) { if (mounted.current) setError((reason as Error).message) }
      finally { if (mounted.current) setBusy(false) }
    }}>{t.aiEditCancel}</button></p>}
    {error && <p role="alert">{error}</p>}
    {latest?.error && <p role="alert">{latest.error}</p>}
    {ready.map(row => <article key={row.id}>
      <b>{t.aiEditCandidate} · {row.duration?.toFixed(2)} s</b>
      <small>{({ regenerate: t.aiEditRegenerate, extend_before: t.aiEditBefore, extend_after: t.aiEditAfter })[row.operation]} · {row.seed}</small>
      <video src={row.url ?? undefined} controls preload="metadata" playsInline aria-label={t.aiEditCandidate} />
      <button type="button" disabled={controlsDisabled} onClick={() => decide(row.id, 'accept')}>{t.aiEditAccept}</button>
      <button type="button" disabled={controlsDisabled} onClick={() => decide(row.id, 'reject')}>{t.aiEditReject}</button>
    </article>)}
    {candidates.some(row => row.status === 'accepted') && <p role="status">{t.aiEditAccepted}</p>}
  </section>
}
