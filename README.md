# VietType v1.3.0 — Khung gõ Telex nhỏ gọn cho Ubuntu / Compact Telex Pad for Ubuntu

> **Tiếng Việt:** VietType là một khung nhập liệu nhỏ, luôn sẵn sàng trên Ubuntu — gõ Telex trực tiếp (live), quản lý câu mẫu bằng chips, copy/chèn nhanh, luôn trên cùng, hiện icon trên top bar và tự khởi động cùng hệ thống.
>
> **English:** VietType is a small always-ready input pad for Ubuntu — live Telex typing, chip-based snippet templates, one-click copy/insert, always-on-top, top-bar indicator, and autostart support.

![Platform](https://img.shields.io/badge/platform-Ubuntu%2024%2F26-blue) ![Toolkit](https://img.shields.io/badge/GTK-3-orange) ![Engine](https://img.shields.io/badge/Telex-GoTV%2FOpenKey--style-green) ![Version](https://img.shields.io/badge/version-1.3.0-brightgreen)

---

## English

### 1. Overview

VietType is a lightweight Vietnamese input pad. Instead of switching system-wide input methods, you type in a small window with a built-in Telex engine (behavior compatible with GoTV/OpenKey), then copy the result anywhere — chat, email, documents. Frequently used sentences live as **chips** (`{abbreviation, content}`): single-click to copy, double-click to insert.

### 2. Features

| Area | Details |
|---|---|
| Live Telex input | Type `as` → `á` directly in the text area; toggle Telex ON/OFF (OFF = plain ASCII). Repeat-key undo in GoTV/OpenKey style (`ww` → `w`, `ass` → `as`). **ESC** undoes the last applied mark (50-step history). |
| Template chips | Each template has an **abbreviation** shown on the chip and a **content** body. Horizontal scroll, unlimited count, drag-and-drop reorder. **Click** = copy content • **Double-click** = insert at cursor • Right-click = insert / copy / edit / move / delete. The **+** button adds a new template (abbreviation + content, auto-suggested). Stored in `~/.config/viettype/samples.json`; legacy plain-string lists auto-migrate. |
| Window behavior | Always-on-top toggle (`Top`), fade toggle (`Mờ` — 70% opacity), hide-to-tray (`Ẩn`). Drag from the background/status strip, or **Alt + drag anywhere** (text area, chips, buttons). Default size 320×270, freely resizable. |
| System integration | Top-bar indicator (Ayatana AppIndicator): show/hide, Telex, fade, autostart, about, quit. Dock icon via `StartupWMClass` + SVG icon. Optional autostart on login. Version shown in header subtitle, About dialog, and `--version`. |
| Offline & private | Pure local Python, no network, no keylogger-style hooks. |

### 3. Telex reference (GoTV/OpenKey style)

| Keys | Result |
|---|---|
| `aa` `ee` `oo` | `â` `ê` `ô` |
| `aw` `ow` `uw` / `w` | `ă` `ơ` `ư` / `ư` |
| `dd` / `DD` | `đ` / `Đ` |
| `s` `f` `r` `x` `j` | sắc huyền hỏi ngã nặng |
| `z` | remove tone, then strip `ă â ê ô ơ ư đ` |
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
- **Hiding:** closing the window (X) hides it to the top bar when the indicator is active; choose *Quit* in the indicator menu to exit fully.
- **Literal letters:** to type a raw `w`/`s`/… after a transformed syllable, just press the key again (`ww` → `w`, `ass` → `as`) or press **ESC**.

### 8. Project layout

```
VietType/
├── viettype_app.py    # GTK3 UI: pad, chips, tray, autostart, drag, ESC-undo
├── telex_engine.py    # Stateless Telex engine (live key-by-key conversion)
├── test_telex.py      # 42 engine test cases (run: /usr/bin/python3 test_telex.py)
├── viettype.svg       # App/dock icon
├── viettype.desktop   # Launcher (StartupWMClass=VietType)
├── install.sh         # Full installer
└── run.sh             # Quick launcher
```

### 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'gi'` | Use `/usr/bin/python3`, not mise/venv Python. |
| No top-bar icon | Install `gir1.2-ayatanaappindicator3-0.1` and run `gnome-extensions enable ubuntu-appindicators@ubuntu.com`, then relaunch. The app still works without it. |
| Two dock icons / gray icon | Re-run `./install.sh` so `StartupWMClass=VietType` matches the window class, then log out/in. |
| Can't click/type in the text area | Update to the latest version — window dragging is now restricted to the background/status strip and **Alt + drag**, and never steals text-area clicks. |
| Lost templates | They live in `~/.config/viettype/samples.json` — back up this file. |

---

## Tiếng Việt

### 1. Tổng quan

VietType là khung nhập liệu tiếng Việt gọn nhẹ. Thay vì chuyển bộ gõ toàn hệ thống, bạn gõ trong một cửa sổ nhỏ với engine Telex tích hợp (hành vi tương thích GoTV/OpenKey), rồi copy kết quả đi bất kỳ đâu — chat, email, văn bản. Các câu dùng nhiều được lưu dưới dạng **chips** (`{viết tắt, nội dung}`): click để copy, đúp để chèn.

### 2. Tính năng

| Nhóm | Chi tiết |
|---|---|
| Gõ Telex trực tiếp | Gõ `as` → `á` ngay trong ô nhập; công tắc Telex BẬT/TẮT (TẮT = gõ không dấu). Gõ lặp phím để hoàn tác kiểu GoTV/OpenKey (`ww` → `w`, `ass` → `as`). Phím **ESC** hoàn tác dấu vừa gõ (lịch sử 50 bước). |
| Chips mẫu câu | Mỗi mẫu gồm **viết tắt** (hiện trên chip) và **nội dung**. Cuộn ngang không giới hạn, kéo-thả sắp xếp. **Click** = copy • **Đúp** = chèn vào con trỏ • Chuột phải = chèn / copy / sửa / dời / xoá. Nút **+** thêm mẫu mới (tự gợi ý viết tắt). Lưu tại `~/.config/viettype/samples.json`; dữ liệu mẫu cũ (list chuỗi) tự chuyển sang dạng mới. |
| Cửa sổ | `Top` = luôn trên cùng, `Mờ` = trong suốt 70%, `Ẩn` = thu xuống khay. Kéo từ nền/thanh trạng thái, hoặc giữ **Alt + kéo ở mọi nơi**. Mặc định 320×270, co giãn tự do. |
| Tích hợp hệ thống | Icon top bar (Ayatana AppIndicator): hiện/ẩn, Telex, mờ, autostart, giới thiệu, thoát. Icon dock qua `StartupWMClass` + SVG. Tuỳ chọn tự chạy khi đăng nhập. Phiên bản hiện ở subtitle, hộp Giới thiệu và `--version`. |
| Riêng tư | Python thuần, chạy offline hoàn toàn, không hook bàn phím toàn cục. |

### 3. Bảng quy tắc Telex (kiểu GoTV/OpenKey)

| Phím gõ | Kết quả |
|---|---|
| `aa` `ee` `oo` | `â` `ê` `ô` |
| `aw` `ow` `uw` / `w` | `ă` `ơ` `ư` / `ư` |
| `dd` / `DD` | `đ` / `Đ` |
| `s` `f` `r` `x` `j` | sắc huyền hỏi ngã nặng |
| `z` | xoá dấu thanh, rồi bóc `ă â ê ô ơ ư đ` |
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
- **Ẩn:** nút X sẽ ẩn xuống top bar khi có indicator; chọn *Thoát* trong menu indicator để tắt hẳn.
- **Gõ chữ thô:** muốn ra chữ cái gốc sau âm đã biến đổi, gõ lặp phím đó (`ww` → `w`, `ass` → `as`) hoặc nhấn **ESC**.

### 8. Cấu trúc dự án

```
VietType/
├── viettype_app.py    # Giao diện GTK3: ô nhập, chips, tray, autostart, kéo thả, ESC
├── telex_engine.py    # Engine Telex stateless (biến đổi từng phím live)
├── test_telex.py      # 42 case kiểm thử (chạy: /usr/bin/python3 test_telex.py)
├── viettype.svg       # Icon app/dock
├── viettype.desktop   # Launcher (StartupWMClass=VietType)
├── install.sh         # Cài đặt đầy đủ
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
