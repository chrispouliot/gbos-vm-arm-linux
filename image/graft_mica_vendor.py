#!/usr/bin/env python3
"""Replace only the vendor partition of a persistent Mica image with the one
from a freshly built variant, keeping userdata. Usage: graft_mica_vendor.py PERSISTENT NEW
Requires identical vendor offset and partition size, so the super metadata stays valid.
Keeps one copy-on-write backup (googlebook.raw.before-graft)."""
import json,shutil,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
dst,src=[R/'artifacts/mica'/n for n in sys.argv[1:3]]
assert (dst/'persistent.json').is_file() and (src/'vendor.erofs').is_file()
assert not any(c.strip().endswith('qemu-interop') for c in subprocess.check_output(['/bin/ps','-axo','comm='],text=True).splitlines()),'stop the VM first'
a,b=[json.loads((d/'relocation.json').read_text()) for d in (dst,src)]
assert (a['vendor_offset'],a['vendor_partition_bytes'])==(b['vendor_offset'],b['vendor_partition_bytes']),(a,b)
vendor=(src/'vendor.erofs').read_bytes();assert len(vendor)==a['vendor_partition_bytes']
backup=dst/'googlebook.raw.before-graft';backup.unlink(missing_ok=True)
subprocess.run(['cp','-c',str(dst/'googlebook.raw'),str(backup)],check=True)
with (dst/'googlebook.raw').open('r+b') as f:f.seek(a['vendor_offset']);f.write(vendor)
for n in ('vendor.erofs','overlay.tar','manifest.json'):shutil.copyfile(src/n,dst/n)
print('grafted vendor from',src.name,'into',dst.name)
