"""Local hardware observations, without admitting a compute backend."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess


def inspect_hardware(*, probe_accelerators: bool = False) -> dict:
    process_count, count_source = None, 'unavailable'
    try:
        if hasattr(os, 'process_cpu_count'):
            process_count, count_source = os.process_cpu_count(), 'os.process_cpu_count'
        elif hasattr(os, 'sched_getaffinity'):
            process_count, count_source = len(os.sched_getaffinity(0)), 'os.sched_getaffinity'
    except OSError:
        count_source = 'unavailable'
    accelerators = {}
    for kind in ('metal', 'cuda'):
        row = {'probe_status': 'not_requested', 'devices': None}
        accelerators[kind] = row
        if not probe_accelerators:
            continue
        if kind == 'metal' and platform.system() != 'Darwin':
            row['probe_status'] = 'not_applicable'
            continue
        executable = shutil.which('system_profiler' if kind == 'metal' else 'nvidia-smi')
        if executable is None:
            row['probe_status'] = 'tool_unavailable'
            continue
        command = ([executable, 'SPDisplaysDataType', '-json'] if kind == 'metal' else
                   [executable, '--query-gpu=name', '--format=csv,noheader'])
        try:
            completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       timeout=3, check=False)
            if completed.returncode != 0:
                raise RuntimeError('hardware probe failed')
            if len(completed.stdout) > 65536:
                raise ValueError('hardware probe output exceeds 64 KB')
            output = completed.stdout.decode('utf-8')
            if kind == 'metal':
                displays = json.loads(output)['SPDisplaysDataType']
                if type(displays) is not list:
                    raise ValueError('unexpected display inventory')
                names = [display['sppci_model'] for display in displays]
            else:
                names = [line.strip() for line in output.splitlines() if line.strip()]
            if len(names) > 32 or any(type(name) is not str or not 1 <= len(name) <= 256 for name in names):
                raise ValueError('unexpected device names')
            row.update(probe_status='reported' if names else 'no_devices_reported', devices=names)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            row.update(probe_status='error', error_type=type(exc).__name__)
    return {
        'cpu': {'architecture': platform.machine(), 'description': platform.processor(),
                'logical_cpus': os.cpu_count(), 'process_logical_cpus': process_count,
                'process_count_source': count_source},
        'accelerators': accelerators,
        'polya_gpu_execution': 'not_implemented',
        'scope': 'OS/tool observations only, not compute verification or backend admission. '
                 'Unavailable probes mean unknown hardware. CPU counts do not establish a compute quota. '
                 'Optional probes have a 3-second timeout each and accept at most 64 KB of stdout; '
                 'only Apple display and NVIDIA device names are inspected.',
    }
