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


def is_autostart_mac():
    return os.path.exists(autostart_path())


_quit_handler_ref = None  # giữ callback ctypes sống suốt đời tiến trình


def install_quit_handler(on_quit):
    """Nhận Apple Event 'quit' (tắt máy / đăng xuất / khởi động lại, Cmd+Q từ Dock,
    `tell application "VietType" to quit`). GTK3 không xử lý event này nên macOS
    báo lỗi -1708 và bị chặn tắt máy. on_quit() chạy trên main thread; trả về
    noErr ngay để macOS tiếp tục tắt máy. True nếu cài được."""
    global _quit_handler_ref
    import ctypes
    try:
        cs = ctypes.CDLL('/System/Library/Frameworks/CoreServices.framework/CoreServices')
    except OSError as e:
        print('quit handler:', e)
        return False
    handler_t = ctypes.CFUNCTYPE(ctypes.c_int16, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    install = cs.AEInstallEventHandler
    install.argtypes = [ctypes.c_uint32, ctypes.c_uint32, handler_t, ctypes.c_void_p, ctypes.c_ubyte]
    install.restype = ctypes.c_int16

    def fourcc(s):
        return int.from_bytes(s.encode('ascii'), 'big')

    def _handler(_event, _reply, _refcon):
        try:
            on_quit()
        except Exception as e:
            print('quit handler:', e)
        return 0  # noErr

    _quit_handler_ref = handler_t(_handler)
    err = install(fourcc('aevt'), fourcc('quit'), _quit_handler_ref, None, 0)
    if err != 0:
        print('quit handler: AEInstallEventHandler error', err)
        return False
    return True


def autostart_argv_mac():
    """ProgramArguments của LaunchAgent hiện có ([] nếu không có/đọc lỗi)."""
    try:
        with open(autostart_path(), 'rb') as f:
            return list(plistlib.load(f).get('ProgramArguments') or [])
    except Exception:
        return []


def set_autostart_mac(on, argv):
    """argv: list, e.g. [python, script] or [bundle_binary]."""
    p = autostart_path()
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
