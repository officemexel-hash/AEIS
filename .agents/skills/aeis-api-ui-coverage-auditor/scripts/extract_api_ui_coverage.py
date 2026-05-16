from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
FRONTEND_APP = REPO_ROOT / "src" / "sylion-frontend" / "src" / "app" / "(app)"
API_CLIENT = REPO_ROOT / "src" / "sylion-frontend" / "src" / "lib" / "api" / "client.ts"
API_ROUTER = REPO_ROOT / "src" / "sylion-pipeline" / "sylion" / "api" / "router.py"


def route_pages() -> list[dict[str, str]]:
    pages: list[dict[str, str]] = []
    for page in sorted(FRONTEND_APP.rglob("page.tsx")):
        rel = page.relative_to(FRONTEND_APP).parent.as_posix()
        route = "/" if rel == "." else f"/{rel}"
        pages.append({"route": route, "path": str(page.relative_to(REPO_ROOT)).replace("\\", "/")})
    return pages


def api_paths() -> list[str]:
    if not API_CLIENT.exists():
        return []
    text = API_CLIENT.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(r'"/api/v1/[^"]+"|`/api/v1/[^`]+`', text)
    cleaned = []
    seen = set()
    for raw in matches:
        path = raw.strip('"`')
        if path not in seen:
            cleaned.append(path)
            seen.add(path)
    return cleaned


def routers() -> list[str]:
    if not API_ROUTER.exists():
        return []
    text = API_ROUTER.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(r"include_router\(([^)]+)\)", text)
    return [item.strip() for item in matches]


def main() -> None:
    payload = {
        "frontend_pages": route_pages(),
        "frontend_api_paths": api_paths(),
        "backend_router_mounts": routers(),
        "counts": {
            "frontend_pages": len(route_pages()),
            "frontend_api_paths": len(api_paths()),
            "backend_router_mounts": len(routers()),
        },
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

