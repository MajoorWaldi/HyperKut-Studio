import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { Toast, type ToastTone } from '../components/Toast'

afterEach(cleanup)

test.each(['success', 'info', 'warning', 'error'] as ToastTone[])('notice %s announces its state beyond color', tone => {
  const { container } = render(<Toast tone={tone} lang="en">Readable message</Toast>)
  const notice = screen.getByRole(tone === 'error' ? 'alert' : 'status')
  expect(notice.textContent).toContain('Readable message')
  expect(container.querySelector(`.toast-${tone} strong`)?.textContent).toBeTruthy()
})

test('French labels and independent undo/dismiss controls work', () => {
  const undo = vi.fn(), dismiss = vi.fn()
  render(<Toast tone="success" lang="fr" action={{ label: 'Annuler', run: undo }} onDismiss={dismiss}>Preset enregistré</Toast>)
  expect(screen.getByText('Succès')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
  expect(undo).toHaveBeenCalledOnce()
  expect(dismiss).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Fermer la notification' }))
  expect(dismiss).toHaveBeenCalledOnce()
})
