import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Tooltips } from '../components/Tooltips'
import { dictionaries } from '../i18n'

afterEach(cleanup)

const files = import.meta.glob('../**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true }) as Record<string, string>
const code = Object.entries(files).filter(([path]) => !path.includes('__tests__')).map(([, text]) => text).join('\n')

describe('the tooltips of the Studio', () => {
  const tips = (lang: 'en' | 'fr') => Object.entries(dictionaries[lang].tip) as [string, string][]

  it('are written in both languages with the same keys', () => {
    expect(tips('fr').map(([key]) => key)).toEqual(tips('en').map(([key]) => key))
  })

  it('are short, finished sentences, and French is not a copy of English', () => {
    for (const lang of ['en', 'fr'] as const) {
      for (const [key, text] of tips(lang)) {
        expect(text.trim(), `${lang}.${key}`).not.toBe('')
        expect(text.length, `${lang}.${key} is long`).toBeLessThanOrEqual(260)
        expect(/[.?!)]$/.test(text), `${lang}.${key} has no final stop`).toBe(true)
      }
    }
    for (const [key, text] of tips('fr')) expect(text, key).not.toBe(dictionaries.en.tip[key as keyof typeof dictionaries.en.tip])
  })

  it('all belong to a control: no tip is left unused', () => {
    const unused = tips('en').map(([key]) => key).filter(key => !new RegExp(`tip\\.${key}\\b`).test(code))
    expect(unused).toEqual([])
  })
})

describe('the tooltip bubble', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  const hover = (element: Element) => { fireEvent.mouseOver(element); act(() => { vi.advanceTimersByTime(600) }) }

  it('explains a switch that is already on, since it is the only place the switch is described', () => {
    render(<><Tooltips /><label className="chip-toggle on" title="What the switch does.">Switch</label></>)
    hover(screen.getByText('Switch'))
    expect(screen.getByRole('tooltip').textContent).toBe('What the switch does.')
  })

  it('stays quiet on what is already chosen', () => {
    render(<><Tooltips /><button aria-pressed="true" title="Chosen">Chosen</button></>)
    hover(screen.getByText('Chosen'))
    expect(screen.queryByRole('tooltip')).toBeNull()
  })
})
