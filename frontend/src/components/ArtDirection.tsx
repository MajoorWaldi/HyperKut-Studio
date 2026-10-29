import { useEffect, useRef, useState } from 'react'
import { artDirectionCatalog, prepareBrief, approveBrief } from '../api'
import { levelValue } from '../creativeControls'
import { useI18n } from '../i18n'
import type { DirectionField, Inputs, Mode, Settings } from '../types'

interface Props { mode: Mode; inputs: Inputs; settings: Settings; busy: boolean; onSettings: (change: Partial<Settings>) => void; onPreparing?: (value: boolean) => void }

export function ArtDirection({ mode, inputs, settings, busy, onSettings, onPreparing }: Props) {
  const { lang } = useI18n(); const fr = lang === 'fr'
  const [open, setOpen] = useState(false)
  const [fields, setFields] = useState<DirectionField[]>([])
  const [draft, setDraft] = useState<string | null>(null); const [context, setContext] = useState('')
  const [working, setWorking] = useState(false); const [error, setError] = useState('')
  const { approved_brief: _brief, approved_brief_context: _context, seed: _seed, ...creative } = settings
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
  const prepare = async () => {
    if (working || busy) return
    const started = key; setWorking(true); onPreparing?.(true); setError('')
    try {
      const result = await prepareBrief(mode, settings, inputs, lang)
      if (current.current !== started) return
      setDraft(result.brief); setContext(result.context)
    } catch (cause) { if (current.current === started) setError((cause as Error).message) }
    finally { setWorking(false); onPreparing?.(false) }
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
  return <details className="creative-direction" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>{fr ? 'Direction artistique' : 'Artistic direction'} <small>{fr ? 'facultatif' : 'optional'}</small></summary>
    <div className="creative-direction-body">
      <p>{fr ? 'Une phrase suffit. Précise seulement les choix qui comptent ; le reste reste automatique.' : 'A short phrase is enough. Choose only what matters; everything else stays automatic.'}</p>
      <div className="creative-direction-fields">{fields.map(field => <label className="field" key={field.key}>
        <span>{fr ? field.fr : field.en}</span>
        <select value={settings.art_direction?.[field.key] ?? 'auto'} disabled={busy || working} onChange={event => onSettings({ art_direction: { ...settings.art_direction, [field.key]: event.target.value } })}>
          <option value="auto">{fr ? 'Automatique' : 'Automatic'}</option>
          {field.choices.map(choice => <option key={choice.value} value={choice.value}>{fr ? choice.fr : choice.en}</option>)}
        </select>
      </label>)}</div>
      {mode !== 'remix' ? <>
        <button type="button" className="secondary" onClick={prepare} disabled={busy || working || settings.prompt.trim().length < 3}>{working ? (fr ? 'Préparation du brief…' : 'Preparing the brief…') : (fr ? 'Voir la direction retenue' : 'Preview the creative brief')}</button>
        <small>{fr ? 'Prépare uniquement le texte avec le modèle local. Aucune vidéo ni musique ne sera générée.' : 'Uses the local model to prepare text only. No video or music will be generated.'}</small>
      </> : <p>{fr ? 'En Remix, ces choix accompagnent la référence sans remplacer son découpage.' : 'In Remix, these choices accompany the reference without replacing its cut timing.'}</p>}
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
