"""Router otentikasi sederhana menggunakan Discord OAuth2.

Instruksi singkat (ENV vars):
- DISCORD_CLIENT_ID
- DISCORD_CLIENT_SECRET
- DISCORD_REDIRECT_URI (mis. http://localhost:8000/auth/callback)

Semua pesan dan komentar ditulis dalam Bahasa Indonesia.
"""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
import os
import aiohttp
from urllib.parse import urlencode

router = APIRouter()

DISCORD_BASE = "https://discord.com/api"
CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID')
CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET')
REDIRECT_URI = os.environ.get('DISCORD_REDIRECT_URI', 'http://localhost:8000/auth/callback')


def _discord_authorize_url(state: str = None, scope: str = "identify"):
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': scope,
    }
    if state:
        params['state'] = state
    return f"{DISCORD_BASE}/oauth2/authorize?" + urlencode(params)


@router.get('/login')
async def login(request: Request):
    """Redirect ke Discord untuk login (OAuth2).

    Pastikan ENV vars sudah diset. Jika belum, akan mengembalikan pesan error sederhana.
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        return JSONResponse({'error': 'DISCORD_CLIENT_ID atau DISCORD_CLIENT_SECRET belum diset di environment'}, status_code=500)
    # Redirect ke URL authorisasi Discord
    url = _discord_authorize_url(scope='identify')
    return RedirectResponse(url)


@router.get('/callback')
async def callback(request: Request, code: str = None, state: str = None):
    """Callback OAuth dari Discord. Tukar kode dengan access token, lalu ambil data user."""
    if not code:
        return JSONResponse({'error': 'Tidak menerima kode dari Discord'}, status_code=400)

    token_url = f"{DISCORD_BASE}/oauth2/token"
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    async with aiohttp.ClientSession() as session:
        # tukar kode -> token
        async with session.post(token_url, data=data, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                return JSONResponse({'error': 'Gagal menukar token', 'detail': text}, status_code=502)
            token_json = await resp.json()

        access_token = token_json.get('access_token')
        if not access_token:
            return JSONResponse({'error': 'Token tidak ditemukan dalam respon'}, status_code=502)

        # ambil data user
        async with session.get(f"{DISCORD_BASE}/users/@me", headers={'Authorization': f'Bearer {access_token}'}) as uresp:
            if uresp.status != 200:
                txt = await uresp.text()
                return JSONResponse({'error': 'Gagal mengambil data user', 'detail': txt}, status_code=502)
            user = await uresp.json()

    # Simpan info user ke session
    request.session['user'] = {
        'id': user.get('id'),
        'username': user.get('username'),
        'discriminator': user.get('discriminator'),
        'avatar': user.get('avatar'),
    }

    # Redirect kembali ke frontend root atau halaman dashboard
    # Baca dari DASHBOARD_FRONTEND_URL (sesuai .env)
    frontend = os.environ.get('DASHBOARD_FRONTEND_URL', '/')
    return RedirectResponse(frontend)


@router.get('/me')
async def me(request: Request):
    """Kembalikan info user yang sedang login, atau 401 jika belum login."""
    user = request.session.get('user')
    if not user:
        return JSONResponse({'error': 'Belum login'}, status_code=401)
    return JSONResponse({'user': user})


@router.post('/logout')
async def logout(request: Request):
    """Hapus session user (logout)."""
    request.session.pop('user', None)
    return JSONResponse({'status': 'logout'})
