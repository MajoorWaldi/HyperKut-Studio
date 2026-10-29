import {describe, it, expect} from 'vitest'
import {localizePreset, translatePresetSettings} from '../presets'
import {DEFAULTS} from '../settings'
import type {Preset} from '../types'

const preset: Preset = {id:'test', name:'Product', mode:'text', description:'English', prompt:'A bottle', settings:{mood:'Trap',camera:'Macro'}, translations:{fr:{name:'Produit',description:'Français',prompt:'Un flacon',settings:{mood:'Musique trap',camera:'Caméra macro'}}}}
describe('preset language', () => {
 it('localizes cards and editable fields without changing the source', () => {
   expect(localizePreset(preset,'fr').prompt).toBe('Un flacon')
   expect(localizePreset(preset,'en').description).toBe('English')
   expect(preset.prompt).toBe('A bottle')
 })
 it('switches untouched text and preserves user edits', () => {
   const next=translatePresetSettings({...DEFAULTS,prompt:'A bottle',mood:'Trap',camera:'Custom camera'},preset,'fr')
   expect(next.prompt).toBe('Un flacon'); expect(next.mood).toBe('Musique trap'); expect(next.camera).toBe('Custom camera')
   expect(translatePresetSettings({...next,prompt:'My story'},preset,'en').prompt).toBe('My story')
 })
})
