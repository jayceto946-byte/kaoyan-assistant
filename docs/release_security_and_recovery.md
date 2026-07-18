# Release, security, and recovery baseline

## Product version

`VERSION` is the product version source. The current release is `1.0.0`.

To prepare a later version:

```powershell
.\venv310\Scripts\python.exe scripts\set_version.py 1.0.1
.\venv310\Scripts\python.exe scripts\check_version_consistency.py
```

Create the Git tag with the same `v`-prefixed value. The desktop release workflow rejects a tag that does not match `VERSION`, and runs backend tests, frontend tests, lint, and the production build before publishing.

For signed Windows installers, configure these GitHub repository secrets:

- `WINDOWS_CSC_LINK`: base64 certificate or supported certificate URL.
- `WINDOWS_CSC_KEY_PASSWORD`: certificate password.

Without those external credentials, the workflow can build an installer but cannot establish a trusted Windows publisher identity.

## Backup and restore

Open **设置 → 备份恢复** in the desktop app.

- A normal backup contains textbooks, chapters, images, mistake/exercise databases, and learning records.
- API keys and `.env` are never included.
- The optional derived-data switch also includes Chroma and MinerU artifacts.
- Every archive contains a versioned manifest and is verified after creation.
- Restore first creates a safety backup of the current state, then schedules the selected archive for the next restart.
- Restore is applied before model/vector warmup. If replacement fails, the previous directories are moved back automatically.

Desktop backups are stored beside the desktop data directory. Source/Docker mode defaults to `./backups`; override with `BACKUP_PATH` when needed.

## API access boundary

Electron listens on loopback and does not require a token. Docker Compose also publishes port 8000 only on `127.0.0.1` by default.

To intentionally expose the application through a LAN or reverse proxy:

1. Set a long random `KAOYAN_API_TOKEN` on the server.
2. Do not enable `KAOYAN_ALLOW_PRIVATE_CLIENTS` on a LAN-facing deployment.
3. Open the web client once with `#access_token=YOUR_TOKEN` appended to the URL. The fragment is stored locally by the browser and is not sent in the URL to the server.
4. Use HTTPS when traffic leaves the local machine.

Remote API requests without a configured token are rejected. Set `KAOYAN_REQUIRE_API_TOKEN=1` only when token authentication should also apply to loopback requests.
