import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _strip_wrapping_quotes(value: str) -> str:
    text = (value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1].strip()
    return text


def _parse_env_assignment(line: str):
    text = (line or "").strip()
    if not text or text.startswith("#"):
        return None

    powershell_match = re.match(r"^\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", text)
    if powershell_match:
        return powershell_match.group(1), _strip_wrapping_quotes(
            powershell_match.group(2)
        )

    setx_match = re.match(
        r"^setx\s+([A-Za-z_][A-Za-z0-9_]*)\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if setx_match:
        return setx_match.group(1), _strip_wrapping_quotes(setx_match.group(2))

    simple_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", text)
    if simple_match:
        return simple_match.group(1), _strip_wrapping_quotes(simple_match.group(2))

    return None


def _load_local_env_defaults() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    try:
        lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return
    for line in lines:
        parsed = _parse_env_assignment(line)
        if not parsed:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def _to_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes"}


def _to_float(
    value: str | None,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if value is None:
        parsed = default
    else:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _resolve_model_path(model_dir: Path) -> Path:
    for candidate in (
        "tomato_cnn.keras",
        "trained_plant_disease_model.keras",
        "tomato_cnn.h5",
    ):
        resolved_path = model_dir / candidate
        if resolved_path.exists():
            return resolved_path
    return model_dir / "tomato_cnn.keras"


_load_local_env_defaults()


class Config:
    _secret_key = (os.environ.get("SECRET_KEY") or "").strip()
    if not _secret_key:
        raise RuntimeError(
            "SECRET_KEY is required. Set SECRET_KEY in environment or .env with at least 32 characters."
        )
    if len(_secret_key) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters long.")
    SECRET_KEY = _secret_key
    SMTP_HOST = (os.environ.get("SMTP_HOST") or "").strip()
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = (os.environ.get("SMTP_USER") or "").strip()
    SMTP_PASSWORD = "".join((os.environ.get("SMTP_PASSWORD") or "").split())
    SMTP_USE_TLS = _to_bool(os.environ.get("SMTP_USE_TLS"), default=True)
    SMTP_USE_SSL = _to_bool(os.environ.get("SMTP_USE_SSL"), default=False)
    MAIL_FROM = (
        (os.environ.get("MAIL_FROM") or "").strip() or SMTP_USER or "no-reply@localhost"
    )
    CONTACT_RECEIVER = (os.environ.get("CONTACT_RECEIVER") or "").strip() or MAIL_FROM
    RESET_TOKEN_MAX_AGE = int(os.environ.get("RESET_TOKEN_MAX_AGE", "3600"))
    PASSWORD_RESET_LINK_FALLBACK = _to_bool(
        os.environ.get("PASSWORD_RESET_LINK_FALLBACK"), default=False
    )
    EMAIL_FILE_FALLBACK = _to_bool(os.environ.get("EMAIL_FILE_FALLBACK"), default=False)

    _database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not _database_url:
        raise RuntimeError(
            "PostgreSQL is required. Set DATABASE_URL (or POSTGRES_URL), e.g. "
            "postgresql://USER:PASSWORD@localhost:5432/tomato_care"
        )
    if _database_url.startswith("postgres://"):
        _database_url = "postgresql://" + _database_url[len("postgres://") :]

    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    UPLOAD_FOLDER = BASE_DIR / "uploads"

    LEAF_GATE_MIN_FOLIAGE_RATIO = _to_float(
        os.environ.get("LEAF_GATE_MIN_FOLIAGE_RATIO"),
        0.25,
        minimum=0.0,
        maximum=1.0,
    )
    LEAF_GATE_MIN_LARGEST_COMPONENT_RATIO = _to_float(
        os.environ.get("LEAF_GATE_MIN_LARGEST_COMPONENT_RATIO"),
        0.25,
        minimum=0.0,
        maximum=1.0,
    )
    LEAF_GATE_MAX_COMPONENT_COMPLEXITY = _to_float(
        os.environ.get("LEAF_GATE_MAX_COMPONENT_COMPLEXITY"),
        9.0,
        minimum=0.0,
    )
    LEAF_GATE_MIN_EDGE_RATIO = _to_float(
        os.environ.get("LEAF_GATE_MIN_EDGE_RATIO"),
        0.015,
        minimum=0.0,
        maximum=1.0,
    )
    MODEL_PATH = _resolve_model_path(BASE_DIR / "models")
