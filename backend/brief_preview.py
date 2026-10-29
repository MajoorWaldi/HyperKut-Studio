"""Run only the existing local enrichment branch, never music or video generation."""
import asyncio
import json
from pathlib import Path
import httpx
from .direction import brief_context, resolved_brief, normalize_media_roles
from .jobs import Job
from .runner import ComfyRunner
from .templates import load_templates


def branch(graph,root):
    keep=set()
    def visit(key):
        if key in keep:return
        keep.add(key)
        for value in graph[key]['inputs'].values():
            if isinstance(value,list):visit(str(value[0]))
    visit(root)
    return {k:graph[k] for k in keep}


async def prepare_brief(request,settings,uploads,language='en'):
    if request.mode=='remix':raise ValueError('Remix follows the source edit; prepare a direction in Text or Music mode.')
    clean=request.model_copy(deep=True);clean.settings.approved_brief='';clean.settings.approved_brief_context=''
    if settings.mock:return {'brief':resolved_brief(clean.settings),'context':brief_context(clean)}
    template=load_templates(settings.templates_dir,clean.mode)['stage1'];runner=ComfyRunner(settings,uploads);job=Job(clean);values=runner._values(job)
    values['planning_instructions'] += '\nWrite the complete enriched brief in '+('French' if language=='fr' else 'English')+'.'
    supplied={k:v for k,v in values.items() if k in template.slots}
    graph=template.fill({k:v for k,v in supplied.items() if not isinstance(v,Path)},tuple(k for k in runner._absent(job) if k in template.slots))
    normalize_media_roles(graph)
    target=None
    for key,node in graph.items():
        link=node['inputs'].get('system_prompt')
        if node['class_type']=='TextGenerate' and isinstance(link,list) and graph[str(link[0])]['inputs'].get('skill')=='prompt_enhancer':target=key;break
    if target is None:raise ValueError('This workflow has no brief enrichment branch')
    graph['brief_preview_output']={'class_type':'PreviewAny','inputs':{'source':[target,0]}}
    graph=branch(graph,'brief_preview_output')
    async with httpx.AsyncClient(base_url=settings.comfyui_url,timeout=60) as client:
        queue=(await client.get('/queue')).json()
        if queue['queue_running'] or queue['queue_pending']:raise ValueError('The GPU is busy. Prepare the direction after the current generation finishes.')
        for name,file in supplied.items():
            if not isinstance(file,Path):continue
            targets=[(n,f) for n,f in template.slots[name] if n in graph]
            if not targets:continue
            with file.open('rb') as stream:response=await client.post('/upload/image',files={'image':(file.name,stream,'application/octet-stream')},data={'type':'input'})
            response.raise_for_status();item=response.json();path='/'.join(s for s in [item.get('subfolder',''),item['name']] if s)
            for n,f in targets:graph[n]['inputs'][f]=path
        response=await client.post('/prompt',json={'prompt':graph,'client_id':'secator-brief-preview'});response.raise_for_status();pid=response.json()['prompt_id']
        # Do not cancel a global queue or interrupt someone else's work on disconnect.
        for _ in range(180):
            response=await client.get('/history/'+pid);response.raise_for_status();state=response.json().get(pid)
            if state:
                if state['status']['status_str']!='success':raise ValueError('Brief preparation failed. Check the local model and try again.')
                text='\n'.join(state['outputs']['brief_preview_output']['text']).strip()
                if not text:raise ValueError('The local model returned an empty brief')
                return {'brief':text,'context':brief_context(clean)}
            await asyncio.sleep(1)
        raise ValueError('Brief preparation is taking longer than expected; no video was started.')
