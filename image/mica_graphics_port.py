"""Construct an offline VirGL/Mesa + Cuttlefish minigbm guest vendor overlay."""
from pathlib import Path
import os,subprocess
R=Path(__file__).resolve().parents[1]
def apply(add,original):
 B=R/'experiments/mesa-android-build';O=R/'artifacts/graphics-port-review/mesa-runtime';O.mkdir(exist_ok=True)
 strip=os.path.join(os.environ.get('ANDROID_NDK',''),'toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-strip')  # only used without GOOGLEBOOK_GUEST_DIR
 mesa={'lib64/egl/libEGL_virgl.so':'src/egl/libEGL_virgl.so','lib64/egl/libGLESv1_CM_virgl.so':'src/mesa/glapi/es1api/libGLESv1_CM_virgl.so','lib64/egl/libGLESv2_virgl.so':'src/mesa/glapi/es2api/libGLESv2_virgl.so','lib64/libgallium_dri.so':'src/gallium/targets/dri/libgallium_dri.so','lib64/libdrm.so':'subprojects/libdrm-2.4.133/libdrm.so'}
 for n,p in mesa.items():
  # GOOGLEBOOK_GUEST_DIR: use already-stripped libraries from publish/build-guest.sh.
  if os.environ.get('GOOGLEBOOK_GUEST_DIR'):add(n,(Path(os.environ['GOOGLEBOOK_GUEST_DIR'])/'mesa-runtime'/Path(n).name).read_bytes(),'same_process_hal_file');continue
  out=O/Path(n).name;subprocess.run([strip,'--strip-unneeded','-o',str(out),str(B/p)],check=True);add(n,out.read_bytes(),'same_process_hal_file')
 donor=R/'artifacts/graphics-port-review/extracted'
 for n in ['libminigbm_gralloc.so','libminigbm_gralloc4_utils.so','android.hardware.graphics.allocator-V3-ndk.so','android.hardware.graphics.common-V7-ndk.so']:
  add('lib64/'+n,(donor/n).read_bytes(),'same_process_hal_file')
 add('lib64/hw/mapper.minigbm.so',(donor/'mapper.minigbm.so').read_bytes(),'same_process_hal_file')
 add('lib64/hw/gralloc.default.so',(donor/'gralloc.default.so').read_bytes(),'same_process_hal_file')
 # The stock compositor embeds Qualcomm SnapAlloc metadata readers.
 # Keep its service identity/policy; use AOSP's matching generic DRM implementation.
 composer=R/'artifacts/graphics-port-review/cf-composer'
 n='android.hardware.composer.hwc3-service.drm'
 add('bin/hw/'+n,(composer/n).read_bytes(),'hal_graphics_composer_default_exec',0o755)
 # A capability-bearing service's linker did not use LD_LIBRARY_PATH: its
 # tombstone proved it loaded the stock reporter, whose C++ ABI differs.
 # Replace that compositor-specific dependency at the actual search path.
 n='drm_hwcomposer_atom_reporter.so'
 add('lib64/'+n,(composer/n).read_bytes(),'same_process_hal_file')
 n='android.hardware.graphics.allocator-service.minigbm';add('bin/hw/'+n,(donor/n).read_bytes(),'hal_graphics_allocator_default_exec',0o755)
 add('etc/init/vendor.qti.hardware.display.allocator-service.rc',b'''# Disposable VM: AOSP minigbm replaces the physical Qualcomm allocator.
service vendor.graphics.allocator /vendor/bin/hw/android.hardware.graphics.allocator-service.minigbm
    class hal animation
    user system
    group graphics drmrpc
    capabilities SYS_NICE
    onrestart restart surfaceflinger
    task_profiles ServiceCapacityLow
''','vendor_configs_file')
 add('etc/vintf/manifest/vendor.qti.hardware.display.allocator-service.xml',b'''<manifest version="9.0" type="device"><hal format="aidl"><name>android.hardware.graphics.allocator</name><version>3</version><fqname>IAllocator/default</fqname></hal></manifest>\n''','vendor_configs_file')
 add('etc/vintf/manifest/mapper.qti.xml',b'''<manifest version="9.0" type="device"><hal format="native"><name>mapper</name><fqname>@5.0/minigbm</fqname></hal></manifest>\n''','vendor_configs_file')
 props={'ro.hardware.egl':'virgl','ro.hardware.vulkan':'none','ro.hwui.use_vulkan':'false','debug.renderengine.backend':'skiaglthreaded','debug.renderengine.vulkan':'false','debug.renderengine.graphite_desktop_optin':'false','debug.hwui.renderer':'skiagl','ro.gfx.angle.supported':'false','ro.vendor.hwcomposer.mode':'client','ro.surface_flinger.has_wide_color_display':'false','ro.surface_flinger.has_HDR_display':'false'}
 props['ro.vendor.hwc.drop_drm_master']='0'
 text=original('build.prop').decode();lines=[l for l in text.splitlines() if l.split('=',1)[0] not in props]
 lines += ['# Workspace-built Mesa VirGL and virtual buffer allocator.']+[k+'='+v for k,v in props.items()]
 add('build.prop',('\n'.join(lines)+'\n').encode(),'vendor_file',0o600)
 # Label only the emulated GPU's sysfs subtree using Google's existing GPU type.
 contexts=original('etc/selinux/vendor_file_contexts')+b'\n/dev/ttyAMA0 u:object_r:console_device:s0\n/sys/devices/platform/3f000000\\.pcie/pci0000:00/0000:00:01\\.0(/.*)? u:object_r:sysfs_gpu:s0\n'
 add('etc/selinux/vendor_file_contexts',contexts,'vendor_configs_file')
 add('etc/init/vm-graphics.rc',b'''# This path is the QEMU virtual GPU only, not host hardware.
on init
    restorecon_recursive /sys/devices/platform/3f000000.pcie/pci0000:00/0000:00:01.0
    start vm-gpu-state

service vm-gpu-state /system/bin/sh -c "ls -lZ /dev/dri /sys/class/drm; ls -lZ /sys/bus/pci/devices/0000:00:01.0/; cat /sys/bus/pci/devices/0000:00:01.0/uevent; getprop drm.gpu.vendor_name"
    disabled
    oneshot
    user shell
    group shell graphics log readproc
    seclabel u:r:shell:s0
    console ttyAMA0
''','vendor_configs_file')
