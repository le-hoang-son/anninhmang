"""Giao dien web Flask cho ImgSign (FR-11).

Ap dung quy tac an toan (AGENTS.md muc 5):
- MAX_CONTENT_LENGTH = 10 MB
- secure_filename + luu file bang uuid4
- kiem tra PNG hop le bang Pillow (khong chi nhin duoi)
- debug=False mac dinh
- khong route nao nhan duong dan tuy y tu nguoi dung (chong path traversal)
"""

from __future__ import annotations

import csv
import io
import re
import sys
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    flash,
    render_template,
    request,
    send_file,
)
from werkzeug.utils import secure_filename

# Cho phep chay 'python web/app.py' tu thu muc goc du an
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.stdout.reconfigure(encoding="utf-8")

import config
from imgsign import assets as assets_mod
from imgsign import compare as compare_mod
from imgsign import docfile
from imgsign import keys as keys_mod
from imgsign import logger as logger_mod
from imgsign import lsb as lsb_mod
from imgsign import notifier
from imgsign import pipeline
from imgsign import recover as recover_mod
from imgsign import tamper as tamper_mod

UPLOADS_DIR = config.DATA_DIR / "uploads"
COMPARE_DIR = config.DATA_DIR / "compare"
RECOVERED_DIR = config.DATA_DIR / "recovered"
ASSET_ID_RE = re.compile(r"^IMG-\d{4}$")
TAMPER_MODE_RE = re.compile(r"^(text|crop|pixel)$")
# Duoi file duoc phep upload (chong dat ten la); chi lay phan duoi, khong dung ten goc lam duong dan
_ALLOWED_EXT = (".png", ".docx", ".pdf")
_DOC_MIME = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
}

# Ten file duoc phep phuc vu theo tung loai thu muc (chong path traversal)
_MEDIA_ALLOW = {
    "signed": re.compile(r"^IMG-\d{4}\.png$"),
    "original": re.compile(r"^IMG-\d{4}\.png$"),
    "tampered": re.compile(r"^IMG-\d{4}_(text|crop|pixel)\.png$"),
    "compare": re.compile(r"^[0-9a-f]{32}(_mark)?\.png$"),
}
_MEDIA_DIR = {
    "signed": config.SIGNED_DIR,
    "original": config.ORIGINALS_DIR,
    "tampered": config.TAMPERED_DIR,
    "compare": COMPARE_DIR,
}

VERDICT_LABEL = {
    "HOP_LE": "HỢP LỆ",
    "HOP_LE_CANH_BAO": "HỢP LỆ (CẢNH BÁO)",
    "KHONG_HOP_LE": "KHÔNG HỢP LỆ",
    "KHONG_XAC_MINH_DUOC": "KHÔNG XÁC MINH ĐƯỢC",
}
VERDICT_CLASS = {
    "HOP_LE": "ok",
    "HOP_LE_CANH_BAO": "warn",
    "KHONG_HOP_LE": "bad",
    "KHONG_XAC_MINH_DUOC": "warn",
}

# Nhan va mau cho cac su kien log (dung o bang dieu khien "5 su kien gan nhat").
EVENT_LABEL = {
    "BAO_VE": "ĐÃ BẢO VỆ",
    "RECOVER": "KHÔI PHỤC",
    "ALERT": "CẢNH BÁO",
    **VERDICT_LABEL,
}
EVENT_CLASS = {
    "BAO_VE": "ok",
    "RECOVER": "ok",
    "ALERT": "bad",
    **VERDICT_CLASS,
}

# Cau hinh trang nhat ky /logs (FR-18)
LOG_PAGE_SIZE = 50
LOG_VERDICTS = [
    "BAO_VE",
    "HOP_LE",
    "HOP_LE_CANH_BAO",
    "KHONG_HOP_LE",
    "KHONG_XAC_MINH_DUOC",
    "RECOVER",
    "ALERT",
]

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
# Khoa phien: doc tu bien moi truong IMGSIGN_SECRET_KEY, khong co thi sinh ngau nhien moi lan khoi dong.
app.secret_key = config.SECRET_KEY

# --- Gioi han tan suat POST trong bo nho (theo IP) ---
_REQ_HITS: dict[str, deque[float]] = {}


def reset_rate_limit() -> None:
    """Xoa bo dem gioi han tan suat (dung cho kiem thu)."""
    _REQ_HITS.clear()


@app.before_request
def _rate_limit():
    """Chan lam dung: toi da config.RATE_LIMIT_MAX lan POST moi IP trong RATE_LIMIT_WINDOW giay."""
    if request.method != "POST":
        return None

    ip = request.remote_addr or "unknown"
    now_ts = time.monotonic()
    bucket = _REQ_HITS.setdefault(ip, deque())

    # Bo cac lan goi da qua cua so thoi gian
    while bucket and now_ts - bucket[0] > config.RATE_LIMIT_WINDOW:
        bucket.popleft()

    if len(bucket) >= config.RATE_LIMIT_MAX:
        abort(429)

    bucket.append(now_ts)
    return None


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_ext(filename: str) -> str:
    """Lay duoi file an toan tu ten goc; chi cho phep .png/.docx/.pdf, mac dinh .png."""
    ext = Path(secure_filename(filename or "")).suffix.lower()
    return ext if ext in _ALLOWED_EXT else ".png"


def _save_upload(file_storage, forced_ext: str = ".png") -> Path:
    """Luu file upload voi ten uuid4 (khong dung ten goc lam duong dan)."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    secure_filename(file_storage.filename or "")  # chuan hoa ten goc (khong dung lam path)
    dst = UPLOADS_DIR / f"{uuid.uuid4().hex}{forced_ext}"
    file_storage.save(dst)
    return dst


def _sidecar_for_asset(asset_id: str) -> Path | None:
    """Tim sidecar cua asset trong data/signed/ (ho tro .png/.docx/.pdf)."""
    signed = docfile.find_signed(config.SIGNED_DIR, asset_id)
    if signed is None:
        return None
    sidecar = Path(str(signed) + ".sig.json")
    return sidecar if sidecar.exists() else None


# Nhan phuong phap watermark an theo dinh dang (hien thi cho nguoi dung)
WM_METHOD = {
    "png": "LSB trong điểm ảnh",
    "docx": "metadata DOCX (docProps/core.xml)",
    "pdf": "không có (PDF chỉ ký)",
}


def _read_hidden_watermark(signed_path: Path, kind: str) -> dict | None:
    """Doc lai watermark an tu file da ky (PNG: LSB, DOCX: metadata, PDF: khong co)."""
    if kind == "png":
        try:
            return lsb_mod.extract(signed_path)
        except (ValueError, OSError):
            return None
    if kind == "docx":
        return docfile.extract_docx_metadata(signed_path)
    return None


def _recent_events(limit: int = 5) -> list[dict]:
    """Phan tich `limit` su kien log moi nhat thanh dict co mau de hien thi."""
    events: list[dict] = []
    for line in logger_mod.read_log_lines()[-limit:][::-1]:
        parsed = logger_mod.parse_line(line)
        if parsed is None:
            continue
        ts, file_name, verdict, detail = parsed
        events.append(
            {
                "time": ts,
                "file": file_name,
                "verdict": verdict,
                "label": EVENT_LABEL.get(verdict, verdict),
                "cls": EVENT_CLASS.get(verdict, "warn"),
                "detail": detail,
            }
        )
    return events


@app.route("/")
def index() -> str:
    """FR-15: bang dieu khien voi the so lieu, bieu do cot va 5 su kien gan nhat."""
    stats = logger_mod.summarize()
    asset_count = len(assets_mod.list_assets())
    valid = stats["total_hop_le"]
    invalid = stats["khong_hop_le"]
    peak = max(valid, invalid, 1)
    chart = [
        {"label": "Hợp lệ", "value": valid, "cls": "ok", "pct": round(valid / peak * 100)},
        {"label": "Không hợp lệ", "value": invalid, "cls": "bad", "pct": round(invalid / peak * 100)},
    ]
    return render_template(
        "index.html",
        now=_now(),
        asset_count=asset_count,
        total_verify=stats["total_verify"],
        valid=valid,
        invalid=invalid,
        chart=chart,
        events=_recent_events(5),
    )


@app.route("/protect", methods=["GET", "POST"])
def protect() -> str:
    if request.method == "GET":
        return render_template("protect.html", now=_now(), result=None)

    name = (request.form.get("name") or "").strip()
    asset_type = (request.form.get("type") or "").strip()
    importance_raw = request.form.get("importance") or ""
    # Checkbox watermark hien: chi gui gia tri neu duoc tick
    visible_watermark = request.form.get("visible_watermark") is not None
    upload = request.files.get("png")

    if not name or not asset_type:
        flash("Vui lòng nhập tên tài sản và loại ảnh.")
        return render_template("protect.html", now=_now(), result=None), 400
    if importance_raw not in ("1", "2", "3"):
        flash("Mức quan trọng phải là 1, 2 hoặc 3.")
        return render_template("protect.html", now=_now(), result=None), 400
    if upload is None or not upload.filename:
        flash("Vui lòng chọn một file PNG, DOCX hoặc PDF.")
        return render_template("protect.html", now=_now(), result=None), 400

    tmp = _save_upload(upload, forced_ext=_safe_ext(upload.filename))
    try:
        result = pipeline.protect(
            tmp, name, asset_type, int(importance_raw),
            visible_watermark=visible_watermark,
        )
    except ValueError as exc:
        flash(str(exc))
        return render_template("protect.html", now=_now(), result=None), 400
    finally:
        tmp.unlink(missing_ok=True)

    return render_template(
        "protect.html",
        now=_now(),
        result={
            "asset_id": result.asset_id,
            "kind": result.kind,
            "signed_name": result.signed_path.name,
            "original_name": result.original_path.name,
            "sha256": result.sha256_signed,
            "wm_method": WM_METHOD.get(result.kind, ""),
            "wm": _read_hidden_watermark(result.signed_path, result.kind),
            "visible_watermark": result.visible_watermark,
        },
    )


@app.route("/verify", methods=["GET", "POST"])
def verify() -> str:
    if request.method == "GET":
        return render_template("verify.html", now=_now(), report=None)

    upload = request.files.get("png")
    if upload is None or not upload.filename:
        flash("Vui lòng chọn một file PNG, DOCX hoặc PDF.")
        return render_template("verify.html", now=_now(), report=None), 400

    tmp = _save_upload(upload, forced_ext=_safe_ext(upload.filename))
    sidecar_path: Path | None = None
    sidecar_file = request.files.get("sig")
    if sidecar_file is not None and sidecar_file.filename:
        sidecar_path = _save_upload(sidecar_file, forced_ext=".sig.json")

    try:
        # Neu nguoi dung khong nop sidecar: tim theo asset_id doc tu watermark an.
        # PNG: doc tu LSB. DOCX: doc tu metadata. PDF: khong co watermark nen phai nop sidecar.
        if sidecar_path is None:
            ext = tmp.suffix.lower()
            payload = None
            if ext == ".docx":
                payload = docfile.extract_docx_metadata(tmp)
            elif ext == ".png":
                payload = lsb_mod.extract(tmp)
            if payload and ASSET_ID_RE.match(str(payload.get("asset_id", ""))):
                sidecar_path = _sidecar_for_asset(str(payload["asset_id"]))

        report = pipeline.verify_full(tmp, sidecar_path)
        sidecar = report.sig.sidecar or {}
        kind = tmp.suffix.lower().lstrip(".")
        context = {
            "verdict": report.verdict,
            "label": VERDICT_LABEL.get(report.verdict, report.verdict),
            "cls": VERDICT_CLASS.get(report.verdict, "warn"),
            "reason": report.sig.reason,
            "sha256": report.sig.sha256,
            "kind": kind,
            "wm_method": WM_METHOD.get(kind, ""),
            "wm": report.lsb_payload,
            "lsb_ok": report.lsb_payload is not None,
            "lsb_payload": report.lsb_payload,
            "notes": report.notes,
            "sidecar_missing": report.sig.sidecar is None,
            "asset_id": sidecar.get("asset_id"),
            "owner": sidecar.get("owner"),
            "key_fingerprint": sidecar.get("key_fingerprint"),
            "signed_at": sidecar.get("signed_at"),
            "file_name": upload.filename,
        }
    finally:
        tmp.unlink(missing_ok=True)
        if sidecar_path is not None and sidecar_path.exists() and sidecar_path.parent == UPLOADS_DIR:
            sidecar_path.unlink(missing_ok=True)

    return render_template("verify.html", now=_now(), report=context)


@app.route("/verify-batch", methods=["GET", "POST"])
def verify_batch():
    """FR-16: xac minh nhieu anh cung luc, chi gui mot canh bao tom tat cho ca lo."""
    if request.method == "GET":
        return render_template(
            "verify_batch.html", now=_now(), rows=None, summary=None, batch_max=config.BATCH_MAX
        )

    files = [f for f in request.files.getlist("pngs") if f and f.filename]
    if not files:
        flash("Vui lòng chọn ít nhất một ảnh PNG.")
        return render_template(
            "verify_batch.html", now=_now(), rows=None, summary=None, batch_max=config.BATCH_MAX
        ), 400
    if len(files) > config.BATCH_MAX:
        flash(f"Tối đa {config.BATCH_MAX} ảnh mỗi lần xác minh theo lô.")
        return render_template(
            "verify_batch.html", now=_now(), rows=None, summary=None, batch_max=config.BATCH_MAX
        ), 400

    rows: list[dict] = []
    fakes: list[str] = []
    for upload in files:
        tmp = _save_upload(upload)
        try:
            pipeline.validate_png(tmp)
            # Tim sidecar theo asset_id doc tu LSB giong nhu /verify
            sidecar_path: Path | None = None
            payload = lsb_mod.extract(tmp)
            if payload and ASSET_ID_RE.match(str(payload.get("asset_id", ""))):
                sidecar_path = _sidecar_for_asset(str(payload["asset_id"]))
            # send_alert=False: khong gui ntfy tung anh, chi gui mot thong bao tom tat sau
            report = pipeline.verify_full(tmp, sidecar_path, send_alert=False)
            verdict = report.verdict
            reason = "; ".join(report.notes) or report.sig.reason
        except ValueError as exc:
            verdict = "KHONG_XAC_MINH_DUOC"
            reason = str(exc)
        finally:
            tmp.unlink(missing_ok=True)

        if verdict == "KHONG_HOP_LE":
            fakes.append(upload.filename)
        rows.append(
            {
                "file": upload.filename,
                "label": VERDICT_LABEL.get(verdict, verdict),
                "cls": VERDICT_CLASS.get(verdict, "warn"),
                "reason": reason,
            }
        )

    # Chi gui MOT thong bao tom tat cho ca lo neu co anh gia.
    summary = {"total": len(files), "fake_count": len(fakes), "sent": False}
    if fakes:
        sent = notifier.send_alert(
            "[RESPOND] Phat hien anh gia (lo)",
            f"Lo {len(files)} anh co {len(fakes)} anh KHONG HOP LE: {', '.join(fakes)}.",
        )
        logger_mod.log_verify(
            "batch", "ALERT", f"lo {len(files)} anh; so_anh_gia={len(fakes)}; thanh_cong={sent}"
        )
        summary["sent"] = sent

    return render_template(
        "verify_batch.html", now=_now(), rows=rows, summary=summary, batch_max=config.BATCH_MAX
    )


@app.route("/assets")
def assets() -> str:
    rows = assets_mod.list_assets()
    return render_template("assets.html", now=_now(), rows=rows)


@app.route("/assets/<asset_id>", methods=["GET", "POST"])
def asset_detail(asset_id: str):
    """FR-14: chi tiet mot tai san, lich su xac minh rieng va nut khoi phuc."""
    if not ASSET_ID_RE.match(asset_id):
        abort(404)

    asset = assets_mod.get_asset(asset_id)
    signed = docfile.find_signed(config.SIGNED_DIR, asset_id)
    signed_name = signed.name if signed is not None else ""
    signed_kind = signed.suffix.lower().lstrip(".") if signed is not None else ""
    if asset is None and signed is None:
        abort(404)

    if request.method == "POST":
        try:
            dst = RECOVERED_DIR / signed_name
            result = recover_mod.recover(asset_id, dst)
            ket_luan = "HỢP LỆ" if result.valid else "KHÔNG HỢP LỆ"
            flash(f"Đã khôi phục {asset_id}. Xác minh lại: {ket_luan} — {result.reason}")
        except (FileNotFoundError, OSError) as exc:
            flash(str(exc))

    history = [ln for ln in logger_mod.read_log_lines() if asset_id in ln]
    wm = _read_hidden_watermark(signed, signed_kind) if signed is not None else None
    return render_template(
        "asset_detail.html",
        now=_now(),
        asset=asset,
        asset_id=asset_id,
        signed_name=signed_name,
        signed_exists=signed is not None,
        signed_kind=signed_kind,
        wm_method=WM_METHOD.get(signed_kind, ""),
        wm=wm,
        history=history[-50:][::-1],
    )


@app.route("/compare", methods=["GET", "POST"])
def compare():
    """FR-12: so sanh anh nghi gia voi ban da ky bang ImageChops.difference."""
    signed_files = sorted(config.SIGNED_DIR.glob("IMG-*.png")) if config.SIGNED_DIR.exists() else []
    asset_ids = [p.stem for p in signed_files if ASSET_ID_RE.match(p.stem)]

    if request.method == "GET":
        return render_template("compare.html", now=_now(), asset_ids=asset_ids, result=None)

    asset_id = (request.form.get("asset_id") or "").strip()
    upload = request.files.get("png")

    if not ASSET_ID_RE.match(asset_id):
        flash("asset_id không hợp lệ (phải có dạng IMG-0001).")
        return render_template("compare.html", now=_now(), asset_ids=asset_ids, result=None), 400
    if upload is None or not upload.filename:
        flash("Vui lòng chọn ảnh PNG nghi giả.")
        return render_template("compare.html", now=_now(), asset_ids=asset_ids, result=None), 400

    ref_path = config.SIGNED_DIR / f"{asset_id}.png"
    if not ref_path.exists():
        flash(f"Không tìm thấy bản đã ký cho asset '{asset_id}'.")
        return render_template("compare.html", now=_now(), asset_ids=asset_ids, result=None), 404

    tmp = _save_upload(upload)
    try:
        pipeline.validate_png(tmp)  # kiem PNG hop le bang Pillow
        cmp = compare_mod.compare_images(ref_path, tmp, COMPARE_DIR)
    except ValueError as exc:
        flash(str(exc))
        return render_template("compare.html", now=_now(), asset_ids=asset_ids, result=None), 400
    finally:
        tmp.unlink(missing_ok=True)

    return render_template(
        "compare.html",
        now=_now(),
        asset_ids=asset_ids,
        result={
            "asset_id": asset_id,
            "ref_name": f"{asset_id}.png",
            "suspect_name": cmp.suspect_name,
            "annotated_name": cmp.annotated_name,
            "ref_size": cmp.ref_size,
            "suspect_size": cmp.suspect_size,
            "same_size": cmp.same_size,
            "diff_pixels": cmp.diff_pixels,
            "total_pixels": cmp.total_pixels,
            "percent": f"{cmp.percent:.4f}",
            "box_count": cmp.box_count,
        },
    )


@app.route("/nist")
def nist() -> str:
    """FR-13: bang 5 o NIST CSF 1.1 kem so lieu thuc te."""
    stats = logger_mod.summarize()
    assets_count = len(assets_mod.list_assets())
    signed_count = (
        len(list(config.SIGNED_DIR.glob("IMG-*.png"))) if config.SIGNED_DIR.exists() else 0
    )

    cards = [
        {
            "name": "Identify",
            "cls": "identify",
            "cats": "ID.AM, ID.RA",
            "does": "Đăng ký tài sản ảnh (tên, loại, mức quan trọng); mức quan trọng dùng để đánh giá rủi ro.",
            "metrics": [("Số tài sản đã đăng ký", assets_count)],
        },
        {
            "name": "Protect",
            "cls": "protect",
            "cats": "PR.DS, PR.AC, PR.IP",
            "does": "Chữ ký số RSA-PSS bảo vệ toàn vẹn; watermark hiện và ẩn bảo vệ nguồn gốc; quy trình 4 bước cố định.",
            "metrics": [("Số ảnh đã ký", signed_count), ("Số lần bảo vệ", stats["bao_ve"])],
        },
        {
            "name": "Detect",
            "cls": "detect",
            "cats": "DE.CM, DE.AE",
            "does": "Xác minh chữ ký và watermark ẩn mỗi ảnh; phân loại 4 kết luận, phát hiện cả sửa 1 điểm ảnh.",
            "metrics": [
                ("Số lần xác minh", stats["total_verify"]),
                ("Hợp lệ", stats["total_hop_le"]),
                ("Không hợp lệ", stats["khong_hop_le"]),
                ("Không xác minh được", stats["khong_xac_minh"]),
            ],
        },
        {
            "name": "Respond",
            "cls": "respond",
            "cats": "RS.AN, RS.CO",
            "does": "Ghi log mỗi lần xác minh; gửi cảnh báo ntfy khi phát hiện ảnh giả.",
            "metrics": [
                ("Cảnh báo đã gửi", stats["alerts_sent"]),
                ("Cảnh báo thất bại", stats["alerts_failed"]),
                ("Số lần phát hiện giả", stats["khong_hop_le"]),
            ],
        },
        {
            "name": "Recover",
            "cls": "recover",
            "cats": "RC.RP",
            "does": "Lưu bản gốc khi bảo vệ; khôi phục bản đã ký và xác minh lại.",
            "metrics": [("Số lần khôi phục", stats["recovers"])],
        },
    ]
    return render_template("nist.html", now=_now(), cards=cards, stats=stats)


def _filtered_log_rows(verdict: str, query: str) -> list[tuple[str, str, str, str]]:
    """Loc log theo ket luan va ten file, tra ve moi nhat truoc."""
    rows: list[tuple[str, str, str, str]] = []
    for line in logger_mod.read_log_lines():
        parsed = logger_mod.parse_line(line)
        if parsed is None:
            continue
        _, file_name, line_verdict, _ = parsed
        if verdict and verdict != "all" and line_verdict != verdict:
            continue
        if query and query.lower() not in file_name.lower():
            continue
        rows.append(parsed)
    return rows[::-1]


def _csv_guard(value: str) -> str:
    """Chong CSV injection: o bat dau bang = + - @ thi them dau nhay don phia truoc."""
    text = str(value)
    if text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


@app.route("/logs")
def logs() -> str:
    """FR-18: loc, tim kiem, phan trang 50 dong."""
    verdict = request.args.get("verdict", "all")
    query = (request.args.get("q") or "").strip()
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1

    rows = _filtered_log_rows(verdict, query)
    total = len(rows)
    pages = max(1, (total + LOG_PAGE_SIZE - 1) // LOG_PAGE_SIZE)
    page = min(page, pages)
    start = (page - 1) * LOG_PAGE_SIZE
    page_rows = [
        {
            "time": r[0],
            "file": r[1],
            "label": EVENT_LABEL.get(r[2], r[2]),
            "cls": EVENT_CLASS.get(r[2], "warn"),
            "detail": r[3],
        }
        for r in rows[start : start + LOG_PAGE_SIZE]
    ]
    return render_template(
        "logs.html",
        now=_now(),
        rows=page_rows,
        total=total,
        page=page,
        pages=pages,
        verdict=verdict,
        q=query,
        verdicts=LOG_VERDICTS,
    )


@app.route("/logs/export.csv")
def logs_export():
    """FR-18: xuat CSV theo dung bo loc dang xem, co chong CSV injection."""
    verdict = request.args.get("verdict", "all")
    query = (request.args.get("q") or "").strip()
    rows = _filtered_log_rows(verdict, query)

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["thoi_gian", "ten_file", "ket_luan", "chi_tiet"])
    for r in rows:
        writer.writerow([_csv_guard(cell) for cell in r])

    # BOM de Excel doc dung tieng Viet
    data = "\ufeff" + buffer.getvalue()
    return Response(
        data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=verify_log.csv"},
    )


@app.route("/keys")
def keys_view() -> str:
    """FR-17: hien van tay khoa cong khai, ngay tao khoa, nut tai public.pem."""
    exists = config.PUBLIC_KEY_FILE.exists()
    fingerprint = None
    created = None
    if exists:
        try:
            fingerprint = pipeline.key_fingerprint()
        except (OSError, ValueError):
            fingerprint = None
        try:
            created = datetime.fromtimestamp(
                config.PUBLIC_KEY_FILE.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            created = None
    return render_template(
        "keys.html",
        now=_now(),
        exists=exists,
        fingerprint=fingerprint,
        created=created,
        algo="RSA-2048 / RSA-PSS / SHA-256",
    )


@app.route("/keys/public.pem")
def keys_public_download():
    """Chi phuc vu DUY NHAT public.pem. Khong co route nao tra private.pem."""
    if not config.PUBLIC_KEY_FILE.exists():
        abort(404)
    return send_file(
        config.PUBLIC_KEY_FILE,
        mimetype="application/x-pem-file",
        as_attachment=True,
        download_name="public.pem",
    )


@app.route("/alert-test", methods=["GET", "POST"])
def alert_test():
    """FR-19: xem trang thai ntfy (chi lo 3 ky tu dau ten kenh) va gui thu canh bao."""
    configured = bool(config.NTFY_TOPIC)
    topic_hint = (config.NTFY_TOPIC[:3] + "...") if configured else ""
    result = None
    if request.method == "POST":
        sent = notifier.send_alert(
            "[RESPOND] Thu canh bao ImgSign",
            f"Tin nhan thu tu ImgSign luc {_now()}.",
        )
        result = {"sent": sent}
    return render_template(
        "alert_test.html",
        now=_now(),
        configured=configured,
        topic_hint=topic_hint,
        url=config.NTFY_URL,
        result=result,
    )


@app.route("/demo-tamper", methods=["GET", "POST"])
def demo_tamper() -> str:
    signed_files = sorted(config.SIGNED_DIR.glob("IMG-*.png")) if config.SIGNED_DIR.exists() else []
    asset_ids = [p.stem for p in signed_files if ASSET_ID_RE.match(p.stem)]

    if request.method == "GET":
        return render_template(
            "demo_tamper.html", now=_now(), asset_ids=asset_ids, result=None, modes=tamper_mod.TAMPER_MODES
        )

    asset_id = (request.form.get("asset_id") or "").strip()
    mode = (request.form.get("mode") or "").strip()

    if not ASSET_ID_RE.match(asset_id):
        flash("asset_id không hợp lệ (phải có dạng IMG-0001).")
        return render_template(
            "demo_tamper.html", now=_now(), asset_ids=asset_ids, result=None, modes=tamper_mod.TAMPER_MODES
        ), 400
    if not TAMPER_MODE_RE.match(mode):
        flash("Chế độ không hợp lệ.")
        return render_template(
            "demo_tamper.html", now=_now(), asset_ids=asset_ids, result=None, modes=tamper_mod.TAMPER_MODES
        ), 400

    src = config.SIGNED_DIR / f"{asset_id}.png"
    if not src.exists():
        flash(f"Không tìm thấy bản đã ký cho asset '{asset_id}'.")
        return render_template(
            "demo_tamper.html", now=_now(), asset_ids=asset_ids, result=None, modes=tamper_mod.TAMPER_MODES
        ), 404

    dst = config.TAMPERED_DIR / f"{asset_id}_{mode}.png"
    detail = tamper_mod.apply_tamper(src, dst, mode)

    return render_template(
        "demo_tamper.html",
        now=_now(),
        asset_ids=asset_ids,
        modes=tamper_mod.TAMPER_MODES,
        result={"asset_id": asset_id, "mode": mode, "file_name": dst.name, "detail": detail},
    )


@app.route("/media/<kind>/<filename>")
def media(kind: str, filename: str):
    """Phuc vu anh noi bo (signed/original/tampered) voi ten file da kiem tra chat."""
    if kind not in _MEDIA_ALLOW or not _MEDIA_ALLOW[kind].match(filename):
        abort(404)

    directory = _MEDIA_DIR[kind]
    target = (directory / filename).resolve()
    if target.parent != directory.resolve() or not target.exists():
        abort(404)

    as_attachment = request.args.get("dl") == "1"
    return send_file(target, mimetype="image/png", as_attachment=as_attachment, download_name=filename)


@app.route("/download/<asset_id>/<kind>")
def download(asset_id: str, kind: str):
    """Tai file da ky (png/doc) hoac sidecar. kind chi nhan 'png', 'doc' hoac 'sig'."""
    if not ASSET_ID_RE.match(asset_id):
        abort(404)
    if kind not in ("png", "doc", "sig"):
        abort(404)

    signed = docfile.find_signed(config.SIGNED_DIR, asset_id)
    if signed is None:
        abort(404)

    ext = signed.suffix.lower()
    if kind == "png":
        if ext != ".png":
            abort(404)
        target, ctype, dl = signed, "image/png", signed.name
    elif kind == "doc":
        if ext not in _DOC_MIME:
            abort(404)
        target, ctype, dl = signed, _DOC_MIME[ext], signed.name
    else:
        target = Path(str(signed) + ".sig.json")
        ctype, dl = "application/json", target.name

    resolved = target.resolve()
    if resolved.parent != config.SIGNED_DIR.resolve() or not resolved.exists():
        abort(404)

    return send_file(resolved, mimetype=ctype, as_attachment=True, download_name=dl)


@app.errorhandler(413)
def too_large(_exc):
    flash(f"File quá lớn. Giới hạn {config.MAX_UPLOAD_MB} MB.")
    return render_template("verify.html", now=_now(), report=None), 413


@app.errorhandler(404)
def not_found(_exc):
    return render_template("404.html", now=_now()), 404


@app.errorhandler(429)
def too_many_requests(_exc):
    flash(
        f"Bạn đã gửi quá nhiều yêu cầu. Tối đa {config.RATE_LIMIT_MAX} lần mỗi "
        f"{int(config.RATE_LIMIT_WINDOW)} giây cho mỗi địa chỉ IP. Vui lòng thử lại sau."
    )
    return render_template("429.html", now=_now()), 429


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
