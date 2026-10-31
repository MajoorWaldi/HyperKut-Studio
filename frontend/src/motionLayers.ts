/** Reads and edits the motion layers JSON of the settings; the JSON stays the only source of truth. */
export type MotionRow = Record<string, unknown> & { start?: unknown; end?: unknown; template?: string }

export type Category = 'text' | 'hud' | 'hits' | 'layout' | 'subject' | 'fx'

export const CATEGORIES: { id: Category; en: string; fr: string }[] = [
  { id: 'text', en: 'Text', fr: 'Texte' },
  { id: 'hud', en: 'Frames & HUD', fr: 'Cadres & HUD' },
  { id: 'hits', en: 'Hits & transitions', fr: 'Impacts & transitions' },
  { id: 'layout', en: 'Layouts', fr: 'Mises en page' },
  { id: 'subject', en: 'Subject (needs the mask)', fr: 'Sujet (demande le masque)' },
  { id: 'fx', en: 'Particles & stickers', fr: 'Particules & stickers' },
]

interface Template { defaults: MotionRow; category: Category; en: string; fr: string }

/** What each template of VideoTools (core/motion_library.py) is called, where it sits and the layer a click adds. `end` is absent for a hit that lasts a fraction of a second. */
export const TEMPLATES: Record<string, Template> = {
  end_card: { category: 'text', defaults: { title: 'TITLE', start: 0, end: 2 }, en: 'A big title with an optional credit line', fr: 'Un grand titre avec une ligne de crédit' },
  punch_word: { category: 'text', defaults: { word: 'WORD', start: 0, end: 1 }, en: 'One big word that pops in', fr: 'Un gros mot qui claque' },
  caption_mono: { category: 'text', defaults: { content: 'caption', start: 0, end: 2 }, en: 'A small typed caption', fr: 'Une petite légende tapée' },
  rec_hud: { category: 'hud', defaults: { label: 'REC', start: 0, end: 4 }, en: 'Viewfinder corners and a red REC mark', fr: 'Coins de viseur et pastille REC rouge' },
  letterbox: { category: 'hud', defaults: { start: 0, end: 4 }, en: 'Black cinema bars top and bottom', fr: 'Bandes noires de cinéma, haut et bas' },
  polaroid_frame: { category: 'hud', defaults: { start: 0, end: 4 }, en: 'A white photo frame around the picture', fr: 'Un cadre photo blanc autour de l’image' },
  flash_hit: { category: 'hits', defaults: { start: 0 }, en: 'A white flash that fades out', fr: 'Un flash blanc qui s’estompe' },
  whip_wipe: { category: 'hits', defaults: { start: 0 }, en: 'A bar sweeping across the frame', fr: 'Une barre qui balaie l’image' },
  glitch_hit: { category: 'hits', defaults: { start: 0 }, en: 'A short digital glitch', fr: 'Un court glitch numérique' },
  zoom_punch: { category: 'hits', defaults: { start: 0 }, en: 'A quick push into the picture', fr: 'Un rapide zoom avant' },
  split_diagonal: { category: 'layout', defaults: { start: 0, end: 2 }, en: 'A diagonal split with a mirrored half', fr: 'Une coupe en diagonale, moitié en miroir' },
  split_stack: { category: 'layout', defaults: { start: 0, end: 2 }, en: 'Two crops stacked top and bottom', fr: 'Deux cadrages empilés' },
  circle_mask: { category: 'layout', defaults: { start: 0, end: 2 }, en: 'The picture inside a circle', fr: 'L’image dans un cercle' },
  picture_in_picture: { category: 'layout', defaults: { start: 0, end: 2 }, en: 'A zoomed picture with the full frame in a corner', fr: 'Une image zoomée avec le plan entier dans un coin' },
  tiles_grid: { category: 'layout', defaults: { start: 0, end: 2 }, en: 'The picture repeated two by two', fr: 'L’image répétée deux par deux' },
  cutout_echo: { category: 'subject', defaults: { start: 0, end: 2 }, en: 'A white outline and delayed copies of the subject', fr: 'Un contour blanc et des copies décalées du sujet' },
  title_behind: { category: 'subject', defaults: { title: 'NIGHT', start: 0, end: 2 }, en: 'A big title passing behind the subject', fr: 'Un grand titre qui passe derrière le sujet' },
  particles: { category: 'fx', defaults: { start: 0, end: 3 }, en: 'Falling confetti, sparks or snow', fr: 'Confettis, étincelles ou neige qui tombent' },
  sticker: { category: 'fx', defaults: { name: 'burst', start: 0, end: 2 }, en: 'An animated sticker (Lottie)', fr: 'Un sticker animé (Lottie)' },
}

/** What each recipe (a style of VideoTools) is for. */
export const RECIPE_TIPS: Record<string, [string, string]> = {
  kinetic_lyrics: ['The words appear one by one as they are sung, accented words bigger, ending on a title card.', 'Les mots apparaissent un à un quand ils sont chantés, les accentués plus gros, avec une carte titre finale.'],
  punch_text_anime: ['One keyword hits on each cut, very short shots, mixed animation styles.', 'Un mot-clé claque à chaque coupe, plans très courts, styles d’animation mélangés.'],
  editorial_layouts: ['A fashion edit where the layout changes at every cut: splits, circle, fisheye.', 'Un montage mode où la mise en page change à chaque coupe : coupes, cercle, fisheye.'],
  camera_rec_hud: ['A viewfinder look: REC mark, frame brackets, focus pulls, an outfit change on the beat.', 'Un look de viseur : REC, coins de cadre, mises au point, changement de tenue sur le temps.'],
  cutout_collage: ['The subject gets a white outline and delayed copies. Needs the subject mask.', 'Le sujet reçoit un contour blanc et des copies décalées. Demande le masque du sujet.'],
  lipsync_rap: ['Several characters perform the parts of a vocal track, cutting on its phrases.', 'Plusieurs personnages interprètent les parties d’une piste vocale, coupes sur ses phrases.'],
  brand_film_noir: ['Hard light, line art, a glow on objects and an end card with the name.', 'Lumière dure, line art, lueur sur les objets et carte finale avec le nom.'],
}

const TEXT_KEYS = ['content', 'title', 'word', 'label'] as const
const round = (value: number) => Math.round(value * 100) / 100

export interface MotionDoc { rows: MotionRow[]; rest: Record<string, unknown> }

/** The layers of the JSON, which is a list or an object {layers, pack, accent...}: the other keys of the object are kept to write it back. */
export function parseDoc(text: string): MotionDoc | null {
  try {
    const data: unknown = JSON.parse(text.trim() || '[]')
    const object = data && typeof data === 'object' && !Array.isArray(data) ? data as Record<string, unknown> : null
    const rows = object ? object.layers ?? [] : data
    if (!Array.isArray(rows) || !rows.every(row => row && typeof row === 'object' && !Array.isArray(row))) return null
    const { layers: _layers, ...rest } = object ?? {}
    return { rows: rows as MotionRow[], rest }
  } catch {
    return null
  }
}

export const parseRows = (text: string): MotionRow[] | null => parseDoc(text)?.rows ?? null

/** The JSON for `rows`; a document that was an object keeps its other keys (a motion pack, its accent). */
export function writeRows(rows: MotionRow[], original = ''): string {
  const rest = parseDoc(original)?.rest ?? {}
  return JSON.stringify(Object.keys(rest).length ? { ...rest, layers: rows } : rows)
}

const lastEnd = (rows: MotionRow[]) => Math.max(0, ...rows.map(row => typeof row.end === 'number' ? row.end : typeof row.start === 'number' ? row.start : 0))

/** A template after the last layer, pulled back inside the edit when its length is known. */
export function addTemplate(rows: MotionRow[], template: string, duration = 0): MotionRow[] {
  const base = TEMPLATES[template].defaults
  const length = typeof base.end === 'number' ? base.end - (base.start as number) : 0.3
  const start = round(duration > 0 ? Math.max(0, Math.min(lastEnd(rows), duration - length)) : lastEnd(rows))
  const row: MotionRow = { template, ...base, start }
  if (typeof base.end === 'number') row.end = round(start + length)
  return [...rows, row]
}

/** Where the layers of one category sit in the list. */
export const categoryRows = (rows: MotionRow[], category: Category) => rows.flatMap((row, index) => row.template && TEMPLATES[row.template]?.category === category ? [index] : [])

/** One choice for a category: it replaces the template layers of that category, in place and keeping its start when there is just one; '' removes them. */
export function setCategory(rows: MotionRow[], category: Category, template: string, duration = 0): MotionRow[] {
  const present = categoryRows(rows, category)
  const rest = rows.filter((_, index) => !present.includes(index))
  if (!template || !TEMPLATES[template]) return rest
  if (present.length !== 1) return addTemplate(rest, template, duration)
  const old = rows[present[0]]
  const [added] = addTemplate([], template, duration)
  const start = typeof old.start === 'number' ? old.start : 0
  const length = typeof added.end === 'number' ? (added.end as number) - (added.start as number) : 0
  const placed: MotionRow = { ...added, start }
  if (length) placed.end = round(start + length)
  return rows.map((row, index) => index === present[0] ? placed : row)
}

export const textKey = (row: MotionRow) => TEXT_KEYS.find(key => typeof row[key] === 'string')

/** The rows of the text track: words with numeric times, whatever template they belong to. */
export const textRows = (rows: MotionRow[]) => rows.flatMap((row, index) => textKey(row) && typeof row.start === 'number' && typeof row.end === 'number' ? [{ index, row, start: row.start, end: row.end, text: String(row[textKey(row)!]) }] : [])

/** Every layer, with what to show of it: the template or the type, its text and whether it has times to edit. */
export const describeRows = (rows: MotionRow[]) => rows.map((row, index) => {
  const key = textKey(row)
  const name = row.template ?? (row.type === 'effect' && row.kind ? `${row.kind}` : String(row.type ?? 'layer'))
  return { index, name: String(name).replaceAll('_', ' '), category: row.template ? TEMPLATES[row.template]?.category : undefined, text: key ? String(row[key]) : '', timed: typeof row.start === 'number', start: row.start, end: row.end }
})

/** New times for a layer; the end stays after the start and inside the edit when its length is known. */
export function setTimes(rows: MotionRow[], index: number, change: { start?: number; end?: number }, duration = 0): MotionRow[] {
  return rows.map((row, i) => {
    if (i !== index) return row
    const start = Math.max(0, change.start ?? (typeof row.start === 'number' ? row.start : 0))
    const row2: MotionRow = { ...row, start: round(duration > 0 ? Math.min(start, duration) : start) }
    const end = change.end ?? row.end
    if (typeof end === 'number') row2.end = round(Math.max(duration > 0 ? Math.min(end, duration) : end, (row2.start as number) + 0.05))
    return row2
  })
}

export function moveRow(rows: MotionRow[], index: number, seconds: number, duration = 0): MotionRow[] {
  return rows.map((row, i) => {
    if (i !== index || typeof row.start !== 'number') return row
    const length = typeof row.end === 'number' ? row.end - row.start : 0
    const top = duration > 0 ? Math.max(duration - length, 0) : Infinity
    const start = round(Math.min(Math.max(row.start + seconds, 0), top))
    return typeof row.end === 'number' ? { ...row, start, end: round(start + length) } : { ...row, start }
  })
}

export const setText = (rows: MotionRow[], index: number, text: string) => rows.map((row, i) => i === index && textKey(row) ? { ...row, [textKey(row)!]: text } : row)

export const removeRow = (rows: MotionRow[], index: number) => rows.filter((_, i) => i !== index)
