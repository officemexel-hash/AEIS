from pathlib import Path


def test_operator_mobile_frontend_pages_exist():
    root = Path(__file__).resolve().parents[4] / "src" / "sylion-frontend" / "src" / "app" / "(app)" / "operator-mobile"
    expected = [
        root / "page.tsx",
        root / "queue" / "page.tsx",
        root / "queue" / "[ticketId]" / "page.tsx",
        root / "devices" / "page.tsx",
    ]

    for path in expected:
        assert path.exists(), f"missing operator mobile route: {path}"
