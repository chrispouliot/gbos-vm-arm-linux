#!/usr/bin/env python3
"""Reliability run: boot an image with the viewer attached, sample host resource use while the
guest does whatever it does (a --stress-test image drives itself), then shut down and report.

  soak.py WORK NAME SECONDS [--image DIR] [--persist]

Reports boot time, stress rounds completed, renderer worker deaths, rejected buffers, guest
crashes (known-absent hardware listed separately), and how file descriptors and memory of the
QEMU and renderer processes moved between the first and last sample.
"""
import json, os, re, signal, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
KNOWN = ('gscd', 'bluetooth', 'secretkeeper')  # hardware a VM does not have


def procs(work):
    """pid -> name for this folder's QEMU and its renderer processes."""
    out = {}
    lines = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,args='], text=True).splitlines()
    rows = [l.split(None, 2) for l in lines if len(l.split(None, 2)) == 3]
    qemu = [int(p) for p, _, a in rows if a.startswith(str(work / 'host/qemu-interop'))]
    for pid in qemu: out[pid] = 'qemu'
    known = set(qemu)
    for _ in range(3):
        for p, pp, a in rows:
            if int(pp) in known and int(p) not in known and 'virgl_render_server' in a:
                known.add(int(p)); out[int(p)] = 'renderer'
    return out


def sample(work):
    ps = procs(work); rss = {'qemu': 0, 'renderer': 0}; fds = {'qemu': 0, 'renderer': 0}
    for pid, name in ps.items():
        try:
            rss[name] += int(subprocess.check_output(['/bin/ps', '-o', 'rss=', '-p', str(pid)], text=True).strip() or 0)
            fds[name] += len(subprocess.run(['/usr/sbin/lsof', '-p', str(pid)], capture_output=True, text=True).stdout.splitlines())
        except (subprocess.CalledProcessError, ValueError):
            pass
    return {'renderers': sum(1 for n in ps.values() if n == 'renderer'), 'rss_mb': {k: v // 1024 for k, v in rss.items()}, 'fds': fds}


def main():
    work = Path(sys.argv[1]).resolve(); name = sys.argv[2]; seconds = int(sys.argv[3])
    image = sys.argv[sys.argv.index('--image') + 1] if '--image' in sys.argv else str(work / 'image')
    run = work / 'logs' / name
    cmd = [sys.executable, str(HERE / 'run/run_vm.py'), str(work), name, '--seconds', str(seconds + 120), '--image', image, '--no-audio']
    if '--persist' not in sys.argv: cmd.append('--snapshot')
    vm = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + 30
    while not (run / 'spice.sock').exists():
        if vm.poll() is not None or time.monotonic() > deadline: sys.exit('VM did not start')
        time.sleep(.2)
    env = dict(os.environ, VM_MOUSE_SEAMLESS='0', VM_MOUSE_RELATIVE='0', VM_INPUT_TOKEN=(run / 'token').read_text())
    viewer = subprocess.Popen([str(work / 'host/Googlebook VM.app/Contents/MacOS/GooglebookViewer'), str(run / 'spice.sock')],
                              env=env, stdout=(run / 'viewer.log').open('w'), stderr=subprocess.STDOUT, start_new_session=True)
    samples = []; start = time.monotonic()
    try:
        while time.monotonic() - start < seconds and vm.poll() is None:
            time.sleep(15)
            s = sample(work); s['t'] = round(time.monotonic() - start); samples.append(s)
            serial = (run / 'serial.log').read_bytes() if (run / 'serial.log').exists() else b''
            if b'VM_STRESS_END' in serial: break
    finally:
        if vm.poll() is None: os.killpg(vm.pid, signal.SIGTERM)
        try: vm.wait(timeout=60)
        except subprocess.TimeoutExpired: os.killpg(vm.pid, signal.SIGKILL)
        if viewer.poll() is None: os.killpg(viewer.pid, signal.SIGTERM)
    serial = (run / 'serial.log').read_text(errors='replace'); host = (run / 'host.log').read_text(errors='replace')
    crashes = re.findall(r'F DEBUG\s*:\s*Cmdline: (\S+)', serial)
    other = [c for c in crashes if not any(k in c for k in KNOWN)]
    boot = re.search(r'VM_BOOT_COMPLETED uptime=([0-9.]+)', serial)
    report = {
        'run': name, 'watched_seconds': round(time.monotonic() - start),
        'boot_seconds': float(boot.group(1)) if boot else None,
        'stress_rounds': len(re.findall(r'VM_STRESS round=', serial)), 'stress_finished': 'VM_STRESS_END' in serial,
        'renderer_worker_deaths': host.count(' DIED '), 'rejected_buffers': len(re.findall(r'rejected|unexportable|unexpected fd_type', host)),
        'system_server_crashes': serial.count('>>> system_server <<<'), 'surfaceflinger_crashes': serial.count('>>> /system/bin/surfaceflinger <<<'),
        'guest_crashes_other': sorted(set(other)), 'guest_crashes_known_absent_hardware': len(crashes) - len(other),
        'clean_poweroff': 'VM_CONTROL poweroff' in serial, 'exit': json.loads((run / 'result.json').read_text()) if (run / 'result.json').exists() else None,
        'first_sample': samples[0] if samples else None, 'last_sample': samples[-1] if samples else None,
    }
    (run / 'soak.json').write_text(json.dumps({'report': report, 'samples': samples}, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
