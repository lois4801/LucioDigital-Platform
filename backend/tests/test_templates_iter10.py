"""Iteration 10: 18 industry templates + apply + export starter."""
import os, io, zipfile, pytest, requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
EMAIL = "jaybernabe@luciodigital.com"
PASSWORD = "Lucio2026!"

EXPECTED_KEYS = ["health_safety","construction","hvac","plumbing","carpentry","electrical","retail",
                 "hospitality","fitness","finance","it_services","real_estate","education","healthcare",
                 "legal","restaurant","events","logistics"]

EXPECTED_PRIMARY = {
    "health_safety": "#F59E0B", "construction": "#F97316", "hvac": "#0284C7", "plumbing": "#2563EB",
    "carpentry": "#92400E", "electrical": "#65A30D", "retail": "#7C3AED", "hospitality": "#C2410C",
    "fitness": "#16A34A", "finance": "#1E3A8A", "it_services": "#4F46E5", "real_estate": "#059669",
    "education": "#0891B2", "healthcare": "#0D9488", "legal": "#334155", "restaurant": "#DC2626",
    "events": "#9333EA", "logistics": "#F59E0B",
}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    assert s.cookies.get("access_token"), "no access_token cookie set"
    return s


@pytest.fixture(scope="module")
def app_id(client):
    r = client.post(f"{BASE_URL}/api/apps", json={"name": "TEST_iter10_templates", "kind": "app", "industry": "Healthcare"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    aid = r.json().get("app_id") or r.json().get("id")
    assert aid
    yield aid
    try:
        client.delete(f"{BASE_URL}/api/apps/{aid}", timeout=30)
    except Exception:
        pass


def test_templates_list_has_18(client):
    r = client.get(f"{BASE_URL}/api/templates", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 18, f"expected 18 templates, got {len(data)}"
    keys = {t["key"] for t in data}
    assert keys == set(EXPECTED_KEYS)
    for t in data:
        for f in ("key", "name", "industry", "primary", "secondary", "screens", "models", "suite"):
            assert f in t, f"template {t.get('key')} missing {f}"


def test_apply_unknown_template_404(client, app_id):
    r = client.post(f"{BASE_URL}/api/apps/{app_id}/templates/does_not_exist/apply", timeout=30)
    assert r.status_code == 404


@pytest.mark.parametrize("key", EXPECTED_KEYS)
def test_apply_template(client, app_id, key):
    r = client.post(f"{BASE_URL}/api/apps/{app_id}/templates/{key}/apply", timeout=60)
    assert r.status_code == 200, f"{key}: {r.status_code} {r.text}"
    data = r.json()
    assert "spec" in data and "theme" in data
    spec = data["spec"]
    for f in ("screens", "models", "api", "palette"):
        assert f in spec, f"{key} spec missing {f}"
    assert isinstance(spec["screens"], list) and len(spec["screens"]) > 0
    assert isinstance(spec["models"], list) and len(spec["models"]) > 0
    theme = data["theme"]
    assert theme.get("mode") == "light", f"{key} theme mode: {theme.get('mode')}"
    assert theme.get("primary", "").upper() == EXPECTED_PRIMARY[key].upper(), f"{key} primary: {theme.get('primary')}"


def test_export_starter_after_healthcare(client, app_id):
    # apply healthcare (teal #0D9488) then export
    r = client.post(f"{BASE_URL}/api/apps/{app_id}/templates/healthcare/apply", timeout=60)
    assert r.status_code == 200
    r = client.get(f"{BASE_URL}/api/apps/{app_id}/export/source", timeout=120)
    assert r.status_code == 200
    assert "zip" in r.headers.get("content-type", "").lower() or r.content[:2] == b"PK"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    # Locate files (may be nested under a top-level dir)
    def find(suffix):
        for n in names:
            if n.endswith(suffix):
                return n
        return None
    css_path = find("frontend/src/styles.css")
    app_path = find("frontend/src/App.jsx")
    theme_path = find("frontend/src/theme.json")
    assert css_path, f"styles.css missing. files={names[:20]}"
    assert app_path, "App.jsx missing"
    assert theme_path, "theme.json missing"
    css = z.read(css_path).decode()
    assert "--p:#0D9488" in css, f"--p not teal: {css[:200]}"
    assert ".sidebar" in css and "position:fixed" in css
    appjsx = z.read(app_path).decode()
    assert "NavLink" in appjsx and "Breadcrumbs" in appjsx
    import json as _j
    theme = _j.loads(z.read(theme_path))
    assert theme.get("layout") == "fixed-left-sidebar"
    assert theme.get("mode") == "light"
