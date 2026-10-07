#!/usr/bin/env python3
"""Build the viewer app.  build_viewer.py COCOASPICE_SRC UTM_FRAMEWORKS VIEWER_M OUT_DIR
Links the SPICE client libraries that ship inside the UTM app (nothing is copied out of it)."""
import plistlib, subprocess, sys
from pathlib import Path

src, frameworks, viewer_m, out = [Path(p).resolve() for p in sys.argv[1:5]]
S = src / 'Sources'
app = out / 'Googlebook Viewer.app/Contents'
build = out / 'viewer-build'
for p in (app / 'MacOS', app / 'Resources', build / 'modules', build / 'module-cache'):
    p.mkdir(parents=True, exist_ok=True)
(build / 'modules/module.modulemap').write_text(
    'module CocoaSpiceRenderer { umbrella "' + str(S / 'CocoaSpiceRenderer/include') + '" export * }\n')
shader = (S / 'CocoaSpiceRenderer/CSShaders.metal').read_text().replace(
    '#import "include/CSShaderTypes.h"', (S / 'CocoaSpiceRenderer/include/CSShaderTypes.h').read_text())
(app / 'Resources/VMShaders.metal').write_text(shader)
(app / 'Info.plist').write_bytes(plistlib.dumps({
    'CFBundleIdentifier': 'local.googlebook.viewer', 'CFBundleName': 'Googlebook',
    'CFBundleExecutable': 'GooglebookViewer', 'CFBundlePackageType': 'APPL', 'NSHighResolutionCapable': True}))
skip = {'CSUSBDevice.m', 'CSUSBManager.m', 'CSSession+Sharing.m', 'gst_ios_init.m'}
sources = [str(p) for p in sorted((S / 'CocoaSpice').glob('*.m')) if p.name not in skip]
sources += [str(S / 'CocoaSpiceRenderer/CSMetalRenderer.m'), str(viewer_m)]
cmd = ['clang', '-fobjc-arc', '-fblocks', '-fmodules', f'-fmodules-cache-path={build}/module-cache', '-O2',
       '-Wno-incomplete-implementation', '-w']
headers = S / 'CocoaSpice/ExternalHeaders'
for p in [build / 'modules', S / 'CocoaSpice/include', S / 'CocoaSpice', S / 'CocoaSpiceRenderer/include',
          S / 'CocoaSpiceRenderer', headers, *[headers / n for n in ('glib-2.0', 'gstreamer-1.0', 'spice-1', 'spice-client-glib-2.0')]]:
    cmd += ['-I', str(p)]
cmd += sources
for n in ('AppKit', 'Metal', 'MetalKit', 'CoreGraphics', 'CoreImage', 'IOSurface', 'CoreVideo'):
    cmd += ['-framework', n]
for n in ('spice-client-glib-2.0.8', 'glib-2.0.0', 'gobject-2.0.0', 'gio-2.0.0', 'gstreamer-1.0.0'):
    cmd.append(str(frameworks / (n + '.framework') / n))
cmd += ['-Wl,-rpath,' + str(frameworks), '-o', str(app / 'MacOS/GooglebookViewer')]
subprocess.run(cmd, check=True)
subprocess.run(['codesign', '--force', '--sign', '-', str(app.parent)], check=True, capture_output=True)
print(app.parent)
