"""Deploy dachang-news to remote Linux server via SFTP + SSH."""

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
    tmp = Path(tempfile.gettempdir()) / "dachang-news.tar.gz"
    with tarfile.open(tmp, "w:gz") as archive:
        for path in PROJECT_DIR.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(PROJECT_DIR)
            if any(part in EXCLUDE for part in rel.parts):
                continue
            archive.add(path, arcname=str(rel))
    return tmp


def run(client: paramiko.SSHClient, command: str) -> None:
    print(f"$ {command}")
    _, stdout, stderr = client.exec_command(command, get_pty=True)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out.strip().encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print(err.strip().encode("ascii", "replace").decode("ascii"))
    if exit_code != 0:
        raise RuntimeError(f"Command failed ({exit_code}): {command}")


def main() -> None:
    password = read_password()
    host = os.environ.get("DEPLOY_HOST", DEFAULT_HOST)
    user = os.environ.get("DEPLOY_USER", "root")
    archive = build_archive()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {user}@{host} ...")
    client.connect(host, username=user, password=password, timeout=20)

    sftp = client.open_sftp()
    remote_archive = "/tmp/dachang-news.tar.gz"
    print(f"Uploading {archive} ...")
    sftp.put(str(archive), remote_archive)
    sftp.close()

    commands = f"""
set -e
mkdir -p {REMOTE_DIR}/data
tar -xzf {remote_archive} -C {REMOTE_DIR}
rm -f {remote_archive}
if ! command -v python3 >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip nginx
  elif command -v yum >/dev/null 2>&1; then
    yum install -y python3 python3-pip nginx
  fi
fi
python3 -m venv {REMOTE_DIR}/.venv
{REMOTE_DIR}/.venv/bin/pip install --upgrade pip
{REMOTE_DIR}/.venv/bin/pip install -r {REMOTE_DIR}/requirements.txt
cp {REMOTE_DIR}/deploy/dachang-news.service /etc/systemd/system/dachang-news.service
cp {REMOTE_DIR}/deploy/nginx-dachang-news.conf /etc/nginx/conf.d/dachang-news.conf
systemctl daemon-reload
systemctl enable dachang-news
cp {REMOTE_DIR}/deploy/dachang-news.service /etc/systemd/system/dachang-news.service
systemctl daemon-reload
systemctl restart dachang-news
nginx -t
bash {REMOTE_DIR}/deploy/patch-nginx-path.sh
systemctl reload nginx
firewall-cmd --permanent --add-port=8080/tcp 2>/dev/null || true
firewall-cmd --reload 2>/dev/null || true
sleep 3
curl -s --max-time 10 http://127.0.0.1:8080/api/health || true
"""
    run(client, commands.strip())
    client.close()
    print(f"Deployment complete: http://{host}:8080/")


if __name__ == "__main__":
    main()
