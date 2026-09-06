# Remote Pay Guide OS — Local Control Center

Remote Pay Guide OS runs on the user's computer as the control center. The AI production path is **remote**: the OS calls an AI Gateway / relay / external AI service. This is not a local GPU/model inference architecture.

The legacy GitHub production and publishing pipeline remains separate and compatible.

## Local Services

The current development setup uses:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- YouTube OAuth callback: `http://localhost:5173/oauth/youtube/callback`
- OS database: `os/database/os.db`

## Start the Backend

From the repository root in PowerShell:

```powershell
python -m pip install -r os/backend/requirements.txt
python -m uvicorn main:app --app-dir os/backend --host 127.0.0.1 --port 8000
```

The backend exposes `/health` and the control-center APIs for production, publish tasks, accounts, OAuth, analytics, and Data Center data.

## Start the Frontend

Open a second PowerShell window:

```powershell
cd os/frontend
npm install
npm run dev -- --host 127.0.0.1
```

Then open:

```text
http://localhost:5173
```

The backend allows the local Vite origins `http://localhost:5173` and `http://127.0.0.1:5173` by default. Additional frontend origins can be supplied with `OS_FRONTEND_ORIGINS`.

## YouTube OAuth Configuration

Reuse the existing Google OAuth **Web Application** client. Add the OS callback URI alongside any existing Postiz redirect URI:

```text
http://localhost:5173/oauth/youtube/callback
```

Before starting the backend, set the OAuth configuration in that PowerShell session:

```powershell
$env:YOUTUBE_OAUTH_CLIENT_ID="<client-id>"
$env:YOUTUBE_OAUTH_CLIENT_SECRET="<client-secret>"
$env:YOUTUBE_OAUTH_REDIRECT_URI="http://localhost:5173/oauth/youtube/callback"
```

Do not commit real client-secret values to the repository.

The control center can check configuration through `/oauth/youtube/status`. When configured, **Connect YouTube (Publish + Analytics)** requests the explicit `full` scope profile. Existing upload-only credentials are not silently upgraded.

## Publish → Traffic Flow

For a published YouTube task with a platform video ID and account binding, the control center can trigger analytics collection through:

```text
POST /analytics/collector/collect/publish-task/{task_id}
```

The bridge reads the existing Publish Center task, calls the external analytics collector, and stores the returned snapshot in the existing Data Center. It does not create a second publish database or a second analytics store.

## External Authorization Boundary

Code and local control-center wiring can be verified without external credentials. Real YouTube analytics still requires:

1. The OAuth Web Application to allow the OS callback URI.
2. The backend process to have the OAuth client configuration.
3. The user to complete Google consent for the full YouTube scopes.

No real OAuth consent or live YouTube analytics request is performed by repository CI.
