#!/usr/bin/env /usr/bin/python3
"""VietType: TextArea gõ Telex + chips mẫu câu (viết tắt + nội dung).
- Click chip: copy nội dung • Đúp chip: chèn vào ô nhập • Phải: sửa/xoá/dời
- Kéo-thả chip để sắp xếp • ESC: hoàn tác dấu vừa gõ
- Alt+kéo (mọi nơi) hoặc kéo từ nền/thanh trạng thái để di chuyển cửa sổ."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject, GLib
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telex_engine import TelexEngine

APP_ID = 'vn.viettype.pad'
APP_VERSION = '1.3.0'
CONFIG_DIR = os.path.expanduser('~/.config/viettype')
SAMPLES_FILE = os.path.join(CONFIG_DIR, 'samples.json')
AUTOSTART_FILE = os.path.expanduser('~/.config/autostart/viettype.desktop')


def app_dir():
    return os.path.dirname(os.path.abspath(__file__))


def icon_path():
    for p in ('/opt/viettype/viettype.svg',
              os.path.join(app_dir(), 'viettype.svg')):
        if os.path.exists(p):
            return p
    return None


def app_exec_path():
    installed = '/opt/viettype/viettype_app.py'
    if os.path.exists(installed):
        return '/usr/bin/python3 ' + installed
    return '/usr/bin/python3 ' + os.path.abspath(__file__)


def is_autostart():
    return os.path.exists(AUTOSTART_FILE)


def set_autostart(on):
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

DEFAULT_SAMPLES = [
    {"abbr": "chao", "content": "Xin chào, tôi có thể giúp gì cho bạn?"},
    {"abbr": "camon", "content": "Cảm ơn quý khách đã tin tưởng sử dụng dịch vụ."},
    {"abbr": "xn", "content": "Vui lòng xác nhận lại thông tin giúp em ạ."},
    {"abbr": "hen", "content": "Hẹn gặp lại vào lúc 9 giờ sáng mai."},
    {"abbr": "mail", "content": "Tôi đã nhận được email của bạn, tôi sẽ phản hồi sớm."},
]
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
    Tự chuyển dữ liệu cũ (list chuỗi) sang định dạng mới."""
    def defaults():
        return [dict(d) for d in DEFAULT_SAMPLES]
    try:
        if os.path.exists(SAMPLES_FILE):
            with open(SAMPLES_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
                if isinstance(d, dict) and isinstance(d.get('templates'), list):
                    d = d['templates']
                if isinstance(d, list) and d:
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
                    if out:
                        return out
    except Exception as e:
        print('samples:', e)
    return defaults()


def save_samples(s):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(SAMPLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print('save:', e)


class VietTypeWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title='VietType')
        # WM_CLASS phải khớp StartupWMClass trong .desktop để dock gom icon
        try:
            self.set_wmclass('VietType', 'VietType')
        except Exception:
            pass
        ip = icon_path()
        if ip:
            try:
                self.set_icon_from_file(ip)
            except Exception as e:
                print('icon:', e)
        self.set_default_size(320, 270)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.engine = TelexEngine()
        self.telex_enabled = True
        self._busy = False
        self._faded = False
        self.samples = load_samples()
        self.indicator = None
        self.undo = []          # stack (mark, old_word, new_word) cho ESC hoàn tác
        self._click_timer = None
        self._click_pending = None  # idx chip chờ phân biệt click/đúp

        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.props.title = 'VietType'
        hb.props.subtitle = f'Telex pad • v{APP_VERSION}'
        hb.set_decoration_layout('menu:close')
        self.set_titlebar(hb)

        self.telex_sw = Gtk.Switch()
        self.telex_sw.set_active(True)
        self.telex_sw.set_tooltip_text('Telex BẬT/TẮT')
        self.telex_sw.connect('notify::active', self.on_telex)
        b1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        b1.pack_start(Gtk.Label(label='Telex', opacity=0.8), False, False, 0)
        b1.pack_start(self.telex_sw, False, False, 0)
        hb.pack_start(b1)

        self.top_btn = Gtk.ToggleButton(label='Top')
        self.top_btn.set_tooltip_text('Luôn trên cùng')
        self.top_btn.connect('toggled', lambda b: self.set_keep_above(b.get_active()))
        hb.pack_end(self.top_btn)

        self.fade_btn = Gtk.ToggleButton(label='Mờ')
        self.fade_btn.set_tooltip_text('Bật/tắt chế độ mờ (trong suốt 70%)')
        self.fade_btn.connect('toggled', self.on_fade)
        hb.pack_end(self.fade_btn)

        self.hide_btn = Gtk.Button(label='Ẩn')
        self.hide_btn.set_tooltip_text('Ẩn xuống top bar (mở lại từ icon VIE)')
        self.hide_btn.connect('clicked', self.on_hide_clicked)
        hb.pack_end(self.hide_btn)

        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        v.set_border_width(6)
        self.add(v)

        css = Gtk.CssProvider()
        css.load_from_data(b'''
        .chip { border-radius: 12px; padding: 1px 10px; font-size: 11px; }
        .chip-add { border-radius: 12px; padding: 1px 10px; font-weight: bold; opacity: 0.8; }
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
        self.tv.set_tooltip_text('Gõ Telex • ESC: hoàn tác dấu vừa gõ • Alt+kéo: di chuyển cửa sổ')
        self.tv.get_buffer().connect('insert-text', self.on_insert)
        self.tv.get_buffer().connect('changed', self.on_changed)
        self.tv.connect('key-press-event', self.on_key)
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

        # 1 hàng nút duy nhất
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for label, tip, cb in [
            ('Copy', 'Copy vào clipboard', self.on_copy),
            ('Clear', 'Xoá trắng', self.on_clear),
        ]:
            b = Gtk.Button(label=label)
            b.set_tooltip_text(tip)
            b.connect('clicked', cb)
            b.connect('button-press-event', self._on_press_drag)
            r.pack_start(b, True, True, 0)
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
        self.connect('delete-event', self.on_close)

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

    # --- ESC hoàn tác dấu vừa gõ ---
    def on_key(self, _w, event):
        if Gdk.keyval_name(event.keyval) == 'Escape':
            if self.try_undo():
                return True
        return False

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
            if not end.forward_chars(len(new)):
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
        if getattr(event, 'button', 0) != 1:
            return False
        if event.state & Gdk.ModifierType.MOD1_MASK:
            return self._begin_move(event)
        try:
            target = Gtk.get_event_widget(event)
        except Exception:
            return False
        # CHỈ kéo khi nhấn trực tiếp lên nền/vùng trống — tuyệt đối không
        # đi ngược parents (nếu không, click trong TextView/nút/chip cũng
        # kích hoạt di chuyển cửa sổ và cướp focus/gõ phím).
        if target is self or target is self.main_vbox \
                or target is self.drag_eb or target is self.st:
            return self._begin_move(event)
        return False

    def on_changed(self, buf):
        m = 'BẬT' if self.telex_enabled else 'TẮT'
        self.st.set_markup(f'<small>Telex <b>{m}</b> • {buf.get_char_count()}</small>')

    def on_telex(self, sw, _p):
        self.telex_enabled = sw.get_active()
        self.on_changed(self.tv.get_buffer())
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
        GLib.timeout_add(1200, lambda: self.on_changed(buf) or False)

    def on_clear(self, _b):
        self.tv.get_buffer().set_text('')
        self.tv.grab_focus()

    def on_fade(self, btn):
        self._faded = btn.get_active()
        try:
            self.set_opacity(0.7 if self._faded else 1.0)
        except Exception:
            pass

    def on_hide_clicked(self, _b):
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
        buf = self.tv.get_buffer()
        GLib.timeout_add(1200, lambda: self.on_changed(buf) or False)

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
            self.tv.get_buffer().insert_at_cursor(self.samples[idx]['content'])
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


if __name__ == '__main__':
    main()
