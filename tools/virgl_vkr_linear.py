#!/usr/bin/env python3
"""Venus host side: import linear Android buffers with the host's own linear layout.

The guest describes a gralloc buffer with VK_IMAGE_TILING_DRM_FORMAT_MODIFIER_EXT, modifier
LINEAR and an explicit plane layout built from its own (tightly packed) stride. The memory it
then imports is a linear GBM buffer that the host driver laid out itself, with the driver's
pitch alignment, so the explicit layout can be rejected or wrong (e.g. 36x36 BGRA: 144-byte rows).
The guest only touches these pixels through the GPU or virgl transfers, so let the host driver
pick the linear layout: drop the explicit layout and create the image with VK_IMAGE_TILING_LINEAR.
Logs each rewrite to stderr when GBOS_VKR_LOG is set. Usage: virgl_vkr_linear.py SRC_ROOT"""
import re, sys
from pathlib import Path

f = Path(sys.argv[1]) / 'src/venus/vkr_image.c'
s = f.read_text()
m = re.search(r'\nvkr_dispatch_vkCreateImage\s*\(\s*struct vn_dispatch_context \*dispatch,\s*'
              r'struct vn_command_vkCreateImage \*args\s*\)\s*\{', s)
if not m:
    sys.exit('vkr_dispatch_vkCreateImage not found')
inject = r'''
   {
      VkImageCreateInfo *gbos_info = (VkImageCreateInfo *)args->pCreateInfo;
      if (gbos_info && gbos_info->tiling == VK_IMAGE_TILING_DRM_FORMAT_MODIFIER_EXT) {
         VkBaseOutStructure *prev = (VkBaseOutStructure *)gbos_info;
         while (prev->pNext) {
            VkBaseOutStructure *cur = prev->pNext;
            const VkImageDrmFormatModifierExplicitCreateInfoEXT *ex =
               (const VkImageDrmFormatModifierExplicitCreateInfoEXT *)cur;
            if (cur->sType == VK_STRUCTURE_TYPE_IMAGE_DRM_FORMAT_MODIFIER_EXPLICIT_CREATE_INFO_EXT &&
                ex->drmFormatModifier == 0 /* DRM_FORMAT_MOD_LINEAR */) {
               if (getenv("GBOS_VKR_LOG")) fprintf(stderr, "gbos-vkr: linear %ux%u fmt %d guest rowPitch %llu offset %llu -> host layout\n",
                       gbos_info->extent.width, gbos_info->extent.height, (int)gbos_info->format,
                       ex->drmFormatModifierPlaneCount ? (unsigned long long)ex->pPlaneLayouts[0].rowPitch : 0ull,
                       ex->drmFormatModifierPlaneCount ? (unsigned long long)ex->pPlaneLayouts[0].offset : 0ull);
               prev->pNext = cur->pNext;
               gbos_info->tiling = VK_IMAGE_TILING_LINEAR;
               continue;
            }
            prev = cur;
         }
      }
   }
'''
s = s[:m.end()] + inject + s[m.end():]
for h in ('stdio.h', 'stdlib.h'):
    if f'#include <{h}>' not in s:
        s = f'#include <{h}>\n' + s
f.write_text(s)
print('patched', f)
