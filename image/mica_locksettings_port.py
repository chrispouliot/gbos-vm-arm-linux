"""Software Gatekeeper from AOSP, and no Weaver (the VM has no such hardware)."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def apply(add):
 # Preserve the official APEX's linker namespace, dependencies and file labels.
 p=R/'artifacts/security-port-review/com.android.hardware.gatekeeper.nonsecure.apex'
 add('apex/com.android.hardware.gatekeeper.nonsecure.apex',p.read_bytes(),'vendor_apex_file')
 add('etc/init/android.hardware.gatekeeper-service.trusty.rc',b'# Official software Gatekeeper APEX supplies this VM service.\n','vendor_configs_file')
 add('etc/vintf/manifest/android.hardware.gatekeeper-service.trusty.xml',b'<manifest version="9.0" type="device"/>\n','vendor_configs_file')
 # AOSP/Cuttlefish support Gatekeeper without optional Weaver hardware.
 # Advertising an absent Weaver caused waitForDeclaredService to hang.
 add('etc/vintf/manifest/android.hardware.weaver-service.android-desktop.xml',b'<manifest version="9.0" type="device"/>\n','vendor_configs_file')
 add('etc/init/android.hardware.weaver-service.android-desktop.rc',b'# No Weaver hardware in a VM.\n','vendor_configs_file')
