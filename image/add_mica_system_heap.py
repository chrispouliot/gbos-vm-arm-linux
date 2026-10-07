#!/usr/bin/env python3
"""Clone an existing disposable Mica variant and load the official CF heap driver."""
from pathlib import Path
import hashlib,json,shutil,stat,subprocess,sys
from cpio_tools import read,write
R=Path(__file__).resolve().parents[1]
source,target=sys.argv[1:3]
assert all(n.replace('-','').isalnum() for n in [source,target])
src=R/'artifacts/mica'/source;dst=R/'artifacts/mica'/target;dst.mkdir()
for p in src.iterdir():
 if p.name=='googlebook.raw':subprocess.run(['cp','-c',str(p),str(dst/p.name)],check=True)
 elif p.is_file():shutil.copyfile(p,dst/p.name)
data=subprocess.check_output(['lz4','-d','-c',str(src/'initrd.img')]);entries=read(data)
module=(R/'artifacts/cuttlefish-arm17/modules/system_heap.ko').read_bytes()
extra={'lib/modules/system_heap.ko':(stat.S_IFREG|0o644,module)}
for name in ['modules.load','modules.load.recovery']:
 mode,b=entries['lib/modules/'+name]
 extra['lib/modules/'+name]=(mode,b+b'system_heap.ko\n')
mode,b=entries['lib/modules/modules.dep']
extra['lib/modules/modules.dep']=(mode,b+b'\n/lib/modules/system_heap.ko:\n')
(dst/'initrd.img').write_bytes(subprocess.check_output(['lz4','-l','-c'],input=data+write(extra)))
(dst/'system-heap.json').write_text(json.dumps({'source_variant':source,'source':'official Cuttlefish build 16373615 vendor_dlkm','sha256':hashlib.sha256(module).hexdigest(),'module_checks':'unchanged','abi_evidence':'artifacts/mica/system-heap-abi.json'},indent=2)+'\n')
print(dst)
