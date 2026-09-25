"""xlsx 结构检查工具（只读）：打印工作表的单元格、合并区、列宽与关键样式。

用法： python scripts/xlsx_inspect.py <xlsx路径> [--sheet 名称] [--max-rows N] [--style]
仅读取，不会修改目标文件。
"""
from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def col_index(ref: str) -> int:
    m = re.match(r"([A-Z]+)(\d+)", ref or "")
    if not m:
        return 0
    idx = 0
    for ch in m.group(1):
        idx = idx * 26 + (ord(ch) - 64)
    return idx


def load(zpath):
    z = zipfile.ZipFile(zpath)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    styles = {}
    if "xl/styles.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/styles.xml"))
        fonts = []
        for f in root.findall("m:fonts/m:font", NS):
            bold = f.find("m:b", NS) is not None
            name = f.find("m:name", NS)
            size = f.find("m:sz", NS)
            fonts.append({"bold": bold, "name": name.get("val") if name is not None else "",
                          "size": size.get("val") if size is not None else ""})
        fills = []
        for f in root.findall("m:fills/m:fill", NS):
            pf = f.find("m:patternFill", NS)
            color = ""
            if pf is not None:
                fg = pf.find("m:fgColor", NS)
                if fg is not None:
                    color = fg.get("rgb") or fg.get("theme") or ""
            fills.append(color)
        borders = []
        for b in root.findall("m:borders/m:border", NS):
            edges = [e.tag.split("}")[1] for e in b if e.tag.split("}")[1] in ("left", "right", "top", "bottom") and len(e)]
            borders.append(",".join(edges))
        xfs = []
        for xf in root.findall("m:cellXfs/m:xf", NS):
            xfs.append({"font": int(xf.get("fontId", 0)), "fill": int(xf.get("fillId", 0)),
                        "border": int(xf.get("borderId", 0)), "align": xf.find("m:alignment", NS) is not None})
        styles = {"fonts": fonts, "fills": fills, "borders": borders, "xfs": xfs}
    return z, shared, styles


def sheets(z):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rel_map = {r.get("Id"): r.get("Target") for r in rels}
    out = []
    for sh in wb.findall("m:sheets/m:sheet", NS):
        rid = sh.get("{%s}id" % NS["r"])
        target = rel_map.get(rid, "")
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        out.append((sh.get("name"), target))
    return out


def dump(zpath, only_sheet=None, max_rows=40, show_style=False):
    z, shared, styles = load(zpath)
    print("=" * 70)
    print("文件:", zpath)
    for name, target in sheets(z):
        if only_sheet and name != only_sheet:
            continue
        root = ET.fromstring(z.read(target))
        dim = root.find("m:dimension", NS)
        print("-" * 70)
        print("工作表: %s  范围: %s" % (name, dim.get("ref") if dim is not None else "?"))
        cols = root.find("m:cols", NS)
        if cols is not None:
            widths = []
            for c in cols.findall("m:col", NS):
                widths.append("%s-%s w=%s" % (c.get("min"), c.get("max"), c.get("width")))
            print("列宽:", "; ".join(widths))
        merges = root.find("m:mergeCells", NS)
        if merges is not None:
            print("合并区:", ", ".join(m.get("ref") for m in merges.findall("m:mergeCell", NS)))
        rows = root.findall("m:sheetData/m:row", NS)
        print("行数:", len(rows))
        for row in rows[:max_rows]:
            cells = []
            for c in row.findall("m:c", NS):
                ref = c.get("r")
                t = c.get("t")
                s = c.get("s")
                v = c.find("m:v", NS)
                isel = c.find("m:is", NS)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr" and isel is not None:
                    val = "".join(x.text or "" for x in isel.iter("{%s}t" % NS["m"]))
                else:
                    val = v.text if v is not None else ""
                if val == "" and not show_style:
                    continue
                extra = ""
                if show_style and s is not None:
                    xf = styles["xfs"][int(s)] if int(s) < len(styles["xfs"]) else {}
                    f = styles["fonts"][xf.get("font", 0)] if xf else {}
                    fill = styles["fills"][xf.get("fill", 0)] if xf and xf.get("fill", 0) < len(styles["fills"]) else ""
                    bd = styles["borders"][xf.get("border", 0)] if xf and xf.get("border", 0) < len(styles["borders"]) else ""
                    extra = " [s=%s bold=%s fill=%s border=%s]" % (s, f.get("bold"), fill, bd)
                cells.append("%s=%s%s" % (ref, val, extra))
            if cells:
                print("  ", " | ".join(cells))


if __name__ == "__main__":
    args = sys.argv[1:]
    path = args[0]
    sheet = None
    max_rows = 40
    show = False
    out_path = None
    i = 1
    while i < len(args):
        if args[i] == "--sheet":
            i += 1; sheet = args[i]
        elif args[i] == "--max-rows":
            i += 1; max_rows = int(args[i])
        elif args[i] == "--style":
            show = True
        elif args[i] == "--out":
            i += 1; out_path = args[i]
        i += 1
    if out_path:
        import io
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            dump(path, sheet, max_rows, show)
        finally:
            sys.stdout = old_stdout
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(buf.getvalue())
        print("written:", out_path)
    else:
        dump(path, sheet, max_rows, show)

