import { BRAND, readPreference, writePreference } from './brand'
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import * as api from './api'
import { Dropdown } from './components/Dropdown'
import { Icon, type IconName } from './components/Icon'
import { canEditAgain, EditStyle } from './components/EditStyle'
import { Examples } from './components/Examples'
import { InputsPanel, type SlotName } from './components/InputsPanel'
import { Library, megabytes } from './components/Library'
import { Preview } from './components/Preview'
import { ShotPanel } from './components/ShotPanel'
import { Timeline } from './components/Timeline'
import { ManualTimeline } from './components/ManualTimeline'
import { Toolbar } from './components/Toolbar'
import { Tooltips } from './components/Tooltips'
import { Toast, type ToastTone } from './components/Toast'
import { DEFAULTS, applySettingsChanges, restoreSettings } from './settings'
import { localizePreset, translatePresetSettings } from './presets'
import { dictionaries, I18n, initialLang, type Lang } from './i18n'
import type { EditStyle as Style, Health, Inputs, JobState, Mode, Preset, Settings, Upload } from './types'

const MODES: Mode[] = ['remix', 'text', 'music']
const ZOOMS = [0.7, 0.8, 0.9, 1, 1.1]

/** The size of the whole interface: the one that was chosen, else the largest that is comfortable for the width of the window. */
function initialZoom(): number {
  const saved = Number(readPreference('zoom'))
  return ZOOMS.includes(saved) ? saved : window.innerWidth >= 1700 ? 1 : window.innerWidth >= 1500 ? 0.9 : window.innerWidth >= 1250 ? 0.8 : 0.7
}
const MODE_ICON: Record<Mode, IconName> = { remix: 'sparkles', text: 'type', music: 'music' }

const EMPTY: Inputs = { source: null, refs: [null, null, null, null, null], refVideo: null, music: null, voice: null }

export default function App() {
  const [lang, setLangState] = useState<Lang>(initialLang)
  useEffect(() => { document.documentElement.lang = lang }, [lang])
  const [mode, setMode] = useState<Mode>('remix')
  const [settings, setSettings] = useState<Settings>(DEFAULTS)
  const [inputs, setInputs] = useState<Inputs>(EMPTY)
  const [job, setJob] = useState<JobState | null>(null)
  const [healthResult, setHealthResult] = useState<{ scope: string; value: Health } | null>(null)
  const healthInputs = useMemo(() => ({ refs: inputs.refs.filter(Boolean).length, ref_video: !!inputs.refVideo, voice: !!inputs.voice }), [inputs])
  const healthScope = `${mode}:${healthInputs.refs}:${healthInputs.ref_video}:${healthInputs.voice}`
  const currentHealthScope = useRef(healthScope)
  currentHealthScope.current = healthScope
  const healthRequest = useRef(0)
  const health = healthResult?.scope === healthScope ? healthResult.value : null
  const refreshHealth = useCallback(async () => {
    const request = ++healthRequest.current
    try {
      const value = await api.health(mode, healthInputs)
      if (request !== healthRequest.current || currentHealthScope.current !== healthScope) return null
      setHealthResult({ scope: healthScope, value })
      return value
    } catch (error) {
      if (request !== healthRequest.current || currentHealthScope.current !== healthScope) return null
      setHealthResult(null)
      throw error
    }
  }, [mode, healthInputs, healthScope])
  const [presetSources, setPresets] = useState<Preset[]>([])
  const [recent, setRecent] = useState<JobState[]>([])
  const [library, setLibrary] = useState(false)
  const [shape, setShape] = useState(9 / 16)
  const [applied, setApplied] = useState<string | null>(null)
  const [zoom, setZoom] = useState(initialZoom)
  const [selection, setSelection] = useState<string[]>([])
  const [primary, setPrimary] = useState(0)
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [bottom, setBottom] = useState<'shots' | 'style' | 'manual'>('shots')
  const [sizes, setSizes] = useState<Record<string, number>>({})
  const [undo, setUndo] = useState<{ label: string; run: () => void } | null>(null)
  const [message, setMessageState] = useState<string | null>(null)
  const [messageTone, setMessageTone] = useState<ToastTone>('success')
  const [dismissedFallback, setDismissedFallback] = useState<string | null>(null)
  const setMessage = (value: string | null, tone: ToastTone = 'success') => { setMessageState(value); setMessageTone(tone) }
  const [actionError, setActionError] = useState<string | null>(null)
  const [restarting, setRestarting] = useState(false)
  const [cancelling,setCancelling] = useState(false)
  const [regenerating,setRegenerating] = useState<{job:string;operation?:number;shots:string[]} | null>(null)
  const [preparing, setPreparing] = useState(false)
  const [uploading, setUploading] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const submission = useRef(false)
  const stopFollowing = useRef<() => void>(() => {})
  const videoRef = useRef<HTMLVideoElement>(null)
  const startedAt = useRef<number | null>(null)
  const [played, setPlayed] = useState({ time: 0, duration: 0 })
  const presets = useMemo(() => presetSources.map(p => localizePreset(p, lang)), [presetSources, lang])
  useEffect(() => {
    const source = presetSources.find(p => p.id === applied)
    if (source) setSettings(current => translatePresetSettings(current, source, lang))
  }, [lang, applied, presetSources])
  const t = dictionaries[lang]
  const i18n = useMemo(() => ({ lang, t, setLang: (next: Lang) => { writePreference('lang', next); setLangState(next) } }), [lang, t])
  const running = restarting || submitting || job?.status === 'queued' || job?.status === 'running'
  const fallbackMessages: Record<string, string> = lang === 'fr' ? {
    'optional:hyperframes:unavailable': 'Vidéo prête sans finition graphique : HyperFrames est indisponible ou a échoué.',
    'optional:tone:missing': 'Banque Tone.js absente : effets sonores de secours utilisés.',
    'optional:tone:unavailable': 'Banque Tone.js inutilisable : effets sonores de secours utilisés.',
    'optional:mask:unavailable': 'Détourage indisponible : vidéo livrée sans la finition graphique qui en dépend.',
    'optional:layout:unavailable': 'Vidéo prête. Le contrôle facultatif de disposition des calques n’a pas pu être effectué.',
    'optional:qc:duration': 'Contrôle export : la durée de la vidéo s’écarte de celle demandée.',
    'optional:qc:ratio': 'Contrôle export : le format de la vidéo diffère du format demandé.',
    'optional:qc:no_audio': 'Contrôle export : la vidéo n’a pas de piste audio.',
    'optional:qc:remix_cuts': 'Contrôle export : le nombre de coupes s’écarte de la vidéo de référence.',
  } : {
    'optional:hyperframes:unavailable': 'Video ready without graphic finishing: HyperFrames is unavailable or failed.',
    'optional:tone:missing': 'Tone.js bank is missing: fallback sound effects were used.',
    'optional:tone:unavailable': 'Tone.js bank is unusable: fallback sound effects were used.',
    'optional:mask:unavailable': 'Subject masking unavailable: video delivered without the dependent graphic finishing.',
    'optional:layout:unavailable': 'Video ready. The optional layer layout check could not be completed.',
    'optional:qc:duration': 'Export check: the video length differs from the requested length.',
    'optional:qc:ratio': 'Export check: the video format differs from the requested format.',
    'optional:qc:no_audio': 'Export check: the video has no audio track.',
    'optional:qc:remix_cuts': 'Export check: the number of cuts differs from the reference video.',
  }
  const fallbackWarnings = [...new Set((job?.warnings ?? []).filter(w => w.startsWith('optional:')))]
  const fallbackKey = `${job?.id}:${job?.operation}:${fallbackWarnings.join('|')}`

  useEffect(() => {
    void refreshHealth().catch(() => {})
    return () => { healthRequest.current += 1 }
  }, [refreshHealth])
  useEffect(() => { api.recentJobs().then(setRecent).catch(() => setRecent([])) }, [job?.status])
  useEffect(() => { api.presets().then(setPresets).catch(() => setPresets([])) }, [])
  useEffect(() => { if (library) api.sizes().then(setSizes).catch(() => setSizes({})) }, [library, recent])
  useEffect(() => {
    if (!undo) return
    const timer = window.setTimeout(() => setUndo(null), 8000)
    return () => window.clearTimeout(timer)
  }, [undo])
  useEffect(() => () => stopFollowing.current(), [])
  useEffect(() => {
    // the layout follows the size the interface has once zoomed: a media query would look at the window, not at that
    const root = document.documentElement
    const apply = () => {
      const width = window.innerWidth / zoom
      root.dataset.w = [width <= 1190 && 'md', width <= 800 && 'sm'].filter(Boolean).join(' ')
      root.dataset.h = window.innerHeight / zoom <= 900 ? 'short' : ''
    }
    root.style.setProperty('--ui-zoom', String(zoom))
    writePreference('zoom', String(zoom))
    apply()
    window.addEventListener('resize', apply)
    return () => window.removeEventListener('resize', apply)
  }, [zoom])
  useEffect(() => { setSelection([]); setPrimary(0); setEdits({}) }, [job?.id])

  const chooseMode = (next: Mode) => {
    setMode(next)
    setSettings(current => ({ ...current, approved_brief: '', approved_brief_context: '', audio: next === 'music' || next === 'remix' ? 'original' : current.audio === 'original' ? 'new' : current.audio }))
  }

  const changeSettings = useCallback((changes: Partial<Settings>) => setSettings(current => applySettingsChanges(current,changes)), [])

  const place = (slot: SlotName, value: Upload | null) => {
    setSettings(current => ({ ...current, approved_brief: '', approved_brief_context: '' }))
    setInputs(current => {
    if (typeof slot === 'object') return { ...current, refs: current.refs.map((ref, i) => (i === slot.ref ? value : ref)) }
    return { ...current, [slot]: value }
    })
  }

  const onUpload = async (slot: SlotName, file: File) => {
    setUploading(n => n + 1)
    try { place(slot, await api.upload(file)) } catch (error) { setActionError((error as Error).message) } finally { setUploading(n => n - 1) }
  }

  const watch = (started: JobState) => {
    setActionError(null)
    setJob(started)
    startedAt.current = Date.now()
    stopFollowing.current()
    stopFollowing.current = api.follow(started.id, state => {
      setJob(state)
      if (state.status === 'cancelled') setMessage(t.cancelled, 'warning')
    }, () => setActionError(t.lost))
  }

  const submit = async (action: () => Promise<JobState>) => {
    if (submission.current) return false
    submission.current = true
    setSubmitting(true)
    setActionError(null)
    setMessage(null)
    try { watch(await action()); return true }
    catch (error) { setActionError((error as Error).message); return false }
    finally { submission.current = false; setSubmitting(false) }
  }

  const generate = async () => {
    if (preparing || running || uploading > 0) return
    if (mode === 'music' && !inputs.music) { setActionError(t.noMusic); return }
    if (settings.audio === 'voice' && (!inputs.voice || !settings.dialogue.trim())) { setActionError(t.stepVoice + ': ' + t.dialogue); return }
    if (mode === 'remix' && !inputs.source) { setActionError(t.needSource); return }
    setMessage(null)
    await submit(() => api.createJob(mode, settings, inputs))
  }

  const regenerateShots = async (ids: string[], withEdits: boolean) => {
    if (!job || ids.length === 0) return
    setMessage(null)
    const changed = ids.filter(id => edits[id] !== undefined && edits[id] !== job.shots.find(s => s.id === id)?.prompt)
    await submit(async () => {
      const next=await api.regenerate(job.id, ids, withEdits ? Object.fromEntries(changed.map(id => [id, edits[id]])) : {})
      setRegenerating({job:next.id,operation:next.operation,shots:ids})
      return next
    })
  }

  const stepShot = useCallback((delta: number) => {
    const count = job?.shots.length ?? 0
    if (count === 0) return
    const next = Math.max(0, Math.min(count - 1, primary + delta))
    setPrimary(next)
    setSelection([job!.shots[next].id])
  }, [job, primary])

  const reEdit = async (style: Style) => {
    if (!job) return
    setMessage(null)
    await submit(() => api.reEdit(job.id, style))
  }

  const chooseTake = async (shot: string, take: string) => {
    if (!job) return
    setMessage(null)
    const chosen = await submit(async () => {
      await api.chooseTake(job.id, shot, take)
      return api.reEdit(job.id, {})
    })
    if (chosen) setMessage(t.takeChosen)
  }

  const trimTake = async (shot: string, take: string, start: number) => {
    if (!job) return
    setMessage(null)
    await submit(async () => {
      await api.trimTake(job.id, shot, take, start)
      return api.reEdit(job.id, {})
    })
  }

  const seek = (seconds: number) => {
    if (job?.manual_export) return
    const video = videoRef.current
    if (video && played.duration > 0) video.currentTime = (seconds * played.duration) / Math.max(job?.shots.reduce((sum, s) => sum + s.duration, 0) ?? 1, 0.001)
  }

  const lock = async (shots: string[], locked: boolean) => {
    if (!job) return
    try {
      let state = job
      for (const shot of shots) state = await api.lockShot(job.id, shot, locked)
      setJob(state)
    } catch (error) { setActionError((error as Error).message) }
  }

  const openRecent = async (id: string) => {
    const opened = recent.find(j => j.id === id)
    if (!opened) return
    setMessage(null)
    try {
      const made = await api.jobInputs(id)
      setMode(made.mode)
      setSettings(restoreSettings(made.settings))
      setInputs({ source: made.source, refs: Array.from({ length: 5 }, (_, i) => made.refs[i] ?? null), refVideo: made.ref_video, music: made.music, voice: made.voice })
      watch(opened)
    } catch (error) { setActionError((error as Error).message) }
  }

  const applyPreset = (id: string) => {
    const preset = presets.find(p => p.id === id)
    if (!preset || running || preparing || uploading > 0) return
    const before = { mode, settings, inputs, job, applied }
    stopFollowing.current()
    setJob(null)
    setActionError(null)
    setInputs({ ...EMPTY, ...preset.inputs, refs: Array.from({ length: 5 }, (_, i) => preset.inputs?.refs?.[i] ?? null) })
    if (preset.missing_inputs?.length) setActionError((lang === 'fr' ? 'Médias du preset manquants : ' : 'Missing preset media: ') + preset.missing_inputs.join(', '))
    chooseMode(preset.mode)
    setSettings(() => ({ ...DEFAULTS, ...preset.settings, prompt: preset.prompt, approved_brief: '', approved_brief_context: '' }))
    setLibrary(false)
    setApplied(preset.id)
    setUndo({ label: `${t.presetApplied}: ${preset.name}`, run: () => { setMode(before.mode); setSettings(before.settings); setInputs(before.inputs); setJob(before.job); setApplied(before.applied) } })
  }

  const refreshJobs = () => api.recentJobs().then(setRecent).catch(() => setRecent([]))
  const fail = (error: unknown) => setActionError((error as Error).message)

  const openFromLibrary = async (id: string) => { setLibrary(false); await openRecent(id) }

  const importProject = (file: File) => {
    void submit(() => api.importProject(file)).then(ok => {
      if (!ok) return
      setLibrary(false)
      setMessage(t.projectImported)
      void refreshJobs()
    })
  }

  const duplicate = async (id: string) => {
    try {
      const made = await api.jobInputs(id)
      stopFollowing.current()
      setJob(null)
      setMode(made.mode)
      setSettings(restoreSettings(made.settings))
      setInputs({ source: made.source, refs: Array.from({ length: 5 }, (_, i) => made.refs[i] ?? null), refVideo: made.ref_video, music: made.music, voice: made.voice })
      setLibrary(false)
      setMessage(t.duplicated)
    } catch (error) { fail(error) }
  }

  const patchJob = async (id: string, patch: { title?: string; pinned?: boolean }) => {
    try {
      const changed = await api.patchJob(id, patch)
      if (job?.id === id) setJob(current => (current ? { ...current, title: changed.title, pinned: changed.pinned } : current))
      await refreshJobs()
    } catch (error) { fail(error) }
  }

  const deleteJob = async (id: string, withFiles: boolean) => {
    try {
      await api.deleteJob(id, withFiles)
      if (job?.id === id) { stopFollowing.current(); setJob(null) }
      await refreshJobs()
      setMessage(t.deleted)
    } catch (error) { fail(error) }
  }

  const freeSpace = async (id: string) => {
    try {
      const { freed } = await api.freeSpace(id)
      setMessage(`${megabytes(freed)} ${t.freed}`)
      setSizes(await api.sizes())
    } catch (error) { fail(error) }
  }

  const savePreset = async (name: string, description: string) => {
    if ((inputs.source || inputs.refs.some(Boolean) || inputs.refVideo || inputs.music || inputs.voice) && !health?.preset_inputs) {
      setActionError(lang === 'fr' ? 'Le serveur du Studio doit être redémarré après les générations en cours pour enregistrer les médias des presets.' : 'Restart the Studio server after active generations finish to save preset media.')
      return
    }

    const { prompt, ...rest } = settings
    try {
      await api.savePreset({ name, description, mode, prompt, settings: rest, inputs })
      setPresets(await api.presets())
      setMessage(t.presetSaved)
    } catch (error) { fail(error) }
  }

  const deletePreset = async (id: string) => {
    try { await api.deletePreset(id); setPresets(await api.presets()) } catch (error) { fail(error) }
  }

  const importPreset = async (file: File) => {
    try {
      const found = JSON.parse(await file.text())
      if (typeof found.name !== 'string' || !MODES.includes(found.mode)) { setActionError(t.presetBad); return }
      if (found.inputs && !health?.preset_inputs) {
        setActionError(lang === 'fr' ? 'Redémarre le serveur du Studio après les générations en cours pour importer les médias du preset.' : 'Restart the Studio server after active generations finish to import preset media.')
        return
      }
      await api.savePreset({ name: found.name, description: found.description ?? '', mode: found.mode, prompt: found.prompt ?? '', settings: found.settings ?? {}, translations: found.translations ?? {}, inputs: found.inputs ?? null })
      setPresets(await api.presets())
      setMessage(t.presetSaved)
    } catch { setActionError(t.presetBad) }
  }

  const cancel = async () => {
    if (!job || cancelling) return
    const id=job.id
    setCancelling(true)
    try {
      const stopped=await api.cancelJob(id)
      setJob(current=>current?.id===id ? stopped : current)
    } catch (error) { setActionError((error as Error).message) }
    finally { setCancelling(false) }
  }

  const resume = async () => {
    if (!job) return
    await submit(() => api.resumeJob(job.id))
  }

  const visibleError = actionError || (job?.status === 'failed' ? job.error || t.failed : null)
  const restartStudio = async () => {
    if (restarting || running || preparing || uploading > 0) return
    setRestarting(true)
    setActionError(null)
    try {
      const accepted = await api.restartStudio()
      stopFollowing.current()
      const deadline = Date.now() + 60000
      while (Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 1000))
        try {
          const response = await fetch('/api/studio/status', { signal: AbortSignal.timeout(3500), cache: 'no-store' })
          if (!response.ok) continue
          const found = await response.json() as Health
          if (!found.instance_id || found.instance_id === accepted.instance_id) continue
          await refreshHealth()
          setPresets(await api.presets())
          await refreshJobs()
          setMessage(lang === 'fr' ? 'Studio redémarré.' : 'Studio restarted.')
          return
        } catch { /* brief disconnect while the process restarts */ }
      }
      throw new Error(lang === 'fr' ? 'Le Studio ne répond pas après le redémarrage. Consulte workspace/logs/studio-err.log.' : 'Studio did not return after restarting. Check workspace/logs/studio-err.log.')
    } catch (error) { setActionError((error as Error).message) }
    finally { setRestarting(false) }
  }

  const featured = presets.filter(p => p.featured !== undefined).sort((a, b) => (a.featured ?? 0) - (b.featured ?? 0)).slice(0, 6)
  const fresh = featured.length > 0 && !job && !inputs.source && !inputs.refVideo && inputs.refs.every(ref => ref === null)  // the first screen, until something is added
  const last = recent.find(j => j.output_url)
  const cover = last ? `/api/jobs/${last.id}/cover?v=${last.output_url?.split('v=')[1] ?? 0}` : null  // the picture behind the Library button: the last result
  const planned = job?.shots.reduce((sum, s) => sum + s.duration, 0) ?? 0
  const activeShots = regenerating?.job===job?.id && regenerating?.operation===job?.operation ? regenerating?.shots ?? [] : []
  const position = job?.output_url && !job.manual_export && played.duration > 0 ? (played.time * planned) / played.duration : null
  const readinessIssues = [...(health?.missing_nodes ?? []), ...(health?.missing_models ?? [])]
  const status = !health ? t.gpuMissing : health.mock ? t.simulated : !health.comfyui || !health.proxy ? t.gpuMissing : !health.videotools || readinessIssues.length > 0 ? t.packMissing : t.gpuOk
  const ok = health !== null && (health.mock || (health.comfyui && health.proxy && health.videotools && health.output_dir !== null && !(health.missing_models?.length)))
  const advice = { remix: t.adviceRemix, text: t.adviceText, music: t.adviceMusic }[mode]
  const tips = { remix: t.tip.modeRemix, text: t.tip.modeText, music: t.tip.modeMusic }
  const label = { remix: t.modeRemix, text: t.modeText, music: t.modeMusic }

  return (
    <I18n.Provider value={i18n}>
      <div className="sc-app">
        <header className="header">
          <div className="brand"><div className="brandmark brandmark-hk" aria-label={BRAND.initials}><img src={BRAND.logo} alt="" /></div><div><div className="brand-name"><strong>{BRAND.name}</strong><span className="beta">BETA</span></div><small>{t.tagline}</small></div></div>
          <nav className="tabs" aria-label="Mode">
            {MODES.map(m => <button key={m} type="button" title={tips[m]} className={`tab ${mode === m ? 'active' : ''}`} onClick={() => chooseMode(m)} disabled={running || preparing}><span className="sym"><Icon name={MODE_ICON[m]} size={17} /></span> {label[m]}</button>)}
          </nav>
          <div className="head-right">
            <button type="button" className="chip" title={t.tip.status} onClick={() => { refreshHealth().then(found => { if (!found) return; const issues = [...(found.load_errors ?? []), ...(!found.proxy ? ['Comfy API proxy unavailable'] : []), ...(!found.output_dir ? ['Set HYPERKUT_OUTPUT_DIR'] : [])]; if (issues.length) setActionError(issues.join(' · ')) }).catch(error => setActionError((error as Error).message)) }}><span className={`dot ${ok ? 'on' : ''}`} /> {status}</button>
            <button type="button" className="chip studio-restart" onClick={restartStudio} disabled={restarting || running || preparing || uploading > 0} aria-busy={restarting} aria-label={lang === 'fr' ? 'Redémarrer le Studio' : 'Restart Studio'} title={lang === 'fr' ? 'Redémarrer uniquement le Studio. Attends la fin des générations.' : 'Restart only the Studio. Wait for generations to finish.'}><Icon name="refresh" size={14} />{restarting ? (lang === 'fr' ? 'Redémarrage…' : 'Restarting…') : 'Restart'}</button>
            <Dropdown label={t.language} title={t.tip.language} icon={<Icon name="globe" size={15} />} value={lang} choices={[{ value: 'en', label: 'English', short: 'EN' }, { value: 'fr', label: 'Français', short: 'FR' }]} onChange={i18n.setLang} />
            <Dropdown label={t.zoomPage} title={t.tip.zoomPage} icon={<Icon name="zoom" size={15} />} value={zoom} choices={ZOOMS.map(z => ({ value: z, label: `${Math.round(z * 100)}%` }))} onChange={setZoom} />
            {job && job.project_id && job.shots.length > 0 && (job.status === 'failed' || job.status === 'cancelled') && <button type="button" className="primary" onClick={resume} disabled={submitting || preparing || uploading > 0}>{t.resume}</button>}
            <button type="button" className="primary stop-generation" title={t.tip.cancel} aria-label={lang==='fr' ? 'Annuler la génération' : 'Cancel generation'} aria-busy={cancelling} disabled={submitting || cancelling || !job || (job.status!=='running' && job.status!=='queued')} onClick={cancel}><Icon name="x" size={18} />{cancelling ? (lang==='fr' ? 'Arrêt…' : 'Stopping…') : 'Stop'}</button>
            <button type="button" className="primary" title={t.tip.generate} onClick={generate} disabled={running || preparing || uploading > 0 || (!!settings.approved_brief && !settings.approved_brief_context)}>{running ? t.generating : `▶ ${t.generate}`}</button>
          </div>
        </header>
        {health && !health.mock && readinessIssues.length > 0 && <section className="error-notice" role="status">
          <div className="error-notice-content"><strong>{lang === 'fr' ? 'Dépendances du mode sélectionné' : 'Selected mode dependencies'} · {label[mode]}</strong><p>{readinessIssues.join(' · ')}</p><small>{lang === 'fr' ? 'Les modes non sélectionnés ne sont pas vérifiés. La génération vérifie son graphe réel avant envoi.' : 'Other modes are not checked. Generation validates its actual graph before submission.'}</small></div>
        </section>}
        {visibleError && <section className="error-notice" role="alert" aria-live="assertive" aria-atomic="true">
          <span className="error-notice-mark" aria-hidden="true">!</span>
          <div className="error-notice-content"><strong>{job?.status === 'failed' && !actionError ? (lang === 'fr' ? 'La génération a échoué' : 'Generation failed') : (lang === 'fr' ? 'Action impossible' : 'Action failed')}</strong><p>{visibleError}</p><small>{lang === 'fr' ? 'Consulte le message avant de réessayer.' : 'Review the message before trying again.'}</small></div>
          {actionError && <button type="button" aria-label={lang === 'fr' ? 'Fermer le message d’erreur' : 'Dismiss error message'} onClick={() => setActionError(null)}><Icon name="x" size={18} /></button>}
        </section>}
        {job && <div className="progress" role="progressbar" aria-valuenow={Math.round(job.progress * 100)}><div style={{ width: `${job.progress * 100}%` }} /></div>}
        <div className="main">
          <button type="button" className="library-toggle" aria-pressed={library} title={t.tip.library} style={cover ? { backgroundImage: `url(${cover})` } : undefined} onClick={() => setLibrary(value => !value)}>
            <b><Icon name="layers" size={22} /> {t.library}</b>
            <small>{recent.length} {t.projects.toLowerCase()} · {presets.length} {t.presets.toLowerCase()}</small>
            <span className="lib-chevron" aria-hidden><Icon name={library ? 'x' : 'chevron-right'} size={18} /></span>
          </button>
          <Toolbar mode={mode} settings={settings} busy={running || preparing} hasReferences={inputs.refs.some(Boolean) || !!inputs.refVideo} onSettings={changeSettings} />
          <div className="left">
          <InputsPanel mode={mode} inputs={inputs} settings={settings} busy={running || preparing} onPreparing={setPreparing} onUpload={onUpload} onClear={slot => place(slot, null)} onSettings={changeSettings} />
          <Library open={library} onClose={() => setLibrary(false)} jobs={recent} sizes={sizes} presets={presets} mode={mode} currentJob={job?.id ?? null} onOpenJob={openFromLibrary} onDuplicateJob={duplicate} onPatchJob={patchJob}
            onDeleteJob={deleteJob} onFree={freeSpace} onApplyPreset={applyPreset} onSavePreset={savePreset} onDeletePreset={deletePreset} onImportPreset={importPreset} onImportProject={importProject} />
          </div>
          <main className="workarea">
            <p className="mode-advice">{advice}</p>
            <div className="stage-box">
              {fresh ? <Examples presets={featured} applied={applied} onApply={applyPreset} /> : (
                <div className="stage-area" style={{ '--r': shape } as CSSProperties}>
                  <Preview mode={mode} ratio={settings.ratio} inputs={inputs} job={job} videoRef={videoRef} startedAt={startedAt.current} onTime={(time, duration) => setPlayed({ time, duration })} onShape={setShape} activeShots={activeShots} />
                  <ShotPanel job={job} primary={primary} selection={selection} edits={edits} quality={settings.quality} onEdit={(id, text) => setEdits(current => ({ ...current, [id]: text }))}
                    onStep={stepShot} onRegenerate={regenerateShots} onLock={lock} onChooseTake={chooseTake} onTrimTake={trimTake} onAIState={watch} activeShots={activeShots} />
                </div>
              )}
            </div>
            <div className="bottom">
              <div className="bottom-tabs" role="tablist">
                <button type="button" role="tab" aria-selected={bottom === 'shots'} className={bottom === 'shots' ? 'on' : ''} onClick={() => setBottom('shots')}><Icon name="film" size={14} /> {t.shotsTab}</button>
                <button type="button" role="tab" aria-selected={bottom === 'style' && canEditAgain(job)} className={bottom === 'style' ? 'on' : ''} disabled={!canEditAgain(job)} title={t.tip.editStyle} onClick={() => setBottom('style')}><Icon name="scissors" size={14} /> {t.editStyle}</button>
                <button type="button" role="tab" aria-selected={bottom === 'manual'} className={bottom === 'manual' ? 'on' : ''} disabled={!job?.project_id} onClick={() => setBottom('manual')}><Icon name="scissors" size={14} /> {t.manualTitle}</button>
              </div>
              {bottom === 'manual' && job?.project_id ? <ManualTimeline key={job.id} job={job} onState={watch} /> : bottom === 'style' && canEditAgain(job)
                ? <EditStyle key={job?.id} job={job} onApply={style => { setBottom('shots'); reEdit(style) }} />
                : <Timeline job={job} position={position} onSeek={seek} selection={selection} primary={primary} edits={edits} onSelect={(chosen, main) => { setSelection(chosen); setPrimary(main) }} onRegenerate={ids => regenerateShots(ids, true)} onLock={lock} activeShots={activeShots} />}
            </div>
          </main>
        </div>
        <Tooltips />
        <div className="toast-stack" aria-label={lang === 'fr' ? 'Notifications du Studio' : 'Studio notifications'}>
          {job?.status === 'succeeded' && fallbackWarnings.length > 0 && dismissedFallback !== fallbackKey && <Toast tone="warning" lang={lang} onDismiss={() => setDismissedFallback(fallbackKey)}>{fallbackWarnings.map(w => fallbackMessages[w] ?? (lang === 'fr' ? 'Vidéo prête avec une finition facultative désactivée.' : 'Video ready with optional finishing skipped.')).join(' ')}</Toast>}
          {undo && <Toast tone="info" lang={lang} action={{ label: t.undo, run: () => { undo.run(); setUndo(null) } }} onDismiss={() => setUndo(null)}>{undo.label}</Toast>}
          {(message || uploading > 0) && <Toast tone={uploading > 0 ? 'info' : messageTone} lang={lang} busy={uploading > 0} onDismiss={uploading > 0 ? undefined : () => setMessage(null)}>{uploading > 0 ? t.uploading : message}</Toast>}
        </div>
      </div>
    </I18n.Provider>
  )
}
