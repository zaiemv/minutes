#!/usr/bin/env python3
"""Apply this fork's Linux desktop changes to an upstream (silverstein/minutes) checkout.

    python3 linux/apply.py <upstream checkout>

Upstream builds its Tauri desktop app for macOS and Windows only. Three changes make it a proper GNOME app:
a real "Minutes" window title, a stock GNOME window frame (linux_chrome.rs), and no in-window menu bar.
A fourth is taste: a neutral grey palette with a blue accent in place of upstream's warm one (PALETTE below).

Each edit finds its place by what the code says, not by line number, so upstream moving things around does not
break the build. An edit whose place is gone, or is there twice, stops the run with its name: fix it here.
"""
import re
import shutil
import sys
from pathlib import Path

src = Path(sys.argv[1])
here = Path(__file__).resolve().parent
main = src / "tauri/src-tauri/src/main.rs"
text = main.read_text()


def edit(name, pattern, replacement, flags=re.M):
    global text
    found = len(re.findall(pattern, text, flags))
    if found != 1:
        sys.exit(f"linux/apply.py: '{name}' matched {found} places in main.rs, expected 1")
    text = re.sub(pattern, replacement, text, count=1, flags=flags)
    print(f"applied: {name}")


if "linux_chrome" in text:
    sys.exit("linux/apply.py: main.rs already mentions linux_chrome (upstream took the change, or it was applied twice)")

# 1. the module, next to the other top-level ones
first_mod = re.search(r"^mod \w+;$", text, re.M)
if not first_mod:
    sys.exit("linux/apply.py: no top-level 'mod x;' line in main.rs")
text = text[:first_mod.start()] + '#[cfg(target_os = "linux")]\nmod linux_chrome;\n' + text[first_mod.start():]
print("applied: mod linux_chrome")

# 2. the window title: empty is for the macOS overlay chrome; a Linux title bar, dock and switcher show it
edit("window title", r'^([ \t]*)\.title\(""\)$',
     r'\1.title(if cfg!(target_os = "macos") {\n\1    ""\n\1} else {\n\1    "Minutes"\n\1})')

# 3. the stock GNOME frame, before anything touches GTK and before any thread exists
edit("pin the GTK theme at the start of main()", r"^fn main\(\) \{\n",
     'fn main() {\n    #[cfg(target_os = "linux")]\n    linux_chrome::pin_stock_gnome_theme();\n')

# 4. no in-window menu bar on Linux (every item is in the tray menu)
edit("build_app_menu is unused on Linux", r"^fn build_app_menu\(",
     '#[cfg_attr(target_os = "linux", allow(dead_code))]\nfn build_app_menu(')
edit("no menu bar on Linux", r"^([ \t]*)tauri::Builder::default\(\)\n\s*\.menu\(build_app_menu\)\n",
     r'\1let builder = tauri::Builder::default();\n\1#[cfg(not(target_os = "linux"))]\n'
     r'\1let builder = builder.menu(build_app_menu);\n\1builder\n')

main.write_text(text)
shutil.copy(here / "linux_chrome.rs", main.parent / "linux_chrome.rs")
print("copied: linux_chrome.rs")


# 5. the palette: upstream's is warm (cream and brown in light, olive-black and green in dark). This one is a
#    neutral cool grey with a blue accent, in both appearances. Only the names below change; status colors
#    (red, the green "live" dot, capture blue) stay upstream's. A translucent accent keeps upstream's opacity.
PALETTE = {
    "dark": {
        "bg": "#1B1C20", "bg-elevated": "#232429", "bg-hover": "#2C2D33", "border-mid": "#34353C",
        "text": "#F1F1F3", "text-secondary": "#A8AAB2", "text-tertiary": "#72747D",
        "accent": "#4C8DF6", "accent-hover": "#6BA1F8",
    },
    "light": {
        "bg": "#FAFAFB", "bg-elevated": "#F1F2F4", "bg-hover": "#E8E9EC",
        "text": "#1B1C20", "text-secondary": "#5F626B", "text-tertiary": "#8A8D96",
        "accent": "#2563EB", "accent-hover": "#1D4FD0",
    },
}
ACCENT_ALPHA = re.compile(r"^(accent-(soft|tint|border)[a-z-]*|focus-ring[a-z-]*)$")
WINDOWS = ["index.html", "note.html", "terminal.html", "meeting-prompt.html"]


def recolor(path):
    page = path.read_text()
    out, pos, done = [], 0, []
    # every rule that sets --bg is one appearance's palette
    for bg in re.finditer(r"^[ \t]*--bg:\s*(#[0-9A-Fa-f]{6});", page, re.M):
        start, end = page.rfind("{", 0, bg.start()), page.find("}", bg.end())
        r, g, b = (int(bg.group(1)[i:i + 2], 16) for i in (1, 3, 5))
        mode = "light" if (r + g + b) / 3 > 128 else "dark"
        colors = PALETTE[mode]
        ar, ag, ab = (int(colors["accent"][i:i + 2], 16) for i in (1, 3, 5))
        seen = set()

        def one(m):
            name, value = m.group(2), m.group(4)
            if name in colors:
                seen.add(name)
                return f"{m.group(1)}--{name}:{m.group(3)}{colors[name]};"
            alpha = re.fullmatch(r"rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*([0-9.]+)\s*\)", value)
            if ACCENT_ALPHA.match(name) and alpha:
                return f"{m.group(1)}--{name}:{m.group(3)}rgba({ar}, {ag}, {ab}, {alpha.group(1)});"
            return m.group(0)

        block = re.sub(r"^([ \t]*)--([a-z-]+):(\s*)([^;]+);", one, page[start:end], flags=re.M)
        missing = {"bg", "text", "accent"} - seen
        if missing:
            sys.exit(f"linux/apply.py: {path.name} ({mode}) has no --{', --'.join(sorted(missing))} to recolor")
        out.append(page[pos:start] + block)
        pos = end
        done.append(mode)
    if sorted(done) != ["dark", "light"]:
        sys.exit(f"linux/apply.py: {path.name}: expected one dark and one light palette, found {done}")
    path.write_text("".join(out) + page[pos:])
    print(f"recolored: {path.name}")


for name in WINDOWS:
    recolor(src / "tauri/src" / name)
