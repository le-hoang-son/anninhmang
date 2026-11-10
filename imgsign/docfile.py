"""Bao ve tai lieu .docx/.pdf (FR-21, FR-22).

- PNG: xu ly nhu cu (watermark hien + watermark an LSB) - khong thuoc module nay.
- DOCX: watermark hien bang header (lap lai moi trang) + watermark an metadata.
- PDF : watermark hien bang chen text vao content stream + ky (khong watermark an).

Chi dung thu vien chuan (zipfile, base64, json, re, pathlib, html, zlib).

Watermark an DOCX: chen mot token `IMGSIGN-B64:<base64(JSON)>` vao the <cp:keywords>
cua docProps/core.xml. Nguoi dung binh thuong khong thay; mo Properties cua Word moi thay.
Sau khi chen xong moi KY file cuoi cung (dung bat bien: ky luon la buoc cuoi).
"""

from __future__ import annotations

import base64
import html
import json
import re
import zlib
import zipfile
from pathlib import Path

DOC_EXTENSIONS = (".docx", ".pdf")
SUPPORTED_EXTENSIONS = (".png", ".docx", ".pdf")

_CORE_PART = "docProps/core.xml"
_CORE_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_MARK_PREFIX = "IMGSIGN-B64:"
_TOKEN_RE = re.compile(r"IMGSIGN-B64:([A-Za-z0-9+/]+={0,2})")


def detect_kind(path: Path) -> str:
    """Tra ve 'png' | 'docx' | 'pdf' theo duoi file. Nem ValueError neu khong ho tro."""
    ext = Path(path).suffix.lower()
    if ext == ".png":
        return "png"
    if ext == ".docx":
        return "docx"
    if ext == ".pdf":
        return "pdf"
    raise ValueError(
        f"Chỉ hỗ trợ PNG, DOCX, PDF. File '{Path(path).name}' có đuôi "
        f"{ext or '(không có)'} nên bị từ chối."
    )


def validate_docx(path: Path) -> None:
    """Kiem tra file la DOCX hop le (la ZIP co cau truc OOXML)."""
    path = Path(path)
    if not zipfile.is_zipfile(path):
        raise ValueError(f"File '{path.name}' không phải DOCX hợp lệ (không phải file ZIP).")
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
    except (zipfile.BadZipFile, OSError):
        raise ValueError(f"File '{path.name}' không đọc được như DOCX.")
    if "[Content_Types].xml" not in names or not any(n.startswith("word/") for n in names):
        raise ValueError(f"File '{path.name}' không phải DOCX hợp lệ (thiếu cấu trúc OOXML).")


def validate_pdf(path: Path) -> None:
    """Kiem tra file la PDF hop le (header %PDF- trong 1024 byte dau)."""
    path = Path(path)
    try:
        head = path.read_bytes()[:1024]
    except OSError:
        raise ValueError(f"File '{path.name}' không đọc được.")
    if b"%PDF-" not in head:
        raise ValueError(f"File '{path.name}' không phải PDF hợp lệ.")


def _core_prefix(xml_text: str) -> str:
    """Tim tien to namespace cua core-properties (thuong la 'cp')."""
    m = re.search(r'xmlns:([A-Za-z0-9_]+)="' + re.escape(_CORE_NS) + r'"', xml_text)
    return m.group(1) if m else "cp"


def _keyword_token(payload: dict) -> str:
    """Token watermark: tien to + base64(JSON). Base64 khong chua ky tu XML dac biet."""
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return _MARK_PREFIX + base64.b64encode(body).decode("ascii")


def _inject_token(xml_text: str, token: str) -> str:
    """Chen token vao the keywords (giu keywords cu cua nguoi dung, khong xoa)."""
    prefix = _core_prefix(xml_text)
    open_tag, close_tag = f"<{prefix}:keywords>", f"</{prefix}:keywords>"

    if open_tag in xml_text and close_tag in xml_text:
        start = xml_text.index(open_tag) + len(open_tag)
        end = xml_text.index(close_tag, start)
        old = xml_text[start:end]
        kept = " ".join(p for p in old.split() if not p.startswith(_MARK_PREFIX))
        new_value = (kept + " " + token).strip()
        return xml_text[:start] + new_value + xml_text[end:]

    root_close = f"</{prefix}:coreProperties>"
    if root_close not in xml_text:
        raise ValueError("File DOCX sai định dạng: thiếu thẻ coreProperties.")
    return xml_text.replace(root_close, f"{open_tag}{token}{close_tag}{root_close}", 1)


def embed_docx_metadata(src: Path, dst: Path, payload: dict) -> Path:
    """Ghi watermark an (metadata) vao DOCX, luu ra dst. Nem ValueError neu that bai."""
    src, dst = Path(src), Path(dst)
    validate_docx(src)
    token = _keyword_token(payload)

    try:
        with zipfile.ZipFile(src, "r") as zin:
            names = zin.namelist()
            parts = {n: zin.read(n) for n in names}
    except (zipfile.BadZipFile, OSError):
        raise ValueError(f"File '{src.name}' không đọc được như DOCX.")

    if _CORE_PART not in parts:
        raise ValueError(
            f"File '{src.name}' thiếu '{_CORE_PART}' nên không thể giấu watermark ẩn."
        )

    try:
        xml_text = parts[_CORE_PART].decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"File '{src.name}' có '{_CORE_PART}' sai định dạng.")

    parts[_CORE_PART] = _inject_token(xml_text, token).encode("utf-8")

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for n in names:
                zout.writestr(n, parts[n])
    except OSError:
        raise ValueError(f"Không ghi được file DOCX đầu ra '{dst.name}'.")

    if extract_docx_metadata(dst) is None:
        raise ValueError("Không ghi được watermark ẩn vào DOCX.")
    return dst


def find_signed(signed_dir: Path, asset_id: str) -> Path | None:
    """Tim file da ky cua mot asset trong signed_dir (.png/.docx/.pdf). None neu khong co."""
    signed_dir = Path(signed_dir)
    for ext in SUPPORTED_EXTENSIONS:
        candidate = signed_dir / f"{asset_id}{ext}"
        if candidate.exists():
            return candidate
    return None


def extract_docx_metadata(path: Path) -> dict | None:
    """Doc watermark an tu DOCX. Tra None neu khong co/sai dinh dang."""
    path = Path(path)
    if not zipfile.is_zipfile(path):
        return None
    try:
        with zipfile.ZipFile(path) as z:
            if _CORE_PART not in z.namelist():
                return None
            xml_text = z.read(_CORE_PART).decode("utf-8", errors="ignore")
    except (zipfile.BadZipFile, OSError, KeyError):
        return None

    m = _TOKEN_RE.search(xml_text)
    if m is None:
        return None
    try:
        raw = base64.b64decode(m.group(1), validate=True)
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Watermark HIEN cho DOCX (header lap lai moi trang)
# ---------------------------------------------------------------------------

_DOC_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_HEADER_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
)
_HEADER_CT = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"
)


def _max_rid(rels_xml: str) -> int:
    """Tim so rId lon nhat trong file rels."""
    nums = [int(m) for m in re.findall(r'Id="rId(\d+)"', rels_xml)]
    return max(nums, default=0)


def embed_docx_visible_watermark(src: Path, dst: Path, text: str) -> Path:
    """Chen watermark hien vao DOCX bang header (lap lai moi trang).

    Header co text mau xam nhat (BFBFBF), nghieng, canh giua. Khong sua noi dung
    body cua nguoi dung. Tra ve dst. Nem ValueError neu that bai.
    """
    src, dst = Path(src), Path(dst)
    validate_docx(src)
    if not text:
        raise ValueError("Text watermark không được rỗng.")

    try:
        with zipfile.ZipFile(src) as zin:
            names = zin.namelist()
            parts = {n: zin.read(n) for n in names}
    except (zipfile.BadZipFile, OSError):
        raise ValueError(f"File '{src.name}' không đọc được như DOCX.")

    doc_path = "word/document.xml"
    if doc_path not in parts:
        raise ValueError(f"File '{src.name}' thiếu '{doc_path}'.")

    doc_xml = parts[doc_path].decode("utf-8")

    # Dam bao co namespace r trong document
    if "xmlns:r=" not in doc_xml:
        doc_xml = doc_xml.replace(
            "<w:document",
            f'<w:document xmlns:r="{_REL_NS}"',
            1,
        )

    # Tim ten header chua dung
    i = 1
    while f"word/header{i}.xml" in parts:
        i += 1
    header_name = f"header{i}.xml"
    header_part = f"word/{header_name}"

    # Tao noi dung header
    safe = html.escape(text)
    header_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:hdr xmlns:w="{_DOC_NS}">'
        "<w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr>"
        f'<w:r><w:rPr><w:color w:val="BFBFBF"/><w:i/><w:sz w:val="24"/>'
        f'<w:szCs w:val="24"/></w:rPr><w:t xml:space="preserve">{safe}</w:t></w:r>'
        "</w:p></w:hdr>"
    )

    # Cap nhat rels
    rels_path = "word/_rels/document.xml.rels"
    if rels_path in parts:
        rels_xml = parts[rels_path].decode("utf-8")
    else:
        rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            "</Relationships>"
        )
    rid = _max_rid(rels_xml) + 1
    new_rel = (
        f'<Relationship Id="rId{rid}" Type="{_HEADER_TYPE}" Target="{header_name}"/>'
    )
    if "</Relationships>" not in rels_xml:
        raise ValueError("File rels DOCX sai định dạng.")
    rels_xml = rels_xml.replace("</Relationships>", new_rel + "</Relationships>", 1)

    # Chen headerReference vao sectPr
    header_ref = f'<w:headerReference w:type="default" r:id="rId{rid}"/>'
    sectpr_close = "</w:sectPr>"
    if sectpr_close in doc_xml:
        doc_xml = doc_xml.replace(sectpr_close, header_ref + sectpr_close, 1)
    else:
        # fallback: chen truoc </w:body>
        body_close = "</w:body>"
        if body_close not in doc_xml:
            raise ValueError("DOCX thiếu </w:body>.")
        doc_xml = doc_xml.replace(
            body_close, f"<w:sectPr>{header_ref}</w:sectPr>{body_close}", 1
        )

    # Cap nhat Content_Types
    ct_path = "[Content_Types].xml"
    ct_xml = parts[ct_path].decode("utf-8")
    override = f'<Override PartName="/{header_part}" ContentType="{_HEADER_CT}"/>'
    ct_xml = ct_xml.replace("</Types>", override + "</Types>", 1)

    parts[doc_path] = doc_xml.encode("utf-8")
    parts[rels_path] = rels_xml.encode("utf-8")
    parts[ct_path] = ct_xml.encode("utf-8")
    parts[header_part] = header_xml.encode("utf-8")
    new_names = list(names) + ([header_part] if header_part not in names else [])

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for n in new_names:
                zout.writestr(n, parts[n])
    except OSError:
        raise ValueError(f"Không ghi được file DOCX đầu ra '{dst.name}'.")
    return dst


# ---------------------------------------------------------------------------
# Watermark HIEN cho PDF (chen text vao content stream cua moi trang)
# ---------------------------------------------------------------------------

_OBJ_RE = re.compile(rb"(\d+)\s+\d+\s+obj(.*?)endobj", re.DOTALL)


def _pdf_dict(body: bytes) -> bytes:
    """Lay dict <<...>> trong than object (truoc stream)."""
    start = body.find(b"<<")
    if start < 0:
        return b""
    depth = 0
    i = start
    while i < len(body):
        if body[i : i + 2] == b"<<":
            depth += 1
            i += 2
        elif body[i : i + 2] == b">>":
            depth -= 1
            if depth == 0:
                return body[start : i + 2]
            i += 2
        else:
            i += 1
    return b""


def _pdf_get(d: bytes, key: bytes) -> bytes | None:
    """Lay gia tri cua /key trong dict PDF d (bat dau = <<). Tra None neu khong co."""
    pos = 0
    while True:
        idx = d.find(key, pos)
        if idx < 0:
            return None
        after = idx + len(key)
        # Kiem tra key ket thuc (khong phai /FontName trung nhau)
        if after < len(d):
            c = d[after : after + 1]
            if c not in (b" ", b"\n", b"\r", b"\t", b"/", b"<", b"(", b"[", b"]", b">>", b""):
                pos = after
                continue
        rest = d[after:].lstrip()
        if rest.startswith(b"<<"):
            return _pdf_dict(rest)
        if rest.startswith(b"["):
            depth = 0
            j = 0
            while j < len(rest):
                if rest[j : j + 1] == b"[":
                    depth += 1
                elif rest[j : j + 1] == b"]":
                    depth -= 1
                    if depth == 0:
                        return rest[: j + 1]
                j += 1
            return rest
        # token (so hoac ten) - co the la ref "N G R"
        j = 0
        while j < len(rest) and rest[j : j + 1] not in (b" ", b"\n", b"\r", b"\t", b">>", b"/"):
            j += 1
        token = rest[:j]
        m = re.match(rb"\s+(\d+)\s+R\b", rest[j:])
        if m:
            return token + b" " + m.group(0).strip()
        return token


def _pdf_ref_num(value: bytes | None) -> int | None:
    """Tra so object tu gia tri 'N 0 R', None neu khong phai ref."""
    if value is None:
        return None
    m = re.match(rb"^\s*(\d+)\s+\d+\s+R\s*$", value)
    return int(m.group(1)) if m else None


def _pdf_stream(body: bytes) -> tuple[bytes, bytes | None]:
    """Tach (dict_bytes, stream_data) tu than object. stream_data = None neu khong co."""
    m = re.search(rb"stream\r?\n(.*?)\r?\nendstream", body, re.DOTALL)
    if m is None:
        return _pdf_dict(body), None
    dict_part = body[: m.start()].strip()
    return dict_part, m.group(1)


def _pdf_first_font(font_dict: bytes, objects: dict[int, bytes]) -> bytes | None:
    """Tim ten font dau tien trong /Font dict (co the la ref)."""
    fd = font_dict
    ref = _pdf_ref_num(fd)
    if ref is not None and ref in objects:
        fd = _pdf_dict(objects[ref])
    if not fd:
        return None
    # /Font dict co dang << /F1 N 0 R /F2 ... >> hoac << /F1 <<...>> ...>>
    m = re.search(rb"/([A-Za-z0-9_]+)\s", fd)
    if m:
        return m.group(1)
    return None


def _page_resources(page_dict: bytes, objects: dict[int, bytes]) -> bytes:
    """Lay /Resources cua trang (co the ke thua tu /Pages)."""
    res = _pdf_get(page_dict, b"/Resources")
    if res is not None and res.startswith(b"<<"):
        return res
    ref = _pdf_ref_num(res)
    if ref is not None and ref in objects:
        d = _pdf_dict(objects[ref])
        if d:
            return d
    # Thu ke thua tu /Pages
    parent = _pdf_ref_num(_pdf_get(page_dict, b"/Parent"))
    seen = set()
    while parent is not None and parent not in seen and parent in objects:
        seen.add(parent)
        pd = _pdf_dict(objects[parent])
        res = _pdf_get(pd, b"/Resources")
        if res is not None:
            if res.startswith(b"<<"):
                return res
            rref = _pdf_ref_num(res)
            if rref is not None and rref in objects:
                d = _pdf_dict(objects[rref])
                if d:
                    return d
        parent = _pdf_ref_num(_pdf_get(pd, b"/Parent"))
    return b""


def _page_content_refs(page_dict: bytes) -> list[int]:
    """Lay danh sach object number cua /Contents (co the la 1 ref hoac array)."""
    contents = _pdf_get(page_dict, b"/Contents")
    if contents is None:
        return []
    refs: list[int] = []
    if contents.startswith(b"["):
        for m in re.finditer(rb"(\d+)\s+\d+\s+R", contents):
            refs.append(int(m.group(1)))
    else:
        n = _pdf_ref_num(contents)
        if n is not None:
            refs.append(n)
    return refs


def embed_pdf_visible_watermark(src: Path, dst: Path, text: str) -> Path:
    """Chen watermark hien (text) vao PDF bang cach them lenh ve text vao
    content stream cua moi trang. Thu tim font trong /Resources; neu khong co
    font thi ve duong cheo lam dau hieu watermark.

    Ham nay co gang giu nguyen cau truc PDF; neu that bai se nem ValueError.
    """
    src, dst = Path(src), Path(dst)
    validate_pdf(src)
    if not text:
        raise ValueError("Text watermark không được rỗng.")

    data = src.read_bytes()
    objects: dict[int, bytes] = {}
    for m in _OBJ_RE.finditer(data):
        objects[int(m.group(1))] = m.group(2)

    if not objects:
        raise ValueError("PDF không có object hợp lệ.")

    # Tim trang: object co /Type /Page (khong phai /Pages)
    page_nums: list[int] = []
    for num, body in objects.items():
        d = _pdf_dict(body)
        typ = _pdf_get(d, b"/Type")
        if typ == b"/Page":
            page_nums.append(num)

    if not page_nums:
        # Khong tim thay trang -> giu nguyen
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        return dst

    # Escape text cho PDF string (dau ngoac va gạch chéo)
    esc = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    modified = 0
    for pnum in page_nums:
        pd = _pdf_dict(objects[pnum])
        media = _pdf_get(pd, b"/MediaBox")
        # Vi tri ve: goc tren-trai, cach mép 40pt
        x_pos, y_pos = "40", "760"
        if media and media.startswith(b"["):
            nums = re.findall(rb"-?\d+(?:\.\d+)?", media)
            if len(nums) >= 4:
                try:
                    top = float(nums[3])
                    y_pos = f"{max(40.0, top - 40):.0f}"
                except ValueError:
                    pass

        res = _page_resources(pd, objects)
        font_name: bytes | None = None
        if res:
            font_dict = _pdf_get(res, b"/Font")
            if font_dict is not None:
                font_name = _pdf_first_font(font_dict, objects)

        if font_name:
            wm_cmd = (
                f"BT /{font_name.decode('latin-1')} 26 Tf {x_pos} {y_pos} Td "
                f"0.45 g ({esc}) Tj ET\n".encode("latin-1")
            )
        else:
            # Khong co font -> ve 3 duong cheo lam dau hieu watermark
            wm_cmd = (
                b"q 0.4 G 0.6 w 0 700 m 200 760 l S 40 680 m 240 740 l S "
                b"80 660 m 280 720 l S Q\n"
            )

        for cnum in _page_content_refs(pd):
            if cnum not in objects:
                continue
            body = objects[cnum]
            d, stream = _pdf_stream(body)
            if stream is None:
                continue
            # Giai nen neu can
            filt = _pdf_get(d, b"/Filter")
            compressed = filt in (b"/FlateDecode", b"FlateDecode")
            if compressed:
                try:
                    raw = zlib.decompress(stream)
                except zlib.error:
                    raw = stream
                    compressed = False
            else:
                raw = stream
            new_raw = wm_cmd + raw
            if compressed:
                new_stream = zlib.compress(new_raw)
            else:
                new_stream = new_raw
            # Cap nhat /Length
            new_len = str(len(new_stream)).encode("ascii")
            if b"/Length" in d:
                d = re.sub(rb"/Length\s+\d+", b"/Length " + new_len, d, count=1)
            else:
                d = d.rstrip(b">>") + b" /Length " + new_len + b" >>"
            # Ghi lai object body
            objects[cnum] = d + b"\nstream\n" + new_stream + b"\nendstream"
            modified += 1

    if modified == 0:
        # Khong sua duoc content stream nao -> giu nguyen
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        return dst

    # Xay lai PDF: ghi lai header + objects theo so thu tu + xref + trailer
    out = bytearray()
    header_end = data.find(b"obj")
    header_end = data.rfind(b"\n", 0, header_end)
    out.extend(data[: header_end + 1])

    offsets: dict[int, int] = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out.extend(f"{num} 0 obj".encode("ascii"))
        out.extend(objects[num])
        out.extend(b"endobj\n")

    xref_pos = len(out)
    max_num = max(objects)
    out.extend(f"xref\n0 {max_num + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for num in range(1, max_num + 1):
        if num in offsets:
            out.extend(f"{offsets[num]:010d} 00000 n \n".encode("ascii"))
        else:
            out.extend(b"0000000000 65535 f \n")

    # Trailer: tim trailer cu va giu /Size /Root /Info
    trailer_m = re.search(rb"trailer\s*(<<.*?>>)", data, re.DOTALL)
    trailer_dict = trailer_m.group(1) if trailer_m else b"<< /Size 0 >>"
    trailer_dict = re.sub(rb"/Size\s+\d+", f"/Size {max_num + 1}".encode("ascii"), trailer_dict)
    out.extend(b"trailer\n")
    out.extend(trailer_dict)
    out.extend(b"\nstartxref\n")
    out.extend(str(xref_pos).encode("ascii"))
    out.extend(b"\n%%EOF")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(bytes(out))

    # Kiem tra lai PDF con hop le
    validate_pdf(dst)
    return dst
