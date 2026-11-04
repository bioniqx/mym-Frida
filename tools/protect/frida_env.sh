#!/bin/sh
#
# frida_env.sh — environment for this worktree's custom Frida build.
#
# Source it from any directory (the path is computed from where this file
# lives, so each worktree of this repository gets its own build):
#
#     . tools/protect/frida_env.sh
#     python3 -c "import frida; print(frida.__file__)"
#
# Exports PYTHONPATH so that the `frida` module built under this worktree's
# build/ tree is importable, instead of any pip-installed copy. The module
# entry is an abi3 extension, so the system python3 can import it.
#
# Own-path detection, per shell (verified with bash 3.2 / zsh 5.9):
#   sourced from bash (incl. bash-as-sh): BASH_SOURCE holds the script path
#   sourced from zsh:                     $0 holds the script path
#   executed under sh/bash:               BASH_SOURCE == $0 -> refuse
#   POSIX sh without BASH_SOURCE (e.g. dash): undeterminable -> refuse
# A refusal never guesses a srcroot from an empty BASH_SOURCE; it tells the
# user to run 'make' at the repository root and source the script from there.
# Direct execution under zsh is indistinguishable from sourcing in a POSIX
# script; it merely exports into the executing process and exits harmlessly.

_frida_env_self=$0
if [ "${BASH_SOURCE+set}" = set ] && [ -n "$BASH_SOURCE" ]; then
    if [ "$BASH_SOURCE" = "$0" ]; then
        echo "frida_env.sh: executed, not sourced; cd to the repository root, run 'make' there, and source this script: '. tools/protect/frida_env.sh'" >&2
        return 1 2>/dev/null || exit 1
    fi
    _frida_env_self=$BASH_SOURCE
elif [ -n "${ZSH_VERSION:-}" ]; then
    # zsh keeps $0 at the sourced file even inside functions; the ${(%):-%x}
    # expansion is zsh-only, so it is reached through eval to stay POSIX-parseable.
    _frida_env_self=$(eval 'printf %s "${(%):-%x}"')
fi

case $_frida_env_self in
    frida_env.sh|*/frida_env.sh) ;;
    *)
        echo "frida_env.sh: cannot determine this script's own path (BASH_SOURCE is unset and \$0 is '$_frida_env_self'); cd to the repository root, run 'make' there, and source this script from the repository root: '. tools/protect/frida_env.sh'" >&2
        return 1 2>/dev/null || exit 1
        ;;
esac

_script_dir=$(CDPATH='' cd -- "$(dirname -- "$_frida_env_self")" && pwd) || return 1
_srcroot=$(CDPATH='' cd -- "$_script_dir/../.." && pwd) || return 1

_py_pkg_dir="$_srcroot/build/subprojects/frida-python"
if [ ! -f "$_py_pkg_dir/frida/__init__.py" ]; then
    echo "frida_env.sh: $_py_pkg_dir/frida is missing; run 'make' at $_srcroot (the repository root) first" >&2
    return 1 2>/dev/null || exit 1
fi
export PYTHONPATH="$_py_pkg_dir${PYTHONPATH:+:$PYTHONPATH}"
