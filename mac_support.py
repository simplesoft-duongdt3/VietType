"""macOS helpers for VietType (Intel x86_64 + Apple Silicon arm64).

Stdlib only, safe to import on any platform. All mac-only behavior is
gated behind is_mac() so Linux is untouched.
"""
import os
import sys
import plistlib

APP_ID = 'vn.viettype.pad'


def is_mac():
    return sys.platform == 'darwin'


def base_dir():
    """Where bundled resources live (source tree or .app bundle)."""
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            return meipass
        exe = sys.executable
        res = os.path.join(os.path.dirname(os.path.dirname(exe)), 'Resources')
        if os.path.isdir(res):
            return res
        return os.path.dirname(exe)
    return os.path.dirname(os.path.abspath(__file__))


def icon_file():
    d = base_dir()
    for n in ('viettype.icns', 'viettype.svg'):
        p = os.path.join(d, n)
        if os.path.exists(p):
            return p
    return None


def autostart_path():
    return os.path.expanduser('~/Library/LaunchAgents/%s.plist' % APP_ID)


# ---- Phần native: các hàm vt_* trong launcher của VietType.app (Objective-C) ----
# Python chỉ gọi các hàm C đã biên dịch sẵn, không tự gọi runtime Objective-C.
# Chạy từ mã nguồn (không có launcher) thì native() = None và app dùng cách dự phòng.
_native = False
_callbacks = []          # giữ callback ctypes sống suốt đời tiến trình


def native():
    global _native
    if _native is not False:
        return _native
    _native = None
    if not is_mac():
        return None
    try:
        import ctypes
        lib = ctypes.CDLL(None)                       # chính tiến trình (launcher)
        lib.vt_wake.restype = None
        lib.vt_status_create.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        lib.vt_status_create.restype = ctypes.c_int
        lib.vt_status_set_title.argtypes = [ctypes.c_char_p]
        lib.vt_status_set_title.restype = None
        lib.vt_status_set_tooltip.argtypes = [ctypes.c_char_p]
        lib.vt_status_set_tooltip.restype = None
        lib.vt_install_quit_handler.argtypes = [ctypes.c_void_p]
        lib.vt_install_quit_handler.restype = ctypes.c_int
        lib.vt_status_anchor.argtypes = [ctypes.POINTER(ctypes.c_double)] * 2
        lib.vt_status_anchor.restype = ctypes.c_int
        lib.vt_login_status.restype = ctypes.c_int
        lib.vt_login_set.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        lib.vt_login_set.restype = ctypes.c_int
        _native = lib
    except (AttributeError, OSError):
        _native = None
    return _native


def wake_event_loop():
    lib = native()
    if lib is not None:
        lib.vt_wake()


# SMAppServiceStatus
LOGIN_NOT_REGISTERED, LOGIN_ENABLED, LOGIN_REQUIRES_APPROVAL, LOGIN_NOT_FOUND = 0, 1, 2, 3


def login_item_status():
    """Trạng thái Login Item của VietType.app, hoặc None nếu không dùng được
    (chạy từ mã nguồn, macOS < 13)."""
    lib = native()
    if lib is None:
        return None
    st = lib.vt_login_status()
    return None if st < 0 else st


def set_login_item(on):
    """Bật/tắt VietType trong System Settings > General > Login Items. (ok, lỗi)"""
    import ctypes
    lib = native()
    if lib is None:
        return False, 'Login Items cần chạy từ VietType.app'
    buf = ctypes.create_string_buffer(512)
    ok = bool(lib.vt_login_set(1 if on else 0, buf, len(buf)))
    return ok, buf.value.decode('utf-8', 'replace')


def is_autostart_mac():
    st = login_item_status()
    if st in (LOGIN_ENABLED, LOGIN_REQUIRES_APPROVAL):
        return True
    return os.path.exists(autostart_path())


class MacStatusItem:
    """Mục chữ (VCD/EN) trên menu bar, do launcher tạo bằng NSStatusItem: macOS tự vẽ
    cùng font/màu với các mục menu bar khác. on_click(x, y): góc dưới-trái của mục
    theo toạ độ GDK, gọi qua GLib.idle_add (launcher đánh thức vòng lặp ngay sau đó)."""

    def __init__(self, title, on_click):
        import ctypes
        lib = native()
        if lib is None:
            raise RuntimeError('launcher native API không có (chạy từ mã nguồn?)')
        self._lib = lib
        self._title = title
        self.on_click = on_click

        def clicked(x, y):
            from gi.repository import GLib
            GLib.idle_add(lambda: (self.on_click(int(x), int(y)), False)[-1])

        cb = ctypes.CFUNCTYPE(None, ctypes.c_double, ctypes.c_double)(clicked)
        _callbacks.append(cb)
        if not lib.vt_status_create(title.encode('utf-8'), ctypes.cast(cb, ctypes.c_void_p)):
            raise RuntimeError('không tạo được mục menu bar')

    def set_text(self, text):
        self._title = text
        self._lib.vt_status_set_title(text.encode('utf-8'))

    def set_tooltip(self, text):
        self._lib.vt_status_set_tooltip(text.encode('utf-8'))

    def title(self):
        return self._title

    def anchor(self):
        """(x, y) góc dưới-trái của mục, toạ độ GDK; None nếu chưa hiện."""
        import ctypes
        x, y = ctypes.c_double(), ctypes.c_double()
        if self._lib.vt_status_anchor(ctypes.byref(x), ctypes.byref(y)):
            return int(x.value), int(y.value)
        return None


def install_quit_handler(on_quit):
    """Nhận Apple Event 'quit' (tắt máy / khởi động lại / đăng xuất / Quit trên Dock).
    on_quit() chạy trên main thread; launcher đánh thức vòng lặp ngay sau đó.
    True nếu cài được (cần launcher của VietType.app)."""
    import ctypes
    lib = native()
    if lib is None:
        return False

    def handler():
        try:
            on_quit()
        except Exception as e:
            print('quit handler:', e)

    cb = ctypes.CFUNCTYPE(None)(handler)
    _callbacks.append(cb)
    return bool(lib.vt_install_quit_handler(ctypes.cast(cb, ctypes.c_void_p)))


def autostart_argv_mac():
    """ProgramArguments của LaunchAgent hiện có ([] nếu không có/đọc lỗi)."""
    try:
        with open(autostart_path(), 'rb') as f:
            return list(plistlib.load(f).get('ProgramArguments') or [])
    except Exception:
        return []


def set_autostart_mac(on, argv):
    """Bật/tắt tự chạy. Chạy từ VietType.app (macOS 13+): dùng Login Items của macOS
    (SMAppService) — không nằm trong ~/Library/LaunchAgents nên không bị công cụ
    đồng bộ/quản lý máy ghi đè thư mục đó xoá mất. Ngoài ra: LaunchAgent với argv
    (vd. [python, script] khi chạy từ mã nguồn)."""
    p = autostart_path()
    if login_item_status() is not None:
        ok, msg = set_login_item(on)
        if not ok:
            print('autostart(login item):', msg)
            return False
        try:
            os.remove(p)             # bỏ LaunchAgent cũ để không chạy 2 lần
        except OSError:
            pass
        return True
    try:
        if not on:
            try:
                os.remove(p)
            except OSError:
                pass
            return True
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            plistlib.dump({'Label': APP_ID,
                           'ProgramArguments': list(argv),
                           'RunAtLoad': True}, f)
        return True
    except Exception as e:
        print('autostart(mac):', e)
        return False
