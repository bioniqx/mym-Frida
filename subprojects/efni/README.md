# Efni

Building blocks for protocol-heavy GLib code, written in Vala.

Efni (Old Norse for "material") is the layer underneath
[Idun][] and [frida-core][]. It provides:

- `Buffer`, `BufferBuilder`, `BufferReader`: binary
  (de)serialization with explicit byte order and pointer size.
- `Promise` and `Future`: awaitable results for async code.
- `ObjectBuilder` and `ObjectReader`: structured value access
  over `GLib.Variant` and JSON.
- `VirtualStream`: an `IOStream` base class for user-space
  transports.
- Socket helpers for TCP, UDP and Unix sockets, and socket
  address parsing.
- `FS`: small filesystem helpers.
- `Debugger` and friends: an abstract debugger interface, with
  `GDB.Client` implementing the GDB remote protocol.
- `XpcClient`: an XPC connection wrapper, on macOS.
- `Error`: the error domain shared by everything above.

## Building

```sh
./configure
make
```

[Idun]: https://github.com/frida/idun
[frida-core]: https://github.com/frida/frida-core

## Distro Packaging

For building a shared library suitable for distro packaging:

```console
$ ./configure --enable-shared --without-prebuilds=sdk && make
```

This builds `libefni-1.0.so` against system dependencies, using
Frida's toolchain for the Vala compiler.

Prerequisites on Omarchy / Arch Linux:

```console
$ sudo pacman -S --needed glib2 libgee json-glib libgirepository
```

Prerequisites on Fedora:

```console
$ sudo dnf install glib2-devel libgee-devel json-glib-devel \
      gobject-introspection-devel
```

Prerequisites on Ubuntu:

```console
$ sudo apt install libglib2.0-dev libgee-0.8-dev libjson-glib-dev \
      libgirepository1.0-dev
```

Recipes for Arch (`PKGBUILD`), Fedora (`.spec`) and Debian/Ubuntu
(`debian/`) live in `packaging/`. The Fedora and Debian builds run
without network access, so they take Frida's toolchain as an
additional source, and expect a source tarball that includes the
`releng` submodule.
