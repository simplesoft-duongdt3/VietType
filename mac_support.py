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
