"""Portfolio backend: server-rendered public site, admin portal and admin API.

Run (behind Nginx):  uvicorn server.main:app --host 127.0.0.1 --port 8001
Content lives in the GitHub repo; every admin save is committed through the
GitHub Contents API and mirrored on local disk so the site updates instantly.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urlparse
from xml.sax.saxutils import escape as xml_escape

import httpx
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, JSONResponse, Response as RawResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markupsafe import Markup
import nh3
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "server" / ".env")

PUBLIC = ROOT / "public"
UPLOADS = PUBLIC / "uploads"
CONTENT = ROOT / "content" / "site-data.json"
DATA = ROOT / "data"
DB = DATA / "analytics.db"
for d in (UPLOADS / "images", UPLOADS / "files", CONTENT.parent, DATA):
    d.mkdir(parents=True, exist_ok=True)

JWT_SECRET = os.environ.get("JWT_SECRET", "")
PW_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1") == "1"
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GH_OWNER = os.environ.get("GITHUB_OWNER", "")
GH_REPO = os.environ.get("GITHUB_REPO", "")
GH_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8001").rstrip("/")

if len(JWT_SECRET) < 32 or not PW_HASH:
    raise RuntimeError("Set JWT_SECRET (32+ chars) and ADMIN_PASSWORD_HASH in server/.env")

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
FILE_EXT = {".pdf", ".zip", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv"}
MAX_UPLOAD = 20 * 1024 * 1024  # 20 MB; SVG and HTML are refused on purpose (script risk)

# Everything is served from this origin; the only outside host is the contact-form service.
# 'unsafe-inline' is needed by the admin page and the legacy SecurePulse demo pages.
CSP = ("default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
       "script-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self' https://formspree.io; "
       "form-action 'self' https://formspree.io; frame-ancestors 'none'; base-uri 'self'; object-src 'none'")
LEGAL_UPDATED = "21 November 2026"  # change when privacy.html or terms.html text changes

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if COOKIE_SECURE:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000"
    if request.url.path.startswith(("/admin", "/api")):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------- auth
FAILS: dict[str, list[float]] = {}


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split(":")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), hash_hex)
    except Exception:
        return False


def require_admin(request: Request) -> None:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(401, "Not signed in")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired, sign in again")
    # Cookie is SameSite=Strict; the custom header is a second CSRF guard on writes.
    if request.method != "GET" and request.headers.get("x-requested-with") != "admin":
        raise HTTPException(403, "Bad request")


class LoginBody(BaseModel):
    password: str = Field(max_length=200)


@app.post("/api/login")
def login(body: LoginBody, request: Request, response: Response):
    ip, now = client_ip(request), time.time()
    recent = [t for t in FAILS.get(ip, []) if now - t < 900]
    if len(recent) >= 5:
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    if not verify_password(body.password, PW_HASH):
        FAILS[ip] = recent + [now]
        time.sleep(0.5)
        raise HTTPException(401, "Incorrect password")
    FAILS.pop(ip, None)
    token = jwt.encode({"sub": "admin", "exp": int(now) + 12 * 3600}, JWT_SECRET, algorithm="HS256")
    response.set_cookie("session", token, httponly=True, secure=COOKIE_SECURE,
                        samesite="strict", max_age=12 * 3600, path="/api")
    return {"ok": True}


@app.get("/api/admin/me", dependencies=[Depends(require_admin)])
def me():
    return {"ok": True}


@app.post("/api/admin/logout", dependencies=[Depends(require_admin)])
def logout(response: Response):
    response.delete_cookie("session", path="/api")
    return {"ok": True}


# ---------------------------------------------------------------- storage (GitHub + local)
def _gh():
    base = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "portfolio-admin",
    }
    return base, headers


async def gh_sha(c: httpx.AsyncClient, url: str, headers: dict) -> str | None:
    r = await c.get(url, headers=headers, params={"ref": GH_BRANCH})
    if r.status_code == 200:
        return r.json().get("sha")
    if r.status_code == 404:
        return None
    raise HTTPException(502, f"GitHub lookup failed ({r.status_code})")


async def gh_put(repo_path: str, data: bytes, message: str) -> None:
    if not GH_TOKEN:
        return  # local-only mode (testing)
    base, headers = _gh()
    async with httpx.AsyncClient(timeout=60) as c:
        body = {"message": message, "content": base64.b64encode(data).decode(), "branch": GH_BRANCH}
        sha = await gh_sha(c, base + repo_path, headers)
        if sha:
            body["sha"] = sha
        r = await c.put(base + repo_path, headers=headers, json=body)
        if r.status_code not in (200, 201):
            raise HTTPException(502, f"GitHub commit failed ({r.status_code}): {r.text[:200]}")


async def gh_delete(repo_path: str, message: str) -> None:
    if not GH_TOKEN:
        return
    base, headers = _gh()
    async with httpx.AsyncClient(timeout=60) as c:
        sha = await gh_sha(c, base + repo_path, headers)
        if not sha:
            return
        r = await c.request("DELETE", base + repo_path, headers=headers,
                            json={"message": message, "sha": sha, "branch": GH_BRANCH})
        if r.status_code != 200:
            raise HTTPException(502, f"GitHub delete failed ({r.status_code}): {r.text[:200]}")


async def save_file(path: Path, data: bytes, message: str) -> None:
    """Commit to GitHub first (source of truth), then mirror locally."""
    await gh_put(path.relative_to(ROOT).as_posix(), data, message)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


# ---------------------------------------------------------------- site content
REQUIRED = {"site": dict, "hero": dict, "about": str, "stats": list, "experience": list, "education": list,
            "certifications": list, "skills": dict, "projects": list, "contact": dict}


@app.get("/api/site")
def get_site():
    if not CONTENT.exists():
        raise HTTPException(404, "No content yet")
    return JSONResponse(json.loads(CONTENT.read_text(encoding="utf-8")))


@app.put("/api/admin/site", dependencies=[Depends(require_admin)])
async def put_site(request: Request):
    try:
        site = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if not isinstance(site, dict) or any(not isinstance(site.get(k), t) for k, t in REQUIRED.items()):
        raise HTTPException(422, "Site data is missing a required section")
    ids = [p.get("id") for p in site["projects"] if isinstance(p, dict)]
    if len(ids) != len(site["projects"]) or not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
        raise HTTPException(422, "Every project needs a unique URL slug")
    raw = json.dumps(site, indent=2, ensure_ascii=False).encode("utf-8")
    if len(raw) > 500_000:
        raise HTTPException(413, "Site data is too large")
    await save_file(CONTENT, raw, "cms: update site content")
    return {"ok": True}


# ---------------------------------------------------------------- uploads
def safe_name(filename: str) -> tuple[str, str]:
    stem, ext = os.path.splitext(os.path.basename(filename))
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.")[:60] or "file"
    return stem, ext.lower()


@app.post("/api/admin/upload", dependencies=[Depends(require_admin)])
async def upload(file: UploadFile = File(...), overwrite: bool = Form(False)):
    stem, ext = safe_name(file.filename or "")
    if ext not in IMAGE_EXT | FILE_EXT:
        raise HTTPException(415, f"File type {ext or '(none)'} is not allowed")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File is larger than 20 MB")
    folder = "images" if ext in IMAGE_EXT else "files"
    target, n = UPLOADS / folder / f"{stem}{ext}", 2
    while target.exists() and not overwrite:
        target = UPLOADS / folder / f"{stem}-{n}{ext}"
        n += 1
    await save_file(target, data, f"cms: upload {target.name}")
    return {"ok": True, "name": file.filename, "url": f"/uploads/{folder}/{target.name}"}


@app.get("/api/admin/uploads", dependencies=[Depends(require_admin)])
def list_uploads():
    out = []
    for folder in ("images", "files"):
        for p in sorted((UPLOADS / folder).iterdir()):
            if p.is_file() and p.name != ".gitkeep":
                out.append({"name": p.name, "folder": folder, "url": f"/uploads/{folder}/{p.name}",
                            "size": p.stat().st_size})
    return out


@app.delete("/api/admin/upload/{folder}/{name}", dependencies=[Depends(require_admin)])
async def delete_upload(folder: Literal["images", "files"], name: str):
    target = (UPLOADS / folder / name).resolve()
    if target.parent != (UPLOADS / folder).resolve() or not target.is_file():
        raise HTTPException(404, "File not found")
    await gh_delete(target.relative_to(ROOT).as_posix(), f"cms: delete {name}")
    target.unlink()
    return {"ok": True}


# ---------------------------------------------------------------- analytics (no IPs stored)
with closing(sqlite3.connect(DB)) as _c:
    _c.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, ts TEXT DEFAULT (datetime('now')),
            type TEXT, path TEXT, ref TEXT, device TEXT, label TEXT, vid TEXT);
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
    """)

BOT = re.compile(r"bot|crawl|spider|slurp|preview|curl|python|headless", re.I)


_last_purge = {"day": None}


def purge_old_events() -> None:
    """Privacy policy promises statistics are kept for at most 13 months."""
    if _last_purge["day"] == date.today():
        return
    with closing(sqlite3.connect(DB)) as c:
        c.execute("DELETE FROM events WHERE ts < datetime('now', '-395 days')")
        c.commit()
    _last_purge["day"] = date.today()


def device_of(ua: str) -> str:
    ua = ua.lower()
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    return "mobile" if ("mobi" in ua or "android" in ua) else "desktop"


class TrackBody(BaseModel):
    type: Literal["pageview", "cv_download", "project_view", "link_click"]
    path: str = Field("/", max_length=200)
    ref: str = Field("", max_length=200)
    label: str = Field("", max_length=100)


def record_event(request: Request, type_: str, path: str, ref: str = "", label: str = "") -> None:
    ua = request.headers.get("user-agent", "")
    if BOT.search(ua):
        return
    # Daily-rotating anonymous visitor id: lets us count unique visitors per day without storing an IP.
    vid = hashlib.sha256(f"{JWT_SECRET}{date.today()}{client_ip(request)}{ua}".encode()).hexdigest()[:16]
    host = urlparse(ref).hostname or ref
    if host and host == urlparse(SITE_URL).hostname:
        host = ""  # internal navigation is not a referrer
    purge_old_events()
    with closing(sqlite3.connect(DB)) as c:
        c.execute("INSERT INTO events (type, path, ref, device, label, vid) VALUES (?,?,?,?,?,?)",
                  (type_, path[:200], host[:100], device_of(ua), label[:100], vid))
        c.commit()


@app.post("/api/track")
def track(body: TrackBody, request: Request):
    record_event(request, body.type, body.path, body.ref, body.label)
    return {"ok": True}


@app.get("/api/admin/metrics", dependencies=[Depends(require_admin)])
def metrics(days: int = 30):
    days = max(1, min(days, 365))
    since = f"-{days} days"
    with closing(sqlite3.connect(DB)) as c:
        def q(sql):
            return c.execute(sql, (since,)).fetchall()
        totals = {t: n for t, n in q("SELECT type, COUNT(*) FROM events WHERE ts >= datetime('now', ?) GROUP BY type")}
        visitors = q("SELECT COUNT(*) FROM (SELECT DISTINCT date(ts), vid FROM events "
                     "WHERE type='pageview' AND ts >= datetime('now', ?))")[0][0]
        daily = q("SELECT date(ts), COUNT(*) FROM events WHERE type='pageview' "
                  "AND ts >= datetime('now', ?) GROUP BY date(ts) ORDER BY 1")
        refs = q("SELECT ref, COUNT(*) c FROM events WHERE type='pageview' AND ref != '' "
                 "AND ts >= datetime('now', ?) GROUP BY ref ORDER BY c DESC LIMIT 8")
        devices = q("SELECT device, COUNT(*) c FROM events WHERE type='pageview' "
                    "AND ts >= datetime('now', ?) GROUP BY device ORDER BY c DESC")
        projects = q("SELECT label, COUNT(*) c FROM events WHERE type='project_view' "
                     "AND ts >= datetime('now', ?) GROUP BY label ORDER BY c DESC LIMIT 10")
    pair = lambda rows, a="k", b="c": [{a: r[0], b: r[1]} for r in rows]
    return {"days": days, "totals": totals, "visitors": visitors, "daily": pair(daily, "d", "c"),
            "referrers": pair(refs), "devices": pair(devices), "projects": pair(projects)}


# ---------------------------------------------------------------- public pages (server-rendered)
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))
_md = MarkdownIt("commonmark", {"html": False}).enable("table")
_ALLOWED = {"p", "br", "h2", "h3", "h4", "ul", "ol", "li", "strong", "em", "a", "code", "pre", "blockquote",
            "img", "hr", "table", "thead", "tbody", "tr", "th", "td"}


def _safe_url(u):
    return u if re.match(r"^(https?://|/(?!/)|mailto:|tel:)", u or "", re.I) else ""


def _two_tone(text: str):
    m = re.match(r"(.+?[.!?])\s+(.*)", (text or "").strip(), re.S)
    return (m.group(1), m.group(2)) if m else ((text or "").strip(), "")


TEMPLATES.env.filters["safe_url"] = _safe_url
TEMPLATES.env.filters["two_tone"] = _two_tone
TEMPLATES.env.filters["md"] = lambda t: Markup(nh3.clean(
    _md.render(t or ""), tags=_ALLOWED, link_rel="noopener noreferrer", url_schemes={"http", "https", "mailto"}))

_cache = {"mtime": 0.0, "data": None}


def load_site() -> dict:
    mtime = CONTENT.stat().st_mtime
    if _cache["mtime"] != mtime:
        d = json.loads(CONTENT.read_text(encoding="utf-8"))
        for k in ("site", "hero", "skills", "contact"):
            d.setdefault(k, {})
        for k in ("stats", "experience", "education", "certifications", "projects"):
            d.setdefault(k, [])
        d.setdefault("about", "")
        _cache.update(mtime=mtime, data=d)
    return _cache["data"]


def visible_projects(s: dict) -> list:
    return [p for p in s["projects"] if p.get("visible", True)]


def render(request: Request, template: str, status: int = 200, track_page: bool = True, **ctx):
    s = load_site()
    if track_page and request.method == "GET":
        record_event(request, "pageview", request.url.path, request.headers.get("referer", ""))
    return TEMPLATES.TemplateResponse(request, template, {
        "s": s, "site_url": SITE_URL, "year": datetime.now().year, "legal_updated": LEGAL_UPDATED, **ctx},
        status_code=status)


@app.get("/")
def home(request: Request):
    s = load_site()
    projects = visible_projects(s)
    featured = [p for p in projects if p.get("featured")][:4] or projects[:4]
    person = {"@context": "https://schema.org", "@type": "Person", "name": s["hero"].get("name", ""),
              "url": SITE_URL + "/", "jobTitle": s["hero"].get("role", ""),
              "sameAs": [u for u in (s["contact"].get("linkedin"), s["contact"].get("github")) if u]}
    ld = json.dumps(person).replace("<", "\\u003c")
    return render(request, "home.html", featured=featured, person_ld=ld, nav="home")


@app.get("/works")
def works(request: Request):
    s = load_site()
    return render(request, "works.html", projects=visible_projects(s), nav="works",
                  page_title=f"Works | {s['hero'].get('short_name', '')}",
                  page_desc="Engineering, research and software projects.")


@app.get("/works/{pid}")
def work(request: Request, pid: str):
    s = load_site()
    projects = visible_projects(s)
    idx = next((i for i, p in enumerate(projects) if p.get("id") == pid), None)
    if idx is None:
        raise HTTPException(404, "Project not found")
    p = projects[idx]
    record_event(request, "project_view", request.url.path, "", pid)
    return render(request, "work.html", p=p, nav="works",
                  prev=projects[idx - 1] if idx > 0 else None,
                  next=projects[idx + 1] if idx + 1 < len(projects) else None,
                  page_title=f"{p.get('title', '')} | {s['hero'].get('short_name', '')}",
                  page_desc=p.get("summary", ""), og_image=p.get("thumbnail"))


@app.get("/about")
def about(request: Request):
    s = load_site()
    return render(request, "about.html", nav="about", page_title=f"About | {s['hero'].get('short_name', '')}",
                  page_desc=(s["about"].split("\n\n")[0] if s["about"] else None))


@app.get("/contact")
def contact(request: Request):
    s = load_site()
    return render(request, "contact.html", nav="contact", page_title=f"Contact | {s['hero'].get('short_name', '')}",
                  page_desc="Get in touch about projects, collaborations or opportunities.")


@app.get("/privacy")
def privacy(request: Request):
    s = load_site()
    return render(request, "privacy.html", nav="", page_title=f"Privacy Policy | {s['hero'].get('short_name', '')}",
                  page_desc="How personal information is handled on this website (POPIA).")


@app.get("/terms")
def terms(request: Request):
    s = load_site()
    return render(request, "terms.html", nav="", page_title=f"Terms of Use | {s['hero'].get('short_name', '')}",
                  page_desc="Terms of use, copyright and legal notice for this website.")


@app.get("/cv")
def download_cv(request: Request):
    s = load_site()
    url = s["hero"].get("cv_url", "")
    path = (PUBLIC / url.lstrip("/")).resolve()
    if not url.startswith("/uploads/files/") or not path.is_file() or UPLOADS.resolve() not in path.parents:
        raise HTTPException(404, "CV not available")
    record_event(request, "cv_download", "/cv")
    name = re.sub(r"[^A-Za-z0-9]+", "_", s["hero"].get("name", "CV")).strip("_") or "CV"
    return FileResponse(path, media_type="application/pdf", filename=f"{name}_CV.pdf")


@app.get("/sitemap.xml")
def sitemap():
    s = load_site()
    lastmod = datetime.fromtimestamp(CONTENT.stat().st_mtime, timezone.utc).date().isoformat()
    paths = ["/", "/works", "/about", "/contact", "/privacy", "/terms"] + [f"/works/{quote(p['id'])}" for p in visible_projects(s)]
    body = "".join(f"<url><loc>{xml_escape(SITE_URL + u)}</loc><lastmod>{lastmod}</lastmod></url>" for u in paths)
    return RawResponse('<?xml version="1.0" encoding="UTF-8"?>'
                       f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
                       media_type="application/xml")


@app.exception_handler(StarletteHTTPException)
async def not_found(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and not request.url.path.startswith("/api"):
        return render(request, "404.html", status=404, track_page=False, nav="")
    return await http_exception_handler(request, exc)


@app.get("/admin")
def admin_page():
    return FileResponse(ROOT / "admin" / "index.html")


app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")
app.mount("/", StaticFiles(directory=PUBLIC), name="public")  # assets, legacy SecurePulse pages, robots.txt
