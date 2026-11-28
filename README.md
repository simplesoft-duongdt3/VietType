# VietType v3.6.9 — Khung gõ Telex nhỏ gọn cho Ubuntu & macOS / Compact Telex Pad for Ubuntu & macOS

> **Tiếng Việt:** VietType là một khung nhập liệu nhỏ, luôn sẵn sàng trên Ubuntu — gõ Telex trực tiếp (live), quản lý câu mẫu bằng chips, copy/chèn nhanh, luôn trên cùng, hiện icon trên top bar và tự khởi động cùng hệ thống.
>
> **English:** VietType is a small always-ready input pad for Ubuntu — live Telex typing, chip-based snippet templates, one-click copy/insert, always-on-top, top-bar indicator, and autostart support.

![Platform](https://img.shields.io/badge/platform-Ubuntu%2024%2F26-blue) ![Toolkit](https://img.shields.io/badge/GTK-3-orange) ![Engine](https://img.shields.io/badge/Telex-GoTV%2FOpenKey--style-green) ![Version](https://img.shields.io/badge/version-3.6.9-brightgreen)

---

## English

### 1. Overview

VietType is a lightweight Vietnamese input pad. Instead of switching system-wide input methods, you type in a small window with a built-in Telex engine (behavior compatible with GoTV/OpenKey), then copy the result anywhere — chat, email, documents. Frequently used sentences live as **chips** (`{abbreviation, content}`): single-click to copy, double-click to insert.

### 2. Features

| Area | Details |
|---|---|
| Live Telex input | Type `as` → `á` directly in the text area; toggle Telex ON/OFF (OFF = plain ASCII). Repeat-key undo in GoTV/OpenKey style (`ww` → `w`, `ass` → `as`). **ESC** undoes the last applied mark (50-step history). |
| Undo & history | **Ctrl+Z** / **Ctrl+Shift+Z** (or **Ctrl+Y**) undo/redo whole edits, including *Clear* (200 steps, typing grouped by pause). Every paste / cut / block delete is its own step, so an accidental paste-over is always one Ctrl+Z away; when it replaces most of the text, the old draft is kept as a separate history entry. **Ctrl+H** or the clock button opens the input history: accent-insensitive search (`viet` finds `Việt`), insert/copy/delete, on/off switch. Stored in `~/.local/share/viettype/history.db` (SQLite, mode 600): one row per draft updated in place, duplicates merged, long text zlib-compressed, capped at 1000 entries / 180 days. |
| Template chips | Each template has an **abbreviation** shown on the chip and a **content** body. Chips wrap onto up to 2 visible rows (more scroll vertically), unlimited count, drag-and-drop reorder. **Click** = copy content • **Double-click** = insert at cursor • Right-click = insert / copy / edit / move / delete. The **+** button adds a new template (abbreviation + content, auto-suggested). Stored in `~/.config/viettype/samples.json`; legacy plain-string lists auto-migrate. |
| Window behavior | Header shows the full name with 4 compact icon buttons (pin-on-top, fade, shrink-to-floating-button, dark/light theme). The Telex switch sits in the control row next to Copy / Clear (icon + text). Theme choice is remembered. Drag the status strip, or **Alt + drag anywhere** (text area, chips, buttons) — window borders always resize normally. Default size 320×270, freely resizable, size/position restored on launch. |
| System integration | Top-bar indicator (Ayatana AppIndicator) on Ubuntu, native menu bar text item on macOS (`VCD` / `EN`): view modes, Telex, fade, autostart, dark mode, history, about, quit. Three view modes: window / floating button / hidden. Single instance (opening it again brings the window back). Optional autostart on login (`.desktop` on Ubuntu, Login Items on macOS; `--autostart status\|on\|off`). Version in header subtitle, About dialog and `--version`. |
| Offline & private | Pure local Python, no network, no keylogger-style hooks. Config (`~/.config/viettype`, mode 700) and history are readable only by your account (files mode 600); settings are written atomically. |

### 3. Telex reference (GoTV/OpenKey style)

| Keys | Result |
|---|---|
| `aa` `ee` `oo` | `â` `ê` `ô` |
| `aw` `ow` `uw` / `w` | `ă` `ơ` `ư` / `ư` |
| `dd` / `DD` | `đ` / `Đ` |
| `s` `f` `r` `x` `j` | sắc huyền hỏi ngã nặng |
| `z` | remove tone, then strip `ă â ê ô ơ ư đ` |
| `uoi` / `uou` + `w` | `ươi` / `ươu` (e.g. `nguoiw` → `ngươi`, `tuoiw` → `tươi`, `ruou` + `w` → `rươu`); + `s/f/r/x/j` puts the tone on `ơ` (`ngưới`, `người`, `ngưởi`, `ngưỡi`, `ngượi`) |
| repeat key (undo) | `ww` → `w`, `tư` + `w` → `tw`, `aw` + `w` → `aw` |
| repeat key (undo) | `ass` → `as` (another `s` → `ás`), `ddd` → `dd`, `aaa` → `aa` |
| undo keeps tone | `ấ` + `a` → `áa` |

Tone placement follows the main-vowel rule (`hoà`, `tiếng`, `được`, `nghĩa`), preserves case, and handles `gi`/`qu` onsets.

### 4. Requirements

- Ubuntu 24.04/26.04 (GNOME), system Python: `/usr/bin/python3`
- `python3-gi`, `gir1.2-gtk-3.0`
- For the top-bar icon: `gir1.2-ayatanaappindicator3-0.1` + the `ubuntu-appindicators` GNOME extension

> Do **not** run with mise/venv Python — it lacks `gi` and will report `No module named 'gi'`.

### 5. Quick start

```bash
/usr/bin/python3 viettype_app.py
# or
./run.sh
# print version
/usr/bin/python3 viettype_app.py --version
```

### 6. Full installation (launcher + top bar + autostart)

```bash
./install.sh
```

This installs system dependencies, enables the AppIndicator extension, copies the app to `/opt/viettype`, registers `VietType` in Activities, and creates `~/.config/autostart/viettype.desktop`. Right-click the dock icon → *Add to Favorites* to pin it.

Autostart can also be toggled inside the app (checkbox at the bottom, or the indicator menu).

### 7. Usage tips

- **Snippets:** click a chip to copy, double-click to insert at the cursor. Right-click a chip to edit its abbreviation/content.
- **Undo:** press **ESC** to revert the last Telex transformation, repeatedly if needed.
- **Moving the window:** drag the thin status strip, or hold **Alt** and drag from anywhere.
- **Three view modes** (pick them in the top-bar / menu bar menu, remembered across restarts):
  - **Window** — the normal pad.
  - **Floating button** — a small round, semi-transparent VCD/EN button that stays on top (opaque on hover). Click it to open the pad, drag it anywhere, right-click for the menu. The eye button in the header switches to this mode.
  - **Hidden** — only the top-bar / menu bar item remains. Closing the window (X) switches to this mode when the indicator is active (otherwise to the floating button).
  - Choose *Thoát* (Quit) in the menu to exit fully.
- **Literal letters:** to type a raw `w`/`s`/… after a transformed syllable, just press the key again (`ww` → `w`, `ass` → `as`) or press **ESC**.

### 8. Project layout

```
VietType/
├── viettype_app.py    # GTK3 UI: pad, chips, tray, autostart, drag, ESC-undo
├── telex_engine.py    # Stateless Telex engine (live key-by-key conversion)
├── history_store.py   # Input history (SQLite, dedup + compression + retention)
├── mac_support.py     # macOS: menu bar item, Login Items, quit-on-shutdown (via launcher vt_* API)
├── test_telex.py      # 60 engine test cases (run: /usr/bin/python3 test_telex.py)
├── viettype.svg       # App/dock icon (+ pin/eye/sun/moon/fog.svg header icons)
├── viettype.desktop   # Launcher (StartupWMClass=VietType)
├── install.sh         # Full installer (Linux)
├── build-mac.sh       # macOS .app + DMG builder; compiles the Objective-C launcher (run on a Mac)
├── .github/workflows/build-mac.yml  # CI: DMG for Intel + Apple Silicon
└── run.sh             # Quick launcher
```

### 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'gi'` | Use `/usr/bin/python3`, not mise/venv Python. |
| No top-bar icon | Install `gir1.2-ayatanaappindicator3-0.1` and run `gnome-extensions enable ubuntu-appindicators@ubuntu.com`, then relaunch. The app still works without it. |
| Two dock icons / gray icon | Re-run `./install.sh` so `StartupWMClass=VietType` matches the window class, then log out/in. |
| Can't click/type in the text area | Update to the latest version — window dragging is restricted to the status strip and **Alt + drag**, and never steals text-area clicks. |
| Lost templates | They live in `~/.config/viettype/samples.json` — back up this file. |

### 10. macOS (Intel & Apple Silicon)

**Requirements:** macOS 11+ (Login Items need macOS 13+), [Homebrew](https://brew.sh) and the Xcode Command Line Tools (`xcode-select --install`, Homebrew already needs them).

```bash
brew install python3 gtk+3 pygobject3 gobject-introspection librsvg adwaita-icon-theme
```

**Install (recommended).** Build the app and copy it to Applications:

```bash
bash build-mac.sh                        # -> VietType.app + VietType-3.6.9-mac-<arch>.dmg
cp -R VietType.app /Applications/
open /Applications/VietType.app
```

Or download `VietType-3.6.9-mac-intel.dmg` / `VietType-3.6.9-mac-arm64.dmg` from GitHub Releases (built by `.github/workflows/build-mac.yml`) and drag `VietType.app` to Applications. First launch of a downloaded copy: right-click → *Open* (ad-hoc signature, one time only).

**Run from source (development).** `/opt/homebrew/bin/python3 viettype_app.py` (Intel: `/usr/local/bin/python3`). The menu bar item, Login Items and quit-on-shutdown need the app bundle's launcher; from source the app falls back to a GTK status icon and a LaunchAgent.

**How it works.** `VietType.app/Contents/MacOS/VietType` is a universal (arm64 + x86_64) Objective-C launcher. It embeds Homebrew's Python so the process is *VietType* (native on Apple Silicon), and it provides the macOS-native pieces as a small C API (`vt_*`) that `mac_support.py` calls: the menu bar text item, Login Items (`SMAppService`), the Apple Event *quit* handler and the event-loop wake-up. Python itself never calls the Objective-C runtime.

**On macOS:**
- **Menu bar:** a text item `VCD` (Telex on) / `EN` (Telex off), drawn by macOS in the same font and color as the clock and other items. Left- or right-click opens the menu.
- **View modes:** window, floating button (round, semi-transparent, always on top, drag to move, click to open, right-click for the menu) and hidden (menu bar item only). The eye button → floating button; the red close button → hidden. The last mode is restored on launch.
- **Autostart:** the in-app checkbox / menu item uses **Login Items** (System Settings › General › Login Items). From Terminal: `/Applications/VietType.app/Contents/MacOS/VietType --autostart status|on|off`.
- **Shutdown / restart / logout / Dock › Quit** quit VietType immediately and save the window state.
- Opening VietType again while it runs shows the existing window instead of starting a second copy.
- `Cmd+C / Cmd+V / Cmd+A / Cmd+Z` work in the text area. Telex engine, chips, pin, fade, drag, ESC-undo, history and themes are the same as on Ubuntu.

**macOS troubleshooting**

| Symptom | Fix |
|---|---|
| "VietType cần Python 3 + GTK 3" alert | Run the `brew install …` line above. |
| No `VCD` in the menu bar | On MacBooks with a notch, macOS hides items that don't fit — quit some menu bar apps or hold ⌘ and drag `VCD` to the right. Or use the floating button. |
| Autostart doesn't stick | Check System Settings › General › Login Items › VietType is allowed. `--autostart status` shows `2` when macOS needs your approval. |
| App killed / blocked on a company Mac | Endpoint-security tools (e.g. CrowdStrike, Jamf) may block unsigned apps. Ask IT to allow `vn.viettype.pad`; don't disable the security software. |
| Window gone after restart | It is in the mode you left it in: click `VCD` in the menu bar › *Hiện cửa sổ*. |

---

## Tiếng Việt

### 1. Tổng quan

VietType là khung nhập liệu tiếng Việt gọn nhẹ. Thay vì chuyển bộ gõ toàn hệ thống, bạn gõ trong một cửa sổ nhỏ với engine Telex tích hợp (hành vi tương thích GoTV/OpenKey), rồi copy kết quả đi bất kỳ đâu — chat, email, văn bản. Các câu dùng nhiều được lưu dưới dạng **chips** (`{viết tắt, nội dung}`): click để copy, đúp để chèn.

### 2. Tính năng

| Nhóm | Chi tiết |
|---|---|
| Gõ Telex trực tiếp | Gõ `as` → `á` ngay trong ô nhập; công tắc Telex BẬT/TẮT (TẮT = gõ không dấu). Gõ lặp phím để hoàn tác kiểu GoTV/OpenKey (`ww` → `w`, `ass` → `as`). Phím **ESC** hoàn tác dấu vừa gõ (lịch sử 50 bước). |
| Hoàn tác & lịch sử | **Ctrl+Z** / **Ctrl+Shift+Z** (hoặc **Ctrl+Y**) hoàn tác/làm lại cả thao tác, kể cả nút *Xoá* (200 bước, gộp theo nhịp gõ). Mỗi lần dán / cắt / xoá khối là 1 bước riêng nên lỡ dán đè chỉ cần Ctrl+Z; nếu dán đè phần lớn nội dung, bản cũ được giữ thành mục lịch sử riêng. **Ctrl+H** hoặc nút đồng hồ mở lịch sử nội dung: tìm không dấu (`viet` ra `Việt`), chèn/copy/xoá, bật/tắt lưu. Lưu tại `~/.local/share/viettype/history.db` (SQLite, quyền 600): mỗi bản nháp 1 dòng cập nhật tại chỗ, trùng thì gộp, văn bản dài được nén zlib, giữ tối đa 1000 mục / 180 ngày. |
| Chips mẫu câu | Mỗi mẫu gồm **viết tắt** (hiện trên chip) và **nội dung**. Tự xuống dòng, hiện tối đa 2 dòng (nhiều hơn thì cuộn dọc), không giới hạn số lượng, kéo-thả sắp xếp. **Click** = copy • **Đúp** = chèn vào con trỏ • Chuột phải = chèn / copy / sửa / dời / xoá. Nút **+** thêm mẫu mới (tự gợi ý viết tắt). Lưu tại `~/.config/viettype/samples.json`; dữ liệu mẫu cũ (list chuỗi) tự chuyển sang dạng mới. |
| Cửa sổ | Header hiện tên đầy đủ với 4 nút icon gọn (ghim, mờ, thu nhỏ thành nút nổi, sáng/tối). Công tắc Telex nằm ở hàng điều khiển cạnh Copy / Xoá (icon + chữ). Chế độ sáng/tối được nhớ. Kéo thanh trạng thái, hoặc giữ **Alt + kéo ở mọi nơi** — viền cửa sổ luôn co giãn bình thường. Mặc định 320×270, co giãn tự do, nhớ kích thước/vị trí lần trước. |
| Tích hợp hệ thống | Icon top bar (Ayatana AppIndicator) trên Ubuntu, mục chữ native trên menu bar macOS (`VCD` / `EN`): chế độ hiện, Telex, mờ, tự chạy, chế độ tối, lịch sử, giới thiệu, thoát. Ba chế độ hiện: cửa sổ / nút nổi / ẩn. Chỉ chạy một bản (mở lại sẽ đưa cửa sổ lên). Tuỳ chọn tự chạy khi đăng nhập (`.desktop` trên Ubuntu, Login Items trên macOS; `--autostart status\|on\|off`). Phiên bản ở subtitle, hộp Giới thiệu và `--version`. |
| Riêng tư | Python thuần, chạy offline hoàn toàn, không hook bàn phím toàn cục. Cấu hình (`~/.config/viettype`, quyền 700) và lịch sử chỉ tài khoản của bạn đọc được (file quyền 600); cài đặt được ghi an toàn (atomic). |

### 3. Bảng quy tắc Telex (kiểu GoTV/OpenKey)

| Phím gõ | Kết quả |
|---|---|
| `aa` `ee` `oo` | `â` `ê` `ô` |
| `aw` `ow` `uw` / `w` | `ă` `ơ` `ư` / `ư` |
| `dd` / `DD` | `đ` / `Đ` |
| `s` `f` `r` `x` `j` | sắc huyền hỏi ngã nặng |
| `z` | xoá dấu thanh, rồi bóc `ă â ê ô ơ ư đ` |
| `uoi` / `uou` + `w` | `ươi` / `ươu` (vd `nguoiw` → `ngươi`, `tuoiw` → `tươi`, `ruou` + `w` → `rươu`); + `s/f/r/x/j` đặt dấu lên `ơ` (`ngưới`, `người`, `ngưởi`, `ngưỡi`, `ngượi`) |
| gõ lặp (hoàn tác) | `ww` → `w`, `tư` + `w` → `tw`, `aw` + `w` → `aw` |
| gõ lặp (hoàn tác) | `ass` → `as` (thêm `s` nữa → `ás`), `ddd` → `dd`, `aaa` → `aa` |
| hoàn tác giữ dấu | `ấ` + `a` → `áa` |

Bỏ dấu đúng âm chính (`hoà`, `tiếng`, `được`, `nghĩa`…), giữ hoa/thường, xử lý phụ âm ghép `gi`/`qu`.

### 4. Yêu cầu

- Ubuntu 24.04/26.04 (GNOME), Python hệ thống: `/usr/bin/python3`
- `python3-gi`, `gir1.2-gtk-3.0`
- Để hiện icon top bar: `gir1.2-ayatanaappindicator3-0.1` + extension `ubuntu-appindicators`

> **Không** chạy bằng Python mise/venv — sẽ báo lỗi `No module named 'gi'`.

### 5. Chạy thử

```bash
/usr/bin/python3 viettype_app.py
# hoặc
./run.sh
# xem phiên bản
/usr/bin/python3 viettype_app.py --version
```

### 6. Cài đặt đầy đủ (launcher + top bar + tự chạy)

```bash
./install.sh
```

Script cài dependency, bật extension AppIndicator, copy app vào `/opt/viettype`, tạo `VietType` trong Activities và file autostart `~/.config/autostart/viettype.desktop`. Chuột phải icon trên dock → *Add to Favorites* để ghim.

Cũng có thể bật/tắt autostart ngay trong app (checkbox cuối cửa sổ hoặc menu top bar).

### 7. Mẹo dùng

- **Mẫu câu:** click chip để copy, đúp để chèn vào con trỏ. Chuột phải chip để sửa viết tắt/nội dung.
- **Hoàn tác:** nhấn **ESC** để trả lại dấu vừa gõ, nhấn nhiều lần để lùi tiếp.
- **Di chuyển cửa sổ:** kéo thanh trạng thái mỏng dưới ô nhập, hoặc giữ **Alt** rồi kéo ở bất kỳ đâu.
- **Ba chế độ hiện** (chọn trong menu top bar / menu bar, được nhớ khi mở lại):
  - **Cửa sổ** — khung gõ bình thường.
  - **Nút nổi** — nút tròn nhỏ VCD/EN, trong suốt, luôn trên cùng (rõ hẳn khi rê chuột vào). Click để mở khung gõ, kéo để di chuyển, chuột phải để mở menu. Nút con mắt trên thanh tiêu đề chuyển sang chế độ này.
  - **Ẩn** — chỉ còn mục trên top bar / menu bar. Nút X chuyển sang chế độ này khi có indicator (không có thì chuyển sang nút nổi).
  - Chọn *Thoát* trong menu để tắt hẳn.
- **Gõ chữ thô:** muốn ra chữ cái gốc sau âm đã biến đổi, gõ lặp phím đó (`ww` → `w`, `ass` → `as`) hoặc nhấn **ESC**.

### 8. Cấu trúc dự án

```
VietType/
├── viettype_app.py    # Giao diện GTK3: ô nhập, chips, tray, autostart, kéo thả, ESC
├── telex_engine.py    # Engine Telex stateless (biến đổi từng phím live)
├── history_store.py   # Lịch sử nội dung (SQLite, chống trùng + nén + tự dọn)
├── mac_support.py     # macOS: mục menu bar, Login Items, thoát khi tắt máy (qua API vt_* của launcher)
├── test_telex.py      # 60 case kiểm thử (chạy: /usr/bin/python3 test_telex.py)
├── viettype.svg       # Icon app/dock (+ pin/eye/sun/moon/fog.svg cho header)
├── viettype.desktop   # Launcher (StartupWMClass=VietType)
├── install.sh         # Cài đặt đầy đủ (Linux)
├── build-mac.sh       # Đóng gói .app + DMG macOS, biên dịch launcher Objective-C (chạy trên máy Mac)
├── .github/workflows/build-mac.yml  # CI: build DMG Intel + Apple Silicon
└── run.sh             # Chạy nhanh
```

### 9. Xử lý sự cố

| Hiện tượng | Cách sửa |
|---|---|
| `No module named 'gi'` | Dùng `/usr/bin/python3`, không dùng Python mise/venv. |
| Không thấy icon top bar | Cài `gir1.2-ayatanaappindicator3-0.1`, chạy `gnome-extensions enable ubuntu-appindicators@ubuntu.com`, mở lại app. Không có indicator app vẫn chạy. |
| Dock hiện 2 icon / icon xám | Chạy lại `./install.sh` để `StartupWMClass=VietType` khớp class cửa sổ, rồi đăng nhập lại. |
| Không click/gõ được ô nhập | Cập nhật bản mới nhất — kéo cửa sổ giờ chỉ tác động nền/thanh trạng thái và **Alt + kéo**, không cướp click ô nhập. |
| Mất mẫu câu | Mẫu lưu ở `~/.config/viettype/samples.json` — hãy sao lưu file này. |

### 10. macOS (Intel & Apple Silicon)

**Yêu cầu:** macOS 11+ (Login Items cần macOS 13+), [Homebrew](https://brew.sh) và Xcode Command Line Tools (`xcode-select --install`, Homebrew vốn đã cần).

```bash
brew install python3 gtk+3 pygobject3 gobject-introspection librsvg adwaita-icon-theme
```

**Cài đặt (khuyên dùng).** Build app rồi chép vào Applications:

```bash
bash build-mac.sh                        # -> VietType.app + VietType-3.6.9-mac-<arch>.dmg
cp -R VietType.app /Applications/
open /Applications/VietType.app
```

Hoặc tải `VietType-3.6.9-mac-intel.dmg` / `VietType-3.6.9-mac-arm64.dmg` từ GitHub Releases (do `.github/workflows/build-mac.yml` build) và kéo `VietType.app` vào Applications. Lần đầu mở bản tải về: chuột phải → *Open* (chữ ký ad-hoc, chỉ một lần).

**Chạy từ mã nguồn (khi phát triển).** `/opt/homebrew/bin/python3 viettype_app.py` (Intel: `/usr/local/bin/python3`). Mục chữ menu bar, Login Items và tự thoát khi tắt máy cần launcher của app; chạy từ mã nguồn thì app dùng icon GTK và LaunchAgent thay thế.

**Cách hoạt động.** `VietType.app/Contents/MacOS/VietType` là launcher Objective-C universal (arm64 + x86_64). Nó nhúng Python của Homebrew nên tiến trình tên là *VietType* (chạy native trên Apple Silicon), và cung cấp phần native của macOS qua một API C nhỏ (`vt_*`) mà `mac_support.py` gọi: mục chữ menu bar, Login Items (`SMAppService`), nhận Apple Event *quit* và đánh thức vòng lặp sự kiện. Python không tự gọi runtime Objective-C.

**Trên macOS:**
- **Menu bar:** mục chữ `VCD` (bật Telex) / `EN` (tắt Telex), do macOS vẽ cùng font và màu với đồng hồ và các mục khác. Bấm chuột trái hoặc phải để mở menu.
- **Chế độ hiện:** cửa sổ, nút nổi (tròn, trong suốt, luôn trên cùng, kéo để di chuyển, click để mở, chuột phải để mở menu) và ẩn (chỉ còn mục menu bar). Nút con mắt → nút nổi; nút đỏ đóng cửa sổ → ẩn. Mở lại app sẽ về đúng chế độ lần trước.
- **Tự chạy:** checkbox / mục menu trong app dùng **Login Items** (System Settings › General › Login Items). Từ Terminal: `/Applications/VietType.app/Contents/MacOS/VietType --autostart status|on|off`.
- **Tắt máy / khởi động lại / đăng xuất / Quit trên Dock** đều thoát VietType ngay và lưu trạng thái cửa sổ.
- Mở VietType lần nữa khi đang chạy sẽ hiện cửa sổ đang có, không mở thêm bản thứ hai.
- `Cmd+C / Cmd+V / Cmd+A / Cmd+Z` hoạt động trong ô nhập. Engine Telex, chips, ghim, mờ, kéo thả, ESC, lịch sử và sáng/tối giống hệt Ubuntu.

**Xử lý sự cố trên macOS**

| Hiện tượng | Cách sửa |
|---|---|
| Hộp thoại "VietType cần Python 3 + GTK 3" | Chạy dòng `brew install …` ở trên. |
| Không thấy `VCD` trên menu bar | MacBook có tai thỏ sẽ giấu mục không đủ chỗ — thoát bớt app menu bar, hoặc giữ ⌘ và kéo `VCD` sang phải. Hoặc dùng nút nổi. |
| Tự chạy không giữ được | Vào System Settings › General › Login Items, cho phép VietType. `--autostart status` báo `2` khi macOS cần bạn duyệt. |
| App bị kill / chặn trên máy công ty | Phần mềm bảo mật (vd CrowdStrike, Jamf) có thể chặn app không ký. Nhờ IT cho phép `vn.viettype.pad`; đừng tắt phần mềm bảo mật. |
| Mở lại máy không thấy cửa sổ | App đang ở chế độ bạn để lần trước: bấm `VCD` trên menu bar › *Hiện cửa sổ*. |
