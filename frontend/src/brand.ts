export const BRAND = { name: 'HyperKut', initials: 'HK', logo: '/hyperkut-logo.svg?v=scissors-symmetric', exportPrefix: 'hyperkut' } as const

// Retain installed preferences when upgrading from SECATOR.
export function readPreference(key: string): string | null {
  return localStorage.getItem(`hyperkut.${key}`) ?? localStorage.getItem(`secator.${key}`)
}

export function writePreference(key: string, value: string) {
  localStorage.setItem(`hyperkut.${key}`, value)
  localStorage.setItem(`secator.${key}`, value)
}
