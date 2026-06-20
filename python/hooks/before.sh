#!/bin/sh
# before.sh — session hook for the python-sandbox nono pack
#
# Runs OUTSIDE the sandbox with host privileges before the sandboxed process
# starts. Receives: NONO_SESSION_ID, NONO_WORKDIR, NONO_ENV_FILE.
#
# The profile's set_vars redirect several cache and runtime directories to
# paths under $PREFIX/tmp. Those directories must exist before the sandboxed
# process starts, because some libraries (notably Jupyter) probe for them
# rather than creating them lazily.
#
# $PREFIX is not directly available here — it is a build-var expanded inside
# nono's profile runtime, not a hook environment variable. Instead we read
# the value of TMPDIR that set_vars will inject, which is always $PREFIX/tmp.
# We derive $PREFIX by stripping the trailing /tmp component.
#
# If TMPDIR is not set or doesn't end in /tmp, we skip directory creation
# silently — the sandboxed process can still create them via the $PREFIX
# write grant.

set -e

if [ -z "$TMPDIR" ]; then
    exit 0
fi

# Derive PREFIX from TMPDIR ($PREFIX/tmp → $PREFIX)
case "$TMPDIR" in
    */tmp)
        PREFIX="${TMPDIR%/tmp}"
        ;;
    *)
        # Unexpected shape — don't guess; let the sandboxed process create dirs.
        exit 0
        ;;
esac

# Pre-create directories that set_vars points at.
# exist_ok equivalent: mkdir -p is idempotent.
mkdir -p \
    "$PREFIX/tmp" \
    "$PREFIX/tmp/pip" \
    "$PREFIX/tmp/jupyter/runtime" \
    "$PREFIX/tmp/jupyter/config" \
    "$PREFIX/tmp/matplotlib" \
    "$PREFIX/tmp/numba" \
    "$PREFIX/tmp/triton" \
    "$PREFIX/tmp/torch_inductor" \
    "$PREFIX/__pycache__" \
    "$PREFIX/share/jupyter"
