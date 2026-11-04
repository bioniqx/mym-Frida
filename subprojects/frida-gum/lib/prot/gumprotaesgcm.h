#ifndef __GUM_PROT_AESGCM_H__
#define __GUM_PROT_AESGCM_H__

#include <glib.h>

G_BEGIN_DECLS

gboolean gum_prot_aes256gcm_decrypt (const guint8 key[32],
    const guint8 nonce[12], const guint8 * ct, gsize ct_len, guint8 * out,
    gsize * out_len);

G_END_DECLS

#endif
