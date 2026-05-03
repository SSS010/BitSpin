# BitSpin CLI

**BitSpin** is a terminal slot machine built with Python and [Rich](https://github.com/Textualize/rich). It renders a stylized three-reel machine inside a `Panel`, animates spins with `Live`, saves your balance to JSON, and uses non-blocking keyboard input via `pynput`.

<img width="1108" height="577" alt="Снимок экрана 2026-05-03 120440" src="https://github.com/user-attachments/assets/f0e8f668-f2d2-48e9-9482-b977ba3fcde3" />


## Run & install

| Step | Command |
|------|---------|
| 1. Clone or copy the project | `cd bitspin` |
| 2. Create a virtual environment (recommended) | `python -m venv .venv` |
| 3. Activate it | **Windows (PowerShell):** `.venv\Scripts\Activate.ps1` · **macOS/Linux:** `source .venv/bin/activate` |
| 4. Install dependencies | `pip install -r requirements.txt` |
| 5. Start the game | `python main.py` |

**Requirements:** Python 3.10+ recommended (uses modern typing syntax).

---

## Controls

| Key | Action |
|-----|--------|
| **Enter** | Spin (when idle and you have enough balance) |
| **Q** or **Esc** | Quit |
| *(during spin or win flash)* | Spin is ignored until the animation finishes |

---

## Game rules (summary)

| Setting | Value |
|---------|--------|
| Starting balance | 1000 |
| Bet per spin | 10 |
| Win condition | Same symbol on all three reels (middle payline) |
| Payout | `bet × symbol multiplier` |

Balance is stored in **`bitspin_data.json`** in the current working directory.

---

## Symbol payouts

Triple match on the middle row pays:

| Symbol | Multiplier |
|--------|------------|
| Cherry | ×2 |
| Lemon | ×5 |
| Grapes | ×10 |
| Diamond | ×50 |
| 7️⃣ | ×100 (jackpot line) |

*(Emoji rendering depends on your terminal font.)*

---

## Reel animation

| Reel (left → right) | Stop delay (from spin start) |
|----------------------|------------------------------|
| Left | 1.0 s |
| Middle | 1.8 s |
| Right | 2.5 s |

The apparent spin speed eases down toward each stop (inertia-style slowdown).

---

## Project layout

| File | Role |
|------|------|
| `main.py` | Game loop, `Live` updates, keyboard listener, physics/timing |
| `slot_machine.py` | `SlotMachine` — logic, weighted outcomes, JSON persistence |
| `render.py` | Rich layout — panels, reels table, status line |
| `requirements.txt` | Dependencies |
| `bitspin_data.json` | *(created at runtime)* Saved balance |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `rich` | Panels, tables, `Live` TUI |
| `pynput` | Non-blocking global key handling alongside `Live` |

---

## License

This is a small demo project; add a license file if you distribute it.
