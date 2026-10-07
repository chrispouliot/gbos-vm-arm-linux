#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv,char **envp){
 void *lib=dlopen(getenv("VM_QEMU_LIBRARY"),RTLD_LOCAL|RTLD_LAZY);
 if(!lib){fprintf(stderr,"%s\n",dlerror());return 1;}
 void (*init)(int,char**,char**)=dlsym(lib,"qemu_init");
 void (*loop)(void)=dlsym(lib,"qemu_main_loop");
 void (*cleanup)(void)=dlsym(lib,"qemu_cleanup");
 if(!init||!loop||!cleanup)return 2;
 init(argc,argv,envp);loop();cleanup();return 0;
}
