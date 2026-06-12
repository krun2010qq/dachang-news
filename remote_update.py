"""Quick code-only update for dachang-news."""

from __future__ import annotations

import os
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

PROJECT_DIR = Path(__file__).resolve().parent
REMOTE_DIR = "/opt/dachang-news"
PASSWORD_FILE = PROJECT_DIR / ".deploy_password"
DEFAULT_HOST = "49.51.195.205"
EXCLUDE = {".venv", ".git", "__pycache__", ".deploy_password", "deploy_remote.py", "data"}


def read_password() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    if os.environ.get("DEPLOY_PASSWORD"):
        return os.environ["DEPLOY_PASSWORD"]
    if PASSWORD_FILE.exists():
        return PASSWORD_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit("Provide password via DEPLOY_PASSWORD, .deploy_password, or argv")


def build_archive() -> Path:
    tmp = Path(tempfile.gettempdir()) / "dachang-news-update.tar.gz"
    with tarfile.open(tmp, "w:gz") as archive:
        for path in PROJECT_DIR.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(PROJECT_DIR)
            if any(part in EXCLUDE for part in rel.parts):
                continue
            archive.add(path, arcname=str(rel))
    return tmp


def main() -> None:
    password = read_password()
    host = os.environ.get("DEPLOY_HOST", DEFAULT_HOST)
    user = os.environ.get("DEPLOY_USER", "root")
    archive = build_archive()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=20)

    sftp = client.open_sftp()
    remote_archive = "/tmp/dachang-news-update.tar.gz"
    sftp.put(str(archive), remote_archive)
    sftp.close()

    cmd = f"""
set -e
tar -xzf {remote_archive} -C {REMOTE_DIR}
rm -f {remote_archive}
systemctl restart dachang-news
sleep 2
curl -s http://127.0.0.1:8080/api/health
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(err)
    client.close()
    print(f"Update complete: http://{host}:8080/")


if __name__ == "__main__":
    main()
