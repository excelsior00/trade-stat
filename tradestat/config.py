"""설정(settings.yaml)과 환경변수(.env) 로딩."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DOCS_DATA_DIR = ROOT / "docs" / "data"


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


@lru_cache
def settings() -> dict:
    with open(ROOT / "config" / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def env(name: str, required: bool = False) -> str:
    v = os.environ.get(name, "").strip()
    if required and not v:
        raise SystemExit(f"환경변수 {name} 가 설정되지 않았습니다 (.env 또는 GitHub Secrets).")
    return v


def service_key() -> str:
    # 포털의 Encoding 키를 넣어도 requests가 다시 인코딩하므로 한 번 디코딩해 둔다.
    return unquote(env("DATA_GO_KR_KEY", required=True))
