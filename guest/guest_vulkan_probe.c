/* Vulkan smoke test for the guest: enumerate, submit, read back 4 KiB; with --ahb-render,
 * share one Android buffer between Vulkan and GLES and check every pixel. */
#define VK_USE_PLATFORM_ANDROID_KHR
#include <vulkan/vulkan.h>
#include <android/hardware_buffer.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include "virtgpu_drm.h"
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#define CHECK(call) do { VkResult r=(call); printf("VM_VULKAN %s = %d\n",#call,r); if(r!=VK_SUCCESS)return 1; } while(0)
int main(int argc, char **argv) {
 int test_render=argc>1 && !strcmp(argv[1],"--ahb-render");
 int test_ahb=test_render || (argc>1 && !strcmp(argv[1],"--ahb"));
 setbuf(stdout,NULL);
 puts("VM_VULKAN_BEGIN");
 setenv("VN_DEBUG","init,result",1);
 setenv("MESA_LOG_LEVEL","debug",1);
 setenv("MESA_LOG","file,android",1);
 int fd=open("/dev/dri/renderD128",O_RDWR|O_CLOEXEC);
 printf("VM_VULKAN render_node_fd=%d errno=%d\n",fd,fd<0?errno:0);
 if(fd>=0){
   for(unsigned int param=1;param<=8;param++){
     uint64_t val=0;
     struct drm_virtgpu_getparam gp={.param=param,.value=(uintptr_t)&val};
     int rc=ioctl(fd,DRM_IOCTL_VIRTGPU_GETPARAM,&gp);
     printf("VM_VULKAN virtgpu_param=%u value=%llu rc=%d errno=%d\n",param,(unsigned long long)val,rc,rc<0?errno:0);
   }
   close(fd);
 }
 VkApplicationInfo ai={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="VM Vulkan probe",.apiVersion=VK_API_VERSION_1_1};
 VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&ai};
 VkInstance inst; CHECK(vkCreateInstance(&ici,NULL,&inst));
 uint32_t count=0; CHECK(vkEnumeratePhysicalDevices(inst,&count,NULL));
 printf("VM_VULKAN physical_devices=%u\n",count);if(!count)return 2;
 VkPhysicalDevice *devices=calloc(count,sizeof(*devices)); CHECK(vkEnumeratePhysicalDevices(inst,&count,devices));
 VkPhysicalDevice phys=devices[0];free(devices);
 VkPhysicalDeviceProperties props;vkGetPhysicalDeviceProperties(phys,&props);
 printf("VM_VULKAN device=%s api=%u.%u.%u vendor=%x device_id=%x\n",props.deviceName,VK_VERSION_MAJOR(props.apiVersion),VK_VERSION_MINOR(props.apiVersion),VK_VERSION_PATCH(props.apiVersion),props.vendorID,props.deviceID);
 uint32_t ne=0;CHECK(vkEnumerateDeviceExtensionProperties(phys,NULL,&ne,NULL));
 VkExtensionProperties *ext=calloc(ne,sizeof(*ext));CHECK(vkEnumerateDeviceExtensionProperties(phys,NULL,&ne,ext));
 for(uint32_t i=0;i<ne;i++)if(strstr(ext[i].extensionName,"external_memory")||strstr(ext[i].extensionName,"android")||strstr(ext[i].extensionName,"swapchain"))printf("VM_VULKAN extension=%s\n",ext[i].extensionName);
 if(argc>1 && !strcmp(argv[1],"--caps")){
  for(uint32_t i=0;i<ne;i++)printf("VM_CAPS ext %s\n",ext[i].extensionName);
  VkPhysicalDeviceTransformFeedbackFeaturesEXT tf={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_TRANSFORM_FEEDBACK_FEATURES_EXT};
  VkPhysicalDeviceSamplerYcbcrConversionFeatures yc={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SAMPLER_YCBCR_CONVERSION_FEATURES,.pNext=&tf};
  VkPhysicalDeviceFeatures2 f2={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,.pNext=&yc};
  vkGetPhysicalDeviceFeatures2(phys,&f2);
  VkPhysicalDeviceDriverProperties dp={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
  VkPhysicalDeviceProperties2 p2={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,.pNext=&dp};
  vkGetPhysicalDeviceProperties2(phys,&p2);
  printf("VM_CAPS driver id=%d name=%s info=%s type=%d\n",dp.driverID,dp.driverName,dp.driverInfo,props.deviceType);
  printf("VM_CAPS transformFeedback=%u geometryStreams=%u samplerYcbcrConversion=%u\n",tf.transformFeedback,tf.geometryStreams,yc.samplerYcbcrConversion);
  const VkBool32 *fb=(const VkBool32*)&f2.features;
  printf("VM_CAPS features ");for(unsigned i=0;i<sizeof(VkPhysicalDeviceFeatures)/sizeof(VkBool32);i++)putchar(fb[i]?'1':'0');putchar('\n');
#define CF(x) printf("VM_CAPS feature %s %u\n",#x,f2.features.x);
  CF(independentBlend)CF(inheritedQueries)CF(vertexPipelineStoresAndAtomics)CF(fragmentStoresAndAtomics)CF(sampleRateShading)CF(imageCubeArray)CF(geometryShader)CF(tessellationShader)CF(shaderClipDistance)CF(depthClamp)CF(samplerAnisotropy)CF(textureCompressionETC2)CF(textureCompressionASTC_LDR)CF(textureCompressionBC)CF(occlusionQueryPrecise)CF(fullDrawIndexUint32)CF(robustBufferAccess)CF(dualSrcBlend)CF(multiDrawIndirect)CF(shaderInt16)CF(largePoints)CF(wideLines)CF(depthBiasClamp)CF(fillModeNonSolid)
#define CL(x) printf("VM_CAPS limit %s %llu\n",#x,(unsigned long long)props.limits.x);
  CL(standardSampleLocations)CL(maxPerStageDescriptorUniformBuffers)CL(maxPerStageDescriptorStorageBuffers)CL(maxPerStageDescriptorSamplers)CL(maxPerStageDescriptorSampledImages)CL(maxPerStageResources)CL(maxDescriptorSetUniformBuffers)CL(maxDescriptorSetUniformBuffersDynamic)CL(maxDescriptorSetSamplers)CL(maxDescriptorSetSampledImages)CL(maxVertexOutputComponents)CL(maxFragmentInputComponents)CL(maxVertexInputAttributeOffset)CL(maxVertexInputAttributes)CL(maxVertexInputBindings)CL(maxColorAttachments)CL(maxUniformBufferRange)CL(maxImageDimension2D)CL(maxImageDimension3D)CL(maxImageArrayLayers)CL(maxDrawIndexedIndexValue)CL(framebufferColorSampleCounts)CL(maxBoundDescriptorSets)CL(maxPushConstantsSize)CL(maxFragmentOutputAttachments)CL(maxTexelBufferElements)CL(minUniformBufferOffsetAlignment)
  uint32_t nqc=0;vkGetPhysicalDeviceQueueFamilyProperties(phys,&nqc,NULL);VkQueueFamilyProperties qf[8];if(nqc>8)nqc=8;vkGetPhysicalDeviceQueueFamilyProperties(phys,&nqc,qf);
  for(uint32_t i=0;i<nqc;i++)printf("VM_CAPS queue %u flags=%x count=%u\n",i,qf[i].queueFlags,qf[i].queueCount);
  uint32_t ni=0;vkEnumerateInstanceExtensionProperties(NULL,&ni,NULL);VkExtensionProperties ie[64];if(ni>64)ni=64;vkEnumerateInstanceExtensionProperties(NULL,&ni,ie);
  for(uint32_t i=0;i<ni;i++)printf("VM_CAPS instance_ext %s\n",ie[i].extensionName);
  puts("VM_CAPS_END");return 0;
 }
 free(ext);
 uint32_t nq=0;vkGetPhysicalDeviceQueueFamilyProperties(phys,&nq,NULL);
 VkQueueFamilyProperties *qp=calloc(nq,sizeof(*qp));vkGetPhysicalDeviceQueueFamilyProperties(phys,&nq,qp);
 uint32_t qi=0;for(;qi<nq;qi++)if(qp[qi].queueFlags&(VK_QUEUE_GRAPHICS_BIT|VK_QUEUE_COMPUTE_BIT))break;free(qp);if(qi==nq)return 3;
 float priority=1;VkDeviceQueueCreateInfo qci={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=qi,.queueCount=1,.pQueuePriorities=&priority};
 VkDeviceCreateInfo dci={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qci};
 const char *ahb_ext[]={VK_ANDROID_EXTERNAL_MEMORY_ANDROID_HARDWARE_BUFFER_EXTENSION_NAME,VK_EXT_QUEUE_FAMILY_FOREIGN_EXTENSION_NAME};
 if(test_ahb){dci.enabledExtensionCount=test_render?2:1;dci.ppEnabledExtensionNames=ahb_ext;}
 VkDevice dev;CHECK(vkCreateDevice(phys,&dci,NULL,&dev));
 if(test_ahb){
   AHardwareBuffer_Desc desc={.width=64,.height=64,.layers=1,.format=AHARDWAREBUFFER_FORMAT_R8G8B8A8_UNORM,.usage=AHARDWAREBUFFER_USAGE_GPU_SAMPLED_IMAGE|AHARDWAREBUFFER_USAGE_GPU_COLOR_OUTPUT};
   AHardwareBuffer *ahb=NULL;int rc=AHardwareBuffer_allocate(&desc,&ahb);
   printf("VM_AHB allocate_rc=%d\n",rc);if(rc||!ahb)return 6;
   uint64_t id=0;AHardwareBuffer_getId(ahb,&id);AHardwareBuffer_describe(ahb,&desc);
   printf("VM_AHB id=%llu size=%ux%u stride=%u usage=%llu\n",(unsigned long long)id,desc.width,desc.height,desc.stride,(unsigned long long)desc.usage);
   PFN_vkGetAndroidHardwareBufferPropertiesANDROID get=(PFN_vkGetAndroidHardwareBufferPropertiesANDROID)vkGetDeviceProcAddr(dev,"vkGetAndroidHardwareBufferPropertiesANDROID");
   if(!get)return 7;
   VkAndroidHardwareBufferFormatPropertiesANDROID fmt={.sType=VK_STRUCTURE_TYPE_ANDROID_HARDWARE_BUFFER_FORMAT_PROPERTIES_ANDROID};
   VkAndroidHardwareBufferPropertiesANDROID hp={.sType=VK_STRUCTURE_TYPE_ANDROID_HARDWARE_BUFFER_PROPERTIES_ANDROID,.pNext=&fmt};
   puts("VM_AHB QUERY_BEGIN");VkResult result=get(dev,ahb,&hp);
   printf("VM_AHB QUERY_RESULT=%d allocationSize=%llu memoryTypeBits=%x format=%u\n",result,(unsigned long long)hp.allocationSize,hp.memoryTypeBits,fmt.format);
   if(test_render && result==VK_SUCCESS){
     VkExternalMemoryImageCreateInfo external={.sType=VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_IMAGE_CREATE_INFO,.handleTypes=VK_EXTERNAL_MEMORY_HANDLE_TYPE_ANDROID_HARDWARE_BUFFER_BIT_ANDROID};
     VkImageCreateInfo image_ci={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.pNext=&external,.imageType=VK_IMAGE_TYPE_2D,.format=fmt.format,.extent={64,64,1},.mipLevels=1,.arrayLayers=1,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,.usage=VK_IMAGE_USAGE_TRANSFER_DST_BIT|VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED};
     VkImage image;CHECK(vkCreateImage(dev,&image_ci,NULL,&image));
     VkMemoryDedicatedAllocateInfo dedicated={.sType=VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO,.image=image};
     VkImportAndroidHardwareBufferInfoANDROID imported={.sType=VK_STRUCTURE_TYPE_IMPORT_ANDROID_HARDWARE_BUFFER_INFO_ANDROID,.pNext=&dedicated,.buffer=ahb};
     uint32_t mt=0;while(mt<32 && !(hp.memoryTypeBits&(1u<<mt)))mt++;if(mt==32)return 9;
     VkMemoryAllocateInfo mem_ci={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.pNext=&imported,.allocationSize=hp.allocationSize,.memoryTypeIndex=mt};
     VkDeviceMemory memory;CHECK(vkAllocateMemory(dev,&mem_ci,NULL,&memory));CHECK(vkBindImageMemory(dev,image,memory,0));
     VkQueue queue;vkGetDeviceQueue(dev,qi,0,&queue);
     VkCommandPoolCreateInfo pool_ci={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.queueFamilyIndex=qi};
     VkCommandPool pool;CHECK(vkCreateCommandPool(dev,&pool_ci,NULL,&pool));
     VkCommandBufferAllocateInfo cb_ci={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
     VkCommandBuffer cb;CHECK(vkAllocateCommandBuffers(dev,&cb_ci,&cb));
     VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};CHECK(vkBeginCommandBuffer(cb,&begin));
     VkImageSubresourceRange range={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
     VkImageMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED,.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=image,.subresourceRange=range};
     vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&barrier);
     VkClearColorValue red={.float32={1,0,0,1}};vkCmdClearColorImage(cb,image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,&red,1,&range);
     barrier.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;barrier.dstAccessMask=0;barrier.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;barrier.newLayout=VK_IMAGE_LAYOUT_GENERAL;
     barrier.srcQueueFamilyIndex=qi;barrier.dstQueueFamilyIndex=VK_QUEUE_FAMILY_FOREIGN_EXT;
     vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,0,0,NULL,0,NULL,1,&barrier);
     CHECK(vkEndCommandBuffer(cb));
     VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cb};CHECK(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE));CHECK(vkQueueWaitIdle(queue));
     puts("VM_AHB VULKAN_CLEAR_COMPLETE");
     EGLDisplay display=eglGetDisplay(EGL_DEFAULT_DISPLAY);EGLint major,minor;
     if(!eglInitialize(display,&major,&minor)){printf("VM_AHB EGL_INIT_ERROR=%x\n",eglGetError());return 10;}
     EGLint attributes[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES2_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_NONE};
     EGLConfig config;EGLint n;if(!eglChooseConfig(display,attributes,&config,1,&n)||!n)return 11;
     EGLint context_attributes[]={EGL_CONTEXT_CLIENT_VERSION,2,EGL_NONE};EGLContext context=eglCreateContext(display,config,EGL_NO_CONTEXT,context_attributes);
     EGLint surface_attributes[]={EGL_WIDTH,1,EGL_HEIGHT,1,EGL_NONE};EGLSurface surface=eglCreatePbufferSurface(display,config,surface_attributes);
     if(!eglMakeCurrent(display,surface,surface,context))return 12;
     PFNEGLGETNATIVECLIENTBUFFERANDROIDPROC client=(void*)eglGetProcAddress("eglGetNativeClientBufferANDROID");
     PFNEGLCREATEIMAGEKHRPROC create_image=(void*)eglGetProcAddress("eglCreateImageKHR");
     PFNEGLDESTROYIMAGEKHRPROC destroy_image=(void*)eglGetProcAddress("eglDestroyImageKHR");
     PFNGLEGLIMAGETARGETTEXTURE2DOESPROC target=(void*)eglGetProcAddress("glEGLImageTargetTexture2DOES");
     if(!client||!create_image||!destroy_image||!target)return 13;
     EGLint image_attributes[]={EGL_IMAGE_PRESERVED_KHR,EGL_TRUE,EGL_NONE};
     EGLImageKHR ei=create_image(display,EGL_NO_CONTEXT,EGL_NATIVE_BUFFER_ANDROID,client(ahb),image_attributes);
     if(ei==EGL_NO_IMAGE_KHR){printf("VM_AHB EGL_IMPORT_ERROR=%x\n",eglGetError());return 14;}
     GLuint texture,fb;glGenTextures(1,&texture);glBindTexture(GL_TEXTURE_2D,texture);target(GL_TEXTURE_2D,ei);
     glGenFramebuffers(1,&fb);glBindFramebuffer(GL_FRAMEBUFFER,fb);glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,texture,0);
     if(glCheckFramebufferStatus(GL_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE)return 15;
     unsigned char pixels[64*64*4];memset(pixels,0,sizeof(pixels));glReadPixels(0,0,64,64,GL_RGBA,GL_UNSIGNED_BYTE,pixels);
     GLenum error=glGetError();unsigned good=0;for(unsigned j=0;j<64*64;j++)if(pixels[j*4]==255&&pixels[j*4+1]==0&&pixels[j*4+2]==0&&pixels[j*4+3]==255)good++;
     printf("VM_AHB VULKAN_TO_GLES_READBACK=%s pixels=%u/4096 gl_error=%x first=%u,%u,%u,%u\n",good==4096&&error==GL_NO_ERROR?"PASS":"FAIL",good,error,pixels[0],pixels[1],pixels[2],pixels[3]);
     glDeleteFramebuffers(1,&fb);glDeleteTextures(1,&texture);destroy_image(display,ei);eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);eglDestroySurface(display,surface);eglDestroyContext(display,context);eglTerminate(display);
     vkDestroyCommandPool(dev,pool,NULL);vkDestroyImage(dev,image,NULL);vkFreeMemory(dev,memory,NULL);
     if(good!=4096||error!=GL_NO_ERROR)return 16;
   }
   AHardwareBuffer_release(ahb);vkDestroyDevice(dev,NULL);vkDestroyInstance(inst,NULL);
   return result==VK_SUCCESS?0:8;
 }

 VkQueue queue;vkGetDeviceQueue(dev,qi,0,&queue);
 VkBufferCreateInfo bci={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=4096,.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
 VkBuffer buf;CHECK(vkCreateBuffer(dev,&bci,NULL,&buf));
 VkMemoryRequirements req;vkGetBufferMemoryRequirements(dev,buf,&req);
 VkPhysicalDeviceMemoryProperties mp;vkGetPhysicalDeviceMemoryProperties(phys,&mp);
 uint32_t mi=0;for(;mi<mp.memoryTypeCount;mi++)if((req.memoryTypeBits&(1u<<mi))&&(mp.memoryTypes[mi].propertyFlags&VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT))break;if(mi==mp.memoryTypeCount)return 4;
 VkMemoryAllocateInfo mai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=req.size,.memoryTypeIndex=mi};
 VkDeviceMemory mem;CHECK(vkAllocateMemory(dev,&mai,NULL,&mem));CHECK(vkBindBufferMemory(dev,buf,mem,0));
 VkCommandPoolCreateInfo pci={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.queueFamilyIndex=qi};
 VkCommandPool pool;CHECK(vkCreateCommandPool(dev,&pci,NULL,&pool));
 VkCommandBufferAllocateInfo cai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
 VkCommandBuffer cb;CHECK(vkAllocateCommandBuffers(dev,&cai,&cb));
 VkCommandBufferBeginInfo bi={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};CHECK(vkBeginCommandBuffer(cb,&bi));
 vkCmdFillBuffer(cb,buf,0,4096,0x1234abcd);
 VkMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.dstAccessMask=VK_ACCESS_HOST_READ_BIT};
 vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&barrier,0,NULL,0,NULL);
 CHECK(vkEndCommandBuffer(cb));
 VkSubmitInfo si={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cb};
 VkFenceCreateInfo fci={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};VkFence fence;CHECK(vkCreateFence(dev,&fci,NULL,&fence));
 CHECK(vkQueueSubmit(queue,1,&si,fence));CHECK(vkWaitForFences(dev,1,&fence,VK_TRUE,10000000000ull));
 void *mapped;CHECK(vkMapMemory(dev,mem,0,VK_WHOLE_SIZE,0,&mapped));
 VkMappedMemoryRange range={.sType=VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,.memory=mem,.offset=0,.size=VK_WHOLE_SIZE};CHECK(vkInvalidateMappedMemoryRanges(dev,1,&range));
 int ok=1;for(int i=0;i<1024;i++)if(((uint32_t*)mapped)[i]!=0x1234abcd){ok=0;break;}
 printf("VM_VULKAN readback=%s\n",ok?"PASS":"FAIL");
 vkUnmapMemory(dev,mem);vkDestroyFence(dev,fence,NULL);vkDestroyCommandPool(dev,pool,NULL);vkDestroyBuffer(dev,buf,NULL);vkFreeMemory(dev,mem,NULL);vkDestroyDevice(dev,NULL);vkDestroyInstance(inst,NULL);
 puts("VM_VULKAN_END");return ok?0:5;
}
