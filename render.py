"""Rich renderables for the BitSpin TUI."""

from __future__ import annotations

from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from slot_machine import SlotMachine

PANEL_TITLE = "[bold gold1] BitSpin CLI [/bold gold1]"

WIN_BORDER_GREEN = "green"
WIN_BORDER_GOLD = "gold1"


def _reel_cell(symbol: str, *, dim: bool = False) -> RenderableType:
    style = "dim" if dim else "bold"
    inner = Text(symbol, style=style, justify="center")
    # Vertical padding reads as “larger” in monospace terminals.
    return Align.center(Text.assemble("\n", inner, "\n"), vertical="middle")


def build_reels_table(
    visible_rows: tuple[tuple[str, str, str], tuple[str, str, str], tuple[str, str, str]],
    *,
    highlight_middle: bool = True,
) -> Panel:
    """Three reels × three rows; middle row is the payline."""
    top, mid, bot = visible_rows
    table = Table.grid(expand=False)
    table.add_column(justify="center", min_width=12)
    table.add_column(justify="center", min_width=12)
    table.add_column(justify="center", min_width=12)

    def row_cells(r: tuple[str, str, str], *, middle: bool) -> tuple[RenderableType, RenderableType, RenderableType]:
        return tuple(_reel_cell(s, dim=not (middle and highlight_middle)) for s in r)

    table.add_row(*row_cells(top, middle=False))
    table.add_row(*row_cells(mid, middle=True))
    table.add_row(*row_cells(bot, middle=False))

    return Panel(
        table,
        box=box.ROUNDED,
        border_style="bright_blue",
        padding=(0, 1),
        title="[bold cyan]Барабаны[/bold cyan]",
        title_align="center",
    )


def build_status_line(machine: SlotMachine) -> Text:
    return Text(
        f"[Баланс: {machine.balance}] | [Ставка: {machine.bet}] | [Последний выигрыш: {machine.last_win}]",
        style="white",
        justify="center",
    )


def build_help_line() -> Text:
    return Text(
        "Enter — крутить   ·   Q — выйти",
        style="dim italic",
        justify="center",
    )


def build_win_line(amount: int, symbol: str, *, bright: bool) -> Text:
    style = "bold green" if bright else "dim green"
    return Text(
        f"ВЫИГРЫШ: +{amount}  ({symbol} × линия)",
        style=style,
        justify="center",
    )


def build_message_line(message: str, *, style: str = "yellow") -> Text:
    return Text(message, style=style, justify="center")


def build_main_panel(
    *,
    reels_panel: RenderableType,
    machine: SlotMachine,
    win_info: tuple[int, str] | None,
    message_line: Text | None,
    border_style: str,
    win_blink_phase: bool,
) -> Panel:
    parts: list[RenderableType] = [
        Align.center(reels_panel),
        Text(""),
        build_status_line(machine),
        Text(""),
        build_help_line(),
    ]
    if win_info is not None:
        amt, sym = win_info
        parts.insert(2, Text(""))
        parts.insert(
            3,
            Align.center(build_win_line(amt, sym, bright=win_blink_phase)),
        )
    if message_line is not None:
        parts.append(Text(""))
        parts.append(Align.center(message_line))

    body = Group(*parts)
    return Panel(
        Align.center(body),
        title=PANEL_TITLE,
        title_align="center",
        border_style=border_style,
        box=box.DOUBLE,
        padding=(1, 2),
    )


