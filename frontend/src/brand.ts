export const BRAND = { name: 'HyperKut', initials: 'HK', logo: '/hyperkut-logo.svg?v=scissors-symmetric', exportPrefix: 'hyperkut' } as const

// Retain installed preferences when upgrading from SECATOR.
// Storage can be blocked (private mode, enterprise policy) or full: preferences then simply do not persist.
export function readPreference(key: string): string | null {
  try { return localStorage.getItem(`hyperkut.${key}`) ?? localStorage.getItem(`secator.${key}`) } catch { return null }
}

export function writePreference(key: string, value: string) {
  try {
    localStorage.setItem(`hyperkut.${key}`, value)
    localStorage.setItem(`secator.${key}`, value)
  } catch { /* not persisted */ }
}

/** A draft kept in the browser: null when absent, unreadable or corrupt. */
export function readDraft<T>(key: string): T | null {
  try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) as T : null } catch { return null }
}
export function writeDraft(key: string, value: unknown): boolean {
  try { localStorage.setItem(key, JSON.stringify(value)); return true } catch { return false }
}
export function removeDraft(key: string) {
  try { localStorage.removeItem(key) } catch { /* nothing to remove */ }
}
