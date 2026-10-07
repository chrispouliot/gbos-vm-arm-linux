#!/usr/bin/env python3
"""Give a disposable workspace clone a fresh 16 GiB userdata partition.
Preserves all original partition contents; moves only userdata's GPT mapping to
new sparse space beyond the old image and relocates the backup GPT. Android
formats/encrypts the fresh area normally. Never accepts the original image.
"""
import hashlib,json,struct,sys,zlib
from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=Path(sys.argv[1]).resolve()
assert p.name=='googlebook.raw' and p.parent.parent==R/'artifacts/mica'
assert not (p.parent/'userdata-expansion.json').exists()
with p.open('r+b') as f:
 oldsize=p.stat().st_size
 f.seek(512);h=bytearray(f.read(512));assert h[:8]==b'EFI PART'
 hs=struct.unpack_from('<I',h,12)[0];saved=struct.unpack_from('<I',h,16)[0]
 struct.pack_into('<I',h,16,0);assert zlib.crc32(h[:hs])==saved
 entries_lba,n,es,crc=struct.unpack_from('<QIII',h,72)
 assert entries_lba==2 and es==128 and n==128
 f.seek(entries_lba*512);entries=bytearray(f.read(n*es));assert zlib.crc32(entries)==crc
 oldbackup=struct.unpack_from('<Q',h,32)[0]
 f.seek(oldbackup*512);bh=bytearray(f.read(512));assert bh[:8]==b'EFI PART'
 blba=struct.unpack_from('<Q',bh,72)[0];f.seek(blba*512);assert f.read(n*es)==entries
 targets=[i for i in range(n) if entries[i*es+56:(i+1)*es].decode('utf-16le').rstrip('\0')=='userdata'];assert len(targets)==1
 i=targets[0];oldrange=struct.unpack_from('<QQ',entries,i*es+32)
 start=(oldsize+1048575)//1048576*2048;size=16*1024**3//512;end=start+size-1
 backup_entries=end+1;newlast=backup_entries+n*es//512
 for k in range(n):
  if k==i or not any(entries[k*es:k*es+16]):continue
  a,b=struct.unpack_from('<QQ',entries,k*es+32);assert b<start
 struct.pack_into('<QQ',entries,i*es+32,start,end)
 struct.pack_into('<Q',h,32,newlast);struct.pack_into('<Q',h,48,end)
 struct.pack_into('<I',h,88,zlib.crc32(entries))
 def checksum(header):
  struct.pack_into('<I',header,16,0);struct.pack_into('<I',header,16,zlib.crc32(header[:hs]));return header
 checksum(h);bh=bytearray(h)
 struct.pack_into('<QQ',bh,24,newlast,1);struct.pack_into('<Q',bh,72,backup_entries);checksum(bh)
 f.truncate((newlast+1)*512)
 f.seek(512);f.write(h);f.seek(1024);f.write(entries)
 f.seek(backup_entries*512);f.write(entries);f.write(bh)
 f.seek(446);mbr=bytearray(f.read(16));assert mbr[4]==0xee
 struct.pack_into('<I',mbr,12,min(newlast,0xffffffff));f.seek(446);f.write(mbr)
 f.flush()
 for lba,expected in [(1,h),(newlast,bh)]:
  f.seek(lba*512);assert f.read(512)==expected
 f.seek(start*512);assert f.read(4096)==bytes(4096)
report={'image':str(p),'old_size':oldsize,'new_size':p.stat().st_size,'old_userdata_lbas':oldrange,'fresh_userdata_lbas':[start,end],'userdata_bytes':size*512,'partition_table_sha256':hashlib.sha256(entries).hexdigest(),'preserved':'All other partition mappings and original partition contents; original source image untouched'}
(p.parent/'userdata-expansion.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
