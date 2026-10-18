#!/bin/bash
# Cài VietType lên Ubuntu 24/26 (GNOME)
set -e
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "== 1. Cài dependency hệ thống =="
sudo apt update
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gnome-shell-extension-appindicator || true

echo "== 2. Copy app vào /opt/viettype =="
sudo mkdir -p /opt/viettype
sudo cp "$SRC_DIR/telex_engine.py" "$SRC_DIR/viettype_app.py" "$SRC_DIR/viettype.svg" /opt/viettype/
sudo chmod +x /opt/viettype/viettype_app.py

echo "== 3. Tạo launcher =="
sudo cp "$SRC_DIR/viettype.desktop" /usr/share/applications/viettype.desktop
sudo update-desktop-database || true

echo "== 4. Bật AppIndicator trên Ubuntu (để hiện top bar) =="
gnome-extensions enable ubuntu-appindicators@ubuntu.com 2>/dev/null || true

echo "== 5. Tự chạy khi mở máy (autostart, có thể tắt trong app) =="
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/viettype.desktop <<EOF
[Desktop Entry]
Type=Application
Name=VietType
Exec=/usr/bin/python3 /opt/viettype/viettype_app.py
Icon=/opt/viettype/viettype.svg
X-GNOME-Autostart-enabled=true
NoDisplay=false
EOF

echo ""
echo "XONG. Mở VietType từ Activities > VietType."
echo "Chạy thử: /usr/bin/python3 /opt/viettype/viettype_app.py"
echo "Lưu ý: dùng /usr/bin/python3 (bản hệ thống) để có Gtk, không dùng mise/venv python."
