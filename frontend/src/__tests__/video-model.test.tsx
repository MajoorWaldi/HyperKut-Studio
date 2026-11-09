import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as api from '../api'
import { PlanReview } from '../components/PlanReview'
import { VideoModel } from '../components/VideoModel'
import { DEFAULTS } from '../settings'
import type { ApiCost, JobState, Settings } from '../types'

vi.mock('../api')
const MODELS = [
  { id: 'minimax_h3', title: 'MiniMax H3 Ref2VA (local)', source: 'local' as const },
  { id: 'seedance_2_5', title: 'Seedance 2.5 (API)', source: 'api' as const },
  { id: 'wan_3_0', title: 'Wan 3.0 (API)', source: 'api' as const },
]
beforeEach(() => {
  vi.mocked(api.videoModels).mockResolvedValue(MODELS)
  vi.mocked(api.timeline).mockResolvedValue({ bpm: null, beat_times: [], shots: [] })
})
afterEach(cleanup)

const view = (settings: Partial<Settings> = {}, onSettings = vi.fn()) => {
  render(<VideoModel settings={{ ...DEFAULTS, ...settings }} busy={false} onSettings={onSettings} />)
  return onSettings
}

test('offers the models of the pack and keeps H3 the default', async () => {
  expect(DEFAULTS).toMatchObject({ video_model: 'minimax_h3', api_resolution: '720p', api_budget_seconds: 120, api_budget_usd: 0 })
  view()
  const select = (await screen.findByRole('combobox', { name: /Video model/ })) as HTMLSelectElement
  await waitFor(() => expect(Array.from(select.options).map(option => option.textContent)).toEqual(['MiniMax H3 Ref2VA (local)', 'Seedance 2.5 (API) · API', 'Wan 3.0 (API) · API']))
  expect(select.value).toBe('minimax_h3')
})

test('a local model has nothing to pay: no resolution, no budget', async () => {
  view()
  await screen.findByRole('combobox', { name: /Video model/ })
  expect(screen.queryByText(/API resolution/)).toBeNull()
  expect(screen.queryByText(/Budget/)).toBeNull()
})

test('choosing an API model writes the setting, and its model shows the resolution and the budgets', async () => {
  const onSettings = view({ video_model: 'seedance_2_5' })
  fireEvent.change(await screen.findByRole('combobox', { name: /Video model/ }), { target: { value: 'wan_3_0' } })
  expect(onSettings).toHaveBeenLastCalledWith({ video_model: 'wan_3_0' })
  fireEvent.change(screen.getByLabelText(/API resolution/), { target: { value: '1080p' } })
  expect(onSettings).toHaveBeenLastCalledWith({ api_resolution: '1080p' })
  fireEvent.change(screen.getByLabelText(/seconds of video/), { target: { value: '60' } })
  expect(onSettings).toHaveBeenLastCalledWith({ api_budget_seconds: 60 })
  fireEvent.change(screen.getByLabelText(/dollars/), { target: { value: '2.5' } })
  expect(onSettings).toHaveBeenLastCalledWith({ api_budget_usd: 2.5 })
  expect(screen.getByText(/spends Comfy credits/)).toBeTruthy()
})

test('a budget cannot be negative or empty', async () => {
  const onSettings = view({ video_model: 'seedance_2_5' })
  await screen.findByRole('combobox', { name: /Video model/ })
  fireEvent.change(screen.getByLabelText(/seconds of video/), { target: { value: '-5' } })
  fireEvent.change(screen.getByLabelText(/dollars/), { target: { value: '' } })
  expect(onSettings).not.toHaveBeenCalled()
})

test('a model the list does not know (a saved project) is still shown', async () => {
  view({ video_model: 'some_old_model' })
  const select = (await screen.findByRole('combobox', { name: /Video model/ })) as HTMLSelectElement
  await waitFor(() => expect(select.value).toBe('some_old_model'))
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
