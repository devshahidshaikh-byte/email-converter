
from pathlib import Path
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as generator_router
from app.api.auth_routes import router as auth_router
from app.auth import get_current_user, init_db

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"
LOGIN_FILE = FRONTEND_DIR / "login.html"
ADMIN_FILE = FRONTEND_DIR / "admin.html"

app = FastAPI(
    title="Email Permutation Studio",
    description="Professional email-pattern generation API with secure user accounts and admin controls.",
    version="2.0.0",
)

# CORS is required when the frontend is hosted on Netlify and the API is
# hosted on Render. Put your exact Netlify URL in FRONTEND_ORIGIN.
# Example:
# FRONTEND_ORIGIN=https://your-site.netlify.app
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "FRONTEND_ORIGIN",
        "http://127.0.0.1:8000,http://localhost:8000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

# Create the SQLite database and initial administrator.
init_db()

# Authentication and generator APIs.
app.include_router(auth_router)
app.include_router(generator_router)


@app.get("/", include_in_schema=False)
async def frontend_home(request: Request):
    """
    The home page is now login-protected.

    If there is no valid session, the user is sent to /login.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    return FileResponse(INDEX_FILE)


@app.get("/login", include_in_schema=False)
async def login_page():
    return FileResponse(LOGIN_FILE)


@app.get("/admin", include_in_schema=False)
async def admin_page(request: Request):
    """Only an authenticated admin should be able to open the dashboard page."""
    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login", status_code=303)

    if user["role"] != "admin":
        return RedirectResponse("/", status_code=303)

    return FileResponse(ADMIN_FILE)


# Static assets are mounted last.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
