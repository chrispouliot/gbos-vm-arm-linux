#!/usr/bin/env python3
"""Let Venus import Android gralloc buffers on a Linux host (applied as a virglrenderer postPatch).

vrend only exports GBM-backed resources as dma-bufs, and only allocates through GBM for
SCANOUT/SHARED binds whose bind flags map to non-zero GBM usage. The guest's minigbm gives
ordinary window buffers RENDER_TARGET|SAMPLER_VIEW (no SHARED), and SAMPLER_VIEW alone maps to
no usage with Mesa GBM, so Venus cannot import them ("invalid res_id"). When the GBM-layout
path is active (Venus enabled + VIRGL_GBM_LAYOUT_FORCE_ENABLE), also put 2D render-target /
sampler / shared textures in linear GBM buffers.
Usage: virgl_venus_share.py SRC_ROOT"""
import sys
from pathlib import Path

f = Path(sys.argv[1]) / 'src/vrend/vrend_renderer.c'
s = f.read_text()

gate = '   if (!gbm || !gbm->device || !gbm_format || !gbm_flags)'
assert s.count(gate) == 1, 'GBM device check not found'
s = s.replace(gate, '''   const bool gbos_venus_share = vrend_state.gbm_layout_feat &&
      gr->base.target == PIPE_TEXTURE_2D &&
      (gr->base.bind & (VIRGL_BIND_RENDER_TARGET | VIRGL_BIND_SAMPLER_VIEW | VIRGL_BIND_SHARED));
   if (gbos_venus_share) {
      if (!gbm_flags)
         gbm_flags = GBM_BO_USE_RENDERING;
      gbm_flags |= GBM_BO_USE_LINEAR;
   }
''' + gate)

pref = '   if (!virgl_gbm_external_allocation_preferred(gr->base.bind))'
assert s.count(pref) == 1, 'external allocation check not found'
s = s.replace(pref, '   if (!virgl_gbm_external_allocation_preferred(gr->base.bind) && !gbos_venus_share)')

f.write_text(s)
print('patched', f)
