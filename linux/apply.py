#!/usr/bin/env python3
"""Apply this fork's Linux desktop changes to an upstream (silverstein/minutes) checkout.

    python3 linux/apply.py <upstream checkout>

Upstream builds its Tauri desktop app for macOS and Windows only. Three changes make it a proper GNOME app:
a real "Minutes" window title, a stock GNOME window frame (linux_chrome.rs), and no in-window menu bar.

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
