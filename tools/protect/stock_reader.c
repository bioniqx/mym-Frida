/*
 * stock_reader.c — minimal stock QuickJS bytecode reader.
 *
 * Usage:
 *   stock_reader <bytecode-file>
 *       Reads <bytecode-file> with the stock JS_ReadObject() and prints
 *       PARSED_OK on success or PARSE_FAIL plus the exception on error.
 *
 *   stock_reader --make-control <script.js> <out.bin>
 *       Compiles <script.js> with the stock engine and writes the
 *       resulting serialized bytecode to <out.bin>. Used only to produce
 *       a non-permuted control blob for the reader sanity check.
 */
#include <signal.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "quickjs.h"

/* JS_ReadObject() validates bytecode by walking it; a blob whose opcodes
 * were permuted by a different engine build can drive that walk into a
 * non-terminating loop (observed: stock 2026-06-04 spins forever on a
 * blob compiled by the permuted fork). This reader is a gate oracle and
 * must always terminate, so bound every read with a wall-clock alarm. */
#define READER_TIMEOUT_SECONDS 60

static void on_read_timeout(int sig) {
    (void)sig;
    printf("PARSE_FAIL: stock reader timed out after %d seconds\n",
           READER_TIMEOUT_SECONDS);
    fflush(stdout);
    _exit(1);
}

static uint8_t *read_file(const char *path, size_t *out_len) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *buf = malloc((size_t)len);
    if (!buf || fread(buf, 1, (size_t)len, f) != (size_t)len) {
        fclose(f);
        free(buf);
        return NULL;
    }
    fclose(f);
    *out_len = (size_t)len;
    return buf;
}

static int make_control(const char *script_path, const char *out_path) {
    size_t src_len;
    uint8_t *src = read_file(script_path, &src_len);
    if (!src) {
        fprintf(stderr, "PARSE_FAIL: cannot read %s\n", script_path);
        return 1;
    }

    JSRuntime *rt = JS_NewRuntime();
    JSContext *ctx = JS_NewContext(rt);

    JSValue obj = JS_Eval(ctx, (const char *)src, src_len, script_path,
                          JS_EVAL_TYPE_GLOBAL | JS_EVAL_FLAG_COMPILE_ONLY);
    free(src);
    if (JS_IsException(obj)) {
        JSValue exc = JS_GetException(ctx);
        const char *msg = JS_ToCString(ctx, exc);
        fprintf(stderr, "PARSE_FAIL: %s\n", msg ? msg : "(no exception message)");
        JS_FreeCString(ctx, msg);
        JS_FreeValue(ctx, exc);
        JS_FreeValue(ctx, obj);
        JS_FreeContext(ctx);
        JS_FreeRuntime(rt);
        return 1;
    }

    size_t bc_len;
    uint8_t *bc = JS_WriteObject(ctx, &bc_len, obj, JS_WRITE_OBJ_BYTECODE);
    JS_FreeValue(ctx, obj);
    if (!bc) {
        fprintf(stderr, "PARSE_FAIL: JS_WriteObject failed\n");
        JS_FreeContext(ctx);
        JS_FreeRuntime(rt);
        return 1;
    }

    FILE *out = fopen(out_path, "wb");
    if (!out || fwrite(bc, 1, bc_len, out) != bc_len) {
        fprintf(stderr, "PARSE_FAIL: cannot write %s\n", out_path);
        if (out) fclose(out);
        js_free(ctx, bc);
        JS_FreeContext(ctx);
        JS_FreeRuntime(rt);
        return 1;
    }
    fclose(out);
    js_free(ctx, bc);
    JS_FreeContext(ctx);
    JS_FreeRuntime(rt);
    printf("CONTROL_WRITTEN\n");
    return 0;
}

static int read_bytecode(const char *bc_path) {
    size_t len;
    uint8_t *buf = read_file(bc_path, &len);
    if (!buf) {
        printf("PARSE_FAIL: cannot open %s\n", bc_path);
        return 1;
    }

    JSRuntime *rt = JS_NewRuntime();
    JSContext *ctx = JS_NewContext(rt);

    signal(SIGALRM, on_read_timeout);
    alarm(READER_TIMEOUT_SECONDS);
    JSValue obj = JS_ReadObject(ctx, buf, len, JS_READ_OBJ_BYTECODE);
    alarm(0);
    free(buf);

    if (JS_IsException(obj)) {
        JSValue exc = JS_GetException(ctx);
        const char *msg = JS_ToCString(ctx, exc);
        printf("PARSE_FAIL: %s\n", msg ? msg : "(no exception message)");
        JS_FreeCString(ctx, msg);
        JS_FreeValue(ctx, exc);
        JS_FreeValue(ctx, obj);
        JS_FreeContext(ctx);
        JS_FreeRuntime(rt);
        return 1;
    }

    printf("PARSED_OK\n");
    JS_FreeValue(ctx, obj);
    JS_FreeContext(ctx);
    JS_FreeRuntime(rt);
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 4 && strcmp(argv[1], "--make-control") == 0) {
        return make_control(argv[2], argv[3]);
    }
    if (argc == 2) {
        return read_bytecode(argv[1]);
    }
    fprintf(stderr, "usage: %s <bytecode-file>\n", argv[0]);
    fprintf(stderr, "       %s --make-control <script.js> <out.bin>\n", argv[0]);
    return 2;
}
