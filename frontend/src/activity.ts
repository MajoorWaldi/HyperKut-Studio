import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'
import type { JobState } from './types'

export function workingShots(job: JobState | null, requested: string[] = []): string[] {
  if (job?.status !== 'running' || job.stage !== 'shots') return []
  if (requested.length) return requested.filter(id=>job.shots.some(shot=>shot.id===id))
  const shot=job.shots.find(shot=>!shot.done)
  return shot ? [shot.id] : []
}

/** Only flash for a completion observed here, never when opening an old result. */
export function useCompletionFlash(element: RefObject<HTMLElement | null>, job: JobState | null) {
  const previous=useRef<{key:string;busy:boolean} | null>(null)
  const id=job?.id, operation=job?.operation, status=job?.status
  useEffect(()=>{
    const key=`${id}:${operation ?? 0}`
    const before=previous.current
    const busy=status==='running' || status==='queued'
    previous.current={key,busy}
    if (status!=='succeeded' || !before?.busy || before.key!==key || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    const animation=element.current?.animate?.([
      {boxShadow:'0 0 0 1px #c6de9ab3, 0 0 15px #c6de9a33'},
      {boxShadow:'0 0 0 1px #c6de9a00, 0 0 0 #c6de9a00'},
    ],{duration:800,easing:'ease-out'})
    return ()=>animation?.cancel()
  },[element,id,operation,status])
}
