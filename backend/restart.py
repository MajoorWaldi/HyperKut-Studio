"""Restart only this single-process uvicorn Studio; never manage ComfyUI."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def restart_command(argv=None):
    argv = list(sys.orig_argv if argv is None else argv)
    # A reload supervisor or worker manager must own its own restarts.
    if len(argv) < 4 or argv[1:3] != ['-m', 'uvicorn'] or argv[3] != 'backend.server:create_app':
        raise ValueError('Restart is available for the standard Studio launcher only')
    if any(a in ('--reload', '--workers', '-w', '--fd', '--uds') or a.startswith(('--workers=', '--fd=', '--uds=')) for a in argv):
        raise ValueError('Restart is unavailable with a supervisor or multiple workers')
    return [sys.executable, *argv[1:]]


def launch_restart(workspace):
    command = restart_command()
    logs = Path(workspace) / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    options = dict(cwd=Path(__file__).resolve().parents[1], stdin=subprocess.DEVNULL,
                   close_fds=True)
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options['start_new_session'] = True
    with (logs / 'studio-restart.log').open('ab') as log:
        subprocess.Popen([getattr(sys, '_base_executable', sys.executable), str(Path(__file__).resolve()), str(os.getpid()),
                          json.dumps(command), str(logs)], stdout=log, stderr=log, **options)


def main():
    pid, command, logs = int(sys.argv[1]), json.loads(sys.argv[2]), Path(sys.argv[3])
    if pid != os.getppid():
        raise RuntimeError('Restart target is not the helper parent')
    # Open a stable Windows process handle before waiting: no PID reuse hazard.
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x0001 | 0x00100000, False, pid)
        if not handle:
            raise OSError(ctypes.get_last_error(), 'Cannot open Studio process')
        try:
            time.sleep(.8)  # let the accepted response reach the browser
            if not kernel.TerminateProcess(handle, 0):
                raise OSError(ctypes.get_last_error(), 'Cannot stop Studio process')
            if kernel.WaitForSingleObject(handle, 15000) != 0:
                raise RuntimeError('Studio did not stop')
        finally:
            kernel.CloseHandle(handle)
    else:
        time.sleep(.8)
        os.kill(pid, signal.SIGTERM)
        for _ in range(150):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('Studio did not stop')
    with (logs / 'studio-out.log').open('ab') as out, (logs / 'studio-err.log').open('ab') as err:
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
        subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1], stdin=subprocess.DEVNULL,
                         stdout=out, stderr=err, close_fds=True, **options)


if __name__ == '__main__':
    main()
