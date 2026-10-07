"""Relocate vendor_a into unused space in the super partition of a cloned image.
AOSP LpMetadata format; validates hashes, bounds and all original extent ranges.
"""
from pathlib import Path
import hashlib,json,struct
R=Path(__file__).resolve().parents[1]
u=lambda b,o:struct.unpack_from('<I',b,o)[0]
def relocate(image,vendor):
 image=Path(image).resolve();assert image.is_relative_to(R/'artifacts/mica') and image.name=='googlebook.raw'
 base,end=json.loads((R/'artifacts/mica/outer_gpt.json').read_text())['super']
 records=[];ranges=[]
 with image.open('r+b') as f:
  f.seek(base+4096);g=f.read(4096);gg=bytearray(g[:u(g,4)]);gg[8:40]=bytes(32);assert hashlib.sha256(gg).digest()==g[8:40]
  sz,count,bs=struct.unpack_from('<III',g,40)
  for slot in range(count*2):
   pos=base+12288+slot*sz;f.seek(pos);m=bytearray(f.read(sz));assert u(m,0)==0x414c5030
   hs=u(m,8);h=bytearray(m[:hs]);h[12:44]=bytes(32);assert hashlib.sha256(h).digest()==m[12:44]
   assert hashlib.sha256(m[hs:hs+u(m,44)]).digest()==m[48:80]
   po,pc,ps=struct.unpack_from('<III',m,80);eo,ec,es=struct.unpack_from('<III',m,92)
   for i in range(ec):
    n,k,t,s=struct.unpack_from('<QIQI',m,hs+eo+i*es);assert k==0 and s==0
    if n:ranges.append((base+t*512,base+(t+n)*512))
   found=[]
   for i in range(pc):
    p=hs+po+i*ps
    if m[p:p+36].split(b'\0')[0]==b'vendor_a':
     first,num=struct.unpack_from('<II',m,p+40);assert num==1;found.append(hs+eo+first*es)
   assert len(found)==1;records.append((pos,m,hs,found[0]))
  align=1024*1024;start=(max(e for s,e in ranges)+align-1)//align*align
  length=(vendor.stat().st_size+bs-1)//bs*bs
  assert base<start and start+length<=end
  assert all(start>=e or start+length<=s for s,e in ranges)
  # Copy data first, then update each metadata slot and its backup.
  f.seek(start)
  with vendor.open('rb') as v:
   while chunk:=v.read(1024*1024):f.write(chunk)
  f.write(bytes(length-vendor.stat().st_size))
  for pos,m,hs,ep in records:
   struct.pack_into('<QIQI',m,ep,length//512,0,(start-base)//512,0)
   m[48:80]=hashlib.sha256(m[hs:hs+u(m,44)]).digest();m[12:44]=bytes(32);m[12:44]=hashlib.sha256(m[:hs]).digest()
   f.seek(pos);f.write(m);f.flush();f.seek(pos);assert f.read(len(m))==m
 return {'vendor_offset':start,'vendor_partition_bytes':length,'metadata_copies_updated':len(records),'preserved':'All other logical-partition extents unchanged; original image untouched.'}
