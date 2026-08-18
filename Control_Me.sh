#!/usr/bin/env bash

# Resolve the directory of this script (handles symlinks)
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# Allow overriding project dir; default to the script's directory
PROJECT_DIR="${SCRLLM_PROJECT_DIR:-$SCRIPT_DIR}"

# Move to project directory so relative paths behave consistently
cd "$PROJECT_DIR" || {
  echo "Failed to cd to project directory: $PROJECT_DIR"
  exit 1
}

# Configuration (overridable via env)

# lock file
LOCKFILE="${SCRLLM_LOCKFILE:-/tmp/control_me.lock}"

# Virtual environment directory (defaults to project-local .venv/)
# Trailing slash preserved to keep relative semantics if overridden
DEFAULT_VENV="${PROJECT_DIR}/.venv/"
VENVPATH="${VENVPATH:-$DEFAULT_VENV}"

# Main and requirements paths (relative to the project dir by default)
MAIN="${SCRLLM_MAIN:-$PROJECT_DIR/main.py}"
REQUIREMENTS="${SCRLLM_REQUIREMENTS:-$PROJECT_DIR/requirements.txt}"
LOGFILE="${SCRLLM_LOGFILE:-$PROJECT_DIR/output.log}"

check_running() {
    # $1: pattern to search for
    if hash pgrep &>/dev/null; then
        pgrep -f "$1" &>/dev/null
    elif [[ "$OSTYPE" == cygwin* || "$OSTYPE" == msys* ]]; then
        # Git Bash/Cygwin fallback
        find /proc -maxdepth 1 -type d -regextype sed -regex '^.\+/[0-9]\+' \
          -exec bash -c 'xargs -0 < {}/cmdline' \; | grep -F "$1" &>/dev/null
    else
        ps -ef | grep -F "$1" | grep -v grep &>/dev/null
    fi
}

pause_script() {
    if [ -z "$SCRLLM_SYSTEMD_UNIT" ]; then
        echo "An error occurred. Pausing the script. Press [Enter] to continue..."
        [ -f "$LOCKFILE" ] && rm -f "$LOCKFILE"
        read
    fi
    exit 1
}

detect_python() {
    if command -v python3 >/dev/null 2>&1; then
        echo "python3"
    elif command -v python >/dev/null 2>&1; then
        echo "python"
    elif command -v py >/dev/null 2>&1; then
        # Windows Python launcher
        echo "py -3"
    else
        return 1
    fi
}

# Prepare env file
if [[ -n "$SCRLLM_ENV_FILE" && ! -e "$SCRLLM_ENV_FILE" ]]; then
    [ ! -e "${SCRLLM_ENV_FILE%/*}" ] && mkdir -p "${SCRLLM_ENV_FILE%/*}"
    touch "$SCRLLM_ENV_FILE"
fi

# -------------------------------
# Locking (skip when run from systemd)
# -------------------------------
if [ -z "$SCRLLM_SYSTEMD_UNIT" ]; then
    if [ -e "$LOCKFILE" ]; then
        echo "Another instance is already running. Exiting."
        pause_script
    else
        touch "$LOCKFILE" || { echo "Failed to create lockfile: $LOCKFILE"; pause_script; }
        # Ensure lock removal on exit
        trap 'status=$?; [ -f "$LOCKFILE" ] && rm -f "$LOCKFILE"; exit $status' EXIT
    fi
fi

# Ensure venv exists
PY_CMD="$(detect_python)" || { echo "Python not found on PATH."; pause_script; }

if [ ! -d "${VENVPATH%/}" ]; then
    echo "Virtual environment not found at ${VENVPATH}. Creating one..."
    mkdir -p "${VENVPATH%/}" || { echo "Failed to create venv directory: ${VENVPATH}"; pause_script; }
    # shellcheck disable=SC2086
    $PY_CMD -m venv "${VENVPATH%/}" || { echo "Failed to create virtual environment."; pause_script; }
fi

# Activate venv
if [[ "$OSTYPE" == cygwin* || "$OSTYPE" == msys* ]]; then
    [ -z "$SCREENSHOT_DIRECTORY" ] && SCREENSHOT_DIRECTORY="${HOME}/Pictures/Screenshots"
    ACTIVATE="${VENVPATH%/}/Scripts/activate"
else
    ACTIVATE="${VENVPATH%/}/bin/activate"
fi

# shellcheck disable=SC1090
source "$ACTIVATE" || { echo "Failed to activate virtual environment at $ACTIVATE"; pause_script; }

# Install requirements (if present)
if [ -f "$REQUIREMENTS" ]; then
    if [ -z "$SCRLLM_SYSTEMD_UNIT" ]; then
        python -m pip install -r "$REQUIREMENTS" >/dev/null 2>&1
    else
        python -m pip install -r "$REQUIREMENTS"
    fi
    if [ $? -ne 0 ]; then
        echo "Failed to install required Python packages from $REQUIREMENTS."
        pause_script
    fi
fi

# Prevent duplicate runs (when not systemd)
if [ -z "$SCRLLM_SYSTEMD_UNIT" ]; then
    RUN_PATTERN="$MAIN --control_me"
    if check_running "$RUN_PATTERN"; then
        echo "Python script is already running. Exiting."
        rm -f "$LOCKFILE"
        exit 1
    fi
fi

# Launch
if [ -z "$SCRLLM_SYSTEMD_UNIT" ]; then
    nohup python -u "$MAIN" --control_me > "$LOGFILE" 2>&1 &
    rc=$?
else
    python -u "$MAIN" --control_me
    rc=$?
fi

# Post-launch check (non-systemd)
if [ -z "$SCRLLM_SYSTEMD_UNIT" ]; then
    if [ $rc -eq 0 ]; then
        echo "Python script started successfully. Check '$LOGFILE' for output."
    else
        echo "Failed to start the Python script."
        pause_script
    fi
fi