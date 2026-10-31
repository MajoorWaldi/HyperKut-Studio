import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MotionGallery } from '../components/MotionGallery'
import { addTemplate, CATEGORIES, categoryRows, describeRows, moveRow, parseRows, removeRow, setCategory, setText, setTimes, TEMPLATES, textRows, writeRows } from '../motionLayers'

afterEach(cleanup)

describe('motion layers helpers', () => {
  it('reads a list or an object and refuses broken JSON', () => {
    expect(parseRows('[]')).toEqual([])
    expect(parseRows('{"layers":[{"type":"text"}]}')).toEqual([{ type: 'text' }])
    expect(parseRows('{nope')).toBeNull()
    expect(parseRows('[1]')).toBeNull()
  })

  it('keeps the other keys of a motion document when it writes the layers back', () => {
    const original = '{"pack":"tech","accent":"#ff0000","layers":[]}'
    expect(JSON.parse(writeRows([{ type: 'text', content: 'A' }], original))).toEqual({ pack: 'tech', accent: '#ff0000', layers: [{ type: 'text', content: 'A' }] })
    expect(JSON.parse(writeRows([{ type: 'text', content: 'A' }], '[]'))).toEqual([{ type: 'text', content: 'A' }])
  })

  it('puts every template in a category and every category holds one', () => {
    const known = new Set(CATEGORIES.map(category => category.id))
    expect(Object.values(TEMPLATES).every(template => known.has(template.category) && template.en && template.fr)).toBe(true)
    expect(CATEGORIES.every(category => Object.values(TEMPLATES).some(template => template.category === category.id))).toBe(true)
  })

  it('adds a template after the last layer, inside the edit when its length is known', () => {
    const rows = addTemplate(addTemplate([], 'punch_word'), 'end_card')
    expect(rows[1]).toMatchObject({ template: 'end_card', start: 1, end: 3 })
    expect(addTemplate([{ template: 'end_card', start: 0, end: 9 }], 'flash_hit', 9)[1]).toMatchObject({ start: 8.7 })
    expect(addTemplate([{ template: 'end_card', start: 0, end: 9 }], 'end_card', 9)[1]).toMatchObject({ start: 7, end: 9 })
  })

  it('moves a layer with its end and keeps it inside the edit', () => {
    const rows = addTemplate(addTemplate([], 'punch_word'), 'end_card')
    expect(moveRow(rows, 1, 1.5)[1]).toMatchObject({ start: 2.5, end: 4.5 })
    expect(moveRow(rows, 0, -5)[0]).toMatchObject({ start: 0, end: 1 })
    expect(moveRow(rows, 1, 50, 6)[1]).toMatchObject({ start: 4, end: 6 })
  })

  it('sets times without letting the end pass the start or the edit', () => {
    const rows = [{ template: 'end_card', title: 'A', start: 1, end: 3 }]
    expect(setTimes(rows, 0, { end: 0.5 })[0]).toMatchObject({ start: 1, end: 1.05 })
    expect(setTimes(rows, 0, { end: 99 }, 9)[0]).toMatchObject({ end: 9 })
    expect(setTimes(rows, 0, { start: -4 })[0]).toMatchObject({ start: 0 })
    expect(setTimes([{ template: 'flash_hit', start: 1 }], 0, { start: 2 })[0]).toEqual({ template: 'flash_hit', start: 2 })
  })

  it('describes every layer, also those without text', () => {
    const rows = [{ type: 'text', content: 'A', start: 0, end: 1 }, { template: 'flash_hit', start: 1 }, { type: 'effect', kind: 'grain', start: 0, end: 2 }, { type: 'box' }]
    expect(describeRows(rows).map(row => [row.name, row.category, row.timed])).toEqual([['text', undefined, true], ['flash hit', 'hits', true], ['grain', undefined, true], ['box', undefined, false]])
    expect(textRows(rows).map(row => row.text)).toEqual(['A'])
    expect(setText(rows, 0, 'C')[0].content).toBe('C')
    expect(removeRow(rows, 0)).toHaveLength(3)
  })
})

function Host({ start = '[]', duration = 9, watch }: { start?: string; duration?: number; watch?: (json: string) => void }) {
  const [layers, setLayers] = useState(start)
  return <MotionGallery layers={layers} busy={false} duration={duration} onLayers={json => { setLayers(json); watch?.(json) }} />
}

describe('one choice for each category', () => {
  const rows = [{ template: 'flash_hit', start: 2 }, { template: 'end_card', title: 'A', start: 5, end: 7 }]

  it('finds the layers of a category', () => {
    expect(categoryRows(rows, 'hits')).toEqual([0])
    expect(categoryRows(rows, 'layout')).toEqual([])
  })

  it('replaces the layer of a category in place and keeps its start', () => {
    const next = setCategory(rows, 'hits', 'whip_wipe')
    expect(next).toHaveLength(2)
    expect(next[0]).toMatchObject({ template: 'whip_wipe', start: 2 })
    expect(next[1]).toBe(rows[1])
    expect(setCategory(rows, 'text', 'caption_mono')[1]).toMatchObject({ template: 'caption_mono', start: 5, end: 7 })
  })

  it('adds the first layer of a category, removes it with none, and replaces several by one', () => {
    expect(setCategory(rows, 'layout', 'tiles_grid', 9)[2]).toMatchObject({ template: 'tiles_grid', start: 7, end: 9 })
    expect(setCategory(rows, 'hits', '')).toEqual([rows[1]])
    const many = [...rows, { template: 'glitch_hit', start: 4 }]
    expect(categoryRows(many, 'hits')).toEqual([0, 2])
    expect(setCategory(many, 'hits', 'zoom_punch').map(row => row.template)).toEqual(['end_card', 'zoom_punch'])
  })

  it('leaves layers that are not templates alone', () => {
    const plain = [{ type: 'effect', kind: 'flash', start: 1 }]
    expect(setCategory(plain, 'hits', 'flash_hit')).toHaveLength(2)
  })
})

describe('MotionGallery', () => {
  it('offers one list for each category and applies a choice', () => {
    const watch = vi.fn()
    render(<Host watch={watch} />)
    expect(CATEGORIES.every(category => screen.getByRole('combobox', { name: category.en }))).toBe(true)
    fireEvent.change(screen.getByRole('combobox', { name: 'Hits & transitions' }), { target: { value: 'flash_hit' } })
    expect(JSON.parse(watch.mock.lastCall![0])).toEqual([expect.objectContaining({ template: 'flash_hit' })])
    fireEvent.change(screen.getByRole('combobox', { name: 'Hits & transitions' }), { target: { value: 'glitch_hit' } })
    expect(JSON.parse(watch.mock.lastCall![0])).toEqual([expect.objectContaining({ template: 'glitch_hit' })])
    fireEvent.change(screen.getByRole('combobox', { name: 'Hits & transitions' }), { target: { value: '' } })
    expect(JSON.parse(watch.mock.lastCall![0])).toEqual([])
  })

  it('says when a category holds several layers and keeps the rest in a folded block', () => {
    render(<Host start='[{"template":"flash_hit","start":1},{"template":"glitch_hit","start":2}]' />)
    expect((screen.getByRole('combobox', { name: 'Hits & transitions' }) as HTMLSelectElement).value).toBe('__many__')
    expect(screen.getByText('Several (2)')).toBeTruthy()
    const more = document.querySelector('details.gallery-more') as HTMLDetailsElement
    expect(more.open).toBe(false)
    expect(more.querySelector('summary')?.textContent).toMatch(/All templates, layers and text track · 2/)
  })

  it('groups the templates by category', () => {
    render(<Host />)
    const group = [...document.querySelectorAll('.tag-group')].find(node => node.querySelector('.tag-label')?.textContent === 'Hits & transitions') as HTMLElement
    expect(within(group).getAllByRole('button').map(button => button.textContent)).toEqual(['flash hit', 'whip wipe', 'glitch hit', 'zoom punch'])
    expect(within([...document.querySelectorAll('.tag-group')].find(node => node.querySelector('.tag-label')?.textContent === 'Subject (needs the mask)') as HTMLElement).getAllByRole('button').map(button => button.textContent)).toEqual(['cutout echo', 'title behind'])
  })

  it('lists an added effect that has no text and removes it', async () => {
    const watch = vi.fn()
    render(<Host watch={watch} />)
    await userEvent.click(screen.getByRole('button', { name: 'flash hit' }))
    expect(screen.getByText('Layers on this edit · 1')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Remove flash hit' }))
    expect(JSON.parse(watch.mock.lastCall![0])).toEqual([])
    expect(screen.queryByText(/Layers on this edit/)).toBeNull()
  })

  it('undoes the last changes one by one', async () => {
    const watch = vi.fn()
    render(<Host watch={watch} />)
    const undo = screen.getByRole('button', { name: /undo/i }) as HTMLButtonElement
    expect(undo.disabled).toBe(true)
    await userEvent.click(screen.getByRole('button', { name: 'flash hit' }))
    await userEvent.click(screen.getByRole('button', { name: 'letterbox' }))
    expect(JSON.parse(watch.mock.lastCall![0])).toHaveLength(2)
    await userEvent.click(undo)
    expect(JSON.parse(watch.mock.lastCall![0])).toHaveLength(1)
    await userEvent.click(undo)
    expect(JSON.parse(watch.mock.lastCall![0])).toEqual([])
    expect(undo.disabled).toBe(true)
  })

  it('makes the keystrokes of one field a single undo step', () => {
    const watch = vi.fn()
    render(<Host start='[{"template":"punch_word","word":"HI","start":0,"end":1}]' watch={watch} />)
    const input = screen.getByRole('textbox', { name: 'Text' })
    fireEvent.change(input, { target: { value: 'H' } })
    fireEvent.change(input, { target: { value: 'HEY' } })
    expect(JSON.parse(watch.mock.lastCall![0])[0].word).toBe('HEY')
    fireEvent.click(screen.getByRole('button', { name: /undo/i }))
    expect(JSON.parse(watch.mock.lastCall![0])[0].word).toBe('HI')
  })

  it('edits the times of a layer from the list', () => {
    const watch = vi.fn()
    render(<Host start='[{"template":"end_card","title":"A","start":0,"end":2}]' watch={watch} />)
    fireEvent.change(screen.getByLabelText('End of end card'), { target: { value: '30' } })
    expect(JSON.parse(watch.mock.lastCall![0])[0]).toMatchObject({ start: 0, end: 9 })
  })

  it('keeps the pack of a motion document', async () => {
    const watch = vi.fn()
    render(<Host start='{"pack":"tech","layers":[]}' watch={watch} />)
    await userEvent.click(screen.getByRole('button', { name: 'flash hit' }))
    expect(JSON.parse(watch.mock.lastCall![0])).toMatchObject({ pack: 'tech', layers: [{ template: 'flash_hit' }] })
  })

  it('drags a block of the text track', () => {
    const watch = vi.fn()
    render(<Host start='[{"template":"punch_word","word":"HI","start":0,"end":1}]' watch={watch} />)
    const block = document.querySelector('.text-block') as HTMLElement
    fireEvent.pointerDown(block, { clientX: 10, pointerId: 1 })
    fireEvent.pointerUp(block, { clientX: 62, pointerId: 1 })
    expect(JSON.parse(watch.mock.lastCall![0])[0]).toMatchObject({ start: 2, end: 3 })
  })

  it('says so when the JSON is broken', () => {
    render(<Host start="{nope" />)
    expect(screen.getByText(/invalid/)).toBeTruthy()
  })
})
