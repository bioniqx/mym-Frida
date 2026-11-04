#include "native_core.h"

#include <string.h>

int
gum_prot_native_entry (const char * op,
                       const char * arg,
                       char * out,
                       size_t out_len)
{
  (void) arg;

  if (out_len == 0)
    return -1;

  if (strcmp (op, "ping") == 0)
  {
    size_t n = strlen ("pong");

    if (n >= out_len)
      n = out_len - 1;

    memcpy (out, "pong", n);
    out[n] = '\0';

    return 0;
  }

  out[0] = '\0';

  return -1;
}
