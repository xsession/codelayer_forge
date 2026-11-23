from __future__ import annotations

import os
import ipaddress
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path

try:
    from platformdirs import user_data_path
except ImportError:  # pragma: no cover - fallback for minimal/offline environments
    user_data_path = None


@dataclass(frozen=True)
class LocalConfig:
    data_dir: Path
    workspace: Path
    host: str = "127.0.0.1"
    port: int = 9010
    api_token: str | None = None
    allow_remote: bool = False

    def __post_init__(self) -> None:
        if not _is_loopback_host(self.host) and not self.allow_remote:
            raise ValueError(
                f"Refusing non-loopback Studio bind to {self.host!r}; pass --allow-remote explicitly"
            )
        if self.allow_remote and not (self.api_token or "").strip():
            raise ValueError("Remote Studio requires a non-empty API token")

    @classmethod
    def from_env(
        cls,
        *,
        data_dir: str | Path | None = None,
        workspace: str | Path | None = None,
        host: str | None = None,
        port: int | None = None,
        allow_remote: bool = False,
    ) -> "LocalConfig":
        if data_dir is None:
            data_dir = os.environ.get("EMBEDDYN_LOCAL_DATA_DIR") or os.environ.get("VSD_LOCAL_DATA_DIR")
        if data_dir is None:
            if user_data_path is not None:
                data_dir = user_data_path("embeddyn", "CodeLayer")
            else:
                data_dir = Path.home() / ".local" / "share" / "embeddyn"
        data_path = Path(data_dir).expanduser().resolve()

        if workspace is None:
            workspace = os.environ.get("EMBEDDYN_WORKSPACE") or os.environ.get("VSD_WORKSPACE", str(Path.cwd()))
        workspace_path = Path(workspace).expanduser().resolve()

        resolved_host = host or os.environ.get("EMBEDDYN_STUDIO_HOST") or os.environ.get("VSD_STUDIO_HOST", "127.0.0.1")
        resolved_port = int(port or os.environ.get("EMBEDDYN_STUDIO_PORT") or os.environ.get("VSD_STUDIO_PORT", "9010"))
        non_loopback = not _is_loopback_host(resolved_host)
        if non_loopback and not allow_remote:
            raise ValueError(
                f"Refusing non-loopback Studio bind to {resolved_host!r}; pass --allow-remote explicitly"
            )
        remote = bool(allow_remote or non_loopback)

        data_path.mkdir(parents=True, exist_ok=True)
        token = (os.environ.get("EMBEDDYN_STUDIO_TOKEN") or os.environ.get("VSD_STUDIO_TOKEN") or "").strip() or None
        if remote and not token:
            token = _load_or_create_token(data_path / "studio.token")

        return cls(
            data_dir=data_path,
            workspace=workspace_path,
            host=resolved_host,
            port=resolved_port,
            api_token=token,
            allow_remote=remote,
        )


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().strip("[]")
    if normalized.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _load_or_create_token(path: Path) -> str:
    token = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    if not token:
        token = secrets.token_urlsafe(32)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(token + "\n", encoding="utf-8")
        temporary.replace(path)
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return token
