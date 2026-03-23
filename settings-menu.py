#!/usr/bin/env python3
"""Claude Code Settings Menu — game-style animated TUI."""
import json, os, sys, msvcrt, time, re
sys.stdout.reconfigure(encoding="utf-8")

SETTINGS_PATH    = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
CLAUDE_JSON_PATH = os.path.join(os.path.expanduser("~"), ".claude.json")

# ── file helpers ───────────────────────────────────────────────────────────────

def read_json(path):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

# ── menu items ─────────────────────────────────────────────────────────────────
# (label, file, key, type, options, description)

ITEMS = [
    ("◈ MODEL & INTELLIGENCE", None, None, "header", [], ""),
    (
        "Model", "settings", "model", "cycle",
        ["sonnet", "opus", "haiku"],
        "The AI model Claude uses by default.\n"
        "Opus is most capable but slower. Sonnet balances speed\n"
        "and intelligence. Haiku is the fastest and lightest."
    ),
    (
        "Effort Level", "settings", "effortLevel", "cycle",
        ["low", "medium", "high"],
        "How deeply Claude reasons before replying.\n"
        "High effort = longer thinking, smarter answers.\n"
        "Low effort = faster responses for simple tasks."
    ),
    (
        "Always Thinking", "settings", "alwaysThinkingEnabled", "toggle", [],
        "Enables extended thinking on every message by default.\n"
        "Claude works through complex problems step-by-step\n"
        "before answering, like showing its working."
    ),
    (
        "Plan Mode", "settings", "defaultPermissionMode", "cycle",
        ["default", "plan"],
        "In plan mode Claude only reads files and proposes changes\n"
        "— it never writes or executes anything without your\n"
        "explicit approval. Great for reviewing intent first."
    ),
    ("◈ INTERFACE", None, None, "header", [], ""),
    (
        "Editor Mode", "claude", "editorMode", "cycle",
        ["normal", "vim"],
        "Controls keybindings in the prompt input.\n"
        "Vim mode gives you normal/insert navigation\n"
        "with Esc, i, hjkl, w, b, 0, $, and more."
    ),
    (
        "Language", "settings", "language", "cycle",
        ["english", "dutch", "spanish", "french", "german", "japanese", "chinese"],
        "The language Claude uses when writing responses.\n"
        "Useful if you prefer working in a language\n"
        "other than English."
    ),
    (
        "Spinner Tips", "settings", "spinnerTipsEnabled", "toggle", [],
        "Shows helpful tips in the status bar while Claude\n"
        "is thinking. Disable if you find them distracting\n"
        "or just want a cleaner interface."
    ),
    (
        "Auto Updates", "settings", "autoUpdatesChannel", "cycle",
        ["latest", "stable"],
        "Which release channel to use for updates.\n"
        "'latest' gets new features sooner.\n"
        "'stable' is more conservative and tested."
    ),
    ("◈ RUNTIME  (session-only, use in Claude)", None, None, "header", [], ""),
    (
        "Fast Mode", None, None, "info", [],
        "Type  /fast  inside Claude Code to toggle.\n"
        "Speeds up responses at the cost of some quality.\n"
        "State resets when you start a new session."
    ),
    (
        "Theme", None, None, "info", [],
        "Type  /config  inside Claude Code to change.\n"
        "Claude matches your terminal's light or dark\n"
        "background for comfortable reading."
    ),
]

# ── ANSI palette ───────────────────────────────────────────────────────────────

def c256(n):   return f"\033[38;5;{n}m"   # 256-colour foreground
def bg256(n):  return f"\033[48;5;{n}m"   # 256-colour background

RST  = "\033[0m"
BOLD = "\033[1m"
DIM  = "\033[2m"
INV  = "\033[7m"

# Theme colours
C_ORANGE  = c256(208)   # Claude-style header
C_AMBER   = c256(214)
C_YELLOW  = c256(220)
C_CYAN    = c256(39)    # section headers / info items
C_BLUE    = c256(75)    # model section values
C_GREEN   = c256(77)    # ON / active values
C_RED     = c256(196)   # plan mode active
C_MAGENTA = c256(171)   # UI section values
C_DIMVAL  = c256(242)   # unset / off values
C_BORDER  = c256(240)   # box lines
C_SEL_BG  = bg256(236)  # selected row background
C_SEL_FG  = c256(255)   # selected row text

# Per-section value colour
def section_colour(key):
    model_keys = {"model", "effortLevel", "alwaysThinkingEnabled", "defaultPermissionMode"}
    ui_keys    = {"editorMode", "language", "spinnerTipsEnabled", "autoUpdatesChannel"}
    if key in model_keys: return C_BLUE
    if key in ui_keys:    return C_MAGENTA
    return C_GREEN

# ── box drawing ────────────────────────────────────────────────────────────────

W = 64   # visible inner width

def strip_ansi(s):
    return re.sub(r"\033\[[0-9;]*m", "", s)

def bline(s=""):
    pad = max(0, W - 2 - len(strip_ansi(s)))
    print(f"{C_BORDER}║{RST} {s}{' ' * pad} {C_BORDER}║{RST}")

def btop():
    print(f"{C_BORDER}╔{'═' * W}╗{RST}")
def bbot():
    print(f"{C_BORDER}╚{'═' * W}╝{RST}")
def bsep():
    print(f"{C_BORDER}╠{'═' * W}╣{RST}")
def bblank():
    bline()

# ── gradient header ────────────────────────────────────────────────────────────

HEADER_ART = [
    r" ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗",
    r"██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝",
    r"██║     ██║     ███████║██║   ██║██║  ██║█████╗  ",
    r"██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝  ",
    r"╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗",
    r" ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝╚═════╝ ╚══════╝",
]
# Gradient: orange → amber → yellow across columns
GRAD = [208, 208, 209, 210, 214, 214, 214, 220, 220, 226]

def gradient_line(text):
    out = ""
    cols = max(1, len(text))
    for i, ch in enumerate(text):
        ci = int(i / cols * (len(GRAD) - 1))
        out += c256(GRAD[ci]) + ch
    return out + RST

def render_header():
    btop()
    bblank()
    art_w = len(HEADER_ART[0])
    indent = max(0, (W - art_w) // 2)
    for row in HEADER_ART:
        padded = " " * indent + row
        # pad to inner width
        inner = " " + padded + " " * max(0, W - 2 - len(padded))
        print(f"{C_BORDER}║{RST}{gradient_line(inner)}{C_BORDER}║{RST}")
    # Subtitle
    subtitle = "S E T T I N G S"
    sub_indent = (W - len(subtitle)) // 2
    sub_line = " " * sub_indent + subtitle
    sub_line_padded = " " + sub_line + " " * max(0, W - 2 - len(sub_line))
    print(f"{C_BORDER}║{RST}{C_AMBER}{BOLD}{sub_line_padded}{RST}{C_BORDER}║{RST}")
    bblank()

# ── effort bar ─────────────────────────────────────────────────────────────────

EFFORT_BARS = {
    "low":    (1, c256(214)),
    "medium": (3, c256(208)),
    "high":   (5, c256(196)),
}

def effort_bar(val):
    filled, col = EFFORT_BARS.get(val, (0, C_DIMVAL))
    bar = col + "▓" * filled + RST + C_DIMVAL + "░" * (5 - filled) + RST
    return bar + " " + (col + BOLD + val + RST if val else "")

# ── value formatter ────────────────────────────────────────────────────────────

def fmt_val(item, settings, claude, blink=False):
    label, file_, key, type_, options, desc = item
    if type_ in ("info", "header") or key is None: return ""
    data  = settings if file_ == "settings" else claude
    val   = data.get(key)
    vcol  = section_colour(key)

    if val is None:
        return f"{C_DIMVAL}(unset){RST}"
    if type_ == "toggle":
        if val:  return f"{C_GREEN}{BOLD}● ON{RST}"
        else:    return f"{C_DIMVAL}○ off{RST}"
    if key == "effortLevel":
        return effort_bar(val)
    if key == "defaultPermissionMode" and val == "plan":
        pulse = BOLD if blink else ""
        return f"{C_RED}{pulse}⚠ PLAN MODE{RST}"
    return f"{vcol}{BOLD}{val}{RST}"

# ── render ─────────────────────────────────────────────────────────────────────

LABEL_W = 20

def render(sel, settings, claude, blink=False):
    os.system("cls")
    render_header()
    bsep()

    selectable = []
    for i, item in enumerate(ITEMS):
        label, file_, key, type_, options, desc = item

        if type_ == "header":
            bline(f"{C_CYAN}{BOLD}{label}{RST}")
            continue

        selectable.append(i)
        is_sel = (i == sel)

        if type_ == "info":
            if is_sel:
                row = f"{C_SEL_BG}{C_SEL_FG}  ▶ {label:<{LABEL_W + 4}}{RST}"
                hint = f"  {DIM}use inside Claude Code{RST}"
                bline(row + hint if len(strip_ansi(row + hint)) < W - 2 else row)
            else:
                bline(f"  {C_CYAN}· {label}{RST}")
            continue

        vstr    = fmt_val(item, settings, claude, blink and is_sel)
        v_vis   = strip_ansi(vstr)

        if is_sel:
            # full-width highlight row
            content = f"  ▶ {label:<{LABEL_W}}  {vstr}"
            content_vis = f"  ▶ {label:<{LABEL_W}}  {v_vis}"
            pad = max(0, W - 2 - len(content_vis))
            print(
                f"{C_BORDER}║{RST}"
                f"{C_SEL_BG}{C_SEL_FG}  ▶ {label:<{LABEL_W}}  {RST}"
                f"{vstr}"
                f"{C_SEL_BG}{' ' * pad}{RST}"
                f" {C_BORDER}║{RST}"
            )
        else:
            bline(f"  {DIM}·{RST} {label:<{LABEL_W}}  {vstr}")

    # ── description panel ──────────────────────────────────────────────────────
    bsep()
    if sel < len(ITEMS):
        label, file_, key, type_, options, desc = ITEMS[sel]
        bline(f"  {C_AMBER}{BOLD}{label}{RST}")
        if desc:
            for line in desc.splitlines():
                bline(f"  {DIM}{line}{RST}")
            # pad to 3 desc lines minimum
            for _ in range(max(0, 3 - len(desc.splitlines()))):
                bblank()
        else:
            bblank(); bblank(); bblank()

    bsep()
    bline(
        f"  {C_DIMVAL}↑ ↓  navigate"
        f"   {C_AMBER}Space{C_DIMVAL} / {C_AMBER}Enter{C_DIMVAL}  toggle / cycle"
        f"   {C_AMBER}Q{C_DIMVAL}  quit{RST}"
    )
    bbot()
    return selectable

# ── logic ──────────────────────────────────────────────────────────────────────

def first_selectable():
    for i, item in enumerate(ITEMS):
        if item[3] not in ("header", "info"): return i
    return 0

def next_sel(cur, direction, selectable):
    if cur not in selectable: return selectable[0]
    idx = selectable.index(cur)
    return selectable[(idx + direction) % len(selectable)]

def apply(sel, settings, claude):
    item = ITEMS[sel]
    label, file_, key, type_, options, desc = item
    if type_ in ("info", "header") or key is None: return settings, claude
    data = settings if file_ == "settings" else claude
    if type_ == "toggle":
        data[key] = not data.get(key, False)
    elif type_ == "cycle":
        cur = data.get(key, options[0])
        idx = options.index(cur) if cur in options else 0
        data[key] = options[(idx + 1) % len(options)]
    if file_ == "settings": write_json(SETTINGS_PATH, settings)
    else:                    write_json(CLAUDE_JSON_PATH, claude)
    return settings, claude

# ── main loop with blink animation ────────────────────────────────────────────

def main():
    settings  = read_json(SETTINGS_PATH)
    claude    = read_json(CLAUDE_JSON_PATH)
    sel       = first_selectable()
    blink     = True
    last_blink = time.time()

    selectable = render(sel, settings, claude, blink)

    while True:
        # blink every 0.55s without blocking input
        now = time.time()
        if now - last_blink > 0.55:
            blink = not blink
            last_blink = now
            selectable = render(sel, settings, claude, blink)

        if not msvcrt.kbhit():
            time.sleep(0.04)
            continue

        key = msvcrt.getch()
        if key == b"\xe0":
            key2 = msvcrt.getch()
            if   key2 == b"H": sel = next_sel(sel, -1, selectable)
            elif key2 == b"P": sel = next_sel(sel, +1, selectable)
        elif key in (b"\r", b" "):
            settings, claude = apply(sel, settings, claude)
        elif key in (b"q", b"Q", b"\x1b"):
            os.system("cls")
            print(f"{C_AMBER}{BOLD}Settings saved.{RST} Restart Claude Code for changes to take effect.")
            break

        selectable = render(sel, settings, claude, blink)

if __name__ == "__main__":
    main()
