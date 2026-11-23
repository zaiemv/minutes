# Minutes desktop for Linux

Automatic Linux builds of the [Minutes](https://github.com/silverstein/minutes) desktop app. Upstream publishes the
desktop app for macOS and Windows only; Linux gets the CLI.

- `.github/workflows/linux-desktop.yml` checks upstream for a new release four times a day, applies the changes in
  `linux/` to it, builds a `.deb` and publishes it under [Releases](../../releases) as `v<version>-linux.<n>`.
- `linux/apply.py` makes the edits (a real window title, a stock GNOME window frame, no in-window menu bar, and a neutral grey palette with a blue
  accent in place of upstream's warm one: the colors are the PALETTE table in that file);
  `linux/linux_chrome.rs` is the new file it adds.

If a build fails at "Apply the Linux changes", upstream changed one of the places `apply.py` edits: the message names
which. Fix the pattern there and run the workflow again by hand (Actions → Linux desktop build → Run workflow).

The other branches are upstream's, kept as GitHub made them when forking.
