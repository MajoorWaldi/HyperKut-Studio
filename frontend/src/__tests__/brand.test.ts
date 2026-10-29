import { beforeEach, expect, test } from 'vitest'
import { BRAND, readPreference, writePreference } from '../brand'
beforeEach(() => localStorage.clear())
test('HyperKut exposes its new identity', () => { expect(BRAND.name).toBe('HyperKut'); expect(BRAND.initials).toBe('HK') })
test('existing language and zoom survive rebranding; new preference wins', () => {
 localStorage.setItem('secator.lang', 'fr'); expect(readPreference('lang')).toBe('fr')
 localStorage.setItem('hyperkut.lang', 'en'); expect(readPreference('lang')).toBe('en')
 localStorage.setItem('secator.zoom', '.8'); expect(readPreference('zoom')).toBe('.8')
})
test('preferences remain readable by previous clients', () => {
 writePreference('lang','fr'); expect(localStorage.getItem('hyperkut.lang')).toBe('fr'); expect(localStorage.getItem('secator.lang')).toBe('fr')
})
