# Email Permutation Studio — Professional Edition

A FastAPI + vanilla HTML/CSS/JavaScript email-pattern generator with a real SQLite account system, secure sessions, administrator dashboard, private Gmail allowlist, login tracking and server-side private bulk processing.

## What was added

### User accounts
- Gmail-only registration.
- Secure password hashing with `hashlib.scrypt`.
- Server-side sessions stored in SQLite.
- HttpOnly session cookie.
- CSRF protection for account/admin state-changing actions.
- Sign out.
- Account activity tracking.

### Administrator
Initial administrator:

```text
Email:    dev.shahidshaikh@gmail.com
Password: Admin@2026!ChangeMe
```

**Change this password immediately after your first login.**

Open:

```text
http://127.0.0.1:8000/admin
```

The admin dashboard can:

- View all users.
- See registration time and last login.
- See login counts.
- Approve users for private features.
- Disable/enable accounts.
- Permanently delete users.
- Add selected Gmail addresses to the private allowlist.
- Remove private Gmail addresses.
- View the security/login audit log.
- Change the administrator Gmail and password.

The initial values in `.env` are only used to create the first administrator when the database has no admin yet. After that, changing the admin account from the dashboard is persistent.

### Premium account access rule

This version uses an administrator-controlled allowlist for the entire application:

1. Admin logs in with the initial admin account.
2. Admin opens **Private access** and adds a Gmail address.
3. Only then can that Gmail address create an account.
4. That account can log in and use the workspace.
5. Removing the Gmail from the allowlist blocks that user from logging in on the next attempt.

The check is performed by FastAPI on the server.

### Private feature

The **server-side CSV bulk generator** is private.

Only:
- the administrator, or
- a Gmail account approved by the administrator

can use it.

This is enforced on the FastAPI server. The JavaScript hiding/showing the button is only for user experience; it is not the security boundary.

## Project structure

```text
emailtool/
│
├── app/
│   ├── api/
│   │   ├── auth_routes.py       # Login, registration, admin dashboard APIs
│   │   └── routes.py            # Generator + private bulk API
│   │
│   ├── services/
│   │   ├── permutation_service.py
│   │   ├── validation_service.py
│   │   └── export_service.py
│   │
│   ├── auth.py                  # Passwords, sessions, CSRF, permissions
│   ├── config.py
│   ├── models.py
│   ├── pattern_engine.py
│   └── main.py                  # Starts FastAPI and serves frontend
│
├── frontend/
│   ├── index.html               # Main generator
│   ├── login.html               # Sign in / registration
│   ├── admin.html               # Administrator dashboard
│   ├── css/
│   │   ├── style.css
│   │   ├── auth.css
│   │   └── admin.css
│   └── js/
│       ├── app.js               # Generator UI
│       ├── api.js               # Browser → FastAPI requests
│       └── auth.js              # Logged-in user + private feature UI
│
├── tests/
├── requirements.txt
├── .env
└── README.md
```

## Windows local setup

Open the VS Code terminal in the folder that contains:

```text
app
frontend
requirements.txt
```

If your terminal is one level above it:

```powershell
cd emailtool
```

Create the virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks scripts, use Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

Install everything:

```powershell
pip install -r requirements.txt
```

Start the website:

```powershell
python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

## First login

Use:

```text
dev.shahidshaikh@gmail.com
Admin@2026!ChangeMe
```

Then open:

```text
http://127.0.0.1:8000/admin
```

Change the administrator account from:

**Admin Dashboard → Overview → Administrator account**

## How to add a private Gmail user

1. Login as admin.
2. Open **Private access**.
3. Enter a Gmail address, for example:

```text
selected.user@gmail.com
```

4. Click **Add Gmail**.
5. If that user already has an account, private access is enabled immediately.
6. If they do not have an account yet, they receive private access when they register using that exact Gmail address.

You can also approve an existing user directly from **Users → Approve**.

## Database

The application creates:

```text
app/data/emailtool.db
```

This SQLite database contains:

- `users`
- `sessions`
- `approved_emails`
- `audit_logs`

Do not upload this database publicly.

To completely reset the local authentication system during development:

1. Stop Uvicorn with `Ctrl + C`.
2. Delete:

```text
app/data/emailtool.db
```

3. Start Uvicorn again.

The initial administrator from `.env` will be recreated.

## Important security notes

This version is designed much more seriously than a simple frontend login.

It includes:
- Password hashing instead of plain-text passwords.
- Random session tokens.
- Only a hash of the session token is stored in SQLite.
- HttpOnly cookies.
- SameSite cookies.
- CSRF checks.
- Server-side authorization.
- Generic invalid-login errors.
- Admin/user role separation.
- Account disabling that removes active sessions.
- Audit logging.
- Private bulk authorization on the backend.
- Input validation and result limits.

Before public production deployment:

1. Use HTTPS.
2. Set:

```env
COOKIE_SECURE=true
```

3. Replace the local development password.
4. Keep `.env` private.
5. Back up the SQLite database securely.
6. Add rate limiting at the application/reverse-proxy level.
7. Restrict CORS to your real domain if the frontend/API are separated.
8. Consider PostgreSQL instead of SQLite if you eventually have many concurrent users.

## Existing generator features

- 50+ built-in patterns
- Multiple domains
- Custom patterns
- Prefix/suffix/number variants
- Case modes
- Search
- Copy one/all
- TXT/CSV/XLSX/JSON export
- Responsive UI
- Dark mode
- Private server-side CSV bulk generation
- No email sending
- No mailbox verification

The project generates email-format candidates only. It does not send emails or verify whether a mailbox exists.

## Tests

Run:

```powershell
pytest
```

The authentication-protected API and normal generator are covered by automated tests.


## Netlify frontend + Render FastAPI deployment

This project is prepared to run with the frontend and backend on separate hosts.

### Frontend: Netlify

Use ONLY the contents of the `frontend` folder for the Netlify site. It contains:
- `index.html`
- `login.html`
- `admin.html`
- `config.js`
- `css/`
- `js/`
- `_redirects`

Before deploying, open `config.js` and change:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://YOUR-RENDER-SERVICE.onrender.com"
};
```

Do not put passwords or `.env` values in this file.

### Backend: Render

Deploy the project folder containing `app/` and `requirements.txt` to Render as a Python web service.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set these Render environment variables:

```text
ADMIN_EMAIL=dev.shahidshaikh@gmail.com
ADMIN_PASSWORD=CHANGE_THIS_BEFORE_PUBLIC_LAUNCH
COOKIE_SECURE=true
REQUIRE_APPROVAL_FOR_APP=true
FRONTEND_ORIGIN=https://YOUR-NETLIFY-SITE.netlify.app
```

The Render API must use HTTPS in production.

### Important database note

The default SQLite database is fine for local development, but a free/ephemeral cloud service may lose local files when the service is rebuilt/redeployed. For a real paid product, use persistent disk storage or PostgreSQL before relying on the account database for production customers.

### Frontend/API connection

All browser API calls are centralized in `frontend/config.js` and `frontend/js/api.js`. The HTML/CSS/JS does not contain admin passwords. The Python server remains the security authority.
