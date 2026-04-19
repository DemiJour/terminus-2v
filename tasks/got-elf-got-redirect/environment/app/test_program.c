#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Declared in libmallocwrapper.so — keep a dynamic ref so .dynsym has this name. */
void *logged_malloc(size_t);
static void *(*volatile _gotpatch_dynsym_anchor)(size_t) = logged_malloc;

static unsigned long fib_hash(int n) {
  if (n <= 1) return (unsigned long)n;
  unsigned long a = 0, b = 1;
  for (int i = 2; i <= n; ++i) {
    unsigned long c = a + b;
    a = b;
    b = c;
  }
  return b;
}

int main(void) {
  unsigned long acc = 0;
  for (int i = 0; i < 120; ++i) {
    void *p = malloc(16 + (i % 7));
    if (!p) {
      return 1;
    }
    memset(p, (unsigned char)(i + 1), 16 + (i % 7));
    acc ^= fib_hash((int)(*(unsigned char *)p)) + (unsigned long)p;
    free(p);
  }
  printf("OK acc=%lu\n", acc);
  return 0;
}
