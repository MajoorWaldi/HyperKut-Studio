import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { InputsPanel } from '../components/InputsPanel'
import { dictionaries } from '../i18n'
import type { Inputs, Settings } from '../types'

vi.mock('../components/ArtDirection', () => ({ ArtDirection: () => null }))
vi.mock('../components/Options', () => ({ Options: () => null }))
afterEach(cleanup)

const image = (id: string) => ({ id, name: `${id}.png`, kind: 'image' as const, url: `/${id}.png` })
const inputs: Inputs = { source: null, refs: [null, null, null, null, null], refVideo: null, music: null, voice: null }
const settings = { prompt: '', audio: 'new', dialogue: '' } as Settings

test.each(['text', 'music', 'remix'] as const)('%s reveals one empty reference at a time and keeps slot targets after removal', mode => {
  const onUpload = vi.fn(), onClear = vi.fn()
  const props = { mode, inputs, settings, busy: false, onUpload, onClear, onSettings: vi.fn() }
  const { container, rerender } = render(<InputsPanel {...props} />)
  const slots = () => container.querySelectorAll('.ref-grid .slot-wrap')
  expect(slots()).toHaveLength(1)
  const file = new File(['image'], 'one.png', { type: 'image/png' })
  fireEvent.change(slots()[0].querySelector('input')!, { target: { files: [file] } })
  expect(onUpload).toHaveBeenLastCalledWith({ ref: 0 }, file)
  rerender(<InputsPanel {...props} inputs={{ ...inputs, refs: [image('a'), image('b'), null, null, null] }} />)
  expect(slots()).toHaveLength(3)
  fireEvent.click(slots()[0].querySelector('.slot-clear')!)
  expect(onClear).toHaveBeenLastCalledWith({ ref: 0 })
  rerender(<InputsPanel {...props} inputs={{ ...inputs, refs: [null, image('b'), null, null, null] }} />)
  expect(slots()).toHaveLength(2)
  expect(screen.getByAltText('b.png')).toBeTruthy()
  fireEvent.change(slots()[1].querySelector('input')!, { target: { files: [file] } })
  expect(onUpload).toHaveBeenLastCalledWith({ ref: 0 }, file)
  rerender(<InputsPanel {...props} inputs={{ ...inputs, refs: ['a','b','c','d','e'].map(image) }} />)
  expect(slots()).toHaveLength(5)
  expect(screen.queryByRole('button', { name: dictionaries.en.addReference })).toBeNull()
})
