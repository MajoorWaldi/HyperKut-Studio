import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { InputsPanel } from '../components/InputsPanel'
import { dictionaries } from '../i18n'
import type { Inputs, Settings } from '../types'

vi.mock('../components/ArtDirection', () => ({ ArtDirection: () => null }))
vi.mock('../components/Options', () => ({ Options: () => null }))
afterEach(cleanup)

const inputs: Inputs = { source: null, refs: [null, null, null, null, null], refVideo: null, music: null, voice: null }
const view = (mode: 'music' | 'text' | 'remix', edit = 'adaptive', onSettings = vi.fn()) => {
  render(<InputsPanel mode={mode} inputs={inputs} settings={{ prompt: '', audio: 'new', dialogue: '', music_edit_mode: edit } as Settings} busy={false} onUpload={vi.fn()} onClear={vi.fn()} onSettings={onSettings} />)
  return onSettings
}

test('the music tab offers three ways to cut, each with a short explanation', () => {
  view('music')
  const group = screen.getByRole('group', { name: 'Editing rhythm' })
  const buttons = Array.from(group.querySelectorAll('button'))
  expect(buttons.map(button => button.textContent)).toEqual(['Adaptive', 'Regular', 'Vocal phrases'])
  expect(buttons.map(button => button.getAttribute('title'))).toEqual([dictionaries.en.tip.rhythmAdaptive, dictionaries.en.tip.rhythmRegular, dictionaries.en.tip.rhythmPhrases])
  expect(buttons.map(button => button.getAttribute('aria-pressed'))).toEqual(['true', 'false', 'false'])
})

test('it sits right under the music uploader', () => {
  view('music')
  const section = screen.getByRole('group', { name: 'Editing rhythm' }).closest('section') as HTMLElement
  const children = Array.from(section.children)
  const slot = children.findIndex(child => child.querySelector('input[type="file"]') || child.matches('.slot-wrap'))
  expect(children.findIndex(child => child.classList.contains('rhythm-choice'))).toBe(slot + 1)
})

test('a choice is written to the setting', () => {
  const onSettings = view('music')
  fireEvent.click(screen.getByRole('button', { name: 'Vocal phrases' }))
  expect(onSettings).toHaveBeenLastCalledWith({ music_edit_mode: 'phrases' })
})

test('a mode loaded from a preset that is not one of the three is shown as custom, not hidden', () => {
  view('music', 'random')
  const custom = screen.getByRole('button', { name: 'Custom' }) as HTMLButtonElement
  expect(custom.disabled).toBe(true)
  expect(custom.getAttribute('aria-pressed')).toBe('true')
})

test.each(['text', 'remix'] as const)('%s does not show it: its options keep the long list', mode => {
  view(mode)
  expect(screen.queryByRole('group', { name: 'Editing rhythm' })).toBeNull()
})
