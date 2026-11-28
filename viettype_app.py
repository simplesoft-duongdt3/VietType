#!/usr/bin/env /usr/bin/python3
"""VietType: TextArea gõ Telex + chips mẫu câu (viết tắt + nội dung).
- Click chip: copy nội dung • Đúp chip: chèn vào ô nhập • Phải: sửa/xoá/dời
- Kéo-thả chip để sắp xếp • ESC: hoàn tác dấu vừa gõ
- Alt+kéo (mọi nơi) hoặc kéo từ nền/thanh trạng thái để di chuyển cửa sổ."""
import fcntl, json, os, signal, sys, time

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
APP_VERSION = '3.6.9'
CONFIG_DIR = os.path.expanduser('~/.config/viettype')
SAMPLES_FILE = os.path.join(CONFIG_DIR, 'samples.json')
AUTOSTART_FILE = os.path.expanduser('~/.config/autostart/viettype.desktop')
STATE_FILE = os.path.join(CONFIG_DIR, 'state.json')
INSTANCE_LOCK_FILE = os.path.join(CONFIG_DIR, 'instance.lock')
HISTORY_FILE = os.path.join(os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share'),
                            'viettype', 'history.db')
SNAP_MAX = 200              # số bước Ctrl+Z tối đa
SNAP_MAX_CHARS = 2_000_000  # giới hạn bộ nhớ cho các bước Ctrl+Z
BIG_EDIT_CHARS = 8          # chèn/xoá >= N ký tự 1 lần = 1 bước Ctrl+Z riêng
                            # (dán, cắt, xoá/gõ đè vùng chọn luôn là bước riêng)
OVERWRITE_MIN = 20          # xoá/đè >= N ký tự và >= nửa nội dung -> giữ bản cũ thành mục lịch sử riêng
CHIP_ROWS = 2               # số dòng chip hiện cùng lúc (nhiều hơn thì cuộn dọc)
CHIP_ROW_SPACING = 4        # khoảng cách giữa các dòng chip (px)
VIEW_WINDOW, VIEW_BUBBLE, VIEW_HIDDEN = 'window', 'bubble', 'hidden'   # 3 chế độ hiện
VIEW_MODES = (VIEW_WINDOW, VIEW_BUBBLE, VIEW_HIDDEN)
LABEL_TELEX_ON = 'VCD'      # chữ trên menu bar / top bar / nút nổi khi bật Telex
LABEL_TELEX_OFF = 'EN'      # ... khi tắt Telex
BUBBLE_SIZE = 44            # cỡ nút nổi (px)
BUBBLE_DRAG_PX = 4          # nhấn rồi di chuột >= N px = kéo nút, không phải click
BUBBLE_OPACITY = 0.55       # độ đục nút nổi lúc thường (nhìn xuyên thấy bên dưới)
BUBBLE_OPACITY_HOVER = 1.0  # khi rê chuột vào nút


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


def _stable_python():
    """python3 không kèm số phiên bản nếu nó cùng là trình thông dịch đang chạy
    (vd. /opt/homebrew/bin/python3 thay vì .../python@3.15/bin/python3.15)."""
    try:
        cur = os.path.realpath(sys.executable)
        for p in ('/opt/homebrew/bin/python3', '/usr/local/bin/python3', '/usr/bin/python3'):
            if os.access(p, os.X_OK) and os.path.realpath(p) == cur:
                return p
    except Exception:
        pass
    return sys.executable


def mac_autostart_argv():
    script = os.path.abspath(__file__)
    res_dir = os.path.dirname(script)
    bundle_exe = os.path.join(os.path.dirname(res_dir), 'MacOS', 'VietType')
    if getattr(sys, 'frozen', False):
        return [sys.executable]
    if res_dir.endswith('.app/Contents/Resources') and os.access(bundle_exe, os.X_OK):
        # Chạy từ VietType.app: dùng launcher native của bundle, không ghim
        # đường dẫn python3.x (sẽ hỏng khi Homebrew nâng cấp Python).
        return [bundle_exe]
    return [_stable_python(), script]


def migrate_autostart_mac():
    """LaunchAgent do bản cũ ghi có thể trỏ tới python3.x đã bị Homebrew gỡ.
    Ghi lại khi lệnh hỏng, hoặc khi nó chạy chính bản này theo cách cũ.
    Không đụng LaunchAgent trỏ tới bản cài khác còn chạy được."""
    if _mac is None or not _mac.is_autostart_mac():
        return
    # Chạy từ VietType.app: chuyển LaunchAgent cũ sang Login Items của macOS
    if _mac.login_item_status() is not None:
        if os.path.exists(_mac.autostart_path()):
            _mac.set_autostart_mac(True, mac_autostart_argv())
        return
    cur = _mac.autostart_argv_mac()
    want = mac_autostart_argv()
    if cur == want:
        return
    broken = not cur or not os.access(cur[0], os.X_OK)
    if broken or os.path.abspath(__file__) in cur:
        _mac.set_autostart_mac(True, want)


def set_autostart(on):
    if _mac is not None:
        return _mac.set_autostart_mac(bool(on), mac_autostart_argv())
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


def ensure_private_dir(path):
    """Thư mục cấu hình chỉ chủ máy đọc được (mẫu câu có thể chứa thông tin riêng)."""
    os.makedirs(path, mode=0o700, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def write_private(path, text):
    """Ghi file quyền 0600, ghi ra file tạm rồi đổi tên để không hỏng file khi máy tắt ngang."""
    ensure_private_dir(os.path.dirname(path))
    tmp = path + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def save_samples(s):
    try:
        write_private(SAMPLES_FILE, json.dumps(s, ensure_ascii=False, indent=2))
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


def save_window_state(w, h, x, y, keep_above=False, dark=False, history=True,
                      view_mode=None, bubble_pos=None):
    try:
        d = {'width': w, 'height': h, 'x': x, 'y': y,
             'keep_above': bool(keep_above), 'dark': bool(dark),
             'history': bool(history)}
        if view_mode in VIEW_MODES:
            d['view_mode'] = view_mode
        if bubble_pos is not None:
            d['bubble_x'], d['bubble_y'] = int(bubble_pos[0]), int(bubble_pos[1])
        write_private(STATE_FILE, json.dumps(d))
    except Exception as e:
        print('state:', e)


def badge_pixbuf(text, px, round_shape=False, opacity=1.0):
    """Icon xanh chữ trắng (VCD/EN) như viettype.svg, vẽ ở px điểm ảnh.
    round_shape=True: hình tròn có viền trắng (nút nổi). opacity: độ đục cả hình."""
    fs = 24 if len(text) <= 2 else 20
    if round_shape:
        shape = ('<circle cx="32" cy="32" r="29" fill="#2e7cf6" stroke="white" '
                 'stroke-width="3" stroke-opacity="0.9"/>')
        ty, bar = 39, ''
    else:
        shape = '<rect x="2" y="2" width="60" height="60" rx="12" fill="#2e7cf6"/>'
        ty = 40
        bar = '<rect x="14" y="46" width="36" height="3" rx="1.5" fill="white" opacity="0.85"/>'
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
           f'<g opacity="{opacity:.2f}">{shape}<text x="32" y="{ty}" '
           'font-family="Helvetica, Arial, sans-serif" '
           f'font-size="{fs}" font-weight="bold" fill="white" text-anchor="middle">{text}</text>'
           f'{bar}</g></svg>').encode()
    loader = GdkPixbuf.PixbufLoader.new_with_type('svg')
    loader.set_size(px, px)
    loader.write(svg)
    loader.close()
    return loader.get_pixbuf()


class FloatingButton(Gtk.Window):
    """Nút nổi nhỏ luôn trên cùng: click = mở cửa sổ, kéo = di chuyển,
    chuột phải = menu (giống icon menu bar / top bar)."""

    def __init__(self, owner):
        super().__init__(title='VietType')
        self.owner = owner
        self._press = None          # (x_root, y_root) khi nhấn chuột trái, chưa kéo
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_size_request(BUBBLE_SIZE, BUBBLE_SIZE)
        self.set_default_size(BUBBLE_SIZE, BUBBLE_SIZE)
        try:
            self.set_wmclass('VietType', 'VietType')
        except Exception:
            pass
        screen = self.get_screen()
        vis = screen.get_rgba_visual()
        # Nền trong suốt -> nút tròn. macOS bỏ qua set_opacity với cửa sổ RGBA nên khi đó
        # độ trong suốt được vẽ thẳng vào ảnh; không có RGBA thì dùng set_opacity.
        self._rgba = vis is not None and screen.is_composited()
        if self._rgba:
            self.set_visual(vis)
            self.set_app_paintable(True)
        self._text = LABEL_TELEX_ON
        self._hover = False
        self.get_style_context().add_class('vt-bubble')
        self.img = Gtk.Image()
        box = Gtk.EventBox()
        box.set_visible_window(False)
        box.add(self.img)
        box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                       | Gdk.EventMask.BUTTON1_MOTION_MASK
                       | Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        box.connect('button-press-event', self._on_press)
        box.connect('button-release-event', self._on_release)
        box.connect('motion-notify-event', self._on_motion)
        # Trong suốt lúc thường để thấy nội dung bên dưới, rõ hẳn khi rê chuột vào
        box.connect('enter-notify-event', self._on_enter)
        box.connect('leave-notify-event', self._on_leave)
        self.add(box)
        self.set_tooltip_text('VietType — click: mở • kéo: di chuyển • chuột phải: menu')
        # macOS bỏ qua keep_above gọi trước khi hiện -> đặt lại mỗi lần map (cả độ trong suốt)
        self.connect('map-event', lambda *a: GLib.idle_add(
            lambda: (self.set_keep_above(True), self._render(), False)[-1]))
        self.connect('configure-event', self._on_configure)
        self.set_keep_above(True)
        self.set_text(LABEL_TELEX_ON)
        box.show_all()

    def set_text(self, text):
        self._text = text
        self._render()

    def _render(self):
        alpha = BUBBLE_OPACITY_HOVER if self._hover else BUBBLE_OPACITY
        if not self._rgba:
            self.set_opacity(alpha)
            alpha = 1.0
        scale = max(1, self.get_scale_factor())
        pb = badge_pixbuf(self._text, BUBBLE_SIZE * scale, round_shape=True, opacity=alpha)
        if scale > 1:
            try:                                  # nét trên màn Retina
                self.img.set_from_surface(Gdk.cairo_surface_create_from_pixbuf(pb, scale, None))
                return
            except Exception:
                pb = pb.scale_simple(BUBBLE_SIZE, BUBBLE_SIZE, GdkPixbuf.InterpType.BILINEAR)
        self.img.set_from_pixbuf(pb)

    def show_at(self, pos):
        x, y = self._valid_pos(pos)
        self.move(x, y)
        self.show()
        self.present()

    def _valid_pos(self, pos):
        """Vị trí đã lưu nếu còn nằm trong một màn hình, không thì mép phải màn hình chính."""
        disp = Gdk.Display.get_default()
        if pos is not None:
            x, y = pos
            for i in range(disp.get_n_monitors()):
                g = disp.get_monitor(i).get_geometry()
                if g.x <= x + BUBBLE_SIZE // 2 < g.x + g.width and \
                        g.y <= y + BUBBLE_SIZE // 2 < g.y + g.height:
                    return int(x), int(y)
        mon = disp.get_primary_monitor() or (disp.get_monitor(0) if disp.get_n_monitors() else None)
        if mon is None:                      # màn hình đang ngủ/chưa có monitor: giữ vị trí cũ
            return tuple(int(v) for v in pos) if pos is not None else (100, 100)
        wa = mon.get_workarea()
        return wa.x + wa.width - BUBBLE_SIZE - 16, wa.y + wa.height // 2 - BUBBLE_SIZE // 2

    def _on_press(self, _w, event):
        if event.button == 1:
            self._press = (event.x_root, event.y_root)
            return True
        if event.button == 3:
            self.owner.popup_bubble_menu(event)
            return True
        return False

    def _on_motion(self, _w, event):
        if self._press is None:
            return False
        dx, dy = event.x_root - self._press[0], event.y_root - self._press[1]
        if dx * dx + dy * dy >= BUBBLE_DRAG_PX * BUBBLE_DRAG_PX:
            x0, y0 = self._press
            self._press = None                    # đã thành kéo, nhả chuột không mở cửa sổ
            try:
                self.begin_move_drag(1, int(x0), int(y0), event.time)
            except Exception:
                pass
        return True

    def _on_release(self, _w, event):
        if event.button == 1 and self._press is not None:
            self._press = None
            self.owner.set_view(VIEW_WINDOW)
            return True
        return False

    def _on_enter(self, *_a):
        if not self._hover:
            self._hover = True
            self._render()
        return False

    def _on_leave(self, _w, event):
        # Rời vào ô con (tooltip, ảnh) không tính là rời nút
        if event.detail != Gdk.NotifyType.INFERIOR and self._hover:
            self._hover = False
            self._render()
        return False

    def _on_configure(self, *_a):
        if self.get_visible():
            self.owner.bubble_pos = self.get_position()
            self.owner.on_configure()
        return False


class VietTypeWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title='VietType')
        # WM_CLASS phải khớp StartupWMClass trong .desktop để dock gom icon
        try:
            self.set_wmclass('VietType', 'VietType')
        except Exception:
            pass
        self._theme_menus = []      # mục "Chế độ tối" trong menu menu bar + menu nút nổi
        self._view_items = []       # (mode, RadioMenuItem) của 3 chế độ hiện, mọi menu
        self._view_syncing = False
        self.bubble = None
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
        # Chế độ hiện (cửa sổ / nút nổi / ẩn) + vị trí nút nổi lần trước
        vm = self._saved.get('view_mode')
        self.view_mode = vm if vm in VIEW_MODES else VIEW_WINDOW
        try:
            self.bubble_pos = (int(self._saved['bubble_x']), int(self._saved['bubble_y']))
        except (KeyError, TypeError, ValueError):
            self.bubble_pos = None
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
        self.hide_btn.set_tooltip_text('Thu nhỏ thành nút nổi (click nút để mở lại, kéo để di chuyển)')
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
        .chips flowboxchild { padding: 0; }
        window.vt-bubble { background-color: transparent; }
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

        # Mẫu câu dạng chips: tự xuống dòng, hiện tối đa CHIP_ROWS dòng (nhiều hơn thì
        # cuộn dọc) + drag-drop sắp xếp
        r2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.chip_sw = chip_sw = Gtk.ScrolledWindow()
        chip_sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        chip_sw.set_min_content_height(26)            # _fit_chip_rows chỉnh theo chip thật
        chip_sw.set_max_content_height(26)
        chip_sw.set_hexpand(True)
        self._chip_area_h = 0
        self._chip_fit_pending = False
        self.chip_box = Gtk.FlowBox()
        self.chip_box.get_style_context().add_class('chips')
        self.chip_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.chip_box.set_homogeneous(False)
        self.chip_box.set_max_children_per_line(100)
        self.chip_box.set_column_spacing(4)
        self.chip_box.set_row_spacing(CHIP_ROW_SPACING)
        self.chip_box.set_valign(Gtk.Align.START)
        self.chip_box.set_border_width(1)
        self.chip_box.set_can_focus(False)
        self.chip_box.connect('size-allocate', self._on_chip_alloc)
        chip_sw.add(self.chip_box)
        r2.pack_start(chip_sw, True, True, 0)
        add = Gtk.Button(label='+')
        add.get_style_context().add_class('chip-add')
        add.set_tooltip_text('Thêm mẫu mới (viết tắt + nội dung)')
        add.connect('clicked', self.on_add_dialog)
        add.connect('button-press-event', self._on_press_drag)
        r2.pack_start(add, False, False, 0)
        v.pack_start(r2, False, False, 0)

        # Tự chạy khi đăng nhập (Ubuntu: autostart .desktop, macOS: Login Items)
        self.auto_chk = Gtk.CheckButton(label='Tự chạy khi mở máy (autostart)')
        self.auto_chk.set_active(is_autostart())
        self.auto_chk.set_tooltip_text(
            'Bật = tự mở VietType mỗi lần đăng nhập'
            + (' (Login Items của macOS)' if _mac is not None else ''))
        self.auto_chk.connect('toggled', self.on_autostart)
        self.auto_chk.connect('button-press-event', self._on_press_drag)
        v.pack_start(self.auto_chk, False, False, 0)
        self.main_vbox = v

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect('button-press-event', self._on_window_press)

        self.refresh()
        self.setup_indicator()
        self.bubble = FloatingButton(self)
        # Khôi phục trạng thái ghim (pin) + chế độ tối lần trước
        if self._saved.get('keep_above'):
            self.top_btn.set_active(True)
        if self._saved.get('dark'):
            self.dark_mode = True
            self.apply_theme()
        # macOS bỏ qua set_keep_above gọi trước khi cửa sổ hiện (ghim đã lưu không có tác
        # dụng lúc mở app) và có thể mất khi ẩn -> hiện lại: áp lại mỗi lần cửa sổ map.
        self.connect('map-event', self._reapply_keep_above)
        self.connect('delete-event', self.on_close)
        self.connect('destroy', lambda *_a: self.save_window())
        # Lưu size realtime (debounce) để luôn là "latest", kể cả crash/kill
        self._save_timer = None
        self.connect('configure-event', self.on_configure)

    def _reapply_keep_above(self, *_a):
        GLib.idle_add(lambda: (self.set_keep_above(self.top_btn.get_active()), False)[-1])
        return False

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
                              history=self.history_on,
                              view_mode=self.view_mode,
                              bubble_pos=self.bubble_pos)
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
        for md in self._theme_menus:
            if md.get_active() != self.dark_mode:
                md.set_active(self.dark_mode)
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
        self.update_tray_mode()

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
        self.set_view(VIEW_BUBBLE)

    # --- 3 chế độ hiện: cửa sổ / nút nổi / ẩn (chỉ còn icon menu bar / top bar) ---
    def set_view(self, mode):
        if mode == VIEW_HIDDEN and self.indicator is None:
            mode = VIEW_BUBBLE      # không có icon menu bar/top bar thì ẩn hẳn = mất đường mở lại
        if self.get_visible():
            self.save_window()      # giữ vị trí/cỡ cửa sổ trước khi ẩn
        self.view_mode = mode
        if mode == VIEW_WINDOW:
            self.bubble.hide()
            self.deiconify()
            self.present()
        else:
            self.flush_history()
            self.hide()
            if mode == VIEW_BUBBLE:
                self.bubble.show_at(self.bubble_pos)
            else:
                self.bubble.hide()
        self._sync_view_menu()
        self.save_window()

    def _sync_view_menu(self):
        self._view_syncing = True
        try:
            for mode, item in self._view_items:
                if item.get_active() != (mode == self.view_mode):
                    item.set_active(mode == self.view_mode)
        finally:
            self._view_syncing = False

    def _on_view_item(self, item, mode):
        if item.get_active() and not self._view_syncing and mode != self.view_mode:
            self.set_view(mode)

    def popup_bubble_menu(self, event):
        if getattr(self, '_bubble_menu', None) is None:
            self._bubble_menu = self.build_tray_menu()
            self._bubble_menu.attach_to_widget(self.bubble, None)
        self._bubble_menu.popup_at_widget(self.bubble, Gdk.Gravity.SOUTH_WEST,
                                          Gdk.Gravity.NORTH_WEST, event)

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
            self.chip_box.insert(chip, -1)
            chip.get_parent().set_can_focus(False)   # FlowBoxChild: để Tab/focus vào nút như cũ
        self.chip_box.show_all()
        self._on_chip_alloc()

    def _on_chip_alloc(self, *_a):
        if not self._chip_fit_pending:
            self._chip_fit_pending = True
            GLib.idle_add(self._fit_chip_rows)

    def _fit_chip_rows(self):
        """Chiều cao vùng chip = số dòng chip thật (theo bề rộng hiện tại), tối đa
        CHIP_ROWS dòng; nhiều hơn thì cuộn dọc. Chạy lại khi đổi cỡ cửa sổ."""
        self._chip_fit_pending = False
        kids = self.chip_box.get_children()
        h = kids[0].get_allocation().height if kids else 0
        if h <= 1:
            h = kids[0].get_preferred_height()[1] if kids else 26
        total = len({k.get_allocation().y for k in kids}) if kids else 1
        rows = max(1, min(CHIP_ROWS, total))
        target = rows * h + (rows - 1) * CHIP_ROW_SPACING + 2 * self.chip_box.get_border_width()
        # Thanh cuộn dọc đòi chiều cao tối thiểu (~46px) -> chỉ bật khi thật sự có
        # nhiều hơn CHIP_ROWS dòng; còn lại vẫn cuộn được bằng chuột nhưng không hiện thanh.
        vpol = Gtk.PolicyType.AUTOMATIC if total > CHIP_ROWS else Gtk.PolicyType.EXTERNAL
        if (target, vpol) != (self._chip_area_h, self.chip_sw.get_policy()[1]):
            self._chip_area_h = target           # chỉ đặt khi đổi, tránh vòng lặp layout
            self.chip_sw.set_policy(Gtk.PolicyType.NEVER, vpol)
            self.chip_sw.set_max_content_height(-1)   # GTK đòi min <= max: bỏ max trước
            self.chip_sw.set_min_content_height(target)
            self.chip_sw.set_max_content_height(target)
        return False

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
        if _mac is not None:
            self.setup_status_icon_mac()
            return
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
            self.indicator.set_label(LABEL_TELEX_ON, '')
            self.indicator.set_menu(self.build_tray_menu())
        except Exception:
            self.indicator = None

    # --- icon trên menu bar macOS (thay cho AppIndicator của Ubuntu) ---
    @staticmethod
    def _status_pixbuf(text):
        """Ảnh cho GtkStatusIcon (chỉ dùng khi không tạo được mục chữ native)."""
        return badge_pixbuf(text, 44)

    def setup_status_icon_mac(self):
        self._tray_menu = self.build_tray_menu()
        # Mục chữ native (NSStatusItem): cùng font/màu với menu bar, tự đổi sáng/tối
        try:
            self.indicator = _mac.MacStatusItem(LABEL_TELEX_ON, self._popup_tray_at)
            self.indicator.set_tooltip('VietType — Telex: bật')
            return
        except Exception as e:
            print('menu bar text item:', e)
        # Dự phòng: icon ảnh qua GtkStatusIcon
        try:
            icon = Gtk.StatusIcon.new_from_pixbuf(self._status_pixbuf(LABEL_TELEX_ON))
            icon.set_tooltip_text('VietType — Telex: bật')
            icon.set_visible(True)

            def popup(ic, button=1, time=None):
                if time is None:
                    time = Gtk.get_current_event_time()
                self._tray_menu.popup(None, None, Gtk.StatusIcon.position_menu, ic, button, time)

            # Chuột trái hoặc phải đều mở menu (giống icon menu bar khác trên macOS)
            icon.connect('activate', lambda ic: popup(ic))
            icon.connect('popup-menu', lambda ic, b, t: popup(ic, b, t))
            self.indicator = icon
        except Exception as e:
            print('menu bar icon:', e)
            self.indicator = None

    def _popup_tray_at(self, x, y):
        """Mở menu ngay dưới mục chữ trên menu bar (x, y: góc dưới-trái của mục)."""
        # Menu GTK cần một cửa sổ GTK làm mốc: cửa sổ 1x1 trong suốt đặt ngay dưới mục chữ
        a = getattr(self, '_tray_anchor', None)
        if a is None:
            a = self._tray_anchor = Gtk.Window(type=Gtk.WindowType.POPUP)
            a.set_size_request(1, 1)
            a.set_opacity(0)
            self._tray_menu.attach_to_widget(a, None)
            self._tray_menu.connect('deactivate', lambda *_: a.hide())
        a.move(x, max(0, y - 1))
        a.show()
        self._tray_menu.popup_at_widget(a, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, None)

    def update_tray_mode(self):
        text = LABEL_TELEX_ON if self.telex_enabled else LABEL_TELEX_OFF
        tip = 'VietType — Telex: ' + ('bật' if self.telex_enabled else 'tắt')
        if self.bubble is not None:
            try:
                self.bubble.set_text(text)
            except Exception:
                pass
        if self.indicator is None:
            return
        try:
            if hasattr(self.indicator, 'set_label'):          # AppIndicator (Ubuntu)
                self.indicator.set_label(text, '')
            elif _mac is not None and isinstance(self.indicator, _mac.MacStatusItem):
                self.indicator.set_text(text)                 # chữ menu bar macOS
                self.indicator.set_tooltip(tip)
            elif isinstance(self.indicator, Gtk.StatusIcon):  # dự phòng: icon ảnh
                self.indicator.set_from_pixbuf(self._status_pixbuf(text))
                self.indicator.set_tooltip_text(tip)
        except Exception:
            pass

    def build_tray_menu(self):
        m = Gtk.Menu()
        where = 'menu bar' if _mac is not None else 'top bar'
        group = None
        for mode, label in ((VIEW_WINDOW, 'Hiện cửa sổ'),
                            (VIEW_BUBBLE, 'Nút nổi (thu nhỏ)'),
                            (VIEW_HIDDEN, f'Ẩn (chỉ icon {where})')):
            it = Gtk.RadioMenuItem.new_with_label_from_widget(group, label)
            group = it
            it.set_active(mode == self.view_mode)
            it.connect('toggled', self._on_view_item, mode)
            self._view_items.append((mode, it))
            m.append(it)
        m.append(Gtk.SeparatorMenuItem())
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
        self._theme_menus.append(md)
        mh = Gtk.MenuItem(label='Lịch sử…')
        mh.connect('activate', lambda *a: (self.present(), self.show_history()))
        m.append(mh)
        mi_about = Gtk.MenuItem(label=f'Giới thiệu VietType v{APP_VERSION}')
        mi_about.connect('activate', self.show_about)
        m.append(mi_about)
        mq = Gtk.MenuItem(label='Thoát')
        mq.connect('activate', lambda *a: self.quit_app())
        m.append(mq)
        m.show_all()
        return m

    def quit_app(self):
        """Thoát hẳn: lưu cửa sổ rồi dừng main loop (main() chốt lịch sử + đóng DB)."""
        if getattr(self, '_quitting', False):
            return
        self._quitting = True
        self.save_window()
        # Hộp thoại đang dlg.run() có vòng lặp riêng: đóng (như bấm huỷ) để không chặn thoát
        for win in Gtk.Window.list_toplevels():
            if isinstance(win, Gtk.Dialog) and win.get_visible():
                try:
                    win.response(Gtk.ResponseType.DELETE_EVENT)
                    win.destroy()
                except Exception:
                    pass
        Gtk.main_quit()

    def on_close(self, *a):
        self.save_window()
        self.flush_history()
        if self.indicator is not None:
            self.set_view(VIEW_HIDDEN)      # nút đóng = ẩn, mở lại từ icon menu bar / top bar
            return True
        return False

    def show_about(self, *_a):
        dlg = Gtk.AboutDialog(transient_for=self, modal=True)
        dlg.set_program_name('VietType')
        dlg.set_version(APP_VERSION)
        dlg.set_comments('Khung gõ Telex nhỏ gọn cho Ubuntu và macOS: gõ live,\n'
                         'chips mẫu câu, luôn trên cùng, nút nổi, icon '
                         + ('menu bar.' if _mac is not None else 'top bar.'))
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


_instance_lock = None  # giữ file mở suốt đời tiến trình để giữ khoá


def acquire_single_instance():
    """True nếu đây là bản duy nhất. Nếu đã có bản chạy (cùng state.json /
    history.db), báo nó hiện cửa sổ rồi trả False để bản này thoát."""
    global _instance_lock
    try:
        ensure_private_dir(CONFIG_DIR)
        f = os.fdopen(os.open(INSTANCE_LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600), 'a+')
        os.fchmod(f.fileno(), 0o600)            # file cũ có thể đang 0644
    except OSError as e:
        print('instance lock:', e)
        return True
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        try:
            f.seek(0)
            pid = int(f.read().strip() or 0)
            if pid > 0:
                os.kill(pid, signal.SIGUSR1)
        except (OSError, ValueError) as e:
            print('instance raise:', e)
        f.close()
        print('VietType đang chạy: đưa cửa sổ hiện có lên trước.')
        return False
    f.seek(0)
    f.truncate()
    f.write(str(os.getpid()))
    f.flush()
    _instance_lock = f
    return True


def main():
    if '--version' in sys.argv or '-V' in sys.argv:
        print(f'VietType {APP_VERSION}')
        return
    if '--autostart' in sys.argv:
        # VietType --autostart status|on|off : xem/bật/tắt tự chạy khi đăng nhập, không mở cửa sổ
        i = sys.argv.index('--autostart')
        cmd = sys.argv[i + 1] if i + 1 < len(sys.argv) else 'status'
        if cmd in ('on', 'off'):
            ok = set_autostart(cmd == 'on')
            print('autostart', cmd, 'OK' if ok else 'FAILED')
        how = 'LaunchAgent'
        if _mac is not None and _mac.login_item_status() is not None:
            how = 'Login Items (status %d: 0=off 1=on 2=needs approval)' % _mac.login_item_status()
        print('autostart:', 'on' if is_autostart() else 'off', '-', how)
        return
    GLib.set_prgname('viettype')
    ip = icon_path()
    if ip:
        try:
            Gtk.Window.set_default_icon_from_file(ip)
        except Exception as e:
            print('default icon:', e)
    if not acquire_single_instance():
        return
    for p in (SAMPLES_FILE, STATE_FILE):      # file cũ (0644) -> chỉ chủ máy đọc được
        try:
            if os.path.exists(p):
                os.chmod(p, 0o600)
        except OSError:
            pass
    try:
        migrate_autostart_mac()
    except Exception as e:
        print('autostart migrate:', e)
    w = VietTypeWindow()
    w.connect('destroy', Gtk.main_quit)
    # Bản thứ hai mở ra gửi SIGUSR1: đưa cửa sổ đang chạy lên trước (kể cả khi đang ẩn/thu nhỏ)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1,
                         lambda *a: (w.set_view(VIEW_WINDOW), True)[-1])
    # Thoát thật (không ẩn xuống menu bar) khi hệ thống yêu cầu: SIGTERM (launchd,
    # đăng xuất) và Apple Event 'quit' của macOS (tắt máy, khởi động lại, Cmd+Q từ Dock).
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                         lambda *a: (w.quit_app(), False)[-1])
    if _mac is not None:
        _mac.install_quit_handler(lambda: GLib.idle_add(lambda: (w.quit_app(), False)[-1]))
    # Mở lại đúng chế độ lần trước (cửa sổ / nút nổi / ẩn). Ngoài chế độ cửa sổ thì chỉ
    # dựng sẵn nội dung, không hiện cửa sổ (tránh chớp cửa sổ lúc mở máy).
    if w.view_mode == VIEW_WINDOW:
        w.show_all()
    else:
        for part in (w.get_titlebar(), w.get_child()):
            if part is not None:
                part.show_all()
        w.set_view(w.view_mode)
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
