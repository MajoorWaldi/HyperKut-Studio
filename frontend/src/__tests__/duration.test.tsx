import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Toolbar } from '../components/Toolbar'
import { DEFAULTS } from '../settings'

const setup = (duration = 15) => {
  const onSettings = vi.fn()
  render(<Toolbar mode="text" settings={{ ...DEFAULTS, duration }} busy={false} onSettings={onSettings} />)
  return { onSettings, field: screen.getByLabelText(/seconds|secondes/i) as HTMLInputElement }
}

describe('the length typed in seconds', () => {
  afterEach(cleanup)

  it('is set when the field is left, even above the 30 s of the list', () => {
    const { onSettings, field } = setup()
    fireEvent.change(field, { target: { value: '45' } })
    expect(onSettings).not.toHaveBeenCalled()  // typing "4" then "5" does not set 4 s on the way
    fireEvent.blur(field)
    expect(onSettings).toHaveBeenCalledWith({ duration: 45 })
  })

  it('stays between 2 and 120 seconds and ignores an empty field', () => {
    const { onSettings, field } = setup(20)
    fireEvent.change(field, { target: { value: '500' } })
    fireEvent.keyDown(field, { key: 'Enter' })
    expect(onSettings).toHaveBeenLastCalledWith({ duration: 120 })
    fireEvent.change(field, { target: { value: '1' } })
    fireEvent.blur(field)
    expect(onSettings).toHaveBeenLastCalledWith({ duration: 2 })
    onSettings.mockClear()
    fireEvent.change(field, { target: { value: '' } })
    fireEvent.blur(field)
    expect(onSettings).not.toHaveBeenCalled()
    expect(field.value).toBe('20')
  })

  it('keeps a length that is not in the list as a choice of the list', () => {
    const { field } = setup(45)
    expect(field.value).toBe('45')
  })
})
