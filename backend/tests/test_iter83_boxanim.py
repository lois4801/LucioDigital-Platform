"""Iteration 83 — PowerPoint-style content box animations.
Tests PUT/GET /api/apps/{id}/site-mode {box_anim}: 18 valid keys, rejection of unknown,
GET returns box_anim + options.box_anims. Empty string clears (inherit from template)."""
import os
import pytest
import requests

def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return ""

BASE_URL = _load_url()
API = f"{BASE_URL}/api"
APP_ID = "app_testlab"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}

VALID_KEYS = ("appear", "fade", "fly-in", "float-in", "split", "wipe", "shape", "wheel",
              "random-bars", "grow-turn", "zoom", "swivel", "bounce", "pulse", "spin",
              "grow-shrink", "teeter", "dissolve", "blinds", "checkerboard", "box-in",
              "plus-in", "diamond", "peek-in", "rise-up", "stretch", "compress", "whip",
              "spiral-in", "darken", "lighten", "desaturate", "transparency", "wave",
              "bold-flash", "bold-reveal", "color-pulse", "credits", "none")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    # Session cookie-based auth is applied automatically to `s`.
    yield s
    # teardown — clear box_anim so tenant inherits template default
    s.put(f"{API}/apps/{APP_ID}/site-mode", json={"box_anim": ""}, timeout=20)


def test_get_returns_box_anim_and_options(client):
    r = client.get(f"{API}/apps/{APP_ID}/site-mode", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "box_anim" in data
    opts = data.get("options") or {}
    box_anims = opts.get("box_anims") or []
    assert len(box_anims) == 39, f"expected 39 options, got {len(box_anims)}: {box_anims}"
    assert set(box_anims) == set(VALID_KEYS)


@pytest.mark.parametrize("key", VALID_KEYS)
def test_put_accepts_each_valid_key(client, key):
    r = client.put(f"{API}/apps/{APP_ID}/site-mode", json={"box_anim": key}, timeout=20)
    assert r.status_code == 200, f"{key}: {r.status_code} {r.text[:200]}"
    # Verify persistence via GET
    g = client.get(f"{API}/apps/{APP_ID}/site-mode", timeout=20)
    assert g.status_code == 200
    assert g.json().get("box_anim") == key, f"persistence failed for {key}: {g.json().get('box_anim')}"


def test_put_rejects_unknown_key(client):
    r = client.put(f"{API}/apps/{APP_ID}/site-mode", json={"box_anim": "wobble-xyz"}, timeout=20)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
    detail = (r.json().get("detail") or "").lower()
    assert "unknown" in detail and "box" in detail, f"bad detail: {detail}"


def test_empty_string_clears_override(client):
    # First set to bounce
    client.put(f"{API}/apps/{APP_ID}/site-mode", json={"box_anim": "bounce"}, timeout=20)
    # Empty string via model_dump(exclude_none=True) keeps empty string in patch
    r = client.put(f"{API}/apps/{APP_ID}/site-mode", json={"box_anim": ""}, timeout=20)
    assert r.status_code == 200, r.text
    g = client.get(f"{API}/apps/{APP_ID}/site-mode", timeout=20)
    assert g.json().get("box_anim") == "", f"expected empty (inherit), got {g.json().get('box_anim')}"


def test_public_site_carries_box_anim(client):
    # set bounce, then read the public site payload
    client.put(f"{API}/apps/{APP_ID}/site-mode", json={"box_anim": "bounce"}, timeout=20)
    sm = client.get(f"{API}/apps/{APP_ID}/site-mode", timeout=20).json()
    token = sm.get("preview_token")
    assert token, "no preview_token"
    # public endpoint
    pub = requests.get(f"{API}/public/site/{token}", timeout=20)
    assert pub.status_code == 200, pub.text[:200]
    j = pub.json()
    app_block = j.get("app") or j.get("site") or j
    smode = (app_block.get("site_mode") if isinstance(app_block, dict) else None) or j.get("site_mode") or {}
    assert smode.get("box_anim") == "bounce", f"public payload missing box_anim=bounce: {smode}"
