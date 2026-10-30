"""Compile existing templates to explicit snapshot graphs; publish a local mirror."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from filelock import FileLock
from .artifact_bundle import write_bundle
from .artifact_store import LocalArtifactStore,CHUNK_SIZE
from .project_snapshot import capture_project,materialize_snapshot,checked_file
from .snapshot_schema import shot_list
from .storage import project_path,write_json,ProjectRevisionConflict

EXPORT='__hk_export'
IMPORT='__hk_import'
WORKSPACE='__hk_workspace'


def compile_graph(graph,token,*,initial=False):
    prompt=copy.deepcopy(graph)
    if any(key.startswith('__hk_') for key in prompt):raise ValueError('Reserved remote node id')
    saved=[key for key,node in prompt.items() if node['class_type']=='MajoorSaveProjectInfo']
    loads=[key for key,node in prompt.items() if node['class_type']=='MajoorLoadShotList']
    if initial:
        if len(saved)!=1:raise ValueError('Initial graph must publish exactly one project')
        prompt[WORKSPACE]={'class_type':'HyperKutWorkspace','inputs':{'operation_id':token}}
        for node in prompt.values():
            if node['class_type'] in ('MajoorCreateTimeline','MajoorSceneDetectSplit'):
                node['inputs']['project_root']=[WORKSPACE,0]
        project_link=[saved[0],0]
    else:
        if len(loads)!=1:raise ValueError('Remote graph must load exactly one project')
        prompt[IMPORT]={'class_type':'HyperKutSnapshotImport','inputs':{'archive':'','operation_id':token}}
        old=loads[0]
        for node in prompt.values():
            for key,value in list(node['inputs'].items()):
                if isinstance(value,list) and len(value)==2 and value[0]==old:
                    if value[1]!=0:raise ValueError('Unexpected project output')
                    node['inputs'][key]=[IMPORT,0]
        del prompt[old]
        project_link=[saved[0],0] if saved else [IMPORT,0]
    exports={'shot_list':project_link,'operation_id':token}
    for key,node in list(prompt.items()):
        if node['class_type']=='MajoorSaveProjectMusic':
            node['inputs']['shot_list']=project_link
            exports['after_audio']=[key,0]
        elif node['class_type']=='MajoorLoadProjectMusic':node['inputs']['project']=[IMPORT,0]
        elif node['class_type']=='MajoorHyperFrames':node['inputs']['project']=project_link
        elif node['class_type']=='MajoorEnergyReport':exports['after_report']=[key,0]
        elif node['class_type']=='SaveVideo':exports['after_video']=[key,0]
    prompt[EXPORT]={'class_type':'HyperKutSnapshotExport','inputs':exports}
    return prompt


def file_token(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(CHUNK_SIZE):digest.update(chunk)
    return digest.hexdigest()


def manifest_token(project):
    path=Path(project)/'manifest.json'
    return file_token(path) if path.is_file() else None


class RemoteMirror:
    def __init__(self,settings):
        self.settings=settings
        self.store=LocalArtifactStore(settings.workspace/'artifacts',
            max_artifact_bytes=getattr(settings,'max_artifact_bytes',2*1024**3),
            max_cache_bytes=getattr(settings,'max_artifact_cache_bytes',20*1024**3))
        self.root=settings.output_dir/'MajoorVideoTools'
        LocalArtifactStore(self.root)
        self.scratch=settings.workspace/'remote-transfers'
        self.scratch.mkdir(parents=True,exist_ok=True)
        self.retention_lock=FileLock(str(self.scratch/'.retention.lock'),timeout=120)
        self.coverage=self.scratch/'retention-v1.json'
        if not self.coverage.exists() and self.store.inventory()['artifact_count']==0:
            write_json(self.coverage,{'version':1})

    def prepare(self,project_id,token,*,expected_manifest=None):
        project=project_path(self.root,project_id)
        with self.retention_lock:
            path=self.scratch/f'{token}.input.zip'
            descriptor=self.scratch/f'{token}.input.descriptor.json'
            if os.path.lexists(path) or os.path.lexists(descriptor):
                raise FileExistsError('Snapshot transfer token is already in use')
            snapshot=capture_project(self.store,project)
            expected=snapshot.manifest.sha256
            if expected_manifest is not None and expected!=expected_manifest:
                raise ProjectRevisionConflict('Project changed before remote submission; reload the saved montage and retry')
            write_json(descriptor,snapshot.to_dict())
            try:
                with path.open('xb') as stream:write_bundle(self.store,snapshot,stream)
            except BaseException:
                path.unlink(missing_ok=True)
                descriptor.unlink(missing_ok=True)
                raise
        return path,expected

    def publish(self,snapshot,expected,job_id,operation_id=None):
        project=project_path(self.root,snapshot.project_id)
        identity=hashlib.sha256(json.dumps(
            {'snapshot':snapshot.to_dict(),'expected':expected,'job_id':job_id,'operation_id':operation_id},
            sort_keys=True,allow_nan=False).encode()).hexdigest()
        receipt=self.scratch/'publications'/f'{identity}.json'
        with self.retention_lock,materialize_snapshot(self.store,snapshot,self.scratch) as staged:
            manifest=json.loads((staged/'manifest.json').read_text(encoding='utf-8'))
            sl=shot_list(manifest)
            rows=[]
            for shot in sorted(sl.shots,key=lambda row:row.timeline_index):
                source=sl.source
                start=float((shot.start_pts-source.first_pts)*source.time_base) if source.timing_mode=='VFR' and shot.start_pts is not None else float(shot.start_frame/source.fps)
                plan=shot.plan or {}
                rows.append({'id':shot.shot_id,'start':start,'duration':shot.target_duration_seconds,
                    'prompt':plan.get('prompt',''),'generation_prompt':shot.active.generation_prompt,
                    'generation_frames':plan.get('generation_frames',0),'render_source':plan.get('render_source',{}).get('kind','generated')})
            # Validate the UI projection before installing any result bytes.
            from .models import Shot
            for row in rows:Shot.model_validate(row)
            index={'project_id':sl.project_id,'shots':rows}
            result_token=hashlib.sha256(json.dumps(manifest,sort_keys=True,allow_nan=False).encode()).hexdigest()
            with FileLock(str(project/'.lock'),timeout=120):
                if receipt.is_file():
                    return project
                current=manifest_token(project)
                already_installed=False
                if current is not None:
                    installed=json.loads((project/'manifest.json').read_text(encoding='utf-8'))
                    already_installed=hashlib.sha256(json.dumps(installed,sort_keys=True,allow_nan=False).encode()).hexdigest()==result_token
                    if already_installed:
                        for asset in snapshot.assets:
                            try:
                                destination=checked_file(project,asset.relative_path)
                            except FileNotFoundError:
                                already_installed=False
                                break
                            if file_token(destination)!=asset.artifact.sha256:
                                already_installed=False
                                break
                # The manifest is committed last. Its exact result identity also
                # reconciles a crash between that commit and the durable receipt.
                if current!=expected and not already_installed:
                    # Retain descriptor + all cached blobs for explicit reconciliation.
                    write_json(self.scratch/f'{job_id}-{snapshot.revision}-{uuid.uuid4().hex}.conflict.json',snapshot.to_dict())
                    raise ProjectRevisionConflict('Project changed during remote rendering; result retained for reconciliation')
                for asset in snapshot.assets:
                    source=checked_file(staged,asset.relative_path)
                    destination=project/asset.relative_path
                    # Existing user/project symlinks must never redirect installation.
                    parent=destination.parent
                    while parent!=project.parent:
                        if os.path.lexists(parent):
                            info=parent.lstat()
                            if parent.is_symlink() or getattr(info,'st_file_attributes',0)&0x400:raise ValueError('Mirror path contains a reparse point')
                        parent=parent.parent
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    if destination.exists() or destination.is_symlink():
                        checked_file(project,asset.relative_path)
                        if file_token(destination)==asset.artifact.sha256:continue
                    fd,name=tempfile.mkstemp(dir=destination.parent,suffix='.incoming')
                    try:
                        with os.fdopen(fd,'wb') as stream,source.open('rb') as incoming:
                            shutil.copyfileobj(incoming,stream,CHUNK_SIZE)
                            stream.flush();os.fsync(stream.fileno())
                        os.replace(name,destination)
                    finally:Path(name).unlink(missing_ok=True)
                write_json(self.scratch/'history'/snapshot.project_id/f'{identity}.descriptor.json',snapshot.to_dict())
                write_json(project/'manifest.json',manifest)
                write_json(self.root/'_jobs'/f'{job_id}.json',index)
                write_json(receipt,{'snapshot':snapshot.to_dict(),'expected':expected,'job_id':job_id,'operation_id':operation_id})
            return project

    def finish_transfer(self,token):
        with self.retention_lock:
            for suffix in ('input.zip','input.descriptor.json'):
                (self.scratch/f'{token}.{suffix}').unlink(missing_ok=True)

    def forget_project(self,project_id):
        project_path(self.root,project_id)
        with self.retention_lock:
            history=self.scratch/'history'/project_id
            for path in history.glob('*.descriptor.json'):path.unlink()
            # POSIX file locks retain their inode after release; do not unlink it.
            if history.is_dir() and not any(history.iterdir()):history.rmdir()
            for path in (self.scratch/'publications').glob('*.json'):
                if json.loads(path.read_text(encoding='utf-8'))['snapshot']['project_id']==project_id:path.unlink()

    def cache_inventory(self,*,collect=False,dry_run=True):
        from .artifact_contract import ProjectSnapshot
        with self.retention_lock:
            descriptors=[*self.scratch.glob('*.input.descriptor.json'),*self.scratch.glob('*.conflict.json'),
                         *(self.scratch/'history').glob('*/*.descriptor.json')]
            retained=[ProjectSnapshot.from_dict(json.loads(path.read_text(encoding='utf-8'))) for path in descriptors]
            operation=self.store.collect_garbage if collect else self.store.inventory
            options={'references_complete':self.coverage.is_file()}
            if collect:options['dry_run']=dry_run
            return operation(retained,**options)


def validate_remote_graph(graph,schemas):
    """Check deployment and exact selected weights before any model submission."""
    from .templates import graph_readiness, reachable_graph

    required={'HyperKutWorkspace','HyperKutSnapshotImport','HyperKutSnapshotExport','HyperKutWorkspaceRelease'}
    missing=sorted(required-set(schemas))
    if missing:raise ValueError('Remote worker update not loaded; restart ComfyUI. Missing: '+', '.join(missing))
    graph=reachable_graph(graph,schemas)
    missing,weights=graph_readiness(graph,schemas)
    if missing:raise ValueError('Remote nodes missing; no generation submitted: '+', '.join(missing))
    for kind in ('MajoorSaveProjectInfo','MajoorSaveProjectMusic','MajoorEnergyReport'):
        if any(node['class_type']==kind for node in graph.values()) and not schemas.get(kind,{}).get('output'):
            raise ValueError('Remote VideoTools update not loaded: '+kind)
    if weights:raise ValueError('Remote models missing; no generation submitted: '+', '.join(sorted(set(weights))))
