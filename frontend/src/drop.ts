import type { SlotName } from './components/InputsPanel'
import type { AudioChoice, Inputs, Mode } from './types'

export type Kind = 'video' | 'image' | 'audio'

/** What a file is, from its type or, when the system gives none, its extension. */
export function kindOf(file: { name: string; type: string }): Kind | null {
  const major = file.type.toLowerCase().split('/')[0]
  if (major === 'video' || major === 'image' || major === 'audio') return major
  const ext = file.name.toLowerCase().split('.').pop() ?? ''
  if (['mp4', 'mov', 'webm', 'mkv', 'm4v', 'avi'].includes(ext)) return 'video'
  if (['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'].includes(ext)) return 'image'
  if (['mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac', 'opus'].includes(ext)) return 'audio'
  return null
}

export interface Placed { slot: SlotName; file: File }

/** Where files dropped on the panel go: a video to the source of a Remix then to the reference video, pictures to the free reference slots
 * in order, a sound to the music (Music tab) or to the voice (when the audio is a voice). `first` puts the first picture in a given slot
 * (the one it was dropped on). What has no free slot of its kind comes back in `refused`. A slot already filled is never replaced by a drop
 * on the panel: drop on the slot itself to replace it. */
export function routeFiles(files: File[], at: { mode: Mode; audio: AudioChoice; inputs: Inputs }, first?: number): { placed: Placed[]; refused: File[] } {
  const placed: Placed[] = [], refused: File[] = []
  const freeRefs = at.inputs.refs.map((ref, index) => (ref ? -1 : index)).filter(index => index >= 0 && index !== first)
  if (first !== undefined) freeRefs.unshift(first)
  let video = { source: at.mode === 'remix' && !at.inputs.source, refVideo: !at.inputs.refVideo }
  let audio = { music: at.mode === 'music' && !at.inputs.music, voice: at.mode !== 'music' && at.audio === 'voice' && !at.inputs.voice }
  for (const file of files) {
    const kind = kindOf(file)
    if (kind === 'image' && freeRefs.length) placed.push({ slot: { ref: freeRefs.shift()! }, file })
    else if (kind === 'video' && video.source) { placed.push({ slot: 'source', file }); video = { ...video, source: false } }
    else if (kind === 'video' && video.refVideo) { placed.push({ slot: 'refVideo', file }); video = { ...video, refVideo: false } }
    else if (kind === 'audio' && audio.music) { placed.push({ slot: 'music', file }); audio = { ...audio, music: false } }
    else if (kind === 'audio' && audio.voice) { placed.push({ slot: 'voice', file }); audio = { ...audio, voice: false } }
    else refused.push(file)
  }
  return { placed, refused }
}
