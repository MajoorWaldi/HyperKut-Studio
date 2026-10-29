import { expect, test } from 'vitest'
import { megabytes, presetChips } from '../components/Library'

test('a preset is summed up in a few chips, and sizes are told in MB or GB', () => {
  expect(presetChips({ id: 'x', name: 'x', mode: 'text', description: '', prompt: '', settings: { ratio: '9:16', duration: 15, quality: 'draft', structure: 85, bpm: 128, camera: '' } })).toEqual(['9:16', '15 s', 'Draft', 'Strict', '128 BPM'])
  expect(presetChips({ id: 'x', name: 'x', mode: 'text', description: '', prompt: '' })).toEqual([])
  expect(megabytes(52_000_000)).toBe('52 MB')
  expect(megabytes(2_400_000_000)).toBe('2.4 GB')
  expect(megabytes(10)).toBe('1 MB')
})
