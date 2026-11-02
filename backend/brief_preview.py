"""Run only the existing local enrichment branch, never music or video generation."""
import asyncio
from pathlib import Path
import httpx
from .deployment import brief_texts
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


TREATMENTS = (
    ("direct", "Treatment: DIRECT. Stay close to the request and tell it in its clearest form: one subject, one clear progression from the first shot to the last, the obvious best version."),
    ("twist", "Treatment: TWIST. Keep the subject of the request but give the edit a turn: a surprise, a reveal or a reversal around two thirds of the way, and a last shot that changes how the first is read."),
    ("visual", "Treatment: IMAGE-LED. Less story, more pictures: a motif that comes back changed, strong contrasts of place, scale and light from one shot to the next, the camera as the narrator."),
)


async def prepare_brief(request,settings,uploads,language='en'):
    return (await prepare_briefs(request,settings,uploads,language,('',)))[0]


async def prepare_treatments(request,settings,uploads,language='en'):
    """Three briefs for the same request, each with its own angle, made in one go: the user keeps the one they like."""
    briefs=await prepare_briefs(request,settings,uploads,language,tuple(text for _,text in TREATMENTS))
    return [{**brief,'name':name} for (name,_),brief in zip(TREATMENTS,briefs)]


async def prepare_briefs(request,settings,uploads,language,angles):
    if request.mode=='remix':raise ValueError('Remix follows the source edit; prepare a direction in Text or Music mode.')
    clean=request.model_copy(deep=True);clean.settings.approved_brief='';clean.settings.approved_brief_context=''
    if settings.mock:return [{'brief':(resolved_brief(clean.settings)+(chr(10)+angle if angle else '')).strip(),'context':brief_context(clean)} for angle in angles]
    template=load_templates(settings.templates_dir,clean.mode)['stage1'];runner=ComfyRunner(settings,uploads);job=Job(clean);values=runner._values(job)
    values['planning_instructions'] += chr(10)+'Write the complete enriched brief in '+('French' if language=='fr' else 'English')+'.'
    graphs=[];targets_by_graph=[]
    for number,angle in enumerate(angles):
        mine={**values,'planning_instructions':values['planning_instructions']+(chr(10)+angle if angle else ''),'idea_seed':int(values.get('idea_seed',0))+number}
        supplied={k:v for k,v in mine.items() if k in template.slots}
        graph=template.fill({k:v for k,v in supplied.items() if not isinstance(v,Path)},tuple(k for k in runner._absent(job) if k in template.slots))
        normalize_media_roles(graph)
        target=None
        for key,node in graph.items():
            link=node['inputs'].get('system_prompt')
            if node['class_type']=='TextGenerate' and isinstance(link,list) and graph[str(link[0])]['inputs'].get('skill')=='prompt_enhancer':target=key;break
        if target is None:raise ValueError('This workflow has no brief enrichment branch')
        graph['brief_preview_output']={'class_type':'PreviewAny','inputs':{'source':[target,0]}}
        graphs.append(branch(graph,'brief_preview_output'))
    files={k:v for k,v in values.items() if isinstance(v,Path) and k in template.slots}
    if getattr(settings,'comfy_api',False):
        client=runner.client_factory()
        try:texts=await brief_texts(client,template.slots,graphs,files,'brief_preview_output')
        finally:await client.aclose()
        context=brief_context(clean)
        return [{'brief':text,'context':context} for text in texts]
    async with httpx.AsyncClient(base_url=settings.comfyui_url,timeout=60) as client:
        queue=(await client.get('/queue')).json()
        if queue['queue_running'] or queue['queue_pending']:raise ValueError('The GPU is busy. Prepare the direction after the current generation finishes.')
        for name,file in files.items():
            if not any(n in graph for graph in graphs for n,_ in template.slots[name]):continue
            with file.open('rb') as stream:response=await client.post('/upload/image',files={'image':(file.name,stream,'application/octet-stream')},data={'type':'input'})
            response.raise_for_status();item=response.json();path='/'.join(s for s in [item.get('subfolder',''),item['name']] if s)
            for graph in graphs:
                for n,f in template.slots[name]:
                    if n in graph:graph[n]['inputs'][f]=path
        ids=[]
        for graph in graphs:
            response=await client.post('/prompt',json={'prompt':graph,'client_id':'secator-brief-preview'});response.raise_for_status();ids.append(response.json()['prompt_id'])
        # Do not cancel a global queue or interrupt someone else's work on disconnect.
        results={}
        for _ in range(200*len(ids)):
            for pid in ids:
                if pid in results:continue
                response=await client.get('/history/'+pid);response.raise_for_status();state=response.json().get(pid)
                if state:
                    if state['status']['status_str']!='success':raise ValueError('Brief preparation failed. Check the local model and try again.')
                    text=chr(10).join(state['outputs']['brief_preview_output']['text']).strip()
                    if not text:raise ValueError('The local model returned an empty brief')
                    results[pid]=text
            if len(results)==len(ids):
                context=brief_context(clean)
                return [{'brief':results[pid],'context':context} for pid in ids]
            await asyncio.sleep(1)
        raise ValueError('Brief preparation is taking longer than expected; no video was started.')
