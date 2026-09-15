"""极简 PDF 文本提取器 v2（纯标准库，支持带 ToUnicode 的 CID 字体）。

用途：在没有 pypdf/pdfminer 的环境里，从官方 PDF 手册中提取正文文本，
用于核对 SCPI 协议细节。支持 --grep 关键词过滤输出行。
用法：
  python scripts/pdf_extract.py <pdf> [--grep 关键词 ...] [--max-chars N]
"""
from __future__ import annotations

import re
import sys
import zlib


# ---------------- PDF 基础 ----------------

def find_objects(data: bytes):
    """{objnum: raw_object_bytes}"""
    objs = {}
    pat = re.compile(rb"(\d+)\s+(\d+)\s+obj(.*?)endobj", re.S)
    for m in pat.finditer(data):
        objs[int(m.group(1))] = m.group(3)
    return objs


def decompress_obj(raw: bytes):
    """(字典部分, 解压后的流或 None)"""
    idx = raw.find(b"stream")
    if idx < 0:
        return raw, None
    dict_part = raw[:idx]
    m = re.search(rb"stream\r?\n(.*?)\r?\nendstream", raw[idx:], re.S)
    if not m:
        return dict_part, None
    s = m.group(1)
    try:
        stream = zlib.decompress(s)
    except Exception:
        try:
            stream = zlib.decompress(s, -15)
        except Exception:
            stream = s
    return dict_part, stream



def expand_objstm(objs):
    """展开对象流(ObjStm)：把其中内嵌对象加入字典。"""
    extra = {}
    for num, raw in objs.items():
        dpart, stream = decompress_obj(raw)
        if not stream or dict_get_str(dpart, b"Type") != "ObjStm":
            continue
        kind_n, val_n = dict_get(dpart, b"N")
        kind_f, val_f = dict_get(dpart, b"First")
        if kind_n != "num" or kind_f != "num":
            continue
        n = int(val_n)
        first = int(val_f)
        head = stream[:first].split()
        if len(head) < 2 * n:
            continue
        pairs = []
        for i in range(0, 2 * n, 2):
            pairs.append((int(head[i]), int(head[i + 1])))
        for k in range(n):
            objnum, off = pairs[k]
            end = pairs[k + 1][1] if k + 1 < n else len(stream)
            extra[objnum] = stream[first + off:first + end]
    merged = dict(objs)
    merged.update(extra)
    return merged

def skip_ws(b, i):
    while i < len(b) and b[i] in b" \t\r\n\f\0":
        i += 1
    return i


def read_dict(b, i):
    """i 指向 '<<'，返回 (内部内容, 结束后的位置)。处理嵌套 << >>。"""
    assert b[i:i + 2] == b"<<", (i, b[i:i + 20])
    i += 2
    depth = 1
    j = i
    while j < len(b) and depth > 0:
        if b[j:j + 2] == b"<<":
            depth += 1
            j += 2
        elif b[j:j + 2] == b">>":
            depth -= 1
            j += 2
        else:
            j += 1
    return b[i:j - 2], j


def read_value(b, i):
    """从 i 读一个值：返回 (kind, value_bytes, next_i)。kind: ref/name/num/str/hex/arr/dict"""
    i = skip_ws(b, i)
    if i >= len(b):
        return None, b"", i
    c = b[i]
    if c == 0x2F:
        j = i + 1
        while j < len(b) and b[j] not in b" \t\r\n\f()<>[]{}/%":
            j += 1
        return "name", b[i + 1:j], j
    if c == 0x28:
        depth = 1
        j = i + 1
        while j < len(b) and depth > 0:
            if b[j] == 0x5C:
                j += 2
                continue
            if b[j] == 0x28:
                depth += 1
            elif b[j] == 0x29:
                depth -= 1
            j += 1
        return "str", b[i + 1:j - 1], j
    if c == 0x3C:
        if b[i:i + 2] == b"<<":
            content, j = read_dict(b, i)
            return "dict", content, j
        j = b.find(b">", i + 1)
        if j < 0:
            j = len(b)
        return "hex", b[i + 1:j], j + 1
    if c == 0x5B:
        j = i + 1
        items = []
        while j < len(b) and b[j] != 0x5D:
            kind, val, j2 = read_value(b, j)
            if kind is None:
                break
            items.append((kind, val))
            j = j2
        return "arr", items, min(j + 1, len(b))
    # ref: N g R
    m = re.match(rb"(\d+)\s+(\d+)\s+R", b[i:])
    if m:
        return "ref", m.group(0), i + m.end()
    # number
    m = re.match(rb"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?", b[i:])
    if m:
        return "num", m.group(0), i + m.end()
    # keyword
    j = i
    while j < len(b) and b[j] not in b" \t\r\n\f()<>[]{}/%":
        j += 1
    if j == i:
        j = i + 1
    return "kw", b[i:j], j


def dict_get(dbytes, key):
    """在字典内容字节中找 /key 后的值。key: bytes 如 b'Type'。"""
    pat = re.compile(rb"/" + re.escape(key) + rb"(?=[\s/<\[(])")
    for m in pat.finditer(dbytes):
        kind, val, _ = read_value(dbytes, m.end())
        if kind is not None:
            return kind, val
    return None, None


def dict_get_str(dbytes, key):
    kind, val = dict_get(dbytes, key)
    if kind is None:
        return None
    return val.decode("latin-1", "replace").strip()


def refs_from_array(arr_items):
    return [int(v.split()[0]) for k, v in arr_items if k == "ref"]


# ---------------- ToUnicode ----------------

def load_tounicode(objs, objnum):
    if objnum is None:
        return {}
    raw = objs.get(objnum)
    if raw is None:
        return {}
    _, stream = decompress_obj(raw)
    if not stream:
        return {}
    cmap = {}
    for m in re.finditer(rb"beginbfchar(.*?)endbfchar", stream, re.S):
        for e in re.finditer(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", m.group(1)):
            src = int(e.group(1), 16)
            try:
                cmap[src] = bytes.fromhex(e.group(2).decode()).decode("utf-16-be", "replace")
            except Exception:
                cmap[src] = "?"
    for m in re.finditer(rb"beginbfrange(.*?)endbfrange", stream, re.S):
        for e in re.finditer(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", m.group(1)):
            lo, hi = int(e.group(1), 16), int(e.group(2), 16)
            b0 = bytes.fromhex(e.group(3).decode())
            for code in range(lo, min(hi, lo + 200000) + 1):
                try:
                    cmap[code] = b0.decode("utf-16-be", "replace")
                except Exception:
                    cmap[code] = "?"
                b0 = (int.from_bytes(b0, "big") + 1).to_bytes(max(len(b0), 2), "big")
    return cmap


def font_cmap(objs, fontnum):
    """跟随字体对象/DescendantFonts 找到 ToUnicode 映射。"""
    if fontnum is None:
        return {}
    raw = objs.get(fontnum)
    if raw is None:
        return {}
    dpart, _ = decompress_obj(raw)
    kind, val = dict_get(dpart, b"ToUnicode")
    if kind == "ref":
        return load_tounicode(objs, int(val.split()[0]))
    # Type0: DescendantFonts [ d 0 R ]
    kind, val = dict_get(dpart, b"DescendantFonts")
    if kind == "arr":
        for n in refs_from_array(val):
            cm = font_cmap(objs, n)
            if cm:
                return cm
    return {}


def page_fonts(objs, page_dict):
    """返回 {资源名: cmap}"""
    kind, res = dict_get(page_dict, b"Resources")
    if kind != "dict":
        return {}
    kind, fontdict = dict_get(res, b"Font")
    if kind != "dict":
        return {}
    fonts = {}
    pos = 0
    while True:
        m = re.search(rb"/([A-Za-z0-9_]+)\s*", fontdict[pos:])
        if not m:
            break
        pos2 = pos + m.end()
        kind2, val2, nxt = read_value(fontdict, pos2)
        if kind2 == "ref":
            fonts[m.group(1).decode()] = font_cmap(objs, int(val2.split()[0]))
        pos = nxt
        if pos >= len(fontdict):
            break
    return fonts


def page_contents(objs, page_dict):
    kind, val = dict_get(page_dict, b"Contents")
    nums = []
    if kind == "ref":
        nums = [int(val.split()[0])]
    elif kind == "arr":
        nums = refs_from_array(val)
    streams = []
    for n in nums:
        raw = objs.get(n)
        if raw is None:
            continue
        _, stream = decompress_obj(raw)
        if stream is not None:
            streams.append(stream)
    return streams


def iter_pages(objs):
    for num, raw in objs.items():
        dpart, stream = decompress_obj(raw)
        if dict_get_str(dpart, b"Type") != "Page":
            continue
        yield num, dpart


# ---------------- 解码 ----------------

def decode_hex_string(h: bytes, cmap):
    h = re.sub(rb"[^0-9A-Fa-f]", b"", h)
    if not h:
        return ""
    if len(h) % 2:
        h = b"0" + h

    def try_width(w):
        return "".join(cmap.get(int(h[i:i + w], 16), "") for i in range(0, len(h) - w + 1, w))

    res2 = try_width(4) if len(h) % 4 == 0 else ""
    res1 = try_width(2)
    if res2 and res2.count("") <= res1.count(""):
        return res2
    return res1


def decode_literal(s: bytes, cmap):
    out = bytearray()
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == 0x5C and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in b"()\\":
                out.append(nxt); i += 2; continue
            if nxt in b"nrtbf":
                out.append({ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}[nxt])
                i += 2; continue
            if 48 <= nxt <= 55:
                m = re.match(rb"\\([0-7]{1,3})", s[i:])
                out.append(int(m.group(1), 8) & 0xFF)
                i += m.end(); continue
        out.append(ch); i += 1
    if not out:
        return ""
    if all(b < 128 for b in out) and not any(b in cmap for b in out):
        return out.decode("latin-1", "replace")
    return "".join(cmap.get(b, chr(b)) for b in out)


# ---------------- 文本抽取 ----------------

def tokenize(stream: bytes):
    toks = []
    i, n = 0, len(stream)
    while i < n:
        c = stream[i]
        if c in b" \t\r\n\f\0":
            i += 1
            continue
        if c == 0x25:
            j = stream.find(b"\n", i)
            i = j + 1 if j >= 0 else n
            continue
        if c == 0x2F:
            j = i + 1
            while j < n and stream[j] not in b" \t\r\n\f()<>[]{}/%":
                j += 1
            toks.append(("name", stream[i + 1:j]))
            i = j
            continue
        if c == 0x28:
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if stream[j] == 0x5C:
                    j += 2
                    continue
                if stream[j] == 0x28:
                    depth += 1
                elif stream[j] == 0x29:
                    depth -= 1
                j += 1
            toks.append(("str", stream[i + 1:j - 1]))
            i = j
            continue
        if c == 0x3C:
            if stream[i:i + 2] == b"<<":
                j = i + 2
                depth = 1
                while j < n and depth:
                    if stream[j:j + 2] == b"<<":
                        depth += 1; j += 2
                    elif stream[j:j + 2] == b">>":
                        depth -= 1; j += 2
                    else:
                        j += 1
                i = j
                continue
            j = stream.find(b">", i + 1)
            if j < 0:
                j = n
            toks.append(("hex", stream[i + 1:j]))
            i = j + 1
            continue
        if c == 0x5B:
            j = i + 1
            items = []
            while j < n and stream[j] != 0x5D:
                kind, val, j2 = read_value(stream, j)
                if kind is None:
                    break
                if kind in ("str", "hex"):
                    items.append((kind, val))
                j = j2
            toks.append(("arr", items))
            i = j + 1
            continue
        if 0x30 <= c <= 0x39 or c in b"+-.":
            m = re.match(rb"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?", stream[i:])
            toks.append(("num", m.group(0)))
            i += m.end()
            continue
        j = i
        while j < n and stream[j] not in b" \t\r\n\f()<>[]{}/%":
            j += 1
        if j == i:
            j = i + 1
        toks.append(("kw", stream[i:j]))
        i = j
    return toks


def extract_content(stream: bytes, fonts):
    toks = tokenize(stream)
    lines = []
    cur = []
    font_cmap = {}
    in_text = False
    i = 0
    while i < len(toks):
        kind, val = toks[i]
        if kind == "kw":
            if val == b"BT":
                in_text = True
            elif val == b"ET":
                in_text = False
                if cur:
                    lines.append(b"".join(cur)); cur = []
            elif in_text and val in (b"Td", b"TD", b"T*"):
                if cur:
                    lines.append(b"".join(cur)); cur = []
        elif kind == "name":
            if (i + 2 < len(toks) and toks[i + 1][0] == "num"
                    and toks[i + 2][0] == "kw" and toks[i + 2][1] == b"Tf"):
                font_cmap = fonts.get(val.decode("latin-1"), {})
                i += 2
        elif kind in ("str", "hex") and in_text:
            s = decode_literal(val, font_cmap) if kind == "str" else decode_hex_string(val, font_cmap)
            cur.append(s.encode("utf-8", "replace"))
        elif kind == "arr" and in_text:
            for it in val:
                if it[0] == "str":
                    cur.append(decode_literal(it[1], font_cmap).encode("utf-8", "replace"))
                elif it[0] == "hex":
                    cur.append(decode_hex_string(it[1], font_cmap).encode("utf-8", "replace"))
        i += 1
    if cur:
        lines.append(b"".join(cur))
    out = []
    for ln in lines:
        try:
            out.append(ln.decode("utf-8", "replace"))
        except Exception:
            out.append(ln.decode("latin-1", "replace"))
    return out


# ---------------- 主流程 ----------------

def extract_all(objs):
    lines = []
    for pagenum, pagedict in iter_pages(objs):
        fonts = page_fonts(objs, pagedict)
        for stream in page_contents(objs, pagedict):
            if len(stream) > 1_500_000 or (b"Tj" not in stream and b"TJ" not in stream):
                continue
            for ln in extract_content(stream, fonts):
                t = ln.strip()
                if t:
                    lines.append(t)
    return lines


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    path = args[0]
    greps = []
    max_chars = 200000
    i = 1
    while i < len(args):
        if args[i] == "--grep":
            greps.append(args[i + 1]); i += 2
        elif args[i] == "--max-chars":
            max_chars = int(args[i + 1]); i += 2
        else:
            i += 1
    data = open(path, "rb").read()
    objs = expand_objstm(find_objects(data))
    lines = extract_all(objs)
    if greps:
        seen = set()
        for g in greps:
            for t in lines:
                if g in t and t not in seen:
                    seen.add(t)
                    print(t)
    else:
        print("\n".join(lines)[:max_chars])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

