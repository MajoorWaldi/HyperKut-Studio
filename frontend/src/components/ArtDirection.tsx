import { useEffect, useRef, useState } from 'react'
import { artDirectionCatalog, prepareBrief, prepareTreatments, approveBrief } from '../api'
import { levelValue } from '../creativeControls'
import { useI18n } from '../i18n'
import { CountBadge } from './CountBadge'
import type { DirectionField, Inputs, Mode, Settings } from '../types'

interface Props { mode: Mode; inputs: Inputs; settings: Settings; busy: boolean; onSettings: (change: Partial<Settings>) => void; onPreparing?: (value: boolean) => void }

export function ArtDirection({ mode, inputs, settings, busy, onSettings, onPreparing }: Props) {
  const { t, lang } = useI18n(); const fr = lang === 'fr'
  const [open, setOpen] = useState(false)
  const [fields, setFields] = useState<DirectionField[]>([])
  const [draft, setDraft] = useState<string | null>(null); const [context, setContext] = useState('')
  const [working, setWorking] = useState(false); const [error, setError] = useState('')
  const [treatments, setTreatments] = useState<{ name: string; brief: string; context: string }[]>([])
  const { approved_brief: _brief, approved_brief_context: _context, seed: _seed, idea_seed: _idea, ...creative } = settings
  const {structure:_structure,creativity:_creativity,...baseCreative}=creative
  const baseKey=JSON.stringify({mode,creative:baseCreative,inputs})
  const key = JSON.stringify({baseKey,structure:levelValue(creative.structure),creativity:levelValue(creative.creativity)})
  const current = useRef(key); current.current = key
  const previousBase=useRef(baseKey)
  useEffect(() => { if(previousBase.current!==baseKey)setDraft(null); previousBase.current=baseKey; setContext(''); setError('') }, [key,baseKey])
  useEffect(() => {
    if (!open) return
    let active = true
    artDirectionCatalog().then(data => { if (active && Array.isArray(data.fields)) setFields(data.fields) }).catch(() => { if (active) setError(fr ? 'Les choix sont indisponibles. Tu peux toujours décrire ton style dans la phrase.' : 'Choices are unavailable. You can still describe the style in your brief.') })
    return () => { active = false }
  }, [open, fr])
  const prepare = async (asked: Settings = settings) => {
    if (working || busy) return
    const started = key; setWorking(true); onPreparing?.(true); setError('')
    try {
      const result = await prepareBrief(mode, asked, inputs, lang)
      if (current.current !== started) return
      setDraft(result.brief); setContext(result.context)
    } catch (cause) { if (current.current === started) setError((cause as Error).message) }
    finally { setWorking(false); onPreparing?.(false) }
  }
  const three = async () => {
    if (working || busy) return
    const started = key; setWorking(true); onPreparing?.(true); setError(''); setTreatments([])
    try {
      const result = await prepareTreatments(mode, settings, inputs, lang)
      if (current.current !== started) return
      setTreatments(result.treatments)
    } catch (cause) { if (current.current === started) setError((cause as Error).message) }
    finally { setWorking(false); onPreparing?.(false) }
  }
  const pick = (item: { brief: string; context: string }) => { setDraft(item.brief); setContext(item.context); setTreatments([]) }
  const another = () => {
    if (working || busy) return
    const idea_seed = (settings.idea_seed ?? 0) + 1
    onSettings({ idea_seed, approved_brief: '', approved_brief_context: '' })
    void prepare({ ...settings, idea_seed, approved_brief: '', approved_brief_context: '' })
  }
  const useBrief=async()=>{
    const text=(draft ?? settings.approved_brief ?? '').trim()
    if(!text || working || busy)return
    const started=key;setWorking(true);onPreparing?.(true);setError('')
    try{
      const approved=await approveBrief(mode,settings,inputs,text)
      if(current.current!==started)return
      setContext(approved.context)
      onSettings({approved_brief:text,approved_brief_context:approved.context})
    }catch(cause){if(current.current===started)setError((cause as Error).message)}
    finally{setWorking(false);onPreparing?.(false)}
  }
  const chosen = Object.values(settings.art_direction ?? {}).filter(value => value && value !== 'auto').length + (settings.approved_brief ? 1 : 0)
  return <details className="creative-direction" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>{fr ? 'Direction artistique' : 'Artistic direction'}{chosen > 0 ? <CountBadge count={chosen} label={fr ? 'actif(s)' : 'active'} /> : <> <small>{fr ? 'facultatif' : 'optional'}</small></>}</summary>
    <div className="creative-direction-body">
      <p>{fr ? 'Une phrase suffit. Précise seulement les choix qui comptent ; le reste reste automatique.' : 'A short phrase is enough. Choose only what matters; everything else stays automatic.'}</p>
      <div className="creative-direction-fields">{fields.map(field => <label className="field" key={field.key} title={{ look: t.tip.artLook, mood: t.tip.artMood, camera: t.tip.artCamera, light: t.tip.artLight }[field.key]}>
        <span>{fr ? field.fr : field.en}</span>
        <select value={settings.art_direction?.[field.key] ?? 'auto'} disabled={busy || working} onChange={event => onSettings({ art_direction: { ...settings.art_direction, [field.key]: event.target.value } })}>
          <option value="auto">{fr ? 'Automatique' : 'Automatic'}</option>
          {field.choices.map(choice => <option key={choice.value} value={choice.value}>{fr ? choice.fr : choice.en}</option>)}
        </select>
      </label>)}</div>
      {<>
        <div className="prepared-actions"><button type="button" className="secondary" onClick={() => prepare()} disabled={busy || working || settings.prompt.trim().length < 3}>{working ? (fr ? 'Préparation du brief…' : 'Preparing the brief…') : (fr ? 'Voir la direction retenue' : 'Preview the creative brief')}</button>
        <button type="button" className="secondary" title={fr ? 'Une autre idée pour la même demande : le plan, l’histoire et le casting changent.' : 'Another idea for the same request: the plan, the story and the cast change.'} onClick={another} disabled={busy || working || settings.prompt.trim().length < 3}>{fr ? `Autre idée (n° ${(settings.idea_seed ?? 0) + 1})` : `Another idea (no. ${(settings.idea_seed ?? 0) + 1})`}</button>
        <button type="button" className="secondary" title={mode === 'remix' ? (fr ? 'Trois versions du remix sur le même découpage : fidèle, dans un autre monde, une autre histoire. Tu gardes celle que tu préfères.' : 'Three versions of the remix over the same cuts: faithful, in another world, another story. You keep the one you like.') : (fr ? 'Trois versions de la même demande : directe, avec un retournement, portée par l’image. Tu gardes celle que tu préfères.' : 'Three versions of the same request: direct, with a twist, image-led. You keep the one you like.')} onClick={three} disabled={busy || working || settings.prompt.trim().length < 3}>{fr ? 'Trois traitements' : 'Three treatments'}</button></div>
        {treatments.length > 0 && <div className="treatments">{treatments.map(item => <article className="treatment" key={item.name}>
          <h4>{{ direct: fr ? 'Direct' : 'Direct', twist: fr ? 'Retournement' : 'Twist', visual: fr ? 'Porté par l’image' : 'Image-led', faithful: fr ? 'Fidèle' : 'Faithful', transfer: fr ? 'Autre histoire' : 'Another story' }[item.name] ?? item.name}</h4>
          <p>{item.brief.length > 420 ? item.brief.slice(0, 420) + '…' : item.brief}</p>
          <button type="button" className="secondary" onClick={() => pick(item)}>{fr ? 'Choisir' : 'Choose'}</button>
        </article>)}</div>}
        <small>{fr ? 'Prépare uniquement le texte avec le modèle local. Aucune vidéo ni musique ne sera générée.' : 'Uses the local model to prepare text only. No video or music will be generated.'}</small>
        {mode === 'remix' && <p>{fr ? 'En Remix, ces choix accompagnent la référence sans remplacer son découpage.' : 'In Remix, these choices accompany the reference without replacing its cut timing.'}</p>}
      </>}
      {(draft !== null || settings.approved_brief) && <div className="prepared-brief">
        <label className="field"><span>{fr ? 'Brief enrichi — modifiable' : 'Enriched brief — editable'}</span><textarea rows={8} maxLength={5000} value={draft ?? settings.approved_brief ?? ''} disabled={busy || working} onChange={event => { setDraft(event.target.value); if (!context) setContext(settings.approved_brief_context ?? '') }} /></label>
        <div className="prepared-actions"><button type="button" className="secondary" disabled={busy || working || !(draft ?? settings.approved_brief)?.trim()} onClick={useBrief}>{fr ? 'Utiliser ce brief' : 'Use this brief'}</button>
        <button type="button" className="secondary" disabled={busy || working} onClick={() => { setDraft(null); setContext(''); onSettings({ approved_brief: '', approved_brief_context: '' }) }}>{fr ? 'Revenir à ma phrase' : 'Use my original phrase'}</button></div>
        {settings.approved_brief && <p role="status">{!settings.approved_brief_context ? (fr ? 'Réglages modifiés : ton texte est conservé. Clique sur « Utiliser ce brief » pour le réutiliser, ou prépare une nouvelle direction.' : 'Settings changed: your text is preserved. Choose Use this brief to reuse it, or prepare a new direction.') : draft !== null && draft !== settings.approved_brief ? (fr ? 'Modifications à appliquer avec « Utiliser ce brief ».' : 'Apply your changes with Use this brief.') : (fr ? 'Ce brief sera utilisé au prochain lancement.' : 'This brief will be used for the next generation.')}</p>}
      </div>}
      {error && <p role="alert" className="creative-error">{error}</p>}
    </div>
  </details>
}
