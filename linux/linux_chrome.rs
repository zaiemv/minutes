//! Linux window chrome.
//!
//! Tauri windows are GTK3 windows, so under GNOME they draw client-side
//! decorations with whatever legacy GTK3 theme the user has selected. Third
//! party GTK3 themes often imitate macOS (traffic-light buttons, centred
//! title), which is the one look a Linux build of Minutes must not have:
//! the in-app UI already carries the Minutes identity, and the frame should
//! read as the desktop's own.
//!
//! GTK4 and libadwaita applications ignore the legacy theme entirely, so on a
//! current GNOME desktop most windows already wear the stock look. This module
//! makes the Minutes window match them by pinning `GTK_THEME` for this
//! process only, before GTK initialises:
//!
//! - `adw-gtk3` (the GNOME-blessed GTK3 port of the libadwaita style) when it
//!   is installed, in its light or dark variant to follow the desktop's
//!   colour scheme;
//! - GTK's built-in `Adwaita` otherwise, again light or dark.
//!
//! A `GTK_THEME` the user has already exported wins: that is the documented
//! GTK way to force a theme on one application, and it must keep working.

use std::path::PathBuf;
use std::process::Command;

const ENV_VAR: &str = "GTK_THEME";

/// Choose and export the GTK theme for this process. Must run before any
/// GTK call, i.e. at the top of `main`, on the main thread, before any
/// other thread exists.
pub fn pin_stock_gnome_theme() {
    if std::env::var_os(ENV_VAR).is_some_and(|value| !value.is_empty()) {
        return;
    }
    let theme = pick_theme(prefers_dark(), &theme_dirs());
    // Safe here: `main` has not spawned threads yet (see call site).
    std::env::set_var(ENV_VAR, theme);
}

/// `true` when the desktop asks for dark colours. GNOME publishes this as the
/// `color-scheme` key; other desktops leave it unset, which reads as light.
fn prefers_dark() -> bool {
    Command::new("gsettings")
        .args(["get", "org.gnome.desktop.interface", "color-scheme"])
        .output()
        .ok()
        .filter(|out| out.status.success())
        .map(|out| String::from_utf8_lossy(&out.stdout).contains("prefer-dark"))
        .unwrap_or(false)
}

/// Directories GTK searches for a named theme, highest precedence first.
fn theme_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Some(data_home) = std::env::var_os("XDG_DATA_HOME").filter(|v| !v.is_empty()) {
        dirs.push(PathBuf::from(data_home).join("themes"));
    } else if let Some(home) = dirs::home_dir() {
        dirs.push(home.join(".local/share/themes"));
    }
    if let Some(home) = dirs::home_dir() {
        dirs.push(home.join(".themes"));
    }
    let data_dirs = std::env::var("XDG_DATA_DIRS")
        .ok()
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| "/usr/local/share:/usr/share".to_string());
    for dir in data_dirs.split(':').filter(|d| !d.is_empty()) {
        dirs.push(PathBuf::from(dir).join("themes"));
    }
    dirs
}

/// The theme name to export. `adw-gtk3` ships its dark variant as a separate
/// theme directory; built-in Adwaita selects dark through the `:dark` suffix.
fn pick_theme(dark: bool, theme_dirs: &[PathBuf]) -> &'static str {
    let adw = if dark { "adw-gtk3-dark" } else { "adw-gtk3" };
    let installed = theme_dirs
        .iter()
        .any(|dir| dir.join(adw).join("gtk-3.0").join("gtk.css").is_file());
    match (installed, dark) {
        (true, true) => "adw-gtk3-dark",
        (true, false) => "adw-gtk3",
        (false, true) => "Adwaita:dark",
        (false, false) => "Adwaita",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn theme_tree(root: &std::path::Path, name: &str) {
        let dir = root.join(name).join("gtk-3.0");
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("gtk.css"), "").unwrap();
    }

    #[test]
    fn falls_back_to_builtin_adwaita_when_adw_gtk3_is_absent() {
        let tmp = tempfile::tempdir().unwrap();
        let dirs = vec![tmp.path().to_path_buf()];
        assert_eq!(pick_theme(true, &dirs), "Adwaita:dark");
        assert_eq!(pick_theme(false, &dirs), "Adwaita");
    }

    #[test]
    fn prefers_installed_adw_gtk3_in_the_matching_variant() {
        let tmp = tempfile::tempdir().unwrap();
        theme_tree(tmp.path(), "adw-gtk3-dark");
        let dirs = vec![tmp.path().to_path_buf()];
        assert_eq!(pick_theme(true, &dirs), "adw-gtk3-dark");
        // Only the dark variant is installed: light must not name a missing theme.
        assert_eq!(pick_theme(false, &dirs), "Adwaita");
        theme_tree(tmp.path(), "adw-gtk3");
        assert_eq!(pick_theme(false, &dirs), "adw-gtk3");
    }

    #[test]
    fn a_bare_theme_directory_without_gtk_css_does_not_count() {
        let tmp = tempfile::tempdir().unwrap();
        std::fs::create_dir_all(tmp.path().join("adw-gtk3-dark")).unwrap();
        let dirs = vec![tmp.path().to_path_buf()];
        assert_eq!(pick_theme(true, &dirs), "Adwaita:dark");
    }
}
