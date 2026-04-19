#define _GNU_SOURCE
#include <dlfcn.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

/* Must appear in .dynsym so GOT relocations can be retargeted to this symbol. */
__attribute__((visibility("default"))) void *logged_malloc(size_t size) {
  static void *(*real_malloc)(size_t) = NULL;
  if (!real_malloc) {
    real_malloc = (void *(*)(size_t))dlsym(RTLD_NEXT, "malloc");
  }
  fprintf(stderr, "MALLOC INTERCEPTED size=%zu\n", size);
  return real_malloc(size);
}
