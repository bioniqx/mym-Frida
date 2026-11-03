import os
import sys

DEFAULT_HEADER_PATH = "subprojects/frida-gum/lib/prot/gumprotkey.h"
KEY_SIZE = 32


def render_header(key):
    items = ", ".join("0x%02x" % b for b in key)
    return (
        "#ifndef GUM_PROT_KEY_H\n"
        "#define GUM_PROT_KEY_H\n"
        "\n"
        "static const guint8 gum_prot_key[32] = { %s };\n"
        "\n"
        "#endif\n"
    ) % items


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) != 1:
        sys.stderr.write("usage: python3 tools/protect/gen_key_header.py <key-file>\n")
        return 2
    key_path = argv[0]
    with open(key_path, "rb") as f:
        key = f.read()
    if len(key) != KEY_SIZE:
        sys.stderr.write(
            "gen_key_header.py: key file must be exactly %d bytes, got %d bytes: %s\n"
            % (KEY_SIZE, len(key), key_path)
        )
        return 1
    header_dir = os.path.dirname(DEFAULT_HEADER_PATH)
    if header_dir and not os.path.isdir(header_dir):
        os.makedirs(header_dir)
    with open(DEFAULT_HEADER_PATH, "w") as f:
        f.write(render_header(key))
    print("wrote %s" % DEFAULT_HEADER_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
