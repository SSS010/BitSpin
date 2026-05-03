"""Game logic and persistence for BitSpin."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Final

DATA_FILENAME: Final[str] = "bitspin_data.json"

# Symbol → payout multiplier (on triple match).
SYMBOL_MULTIPLIERS: Final[dict[str, int]] = {
    "🍒": 2,
    "🍋": 5,
    "🍇": 10,
    "💎": 50,
    "7️⃣": 100,
}

# Order used on physical reel strips and weighted picks.
SYMBOL_ORDER: Final[tuple[str, ...]] = tuple(SYMBOL_MULTIPLIERS.keys())

# Relative weights (higher = more frequent). Tune rarity vs payout.
SYMBOL_WEIGHTS: Final[tuple[int, ...]] = (42, 28, 18, 9, 3)


@dataclass
class SpinOutcome:
    """Result of a completed spin round."""

    reels: tuple[str, str, str]
    win_amount: int
    is_jackpot_line: bool


class SlotMachine:
    """Weighted reels, balance, bet, and JSON persistence."""

    def __init__(
        self,
        data_path: str | Path | None = None,
        *,
        start_balance: int = 1000,
        bet: int = 10,
    ) -> None:
        self._path = Path(data_path or DATA_FILENAME)
        self.bet = bet
        self.last_win = 0
        self.balance = start_balance
        self.load()

    def load(self) -> None:
        if not self._path.is_file():
            self.save()
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            bal = int(raw.get("balance", self.balance))
            self.balance = max(0, bal)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    def save(self) -> None:
        payload = {"balance": self.balance}
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def can_spin(self) -> bool:
        return self.balance >= self.bet

    def weighted_random_symbol(self) -> str:
        return random.choices(SYMBOL_ORDER, weights=SYMBOL_WEIGHTS, k=1)[0]

    def draw_result_symbols(self) -> tuple[str, str, str]:
        return (
            self.weighted_random_symbol(),
            self.weighted_random_symbol(),
            self.weighted_random_symbol(),
        )

    def evaluate_line(self, reels: tuple[str, str, str]) -> SpinOutcome:
        a, b, c = reels
        win = 0
        jackpot = False
        if a == b == c:
            mult = SYMBOL_MULTIPLIERS[a]
            win = self.bet * mult
            jackpot = a == "7️⃣"
        return SpinOutcome(reels=reels, win_amount=win, is_jackpot_line=jackpot)

    def apply_spin_cost(self) -> None:
        self.balance -= self.bet
        self.last_win = 0
        self.save()

    def apply_win(self, amount: int) -> None:
        self.last_win = amount
        self.balance += amount
        self.save()
