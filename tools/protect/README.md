# Protect Tooling — Build Bring-up

This directory holds tooling for building and working with protected Frida
agents. `frida_env.sh` is the environment contract for everything downstream:
source it before running any tooling that must use this custom build.

## Custom Frida build

Frida's QuickJS dependency is pinned to the `frida-forks/quickjs` fork of the
upstream Bellard QuickJS fork used by Frida, so that protection tooling can
rely on a known, unmodified QuickJS baseline:

- Pin: `https://github.com/frida-forks/quickjs.git`
- Pinned commit: `cd41bdbf0c6c14a22f4a514bfe8efd6cbca50af3`
- Build options (set in `subprojects/frida-gum/meson.build`, do not change):
  `bignum=true` (CONFIG_BIGNUM), `libc=false`

The wrap file at `subprojects/frida-gum/subprojects/quickjs.wrap` holds this
pin (`url`, `revision`, `depth = 1`, `[provide]`). The wrap file lives inside
the `frida-gum` submodule, so any change to it is committed inside that
submodule, not at the top-level `frida` repo.

## Building

Run these commands from the root of the `frida` repository:

```sh
python3 tools/ensure-submodules.py frida-core frida-python
PYTHON=<python-3.10-or-newer> ./configure --enable-frida-python
MACOS_CERTID=- PYTHON=<python-3.10-or-newer> make
```

One-time step, required before `make`: create a fresh, random 32-byte key
file at `tools/protect/.key` and run the key-header generator from the root
of the `frida` repository:

```sh
head -c 32 /dev/urandom > tools/protect/.key
python3 tools/protect/gen_key_header.py tools/protect/.key
```

The generator writes `subprojects/frida-gum/lib/prot/gumprotkey.h`, which
declares `static const guint8 gum_prot_key[32]` used by the GumJS decrypt
path. The key file is never committed (the root `.gitignore` already excludes
`tools/protect/.key`) and the generated header is git-ignored inside the
`frida-gum` submodule (`subprojects/frida-gum/lib/prot/.gitignore`), so it
must be regenerated per build/release from the current
`tools/protect/.key`. The generator refuses key files whose length is not
exactly 32 bytes and never prints the key bytes.

Environment notes (all three are required on this machine):

- The vendored Meson in `releng/meson` requires Python >= 3.10, so the stock
  macOS `/usr/bin/python3` (3.9.6) fails during configure with
  `AttributeError: module 'typing' has no attribute 'ParamSpec'`. Use the
  uv-managed CPython 3.12:
  `/Users/ethan/.local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12`.
- On macOS the build codesigns its binaries (`subprojects/frida-core/tools/post-process.py`
  exits with `MACOS_CERTID not set` otherwise). This machine has no codesigning
  identities, so build with `MACOS_CERTID=-` (ad-hoc signing).
- This checkout's `configure` takes `--enable-frida-python`; the
  `-Dfrida_python=enabled` meson spelling is not accepted by its argparse.
  (The resulting Meson option is still `frida_python=enabled`.)

Expected artifacts:

- `build/` — the Meson build tree (`build.ninja` plus per-flavor trees).
- `build/subprojects/frida-python/frida/` — the built `frida` Python package
  (`__init__.py` plus the abi3 extension `_frida.abi3.so`), importable via
  `tools/protect/frida_env.sh`.

Prebuild note: by default the build downloads Frida's prebuilt SDKs into
`deps/sdk-*` and satisfies the QuickJS (and glib, capstone, …) dependencies
from there. The wrap checkout at
`subprojects/frida-gum/subprojects/quickjs` is fetched with Meson's own wrap
machinery (see below) and is the source tree to modify for from-source
QuickJS work; making the build itself compile QuickJS from that checkout
requires configuring with `--without-prebuilds=sdk` (which also rebuilds the
other SDK dependencies from source).

## Using the built Python module (PYTHONPATH)

```sh
. tools/protect/frida_env.sh
python3 -c "import frida; print(frida.__file__)"
```

The script computes its location from `BASH_SOURCE`, so it works from any
cwd and in any worktree of this repository. It exports `PYTHONPATH` pointing
at `build/subprojects/frida-python` in the same worktree as the script.
`import frida` must then resolve to `.../build/subprojects/frida-python/frida/__init__.py`,
never a pip-installed copy.

## Verifying the QuickJS pin

```sh
grep -n 'url' subprojects/frida-gum/subprojects/quickjs.wrap
git -C subprojects/frida-gum/subprojects/quickjs rev-parse HEAD
git -C subprojects/frida-gum/subprojects/quickjs remote get-url origin
```

The first command must show `https://github.com/frida-forks/quickjs.git`; the
second must print `cd41bdbf0c6c14a22f4a514bfe8efd6cbca50af3`. If the checkout
is missing, fetch it with Meson's wrap machinery:

```sh
cd subprojects/frida-gum
python3.10-or-newer ../../releng/meson/meson.py subprojects download quickjs
```

## Deferred: GitHub fork

Creating a dedicated GitHub fork of QuickJS under the owner's account was
deferred; the wrap keeps pointing at the existing `frida-forks/quickjs` pin.
When the fork exists, repoint the wrap by changing the `url` line in
`subprojects/frida-gum/subprojects/quickjs.wrap`:

```diff
-url = https://github.com/frida-forks/quickjs.git
+url = https://github.com/OWNER/quickjs.git
```

Keep `revision`, `depth`, and the `[provide]` section unchanged, remove the
stale `subprojects/frida-gum/subprojects/quickjs` checkout so Meson
re-fetches from the new URL, and commit the wrap change inside the
`frida-gum` submodule.
