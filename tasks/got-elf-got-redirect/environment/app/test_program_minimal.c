#include <unistd.h>

/* Dynamic executable that never references malloc — should have no malloc symbol to retarget. */
int main(void) {
  const char msg[] = "ok\n";
  (void)write(1, msg, sizeof msg - 1);
  return 0;
}
