import { useState } from 'react'
import { useI18n } from '../i18n'
import type { EnergyReport, ReviewReport } from '../types'

export function ReferenceEnergy({energy}:{energy:EnergyReport|null|undefined}) {
  const {lang}=useI18n()
  const fr=lang==='fr'
  if(!energy)return <small>{fr?'Énergie non mesurée':'Energy not measured'}</small>
  const rows:[string,string][]=[['cut_rate',fr?'Coupes/s':'Cuts/s'],['flash_rate',fr?'Flashs/s':'Flashes/s'],['shake_rate',fr?'Secousses/s':'Shakes/s'],['punch_rate',fr?'Punchs/s':'Punches/s']]
  return <details><summary>{fr?'Énergie : référence et résultat':'Energy: reference and result'}</summary>
    <table><thead><tr><th></th><th>{fr?'Référence':'Reference'}</th><th>{fr?'Résultat':'Result'}</th></tr></thead><tbody>
      {rows.map(([key,label])=><tr key={key}><th>{label}</th><td>{energy.reference?.[key]?.toFixed(2)??'—'}</td><td>{energy.result?.[key]?.toFixed(2)??'—'}</td></tr>)}
    </tbody></table>
    {!energy.reference&&<small>{fr?'Référence non mesurée':'Reference not measured'}</small>}
    {energy.audio?.true_peak_dbtp != null && <p>True peak : {energy.audio.true_peak_dbtp.toFixed(1)} dBTP {energy.audio.within_ceiling ? '✓' : (fr ? '· dépasse −1 dBTP' : '· exceeds −1 dBTP')}</p>}
  </details>
}

export function ReviewPanel({jobId,onSeek}:{jobId:string;onSeek?:(seconds:number)=>void}) {
  const {lang}=useI18n()
  const fr=lang==='fr'
  const [report,setReport]=useState<ReviewReport|null>(null)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')
  const load=async()=>{
    setLoading(true);setError('')
    try {
      const response=await fetch(`/api/jobs/${jobId}/review`)
      const body=await response.json()
      if(!response.ok)throw new Error(body.detail??'Review unavailable')
      setReport(body)
    }catch(e){setError(String(e))}finally{setLoading(false)}
  }
  return <section className="review-panel">
    <button type="button" onClick={load} disabled={loading}>{loading?(fr?'Préparation…':'Preparing…'):(fr?'Relire le résultat':'Review result')}</button>
    {error&&<p role="alert">{error}</p>}
    {report&&<><p>{fr?'Identité, texte et voix : vérification manuelle':'Identity, text and voice: manual review'}</p>
      <div className="review-frames">{report.frames.map(f=><button key={f.seconds} type="button" onClick={()=>onSeek?.(f.seconds)}><img loading="lazy" src={f.url} alt={`${f.seconds.toFixed(2)} s`}/><small>{f.seconds.toFixed(2)} s</small></button>)}</div>
    </>}
  </section>
}
