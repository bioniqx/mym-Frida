#!/bin/sh
#
# test_frida_env.sh — tests for frida_env.sh (slice F1).
#
# Run: sh tools/protect/test_frida_env.sh   (prints PASS, exits 0 on success)
#
# Each case sources a sandbox copy of frida_env.sh in a throwaway tree so the
# test never depends on the real worktree having a build/ directory.

set -u

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
script="$here/frida_env.sh"
pydir="build/subprojects/frida-python"
keep="/f1_keep"
tmpbase="${TMPDIR:-/tmp}"

sandboxes=""
mk_sandbox() {
    # $1: yes -> create $pydir/frida/__init__.py inside the sandbox
    _sb=$(mktemp -d "$tmpbase/frida_env_test.XXXXXX") || exit 1
    _sb=$(CDPATH='' cd -- "$_sb" && pwd) || return 1
    sandboxes="$_sb $sandboxes"
    mkdir -p "$_sb/tools/protect" || return 1
    cp "$script" "$_sb/tools/protect/frida_env.sh" || return 1
    if [ "$1" = yes ]; then
        mkdir -p "$_sb/$pydir/frida" || return 1
        : > "$_sb/$pydir/frida/__init__.py" || return 1
    fi
    BUILD_SANDBOX=$_sb
}

cleanup() {
    # sandbox dirs come from mktemp under tmpbase (no spaces)
    # shellcheck disable=SC2086
    rm -rf $sandboxes
}
trap cleanup EXIT

fails=0
ok() { echo "ok: $1"; }
bad() {
    echo "FAIL: $1"
    fails=$((fails + 1))
}
want() { # $1 case name, $2 got, $3 expected
    if [ "$2" = "$3" ]; then ok "$1"; else bad "$1: got [$2], want [$3]"; fi
}
contains() { # $1 case name, $2 haystack, $3 needle
    case $2 in
    *$3*) ok "$1" ;;
    *) bad "$1: [$3] not found in [$2]" ;;
    esac
}
lacks() { # $1 case name, $2 haystack, $3 forbidden needle
    case $2 in
    *$3*) bad "$1: forbidden [$3] found in [$2]" ;;
    *) ok "$1" ;;
    esac
}
want_status_nonzero() { # $1 case name, $2 status
    case $2 in
    0) bad "$1: expected non-zero exit, got 0" ;;
    *) ok "$1 (exit $2)" ;;
    esac
}

# --- 1/2: bash sourcing, build present, from root cwd and from a subdir ------
mk_sandbox yes
sb=$BUILD_SANDBOX
if [ -f "$sb/$pydir/frida/__init__.py" ]; then
    ok "bash setup: sandbox build tree present"
else
    bad "bash setup: sandbox build tree missing"
fi

got=$(cd "$sb" || exit 90
    unset PYTHONPATH
    . ./tools/protect/frida_env.sh
    echo "st=$? PP=$PYTHONPATH")
want "bash source from root cwd exports PYTHONPATH" \
    "$got" "st=0 PP=$sb/$pydir"

got=$(cd "$sb/tools/protect" || exit 90
    PYTHONPATH=$keep
    export PYTHONPATH
    . ./frida_env.sh
    echo "st=$? PP=$PYTHONPATH")
want "bash source from subdir cwd prepends to PYTHONPATH" \
    "$got" "st=0 PP=$sb/$pydir:$keep"

# --- 3/4: zsh sourcing, build present, from root cwd and from a subdir -------
got=$(cd "$sb" && zsh -f -c '
    unset PYTHONPATH
    . ./tools/protect/frida_env.sh
    echo "st=$? PP=$PYTHONPATH"')
want "zsh source from root cwd exports PYTHONPATH" \
    "$got" "st=0 PP=$sb/$pydir"

got=$(cd "$sb/tools/protect" && zsh -f -c '
    PYTHONPATH='"$keep"'
    export PYTHONPATH
    . ../protect/frida_env.sh
    echo "st=$? PP=$PYTHONPATH"')
want "zsh source from subdir cwd prepends to PYTHONPATH" \
    "$got" "st=0 PP=$sb/$pydir:$keep"

# --- 5: POSIX sh sourcing (macOS /bin/sh is bash in POSIX mode) ---------------
got=$(cd "$sb" && sh -c '
    unset PYTHONPATH
    . ./tools/protect/frida_env.sh
    echo "st=$? PP=$PYTHONPATH"')
want "sh source from root cwd exports PYTHONPATH" \
    "$got" "st=0 PP=$sb/$pydir"

# --- 6: unset-BASH_SOURCE emulation must fail fast, never guess a srcroot -----
# Emulate a POSIX sh that has no self-location variable (e.g. dash): ksh ships
# with this OS, never sets BASH_SOURCE/ZSH_VERSION, and keeps $0 at the shell
# name when sourcing. (bash 3.2 refuses to unset BASH_SOURCE, and zsh self-
# locates via ${(%):-%x}, so neither of those can reach this branch.)
mkdir -p "$sb/tools/protect/deep" || exit 1
err=$(cd "$sb/tools/protect/deep" && ksh -c '
    unset PYTHONPATH
    . ../frida_env.sh
' 2>&1)
st=$?
want_status_nonzero "unset-BASH_SOURCE emulation exits non-zero" "$st"
contains "unset-BASH_SOURCE emulation error names the failure" \
    "$err" "cannot determine this script's own path"
contains "unset-BASH_SOURCE emulation error reports the unusable \$0" \
    "$err" "\$0 is 'ksh'"
contains "unset-BASH_SOURCE emulation error names the repository root" \
    "$err" "repository root"
lacks "unset-BASH_SOURCE emulation computes no srcroot" "$err" "$pydir"
lacks "unset-BASH_SOURCE emulation does not reach the missing-build check" \
    "$err" "is missing"

# --- 7: direct execution must refuse ------------------------------------------
err=$(cd "$sb" || exit 90
    unset PYTHONPATH
    {
        sh ./tools/protect/frida_env.sh
    } 2>&1)
st=$?
want_status_nonzero "direct execution exits non-zero" "$st"
contains "direct execution error says the script must be sourced" \
    "$err" "executed, not sourced"
lacks "direct execution computes no srcroot" "$err" "$pydir"

# --- 8: missing build must point at the sandbox's own repo root ----------------
mk_sandbox no
sb2=$BUILD_SANDBOX
err=$(cd "$tmpbase" || exit 90
    unset PYTHONPATH
    {
        . "$sb2/tools/protect/frida_env.sh"
    } 2>&1)
st=$?
want_status_nonzero "missing build exits non-zero" "$st"
contains "missing build names the missing path under the correct repo root" \
    "$err" "$sb2/$pydir/frida is missing"
contains "missing build tells the user to run make at that root" \
    "$err" "run 'make' at $sb2"

cleanup
if [ "$fails" -ne 0 ]; then
    echo "$fails case(s) FAILED"
    exit 1
fi
echo "PASS"
