import { useEffect, useState } from 'react'
import type { RefObject } from 'react'
import { useI18n } from '../i18n'
import { Icon } from './Icon'

interface Props {
  video: RefObject<HTMLVideoElement | null>
  container: RefObject<HTMLElement | null>
  mediaKey: string | null
  shape: string
}

const clock = (value: number) => {
  const ticks = Math.floor(Math.max(0, value) * 100 + 1e-6)
  return `${String(Math.floor(ticks / 6000)).padStart(2,'0')}:${String(Math.floor(ticks / 100) % 60).padStart(2,'0')}.${String(ticks % 100).padStart(2,'0')}`
}

// Media properties are imperative DOM state, separate from React component data.
function seekPlayer(video: RefObject<HTMLVideoElement | null>, time: number) {
  const element=video.current
  if (element) element.currentTime=time
}
function setPlayerVolume(video: RefObject<HTMLVideoElement | null>, value: number) {
  const element=video.current
  if (element) { element.volume=value; element.muted=value===0 }
}
function mutePlayer(video: RefObject<HTMLVideoElement | null>) {
  const element=video.current
  if (element) element.muted=!element.muted
}
function loopPlayer(video: RefObject<HTMLVideoElement | null>) {
  const element=video.current
  if (!element) return false
  element.loop=!element.loop
  return element.loop
}

export function PlayerControls({ video, container, mediaKey, shape }: Props) {
  const { lang } = useI18n()
  const fr = lang === 'fr'
  const [media, setMedia] = useState({key:mediaKey,time:0,duration:0,playing:false,volume:1,muted:false,loop:false})
  const [full, setFull] = useState(false)
  const [error, setError] = useState('')
  const state = media.key === mediaKey ? media : {time:0,duration:0,playing:false,volume:1,muted:false,loop:false}
  const available = !!mediaKey && state.duration > 0

  useEffect(() => {
    const element = video.current
    if (!element) return
    const sync = () => setMedia({key:mediaKey,time:Number.isFinite(element.currentTime) ? element.currentTime : 0,
      duration:Number.isFinite(element.duration) ? element.duration : 0,playing:!element.paused && !element.ended,volume:element.volume,muted:element.muted,loop:element.loop})
    const events = ['loadedmetadata','durationchange','timeupdate','play','pause','ended','volumechange','emptied']
    for (const name of events) element.addEventListener(name,sync)
    if (element.readyState) sync()
    return () => { for (const name of events) element.removeEventListener(name,sync) }
  },[video,mediaKey])

  useEffect(() => {
    const sync = () => setFull(document.fullscreenElement === container.current)
    document.addEventListener('fullscreenchange',sync)
    return () => document.removeEventListener('fullscreenchange',sync)
  },[container])

  const toggle = async () => {
    const element = video.current
    if (!element) return
    setError('')
    if (element.paused || element.ended) {
      try { await element.play() } catch { setError(fr ? 'Lecture indisponible.' : 'Playback unavailable.') }
    } else element.pause()
  }

  return <div className="player-transport">
    <button type="button" className="transport-play" disabled={!available} aria-label={state.playing ? 'Pause' : (fr ? 'Lire' : 'Play')} onClick={toggle}><Icon name={state.playing ? 'pause' : 'play'} size={19} /></button>
    <button type="button" disabled={!available} aria-label={fr ? 'Lecture en boucle' : 'Loop playback'} aria-pressed={state.loop} title={state.loop ? (fr ? 'Désactiver la boucle' : 'Disable loop') : (fr ? 'Activer la boucle' : 'Enable loop')} onClick={() => { const loop=loopPlayer(video);setMedia(current=>({...current,loop})) }}><Icon name="repeat" size={17} /></button>
    <div className="transport-time"><span>{clock(state.time)}</span><small>/ {clock(state.duration)}</small></div>
    <input className="transport-seek" type="range" min={0} max={state.duration || 1} step={.01} value={Math.min(state.time,state.duration)} disabled={!available} aria-label={fr ? 'Position de lecture' : 'Playback position'} onChange={event => seekPlayer(video,Number(event.target.value))} />
    <span className="transport-shape">{shape}</span>
    <button type="button" disabled={!mediaKey} aria-label={state.muted ? (fr ? 'Activer le son' : 'Unmute') : (fr ? 'Couper le son' : 'Mute')} onClick={() => mutePlayer(video)}><Icon name={state.muted ? 'volume-off' : 'volume'} size={17} /></button>
    <input className="transport-volume" type="range" min={0} max={1} step={.05} value={state.muted ? 0 : state.volume} disabled={!mediaKey} aria-label="Volume" onChange={event => setPlayerVolume(video,Number(event.target.value))} />
    <button type="button" disabled={!document.fullscreenEnabled} aria-label={full ? (fr ? 'Quitter le plein écran' : 'Exit fullscreen') : (fr ? 'Plein écran' : 'Fullscreen')} onClick={async () => {
      try { if (full) await document.exitFullscreen(); else await container.current?.requestFullscreen() }
      catch { setError(fr ? 'Plein écran indisponible.' : 'Fullscreen unavailable.') }
    }}><Icon name="fullscreen" size={17} /></button>
    {error && <span className="transport-error" role="status">{error}</span>}
  </div>
}
