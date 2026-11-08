#!/usr/bin/env python3
"""Conservative Codex Plus planning aid. It recommends; it never calls a model."""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from quota_snapshot import DEFAULT_TTL_SECONDS, read_snapshot, snapshot_path


@dataclass(frozen=True)
class Window:
    remaining: float
    reset_hours: float


def parse_duration(value: str) -> float:
    """Parse durations like 1h4m, 8h17m, 45m, 2d or HH:MM into hours."""
    value = value.strip().lower()
    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ValueError("use HH:MM or a duration such as 1h4m")
        hours, minutes = map(int, parts)
        if minutes >= 60:
            raise ValueError("minutes in HH:MM must be below 60")
        return hours + minutes / 60
    matches = list(re.finditer(r"(\d+(?:\.\d+)?)\s*([dhms])", value))
    if not matches or "".join(m.group(0).replace(" ", "") for m in matches) != value.replace(" ", ""):
        raise ValueError("use a duration such as 1h4m, 8h17m, 45m, or 2d")
    factors = {"d": 24, "h": 1, "m": 1 / 60, "s": 1 / 3600}
    return sum(float(m.group(1)) * factors[m.group(2)] for m in matches)


def _window(remaining: float | None, reset_hours: float | None) -> Window | None:
    if remaining is None or reset_hours is None:
        return None
    if not 0 <= remaining <= 100:
        raise ValueError("remaining percentages must be between 0 and 100")
    if reset_hours < 0:
        raise ValueError("reset time cannot be negative")
    return Window(remaining, reset_hours)


def make_plan(
    primary_remaining: float | None,
    primary_reset_hours: float | None,
    weekly_remaining: float | None,
    weekly_reset_hours: float | None,
    *,
    urgent: bool = False,
    critical: bool = False,
    sol_authorized: bool = False,
    user_authorized_continue: bool = False,
    saved_reset_available: bool = False,
) -> dict:
    primary = _window(primary_remaining, primary_reset_hours)
    weekly = _window(weekly_remaining, weekly_reset_hours)
    plan = {
        "state": "unknown",
        "model": "gpt-6-luna",
        "reasoning": "medium",
        "max_concurrent_agents": 1,
        "fast": "off",
        "action": "Обновить счётчик, если он доступен. Оставить Fast выключенным; использовать Luna Medium и убрать необязательные этапы.",
        "weekly_even_pace_pp_per_day": None,
        "reasons": [],
    }

    if primary is None or weekly is None:
        plan["reasons"].append("Для адаптивного выбора нужны остатки и время сброса обоих окон.")
        return plan

    plan["weekly_even_pace_pp_per_day"] = round(
        weekly.remaining / max(weekly.reset_hours / 24, 1 / 24), 1
    )
    plan["reasons"].append(
        "Равномерный недельный темп — это остаток, делённый на дни до сброса; он не оценивает стоимость задачи или модели."
    )

    if weekly.remaining <= 10 or primary.remaining <= 10:
        if user_authorized_continue:
            plan.update(state="conserve", max_concurrent_agents=0)
            plan["action"] = "Пользователь явно попросил продолжить: выполнить только необходимую одиночную работу на Luna; без агентов, Fast и необязательных прогонов."
            plan["reasons"].append("Остаток одного из окон не выше 10%; продолжение разрешено прямым указанием пользователя.")
        else:
            plan.update(state="stop", max_concurrent_agents=0)
            plan["action"] = "Сохранить checkpoint и отложить новые модельно-затратные этапы до сброса ограничивающего окна."
            plan["reasons"].append("В одном из окон осталось 10% или меньше.")
            if saved_reset_available:
                plan["reasons"].append("Доступен сохранённый reset: предложить его пользователю, но не применять без явного решения.")
        return plan

    if primary.remaining <= 25 and primary.reset_hours <= 1 and not urgent:
        plan.update(state="wait_for_reset", max_concurrent_agents=0)
        plan["action"] = "Если задача терпит, сохранить checkpoint и продолжить после сброса короткого окна. Если нет — выполнить один минимальный шаг на Luna."
        plan["reasons"].append("В коротком окне мало остатка, сброс будет в течение часа.")
        return plan

    plan["state"] = "conserve" if min(primary.remaining, weekly.remaining) <= 50 else "balanced"

    if min(primary.remaining, weekly.remaining) <= 35:
        plan["max_concurrent_agents"] = 0
        plan["action"] = "Продолжать полезную работу координатором на Luna Medium; не запускать новых агентов и необязательных этапов. Перед следующим затратным этапом обновить оба окна."
        plan["reasons"].append("В одном из окон осталось не более 35%.")
    elif min(primary.remaining, weekly.remaining) <= 50:
        plan["max_concurrent_agents"] = 1
        plan["action"] = "Использовать Luna Medium. Убрать необязательное ревью и Astra; делегировать только если это явно сократит общий объём работы."
        plan["reasons"].append("В одном из окон осталось не более 50%.")
    else:
        plan["max_concurrent_agents"] = 2
        plan["action"] = "Начать с Luna Medium. Запускать до двух агентов одновременно только для независимой полезной работы; сохранить недельный запас для следующих задач."
        plan["reasons"].append("Даже полный остаток — общий бюджет на всё время до недельного сброса.")

    if weekly.remaining <= 25:
        plan["reasons"].append(
            "Недельный остаток 25% или ниже сам по себе не останавливает полезную одиночную работу: короткое окно — отдельный лимит, а недельный запас нужно расходовать экономно до его сброса."
        )

    if critical and sol_authorized and min(primary.remaining, weekly.remaining) > 50:
        plan.update(model="gpt-6.1-sol", reasoning="high")
        plan["reasons"].append("Sol выбран только для явно отмеченного критичного решения.")
    elif critical:
        plan["reasons"].append("Критичность отмечена, но Sol остаётся выключенным без прямого подтверждения пользователя о достаточном остатке.")

    if urgent and min(primary.remaining, weekly.remaining) > 50:
        plan["fast"] = "eligible_for_manual_consideration"
        plan["reasons"].append(
            "Fast можно рассмотреть только для срочного этапа, если выигрыш по времени значителен; он расходует больше лимита. Переключить вручную в Codex, затем выключить."
        )
    else:
        plan["reasons"].append("Fast выключен: нет срочности или подтверждённого запаса в обоих окнах.")

    if weekly.reset_hours <= 12:
        plan["reasons"].append("Недельный сброс близко: не останавливать полезную работу автоматически и не ускорять расход только из-за близкого сброса; checkpoint допустим, если конкретная задача может подождать.")
    if primary.reset_hours <= 1:
        plan["reasons"].append("Сброс короткого окна близко, но недельное окно остаётся отдельным ограничением.")
    return plan


def _percent(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a number between 0 and 100") from exc
    if not 0 <= parsed <= 100:
        raise argparse.ArgumentTypeError("value must be between 0 and 100")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="read a fresh sanitized snapshot (stale snapshots fail closed)")
    parser.add_argument("--primary-remaining", type=_percent, help="remaining percent in the short (usually 5-hour) window")
    parser.add_argument("--primary-reset-in", help="reset countdown, e.g. 1h4m")
    parser.add_argument("--weekly-remaining", type=_percent, help="remaining percent in the weekly window")
    parser.add_argument("--weekly-reset-in", help="reset countdown, e.g. 8h17m or 2d")
    parser.add_argument("--urgent", action="store_true", help="the task cannot reasonably wait and latency matters")
    parser.add_argument("--critical", action="store_true", help="the decision has high impact and warrants stronger reasoning")
    parser.add_argument("--sol-authorized", action="store_true", help="the user confirmed sufficient remaining usage for a Sol run")
    parser.add_argument("--user-authorized-continue", action="store_true", help="the user explicitly asked to continue at/below the reserve threshold")
    parser.add_argument("--saved-reset-available", action="store_true", help="the usage meter reports a saved reset; the script will only recommend asking the user")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.snapshot:
            from_snapshot, fresh, age = read_snapshot(args.snapshot, ttl_seconds=DEFAULT_TTL_SECONDS)
            if from_snapshot is None or not fresh:
                print("Состояние: unknown")
                print("Лимит неизвестен или снимок устарел; обновите get_usage_limits и сохраните новый снимок.")
                print("Модель: gpt-6-luna / medium; Fast: off; без необязательных этапов.")
                return 0
            primary_remaining = float(from_snapshot["primaryRemaining"])
            weekly_remaining = float(from_snapshot["weeklyRemaining"])
            primary_reset = max(0, (int(from_snapshot["primaryResetsAt"]) - int(time.time())) / 3600)
            weekly_reset = max(0, (int(from_snapshot["weeklyResetsAt"]) - int(time.time())) / 3600)
            saved_reset_available = bool(from_snapshot.get("savedResetAvailable"))
            print(f"Снимок лимитов обновлён {age // 60} мин. назад.")
        else:
            primary_remaining = args.primary_remaining
            weekly_remaining = args.weekly_remaining
            primary_reset = parse_duration(args.primary_reset_in) if args.primary_reset_in else None
            weekly_reset = parse_duration(args.weekly_reset_in) if args.weekly_reset_in else None
            saved_reset_available = args.saved_reset_available
        plan = make_plan(
            primary_remaining,
            primary_reset,
            weekly_remaining,
            weekly_reset,
            urgent=args.urgent,
            critical=args.critical,
            sol_authorized=args.sol_authorized,
            user_authorized_continue=args.user_authorized_continue,
            saved_reset_available=saved_reset_available,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Состояние: {plan['state']}")
    print(f"Модель по умолчанию: {plan['model']} / {plan['reasoning']}")
    print(f"Параллельных агентов одновременно: не более {plan['max_concurrent_agents']}")
    print(f"Fast: {plan['fast']}")
    if plan["weekly_even_pace_pp_per_day"] is not None:
        print(f"Справочный равномерный темп недельного остатка: {plan['weekly_even_pace_pp_per_day']} п.п. за 24 часа")
    print(f"Действие: {plan['action']}")
    for reason in plan["reasons"]:
        print(f"- {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
