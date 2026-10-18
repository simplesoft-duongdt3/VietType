"""
VietType Telex Engine
Tham khảo hành vi Go Tieng Viet / OpenKey / Unikey-Telex.

Cách dùng trong Gtk.TextBuffer (live, IME-style):
    engine = TelexEngine()
    handled, new_word, cursor_offset = engine.process(buffer_word_before_cursor, char_typed)
    - nếu handled=True: thay thế word hiện tại bằng new_word (không chèn char gốc)
    - nếu handled=False: chèn char như bình thường

Cũng cung cấp hàm tiện ích telex_to_viet(raw) để convert cả từ raw (dùng cho test).
"""

TONE_MAP = {
    's': 'sac', 'f': 'huyen', 'r': 'hoi', 'x': 'nga', 'j': 'nang',
    'S': 'sac', 'F': 'huyen', 'R': 'hoi', 'X': 'nga', 'J': 'nang',
}

# base -> {tone: char}
VOWEL_TONES = {
    'a': {'ngang': 'a', 'sac': 'á', 'huyen': 'à', 'hoi': 'ả', 'nga': 'ã', 'nang': 'ạ'},
    'ă': {'ngang': 'ă', 'sac': 'ắ', 'huyen': 'ằ', 'hoi': 'ẳ', 'nga': 'ẵ', 'nang': 'ặ'},
    'â': {'ngang': 'â', 'sac': 'ấ', 'huyen': 'ầ', 'hoi': 'ẩ', 'nga': 'ẫ', 'nang': 'ậ'},
    'e': {'ngang': 'e', 'sac': 'é', 'huyen': 'è', 'hoi': 'ẻ', 'nga': 'ẽ', 'nang': 'ẹ'},
    'ê': {'ngang': 'ê', 'sac': 'ế', 'huyen': 'ề', 'hoi': 'ể', 'nga': 'ễ', 'nang': 'ệ'},
    'i': {'ngang': 'i', 'sac': 'í', 'huyen': 'ì', 'hoi': 'ỉ', 'nga': 'ĩ', 'nang': 'ị'},
    'o': {'ngang': 'o', 'sac': 'ó', 'huyen': 'ò', 'hoi': 'ỏ', 'nga': 'õ', 'nang': 'ọ'},
    'ô': {'ngang': 'ô', 'sac': 'ố', 'huyen': 'ồ', 'hoi': 'ổ', 'nga': 'ỗ', 'nang': 'ộ'},
    'ơ': {'ngang': 'ơ', 'sac': 'ớ', 'huyen': 'ờ', 'hoi': 'ở', 'nga': 'ỡ', 'nang': 'ợ'},
    'u': {'ngang': 'u', 'sac': 'ú', 'huyen': 'ù', 'hoi': 'ủ', 'nga': 'ũ', 'nang': 'ụ'},
    'ư': {'ngang': 'ư', 'sac': 'ứ', 'huyen': 'ừ', 'hoi': 'ử', 'nga': 'ữ', 'nang': 'ự'},
    'y': {'ngang': 'y', 'sac': 'ý', 'huyen': 'ỳ', 'hoi': 'ỷ', 'nga': 'ỹ', 'nang': 'ỵ'},
}

# reverse: char -> (base, tone)
CHAR_INFO = {}
for _base, _tones in VOWEL_TONES.items():
    for _tone, _ch in _tones.items():
        CHAR_INFO[_ch] = (_base, _tone)
        CHAR_INFO[_ch.upper()] = (_base.upper() if len(_base) == 1 else _base, _tone)

VOWEL_BASES = set(list(VOWEL_TONES.keys()) + [b.upper() for b in VOWEL_TONES.keys()])
ALL_VOWEL_CHARS = set(CHAR_INFO.keys())

TONE_NAMES = {'sac': 's', 'huyen': 'f', 'hoi': 'r', 'nga': 'x', 'nang': 'j'}

# Bóc dấu mũ/móc/trăng (giữ nguyên dấu thanh + hoa/thường).
# Dùng cho gõ lặp kiểu GoTV/OpenKey: ă+w -> aw, ấ+a -> áa ...
SHAPE_STRIP = {}
for _shape, _plain in (('â', 'a'), ('ê', 'e'), ('ô', 'o'),
                       ('ă', 'a'), ('ơ', 'o'), ('ư', 'u')):
    for _t in VOWEL_TONES[_shape]:
        SHAPE_STRIP[VOWEL_TONES[_shape][_t]] = VOWEL_TONES[_plain][_t]
        SHAPE_STRIP[VOWEL_TONES[_shape][_t].upper()] = VOWEL_TONES[_plain][_t].upper()


def strip_shape(c):
    """ă/â/ê/ô/ơ/ư (+dấu thanh) -> a/e/o/u tương ứng, giữ dấu + case."""
    return SHAPE_STRIP.get(c, c)


def char_info(ch):
    """-> (base_lower_or_upper, tone_name). tone 'ngang' nếu không dấu."""
    if ch in CHAR_INFO:
        return CHAR_INFO[ch]
    # consonant / other
    return (ch, None)


def is_vowel(ch):
    return ch in ALL_VOWEL_CHARS


def base_of(ch):
    b, _ = char_info(ch)
    return b


def tone_of(ch):
    if ch in CHAR_INFO:
        return CHAR_INFO[ch][1]
    return None


def apply_tone_to_char(ch, tone):
    """Đặt dấu lên 1 ký tự nguyên âm, giữ hoa/thường."""
    if ch in CHAR_INFO:
        base, _ = CHAR_INFO[ch]
        # base có thể là 'A' (hoa) nếu ch hoa
        lower_base = base.lower()
        new_lower = VOWEL_TONES[lower_base][tone]
        if ch.isupper():
            return new_lower.upper()
        return new_lower
    return ch


def strip_tone(ch):
    return apply_tone_to_char(ch, 'ngang')


def find_vowel_cluster(word):
    """Trả về list index các nguyên âm liên tiếp dài nhất (cụm vowel chính)."""
    idxs = [i for i, c in enumerate(word) if is_vowel(c)]
    if not idxs:
        return []
    # gom cụm liên tiếp
    clusters = [[idxs[0]]]
    for i in idxs[1:]:
        if i == clusters[-1][-1] + 1:
            clusters[-1].append(i)
        else:
            clusters.append([i])
    # chọn cụm chứa nguyên âm chính: ưu tiên cụm có dấu hoặc cụm dài / cụm cuối?
    # Quy tắc thực tế: cụm vowel chính thường là cụm cuối cùng trước phụ âm cuối,
    # trừ trường hợp "gi"/"qu". Đơn giản: lấy cụm dài nhất, nếu bằng nhau lấy cụm sau?
    # Nhưng "hoa" cụm oa duy nhất. "hai" cụm ai duy nhất. "bàn" cụm a.
    # Trường hợp "nghia" -> cụm ia? "nghi" + "a"? Thực tế "nghĩa": cụm ia? Hmm.
    # Chọn cụm có ít nhất 1 nguyên âm mang dấu, nếu không thì cụm cuối cùng có vowel?
    # Với từ có 2 cụm rời (ví dụ "aoe"?) hiếm. Lấy cụm dài nhất, tie -> cụm cuối.
    best = max(clusters, key=lambda c: (any(tone_of(word[i]) != 'ngang' for i in c), len(c), c[0]))
    # Nếu có cụm mang dấu mà không phải dài nhất, vẫn ưu tiên nó (để thay dấu đúng chỗ)
    return best


def tone_target_index(word):
    """Tìm vị trí đặt dấu theo quy tắc OpenKey/bogo rút gọn."""
    if not word:
        return -1
    low = word.lower()

    # Bỏ qua 'i' trong 'gi' và 'u' trong 'qu' (phụ âm ghép)
    skip = set()
    if low.startswith('gi') and len(word) > 2:
        skip.add(1)
    if low.startswith('qu') and len(word) > 2:
        skip.add(1)

    cluster = [i for i in find_vowel_cluster(word) if i not in skip]
    if not cluster:
        # thử lại không skip (vd từ chỉ "gi", "qu")
        cluster = find_vowel_cluster(word)
    if not cluster:
        return -1
    if len(cluster) == 1:
        return cluster[0]

    cluster_chars = ''.join(base_of(word[i]).lower() for i in cluster)

    # 1. Các cụm đặc biệt luôn đặt dấu ở âm thứ 2: oa oe oo uy iê yê uô ươ oă uă
    #    (bao gồm biến thể đã có dấu: òa, òe...)
    special_second = {'oa', 'oe', 'oo', 'uy', 'ie', 'ye', 'uo', 'uo', 'oa', 'ua'}
    # chuẩn hoá: iê->ie, yê->ye, uô->uo, ươ->uo (base)
    if cluster_chars in ('oa', 'oe', 'oo', 'uy', 'ie', 'ye', 'uo', 'oa', 'ua'):
        return cluster[1]
    if len(cluster) == 3 and cluster_chars in ('ieu', 'yeu', 'uoi', 'uou'):
        # ví dụ: nhiều, yêu, tuổi -> dấu ở âm giữa
        return cluster[1]

    # 2. Nếu có đúng 1 nguyên âm đặc biệt (ă â ê ô ơ ư) -> đặt ở đó
    #    Nếu cụm ươ (ư + ơ): đặt ở ơ (âm 2)
    specials = []
    for i in cluster:
        b = base_of(word[i]).lower()
        if b in ('ă', 'â', 'ê', 'ô', 'ơ', 'ư'):
            specials.append(i)
    if len(specials) == 1:
        return specials[0]
    if len(specials) >= 2:
        # ưu tiên ơ/ê/ô (vd rượu -> ơ)
        for i in specials:
            if base_of(word[i]).lower() in ('ơ', 'ê', 'ô'):
                return i
        return specials[-1]

    # 3. Nếu từ kết thúc bằng phụ âm (sau cụm còn phụ âm) -> dấu ở âm cuối của cụm
    last_cluster_pos = cluster[-1]
    if last_cluster_pos < len(word) - 1:
        return cluster[-1]

    # 4. Mặc định (kết thúc bằng nguyên âm, không có dấu phụ): dấu ở âm đầu
    #    vd: hai->hài, nói, hỏi... nhưng hoa->hoà? Trường hợp oa đã xử lý ở (1).
    return cluster[0]


def set_tone(word, tone):
    """Đặt/thay dấu cho cả âm tiết. tone in sac/huyen/hoi/nga/nang/ngang."""
    idx = tone_target_index(word)
    if idx < 0:
        return None
    chars = list(word)
    # xoá dấu cũ ở toàn bộ từ (mỗi âm tiết chỉ 1 dấu)
    for i, c in enumerate(chars):
        if is_vowel(c) and tone_of(c) not in (None, 'ngang'):
            chars[i] = strip_tone(c)
    chars[idx] = apply_tone_to_char(chars[idx], tone)
    return ''.join(chars)


def current_tone(word):
    for c in word:
        t = tone_of(c)
        if t and t != 'ngang':
            return t
    return 'ngang'


class TelexEngine:
    """State-less: xử lý từng ký tự gõ thêm vào cuối từ hiện tại."""

    def process(self, word, ch):
        """
        word: từ hiện tại trước cursor (không gồm space/câu).
        ch: ký tự vừa gõ (độ dài 1).
        Trả về (handled: bool, new_word: str).
        Nếu handled True -> caller thay word bằng new_word, không chèn ch.
        Nếu False -> caller chèn ch bình thường.
        """
        if not ch or len(ch) != 1:
            return (False, word)

        # --- dd -> đ (gõ lặp d sau đ -> dd, kiểu GoTV: undo + trả phím thô) ---
        if ch in ('d', 'D'):
            if word and word[-1] in ('d', 'D'):
                # dd -> đ : giữ hoa nếu có chữ hoa
                upper = word[-1].isupper() or ch.isupper()
                new_word = word[:-1] + ('Đ' if upper else 'đ')
                return (True, new_word)
            if word and word[-1] in ('đ', 'Đ'):
                # đ + d -> dd (giữ case chữ đ cũ + case phím vừa gõ)
                plain = 'D' if word[-1].isupper() else 'd'
                return (True, word[:-1] + plain + ch)
            return (False, word)

        # --- w : ă ơ ư (quy tắc undo kiểu GoTV/OpenKey) ---
        if ch in ('w', 'W'):
            upper = ch.isupper()
            if not word:
                return (True, 'Ư' if upper else 'ư')
            last = word[-1]
            # 1) shortcut-undo: 'ư'+w -> 'w', 'tư'+w -> 'tw' (bóc token ư, trả phím thô)
            if last in ('ư', 'Ư'):
                out = 'W' if (last.isupper() or upper) else 'w'
                return (True, word[:-1] + out)
            lb = base_of(last).lower()
            lt = tone_of(last)
            # 2) a/o/u + w -> ă/ơ/ư (giữ dấu + hoa, vd á + w -> ắ)
            if lb == 'a' and base_of(last).lower() not in ('ă', 'â'):
                new_c = 'Ă' if (last.isupper() or upper) else 'ă'
                if lt and lt != 'ngang':
                    new_c = apply_tone_to_char(new_c, lt)
                return (True, word[:-1] + new_c)
            # o + w -> ơ
            if lb == 'o' and base_of(last).lower() not in ('ô', 'ơ'):
                new_c = 'Ơ' if (last.isupper() or upper) else 'ơ'
                if lt and lt != 'ngang':
                    new_c = apply_tone_to_char(new_c, lt)
                return (True, word[:-1] + new_c)
            # u + w -> ư
            if lb == 'u' and base_of(last).lower() != 'ư':
                new_c = 'Ư' if (last.isupper() or upper) else 'ư'
                if lt and lt != 'ngang':
                    new_c = apply_tone_to_char(new_c, lt)
                return (True, word[:-1] + new_c)
            # 3) repeat-undo: ă/ơ/ứ... + w -> bóc móc/mũ, giữ dấu, thêm w thô
            #    vd: aw+w -> aw, ắ+w -> áw, tứ+w -> túw
            if base_of(last).lower() in ('ă', 'ơ', 'ư'):
                return (True, word[:-1] + strip_shape(last) + ch)
            # w đơn sau phụ âm -> ư (vd "tw" -> "tư")
            if not is_vowel(last):
                return (True, word + ('Ư' if upper else 'ư'))
            return (False, word)

        # --- aa -> â, oo -> ô, ee -> ê ---
        if ch in ('a', 'A', 'o', 'O', 'e', 'E'):
            lc = ch.lower()
            if word:
                last = word[-1]
                if lc == 'a' and base_of(last).lower() == 'a' and base_of(last).lower() not in ('ă', 'â'):
                    # a + a -> â (giữ dấu + hoa)
                    lt = tone_of(last)
                    is_up = last.isupper() or ch.isupper()
                    new_c = 'Â' if is_up else 'â'
                    if lt and lt != 'ngang':
                        new_c = apply_tone_to_char(new_c, lt)
                    return (True, word[:-1] + new_c)
                if lc == 'o' and base_of(last).lower() == 'o' and base_of(last).lower() not in ('ô', 'ơ'):
                    lt = tone_of(last)
                    is_up = last.isupper() or ch.isupper()
                    new_c = 'Ô' if is_up else 'ô'
                    if lt and lt != 'ngang':
                        new_c = apply_tone_to_char(new_c, lt)
                    return (True, word[:-1] + new_c)
                if lc == 'e' and base_of(last).lower() == 'e' and base_of(last).lower() != 'ê':
                    lt = tone_of(last)
                    is_up = last.isupper() or ch.isupper()
                    new_c = 'Ê' if is_up else 'ê'
                    if lt and lt != 'ngang':
                        new_c = apply_tone_to_char(new_c, lt)
                    return (True, word[:-1] + new_c)
                # â/e/o + trùng phím -> undo + trả phím thô, GIỮ dấu (kiểu GoTV)
                # vd: â+a -> aa, ấ+a -> áa
                if lc == 'a' and base_of(last).lower() == 'â':
                    return (True, word[:-1] + strip_shape(last) + ch)
                if lc == 'o' and base_of(last).lower() == 'ô':
                    return (True, word[:-1] + strip_shape(last) + ch)
                if lc == 'e' and base_of(last).lower() == 'ê':
                    return (True, word[:-1] + strip_shape(last) + ch)
            return (False, word)

        # --- tone s f r x j (gõ lặp phím dấu -> undo + trả phím thô, kiểu GoTV:
        #     ass -> as, rồi s nữa -> ás) ---
        if ch in TONE_MAP:
            tone = TONE_MAP[ch]
            if not word or tone_target_index(word) < 0:
                return (False, word)
            cur = current_tone(word)
            if cur == tone:
                stripped = ''.join(strip_tone(c) if is_vowel(c) else c for c in word)
                return (True, stripped + ch)
            new_word = set_tone(word, tone)
            if new_word is None:
                return (False, word)
            return (True, new_word)

        # --- z: xoá dấu ---
        if ch in ('z', 'Z'):
            if not word:
                return (False, word)
            # nếu có dấu thanh -> xoá dấu thanh
            if current_tone(word) != 'ngang':
                new_word = set_tone(word, 'ngang')
                return (True, new_word)
            # nếu không có dấu thanh nhưng có ă â ê ô ơ ư đ -> trả về gốc
            changed = False
            out = []
            for c in word:
                if c in SHAPE_STRIP:
                    out.append(SHAPE_STRIP[c]); changed = True
                elif c in ('đ', 'Đ'):
                    out.append('D' if c.isupper() else 'd'); changed = True
                else:
                    out.append(c)
            if changed:
                return (True, ''.join(out))
            return (False, word)

        return (False, word)


def telex_to_viet(raw):
    """Convert chuỗi raw telex thành tiếng Việt (dùng cho test/batch).
    Ví dụ: 'Tieng Viet' với telex 'Tieengs Vieets' -> 'Tiếng Việt'."""
    eng = TelexEngine()
    word = ''
    out = ''
    for ch in raw:
        if ch.isalnum() or ch in ('đ', 'Đ', '_'):
            # vẫn xử lý để giữ từ? Với batch, mọi ký tự chữ đều thuộc từ
            # nhưng engine.process cần word hiện tại
            handled, new_word = eng.process(word, ch)
            if handled:
                word = new_word
            else:
                word = word + ch
        else:
            # biên từ: flush
            out += word
            word = ''
            out += ch
    out += word
    # Nếu ký tự telex nằm trong từ nhưng là phụ âm thường (b,c...) process trả False và append.
    return out
