#!/bin/bash
# Build VietType.app + DMG on macOS (Intel x86_64 or Apple Silicon arm64).
# Run ON a Mac (or via GitHub Actions, see .github/workflows/build-mac.yml).
# Output: VietType-<version>-mac-intel.dmg / VietType-<version>-mac-arm64.dmg
set -e
cd "$(dirname "$0")"

VERSION=$(/usr/bin/python3 -c "import re;print(re.search(r\"APP_VERSION = '([^']+)'\", open('viettype_app.py').read()).group(1))")
UNAME_M=$(uname -m)
if [ "$UNAME_M" = "arm64" ]; then ARCH=arm64; else ARCH=intel; fi
APP=VietType
DMG="$APP-$VERSION-mac-$ARCH.dmg"

echo "== VietType $VERSION for macOS ($UNAME_M -> $ARCH) =="

if ! command -v brew >/dev/null 2>&1; then
  echo "Cài Homebrew trước: https://brew.sh"; exit 1
fi
brew install python3 gtk+3 pygobject3 gobject-introspection librsvg adwaita-icon-theme || true
PYBIN="$(brew --prefix)/bin/python3"
"$PYBIN" -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk; print('GTK OK:', Gtk._version)"

# .icns từ viettype.svg
if [ ! -f viettype.icns ]; then
  echo "== Tạo viettype.icns =="
  rm -rf viettype.iconset; mkdir -p viettype.iconset
  for s in 16 32 64 128 256 512; do
    rsvg-convert -w $s -h $s viettype.svg -o "viettype.iconset/icon_${s}x${s}.png"
    d=$((s * 2))
    rsvg-convert -w $d -h $d viettype.svg -o "viettype.iconset/icon_${s}x${s}@2x.png"
  done
  iconutil -c icns viettype.iconset -o viettype.icns
  rm -rf viettype.iconset
fi

echo "== Đóng gói $APP.app =="
rm -rf "$APP.app" "$DMG"
mkdir -p "$APP.app/Contents/MacOS" "$APP.app/Contents/Resources"
cp telex_engine.py viettype_app.py mac_support.py viettype.svg viettype.icns \
   fog.svg pin.svg eye.svg sun.svg moon.svg "$APP.app/Contents/Resources/"

cat > "$APP.app/Contents/MacOS/$APP" <<'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -x "$p" ]; then PY="$p"; break; fi
done
export GI_TYPELIB_PATH="$(brew --prefix 2>/dev/null)/lib/girepository-1.0:${GI_TYPELIB_PATH}"
export XDG_DATA_DIRS="$(brew --prefix 2>/dev/null)/share:${XDG_DATA_DIRS}"
exec "$PY" "$DIR/viettype_app.py" "$@"
LAUNCHER
chmod +x "$APP.app/Contents/MacOS/$APP"

cat > "$APP.app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>VietType</string>
  <key>CFBundleDisplayName</key><string>VietType</string>
  <key>CFBundleIdentifier</key><string>vn.viettype.pad</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleExecutable</key><string>VietType</string>
  <key>CFBundleIconFile</key><string>viettype</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleSignature</key><string>????</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSRequiresAquaSystemAppearance</key><false/>
</dict>
</plist>
PLIST

# Ký ad-hoc để chạy được (Gatekeeper: mở lần đầu bằng chuột phải > Open)
codesign --force --deep --sign - "$APP.app" || true

echo "== Tạo DMG =="
hdiutil create -volname "$APP" -srcfolder "$APP.app" -ov -format UDZO "$DMG"
echo "DONE: $DMG"
ls -la "$DMG"
