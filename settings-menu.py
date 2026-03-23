#!/usr/bin/env python3
"""Claude Code Settings Menu — game-style animated TUI with tabs."""
import json, os, sys, msvcrt, time, re, subprocess
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

# ── ANSI palette ───────────────────────────────────────────────────────────────

def c256(n):  return f"\033[38;5;{n}m"
def bg256(n): return f"\033[48;5;{n}m"

RST  = "\033[0m";  BOLD = "\033[1m";  DIM = "\033[2m"
C_ORANGE  = c256(208); C_AMBER = c256(214); C_YELLOW = c256(220)
C_CYAN    = c256(39);  C_BLUE  = c256(75);  C_GREEN  = c256(77)
C_RED     = c256(196); C_MAG   = c256(171); C_DIMVAL = c256(242)
C_BORDER  = c256(240); C_SEL_BG = bg256(236); C_SEL_FG = c256(255)
GRAD = [208,208,209,210,214,214,214,220,220,226]

def strip_ansi(s): return re.sub(r"\033\[[0-9;]*m","",s)

def gradient_line(text):
    out=""
    cols=max(1,len(text))
    for i,ch in enumerate(text):
        ci=int(i/cols*(len(GRAD)-1))
        out+=c256(GRAD[ci])+ch
    return out+RST

# ── box drawing ────────────────────────────────────────────────────────────────

W = 64

def bline(s=""):
    pad=max(0,W-2-len(strip_ansi(s)))
    print(f"{C_BORDER}║{RST} {s}{' '*pad} {C_BORDER}║{RST}")

def btop(): print(f"{C_BORDER}╔{'═'*W}╗{RST}")
def bbot(): print(f"{C_BORDER}╚{'═'*W}╝{RST}")
def bsep(): print(f"{C_BORDER}╠{'═'*W}╣{RST}")
def bblank(): bline()

# ── ASCII header ───────────────────────────────────────────────────────────────

HEADER_ART = [
    r" ██████╗██╗      █████╗ ██╗   ██╗██████╗ ███████╗",
    r"██╔════╝██║     ██╔══██╗██║   ██║██╔══██╗██╔════╝",
    r"██║     ██║     ███████║██║   ██║██║  ██║█████╗  ",
    r"██║     ██║     ██╔══██║██║   ██║██║  ██║██╔══╝  ",
    r"╚██████╗███████╗██║  ██║╚██████╔╝██████╔╝███████╗",
    r" ╚═════╝╚══════╝╚═╝  ╚═╝ ╚═════╝╚═════╝ ╚══════╝",
]

def render_header(active_tab):
    btop(); bblank()
    art_w = len(HEADER_ART[0])
    indent = max(0,(W-art_w)//2)
    for row in HEADER_ART:
        padded = " "*indent+row
        inner  = " "+padded+" "*max(0,W-2-len(padded))
        print(f"{C_BORDER}║{RST}{gradient_line(inner)}{C_BORDER}║{RST}")
    subtitle = "S E T T I N G S"
    si = (W-len(subtitle))//2
    sl = " "+(" "*si+subtitle)+" "*max(0,W-2-si-len(subtitle))
    print(f"{C_BORDER}║{RST}{C_AMBER}{BOLD}{sl}{RST}{C_BORDER}║{RST}")
    bblank()

    # tab bar
    tabs = ["  ⚙  SETTINGS  ", "  ⬡  SHELLS  "]
    bar = ""
    for i,t in enumerate(tabs):
        if i==active_tab:
            bar += f"{C_SEL_BG}{C_SEL_FG}{BOLD}{t}{RST}"
        else:
            bar += f"{C_DIMVAL}{t}{RST}"
        if i < len(tabs)-1:
            bar += f"{C_BORDER}│{RST}"
    bline(bar)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 0 — SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

ITEMS = [
    ("◈ MODEL & INTELLIGENCE", None,None,"header",[],  ""),
    ("Model","settings","model","cycle",["sonnet","opus","haiku"],
     "The AI model Claude uses by default.\n"
     "Opus is most capable but slower. Sonnet balances speed\n"
     "and intelligence. Haiku is the fastest and lightest."),
    ("Effort Level","settings","effortLevel","cycle",["low","medium","high"],
     "How deeply Claude reasons before replying.\n"
     "High effort = longer thinking, smarter answers.\n"
     "Low effort = faster responses for simple tasks."),
    ("Always Thinking","settings","alwaysThinkingEnabled","toggle",[],
     "Enables extended thinking on every message by default.\n"
     "Claude works through complex problems step-by-step\n"
     "before answering, like showing its working."),
    ("Plan Mode","settings","defaultPermissionMode","cycle",["default","plan"],
     "In plan mode Claude only reads files and proposes changes\n"
     "— it never writes or executes anything without your\n"
     "explicit approval. Great for reviewing intent first."),
    ("◈ INTERFACE", None,None,"header",[],  ""),
    ("Editor Mode","claude","editorMode","cycle",["normal","vim"],
     "Controls keybindings in the prompt input.\n"
     "Vim mode gives you normal/insert navigation\n"
     "with Esc, i, hjkl, w, b, 0, $, and more."),
    ("Language","settings","language","cycle",
     ["english","dutch","spanish","french","german","japanese","chinese"],
     "The language Claude uses when writing responses.\n"
     "Useful if you prefer working in a language\n"
     "other than English."),
    ("Spinner Tips","settings","spinnerTipsEnabled","toggle",[],
     "Shows helpful tips in the status bar while Claude\n"
     "is thinking. Disable if you find them distracting\n"
     "or just want a cleaner interface."),
    ("Auto Updates","settings","autoUpdatesChannel","cycle",["latest","stable"],
     "Which release channel to use for updates.\n"
     "'latest' gets new features sooner.\n"
     "'stable' is more conservative and tested."),
    ("◈ RUNTIME  (session-only)", None,None,"header",[],  ""),
    ("Fast Mode",None,None,"info",[],
     "Type  /fast  inside Claude Code to toggle.\n"
     "Speeds up responses at the cost of some quality.\n"
     "State resets when you start a new session."),
    ("Theme",None,None,"info",[],
     "Type  /config  inside Claude Code to change.\n"
     "Claude matches your terminal's light or dark\n"
     "background for comfortable reading."),
]

EFFORT_BARS = {"low":(1,c256(214)),"medium":(3,c256(208)),"high":(5,c256(196))}

def section_colour(key):
    if key in {"model","effortLevel","alwaysThinkingEnabled","defaultPermissionMode"}: return C_BLUE
    if key in {"editorMode","language","spinnerTipsEnabled","autoUpdatesChannel"}:    return C_MAG
    return C_GREEN

def fmt_val(item, settings, claude, blink=False):
    label,file_,key,type_,options,desc = item
    if type_ in ("info","header") or key is None: return ""
    data = settings if file_=="settings" else claude
    val  = data.get(key)
    vcol = section_colour(key)
    if val is None:   return f"{C_DIMVAL}(unset){RST}"
    if type_=="toggle":
        return f"{C_GREEN}{BOLD}● ON{RST}" if val else f"{C_DIMVAL}○ off{RST}"
    if key=="effortLevel":
        filled,col = EFFORT_BARS.get(val,(0,C_DIMVAL))
        bar = col+"▓"*filled+RST+C_DIMVAL+"░"*(5-filled)+RST
        return bar+" "+(col+BOLD+val+RST if val else "")
    if key=="defaultPermissionMode" and val=="plan":
        pulse=BOLD if blink else ""
        return f"{C_RED}{pulse}⚠ PLAN MODE{RST}"
    return f"{vcol}{BOLD}{val}{RST}"

LABEL_W = 20

def render_settings(sel, settings, claude, blink):
    bsep()
    selectable=[]
    for i,item in enumerate(ITEMS):
        label,file_,key,type_,options,desc = item
        if type_=="header":
            bline(f"{C_CYAN}{BOLD}{label}{RST}"); continue
        selectable.append(i)
        is_sel=(i==sel)
        if type_=="info":
            if is_sel:
                row=f"{C_SEL_BG}{C_SEL_FG}  ▶ {label:<{LABEL_W+4}}{RST}"
                bline(row)
            else:
                bline(f"  {C_CYAN}· {label}{RST}")
            continue
        vstr  = fmt_val(item,settings,claude,blink and is_sel)
        v_vis = strip_ansi(vstr)
        if is_sel:
            pad=max(0,W-2-len(f"  ▶ {label:<{LABEL_W}}  {v_vis}"))
            print(f"{C_BORDER}║{RST}{C_SEL_BG}{C_SEL_FG}  ▶ {label:<{LABEL_W}}  {RST}{vstr}{C_SEL_BG}{' '*pad}{RST} {C_BORDER}║{RST}")
        else:
            bline(f"  {DIM}·{RST} {label:<{LABEL_W}}  {vstr}")

    bsep()
    if sel<len(ITEMS):
        label,file_,key,type_,options,desc = ITEMS[sel]
        bline(f"  {C_AMBER}{BOLD}{label}{RST}")
        lines=desc.splitlines() if desc else []
        for ln in lines: bline(f"  {DIM}{ln}{RST}")
        for _ in range(max(0,3-len(lines))): bblank()
    bsep()
    bline(f"  {C_DIMVAL}↑ ↓  navigate   {C_AMBER}Space{C_DIMVAL}/{C_AMBER}Enter{C_DIMVAL}  toggle   {C_AMBER}←→{C_DIMVAL}  switch tab   {C_AMBER}Q{C_DIMVAL}  quit{RST}")
    bbot()
    return selectable

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SHELLS
# ══════════════════════════════════════════════════════════════════════════════

SHELL_NAMES = {"cmd.exe","powershell.exe","pwsh.exe","bash.exe","sh.exe","nu.exe"}
MY_PID      = os.getpid()

def get_shells():
    try:
        r = subprocess.run(
            ["tasklist","/FO","CSV","/V","/NH"],
            capture_output=True, text=True, timeout=4
        )
        shells=[]
        for line in r.stdout.splitlines():
            parts=[p.strip('"') for p in line.split('","')]
            if len(parts)<9: continue
            name,pid_s=parts[0],parts[1]
            title=parts[8] if parts[8]!="N/A" else ""
            try: pid=int(pid_s)
            except ValueError: continue
            if pid==MY_PID: continue
            if name.lower() in SHELL_NAMES:
                shells.append({"name":name,"pid":pid,"title":title})
        return shells
    except Exception:
        return []

def kill_shell(pid):
    try:
        subprocess.run(["taskkill","/F","/PID",str(pid)],
                       capture_output=True, timeout=3)
        return True
    except Exception:
        return False

def render_shells(sel_sh, shells, confirm_pid):
    bsep()
    if not shells:
        bblank()
        bline(f"  {C_DIMVAL}No shell processes found.{RST}")
        bblank()
    else:
        for i,sh in enumerate(shells):
            is_sel=(i==sel_sh)
            name  = sh["name"]
            pid   = sh["pid"]
            title = sh["title"][:28] if sh["title"] else ""
            pid_s = f"{C_DIMVAL}PID {pid}{RST}"
            name_col = C_CYAN if name.lower() in {"cmd.exe","powershell.exe","pwsh.exe"} else C_BLUE
            if confirm_pid==pid:
                # confirmation row
                pad=max(0,W-2-len(f"  ▶ {name:<16} {strip_ansi(pid_s)}  Really close?  Y/N"))
                print(f"{C_BORDER}║{RST}{bg256(52)}{C_SEL_FG}  ▶ {name:<16} PID {pid}  Really close?  Y / N{' '*pad}{RST} {C_BORDER}║{RST}")
            elif is_sel:
                info=f"{name:<16} {strip_ansi(pid_s):<12} {title}"
                pad=max(0,W-2-len(f"  ▶ {info}"))
                print(f"{C_BORDER}║{RST}{C_SEL_BG}{C_SEL_FG}  ▶ {name:<16} {RST}{C_DIMVAL}PID {pid:<8}{RST}{C_SEL_BG}{C_SEL_FG} {title:<28}{RST}{C_SEL_BG}{' '*max(0,W-2-len(f'  ▶ {name:<16} PID {pid:<8} {title:<28}'))}{RST} {C_BORDER}║{RST}")
            else:
                bline(f"  {DIM}·{RST} {name_col}{name:<16}{RST} {C_DIMVAL}PID {pid:<8}{RST} {DIM}{title}{RST}")

    # description panel
    bsep()
    if shells and sel_sh<len(shells):
        sh=shells[sel_sh]
        bline(f"  {C_AMBER}{BOLD}{sh['name']}{RST}  {C_DIMVAL}PID {sh['pid']}{RST}")
        if sh["title"]:
            bline(f"  {DIM}{sh['title']}{RST}")
        else:
            bblank()
        bblank()
    else:
        bblank(); bblank(); bblank()

    bsep()
    bline(f"  {C_DIMVAL}↑ ↓  navigate   {C_RED}X{C_DIMVAL}  close shell   {C_AMBER}R{C_DIMVAL}  refresh   {C_AMBER}←→{C_DIMVAL}  switch tab   {C_AMBER}Q{C_DIMVAL}  quit{RST}")
    bbot()

# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS helpers
# ══════════════════════════════════════════════════════════════════════════════

def first_selectable():
    for i,item in enumerate(ITEMS):
        if item[3] not in ("header","info"): return i
    return 0

def next_sel(cur, direction, selectable):
    if cur not in selectable: return selectable[0]
    idx=selectable.index(cur)
    return selectable[(idx+direction)%len(selectable)]

def apply_setting(sel, settings, claude):
    item=ITEMS[sel]
    label,file_,key,type_,options,desc=item
    if type_ in ("info","header") or key is None: return settings,claude
    data=settings if file_=="settings" else claude
    if type_=="toggle":   data[key]=not data.get(key,False)
    elif type_=="cycle":
        cur=data.get(key,options[0])
        idx=options.index(cur) if cur in options else 0
        data[key]=options[(idx+1)%len(options)]
    if file_=="settings": write_json(SETTINGS_PATH,settings)
    else:                 write_json(CLAUDE_JSON_PATH,claude)
    return settings,claude

# ══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

def main():
    settings   = read_json(SETTINGS_PATH)
    claude     = read_json(CLAUDE_JSON_PATH)
    tab        = 0          # 0=settings, 1=shells
    sel        = first_selectable()
    sel_sh     = 0
    shells     = []
    confirm_pid= None
    blink      = True
    last_blink = time.time()
    selectable = []

    def full_render():
        nonlocal selectable
        os.system("cls")
        render_header(tab)
        if tab==0:
            selectable=render_settings(sel,settings,claude,blink)
        else:
            render_shells(sel_sh,shells,confirm_pid)

    shells=get_shells()
    full_render()

    while True:
        now=time.time()
        if now-last_blink>0.55:
            blink=not blink
            last_blink=now
            full_render()

        if not msvcrt.kbhit():
            time.sleep(0.04)
            continue

        key=msvcrt.getch()

        if key==b"\xe0":
            k2=msvcrt.getch()
            if k2==b"H":   # up
                if tab==0: sel=next_sel(sel,-1,selectable)
                else:      sel_sh=max(0,sel_sh-1) if shells else 0
            elif k2==b"P": # down
                if tab==0: sel=next_sel(sel,+1,selectable)
                else:      sel_sh=min(len(shells)-1,sel_sh+1) if shells else 0
            elif k2 in (b"K",b"M"):  # left / right → switch tab
                tab=1-tab
                confirm_pid=None
                if tab==1: shells=get_shells(); sel_sh=0
        elif key==b"\t":  # Tab key → switch tab
            tab=1-tab
            confirm_pid=None
            if tab==1: shells=get_shells(); sel_sh=0
        elif key in (b"\r",b" "):
            if tab==0:
                settings,claude=apply_setting(sel,settings,claude)
        elif key in (b"x",b"X"):
            if tab==1 and shells:
                confirm_pid=shells[sel_sh]["pid"]
        elif key in (b"y",b"Y"):
            if confirm_pid:
                kill_shell(confirm_pid)
                confirm_pid=None
                shells=get_shells()
                sel_sh=min(sel_sh,max(0,len(shells)-1))
        elif key in (b"n",b"N"):
            confirm_pid=None
        elif key in (b"r",b"R"):
            if tab==1:
                shells=get_shells(); sel_sh=0
        elif key in (b"q",b"Q",b"\x1b"):
            os.system("cls")
            print(f"{C_AMBER}{BOLD}Settings saved.{RST} Restart Claude Code for changes to take effect.")
            break

        full_render()

if __name__=="__main__":
    main()
