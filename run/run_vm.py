#!/usr/bin/env python3
"""Run the Googlebook VM once with an explicit QEMU command line.

  run_vm.py WORK RUN_NAME [--seconds N] [--snapshot] [--offline] [--no-audio]
            [--display WxH] [--memory MIB] [--cpus N]

WORK is the build folder (host/, image/, UTM-beta/). Logs and sockets go to WORK/logs/RUN_NAME.
On Linux, QEMU comes from PATH (KVM, virglrenderer Venus, a GTK/SDL GL window, PipeWire audio)
and --ui picks the window (gtk or sdl).
The disk is written to unless --snapshot is given. Networking is QEMU user-mode NAT with no
inbound forwards; --offline removes it (the pointer/clipboard helper then cannot connect).
On stop, Android is asked to power off through the guest control channel before QEMU is killed.
"""
import argparse, fcntl, json, os, secrets, shutil, signal, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vm_control

# Kernel command line for the pinned image (mica-user 16471258). The vbmeta values describe the
# original, unmodified vbmeta partition of that image.
CMDLINE = ('console=ttyAMA0,115200 earlycon=pl011,0x9000000 panic=0 root=/dev/ram0 '
           'androidboot.hardware=android-desktop androidboot.hardware.platform=android-desktop '
           'androidboot.slot_suffix=_a androidboot.boot_devices=3f000000.pcie androidboot.vbmeta.size=7680 '
           'androidboot.vbmeta.hash_alg=sha256 '
           'androidboot.vbmeta.digest=9118d58c024a0b43fef17a1dcdf6b999b5ea9cbc053fd4377d5d78c445b15692 '
           'androidboot.vbmeta.device_state=unlocked androidboot.verifiedbootstate=orange '
           'androidboot.veritymode=enforcing printk.devkmsg=on '
           'androidboot.vendor.apex.com.android.hardware.keymint.strongbox.desktop=none '
           'androidboot.vendor.apex.com.android.hardware.audio.desktop=none loglevel=3')


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('work'); a.add_argument('name')
    a.add_argument('--seconds', type=int, default=3600)
    a.add_argument('--snapshot', action='store_true'); a.add_argument('--offline', action='store_true')
    a.add_argument('--no-audio', action='store_true')
    a.add_argument('--display', default='1920x1200'); a.add_argument('--memory', type=int, default=4096)
    a.add_argument('--cpus', type=int, default=6)
    a.add_argument('--image', help='image folder (default WORK/image)')
    a.add_argument('--ui', default='gtk', choices=('gtk', 'sdl'), help='Linux only: QEMU window')
    a.add_argument('--fullscreen', action='store_true', help='Linux only: start the window full screen')
    a.add_argument('--vulkan', action='store_true',
                   help='Linux only: image built with GBOS_VULKAN=1 (Venus); share gralloc buffers through GBM')
    args = a.parse_args()
    linux = sys.platform.startswith('linux')
    work = Path(args.work).resolve()
    assert args.name.replace('-', '').replace('_', '').isalnum() and 10 <= args.seconds <= 86400
    image = Path(args.image).resolve() if args.image else work / 'image'
    host, utm = work / 'host', work / 'UTM-beta/UTM.app'
    needed = (image / 'googlebook.raw', image / 'initrd.img', image / 'kernel.Image')
    if linux:
        if not shutil.which('qemu-system-aarch64'): sys.exit('missing: qemu-system-aarch64 (run inside nix develop)')
    else:
        needed += (host / 'qemu-interop', host / 'qemu-aarch64-softmmu', host / 'virgl_render_server', utm / 'Contents/Frameworks')
    for p in needed:
        if not p.exists(): sys.exit(f'missing: {p}')
    width, height = args.display.split('x')
    (work / 'logs').mkdir(exist_ok=True)
    lock = (work / 'logs/vm.lock').open('a')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: sys.exit('another VM from this folder is already running')
    out = work / 'logs' / args.name; out.mkdir()
    # Random per-boot secret for the pointer/clipboard link (see guest/input).
    token = secrets.token_hex(16)
    (out / 'token').write_text(token); os.chmod(out / 'token', 0o600)

    cmd = [str(host / 'qemu-interop'), '-L', str(utm / 'Contents/Resources/qemu'), '-nodefaults', '-vga', 'none',
           '-nic', 'none', '-device', 'virtio-gpu-gl-pci,hostmem=8G,blob=true,venus=true',
           '-global', f'virtio-gpu-gl-pci.xres={width}', '-global', f'virtio-gpu-gl-pci.yres={height}',
           '-cpu', 'host', '-smp', f'cpus={args.cpus},sockets=1,cores={args.cpus},threads=1',
           '-machine', 'virt,gic-version=3,highmem=on,highmem-ecam=off', '-accel', 'hvf,ipa-granule-size=0x1000',
           '-m', str(args.memory), '-audio', 'none',
           '-kernel', str(image / 'kernel.Image'), '-initrd', str(image / 'initrd.img'), '-append', CMDLINE + ' androidboot.gbos_token=' + token,
           '-drive', f'if=none,media=disk,id=driveimage,format=raw,file={image / "googlebook.raw"}',
           '-device', 'virtio-blk-pci,drive=driveimage', '-device', 'virtio-serial', '-no-reboot',
           '-device', 'qemu-xhci,id=xhci,addr=0x5', '-device', 'usb-kbd,id=keyboard,bus=xhci.0',
           '-device', 'usb-mouse,id=mouse,bus=xhci.0',
           '-display', 'none',
           '-spice', 'unix=on,addr=spice.sock,disable-ticketing=on,disable-copy-paste=on,disable-agent-file-xfer=on,gl=es',
           '-chardev', 'socket,id=serial0,path=serial.sock,server=on,wait=off,logfile=serial.log',
           '-serial', 'chardev:serial0', '-qmp', 'unix:qmp.sock,server=on,wait=off']
    if linux: cmd = linux_command(args, image, token, width, height)
    if args.snapshot: cmd.append('-snapshot')
    if not args.offline:
        cmd += ['-netdev', 'user,id=googlebooknet,ipv6=off',
                '-device', 'usb-net,id=ethernet,netdev=googlebooknet,bus=xhci.0,mac=52:54:00:12:34:56']
    if not args.no_audio:
        backend = 'pipewire' if linux else 'coreaudio'
        cmd += ['-audiodev', f'{backend},id=audio0', '-device', 'usb-audio,audiodev=audio0,bus=xhci.0']
    env = dict(os.environ) if linux else dict(os.environ, VM_QEMU_LIBRARY=str(host / 'qemu-aarch64-softmmu'),
               DYLD_FRAMEWORK_PATH=str(utm / 'Contents/Frameworks'),
               RENDER_SERVER_EXEC_PATH=str(host / 'virgl_render_server'),
               VK_DRIVER_FILES=str(utm / 'Contents/Resources/vulkan/icd.d/MoltenVK_icd.json'),
               ANGLE_DEFAULT_PLATFORM='metal', XDG_RUNTIME_DIR=str(out), TMPDIR=str(out))
    env.pop('APP_SANDBOX_GROUP_ID', None)
    if linux:
        env['TMPDIR'] = str(out)
        # QEMU's GTK pointer grab needs X11; under Wayland the mouse is never captured.
        if args.ui == 'gtk': env.setdefault('GDK_BACKEND', 'x11')
        # vrend allocates Venus-shareable (GBM, dma-buf) buffers only with this set.
        if args.vulkan: env['VIRGL_GBM_LAYOUT_FORCE_ENABLE'] = '1'
    (out / 'command.json').write_text(json.dumps({'command': cmd, 'seconds': args.seconds}, indent=2))
    with (out / 'host.log').open('wb') as log:
        proc = subprocess.Popen(cmd, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        print('PID', proc.pid, 'logs', out, flush=True)
        def interrupt(signum, frame): raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, interrupt)
        rc = None
        try: rc = proc.wait(timeout=args.seconds)
        except (subprocess.TimeoutExpired, KeyboardInterrupt): pass
        finally:
            if proc.poll() is None:
                try:
                    vm_control.send(out, 'VM_POWEROFF'); rc = proc.wait(timeout=30)
                except Exception: pass
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try: rc = proc.wait(timeout=8)
                except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL); rc = proc.wait()
        (out / 'result.json').write_text(json.dumps({'exit_code': rc}))
        print('exit', rc, flush=True)


def linux_command(args, image, token, width, height):
    """Same machine as the Mac launcher, on stock QEMU: KVM (TCG if /dev/kvm is unusable), guest RAM
    in a shared memfd so Venus blob resources can be dma-buf'd to the host GPU, and QEMU's own GL
    window instead of SPICE + the Cocoa viewer. Mouse is captured (click to grab, Ctrl+Alt+G to release)."""
    kvm = os.access('/dev/kvm', os.R_OK | os.W_OK)
    if not kvm: print('warning: /dev/kvm not usable, using TCG (expect a very slow boot)', file=sys.stderr, flush=True)
    accel = ['-accel', 'kvm', '-cpu', 'host'] if kvm else \
            ['-accel', 'tcg,thread=multi,tb-size=1024', '-cpu', 'max,pauth-impdef=on']
    # Closing the window must not yank power: shut down from Android or Ctrl+C the launcher.
    # zoom-to-fit: QEMU sizes the window from its placeholder, not the guest's GL scanout, so
    # launch.py resizes the window (xdotool) and the guest is scaled into it.
    ui = ('gtk,gl=on,zoom-to-fit=on,show-menubar=off' if args.ui == 'gtk' else 'sdl,gl=on') + ',window-close=off'
    return ['qemu-system-aarch64', '-name', 'Googlebook', '-nodefaults', '-vga', 'none', '-nic', 'none',
            '-machine', 'virt,gic-version=3,highmem=on,highmem-ecam=off,memory-backend=ram0',
            '-object', f'memory-backend-memfd,id=ram0,size={args.memory}M,share=on',
            *accel, '-m', str(args.memory), '-smp', f'cpus={args.cpus},sockets=1,cores={args.cpus},threads=1',
            '-device', f'virtio-gpu-gl-pci,hostmem=8G,blob=true,venus=true,xres={width},yres={height}',
            '-display', ui, *(['-full-screen'] if args.fullscreen else []),
            '-kernel', str(image / 'kernel.Image'), '-initrd', str(image / 'initrd.img'),
            '-append', CMDLINE + ' androidboot.gbos_token=' + token,
            '-drive', f'if=none,media=disk,id=driveimage,format=raw,file={image / "googlebook.raw"}',
            '-device', 'virtio-blk-pci,drive=driveimage', '-device', 'virtio-serial', '-no-reboot',
            '-device', 'qemu-xhci,id=xhci,addr=0x5', '-device', 'usb-kbd,id=keyboard,bus=xhci.0',
            '-device', 'usb-mouse,id=mouse,bus=xhci.0',
            '-chardev', 'socket,id=serial0,path=serial.sock,server=on,wait=off,logfile=serial.log',
            '-serial', 'chardev:serial0', '-qmp', 'unix:qmp.sock,server=on,wait=off']


if __name__ == '__main__':
    main()
