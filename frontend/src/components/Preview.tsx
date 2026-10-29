import { BRAND } from '../brand'
import { useEffect, useRef, useState, type CSSProperties, type RefObject, type SyntheticEvent } from 'react'
import { useI18n } from '../i18n'
import { Icon } from './Icon'
import { PlayerControls } from './PlayerControls'
import { useCompletionFlash, workingShots } from '../activity'
import type { Inputs, JobState, Mode, Ratio } from '../types'

interface Props {
  mode: Mode
  ratio: Ratio
  inputs: Inputs
  job: JobState | null
  videoRef: RefObject<HTMLVideoElement | null>
  onTime: (time: number, duration: number) => void
  /** The shape of the picture (width over height): the page gives the room that the player does not need to the panel next to it. */
  onShape: (ratio: number) => void
  startedAt: number | null
  activeShots?: string[]
}

const STAGES = ['analyze', 'shots', 'edit', 'done'] as const
const KNOWN: [number, string][] = [[9 / 16, '9:16'], [16 / 9, '16:9'], [1, '1:1'], [3 / 4, '3:4'], [4 / 3, '4:3'], [4 / 5, '4:5'], [21 / 9, '21:9']]

const asNumber = (ratio: Ratio) => { const [w, h] = ratio.split(':').map(Number); return w / h }
/** The name of a shape: 9:16 and the like when it is close to one, else the number. */
export const shapeName = (ratio: number) => KNOWN.find(([value]) => Math.abs(value / ratio - 1) < 0.03)?.[1] ?? ratio.toFixed(2)

/** What is being made: the stage, the shots as they come, and the time that is left (the proxy sends no preview picture, so this is what there is to see). */
function ProgressCard({ job, startedAt, activeShots=[] }: { job: JobState; startedAt: number | null; activeShots?: string[] }) {
  const { t, lang } = useI18n()
  const fr = lang === 'fr'
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer) }, [])
  const elapsed = startedAt ? Math.max(0, (now - startedAt) / 1000) : 0
  const progress = Number.isFinite(job.progress) ? Math.max(0, Math.min(1, job.progress)) : 0
  const left = elapsed > 0 && progress > 0.08 && progress < 1 ? (elapsed * (1 - progress)) / progress : null
  const working=workingShots(job,activeShots)
  const active = working.length===1 ? job.shots.findIndex(shot=>shot.id===working[0]) : -1
  const done = job.shots.filter(shot => shot.done).length
  const position = active >= 0 ? active + 1 : done
  const title = job.status === 'queued' ? (fr ? 'En attente' : 'Waiting') : job.stage==='shots' && activeShots.length ? (fr ? 'Régénération des plans' : 'Regenerating shots') : [fr ? 'Préparation' : 'Preparing', fr ? 'Création des plans' : 'Creating shots', fr ? 'Montage et effets' : 'Editing and effects', fr ? 'Terminé' : 'Done'][Math.max(STAGES.indexOf(job.stage), 0)]
  const eta = left === null ? '' : left < 60 ? (fr ? 'Encore moins d’une minute' : 'Less than a minute left') : `${fr ? 'Encore environ' : 'About'} ${Math.round(left / 30) * 0.5} min${fr ? '' : ' left'}`
  return (
    <div className="progress-card" role="status" aria-live="polite" title={t.tip.progressCard}>
      <b>{title}</b>
      {job.stage==='shots' && job.status==='running' && active>=0 && <span>{t.shot} {position} {fr ? 'sur' : 'of'} {job.shots.length}</span>}
      {job.stage==='shots' && working.length>1 && <span>{working.length} {fr ? 'plans concernés' : 'affected shots'}</span>}
      {job.shots.length > 0 && (
        <div className="progress-shots" aria-hidden="true">{job.shots.map(shot => <span key={shot.id} className={working.includes(shot.id) ? 'active' : shot.done ? 'done' : 'pending'}>{shot.thumb && shot.done ? <img key={`${shot.thumb}-${shot.takes}`} src={`${shot.thumb}${shot.thumb.includes('?') ? '&' : '?'}v=${shot.takes}`} alt="" onLoad={event => event.currentTarget.classList.add('ready')} /> : null}</span>)}</div>
      )}
      <div className="progress-card-track" role="progressbar" aria-label={title} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}>
        <div style={{ width: `${progress * 100}%` }} />
      </div>
      <small>{Math.round(progress * 100)} %{eta ? ` · ${eta}` : ''}</small>
    </div>
  )
}

/** The player: the result of the job when there is one, else the source video, else the first reference picture. Its frame has the shape of the picture, whatever it is, over a blurred copy of it. */
export function Preview({ mode, ratio, inputs, job, videoRef, onTime, onShape, startedAt, activeShots=[] }: Props) {
  const { t } = useI18n()
  const sourceRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLElement>(null)
  const [compare, setCompare] = useState(false)
  const [size, setSize] = useState<{ url: string; width: number; height: number } | null>(null)
  const result = job?.output_url ?? null
  const running = job?.status === 'queued' || job?.status === 'running'
  useCompletionFlash(containerRef,job)
  const live = job && job.status === 'running' && job.preview > 0 ? `/api/jobs/${job.id}/preview?n=${job.preview}` : null
  const original = mode === 'remix' ? inputs.source?.url ?? null : null
  const canCompare = result !== null && original !== null && !running && !job?.manual_export
  const showCompare = compare && canCompare
  const video = result ?? (mode === 'remix' ? inputs.source?.url : inputs.refVideo?.url) ?? null
  const picture = inputs.refs.find(ref => ref !== null)?.url ?? null
  const backdrop = result && job ? `/api/jobs/${job.id}/cover?v=${result.split('v=')[1] ?? 0}` : picture

  // the shape of what is shown: the real one once the video says it, else what was asked for (a remix has no choice: it is the shape of its source)
  const known = video && size?.url === video ? size.width / size.height : null
  const shape = known ?? (mode === 'remix' ? 16 / 9 : asNumber(ratio))
  const frame = showCompare ? shape * 2 : shape
  useEffect(() => { onShape(frame) }, [frame]) // eslint-disable-line react-hooks/exhaustive-deps

  // the source follows the result: same moment, same state
  const mirror = (action: (source: HTMLVideoElement, main: HTMLVideoElement) => void) => (event: SyntheticEvent<HTMLVideoElement>) => { if (sourceRef.current) action(sourceRef.current, event.currentTarget) }
  const sync = {
    onPlay: mirror(source => { void source.play().catch(() => undefined) }),
    onPause: mirror(source => source.pause()),
    onSeeked: mirror((source, main) => { source.currentTime = main.currentTime }),
    onRateChange: mirror((source, main) => { source.playbackRate = main.playbackRate }),
    onTimeUpdate: mirror((source, main) => { if (Math.abs(source.currentTime - main.currentTime) > 0.3) source.currentTime = main.currentTime }),
  }
  const main = (event: SyntheticEvent<HTMLVideoElement>) => onTime(event.currentTarget.currentTime, event.currentTarget.duration)
  const loaded = (event: SyntheticEvent<HTMLVideoElement>) => {
    const { videoWidth, videoHeight, currentSrc } = event.currentTarget
    if (videoWidth && videoHeight) setSize({ url: video ?? currentSrc, width: videoWidth, height: videoHeight })
    main(event)
  }

  return (
    <section className={`preview ${running ? 'is-busy' : ''}`} ref={containerRef} aria-busy={running}>
      <div className="player-toolbar">
        <div className="player-caption"><span className="preview-badge lime">{result ? job?.manual_export ? t.manualTitle : t.result : mode.toUpperCase()}</span><span title={job?.title || t.previewEmpty}>{job?.title || t.previewEmpty}</span></div>
        {(canCompare || (result && !running)) && <div className="player-actions">
          {canCompare && <button type="button" className={showCompare ? 'on' : ''} aria-pressed={showCompare} aria-label={t.compare} title={t.tip.compare} onClick={() => setCompare(value => !value)}><Icon name="columns" size={17} /></button>}
          {result && !running && job && <><a href={result} download={`${BRAND.exportPrefix}_${job.id}.mp4`} aria-label={t.download} title={t.tip.download}><Icon name="download" size={17} /></a><a href={`/api/jobs/${job.id}/export`} download aria-label={t.exportProject} title={t.tip.exportProject}><Icon name="package" size={17} /></a></>}
        </div>}
      </div>
      <div title={t.tip.preview} className="player-art">
        {backdrop && !showCompare && <img className="backdrop" src={backdrop} alt="" aria-hidden />}
        <div className={`player-frame ${showCompare ? 'compare' : ''} ${video || picture ? '' : 'empty'}`} style={{ '--r': frame } as CSSProperties}>
          {live ? <img src={live} alt={t.livePreview} className="live" /> : video ? (
            <>
              {showCompare && <video ref={sourceRef} src={original ?? undefined} muted playsInline aria-label={t.source} />}
              <video ref={videoRef} key={video} src={video} playsInline onTimeUpdate={event => { main(event); sync.onTimeUpdate(event) }} onSeeked={event => { main(event); if (showCompare) sync.onSeeked(event) }}
                onPlay={showCompare ? sync.onPlay : undefined} onPause={showCompare ? sync.onPause : undefined} onRateChange={showCompare ? sync.onRateChange : undefined} onLoadedMetadata={loaded} />
            </>
          ) : picture ? <img src={picture} alt="" className="cover" /> : (
            <div className="empty-state"><Icon name="film" size={36} /><b>{t.previewEmpty}</b><small>{t.previewEmptyHint}</small></div>
          )}
          <div className="preview-top">
            {showCompare && <><span className="preview-badge">{t.source}</span><span className="preview-badge lime">{t.result}</span></>}
            {running && job && <span className="preview-badge">{Math.round(job.progress * 100)}%</span>}
          </div>
        </div>
        {running && job && <ProgressCard job={job} startedAt={startedAt} activeShots={activeShots} />}
      </div>
      <PlayerControls key={video} video={videoRef} container={containerRef} mediaKey={live ? null : video} shape={shapeName(shape)} />
    </section>
  )
}
