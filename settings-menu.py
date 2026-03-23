#!/usr/bin/env python3
"""Claude Code Settings Menu — arrow-key navigable, game-style."""
import json
import os
import sys
import msvcrt

sys.stdout.reconfigure(encoding="utf-8")

SETTINGS_PATH   = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
CLAUDE_JSON_PATH = os.path.join(os.path.expanduser("~"), ".claude.json")

# ── helpers ────────────────────────────────────────────────────────────────────

def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ── menu definition ────────────────────────────────────────────────────────────
# Each item: (label, file, key, type, options, description)
#   file:  "settings" | "claude" | None (info-only)
#   type:  "cycle" | "toggle" | "info" | "header"

ITEMS = [
    # ── Model & intelligence
    (
        "Model", "settings", "model", "cycle",
        ["sonnet", "opus", "haiku"],
        "The AI model Claude uses by default. Opus is the most capable but\n"
        "slower. Sonnet balances speed and intelligence. Haiku is fastest."
    ),
    (
        "Effort Level", "settings", "effortLevel", "cycle",
        ["low", "medium", "high"],
        "How deeply Claude reasons before replying. High effort means longer\n"
        "thinking time but smarter answers. Low is faster for simple tasks."
    ),
    (
        "Always Thinking", "settings", "alwaysThinkingEnabled", "toggle", [],
        "Enables extended thinking by default on every message, so Claude\n"
        "works through complex problems step-by-step before answering."
    ),
    (
        "Plan Mode", "settings", "defaultPermissionMode", "cycle",
        ["default", "plan"],
        "In plan mode Claude only reads files and proposes changes — it never\n"
        "writes or runs anything without your approval. Good for reviewing\n"
        "what Claude intends to do before it acts. (Restart to apply)"
    ),
    # ── UI / editor
    (
        "Editor Mode", "claude", "editorMode", "cycle",
        ["normal", "vim"],
        "Controls keybindings in the prompt input. Vim mode gives you\n"
        "normal/insert mode navigation (Esc, i, hjkl, etc.)."
    ),
    (
        "Language", "settings", "language", "cycle",
        ["english", "dutch", "spanish", "french", "german", "japanese", "chinese"],
        "The language Claude uses when writing responses. Useful if you\n"
        "prefer to work in a language other than English."
    ),
    (
        "Spinner Tips", "settings", "spinnerTipsEnabled", "toggle", [],
        "Shows helpful tips in the status bar while Claude is thinking.\n"
        "Turn off if you find them distracting."
    ),
    (
        "Auto Updates", "settings", "autoUpdatesChannel", "cycle",
        ["latest", "stable"],
        "Which release channel to use for Claude Code updates. 'latest'\n"
        "gets new features sooner; 'stable' is more conservative."
    ),
    # ── Runtime-only reminders
    ("── RUNTIME (session-only) ──", None, None, "header", [], ""),
    (
        "Fast Mode", None, None, "info", [],
        "Toggle fast mode on/off with /fast inside Claude Code. This\n"
        "speeds up responses at the cost of some quality."
    ),
    (
        "Theme", None, None, "info", [],
        "Change the colour theme with /config inside Claude Code.\n"
        "Claude matches your terminal's light or dark background."
    ),
]

# ── colours & box ──────────────────────────────────────────────────────────────

W    = 62   # inner width (between ║ chars)
BOLD = "\033[1m"
DIM  = "\033[2m"
GRN  = "\033[32m"
CYN  = "\033[36m"
RED  = "\033[31m"
RST  = "\033[0m"
HI   = "\033[7m"   # inverse video

def clr(): os.system("cls")

def bline(s=""):
    """Print a box line, padding s to W-2 visible chars."""
    # strip ANSI for length calculation
    import re
    visible = re.sub(r"\033\[[0-9;]*m", "", s)
    pad = max(0, W - 2 - len(visible))
    print("║ " + s + " " * pad + " ║")

def btop(): print("╔" + "═" * W + "╗")
def bbot(): print("╚" + "═" * W + "╝")
def bsep(): print("╠" + "═" * W + "╣")
def bblank(): bline()

# ── value display ──────────────────────────────────────────────────────────────

def get_val(item, settings, claude):
    label, file_, key, type_, options, desc = item
    if type_ in ("info", "header") or key is None:
        return None
    data = settings if file_ == "settings" else claude
    return data.get(key)

def fmt_val(item, settings, claude):
    label, file_, key, type_, options, desc = item
    val = get_val(item, settings, claude)
    if val is None:
        return f"{DIM}(unset){RST}"
    if type_ == "toggle":
        return f"{GRN}ON{RST}" if val else f"{DIM}OFF{RST}"
    # cycle — highlight plan mode specially
    if key == "defaultPermissionMode" and val == "plan":
        return f"{RED}PLAN{RST}"
    return f"{GRN}{val}{RST}"

# ── render ─────────────────────────────────────────────────────────────────────

LABEL_W = 22
VAL_W   = 10

def render(sel, settings, claude):
    clr()
    btop()
    bline(f"{BOLD}  ⚙  Claude Code Settings{RST}")
    bsep()

    selectable = []
    for i, item in enumerate(ITEMS):
        label, file_, key, type_, options, desc = item

        if type_ == "header":
            bline(f"  {DIM}{label}{RST}")
            continue

        selectable.append(i)
        is_sel = (i == sel)

        if type_ == "info":
            marker = f"{CYN}●{RST}" if is_sel else f"{DIM}·{RST}"
            row = f"  {marker} {CYN}{label}{RST}"
            if is_sel:
                print("║" + f"\033[7m  {marker} {label}" + " " * (W - 4 - len(label)) + f"\033[0m║")
            else:
                bline(row)
        else:
            vstr  = fmt_val(item, settings, claude)
            marker = f"{BOLD}▶{RST}" if is_sel else " "
            row_label = f"  {marker} {label:<{LABEL_W}}"
            if is_sel:
                # highlighted row
                import re
                v_visible = re.sub(r"\033\[[0-9;]*m", "", vstr)
                pad = max(0, W - 2 - len(f"   {label:<{LABEL_W}} {v_visible}"))
                print("║\033[7m" + f"   {label:<{LABEL_W}} " + "\033[0m" + vstr + " " * pad + " ║")
            else:
                bline(f"  {DIM}·{RST} {label:<{LABEL_W}} {vstr}")

    # ── description panel ──────────────────────────────────────────────────────
    bsep()
    if sel < len(ITEMS):
        label, file_, key, type_, options, desc = ITEMS[sel]
        bline(f"  {BOLD}{label}{RST}")
        if desc:
            for line in desc.splitlines():
                bline(f"  {DIM}{line}{RST}")
        else:
            bblank()
    bsep()
    bline(f"{DIM}  ↑ ↓  Navigate     Space / Enter  Toggle / Cycle     Q  Quit{RST}")
    bbot()

    return selectable

# ── logic ──────────────────────────────────────────────────────────────────────

def first_selectable():
    for i, item in enumerate(ITEMS):
        if item[3] not in ("header", "info"):
            return i
    return 0

def next_sel(current, direction, selectable):
    if current not in selectable:
        return selectable[0]
    idx = selectable.index(current)
    return selectable[(idx + direction) % len(selectable)]

def apply(sel, settings, claude):
    item = ITEMS[sel]
    label, file_, key, type_, options, desc = item
    if type_ in ("info", "header") or key is None:
        return settings, claude
    data = settings if file_ == "settings" else claude
    if type_ == "toggle":
        data[key] = not data.get(key, False)
    elif type_ == "cycle":
        cur = data.get(key, options[0])
        idx = options.index(cur) if cur in options else 0
        data[key] = options[(idx + 1) % len(options)]
    if file_ == "settings":
        write_json(SETTINGS_PATH, settings)
    else:
        write_json(CLAUDE_JSON_PATH, claude)
    return settings, claude

def main():
    settings = read_json(SETTINGS_PATH)
    claude   = read_json(CLAUDE_JSON_PATH)
    sel      = first_selectable()

    while True:
        selectable = render(sel, settings, claude)
        key = msvcrt.getch()

        if key == b"\xe0":
            key2 = msvcrt.getch()
            if key2 == b"H":    sel = next_sel(sel, -1, selectable)
            elif key2 == b"P":  sel = next_sel(sel, +1, selectable)
        elif key in (b"\r", b" "):
            settings, claude = apply(sel, settings, claude)
        elif key in (b"q", b"Q", b"\x1b"):
            clr()
            print("Settings saved. Restart Claude Code for changes to take effect.")
            break

if __name__ == "__main__":
    main()
