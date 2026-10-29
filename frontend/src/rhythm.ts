export interface Grid { ticks: number[]; medianMs: number }

/** Compare cuts against independent half-beat times measured from the soundtrack. */
export function beatGrid(cuts: number[], bpm: number, total: number, measured: number[] = []): Grid | null {
  const ticks = measured.filter(t => Number.isFinite(t) && t >= 0 && t <= total)
  if (!(bpm > 0) || cuts.length === 0 || ticks.length === 0) return null
  const offsets = cuts.map(t => Math.min(...ticks.map(beat => Math.abs(t - beat)))).sort((a, b) => a - b)
  return { ticks, medianMs: Math.round(offsets[Math.floor(offsets.length / 2)] * 1000) }
}

/** A step for the marks of the ruler that stays readable at this zoom: about one mark per 60 pixels. */
export function rulerStep(total: number, width: number): number {
  const wanted = (total * 60) / Math.max(width, 1)
  return [0.5, 1, 2, 5, 10, 15, 30, 60].find(step => step >= wanted) ?? 60
}
