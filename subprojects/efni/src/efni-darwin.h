#ifndef __EFNI_DARWIN_H__
#define __EFNI_DARWIN_H__

#include <glib.h>
#include <xpc/xpc.h>

G_BEGIN_DECLS

typedef void (* EfniXpcHandler) (xpc_object_t object, gpointer user_data);
typedef gboolean (* EfniXpcDictionaryApplier) (const gchar * key, xpc_object_t val, gpointer user_data);

gpointer _efni_dispatch_retain (gpointer object);

void _efni_xpc_connection_set_event_handler (xpc_connection_t connection, EfniXpcHandler handler, gpointer user_data);
void _efni_xpc_connection_send_message_with_reply (xpc_connection_t connection, xpc_object_t message, dispatch_queue_t replyq,
    EfniXpcHandler handler, gpointer user_data, GDestroyNotify notify);
gchar * _efni_xpc_object_to_string (xpc_object_t object);
gboolean _efni_xpc_dictionary_apply (xpc_object_t dict, EfniXpcDictionaryApplier applier, gpointer user_data);

G_END_DECLS

#endif
