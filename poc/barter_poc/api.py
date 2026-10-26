"""HTTP API and static page.

No sign-in: this proof of concept runs on synthetic people, and the page lets
you switch between them to walk a circle from every side. The participant id
in each path stands in for a signed-in user.
"""

import hashlib
import hmac
import os
import threading
import time
from typing import List, Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from .service import NotAllowed, Service
from .understanding import from_environment

STATIC = os.path.join(os.path.dirname(__file__), "static")
COOKIE = "barter_pass"
# Reachable without the passcode: the unlock page, its stylesheet, and the health check.
OPEN_PATHS = ("/unlock", "/healthz", "/static/styles.css")


class Profile(BaseModel):
    zone: str
    max_travel: int = 0
    availability: List[str] = []


class Join(Profile):
    name: str


class NewListing(BaseModel):
    kind: str
    text: str
    mode: str = "either"
    effort_hours: Optional[float] = Field(default=None, ge=0, le=100)


class Concepts(BaseModel):
    concepts: List[str]


class Response(BaseModel):
    response: str


class Received(BaseModel):
    note: str = ""


class Report(BaseModel):
    reason: str
    circle_id: Optional[int] = None


class Block(BaseModel):
    other_id: str


def _token(passcode: str) -> str:
    return hashlib.sha256(("barter-poc:" + passcode).encode()).hexdigest()


def _lock_page(error: str = "") -> HTMLResponse:
    with open(os.path.join(STATIC, "lock.html"), encoding="utf-8") as f:
        html = f.read()
    if error:
        html = html.replace("<!--error-->", f'<p class="error">{error}</p>')
    return HTMLResponse(html, status_code=401)


def create_app(service: Service, passcode: Optional[str] = None) -> FastAPI:
    """With a passcode, every page and API call needs the unlock cookie first."""
    app = FastAPI(title="BarterSystem POC", docs_url=None if passcode else "/docs",
                  redoc_url=None, openapi_url=None if passcode else "/openapi.json")
    lock = threading.Lock()  # one SQLite connection; keep writes serial

    if passcode:
        expected = _token(passcode)

        @app.middleware("http")
        async def require_passcode(request: Request, call_next):
            if request.url.path in OPEN_PATHS or hmac.compare_digest(request.cookies.get(COOKIE, ""), expected):
                return await call_next(request)
            if request.url.path.startswith("/api/"):
                return JSONResponse({"detail": "passcode required"}, status_code=401)
            return _lock_page()

        @app.post("/unlock")
        def unlock(request: Request, passcode_attempt: str = Form(alias="passcode")):
            if not hmac.compare_digest(_token(passcode_attempt), expected):
                time.sleep(1)  # slow down guessing
                return _lock_page("That passcode didn't work.")
            response = RedirectResponse("/", status_code=303)
            https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
            response.set_cookie(COOKIE, expected, max_age=30 * 24 * 3600, httponly=True,
                                samesite="lax", secure=https)
            return response

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    def call(fn, *args, **kwargs):
        try:
            with lock:
                return fn(*args, **kwargs)
        except KeyError:
            raise HTTPException(404, "not found")
        except NotAllowed as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.get("/api/status")
    def status():
        return call(service.status)

    @app.get("/api/people")
    def people():
        return call(service.participants)

    @app.post("/api/people")
    def join(body: Join):
        return {"id": call(service.join, body.name, body.zone, body.max_travel, body.availability)}

    @app.put("/api/people/{pid}")
    def update(pid: str, body: Profile):
        call(service.update_profile, pid, body.zone, body.max_travel, body.availability)
        return {"ok": True}

    @app.get("/api/people/{pid}/dashboard")
    def dashboard(pid: str):
        return call(service.dashboard, pid)

    @app.get("/api/people/{pid}/community")
    def community(pid: str):
        return call(service.community_listings, pid)

    @app.post("/api/people/{pid}/listings")
    def add_listing(pid: str, body: NewListing):
        return {"id": call(service.add_listing, pid, body.kind, body.text, body.mode, body.effort_hours)}

    @app.put("/api/people/{pid}/listings/{lid}/concepts")
    def edit_concepts(pid: str, lid: str, body: Concepts):
        call(service.edit_concepts, pid, lid, body.concepts)
        return {"ok": True}

    @app.delete("/api/people/{pid}/listings/{lid}")
    def close_listing(pid: str, lid: str):
        call(service.close_listing, pid, lid)
        return {"ok": True}

    @app.post("/api/people/{pid}/circles/{cid}/respond")
    def respond(pid: str, cid: int, body: Response):
        return {"status": call(service.respond, pid, cid, body.response)}

    @app.post("/api/people/{pid}/circles/{cid}/received")
    def received(pid: str, cid: int, body: Received):
        return {"status": call(service.confirm_received, pid, cid, body.note)}

    @app.post("/api/people/{pid}/reports")
    def report(pid: str, body: Report):
        call(service.report, pid, body.reason, body.circle_id)
        return {"ok": True}

    @app.post("/api/people/{pid}/blocks")
    def block(pid: str, body: Block):
        call(service.block, pid, body.other_id)
        return {"ok": True}

    @app.post("/api/match")
    def run_matching():
        return {"new_circles": call(service.run_matching)}

    @app.post("/api/reset")
    def reset():
        call(service.seed)
        return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(os.path.join(STATIC, "index.html"))

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def build() -> FastAPI:
    path = os.environ.get("BARTER_DB", os.path.join(os.getcwd(), "data", "barter-poc.sqlite3"))
    service = Service(db.connect(path), from_environment())
    if service.is_empty():
        service.seed()
    return create_app(service, passcode=os.environ.get("BARTER_PASSCODE") or None)


def main():
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"BarterSystem POC on http://localhost:{port}")
    uvicorn.run(build(), host=host, port=port)
