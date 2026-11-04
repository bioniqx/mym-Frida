import argparse
import sys


def find_leaked_tokens(blob, tokens):
    leaked = []
    for token in tokens:
        utf8_bytes = token.encode("utf-8")
        utf16le_bytes = token.encode("utf-16-le")
        if utf8_bytes in blob or utf16le_bytes in blob:
            leaked.append(token)
    return leaked


def main():
    parser = argparse.ArgumentParser(
        description="Scan a QuickJS bytecode blob for forbidden tokens."
    )
    parser.add_argument("blob", help="Path to the bytecode blob file")
    parser.add_argument(
        "--forbid",
        nargs="+",
        required=True,
        help="Tokens that must not appear in the blob, as UTF-8 or UTF-16LE bytes",
    )
    args = parser.parse_args()

    with open(args.blob, "rb") as f:
        blob = f.read()

    leaked = find_leaked_tokens(blob, args.forbid)

    if leaked:
        for token in leaked:
            print(f"LEAKED: {token}")
        sys.exit(1)

    print("CLEAN: no forbidden tokens found")
    sys.exit(0)


if __name__ == "__main__":
    main()
