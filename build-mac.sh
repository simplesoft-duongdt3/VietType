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
cp telex_engine.py history_store.py viettype_app.py mac_support.py viettype.svg viettype.icns \
   fog.svg pin.svg eye.svg sun.svg moon.svg "$APP.app/Contents/Resources/"

# Launcher = Mach-O universal (arm64 + x86_64) thay vì shell script. Nó nạp
# libpython của Homebrew và chạy viettype_app.py NGAY TRONG tiến trình của
# VietType.app, nên Activity Monitor / Dock / LaunchServices thấy "VietType"
# (vn.viettype.pad, native Apple Silicon) chứ không phải Python.app.
# Không tìm thấy libpython thì exec python3; không có python3 thì báo lỗi.
LAUNCHER_DIR="$(mktemp -d -t viettype-launcher)"; LAUNCHER_C="$LAUNCHER_DIR/launcher.c"
trap 'rm -rf "$LAUNCHER_DIR"' EXIT
cat > "$LAUNCHER_C" <<'LAUNCHER'
#include <dlfcn.h>
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef int (*py_bytes_main_fn)(int, char **);

static const char *MISSING_MSG =
    "VietType cần Python 3 + GTK 3 từ Homebrew.\n\n"
    "Mở Terminal và chạy:\n"
    "brew install python3 gtk+3 pygobject3 gobject-introspection librsvg adwaita-icon-theme";

static void prepend_env(const char *name, const char *value) {
    const char *old = getenv(name);
    char *buf = NULL;
    int n = (old && *old) ? asprintf(&buf, "%s:%s", value, old)
                          : asprintf(&buf, "%s", value);
    if (n >= 0 && buf) setenv(name, buf, 1);
    free(buf);
}

/* Không có terminal khi mở từ Finder / lúc đăng nhập: báo bằng hộp thoại. */
static int alert(const char *msg) {
    char *script = NULL;
    fprintf(stderr, "VietType: %s\n", msg);
    if (asprintf(&script, "display alert \"VietType\" message \"%s\" as critical", msg) < 0)
        return 1;
    execl("/usr/bin/osascript", "osascript", "-e", script, (char *)NULL);
    return 1;
}

int main(int argc, char *argv[]) {
    char exe[PATH_MAX], real[PATH_MAX], dir[PATH_MAX], script[PATH_MAX];
    char py[PATH_MAX], lib[PATH_MAX], tmp[PATH_MAX];
    uint32_t size = sizeof exe;
    if (_NSGetExecutablePath(exe, &size) != 0 || !realpath(exe, real)) {
        fprintf(stderr, "VietType: cannot resolve executable path\n");
        return 1;
    }
    /* .../VietType.app/Contents/MacOS/VietType -> .../Contents/Resources/viettype_app.py */
    /* dirname() có thể sửa chuỗi đầu vào: luôn đưa bản sao, giữ nguyên real. */
    snprintf(tmp, sizeof tmp, "%s", real);
    snprintf(dir, sizeof dir, "%s", dirname(tmp));       /* .../Contents/MacOS */
    snprintf(tmp, sizeof tmp, "%s", dirname(dir));       /* .../Contents */
    snprintf(script, sizeof script, "%s/Resources/viettype_app.py", tmp);

    const char *prefixes[] = {"/opt/homebrew", "/usr/local", NULL};
    const char *prefix = NULL;
    for (int i = 0; prefixes[i]; i++) {
        snprintf(py, sizeof py, "%s/bin/python3", prefixes[i]);
        if (access(py, X_OK) == 0) { prefix = prefixes[i]; break; }
    }
    if (!prefix) return alert(MISSING_MSG);

    snprintf(tmp, sizeof tmp, "%s/lib/girepository-1.0", prefix);
    prepend_env("GI_TYPELIB_PATH", tmp);
    snprintf(tmp, sizeof tmp, "%s/share", prefix);
    prepend_env("XDG_DATA_DIRS", tmp);

    char **args = calloc((size_t)argc + 2, sizeof *args);
    if (!args) return 1;
    args[1] = script;
    for (int i = 1; i < argc; i++) args[i + 1] = argv[i];

    /* opt/python3 = bản python3 mặc định của Homebrew, tự đổi khi brew nâng cấp. */
    snprintf(lib, sizeof lib,
             "%s/opt/python3/Frameworks/Python.framework/Versions/Current/Python", prefix);
    void *h = dlopen(lib, RTLD_NOW | RTLD_GLOBAL);
    py_bytes_main_fn py_main = h ? (py_bytes_main_fn)dlsym(h, "Py_BytesMain") : NULL;
    if (py_main) {
        args[0] = real;
        return py_main(argc + 1, args);
    }
    fprintf(stderr, "VietType: embed libpython failed (%s), exec %s\n",
            h ? "no Py_BytesMain" : dlerror(), py);

    args[0] = py;
    execv(py, args);
    perror("VietType: execv python3");
    return alert(MISSING_MSG);
}
LAUNCHER
# rpath giống Python.app của Homebrew: typelib GTK tham chiếu dylib bằng tên trần
# (libgobject-2.0.0.dylib), dyld tìm chúng qua LC_RPATH của file chạy chính.
clang -O2 -Wall -Wextra -arch arm64 -arch x86_64 -mmacosx-version-min=11.0 \
  -Wl,-rpath,/opt/homebrew/lib -Wl,-rpath,/usr/local/lib \
  -o "$APP.app/Contents/MacOS/$APP" "$LAUNCHER_C"
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
  <key>LSArchitecturePriority</key><array><string>arm64</string><string>x86_64</string></array>
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
