"""Official Cuttlefish audio APEX and its matching virtual-device configuration."""
from pathlib import Path
import subprocess
R=Path(__file__).resolve().parents[1]
def apply(add):
 p=R/'artifacts/security-port-review/com.android.hardware.audio.apex'
 add('apex/com.android.hardware.audio.apex',p.read_bytes(),'vendor_apex_file')
 # The new official APEX owns this interface; remove the duplicate declaration.
 add('etc/vintf/manifest/bluetooth_audio.xml',b'<manifest version="1.0" type="device"/>\n','vendor_configs_file')
 # No Qualcomm hotword DSP exists in the VM. An advertised but absent AIDL
 # sound-trigger service makes system_server wait forever (watchdog evidence).
 add('etc/vintf/manifest/soundtrigger.qti.xml',b'<manifest version="1.0" type="device"/>\n','vendor_configs_file')
 names=['audio_effects.xml','audio_effects_config.xml','audio_policy_configuration.xml','audio_policy_volumes.xml','default_volume_tables.xml','bluetooth_with_le_audio_policy_configuration_7_0.xml','primary_audio_policy_configuration.xml','r_submix_audio_policy_configuration.xml','surround_sound_configuration_5_0.xml','usb_audio_policy_configuration.xml']
 for n in names:
  b=(R/'artifacts/cuttlefish-audio-config'/n).read_bytes();assert b.startswith(b'<?xml') or b.startswith(b'<!--'),n
  add('etc/'+n,b,'vendor_configs_file')
