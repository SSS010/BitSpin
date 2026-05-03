"""
BitSpin — консольный игровой автомат на Rich с неблокирующим вводом (pynput).
"""

from __future__ import annotations

import random
import sys
import threading
import time
from queue import Empty, Queue
from typing import Final

from pynput import keyboard
from rich.live import Live

from render import (
    WIN_BORDER_GOLD,
    WIN_BORDER_GREEN,
    build_main_panel,
    build_message_line,
    build_reels_table,
)
from slot_machine import SYMBOL_ORDER, SlotMachine

STOP_TIMES: Final[tuple[float, float, float]] = (1.0, 1.8, 2.5)
SPIN_SPEED_MAX: Final[float] = 24.0
SPIN_SPEED_MIN: Final[float] = 0.32
FLASH_SECONDS: Final[float] = 0.85
BLINK_PERIOD: Final[float] = 0.12

# Барабан: повторяющаяся лента для циклической прокрутки.
REEL_STRIP: Final[list[str]] = list(SYMBOL_ORDER) * 16


def lock_scroll(scroll: int, target: str, strip: list[str]) -> int:
    """Минимальный неотрицательный шаг вперёд до совпадения символа на линии."""
    length = len(strip)
    for step in range(length):
        s = scroll + step
        if strip[s % length] == target:
            return s
    return scroll


def visible_rows_for_scrolls(scroll: tuple[int, int, int]) -> tuple[tuple[str, str, str], ...]:
    """Три строки (верх, линия, низ) для трёх барабанов."""
    length = len(REEL_STRIP)
    tops = []
    mids = []
    bots = []
    for sc in scroll:
        tops.append(REEL_STRIP[(sc - 1) % length])
        mids.append(REEL_STRIP[sc % length])
        bots.append(REEL_STRIP[(sc + 1) % length])
    return (tuple(tops), tuple(mids), tuple(bots))


def run_game() -> None:
    machine = SlotMachine()

    keys: Queue[str] = Queue()
    stop_flag = threading.Event()

    def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key == keyboard.Key.enter:
            keys.put("spin")
        elif key == keyboard.Key.esc:
            keys.put("quit")
        elif getattr(key, "char", None) in ("q", "Q"):
            keys.put("quit")

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    spinning = False
    spin_start = 0.0
    final_symbols = ("🍒", "🍒", "🍒")
    scroll = [0, 0, 0]
    acc = [0.0, 0.0, 0.0]
    reel_done = [False, False, False]

    flash_until = 0.0
    flash_win: tuple[int, str] | None = None
    user_message: str | None = None

    clock = time.perf_counter
    last_frame = clock()

    def poll_keys() -> None:
        nonlocal spinning, scroll, acc, reel_done, spin_start, final_symbols
        nonlocal flash_until, flash_win, user_message, last_frame

        try:
            while True:
                cmd = keys.get_nowait()
                if cmd == "quit":
                    stop_flag.set()
                    return
                if cmd != "spin":
                    continue
                if spinning:
                    continue
                if flash_until > clock():
                    continue
                if not machine.can_spin():
                    user_message = "Недостаточно средств для ставки."
                    continue
                user_message = None

                machine.apply_spin_cost()
                final_symbols = machine.draw_result_symbols()

                spinning = True
                spin_start = clock()
                last_frame = spin_start
                scroll = [random.randrange(0, len(REEL_STRIP)) for _ in range(3)]
                acc = [0.0, 0.0, 0.0]
                reel_done = [False, False, False]
        except Empty:
            pass

    def advance_physics(now: float, dt: float) -> None:
        nonlocal spinning, scroll, acc, reel_done, spin_start, final_symbols
        nonlocal flash_until, flash_win

        if not spinning:
            return

        elapsed_spin = now - spin_start
        all_done = True

        for i in range(3):
            if reel_done[i]:
                continue
            all_done = False
            stop_at = STOP_TIMES[i]

            if now >= spin_start + stop_at:
                scroll[i] = lock_scroll(scroll[i], final_symbols[i], REEL_STRIP)
                reel_done[i] = True
                acc[i] = 0.0
                continue

            ratio = min(1.0, elapsed_spin / stop_at)
            speed = SPIN_SPEED_MIN + (SPIN_SPEED_MAX - SPIN_SPEED_MIN) * (1.0 - ratio) ** 2
            acc[i] += speed * dt
            while acc[i] >= 1.0:
                scroll[i] += 1
                acc[i] -= 1.0

        if all_done:
            spinning = False
            outcome = machine.evaluate_line(final_symbols)
            if outcome.win_amount > 0:
                machine.apply_win(outcome.win_amount)
                flash_win = (outcome.win_amount, final_symbols[0])
                flash_until = clock() + FLASH_SECONDS
            else:
                flash_win = None

    def border_and_blink(now: float) -> tuple[str, bool]:
        """Цвет рамки и фаза мигания текста выигрыша."""
        if flash_win is None or now > flash_until:
            return WIN_BORDER_GOLD, True
        toggle = int(now / BLINK_PERIOD) % 2 == 0
        border = WIN_BORDER_GREEN if toggle else WIN_BORDER_GOLD
        return border, toggle

    try:
        initial_reels = visible_rows_for_scrolls((4, 9, 14))
        initial_panel = build_main_panel(
            reels_panel=build_reels_table(initial_reels, highlight_middle=True),
            machine=machine,
            win_info=None,
            message_line=None,
            border_style=WIN_BORDER_GOLD,
            win_blink_phase=True,
        )
        with Live(initial_panel, refresh_per_second=30, screen=True) as live:
            while not stop_flag.is_set():
                now = clock()
                dt = max(0.0, now - last_frame)
                last_frame = now

                poll_keys()
                advance_physics(now, dt)

                border_style, win_phase = border_and_blink(now)
                msg = build_message_line(user_message) if user_message else None

                reels = visible_rows_for_scrolls((scroll[0], scroll[1], scroll[2]))
                reels_panel = build_reels_table(reels, highlight_middle=True)

                win_visible = flash_win if (flash_win and now <= flash_until) else None

                live.update(
                    build_main_panel(
                        reels_panel=reels_panel,
                        machine=machine,
                        win_info=win_visible,
                        message_line=msg,
                        border_style=border_style,
                        win_blink_phase=win_phase,
                    )
                )

                if flash_win and now > flash_until:
                    flash_win = None

                time.sleep(1 / 60)
    finally:
        listener.stop()


if __name__ == "__main__":
    try:
        run_game()
    except KeyboardInterrupt:
        sys.exit(0)
