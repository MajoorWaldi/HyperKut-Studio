import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as api from '../api'
import { PlanReview } from '../components/PlanReview'
import { priceLabel, VideoModel } from '../components/VideoModel'
import { DEFAULTS } from '../settings'
import type { ApiCost, JobState, Mode, Settings, VideoEstimate } from '../types'

vi.mock('../api')
const ROWS: VideoEstimate[] = [
  { id: 'minimax_h3', title: 'MiniMax H3 Ref2VA (local)', source: 'local', seconds: null, usd_low: null, usd_high: null, text: '' },
  { id: 'seedance_2_5', title: 'Seedance 2.5 (API)', source: 'api', seconds: 20, usd_low: 2.79, usd_high: 20.58, text: '' },
  { id: 'wan_3_0', title: 'Wan 3.0 (API)', source: 'api', seconds: 15, usd_low: null, usd_high: null, text: '' },
]
beforeEach(() => {
  vi.mocked(api.videoEstimate).mockResolvedValue(ROWS)
  vi.mocked(api.videoModels).mockResolvedValue(ROWS.map(({ id, title, source }) => ({ id, title, source })))
  vi.mocked(api.timeline).mockResolvedValue({ bpm: null, beat_times: [], shots: [] })
})
afterEach(cleanup)

const view = async (settings: Partial<Settings> = {}, onSettings = vi.fn(), mode: Mode = 'text') => {
  render(<VideoModel mode={mode} settings={{ ...DEFAULTS, ...settings }} busy={false} refs={2} refVideo={false} music={false} onSettings={onSettings} />)
  await screen.findAllByRole('radio')
  return onSettings
}

test('shows one card per model with its price for this edit, and keeps H3 the default', async () => {
  expect(DEFAULTS).toMatchObject({ video_model: 'minimax_h3', api_resolution: '720p', api_budget_seconds: 120, api_budget_usd: 0 })
  await view()
  const cards = screen.getAllByRole('radio')
  expect(cards.map(card => card.getAttribute('aria-checked'))).toEqual(['true', 'false', 'false'])
  expect(cards[0].textContent).toContain('Free · runs here')
  expect(cards[1].textContent).toContain('Seedance 2.5')
  expect(cards[1].textContent).toContain('≈ $2.79 – $21')
  expect(cards[2].textContent).toContain('≈ 15 s of video · price at the plan')
})

test('the estimate is asked for the length, shape, resolution and references of the edit', async () => {
  await view({ duration: 30, ratio: '16:9', api_resolution: '1080p' })
  await waitFor(() => expect(api.videoEstimate).toHaveBeenCalledWith({ mode: 'text', seconds: 30, ratio: '16:9', resolution: '1080p', refs: 2, refVideo: false, music: false }))
})

test('without the estimate the models are still offered, with no price', async () => {
  vi.mocked(api.videoEstimate).mockRejectedValue(new Error('down'))
  await view()
  expect(screen.getAllByRole('radio')).toHaveLength(3)
  expect(screen.getAllByRole('radio')[1].textContent).toContain('Paid per take')
})

test('a local model has nothing to pay: no resolution, no budget', async () => {
  await view()
  expect(screen.queryByText(/API resolution/)).toBeNull()
  expect(screen.queryByText(/Budget/)).toBeNull()
})

test('choosing a card writes the setting, and an API model shows the resolution, the budgets and what the edit will spend', async () => {
  const onSettings = await view({ video_model: 'seedance_2_5' })
  fireEvent.click(screen.getAllByRole('radio')[2])
  expect(onSettings).toHaveBeenLastCalledWith({ video_model: 'wan_3_0' })
  fireEvent.change(screen.getByLabelText(/API resolution/), { target: { value: '1080p' } })
  expect(onSettings).toHaveBeenLastCalledWith({ api_resolution: '1080p' })
  fireEvent.change(screen.getByLabelText(/seconds of video/), { target: { value: '60' } })
  expect(onSettings).toHaveBeenLastCalledWith({ api_budget_seconds: 60 })
  fireEvent.change(screen.getByLabelText(/dollars/), { target: { value: '2.5' } })
  expect(onSettings).toHaveBeenLastCalledWith({ api_budget_usd: 2.5 })
  expect(screen.getByRole('status').textContent).toContain('Estimate for 15 s: ≈ $2.79 – $21')
  expect(screen.getByRole('status').textContent).toContain('within the budget')
  expect(screen.getByText(/spends Comfy credits/)).toBeTruthy()
})

test('an estimate over the budget says what happens', async () => {
  await view({ video_model: 'seedance_2_5', api_budget_seconds: 10 })  // 20 s asked, 10 s allowed
  expect(screen.getByRole('status').textContent).toContain('over the budget')
  cleanup()
  await view({ video_model: 'seedance_2_5', api_budget_seconds: 0, api_budget_usd: 5 })  // up to $21 asked, $5 allowed
  expect(screen.getByRole('status').textContent).toContain('over the budget')
})

test('a budget cannot be negative or empty', async () => {
  const onSettings = await view({ video_model: 'seedance_2_5' })
  fireEvent.change(screen.getByLabelText(/seconds of video/), { target: { value: '-5' } })
  fireEvent.change(screen.getByLabelText(/dollars/), { target: { value: '' } })
  expect(onSettings).not.toHaveBeenCalled()
})

test('a model the list does not know (a saved project) is still shown', async () => {
  await view({ video_model: 'some_old_model' })
  expect(screen.getAllByRole('radio').some(card => card.textContent?.includes('some_old_model') && card.getAttribute('aria-checked') === 'true')).toBe(true)
})

test('the price label reads the same in French', () => {
  expect(priceLabel(ROWS[0], true)).toBe('Gratuit · sur cet ordinateur')
  expect(priceLabel(ROWS[2], true)).toBe('≈ 15 s de vidéo · prix au plan')
  expect(priceLabel({ ...ROWS[1], usd_low: 3, usd_high: 3 }, false)).toBe('≈ $3.00')
})

const cost = (over: Partial<ApiCost> = {}): ApiCost => ({ generator: 'seedance_2_5', title: 'Seedance 2.5 (API)', seconds: 14, usd_low: 2.79, usd_high: 20.58, budget_seconds: 120, budget_usd: 0, over_budget: false, stops_at: null, approved: false,
  text: 'Seedance 2.5 (API): 3 shot(s), 14 s of video asked for from the API, about $2.79 to $20.58. Within the budget of 120 s.', ...over })
const review = (api_cost: ApiCost | null) => render(<PlanReview job={{ id: 'j1', status: 'review', shots: [{ id: 'SHOT_001', start: 0, duration: 4, prompt: 'one', render_source: 'generated' }], api_cost } as unknown as JobState}
  busy={false} onApprove={vi.fn()} onRefuse={vi.fn()} onClose={vi.fn()} />)

test('the plan to approve shows what the API model will cost', () => {
  review(cost())
  expect(screen.getByRole('note').textContent).toContain('about $2.79 to $20.58')
  expect(screen.queryByText(/without this cap/)).toBeNull()
})

test('a plan over the budget says that approving lifts the cap', () => {
  review(cost({ over_budget: true, stops_at: 3, text: 'Seedance 2.5 (API): over the budget of 10 s: the run stops before shot 3.' }))
  expect(screen.getByRole('note').textContent).toContain('stops before shot 3')
  expect(screen.getByText(/Approving runs the generation without this cap/)).toBeTruthy()
})

test('a plan made here shows no cost', () => {
  review(null)
  expect(screen.queryByRole('note')).toBeNull()
})

test('a remix asks for the models that can edit a source video, and says what an edit does', async () => {
  await view({ video_model: 'seedance_2_5' }, vi.fn(), 'remix')
  await waitFor(() => expect(api.videoEstimate).toHaveBeenCalledWith(expect.objectContaining({ mode: 'remix' })))
  expect(screen.getByText(/Seedance edits the shot of the source video/)).toBeTruthy()
})

test('a change of length asks the estimate again, once', async () => {
  vi.useFakeTimers()
  const { rerender } = render(<VideoModel mode="text" settings={{ ...DEFAULTS }} busy={false} refs={0} refVideo={false} music={false} onSettings={vi.fn()} />)
  await act(async () => { await vi.advanceTimersByTimeAsync(300) })
  vi.mocked(api.videoEstimate).mockClear()
  for (const duration of [20, 25, 30]) rerender(<VideoModel mode="text" settings={{ ...DEFAULTS, duration }} busy={false} refs={0} refVideo={false} music={false} onSettings={vi.fn()} />)
  await act(async () => { await vi.advanceTimersByTimeAsync(300) })
  expect(api.videoEstimate).toHaveBeenCalledTimes(1)
  expect(api.videoEstimate).toHaveBeenCalledWith(expect.objectContaining({ seconds: 30 }))
  vi.useRealTimers()
})

test('the cards are one stop of the Tab key and the arrows move the choice', async () => {
  const onSettings = await view({ video_model: 'seedance_2_5' })
  const cards = screen.getAllByRole('radio')
  expect(cards.map(card => card.tabIndex)).toEqual([-1, 0, -1])
  fireEvent.keyDown(cards[1], { key: 'ArrowRight' })
  expect(onSettings).toHaveBeenLastCalledWith({ video_model: 'wan_3_0' })
  fireEvent.keyDown(cards[1], { key: 'ArrowLeft' })
  expect(onSettings).toHaveBeenLastCalledWith({ video_model: 'minimax_h3' })
})

test('the budget is compared with the seconds a retry may add', async () => {
  vi.mocked(api.videoEstimate).mockResolvedValue([ROWS[0], { ...ROWS[1], seconds: 80, seconds_high: 160 }])
  await view({ video_model: 'seedance_2_5', api_budget_seconds: 120 })
  expect((await screen.findByRole('status')).textContent).toContain('over the budget')
})
