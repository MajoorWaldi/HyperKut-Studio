"""Experimental CPU snapshot transport nodes; no H3 graph integration yet."""
import json
import hashlib
import os
import re
import shutil
import stat
import uuid
from dataclasses import replace
from pathlib import Path

import folder_paths
from comfy_api.latest import ComfyExtension, io
from filelock import FileLock

from .runtime.studio.backend.project_snapshot import read_json
from .runtime.studio.backend.snapshot_worker import transform_snapshot, publish_snapshot
from .runtime.studio.backend.artifact_bundle import read_bundle
from .runtime.studio.backend.artifact_store import LocalArtifactStore
from .runtime.studio.backend.project_snapshot import materialize_snapshot, capture_project
from .runtime.studio.backend.snapshot_schema import shot_list

_CONTEXTS={}

def _operation_id(operation_id):
    if not isinstance(operation_id,str) or not re.fullmatch(r'[0-9a-f]{32}',operation_id):
        raise ValueError('Invalid workspace operation id')
    return operation_id


def _private_root(name, directory):
    root=Path(directory).absolute()/name
    for path in (root,*root.parents):
        if os.path.lexists(path):
            info=path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                raise ValueError('Worker paths cannot contain reparse points')
    root.mkdir(parents=True,exist_ok=True)
    return root


def _retention(timeout=-1):
    root=_private_root('_hyperkut_retention',folder_paths.get_output_directory())
    return root,FileLock(str(root/'.retention.lock'),timeout=timeout)


def _save_record(root, record):
    path=root/f"{_operation_id(record['operation_id'])}.json"
    temporary=path.with_suffix('.partial')
    try:
        with temporary.open('w',encoding='utf-8') as stream:
            json.dump(record,stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_record(root,operation_id):
    path=root/f'{_operation_id(operation_id)}.json'
    if not path.exists():
        return None
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
        raise ValueError('Invalid worker retention record')
    record=read_json(path.read_bytes())
    if record.get('operation_id')!=operation_id or record.get('state') not in ('active','completed'):
        raise ValueError('Invalid worker retention record')
    return record


def _file_identity(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
        raise ValueError('Worker artifact must be a regular file')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(64*1024):digest.update(chunk)
    return {'size_bytes':info.st_size,'sha256':digest.hexdigest()}


def _upload_record(source):
    base=Path(folder_paths.get_input_directory()).resolve()
    return {'path':source.relative_to(base).as_posix(),**_file_identity(source)}


def _complete_record(root,record,bundle,descriptor):
    try:
        record={**record,'state':'completed','published':[
            {'path':path.name,**_file_identity(path)} for path in (bundle,descriptor)]}
        _save_record(root,record)
    except BaseException:
        bundle.unlink(missing_ok=True)
        descriptor.unlink(missing_ok=True)
        raise


def release_operation(operation_id, *, acknowledged=False):
    """Release only completed operations; outputs require durable client acknowledgement."""
    _operation_id(operation_id)
    if type(acknowledged) is not bool:raise ValueError('Acknowledgement must be a boolean')
    retention,lock=_retention(timeout=0)
    with lock:
        record=_load_record(retention,operation_id)
        if record is not None and record['state']!='completed':
            raise ValueError('Cannot release an active worker operation')
        if acknowledged and record is None:
            # Acknowledged release is idempotent, including after worker restart.
            return {'removed_bytes':0,'removed_files':0}
        root=None
        base=_private_root('_hyperkut_workspaces',folder_paths.get_output_directory())
        if os.path.lexists(base/operation_id):
            root=workspace(operation_id)
        elif record is None:
            raise ValueError('Unknown worker workspace')
        candidates=[]
        if acknowledged:
            output=_private_root('hyperkut_artifacts',folder_paths.get_output_directory())
            for entry in record.get('published',[]):
                if not re.fullmatch(r'[0-9a-f]{32}\.(snapshot\.zip|descriptor\.json)',entry['path']):
                    raise ValueError('Invalid published artifact ownership')
                candidates.append((output/entry['path'],entry))
            upload=record.get('upload')
            if upload:
                # Another operation, including a completed but unacknowledged one,
                # may still need the same uploaded bundle.
                shared=False
                for path in retention.glob('*.json'):
                    other=_load_record(retention,path.stem)
                    if other['operation_id']!=operation_id and other.get('upload',{}).get('path')==upload['path']:
                        shared=True
                if not shared:
                    base=Path(folder_paths.get_input_directory()).resolve()
                    path=base/upload['path']
                    if not path.resolve().is_relative_to(base):
                        raise ValueError('Upload escapes worker input directory')
                    candidates.append((path,upload))
        # Validate all identities before deleting anything. Never remove replaced
        # uploads, even if an old receipt has the same input filename.
        existing=[]
        for path,entry in candidates:
            if os.path.lexists(path):
                if _file_identity(path)!={key:entry[key] for key in ('size_bytes','sha256')}:
                    raise ValueError('Worker artifact changed since publication')
                existing.append((path,entry))
        manager=_CONTEXTS.pop(operation_id,None)
        if manager is not None:manager.__exit__(None,None,None)
        result={'removed_bytes':0,'removed_files':0}
        for path,entry in existing:
            path.unlink()
            result['removed_bytes']+=entry['size_bytes']
            result['removed_files']+=1
        if root is not None:
            shutil.rmtree(root)
        if acknowledged:
            (retention/f'{operation_id}.json').unlink()
        return result


def workspace(operation_id, create=False):
    _operation_id(operation_id)
    base=_private_root('_hyperkut_workspaces',folder_paths.get_output_directory())
    base.mkdir(parents=True,exist_ok=True)
    if os.path.lexists(base/operation_id) and (base/operation_id).resolve()!=base/operation_id:
        raise ValueError('Workspace cannot be a reparse point')
    path=(base/operation_id).resolve()
    if path.parent!=base:raise ValueError('Workspace escapes private root')
    if create:
        if len(list(base.iterdir()))>=64:raise ValueError('Worker workspace quota reached; release completed operations')
        if shutil.disk_usage(base).free<512*1024**2:raise ValueError('Insufficient worker scratch space')
        path.mkdir()
        (path/'owner.json').write_text(json.dumps({'operation_id':operation_id}))
        (path/'projects').mkdir()
    elif not (path/'owner.json').is_file() or read_json((path/'owner.json').read_bytes()).get('operation_id')!=operation_id:
        raise ValueError('Unknown worker workspace')
    return path

class HyperKutWorkspace(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='HyperKutWorkspace',display_name='Private Worker Workspace',category='HyperKut/Experimental',
                         inputs=[io.String.Input('operation_id')],outputs=[io.String.Output(display_name='project_root')])
    @classmethod
    def fingerprint_inputs(cls,**kwargs):return float('nan')
    @classmethod
    def execute(cls,operation_id):
        retention,lock=_retention()
        with lock:
            if _load_record(retention,operation_id) is not None:raise ValueError('Worker operation already exists')
            root=workspace(operation_id,True)
            _save_record(retention,{'operation_id':operation_id,'state':'active'})
        return io.NodeOutput(str(root/'projects'))

class HyperKutSnapshotImport(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='HyperKutSnapshotImport',display_name='Import Project Snapshot',category='HyperKut/Experimental',
                         inputs=[io.String.Input('archive'),io.String.Input('operation_id')],
                         outputs=[io.Custom('MAJOOR_SHOT_LIST').Output(display_name='shot_list')])
    @classmethod
    def fingerprint_inputs(cls,**kwargs):return float('nan')
    @classmethod
    def execute(cls,archive,operation_id):
        source=Path(folder_paths.get_annotated_filepath(archive)).resolve()
        if not source.is_relative_to(Path(folder_paths.get_input_directory()).resolve()):raise ValueError('Archive must be an uploaded input')
        retention,lock=_retention()
        with lock:
            if _load_record(retention,operation_id) is not None:raise ValueError('Worker operation already exists')
            root=workspace(operation_id,True)
            _save_record(retention,{'operation_id':operation_id,'state':'active','upload':_upload_record(source)})
            store=LocalArtifactStore(root/'cache')
            with source.open('rb') as stream:snapshot=read_bundle(store,stream)
            manager=materialize_snapshot(store,snapshot,root/'projects')
            project=manager.__enter__()
            _CONTEXTS[operation_id]=manager
            manifest=read_json((project/'manifest.json').read_bytes())
        return io.NodeOutput(replace(shot_list(manifest),storage_root=project.parent))

class HyperKutSnapshotExport(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='HyperKutSnapshotExport',display_name='Export Project Snapshot',category='HyperKut/Experimental',is_output_node=True,
            inputs=[io.Custom('MAJOOR_SHOT_LIST').Input('shot_list'),io.String.Input('operation_id'),
                    io.Audio.Input('after_audio',optional=True),io.Video.Input('after_video',optional=True),io.Boolean.Input('after_report',optional=True)],outputs=[])
    @classmethod
    def execute(cls,shot_list,operation_id,after_audio=None,after_video=None,after_report=None):
        retention,lock=_retention()
        with lock:
            record=_load_record(retention,operation_id)
            if record is None or record['state']!='active':raise ValueError('Worker operation is not active')
            root=workspace(operation_id)
            project=Path(shot_list.storage_root)/shot_list.project_id
            if not project.resolve().is_relative_to(root.resolve()):raise ValueError('Project belongs to another workspace')
            extras=[]
            for folder in ('exports','manifests','logs/plate_checks','editor'):
                for path in (project/folder).rglob('*'):
                    if path.is_file() and not path.name.endswith(('.lock','.tmp','.partial')):extras.append(path.relative_to(project).as_posix())
            store=LocalArtifactStore(root/'cache')
            snapshot=capture_project(store,project,extra_paths=extras)
            output=_private_root('hyperkut_artifacts',folder_paths.get_output_directory())
            bundle,descriptor=publish_snapshot(store,snapshot,output)
            _complete_record(retention,record,bundle,descriptor)
        return io.NodeOutput(ui={'files':[{'filename':p.name,'subfolder':'hyperkut_artifacts','type':'output'} for p in (bundle,descriptor)]})

class HyperKutWorkspaceRelease(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='HyperKutWorkspaceRelease',display_name='Release Completed Workspace',category='HyperKut/Experimental',is_output_node=True,
                         inputs=[io.String.Input('operation_id'),io.Boolean.Input('acknowledged',default=False,optional=True)],outputs=[])
    @classmethod
    def fingerprint_inputs(cls,**kwargs):return float('nan')
    @classmethod
    def execute(cls,operation_id,acknowledged=False):
        result=release_operation(operation_id,acknowledged=acknowledged)
        return io.NodeOutput(ui={'text':[json.dumps(result)]})


class HyperKutSnapshotTransform(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='HyperKutSnapshotTransform', display_name='Snapshot Transport (Experimental)',
            category='HyperKut/Experimental', is_output_node=True,
            inputs=[io.String.Input('archive'), io.String.Input('operation_json'),
                    io.String.Input('operation_id',default='',optional=True)],
            outputs=[io.String.Output(display_name='snapshot_json')])

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float('nan')

    @classmethod
    def execute(cls, archive, operation_json, operation_id=''):
        path = Path(folder_paths.get_annotated_filepath(archive)).resolve()
        if not path.is_relative_to(Path(folder_paths.get_input_directory()).resolve()) or not path.is_file():
            raise ValueError('Snapshot archive must be an uploaded input')
        operation = read_json(operation_json.encode('utf-8'))
        operation_id=operation_id or uuid.uuid4().hex
        retention,lock=_retention()
        with lock:
            if _load_record(retention,operation_id) is not None:raise ValueError('Worker operation already exists')
            record={'operation_id':operation_id,'state':'active','upload':_upload_record(path)}
            _save_record(retention,record)
            output=_private_root('hyperkut_artifacts',folder_paths.get_output_directory())
            with path.open('rb') as source:
                snapshot, bundle, descriptor = transform_snapshot(source, output, operation)
            _complete_record(retention,record,bundle,descriptor)
        return io.NodeOutput(json.dumps(snapshot.to_dict()), ui={'text':[operation_id],'files':[
            {'filename':p.name,'subfolder':'hyperkut_artifacts','type':'output'} for p in (bundle, descriptor)]})


class HyperKutSnapshotCapabilities(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='HyperKutSnapshotCapabilities', display_name='Snapshot Capabilities (Experimental)',
            category='HyperKut/Experimental', is_output_node=True, inputs=[], outputs=[])

    @classmethod
    def execute(cls):
        output = Path(folder_paths.get_output_directory()) / 'hyperkut_artifacts'
        output.mkdir(parents=True, exist_ok=True)
        path = output/'capabilities.json'
        path.write_text(json.dumps({'protocol':1,'outputs':'file','operations':['verify','set_prompt'],
                                    'generation':False,'graph_transport':2,'isolated_workspace':True}), encoding='utf-8')
        return io.NodeOutput(ui={'files':[{'filename':path.name,'subfolder':'hyperkut_artifacts','type':'output'}]})


class SnapshotExtension(ComfyExtension):
    async def get_node_list(self):
        return [HyperKutSnapshotTransform, HyperKutSnapshotCapabilities, HyperKutWorkspace, HyperKutSnapshotImport, HyperKutSnapshotExport, HyperKutWorkspaceRelease]


async def comfy_entrypoint():
    return SnapshotExtension()
