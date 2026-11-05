"""
VietType History Store
Lưu lịch sử nội dung đã gõ vào SQLite (một file, không phụ thuộc ngoài).

Tiết kiệm đĩa:
- Mỗi "bản nháp" là MỘT dòng, được cập nhật tại chỗ khi gõ tiếp (không lưu từng phím).
- Trùng nội dung (bỏ qua khác biệt khoảng trắng) -> gộp, chỉ tăng số lần dùng.
- Văn bản dài được nén zlib; giới hạn số dòng + số ngày, tự dọn và thu hồi dung lượng.

Cách dùng:
    store = HistoryStore(path)
    eid = store.save(text, eid)     # tạo mới / cập nhật bản nháp, trả về id
    store.search('viet')            # tìm không dấu: 'viet' khớp 'Việt'
"""
import hashlib
import os
import sqlite3
import time
import unicodedata
import zlib

MAX_ENTRIES = 1000          # giữ tối đa N mục gần nhất
MAX_DAYS = 180              # mục cũ hơn N ngày bị xoá
MAX_CHARS = 100_000         # bỏ qua văn bản quá lớn
ZIP_MIN_BYTES = 200         # chỉ nén khi đủ dài và thực sự nhỏ hơn
PREVIEW_CHARS = 160


def _key(text):
    """Khoá chống trùng: gộp mọi khoảng trắng."""
    return hashlib.sha1(' '.join(text.split()).encode('utf-8')).digest()


def fold(s):
    """Bỏ dấu + chữ thường để tìm kiếm: 'Việt Đức' -> 'viet duc'."""
    s = unicodedata.normalize('NFD', s.lower().replace('đ', 'd').replace('Đ', 'd'))
    return ''.join(c for c in s if not unicodedata.combining(c))


def _pack(text):
    raw = text.encode('utf-8')
    if len(raw) >= ZIP_MIN_BYTES:
        z = zlib.compress(raw, 9)
        if len(z) < len(raw):
            return z, 1
    return raw, 0


def _unpack(body, zipped):
    return (zlib.decompress(body) if zipped else body).decode('utf-8')


class HistoryStore:
    def __init__(self, path, max_entries=MAX_ENTRIES, max_days=MAX_DAYS):
        self.path = path
        self.max_entries = max_entries
        self.max_days = max_days
        self._writes = 0
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, mode=0o700, exist_ok=True)
        new = not os.path.exists(path)
        self.db = sqlite3.connect(path)
        if new:
            # auto_vacuum phải đặt trước khi tạo bảng
            self.db.execute('PRAGMA auto_vacuum = INCREMENTAL')
            try:
                os.chmod(path, 0o600)   # nội dung gõ là riêng tư
            except OSError:
                pass
        self.db.execute('''CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY,
            hash BLOB UNIQUE NOT NULL,
            body BLOB NOT NULL,
            zipped INTEGER NOT NULL DEFAULT 0,
            preview TEXT NOT NULL,
            chars INTEGER NOT NULL,
            created INTEGER NOT NULL,
            updated INTEGER NOT NULL,
            uses INTEGER NOT NULL DEFAULT 1)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS entries_updated ON entries(updated)')
        self.db.commit()
        self.prune()

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass

    # --- ghi ---
    def save(self, text, entry_id=None):
        """Lưu bản nháp. entry_id = dòng đang sửa (None = mục mới).
        Trả về id của dòng chứa nội dung, hoặc None nếu không lưu."""
        text = text.strip()
        if not text or len(text) > MAX_CHARS:
            return entry_id
        h = _key(text)
        now = int(time.time())
        cur = self.db.cursor()
        row = cur.execute('SELECT id FROM entries WHERE hash = ?', (h,)).fetchone()
        if row:
            # Nội dung đã có: bản nháp hiện tại trùng với mục khác -> gộp
            other = row[0]
            if entry_id is not None and entry_id != other:
                cur.execute('DELETE FROM entries WHERE id = ?', (entry_id,))
                cur.execute('UPDATE entries SET updated = ?, uses = uses + 1 WHERE id = ?',
                            (now, other))
            elif entry_id is None:
                cur.execute('UPDATE entries SET updated = ?, uses = uses + 1 WHERE id = ?',
                            (now, other))
            self.db.commit()
            return other
        body, zipped = _pack(text)
        preview = ' '.join(text.split())[:PREVIEW_CHARS]
        if entry_id is not None and cur.execute(
                'SELECT 1 FROM entries WHERE id = ?', (entry_id,)).fetchone():
            cur.execute('''UPDATE entries SET hash = ?, body = ?, zipped = ?, preview = ?,
                           chars = ?, updated = ? WHERE id = ?''',
                        (h, body, zipped, preview, len(text), now, entry_id))
            eid = entry_id
        else:
            cur.execute('''INSERT INTO entries (hash, body, zipped, preview, chars, created, updated)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (h, body, zipped, preview, len(text), now, now))
            eid = cur.lastrowid
        self.db.commit()
        self._writes += 1
        if self._writes % 50 == 0:
            self.prune()
        return eid

    def touch(self, entry_id):
        """Đánh dấu vừa dùng lại (copy/chèn)."""
        self.db.execute('UPDATE entries SET updated = ?, uses = uses + 1 WHERE id = ?',
                        (int(time.time()), entry_id))
        self.db.commit()

    def delete(self, entry_id):
        self.db.execute('DELETE FROM entries WHERE id = ?', (entry_id,))
        self.db.commit()
        self._reclaim()

    def clear(self):
        self.db.execute('DELETE FROM entries')
        self.db.commit()
        self._reclaim()

    def prune(self):
        """Xoá mục quá cũ / vượt giới hạn rồi thu hồi trang trống."""
        cut = int(time.time()) - self.max_days * 86400
        self.db.execute('DELETE FROM entries WHERE updated < ?', (cut,))
        self.db.execute('''DELETE FROM entries WHERE id NOT IN (
            SELECT id FROM entries ORDER BY updated DESC LIMIT ?)''', (self.max_entries,))
        self.db.commit()
        self._reclaim()

    def _reclaim(self):
        try:
            self.db.execute('PRAGMA incremental_vacuum')
            self.db.commit()
        except sqlite3.Error:
            pass

    # --- đọc ---
    def get(self, entry_id):
        row = self.db.execute('SELECT body, zipped FROM entries WHERE id = ?',
                              (entry_id,)).fetchone()
        return _unpack(*row) if row else None

    def search(self, query='', limit=300):
        """[(id, text, updated, uses)] mới nhất trước; tìm không phân biệt dấu."""
        q = fold(query.strip())
        out = []
        for eid, body, zipped, updated, uses in self.db.execute(
                'SELECT id, body, zipped, updated, uses FROM entries ORDER BY updated DESC'):
            text = _unpack(body, zipped)
            if q and q not in fold(text):
                continue
            out.append((eid, text, updated, uses))
            if len(out) >= limit:
                break
        return out

    def stats(self):
        """(số mục, dung lượng file byte)."""
        n = self.db.execute('SELECT COUNT(*) FROM entries').fetchone()[0]
        try:
            size = os.path.getsize(self.path)
        except OSError:
            size = 0
        return n, size
