#!/usr/bin/env python3
"""Instrument virglrenderer (applied in the flake's virglrenderer-debug postPatch).

Logs, to stderr, every early exit of vrend_resource_gbm_init (why a vrend resource did not get a
GBM buffer and so cannot be exported to Venus as a dma-buf), each GBM allocation that succeeds,
and each resource proxy_context_attach_resource skips because it has no dma-buf.
Usage: virgl_gbm_debug.py SRC_ROOT"""
import re, sys
from pathlib import Path

root = Path(sys.argv[1])

vrend = root / 'src/vrend/vrend_renderer.c'
s = vrend.read_text()
m = re.search(r'static void\s+vrend_resource_gbm_init\s*\(\s*struct vrend_resource \*gr,\s*uint32_t format\s*\)\s*\{', s)
if not m:
    sys.exit('vrend_resource_gbm_init not found')
start = m.end()
depth, i = 1, start
while depth:
    depth += {'{': 1, '}': -1}.get(s[i], 0); i += 1
body = s[start:i - 1]
info = ('"gbm_init: %s line %d res bind=0x%x fmt=%u %ux%u depth=%u levels=%u samples=%u\\n", {what}, __LINE__, '
        'gr->base.bind, format, gr->base.width0, gr->base.height0, gr->base.depth0, gr->base.last_level, gr->base.nr_samples')
body = body.replace('return;', '{ fprintf(stderr, ' + info.format(what='"skip"') + '); return; }')
body = body.replace('gr->storage_bits |= VREND_STORAGE_GBM_BUFFER;',
                    'gr->storage_bits |= VREND_STORAGE_GBM_BUFFER; fprintf(stderr, ' + info.format(what='"GBM"') + ');', 1)
body = '\n   fprintf(stderr, ' + info.format(what='"enter"') + ');' + body
s = s[:start] + body + s[i - 1:]
if '#include <stdio.h>' not in s:
    s = '#include <stdio.h>\n' + s
vrend.write_text(s)
print('instrumented', vrend, 'exits:', body.count('"skip"'))

proxy = root / 'src/proxy/proxy_context.c'
p = proxy.read_text()
needle = 'if (res_fd_type != VIRGL_RESOURCE_FD_DMABUF) {'
if needle in p:
    p = p.replace(needle, needle + '\n         fprintf(stderr, "proxy_attach: res %u not attached, export fd type %d\\n", res->res_id, (int)res_fd_type);', 1)
    if '#include <stdio.h>' not in p:
        p = '#include <stdio.h>\n' + p
    proxy.write_text(p)
    print('instrumented', proxy)
else:
    print('warning: proxy attach check not found, skipped', proxy)
