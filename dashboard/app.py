from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi import Request
from redis_client import set_bot_enabled, is_bot_enabled
from dotenv import load_dotenv
import os
from fastapi.responses import HTMLResponse
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "bot_enabled": await is_bot_enabled()
    }


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
