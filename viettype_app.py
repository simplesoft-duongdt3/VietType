#!/usr/bin/env /usr/bin/python3
"""VietType: TextArea gõ Telex + chips mẫu câu (viết tắt + nội dung).
- Click chip: copy nội dung • Đúp chip: chèn vào ô nhập • Phải: sửa/xoá/dời
- Kéo-thả chip để sắp xếp • ESC: hoàn tác dấu vừa gõ
- Alt+kéo (mọi nơi) hoặc kéo từ nền/thanh trạng thái để di chuyển cửa sổ."""
import json, os, sys, time

# Wayland (GNOME) bỏ qua set_keep_above + vị trí cửa sổ → chạy qua XWayland để ghim (pin) hoạt động
if sys.platform.startswith('linux'):
    os.environ.setdefault('GDK_BACKEND', 'x11')

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject, GLib, Pango

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telex_engine import TelexEngine
from history_store import HistoryStore

try:
    import mac_support as _mac
    if not _mac.is_mac():
        _mac = None
except Exception:
    _mac = None

APP_ID = 'vn.viettype.pad'
APP_VERSION = '1.6.9'
CONFIG_DIR = os.path.expanduser('~/.config/viettype')
SAMPLES_FILE = os.path.join(CONFIG_DIR, 'samples.json')
AUTOSTART_FILE = os.path.expanduser('~/.config/autostart/viettype.desktop')
STATE_FILE = os.path.join(CONFIG_DIR, 'state.json')
HISTORY_FILE = os.path.join(os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share'),
                            'viettype', 'history.db')
SNAP_MAX = 200              # số bước Ctrl+Z tối đa
SNAP_MAX_CHARS = 2_000_000  # giới hạn bộ nhớ cho các bước Ctrl+Z
BIG_EDIT_CHARS = 8          # chèn/xoá >= N ký tự 1 lần = 1 bước Ctrl+Z riêng
                            # (dán, cắt, xoá/gõ đè vùng chọn luôn là bước riêng)
OVERWRITE_MIN = 20          # xoá/đè >= N ký tự và >= nửa nội dung -> giữ bản cũ thành mục lịch sử riêng


def app_dir():
    return os.path.dirname(os.path.abspath(__file__))


def icon_path():
    if _mac is not None:
        p = _mac.icon_file()
        if p:
            return p
    for p in ('/opt/viettype/viettype.svg',
              os.path.join(app_dir(), 'viettype.svg')):
        if os.path.exists(p):
            return p
    return None


def asset_path(name):
    for p in (os.path.join('/opt/viettype', name),
              os.path.join(app_dir(), name)):
        if os.path.exists(p):
            return p
    return None


def header_icon(icon_name, fallback_file=None, size=16):
    """Ảnh cho nút header: ưu tiên icon theme, thiếu thì dùng file SVG kèm app."""
    try:
        theme = Gtk.IconTheme.get_default()
        if theme is not None and theme.has_icon(icon_name):
            return Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
    except Exception:
        pass
    if fallback_file:
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(fallback_file, size, size)
            return Gtk.Image.new_from_pixbuf(pb)
        except Exception:
            pass
    return Gtk.Image.new_from_icon_name('missing-image', Gtk.IconSize.MENU)


def file_icon(name, size=16):
    """Ảnh từ file SVG kèm app (chuẩn mọi theme): pin.svg / eye.svg / fog.svg."""
    p = asset_path(name)
    if p:
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(p, size, size)
            return Gtk.Image.new_from_pixbuf(pb)
        except Exception as e:
            print('icon file:', e)
    return Gtk.Image.new_from_icon_name('missing-image', Gtk.IconSize.MENU)


def app_exec_path():
    installed = '/opt/viettype/viettype_app.py'
    if os.path.exists(installed):
        return '/usr/bin/python3 ' + installed
    return '/usr/bin/python3 ' + os.path.abspath(__file__)


def is_autostart():
    if _mac is not None:
        return _mac.is_autostart_mac()
    return os.path.exists(AUTOSTART_FILE)


def set_autostart(on):
    if _mac is not None:
        if getattr(sys, 'frozen', False):
            argv = [sys.executable]
        else:
            argv = [sys.executable, os.path.abspath(__file__)]
        return _mac.set_autostart_mac(bool(on), argv)
    try:
        if on:
            os.makedirs(os.path.dirname(AUTOSTART_FILE), exist_ok=True)
            with open(AUTOSTART_FILE, 'w', encoding='utf-8') as f:
                f.write('[Desktop Entry]\nType=Application\nName=VietType\n'
                        f'Exec={app_exec_path()}\n'
                        'Icon=accessories-text-editor\n'
                        'X-GNOME-Autostart-enabled=true\nNoDisplay=false\n')
        else:
            if os.path.exists(AUTOSTART_FILE):
                os.remove(AUTOSTART_FILE)
        return True
    except Exception as e:
        print('autostart:', e)
        return False

WORD_DELIMS = set(' \t\n.,;:!?()[]{}<>\"\'/\\|@#$%^&*-+=~`0123456789')
CHIP_TARGETS = [Gtk.TargetEntry.new('VIETTYPE_CHIP', Gtk.TargetFlags.SAME_APP, 0)]


def short_label(s, taken):
    t = s.strip()
    base = t[:3] if len(t) >= 3 else t
    if base not in taken:
        taken.add(base)
        return base
    i = 2
    while f'{base}{i}' in taken:
        i += 1
    taken.add(f'{base}{i}')
    return f'{base}{i}'


def load_samples():
    """Đọc mẫu câu. Mỗi mẫu = {'abbr': viết tắt, 'content': nội dung}.
    Tự chuyển dữ liệu cũ (list chuỗi) sang định dạng mới.
    Không có mẫu mặc định: chưa có file -> rỗng, file rỗng -> rỗng,
    file hỏng -> rỗng (không tự sinh gì thêm)."""
    try:
        with open(SAMPLES_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get('templates'), list):
            d = d['templates']
        if not isinstance(d, list):
            return []
        taken = set()
        out = []
        for x in d:
            if isinstance(x, dict) and str(x.get('content', '')).strip():
                ab = str(x.get('abbr', '')).strip()
                co = str(x['content']).strip()
            else:
                co = str(x).strip()
                ab = ''
            if not co:
                continue
            if not ab:
                ab = short_label(co, taken)
            elif ab in taken:
                ab = short_label(ab, taken)
            else:
                taken.add(ab)
            out.append({'abbr': ab, 'content': co})
        return out
    except Exception as e:
        print('samples:', e)
    return []


def save_samples(s):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(SAMPLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print('save:', e)


def load_window_state():
    """Dict trạng thái đã lưu: width/height/x/y/keep_above; {} nếu chưa có."""
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
            if isinstance(d, dict):
                return d
    except Exception:
        pass
    return {}


def save_window_state(w, h, x, y, keep_above=False, dark=False, history=True):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'width': w, 'height': h, 'x': x, 'y': y,
                       'keep_above': bool(keep_above), 'dark': bool(dark),
                       'history': bool(history)}, f)
    except Exception as e:
        print('state:', e)


class VietTypeWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title='VietType')
        # WM_CLASS phải khớp StartupWMClass trong .desktop để dock gom icon
        try:
            self.set_wmclass('VietType', 'VietType')
        except Exception:
            pass
        self._theme_menu = None
        ip = icon_path()
        if ip:
            try:
                self.set_icon_from_file(ip)
            except Exception as e:
                print('icon:', e)
        self.set_default_size(320, 270)
        # Khôi phục kích thước/vị trí lần trước (nếu có)
        self._saved = load_window_state()
        try:
            _sw, _sh = int(self._saved.get('width', 0)), int(self._saved.get('height', 0))
            _sx, _sy = int(self._saved.get('x', -1)), int(self._saved.get('y', -1))
        except (TypeError, ValueError):
            _sw = _sh = 0
            _sx = _sy = -1
        if _sw >= 220 and _sh >= 160:
            self.resize(_sw, _sh)
        if _sx >= 0 and _sy >= 0:
            self.move(_sx, _sy)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.engine = TelexEngine()
        self.telex_enabled = True
        self._busy = False
        self._faded = False
        self.dark_mode = False
        self.samples = load_samples()
        self.indicator = None
        self.undo = []          # stack (mark, old_word, new_word) cho ESC hoàn tác
        # Ctrl+Z / Ctrl+Shift+Z: ảnh chụp (text, vị trí con trỏ), gộp theo nhịp gõ
        self._snaps = [('', 0)]
        self._snap_i = 0
        self._snap_timer = None
        self._applying = False
        # Dán / xoá khối: chốt bước Ctrl+Z trước & sau, giữ bản nháp bị đè
        self._ua_depth = 0
        self._big = False           # thao tác hiện tại là dán/xoá khối
        self._big_removed = 0       # số ký tự bị xoá/đè trong thao tác
        self._big_inserted = 0
        self._pasting = False       # đang chờ nội dung clipboard dán vào
        self._paste_timer = None
        self._status_timer = None
        self._dnd_from = None       # bước Ctrl+Z lúc bắt đầu kéo-thả trong ô
        self._hist_last = None      # nội dung đã lưu lần cuối (tránh lưu lặp)
        # Lịch sử nội dung: 1 dòng / bản nháp, lưu sau khi ngừng gõ
        self.history_on = bool(self._saved.get('history', True))
        self._hist_id = None
        self._hist_timer = None
        try:
            self.history = HistoryStore(HISTORY_FILE)
        except Exception as e:
            print('history:', e)
            self.history = None
        self._click_timer = None
        self._click_pending = None  # idx chip chờ phân biệt click/đúp

        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.props.title = 'VietType'
        hb.props.subtitle = f'Bảng gõ Telex • v{APP_VERSION}'
        hb.set_decoration_layout('menu:close')
        self.set_titlebar(hb)

        # 3 nút icon gọn (designer: relief NONE, icon-only, tooltip đầy đủ)
        # 3 nút icon gọn: ghim (pin) + mờ (fog) + ẩn (eye)
        self.top_btn = Gtk.ToggleButton()
        self.top_btn.set_image(file_icon('pin.svg'))
        self.top_btn.set_always_show_image(True)
        self.top_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.top_btn.set_focus_on_click(False)
        self.top_btn.set_tooltip_text('Ghim luôn trên cùng (Always on top)')
        self.top_btn.connect('toggled', lambda b: self.set_keep_above(b.get_active()))
        hb.pack_end(self.top_btn)

        self.fade_btn = Gtk.ToggleButton()
        self.fade_btn.set_image(header_icon('weather-fog', asset_path('fog.svg')))
        self.fade_btn.set_always_show_image(True)
        self.fade_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.fade_btn.set_focus_on_click(False)
        self.fade_btn.set_tooltip_text('Mờ 70% — nhấn lại để rõ')
        self.fade_btn.connect('toggled', self.on_fade)
        hb.pack_end(self.fade_btn)

        self.hide_btn = Gtk.Button()
        self.hide_btn.set_image(file_icon('eye.svg'))
        self.hide_btn.set_always_show_image(True)
        self.hide_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.hide_btn.set_focus_on_click(False)
        self.hide_btn.set_tooltip_text('Ẩn xuống top bar (mở lại từ icon VIE)')
        self.hide_btn.connect('clicked', self.on_hide_clicked)
        hb.pack_end(self.hide_btn)

        self.theme_btn = Gtk.Button()
        self.theme_btn.set_image(file_icon('moon.svg'))
        self.theme_btn.set_always_show_image(True)
        self.theme_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.theme_btn.set_focus_on_click(False)
        self.theme_btn.set_tooltip_text('Chuyển chế độ tối/sáng (Dark/Light)')
        self.theme_btn.connect('clicked', self.on_theme_toggle)
        hb.pack_end(self.theme_btn)

        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        v.set_border_width(8)
        self.add(v)

        css = Gtk.CssProvider()
        css.load_from_data(b'''
        .chip { border-radius: 12px; padding: 1px 10px; font-size: 11px; }
        .chip-add { border-radius: 12px; padding: 1px 10px; font-weight: bold; opacity: 0.8; }
        .mini { padding: 1px 8px; min-height: 22px; font-size: 11px; }
        ''')
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # Ô nhập — nhỏ, mở rộng theo cửa sổ
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(80)
        sw.set_vexpand(True)
        self.tv = Gtk.TextView()
        self.tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv.set_tooltip_text('Gõ Telex • ESC: hoàn tác dấu vừa gõ • Ctrl+Z / Ctrl+Shift+Z: hoàn tác / làm lại\n'
                                 'Ctrl+H: lịch sử • Alt+kéo: di chuyển cửa sổ')
        self.tv.get_buffer().connect('insert-text', self.on_insert)
        self.tv.get_buffer().connect('delete-range', self.on_delete_range)
        self.tv.get_buffer().connect('begin-user-action', self.on_begin_action)
        self.tv.get_buffer().connect('end-user-action', self.on_end_action)
        self.tv.get_buffer().connect('changed', self.on_changed)
        self.tv.connect('key-press-event', self.on_key)
        self.tv.connect('paste-clipboard', self.on_paste_start)
        self.tv.connect('drag-begin', self.on_drag_begin)
        self.tv.connect('drag-end', self.on_drag_end)
        self.tv.connect('button-press-event', self._on_press_drag)
        sw.add(self.tv)
        v.pack_start(sw, True, True, 0)

        self.st = Gtk.Label()
        self.st.set_halign(Gtk.Align.START)
        self.st.set_markup('<small>Telex <b>BẬT</b> • 0</small>')
        self.drag_eb = Gtk.EventBox()
        self.drag_eb.set_tooltip_text('Kéo để di chuyển cửa sổ • Alt+kéo ở mọi nơi • ESC hoàn tác')
        self.drag_eb.add(self.st)
        self.drag_eb.connect('button-press-event', self._on_press_drag_zone)
        v.pack_start(self.drag_eb, False, False, 0)

        # Hàng điều khiển: Telex toggle gọn + Copy / Xoá (icon + chữ)
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.telex_sw = Gtk.ToggleButton(label='Telex')
        self.telex_sw.set_active(True)
        self.telex_sw.get_style_context().add_class('mini')
        self.telex_sw.set_focus_on_click(False)
        self.telex_sw.set_tooltip_text('Bật/Tắt gõ Telex (tắt = gõ không dấu)')
        self.telex_sw.connect('toggled', self.on_telex)
        r.pack_start(self.telex_sw, False, False, 0)
        for label, icon, tip, cb in [
            ('Copy', 'edit-copy', 'Sao chép nội dung ô nhập vào clipboard', self.on_copy),
            ('Xoá', 'edit-clear', 'Xoá trắng ô nhập', self.on_clear),
        ]:
            b = Gtk.Button(label=label)
            b.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
            b.set_always_show_image(True)
            b.set_tooltip_text(tip)
            b.connect('clicked', cb)
            b.connect('button-press-event', self._on_press_drag)
            r.pack_start(b, True, True, 0)
        hist_btn = Gtk.Button()
        hist_btn.set_image(Gtk.Image.new_from_icon_name('document-open-recent', Gtk.IconSize.BUTTON))
        hist_btn.set_always_show_image(True)
        hist_btn.set_tooltip_text('Lịch sử nội dung đã gõ (Ctrl+H)')
        hist_btn.connect('clicked', self.show_history)
        hist_btn.connect('button-press-event', self._on_press_drag)
        r.pack_start(hist_btn, False, False, 0)
        v.pack_start(r, False, False, 0)

        # Mẫu câu dạng chips: scroll ngang + drag-drop sắp xếp
        r2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        chip_sw = Gtk.ScrolledWindow()
        chip_sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        chip_sw.set_min_content_height(30)
        chip_sw.set_hexpand(True)
        self.chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.chip_box.set_border_width(1)
        chip_sw.add(self.chip_box)
        r2.pack_start(chip_sw, True, True, 0)
        add = Gtk.Button(label='+')
        add.get_style_context().add_class('chip-add')
        add.set_tooltip_text('Thêm mẫu mới (viết tắt + nội dung)')
        add.connect('clicked', self.on_add_dialog)
        add.connect('button-press-event', self._on_press_drag)
        r2.pack_start(add, False, False, 0)
        v.pack_start(r2, False, False, 0)

        # Tự chạy cùng Ubuntu
        self.auto_chk = Gtk.CheckButton(label='Tự chạy khi mở máy (autostart)')
        self.auto_chk.set_active(is_autostart())
        self.auto_chk.set_tooltip_text('Bật = tự mở VietType mỗi lần đăng nhập Ubuntu')
        self.auto_chk.connect('toggled', self.on_autostart)
        self.auto_chk.connect('button-press-event', self._on_press_drag)
        v.pack_start(self.auto_chk, False, False, 0)
        self.main_vbox = v

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect('button-press-event', self._on_window_press)

        self.refresh()
        self.setup_indicator()
        # Khôi phục trạng thái ghim (pin) + chế độ tối lần trước
        if self._saved.get('keep_above'):
            self.top_btn.set_active(True)
        if self._saved.get('dark'):
            self.dark_mode = True
            self.apply_theme()
        self.connect('delete-event', self.on_close)
        self.connect('destroy', lambda *_a: self.save_window())
        # Lưu size realtime (debounce) để luôn là "latest", kể cả crash/kill
        self._save_timer = None
        self.connect('configure-event', self.on_configure)

    def on_configure(self, *_a):
        if self._save_timer is not None:
            GLib.source_remove(self._save_timer)
        self._save_timer = GLib.timeout_add(600, self._delayed_save)
        return False

    def _delayed_save(self):
        self._save_timer = None
        self.save_window()
        return False

    def save_window(self):
        """Lưu kích thước + vị trí + trạng thái ghim + chế độ tối hiện tại."""
        try:
            w, h = self.get_size()
            x, y = self.get_position()
            save_window_state(w, h, x, y,
                              keep_above=self.top_btn.get_active(),
                              dark=self.dark_mode,
                              history=self.history_on)
        except Exception as e:
            print('state:', e)

    def apply_theme(self):
        try:
            Gtk.Settings.get_default().set_property(
                'gtk-application-prefer-dark-theme', self.dark_mode)
        except Exception as e:
            print('theme:', e)
        self.theme_btn.set_image(
            file_icon('sun.svg' if self.dark_mode else 'moon.svg'))
        self.theme_btn.set_always_show_image(True)

    def on_theme_toggle(self, _b=None):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        if self._theme_menu is not None and \
                self._theme_menu.get_active() != self.dark_mode:
            self._theme_menu.set_active(self.dark_mode)
        self.save_window()

    # --- Telex ---
    def word_before(self, buf, cur):
        s = cur.copy()
        while True:
            t = s.copy()
            if not t.backward_char():
                break
            if t.get_char() in WORD_DELIMS:
                break
            s = t
        return buf.get_text(s, cur, False), s

    def on_insert(self, buf, it, text, length):
        if not self._busy and not self._applying:
            if self._pasting or len(text) >= BIG_EDIT_CHARS:
                self._big_edit(inserted=len(text))
                if self._pasting:       # nội dung dán: không chạy Telex
                    return
            elif self._big:
                self._big_inserted += len(text)     # gõ đè vùng chọn
        if self._busy or not self.telex_enabled or len(text) != 1:
            return
        ch = text
        if ch not in 'aAeEoOuUwWdDsSfFrRxXjJzZ':
            return
        cur = buf.get_iter_at_mark(buf.get_insert())
        w, ws = self.word_before(buf, cur)
        ok, nw = self.engine.process(w, ch)
        if ok:
            self._busy = True
            try:
                mk = buf.create_mark(None, ws, True)
                buf.delete(ws, cur)
                buf.insert(ws, nw)
                self.undo.append((mk, w, nw))
                while len(self.undo) > 50:
                    old = self.undo.pop(0)
                    if not old[0].get_deleted():
                        buf.delete_mark(old[0])
            finally:
                self._busy = False
            GObject.signal_stop_emission_by_name(buf, 'insert-text')

    # --- Dán / xoá khối: luôn là 1 bước Ctrl+Z riêng, không gộp với phím gõ ---
    def on_begin_action(self, _buf):
        self._ua_depth += 1

    def on_end_action(self, _buf):
        self._ua_depth = max(0, self._ua_depth - 1)
        if self._ua_depth == 0:
            self._finish_big_edit()

    def on_delete_range(self, buf, start, end):
        if self._busy or self._applying:
            return
        n = abs(end.get_offset() - start.get_offset())
        # xoá vùng chọn (gõ/dán đè, cắt, Delete) hoặc xoá 1 khối lớn
        if n >= BIG_EDIT_CHARS or (n and buf.get_has_selection()) or self._pasting:
            self._big_edit(removed=n)

    # Dán là bất đồng bộ: GTK đợi clipboard rồi mới chèn -> đánh dấu trước
    def on_paste_start(self, _tv):
        self._pasting = True
        if self._paste_timer is not None:
            GLib.source_remove(self._paste_timer)
        self._paste_timer = GLib.timeout_add(1500, self._paste_expire)

    def _paste_expire(self):
        self._paste_timer = None
        self._pasting = False
        return False

    # Kéo-thả di chuyển chữ trong ô: GTK chèn rồi xoá ở 2 thao tác riêng
    # -> gộp lại thành 1 bước Ctrl+Z (không để lại bước chữ bị nhân đôi).
    def on_drag_begin(self, _w, _ctx):
        self.snap_commit()
        self._dnd_from = self._snap_i

    def on_drag_end(self, _w, _ctx):
        GLib.idle_add(self._dnd_collapse)

    def _dnd_collapse(self):
        start, self._dnd_from = self._dnd_from, None
        self.snap_commit()
        if (start is not None and self._snap_i == start + 2
                and len(self._snaps) == self._snap_i + 1):
            del self._snaps[start + 1]
            self._snap_i -= 1
        return False

    def _big_edit(self, removed=0, inserted=0):
        """Gọi TRƯỚC khi buffer đổi: chốt trạng thái cũ thành 1 bước hoàn tác."""
        if not self._big:
            self._big = True
            self.snap_commit()
            if self._ua_depth == 0:     # không nằm trong user-action -> chốt ở idle
                GLib.idle_add(lambda: self._finish_big_edit() or False)
        if removed:
            total = self.tv.get_buffer().get_char_count()
            # Sắp đè/xoá phần lớn nội dung: lưu bản hiện tại vào lịch sử rồi
            # tách mục mới -> bản cũ không bị ghi đè trong lịch sử.
            if removed >= OVERWRITE_MIN and removed * 2 >= total:
                self.new_history_entry()
        self._big_removed += removed
        self._big_inserted += inserted

    def _finish_big_edit(self):
        if not self._big:
            return
        removed, inserted = self._big_removed, self._big_inserted
        self._big = False
        self._big_removed = self._big_inserted = 0
        if self._pasting and inserted:     # đã dán xong
            if self._paste_timer is not None:
                GLib.source_remove(self._paste_timer)
            self._paste_expire()
        self.snap_commit()              # nội dung vừa dán = 1 bước riêng
        if removed >= OVERWRITE_MIN:
            what = 'dán đè' if inserted else 'xoá'
            self.st.set_markup(f'<small>Đã {what} {removed} ký tự — <b>Ctrl+Z</b> để lấy lại</small>')
            if self._status_timer is not None:
                GLib.source_remove(self._status_timer)
            self._status_timer = GLib.timeout_add(3500, self._status_reset)

    def _status_reset(self):
        self._status_timer = None
        self.update_status()
        return False

    @staticmethod
    def _is_overwrite(old, new):
        """new thay thế phần lớn old (>= OVERWRITE_MIN ký tự và >= nửa old)?"""
        n = min(len(old), len(new))
        p = 0
        while p < n and old[p] == new[p]:
            p += 1
        q = 0
        while q < n - p and old[-1 - q] == new[-1 - q]:
            q += 1
        removed = len(old) - p - q
        return removed >= OVERWRITE_MIN and removed * 2 >= len(old)

    # --- ESC hoàn tác dấu vừa gõ ---
    def on_key(self, _w, event):
        name = Gdk.keyval_name(event.keyval)
        if name == 'Escape':
            if self.try_undo():
                return True
        accel = Gdk.ModifierType.CONTROL_MASK
        if _mac is not None:
            accel |= Gdk.ModifierType.META_MASK     # Cmd trên macOS
        if event.state & accel:
            shift = event.state & Gdk.ModifierType.SHIFT_MASK
            if name in ('z', 'Z'):
                (self.snap_redo if shift else self.snap_undo)()
                return True
            if name in ('y', 'Y'):
                self.snap_redo()
                return True
            if name in ('h', 'H'):
                self.show_history()
                return True
        return False

    # --- Ctrl+Z / Ctrl+Shift+Z: ảnh chụp cả ô nhập, gộp các phím gõ liền nhau ---
    def _buf_state(self):
        buf = self.tv.get_buffer()
        return (buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False),
                buf.get_iter_at_mark(buf.get_insert()).get_offset())

    def _schedule_snap(self):
        if self._snap_timer is not None:
            GLib.source_remove(self._snap_timer)
        self._snap_timer = GLib.timeout_add(700, self.snap_commit)

    def snap_commit(self):
        """Chốt trạng thái hiện tại thành 1 bước hoàn tác (nếu có thay đổi)."""
        if self._snap_timer is not None:
            GLib.source_remove(self._snap_timer)
            self._snap_timer = None
        text, pos = self._buf_state()
        if text == self._snaps[self._snap_i][0]:
            self._snaps[self._snap_i] = (text, pos)     # chỉ di chuyển con trỏ
            return False
        del self._snaps[self._snap_i + 1:]      # gõ mới thì bỏ nhánh redo
        self._snaps.append((text, pos))
        total = sum(len(t) for t, _p in self._snaps)
        while len(self._snaps) > 2 and (len(self._snaps) > SNAP_MAX or total > SNAP_MAX_CHARS):
            total -= len(self._snaps.pop(0)[0])
        self._snap_i = len(self._snaps) - 1
        return False

    def _snap_apply(self):
        text, pos = self._snaps[self._snap_i]
        buf = self.tv.get_buffer()
        if self._is_overwrite(self._buf_state()[0], text):
            # hoàn tác/làm lại một lần dán đè: giữ cả 2 bản trong lịch sử
            self.new_history_entry()
        self._applying = self._busy = True
        try:
            buf.set_text(text)
            buf.place_cursor(buf.get_iter_at_offset(min(pos, len(text))))
        finally:
            self._applying = self._busy = False
        # vị trí dấu ESC cũ không còn đúng sau khi thay cả nội dung
        for mk, _o, _n in self.undo:
            if not mk.get_deleted():
                buf.delete_mark(mk)
        self.undo.clear()
        self.tv.scroll_mark_onscreen(buf.get_insert())
        self._schedule_history()

    def snap_undo(self):
        self.snap_commit()
        if self._snap_i > 0:
            self._snap_i -= 1
            self._snap_apply()

    def snap_redo(self):
        self.snap_commit()
        if self._snap_i < len(self._snaps) - 1:
            self._snap_i += 1
            self._snap_apply()

    def try_undo(self):
        buf = self.tv.get_buffer()
        if buf.get_has_selection():
            return False
        while self.undo:
            mk, old, new = self.undo[-1]
            if mk.get_deleted():
                self.undo.pop()
                continue
            it = buf.get_iter_at_mark(mk)
            end = it.copy()
            end.forward_chars(len(new))
            if end.get_offset() - it.get_offset() != len(new):
                self.undo.pop()
                buf.delete_mark(mk)
                continue
            if buf.get_text(it, end, False) != new:
                self.undo.pop()
                buf.delete_mark(mk)
                continue
            if not buf.get_iter_at_mark(buf.get_insert()).equal(end):
                self.undo.pop()
                buf.delete_mark(mk)
                continue
            self._busy = True
            try:
                buf.delete(it, end)
                buf.insert(it, old)
            finally:
                self._busy = False
            buf.delete_mark(mk)
            self.undo.pop()
            self.tv.grab_focus()
            return True
        return False

    # --- kéo cửa sổ: Alt+kéo ở mọi nơi, hoặc kéo từ nền/thanh trạng thái ---
    def _begin_move(self, event):
        try:
            self.begin_move_drag(int(event.button),
                                 int(event.x_root), int(event.y_root),
                                 event.time)
            return True
        except Exception:
            return False

    def _on_press_drag(self, _w, event):
        if getattr(event, 'button', 0) == 1 and (event.state & Gdk.ModifierType.MOD1_MASK):
            return self._begin_move(event)
        return False

    def _on_press_drag_zone(self, _w, event):
        if getattr(event, 'button', 0) == 1:
            return self._begin_move(event)
        return False

    def _on_window_press(self, _w, event):
        # Chỉ Alt+kéo ở cấp cửa sổ. Click thường KHÔNG chạm tới ở đây để
        # nhường cho GTK xử lý: resize viền, kéo titlebar, focus/gõ TextView.
        # (Kéo nền dùng thanh trạng thái EventBox riêng.)
        if getattr(event, 'button', 0) != 1:
            return False
        if event.state & Gdk.ModifierType.MOD1_MASK:
            return self._begin_move(event)
        return False

    def update_status(self):
        m = 'BẬT' if self.telex_enabled else 'TẮT'
        n = self.tv.get_buffer().get_char_count()
        self.st.set_markup(f'<small>Telex <b>{m}</b> • {n}</small>')

    def on_changed(self, _buf):
        self.update_status()
        if not self._applying:
            self._schedule_snap()
            self._schedule_history()

    # --- lịch sử: lưu bản nháp sau 2.5s ngừng gõ, cập nhật tại chỗ ---
    def _schedule_history(self):
        if self.history is None or not self.history_on:
            return
        if self._hist_timer is not None:
            GLib.source_remove(self._hist_timer)
        self._hist_timer = GLib.timeout_add(2500, self.flush_history)

    def flush_history(self):
        if self._hist_timer is not None:
            GLib.source_remove(self._hist_timer)
            self._hist_timer = None
        if self.history is None or not self.history_on:
            return False
        text = self._buf_state()[0]
        try:
            if text.strip():
                if text != self._hist_last:
                    self._hist_id = self.history.save(text, self._hist_id)
                    self._hist_last = text
            else:
                self._hist_id = None    # ô trống -> lần gõ sau là mục mới
        except Exception as e:
            print('history:', e)
        return False

    def new_history_entry(self):
        """Chốt bản nháp hiện tại; nội dung tiếp theo thành mục riêng."""
        self.flush_history()
        self._hist_id = None

    def on_telex(self, sw, _p=None):
        self.telex_enabled = sw.get_active()
        self.update_status()
        if self.indicator and hasattr(self.indicator, 'set_label'):
            try:
                self.indicator.set_label('VIE' if self.telex_enabled else 'EN', '')
            except Exception:
                pass

    # --- nút ---
    def on_copy(self, _b):
        buf = self.tv.get_buffer()
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(
            buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False), -1)
        self.st.set_markup('<small>Đã copy ✓</small>')
        GLib.timeout_add(1200, lambda: self.update_status() or False)
        self.flush_history()

    def on_clear(self, _b):
        self.snap_commit()
        self.new_history_entry()
        self.tv.get_buffer().set_text('')
        self.snap_commit()      # Xoá cũng hoàn tác được bằng Ctrl+Z
        self.tv.grab_focus()

    def on_fade(self, btn):
        self._faded = btn.get_active()
        try:
            self.set_opacity(0.7 if self._faded else 1.0)
        except Exception:
            pass

    def on_hide_clicked(self, _b):
        self.save_window()
        if self.indicator is not None:
            self.hide()
        else:
            self.iconify()

    def on_autostart(self, chk):
        ok = set_autostart(chk.get_active())
        if not ok:
            chk.set_active(not chk.get_active())

    # --- mẫu chips: {abbr, content}; click = copy, đúp = chèn ---
    def refresh(self):
        for c in self.chip_box.get_children():
            self.chip_box.remove(c)
        for idx, t in enumerate(self.samples):
            chip = Gtk.Button(label=t['abbr'][:12])
            chip.get_style_context().add_class('chip')
            chip.set_tooltip_text(
                f"{t['abbr']}: {t['content']}\n— Click: copy • Đúp: chèn • "
                "Chuột phải: sửa/xoá/dời • Kéo-thả: sắp xếp")
            chip.connect('clicked', self.on_chip_clicked, idx)
            chip.connect('button-press-event', self.on_chip_press, idx)
            chip.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, CHIP_TARGETS, Gdk.DragAction.MOVE)
            chip.drag_dest_set(Gtk.DestDefaults.ALL, CHIP_TARGETS, Gdk.DragAction.MOVE)
            chip.connect('drag-data-get', self.on_chip_drag_get, idx)
            chip.connect('drag-data-received', self.on_chip_drag_received, idx)
            self.chip_box.pack_start(chip, False, False, 0)
        self.chip_box.show_all()

    def _copy_text(self, text, msg):
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
        self.st.set_markup(f'<small>{msg}</small>')
        GLib.timeout_add(1200, lambda: self.update_status() or False)

    def on_chip_clicked(self, _btn, idx):
        # Phân biệt click (copy) / đúp (chèn): click đợi 260ms xem có press-2 không
        if not (0 <= idx < len(self.samples)):
            return
        if self._click_pending == idx and self._click_timer is not None:
            GLib.source_remove(self._click_timer)
            self._click_timer = None
            self._click_pending = None
            self.insert_template(idx)
            return
        if self._click_timer is not None:
            GLib.source_remove(self._click_timer)
            self._flush_pending_copy()
        self._click_pending = idx
        self._click_timer = GLib.timeout_add(260, self._pending_copy_timeout)

    def _flush_pending_copy(self):
        self._click_timer = None
        if self._click_pending is not None:
            idx, self._click_pending = self._click_pending, None
            self.copy_template(idx)

    def _pending_copy_timeout(self):
        self._click_timer = None
        if self._click_pending is not None:
            idx, self._click_pending = self._click_pending, None
            self.copy_template(idx)
        return False

    def copy_template(self, idx):
        if 0 <= idx < len(self.samples):
            t = self.samples[idx]
            self._copy_text(t['content'], f"Đã copy '{t['abbr']}' ✓")

    def insert_template(self, idx):
        if 0 <= idx < len(self.samples):
            self.insert_text(self.samples[idx]['content'])

    def insert_text(self, text):
        """Chèn tại con trỏ thành 1 bước Ctrl+Z riêng."""
        self.snap_commit()
        self.tv.get_buffer().insert_at_cursor(text)
        self.snap_commit()
        self.tv.grab_focus()

    def on_chip_press(self, _btn, event, idx):
        if event.button == 3:
            self.open_chip_menu(event, idx)
            return True
        if event.button == 1 and (event.state & Gdk.ModifierType.MOD1_MASK):
            return self._begin_move(event)
        return False

    def open_chip_menu(self, event, idx):
        menu = Gtk.Menu()
        for label, fn in [
            ('Chèn vào ô nhập', lambda *a: self.insert_template(idx)),
            ('Copy', lambda *a: self.copy_template(idx)),
            ('Sửa viết tắt/nội dung', lambda *a: self.on_edit_dialog(idx)),
            ('◀ Dời trái', lambda *a: self.move_chip(idx, -1)),
            ('Dời phải ▶', lambda *a: self.move_chip(idx, 1)),
            ('Xoá chip', lambda *a: self.del_chip(idx)),
        ]:
            mi = Gtk.MenuItem(label=label)
            mi.connect('activate', fn)
            menu.append(mi)
        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    def move_chip(self, idx, delta):
        j = idx + delta
        if 0 <= idx < len(self.samples) and 0 <= j < len(self.samples):
            self.samples[idx], self.samples[j] = self.samples[j], self.samples[idx]
            save_samples(self.samples)
            self.refresh()

    def del_chip(self, idx):
        if 0 <= idx < len(self.samples):
            self.samples.pop(idx)
            save_samples(self.samples)
            self.refresh()

    def on_chip_drag_get(self, _w, _ctx, sel, _info, _t, src_idx):
        sel.set_text(str(src_idx), -1)

    def on_chip_drag_received(self, _w, _ctx, _x, _y, sel, _info, _t, dst_idx):
        try:
            src = int(sel.get_text())
        except (TypeError, ValueError):
            return
        if src == dst_idx or not (0 <= src < len(self.samples)):
            return
        item = self.samples.pop(src)
        dst_idx = max(0, min(dst_idx, len(self.samples)))
        self.samples.insert(dst_idx, item)
        save_samples(self.samples)
        self.refresh()

    def suggest_abbr(self, content, ignore=-1):
        words = content.strip().split()
        cand = ''.join(w[0] for w in words[:4]).lower() or content.strip()[:3].lower()
        cand = ''.join(c for c in cand if c.isalnum())[:8] or 'mau'
        taken = {t['abbr'] for i, t in enumerate(self.samples) if i != ignore}
        if cand not in taken:
            return cand
        i = 2
        while f'{cand}{i}' in taken:
            i += 1
        return f'{cand}{i}'

    def prefill_text(self):
        buf = self.tv.get_buffer()
        try:
            a, z = buf.get_selection_bounds()
            t = buf.get_text(a, z, False).strip()
            if t:
                return t
        except ValueError:
            pass
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()[:500]

    def template_dialog(self, title, abbr_init='', content_init=''):
        dlg = Gtk.Dialog(title=title, parent=self, flags=Gtk.DialogFlags.MODAL)
        dlg.add_buttons('Huỷ', Gtk.ResponseType.CANCEL, 'Lưu', Gtk.ResponseType.OK)
        dlg.set_default_size(300, 140)
        e_abbr = Gtk.Entry()
        e_abbr.set_text(abbr_init)
        e_abbr.set_placeholder_text('Viết tắt (vd: cty, xn, mail…)')
        e_abbr.set_max_length(12)
        e_content = Gtk.Entry()
        e_content.set_text(content_init)
        e_content.set_placeholder_text('Nội dung đầy đủ')
        e_content.set_activates_default(True)
        box = dlg.get_content_area()
        box.set_border_width(8)
        box.set_spacing(6)
        box.pack_start(Gtk.Label(label='Viết tắt (hiện trên chip):'), False, False, 0)
        box.pack_start(e_abbr, False, False, 0)
        box.pack_start(Gtk.Label(label='Nội dung (copy/chèn):'), False, False, 0)
        box.pack_start(e_content, False, False, 0)
        dlg.show_all()
        ok = dlg.run() == Gtk.ResponseType.OK
        ab, co = e_abbr.get_text().strip(), e_content.get_text().strip()
        dlg.destroy()
        return (ok, ab, co)

    def on_add_dialog(self, _b):
        content = self.prefill_text()
        ok, ab, co = self.template_dialog('Thêm mẫu', self.suggest_abbr(content), content)
        if ok and co:
            ab = ab or self.suggest_abbr(co)
            taken = {t['abbr'] for t in self.samples}
            if ab in taken:
                ab = self.suggest_abbr(co)
            self.samples.append({'abbr': ab, 'content': co})
            save_samples(self.samples)
            self.refresh()

    def on_edit_dialog(self, idx):
        if not (0 <= idx < len(self.samples)):
            return
        t = self.samples[idx]
        ok, ab, co = self.template_dialog('Sửa mẫu', t['abbr'], t['content'])
        if ok and co:
            ab = ab or self.suggest_abbr(co, ignore=idx)
            taken = {x['abbr'] for i, x in enumerate(self.samples) if i != idx}
            if ab in taken:
                ab = self.suggest_abbr(co, ignore=idx)
            self.samples[idx] = {'abbr': ab, 'content': co}
            save_samples(self.samples)
            self.refresh()

    # --- top bar ---
    def setup_indicator(self):
        try:
            gi.require_version('AyatanaAppIndicator3', '0.1')
            from gi.repository import AyatanaAppIndicator3 as A
        except Exception:
            try:
                gi.require_version('AppIndicator3', '0.1')
                from gi.repository import AppIndicator3 as A
            except Exception:
                return
        try:
            self.indicator = A.Indicator.new(APP_ID, 'accessories-text-editor',
                                             A.IndicatorCategory.APPLICATION_STATUS)
            self.indicator.set_status(A.IndicatorStatus.ACTIVE)
            self.indicator.set_label('VIE', '')
            m = Gtk.Menu()
            mi = Gtk.MenuItem(label='Hiện / Ẩn')
            mi.connect('activate', lambda *a: self.hide() if self.is_visible() else self.present())
            m.append(mi)
            mt = Gtk.CheckMenuItem(label='Telex')
            mt.set_active(True)
            mt.connect('toggled', lambda x: self.telex_sw.set_active(x.get_active()))
            m.append(mt)
            mf = Gtk.CheckMenuItem(label='Mờ (trong suốt)')
            mf.connect('toggled', lambda x: self.fade_btn.set_active(x.get_active()))
            m.append(mf)
            ma = Gtk.CheckMenuItem(label='Tự chạy khi mở máy')
            ma.set_active(is_autostart())
            ma.connect('toggled', lambda x: (set_autostart(x.get_active()),
                                             self.auto_chk.set_active(x.get_active())))
            m.append(ma)
            md = Gtk.CheckMenuItem(label='Chế độ tối')
            md.set_active(self.dark_mode)
            md.connect('toggled', lambda x: (self.on_theme_toggle()
                                             if x.get_active() != self.dark_mode else None))
            m.append(md)
            self._theme_menu = md
            mh = Gtk.MenuItem(label='Lịch sử…')
            mh.connect('activate', lambda *a: (self.present(), self.show_history()))
            m.append(mh)
            mi_about = Gtk.MenuItem(label=f'Giới thiệu VietType v{APP_VERSION}')
            mi_about.connect('activate', self.show_about)
            m.append(mi_about)
            mq = Gtk.MenuItem(label='Thoát')
            mq.connect('activate', lambda *a: Gtk.main_quit())
            m.append(mq)
            m.show_all()
            self.indicator.set_menu(m)
        except Exception:
            self.indicator = None

    def on_close(self, *a):
        self.save_window()
        self.flush_history()
        if self.indicator is not None:
            self.hide()
            return True
        return False

    def show_about(self, *_a):
        dlg = Gtk.AboutDialog(transient_for=self, modal=True)
        dlg.set_program_name('VietType')
        dlg.set_version(APP_VERSION)
        dlg.set_comments('Khung gõ Telex nhỏ cho Ubuntu: ô nhập live,\nchips mẫu câu, always-on-top, top-bar indicator.')
        dlg.set_website('https://github.com/')
        ip = icon_path()
        if ip:
            try:
                dlg.set_logo(GdkPixbuf.Pixbuf.new_from_file_at_size(ip, 64, 64))
            except Exception:
                pass
        dlg.run()
        dlg.destroy()

    # --- cửa sổ lịch sử: tìm không dấu, chèn / copy / xoá ---
    def show_history(self, *_a):
        if self.history is None:
            self.st.set_markup('<small>Không mở được lịch sử</small>')
            return
        if getattr(self, '_hist_dlg', None) is not None:
            self._hist_dlg.present()
            return
        self.flush_history()
        dlg = Gtk.Dialog(title='Lịch sử VietType', transient_for=self)
        dlg.set_default_size(380, 440)
        self._hist_dlg = dlg
        box = dlg.get_content_area()
        box.set_border_width(8)
        box.set_spacing(6)

        search = Gtk.SearchEntry()
        search.set_placeholder_text('Tìm (gõ không dấu cũng được)…')
        box.pack_start(search, False, False, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        lb = Gtk.ListBox()
        lb.set_selection_mode(Gtk.SelectionMode.SINGLE)
        lb.set_placeholder(Gtk.Label(label='Chưa có gì'))
        sw.add(lb)
        box.pack_start(sw, True, True, 0)

        info = Gtk.Label()
        info.set_halign(Gtk.Align.START)
        rec = Gtk.CheckButton(label='Lưu lịch sử')
        rec.set_active(self.history_on)
        rec.set_tooltip_text(f'Lưu tại {HISTORY_FILE}\nTắt = không ghi gì thêm (mục cũ vẫn giữ)')
        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        foot.pack_start(rec, False, False, 0)
        foot.pack_end(info, False, False, 0)

        def fmt_time(ts):
            t, now = time.localtime(ts), time.localtime()
            if t[:3] == now[:3]:
                return time.strftime('%H:%M', t)
            if t.tm_year == now.tm_year:
                return time.strftime('%d/%m %H:%M', t)
            return time.strftime('%d/%m/%Y', t)

        def reload(*_x):
            for c in lb.get_children():
                lb.remove(c)
            for eid, text, updated, uses in self.history.search(search.get_text()):
                row = Gtk.ListBoxRow()
                row.eid, row.text = eid, text
                vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
                vb.set_border_width(4)
                body = Gtk.Label(label=' '.join(text.split()))
                body.set_halign(Gtk.Align.START)
                body.set_xalign(0)
                body.set_line_wrap(True)
                body.set_lines(2)
                body.set_ellipsize(Pango.EllipsizeMode.END)
                body.set_tooltip_text(text[:2000])
                meta = Gtk.Label()
                meta.set_halign(Gtk.Align.START)
                extra = f' • dùng {uses} lần' if uses > 1 else ''
                meta.set_markup(f'<small><span alpha="60%">{fmt_time(updated)} • '
                                f'{len(text)} ký tự{extra}</span></small>')
                vb.pack_start(body, False, False, 0)
                vb.pack_start(meta, False, False, 0)
                row.add(vb)
                lb.add(row)
            lb.show_all()
            n, size = self.history.stats()
            info.set_markup(f'<small>{n} mục • {size / 1024:.0f} KB</small>')

        def selected():
            return lb.get_selected_row()

        def do_insert(*_x):
            row = selected()
            if row is not None:
                self.history.touch(row.eid)
                self.new_history_entry()
                was_empty = not self._buf_state()[0].strip()
                self.insert_text(row.text)
                if was_empty:
                    self._hist_id = row.eid     # sửa tiếp thì cập nhật đúng mục này
                dlg.destroy()

        def do_copy(*_x):
            row = selected()
            if row is not None:
                self.history.touch(row.eid)
                Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(row.text, -1)
                info.set_markup('<small>Đã copy ✓</small>')
                GLib.timeout_add(1200, lambda: reload() or False)

        def do_delete(*_x):
            row = selected()
            if row is not None:
                idx = row.get_index()
                if row.eid == self._hist_id:
                    self._hist_id = None
                self._hist_last = None
                self.history.delete(row.eid)
                reload()
                nxt = lb.get_row_at_index(min(idx, len(lb.get_children()) - 1))
                if nxt is not None:
                    lb.select_row(nxt)

        def do_clear_all(*_x):
            q = Gtk.MessageDialog(transient_for=dlg, modal=True,
                                  message_type=Gtk.MessageType.QUESTION,
                                  buttons=Gtk.ButtonsType.YES_NO,
                                  text='Xoá toàn bộ lịch sử?')
            q.format_secondary_text('Không thể khôi phục.')
            ok = q.run() == Gtk.ResponseType.YES
            q.destroy()
            if ok:
                self.history.clear()
                self._hist_id = None
                self._hist_last = None
                reload()

        def on_rec(chk):
            self.history_on = chk.get_active()
            if not self.history_on and self._hist_timer is not None:
                GLib.source_remove(self._hist_timer)
                self._hist_timer = None
            self.save_window()

        def on_list_key(_w, ev):
            if Gdk.keyval_name(ev.keyval) == 'Delete':
                do_delete()
                return True
            return False

        acts = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, icon, tip, cb in [
            ('Chèn', 'insert-text', 'Chèn vào ô nhập (hoặc đúp / Enter)', do_insert),
            ('Copy', 'edit-copy', 'Sao chép vào clipboard', do_copy),
            ('Xoá', 'edit-delete', 'Xoá mục này (phím Delete)', do_delete),
        ]:
            b = Gtk.Button(label=label)
            b.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
            b.set_always_show_image(True)
            b.set_tooltip_text(tip)
            b.connect('clicked', cb)
            acts.pack_start(b, True, True, 0)
        clr = Gtk.Button(label='Xoá hết')
        clr.set_tooltip_text('Xoá toàn bộ lịch sử')
        clr.connect('clicked', do_clear_all)
        acts.pack_end(clr, False, False, 0)
        box.pack_start(acts, False, False, 0)
        box.pack_start(foot, False, False, 0)

        search.connect('search-changed', reload)
        search.connect('activate', lambda *_x: (lb.select_row(lb.get_row_at_index(0)),
                                                do_insert()))
        lb.connect('row-activated', do_insert)
        lb.connect('key-press-event', on_list_key)
        rec.connect('toggled', on_rec)

        def on_destroy(*_x):
            self._hist_dlg = None
        dlg.connect('destroy', on_destroy)
        dlg.connect('response', lambda d, _r: d.destroy())
        reload()
        if lb.get_row_at_index(0) is not None:
            lb.select_row(lb.get_row_at_index(0))
        dlg.show_all()
        search.grab_focus()


def main():
    if '--version' in sys.argv or '-V' in sys.argv:
        print(f'VietType {APP_VERSION}')
        return
    GLib.set_prgname('viettype')
    ip = icon_path()
    if ip:
        try:
            Gtk.Window.set_default_icon_from_file(ip)
        except Exception as e:
            print('default icon:', e)
    w = VietTypeWindow()
    w.connect('destroy', Gtk.main_quit)
    w.show_all()
    Gtk.main()
    # Thoát từ top bar không qua delete-event: chốt bản nháp cuối
    try:
        w.flush_history()
    except Exception:
        pass
    if w.history is not None:
        w.history.close()


if __name__ == '__main__':
    main()
