export type Mode = 'remix' | 'text' | 'music'
export type Stage = 'analyze' | 'shots' | 'edit' | 'done'
export type Status = 'queued' | 'running' | 'review' | 'succeeded' | 'failed' | 'cancelled'
export type Ratio = '9:16' | '16:9' | '1:1' | '3:4'
export type Quality = 'draft' | 'standard' | 'max' | 'xhigh'
export type AudioChoice = 'original' | 'new' | 'voice'

export interface Upload { id: string; name: string; kind: 'video' | 'image' | 'audio'; url: string }

export interface Settings {
  prompt: string
  art_direction?: Record<string, string>
  approved_brief?: string
  approved_brief_context?: string
  duration: number
  ratio: Ratio
  quality: Quality
  structure: number
  remix_strategy: '' | 'preserve' | 'creative' | 'transfer'
  creativity: number
  seed: number | null  // null: a random one for every generation
  idea_seed: number  // which idea the text models write: 0 is the first, another number is another idea for the same request
  audio: AudioChoice
  mood: string
  bpm: number
  effects: boolean
  text: boolean
  sound_design: boolean
  sub_cuts?: boolean
  sound_effects: boolean
  music_sync: boolean
  retry_bad_takes: boolean
  flex: boolean
  best_of_two: boolean
  kinetic_lyrics: boolean
  dialogue: string
  places: boolean
  casting: boolean
  camera: string
  music_volume?: number
  motion_design?: boolean
  motion_direction?: string
  motion_title?: string
  motion_cues?: string
  motion_layers: string
  subject_mask: boolean
  redraw_text: boolean
  pose_only: boolean
  quality_check: boolean
  review_plan: boolean
  video_model: string  // 'minimax_h3' runs here; an API model of the generators folder of the pack is paid per take (Text and Music)
  api_resolution: '480p' | '720p' | '1080p'
  api_budget_seconds: number  // the most seconds of video one run may ask from an API model, retries included; 0: no limit
  api_budget_usd: number  // the same in dollars (the price badges of the API nodes); 0: no limit
  music_energy?: 'peak' | 'calm' | 'balanced' | 'intense'
  music_start: number
  style: string
  cut_density: 'auto' | 'low' | 'medium' | 'high'
  transition_intensity: 'auto' | 'subtle' | 'moderate' | 'bold'
  cut_every: 'half_beat' | 'beat' | '2_beats' | 'bar' | '2_bars' | '4_bars'
  music_edit_mode: 'legacy' | 'adaptive' | 'random' | 'regular' | 'free' | 'phrases' | 'hits'
  music_cut_variation: number
  music_cut_sync: number
  text_allowed: string
  efficient_sources?: boolean
  reference_style?: 'camera'|'montage'
  sfx_library?: string
}

export interface EditStyle { rendered_layers?: string; motion_cues?: string; motion_design?: boolean; motion_direction?: string; motion_title?: string; effects?: boolean; text?: boolean; sub_cuts?: boolean; auto_sfx?: boolean; shot_volume?: number; duck?: number; music_volume?: number; motion_layers?: string }

export interface Shot { id: string; start: number; duration: number; prompt: string; generation_prompt?: string; version: number; locked: boolean; thumb: string | null; done: boolean; takes: number; generation_frames?: number; render_source?:string }

export interface JobState {
  id: string
  mode: Mode
  status: Status
  stage: Stage
  progress: number
  node: string | null
  step: number | null
  steps: number | null
  shots: Shot[]
  output_url: string | null
  error: string | null
  project_id: string | null
  style: EditStyle
  preview: number
  title: string
  created_at: number
  pinned: boolean
  operation?: number
  generation_budget?: { seconds: number; with_retries: number; final_seconds: number }
  api_cost?: ApiCost | null
  energy?: EnergyReport | null
  warnings?: string[]
  manual_export?: { duration: number; clips: number; etag: string } | null
}

export interface ApiCost { generator: string; title: string; seconds: number; usd_low: number | null; usd_high: number | null; budget_seconds: number; budget_usd: number; over_budget: boolean; stops_at: number | null; text: string; approved: boolean }
export interface VideoModel { id: string; title: string; source: 'local' | 'api' }
/** A model with what an edit of the length asked costs with it: seconds the API is asked for and dollars, null when it runs here or the price is not known. */
export interface VideoEstimate extends VideoModel { seconds: number | null; seconds_high?: number | null; usd_low: number | null; usd_high: number | null; text: string }

export interface EnergyReport { status: string; reference: Record<string,number> | null; result: Record<string,number> | null; ratios: Record<string,number|null>; audio?: {true_peak_dbtp?: number|null;within_ceiling?: boolean;silent?: boolean;status?:string} }
export interface ReviewReport { frames: {seconds:number;url:string}[]; energy?: EnergyReport | null; warnings?:string[]; checks:Record<string,string> }

export interface JobInputs { mode: Mode; settings: Settings; source: Upload | null; refs: Upload[]; ref_video: Upload | null; music: Upload | null; voice: Upload | null; place?: Upload | null }

export interface Take { id: string; active: boolean; url: string; thumb?: string | null; generation_prompt?: string; duration?: number; start?: number; window?: number; max_start?: number; step?: number }

export interface TimelineClip { id: string; shot_id: string; revision_id: string; in_frame: number; out_frame: number }
export interface TimelineDocument {
  version: 1
  project_id: string
  source_signature: string
  fps_num: number
  fps_den: number
  clips: TimelineClip[]
  dialogue?: (TimelineClip & { at_frame: number; gain?: number })[]
  music_gain?: number
}
export interface ManualTimelinePayload {
  library: { id: string; takes: { id: string; file: string; offset: number; frames: number; prompt: string; audio?: { file: string; duration: number; peaks: number[]; frames?: number } | null }[] }[]
  initial: TimelineDocument
  document: TimelineDocument
  music: { file: string; duration: number; peaks: number[]; source_audio?: boolean } | null
  etag: string | null
  enabled: boolean
  stale: boolean
}
export interface TimelineEditorModule {
  openTimelineEditor: (payload: ManualTimelinePayload, document: TimelineDocument, options: {
    urlFor: (file: string) => string
    onChange: (document: TimelineDocument) => void
    onClose: () => void
    onSave: (document: TimelineDocument) => Promise<void>
    onRender: (document: TimelineDocument) => Promise<void>
    labels: Record<string, string>
    theme?: 'studio'
  }) => () => void
}

export type AIOperation = 'regenerate' | 'extend_before' | 'extend_after'
export interface AICandidate {
  id: string
  shot_id: string
  operation: AIOperation
  status: 'queued' | 'running' | 'ready' | 'failed' | 'cancelled' | 'accepted' | 'rejected'
  take: string
  prompt: string
  seed: number
  duration: number | null
  generated_seconds: number
  error: string | null
  revision_id: string | null
  url: string | null
}

export interface TimelineInfo { bpm: number | null; beat_times?: number[]; shots: { id: string; cuts: number[]; effects: string[]; text?: string }[] }

export interface Health { mode?: Mode; instance_id?: string; preset_inputs?: boolean; music_rhythm_modes?: boolean; adaptive_editing_modes?: boolean; mock: boolean; comfyui: boolean; proxy: boolean; videotools: boolean; output_dir: string | null; missing_nodes?: string[]; missing_models?: string[]; load_errors?: string[] }

export interface Inputs { source: Upload | null; refs: (Upload | null)[]; refVideo: Upload | null; music: Upload | null; voice: Upload | null; place?: Upload | null }  // place: a picture of the place, used instead of the generated places

export interface PresetTranslation { name: string; description: string; prompt: string; settings?: Partial<Settings> }
export interface Preset { inputs?: Inputs | null; missing_inputs?: string[]; translations?: Partial<Record<'en' | 'fr', PresetTranslation>>; id: string; name: string; mode: Mode; description: string; prompt: string; settings?: Partial<Settings>; user?: boolean; preview?: string; reference?: string; featured?: number }

export interface DirectionField { key: string; fr: string; en: string; choices: { value: string; fr: string; en: string }[] }
export interface PreparedBrief { brief: string; context: string }
