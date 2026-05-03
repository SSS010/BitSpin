"""
BitSpin — консольный слот в терминале (rich TUI).
"""

from __future__ import annotations

import json
import queue
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from pynput import keyboard
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# --- Константы игры ---

DATA_FILE = Path(__file__).resolve().parent / "bitspin_data.json"

SYMBOL_MULT = {
    "🍒": 2,
    "🍋": 5,
    "🍇": 10,
    "💎": 50,
    "7️⃣": 100,
}

SYMBOL_POOL = ["🍒", "🍋", "🍇", "💎", "7️⃣"]

# Веса для выпадения (чем больше — тем чаще)
SYMBOL_WEIGHTS = [45, 28, 15, 8, 4]

START_BALANCE = 1000
DEFAULT_BET = 10

REEL_STOP_TIMES = (1.0, 1.8, 2.5)

# Анимация
FLASH_FRAMES = 16
WIN_BORDER_STYLES = ("green", "gold1")


def weighted_random_symbol() -> str:
    return random.choices(SYMBOL_POOL, weights=SYMBOL_WEIGHTS, k=1)[0]


@dataclass
class SpinAnimation:
    """Состояние анимации барабанов."""

    started_at: float
    outcomes: tuple[str, str, str]
    # Позиция «ленты» (float для суб-пиксельного замедления визуально через int)
    positions: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    velocities: list[float] = field(default_factory=lambda: [24.0, 24.0, 24.0])
    stopped: list[bool] = field(default_factory=lambda: [False, False, False])

    tape_length: int = field(init=False)

    def __post_init__(self) -> None:
        self.tape_length = len(SYMBOL_POOL)
        # Случайный фазовый сдвиг, чтобы полосы не были синхронны
        for i in range(3):
            self.positions[i] = random.uniform(0, self.tape_length)

    def _target_index(self, reel: int) -> int:
        sym = self.outcomes[reel]
        return SYMBOL_POOL.index(sym)

    def tick(self, now: float) -> None:
        dt = 0.05  # шаг логики (~20 Hz), скорости подобраны под визуал
        for i in range(3):
            if self.stopped[i]:
                continue
            elapsed = now - self.started_at
            stop_at = REEL_STOP_TIMES[i]
            remaining = stop_at - elapsed

            if remaining <= 0:
                # Жёсткая стыковка на целевой символ по центру
                tgt = self._target_index(i)
                base = int(round(self.positions[i])) % self.tape_length
                # Ближайшая позиция с нужным символом на центральной линии
                diff = (tgt - base) % self.tape_length
                self.positions[i] = float(int(round(self.positions[i])) + diff)
                self.stopped[i] = True
                self.velocities[i] = 0.0
                continue

            # Инерция: чем ближе к остановке, тем медленнее
            t = 1.0 - (remaining / stop_at)
            ease = (1.0 - t) ** 2  # замедление к концу
            max_v = 22.0 + 8.0 * ease
            min_v = 0.9 + 4.0 * (remaining / stop_at) ** 2
            target_v = max(min_v, min(max_v, 14.0 * (remaining / stop_at) ** 0.55))

            # Сглаживание скорости
            self.velocities[i] += (target_v - self.velocities[i]) * 0.25
            self.positions[i] += self.velocities[i] * dt

            # не даём уйти в отрицательные позиции бесконечно
            while self.positions[i] >= self.tape_length:
                self.positions[i] -= self.tape_length


class SlotMachine:
    """Логика слота: баланс, ставка, расчёт выигрыша, сохранение."""

    def __init__(self) -> None:
        self.balance = START_BALANCE
        self.bet = DEFAULT_BET
        self.last_win = 0
        self.last_symbols: tuple[str, str, str] = ("🍒", "🍋", "🍇")
        self.load()

    def load(self) -> None:
        if not DATA_FILE.is_file():
            return
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            self.balance = int(data.get("balance", START_BALANCE))
            self.bet = int(data.get("bet", DEFAULT_BET))
            self.last_win = int(data.get("last_win", 0))
            ls = data.get("last_symbols")
            if isinstance(ls, list) and len(ls) == 3:
                self.last_symbols = (ls[0], ls[1], ls[2])
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass

    def save(self) -> None:
        payload = {
            "balance": self.balance,
            "bet": self.bet,
            "last_win": self.last_win,
            "last_symbols": list(self.last_symbols),
        }
        try:
            DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def can_spin(self) -> bool:
        return self.balance >= self.bet

    def prepare_spin(self) -> tuple[str, str, str] | None:
        if not self.can_spin():
            return None
        self.balance -= self.bet
        self.last_win = 0
        outcomes = (weighted_random_symbol(), weighted_random_symbol(), weighted_random_symbol())
        self.save()
        return outcomes

    def settle(self, symbols: tuple[str, str, str]) -> None:
        self.last_symbols = symbols
        if symbols[0] == symbols[1] == symbols[2]:
            mult = SYMBOL_MULT[symbols[0]]
            self.last_win = self.bet * mult
            self.balance += self.last_win
        else:
            self.last_win = 0
        self.save()


# --- Отрисовка ---


def symbol_at_position(pos: float, row_offset: int) -> str:
    """row_offset: -1 верх, 0 центр, +1 низ относительно текущей позиции ленты."""
    idx = (int(pos) + row_offset) % len(SYMBOL_POOL)
    return SYMBOL_POOL[idx]


def render_reel_cell(center_sym: str, top_sym: str, bot_sym: str) -> Panel:
    inner = Table.grid(padding=(0, 1))
    inner.add_row(Align.center(Text(top_sym, style="dim")))
    inner.add_row(Align.center(Text(center_sym, style="bold")))
    inner.add_row(Align.center(Text(bot_sym, style="dim")))
    return Panel(
        inner,
        box=box.ROUNDED,
        padding=(0, 1),
        width=11,
    )


def render_slot_machine(
    anim: SpinAnimation | None,
    settled_symbols: tuple[str, str, str],
    flash_phase: int,
    win_active: bool,
) -> tuple[Panel, str]:
    """
    Возвращает основную панель автомата и строку стиля рамки для Panel.
    flash_phase используется для мигания при выигрыше.
    """
    reels: list[Panel] = []
    border_pick = 0

    if anim is not None:
        for i in range(3):
            pos = anim.positions[i]
            top_s = symbol_at_position(pos, -1)
            mid_s = symbol_at_position(pos, 0)
            bot_s = symbol_at_position(pos, 1)
            reels.append(render_reel_cell(mid_s, top_s, bot_s))
    else:
        for sym in settled_symbols:
            reels.append(render_reel_cell(sym, symbol_at_position(0, -1), symbol_at_position(0, 1)))

    columns = Columns(reels, equal=True, expand=False)

    win_line = Text()
    if win_active:
        border_pick = (flash_phase // 2) % 2
        styles = ("blink bold green", "blink bold gold1")
        win_line.append("★ ТРИ В РЯД! Выигрыш начислен! ★\n", style=styles[flash_phase % 2])

    body = Group(
        Align.center(columns),
        Align.center(Text("")),
        Align.center(win_line) if win_active else Text(""),
    )

    border_style = WIN_BORDER_STYLES[border_pick] if win_active else "gold1"

    panel = Panel(
        Align.center(body),
        title="[bold gold1]🎰 BitSpin CLI 🎰[/bold gold1]",
        subtitle_align="center",
        border_style=border_style,
        padding=(1, 2),
        width=52,
    )
    return panel, border_style


def status_bar(balance: int, bet: int, last_win: int) -> Text:
    t = Text()
    t.append("[Баланс: ", style="cyan")
    t.append(str(balance), style="bold white")
    t.append("] ", style="cyan")
    t.append("| ", style="dim")
    t.append("[Ставка: ", style="magenta")
    t.append(str(bet), style="bold white")
    t.append("] ", style="magenta")
    t.append("| ", style="dim")
    t.append("[Последний выигрыш: ", style="green")
    t.append(str(last_win), style="bold white")
    t.append("]", style="green")
    return t


def full_layout(
    machine: SlotMachine,
    anim: SpinAnimation | None,
    flash_phase: int,
    win_flash: bool,
) -> Group:
    syms = machine.last_symbols
    panel, _ = render_slot_machine(anim, syms, flash_phase, win_flash)
    return Group(
        Align.center(panel),
        Align.center(Text("")),
        Align.center(status_bar(machine.balance, machine.bet, machine.last_win)),
        Align.center(Text("Enter — крутить   Q — выйти", style="dim")),
    )


def run() -> None:
    console = Console()
    machine = SlotMachine()
    key_queue: queue.Queue[str] = queue.Queue()

    def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
        try:
            if key == keyboard.Key.enter:
                key_queue.put("enter")
            elif key == keyboard.KeyCode.from_char("q") or key == keyboard.KeyCode.from_char("Q"):
                key_queue.put("q")
        except (AttributeError, ValueError):
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    spinning = False
    anim: SpinAnimation | None = None
    pending_outcomes: tuple[str, str, str] | None = None
    win_flash_frames = 0
    flash_phase = 0
    running = True

    try:
        with Live(
            full_layout(machine, None, 0, False),
            console=console,
            refresh_per_second=24,
            transient=False,
            screen=True,
        ) as live:
            last_tick = time.monotonic()

            while running:
                now = time.monotonic()
                # неблокирующая обработка клавиш
                try:
                    while True:
                        k = key_queue.get_nowait()
                        if k == "q":
                            running = False
                            break
                        if k == "enter" and not spinning:
                            if machine.can_spin():
                                prep = machine.prepare_spin()
                                if prep:
                                    pending_outcomes = prep
                                    spinning = True
                                    anim = SpinAnimation(time.monotonic(), prep)
                                    win_flash_frames = 0
                            break
                except queue.Empty:
                    pass

                if not running:
                    break

                if spinning and anim:
                    # несколько тиков анимации за кадр, если отстали
                    while now - last_tick > 0.03:
                        anim.tick(last_tick)
                        last_tick += 0.03
                    anim.tick(now)
                    last_tick = now

                    if all(anim.stopped):
                        assert pending_outcomes is not None
                        machine.settle(pending_outcomes)
                        pending_outcomes = None
                        spinning = False
                        anim = None
                        if machine.last_win > 0:
                            win_flash_frames = FLASH_FRAMES
                            flash_phase = 0

                if win_flash_frames > 0:
                    flash_phase += 1
                    win_flash_frames -= 1

                win_show = win_flash_frames > 0 and machine.last_win > 0
                live.update(full_layout(machine, anim, flash_phase, win_show))

                time.sleep(1 / 60)
    finally:
        listener.stop()


if __name__ == "__main__":
    run()
