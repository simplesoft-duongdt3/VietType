# VietType v1.3.0 — Khung gõ Telex nhỏ cho Ubuntu 26

Cửa sổ nhỏ (320×270), resize thoải mái, gồm:

- **Ô nhập TextArea** gõ Telex trực tiếp (live, kiểu Unikey/OpenKey/GoTV)
- Công tắc **Telex BẬT/TẮT** (tắt = gõ không dấu), **ESC** hoàn tác dấu vừa gõ
- **Chips mẫu câu** `{viết tắt, nội dung}`: scroll ngang, kéo-thả sắp xếp
  - **Click** chip = copy nội dung • **Đúp** chip = chèn vào ô nhập
  - Chuột phải = chèn/copy/sửa/dời/xoá • nút **+** = thêm (nhập viết tắt + nội dung)
  - Tự lưu `~/.config/viettype/samples.json` (tự chuyển dữ liệu mẫu cũ sang dạng mới)
- Nút **Copy** / **Clear**, nút **Top** (always on top), **Mờ** (trong suốt 70%), **Ẩn**
- Kéo cửa sổ từ nền/thanh trạng thái, hoặc giữ **Alt + kéo ở bất kỳ đâu**
- Checkbox **Tự chạy khi mở máy** + `./install.sh` tạo autostart
- **Icon trên top bar** Ubuntu (Ayatana AppIndicator): Hiện/Ẩn, Telex, Mờ, Autostart, Thoát

## Quy tắc Telex (theo OpenKey / GoTV — lõi C `compose.c`)

| Gõ | Ra |
|---|---|
| `aa` `ee` `oo` | `â` `ê` `ô` |
| `aw` `ow` `uw` / `w` | `ă` `ơ` `ư` / `ư` |
| `dd` | `đ` |
| `s` `f` `r` `x` `j` | sắc huyền hỏi ngã nặng |
| `z` | xoá dấu thanh, rồi bóc `ăâêôơưđ` |
| gõ lặp phím (undo) | `ww` → `w`, `tư+w` → `tw`, `aw+w` → `aw` |
| gõ lặp phím (undo) | `ass` → `as` (rồi `s` nữa → `ás`), `ddd` → `dd`, `aaa` → `aa` |
| giữ dấu khi undo | `ấ+a` → `áa` |

Bỏ dấu đúng vị trí âm chính (`hoà`, `tiếng`, `được`, `nghĩa`…), giữ hoa/thường, xử lý `gi`/`qu`.

## Chạy thử

```bash
/usr/bin/python3 viettype_app.py
# hoặc
./run.sh
```

> Bắt buộc dùng `/usr/bin/python3` hệ thống (có `python3-gi` + Gtk). Python mise/venv sẽ báo `No module named 'gi'`.

## Cài đặt đầy đủ (launcher + top bar + autostart)

```bash
./install.sh
```

Script cài `gir1.2-gtk-3.0`, `gir1.2-ayatanaappindicator3-0.1`, bật extension `ubuntu-appindicators`, copy app vào `/opt/viettype`, tạo `VietType` trong Activities và file autostart `~/.config/autostart/viettype.desktop`.

Nếu top bar chưa hiện icon:

```bash
gnome-extensions list | grep -i indicator
gnome-extensions enable ubuntu-appindicators@ubuntu.com
```

Đóng cửa sổ (X) sẽ ẩn xuống top bar, chọn *Thoát* trong menu indicator để tắt hẳn.

## Test engine

```bash
/usr/bin/python3 test_telex.py   # 42 case Telex + undo
```
