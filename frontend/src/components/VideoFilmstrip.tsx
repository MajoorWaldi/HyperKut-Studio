import { useEffect, useState } from 'react'

/** Decode a bounded set of real source frames, independently of the preview player. */
export function VideoFilmstrip({ url, duration }: { url: string; duration: number }) {
  const [frames,setFrames] = useState<{url:string;images:string[]}>({url:'',images:[]})
  useEffect(() => {
    const video=document.createElement('video')
    if (!video.canPlayType('video/mp4')) return
    video.muted=true; video.preload='auto'; video.playsInline=true
    const canvas=document.createElement('canvas');canvas.width=120;canvas.height=72
    const context=canvas.getContext('2d')
    if (!context || !(duration>0)) return
    let stopped=false
    const images:string[]=[]
    const times=Array.from({length:6},(_,i)=>Math.min(Math.max(0,duration-.05),duration*(i+.5)/6))
    const seek=()=> { if (!stopped) video.currentTime=times[images.length] }
    const capture=()=> {
      if (stopped || !video.videoWidth || !video.videoHeight) return
      const scale=Math.max(canvas.width/video.videoWidth,canvas.height/video.videoHeight)
      try {
        context.drawImage(video,(canvas.width-video.videoWidth*scale)/2,(canvas.height-video.videoHeight*scale)/2,video.videoWidth*scale,video.videoHeight*scale)
        images.push(canvas.toDataURL('image/jpeg',.65))
      } catch { stop(); return }
      if (images.length===times.length) { setFrames({url,images});stop() }
      else seek()
    }
    const stop=()=> { stopped=true;clearTimeout(timer);video.removeEventListener('loadedmetadata',seek);video.removeEventListener('seeked',capture);video.removeEventListener('error',stop);video.removeAttribute('src');video.load() }
    const timer=window.setTimeout(stop,12000)
    video.addEventListener('loadedmetadata',seek)
    video.addEventListener('seeked',capture)
    video.addEventListener('error',stop)
    video.src=url
    return stop
  },[url,duration])
  return <div className="video-filmstrip" aria-hidden="true">{frames.url===url && frames.images.map((src,index)=><img src={src} key={index} alt="" />)}</div>
}
