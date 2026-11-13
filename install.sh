#!/bin/sh
# One-command installer for Adaptive Codex on macOS and Linux.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

fail() {
    printf 'Ошибка: %s\n' "$1" >&2
    exit 1
}

PYTHON_BIN=${PYTHON:-}
for candidate in "$PYTHON_BIN" python3.14 python3.13 python3.12 python3.11 python3; do
    [ -n "$candidate" ] || continue
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys,tomllib; raise SystemExit(sys.version_info < (3,11))' >/dev/null 2>&1; then
        PYTHON_BIN=$(command -v "$candidate")
        break
    fi
done
[ -n "$PYTHON_BIN" ] || fail 'нужен Python 3.11+ с tomllib. Установите Python и повторите ./install.sh.'

command -v codex >/dev/null 2>&1 || fail 'Codex CLI не найден. Установите или запустите Codex Desktop с CLI и повторите.'

STEP='установки инструкций и инструментов'
on_error() {
    status=$?
    trap - EXIT HUP INT TERM
    [ "$status" -ne 0 ] || return 0
    printf '\nОшибка на этапе %s (код %s). Запустите ./install.sh повторно: уже выполненные шаги безопасно повторяются.\n' "$STEP" "$status" >&2
    exit "$status"
}
trap on_error HUP INT TERM
trap on_error EXIT

printf 'Будут установлены инструкции, 6 ролей, 3 skills и служебные инструменты в CODEX_HOME.\n'
"$PYTHON_BIN" "$ROOT/scripts/install.py" --dry-run
printf '\nПодключится локальный plugin adaptive-quota с SessionStart hook.\n'
printf 'Продолжить? [y/N] '
IFS= read -r answer || answer=
case "$answer" in
    y|Y|yes|YES|д|Д|да|ДА) ;;
    *) printf 'Установка отменена.\n'; exit 0 ;;
esac

"$PYTHON_BIN" "$ROOT/scripts/install.py"

STEP='подключения локального marketplace'
codex plugin marketplace add "$ROOT"

STEP='установки плагина'
if codex plugin list 2>/dev/null | awk '$1 == "adaptive-quota@adaptive-codex" && $2 ~ /installed/ && $3 == "enabled" { found=1 } END { exit !found }'; then
    printf 'Плагин adaptive-quota уже установлен и включён.\n'
else
    codex plugin add adaptive-quota@adaptive-codex
fi

trap - EXIT HUP INT TERM
printf '\nГотово. Перезапустите Codex и проверьте SessionStart hook в Settings → Hooks перед первым использованием.\n'
