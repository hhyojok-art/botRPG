from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi import Request
from redis_client import set_bot_enabled, is_bot_enabled
from dotenv import load_dotenv
import os
from fastapi.responses import HTMLResponse, JSONResponse
import datetime
import asyncio
import traceback

# Muat variabel environment dari file .env jika ada
load_dotenv()

app = FastAPI(title="Bot Dashboard")

# Tambahkan middleware session sederhana untuk menyimpan info login
SECRET = os.environ.get('DASHBOARD_SESSION_SECRET', 'change-me-in-production')
app.add_middleware(SessionMiddleware, secret_key=SECRET)

# Allow Vite dev server and localhost to talk to this backend
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Optionally allow permissive CORS in development via env `DASHBOARD_PERMISSIVE_CORS`
# Set to 1/true to allow all origins for quick testing.
_permissive = os.environ.get('DASHBOARD_PERMISSIVE_CORS', '0').lower() in ('1', 'true', 'yes')
if _permissive:
    _allow_origins = ["*"]
else:
    _allow_origins = origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path ke folder build frontend (akan dipasang di akhir file sehingga rute API tidak tertimpa)
frontend_dist = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')


# Middleware: jika bot dimatikan (maintenance), kembalikan halaman maintenance untuk request GET
@app.middleware("http")
async def maintenance_middleware(request: Request, call_next):
    try:
        enabled = await is_bot_enabled()
    except Exception:
        enabled = True

    # Jika maintenance (enabled == False), izinkan akses ke rute tertentu saja
    if not enabled:
        path = request.url.path
        # Allowlist: health, maintenance control, and auth endpoints
        allow_prefixes = ['/health', '/maintenance', '/auth']
        # Jika request bukan ke salah satu allowlist dan metode GET, tampilkan halaman maintenance
        if request.method == 'GET' and not any(path.startswith(p) for p in allow_prefixes):
            html = """
            <!doctype html>
            <html><head><meta charset='utf-8'><title>Maintenance</title></head>
            <body style='font-family:Arial,Helvetica,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;'>
            <div style='text-align:center;'>
              <h1>Server sedang dalam maintenance</h1>
              <p>Mohon tunggu beberapa saat. Silakan coba lagi nanti.</p>
            </div>
            </body></html>
            """
            return HTMLResponse(html, status_code=503)

    response = await call_next(request)
    return response

# Mount router auth jika tersedia
try:
    from . import auth
    app.include_router(auth.router, prefix="/auth")
except Exception:
    # Jika belum ada atau error, lewati (file mungkin belum dibuat saat pengembangan)
    pass


@app.get("/")
async def root():
        # Quick immediate response for health checks (avoid any blocking I/O)
        html = """
        <!doctype html>
        <html><head><meta charset='utf-8'><title>Bot Dashboard</title></head>
        <body style='font-family:Arial,Helvetica,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;'>
        <div style='text-align:center;'>
            <h1>Bot Dashboard</h1>
            <p>Status: <strong>ok</strong></p>
            <p>JSON health: <a href="/health">/health</a></p>
        </div>
        </body></html>
        """
        return HTMLResponse(html)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "bot_enabled": await is_bot_enabled()
    }


@app.get("/replit", response_class=HTMLResponse)
async def replit_health():
        # Keep this endpoint fast and avoid awaiting external services.
        html = """
        <!doctype html>
        <html><head><meta charset='utf-8'><title>Replit Health</title></head>
        <body style='font-family:Arial,Helvetica,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;'>
        <div style='text-align:center;'>
            <h1>Replit Health</h1>
            <p>Bot enabled: <strong>unknown</strong></p>
            <p>Raw API: <a href="/health">/health</a></p>
        </div>
        </body></html>
        """
        return HTMLResponse(html)


@app.post("/maintenance/on")
async def maintenance_on():
    await set_bot_enabled(False)
    # Generate/update Undertale-styled maintenance image in background
    # Only auto-generate maintenance image if MAINT_AUTO_GENERATE is enabled
    try:
        auto = os.getenv('MAINT_AUTO_GENERATE', '0').lower() in ('1', 'true', 'yes')
    except Exception:
        auto = False
    if auto:
        try:
            import scripts.update_maintenance_image as umi

            def _run_generator():
                try:
                    umi.main()
                except Exception as e:
                    print(f"[dashboard] maintenance generator error: {e}")
                    traceback.print_exc()

            asyncio.create_task(asyncio.to_thread(_run_generator))
        except Exception as e:
            print(f"[dashboard] failed to import maintenance generator: {e}")
            traceback.print_exc()
    return {"maintenance": "on"}


@app.post("/maintenance/off")
async def maintenance_off():
    await set_bot_enabled(True)
    return {"maintenance": "off"}


# Pasang static frontend terakhir supaya semua rute API di atas tetap bekerja
if os.path.isdir(os.path.abspath(frontend_dist)):
    app.mount('/', StaticFiles(directory=os.path.abspath(frontend_dist), html=True), name='frontend')


@app.on_event("startup")
async def _write_uvicorn_marker():
    """Write a small marker file when the FastAPI app starts and binds to a port.

    This helps Replit detect that the process opened a port quickly.
    """
        try:
            port = os.environ.get('PORT', '8000')
            marker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.uvicorn_bound'))
            # ensure logs dir exists
            logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
            try:
                os.makedirs(logs_dir, exist_ok=True)
            except Exception:
                pass

            with open(marker_path, 'w', encoding='utf-8') as f:
                f.write(f"started: {datetime.datetime.utcnow().isoformat()}Z\n")
                f.write(f"port: {port}\n")

            # append a human-readable startup line to logs/replit_startup.log
            try:
                startup_log = os.path.join(logs_dir, 'replit_startup.log')
                with open(startup_log, 'a', encoding='utf-8') as lf:
                    lf.write(f"{datetime.datetime.utcnow().isoformat()}Z | dashboard started on port {port}\n")
                app_logger.info(f"dashboard started; marker written to {marker_path}")
            except Exception as e:
                try:
                    app_logger.warning(f"failed to write replit startup log: {e}")
                except Exception:
                    pass
        except Exception:
            # Never crash startup due to marker write failures
            pass


@app.get('/probe')
async def probe():
    """Quick JSON probe for deployment systems to confirm uvicorn started."""
    try:
        marker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.uvicorn_bound'))
        if os.path.isfile(marker_path):
            with open(marker_path, 'r', encoding='utf-8') as f:
                data = f.read()
            return JSONResponse({"status": "bound", "marker": data}, status_code=200)
        else:
            return JSONResponse({"status": "not_bound"}, status_code=503)
    except Exception:
        return JSONResponse({"status": "error"}, status_code=500)
