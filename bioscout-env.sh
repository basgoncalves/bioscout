# bioscout-env.sh — the part `python -m bioscout` cannot do for you.
#
#   source /c/Git/bioscout/bioscout-env.sh
#   bioscout-env            # create if missing, install, ACTIVATE
#   bioscout-env --check    # report only
#
# Put the `source` line in your ~/.bashrc to have it always available.
#
# Why a shell function and not a Python flag: activating a conda environment
# means editing THIS shell's PATH and variables. A child process — python,
# pip, anything — gets a copy of the environment and cannot write back to its
# parent. So `bioscout --env-create` can build the environment (that is real
# work in a subprocess) but the `conda activate` has to happen in your shell.
# This function runs in your shell, so it can.

bioscout-env() {
    local check_only=0 pyver="3.11"
    while [ $# -gt 0 ]; do
        case "$1" in
            --check)  check_only=1; shift ;;
            --python) pyver="$2"; shift 2 ;;
            -h|--help)
                echo "usage: bioscout-env [--check] [--python 3.11]"; return 0 ;;
            *) echo "bioscout-env: unknown flag $1" >&2; return 2 ;;
        esac
    done

    if ! command -v conda >/dev/null 2>&1; then
        echo "[env] conda is not on PATH." >&2; return 1
    fi

    # Read the version off disk FIRST. Importing bioscout requires its
    # dependencies, which is the very thing that may not be installed yet —
    # so the import is the fallback, not the primary route.
    local want init
    init="$(dirname "${BASH_SOURCE[0]}")/bioscout/__init__.py"
    want="bioscoutv$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$init" 2>/dev/null | head -1)"
    if [ "$want" = "bioscoutv" ]; then
        want=$(python -c "from bioscout.envcheck import expected_env_name as e; print(e())" 2>/dev/null)
    fi
    if [ "$want" = "bioscoutv" ] || [ -z "$want" ]; then
        echo "[env] could not determine the bioscout version." >&2; return 1
    fi

    echo "[env] wanted environment: $want"
    echo "[env] current:            ${CONDA_DEFAULT_ENV:-none}"
    if [ "${CONDA_DEFAULT_ENV:-}" = "$want" ]; then
        echo "[env] already active."; return 0
    fi
    [ "$check_only" = "1" ] && { echo "[env] --check: not activating."; return 0; }

    if ! conda env list | awk '{print $1}' | grep -qx "$want"; then
        echo "[env] creating $want (python $pyver) ..."
        conda create -y -n "$want" "python=$pyver" || return 1
        # Build the env from a subprocess, then activate here.
        python -m bioscout.envcheck --create --python "$pyver" \
            || echo "[env] install reported errors — read the log above" >&2
    fi

    # `conda activate` needs conda's shell hook, which a non-login shell may not
    # have sourced. This is the documented way to get it in a script.
    eval "$(conda shell.bash hook)" || return 1
    conda activate "$want" || return 1
    echo "[env] activated $want"
    python -c "import bioscout; print('[env] bioscout', bioscout.__version__)" 2>/dev/null
}
