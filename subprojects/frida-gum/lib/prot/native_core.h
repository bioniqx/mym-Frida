/*
 * Native core for the Prot white-box hardening layer.
 *
 * This is scaffolding: it wires a callable path from JavaScript down to
 * native code end-to-end. The real per-operation logic lands later.
 */

#ifndef __GUM_PROT_NATIVE_CORE_H__
#define __GUM_PROT_NATIVE_CORE_H__

#include <stddef.h>

int gum_prot_native_entry (const char * op, const char * arg, char * out,
    size_t out_len);

#endif
