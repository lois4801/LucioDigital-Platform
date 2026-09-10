"""Iter75 — Restore template looks/imagery/motions while preserving content."""
import os, re, pytest, requests
from collections import Counter

def _load_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v.strip('"'))
_load_env()
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

SAMPLE_KEYS = ["hvac", "healthcare", "legal", "restaurant", "saas", "construction", "fitness", "retail"]


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def templates():
    r = requests.get(f"{BASE}/api/public/templates", timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("templates") or j


def test_33_templates(templates):
    assert len(templates) == 33, f"expected 33 got {len(templates)}"


def test_palette_diversity(templates):
    primaries = [str(t.get("primary") or "").lower() for t in templates if t.get("primary")]
    fonts = [str(t.get("font_heading") or "") for t in templates if t.get("font_heading")]
    radii = [t.get("radius") for t in templates if t.get("radius") is not None]
    modes = [t.get("mode") for t in templates]
    uniq_primaries = len(set(primaries))
    uniq_fonts = len(set(fonts))
    print(f"primaries {len(primaries)} unique={uniq_primaries}; fonts unique={uniq_fonts}; radii unique={len(set(radii))}; modes={Counter(modes)}")
    print(f"sample primaries: {sorted(set(primaries))[:10]}")
    print(f"sample fonts: {sorted(set(fonts))}")
    assert uniq_primaries >= 25, f"only {uniq_primaries} distinct primary colors (spec: ~29)"
    assert uniq_fonts >= 9, f"only {uniq_fonts} distinct heading fonts (spec: ~11)"
    assert "light" in modes and "dark" in modes, f"expected mix of light+dark, got {Counter(modes)}"


UNSPLASH_RE = re.compile(r"images\.unsplash\.com/(?:photo-([a-zA-Z0-9_-]+)|[^\"' )]+)")


def _collect_images(obj, out):
    if isinstance(obj, dict):
        for v in obj.values():
            _collect_images(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_images(v, out)
    elif isinstance(obj, str):
        for m in UNSPLASH_RE.finditer(obj):
            out.append(m.group(0))


@pytest.mark.parametrize("key", SAMPLE_KEYS)
def test_template_has_images(key):
    r = requests.get(f"{BASE}/api/public/templates/{key}", timeout=30)
    assert r.status_code == 200, f"{key} => {r.status_code}"
    data = r.json()
    images = []
    _collect_images(data, images)
    uniq = set(images)
    print(f"{key}: {len(images)} refs, {len(uniq)} distinct unsplash images")
    assert len(uniq) >= 8, f"{key} only has {len(uniq)} distinct images (expected ~9+)"


def test_team_photos_unique_within_and_across_templates(templates):
    # Fetch each template and gather team photos
    per_template = {}
    all_team_photos = []
    for t in templates:
        key = t.get("key") or t.get("id") or t.get("slug")
        if not key: continue
        r = requests.get(f"{BASE}/api/public/templates/{key}", timeout=30)
        if r.status_code != 200: continue
        data = r.json()
        # find team section - look for blocks with kind/type containing 'team'
        team_photos = []
        def walk(o):
            if isinstance(o, dict):
                kind = str(o.get("kind") or o.get("type") or "").lower()
                if "team" in kind:
                    imgs = []
                    _collect_images(o, imgs)
                    team_photos.extend(imgs)
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(data)
        if team_photos:
            per_template[key] = team_photos
            all_team_photos.extend([(key, p) for p in team_photos])

    print(f"templates with team sections: {len(per_template)}")
    dup_within = {k: [p for p, c in Counter(v).items() if c > 1] for k, v in per_template.items() if len(set(v)) != len(v)}
    if dup_within:
        print(f"DUP WITHIN: {dup_within}")

    # cross-template overlap
    photo_owners = {}
    cross = []
    for k, p in all_team_photos:
        if p in photo_owners and photo_owners[p] != k:
            cross.append((p, photo_owners[p], k))
        else:
            photo_owners[p] = k
    print(f"cross-template team photo overlaps: {len(cross)}")
    if cross:
        for c in cross[:5]: print("  ", c)
    # Not making assertion fatal - report only
    assert len(cross) == 0, f"{len(cross)} cross-template team photo overlaps (spec: zero)"


def test_content_preserved_pages_blocks(templates):
    for t in templates[:5]:
        key = t.get("key") or t.get("id")
        r = requests.get(f"{BASE}/api/public/templates/{key}", timeout=30)
        assert r.status_code == 200
        data = r.json()
        pages = data.get("pages") or []
        assert len(pages) == 4, f"{key} has {len(pages)} pages"
        # Hero must have title/badge/subtitle/cta
        for pg in pages:
            for b in pg.get("blocks", []):
                if str(b.get("kind") or b.get("type") or "").lower().startswith("hero"):
                    props = b.get("props") or b.get("data") or b
                    keys = str(props).lower()
                    assert "title" in keys or "headline" in keys, f"{key} hero missing title"


def test_testlab_site_content_preserved():
    r = requests.get(f"{BASE}/api/public/site/pv_c3b797fcdafc58d4e70e320f", timeout=30)
    assert r.status_code == 200, r.status_code
    data = r.json()
    pages = data.get("pages") or []
    total_blocks = sum(len(p.get("blocks") or []) for p in pages)
    print(f"testlab pages={len(pages)} blocks={total_blocks}")
    assert len(pages) == 33, f"expected 33 pages got {len(pages)}"
    assert total_blocks == 366, f"expected 366 blocks got {total_blocks}"


def test_rollout_status_all_live(auth_session):
    r = auth_session.get(f"{BASE}/api/templates/rollout-status", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data.get("pending", -1) == 0, f"pending={data.get('pending')}"
    templates = data.get("templates") or []
    non_live = [t for t in templates if t.get("status") != "live"]
    assert not non_live, f"non-live templates: {non_live[:3]}"


def test_testlab_pending_zero(auth_session):
    r = auth_session.get(f"{BASE}/api/test-lab/pending", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data.get("total", -1) == 0, f"testlab pending: {data}"


def test_auto_propagate_run(auth_session):
    r = auth_session.post(f"{BASE}/api/auto-propagate/run", timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert data.get("templates") == 33, data


def test_motion_reel_distinct():
    r = requests.get(f"{BASE}/api/public/motion-reel", timeout=30)
    assert r.status_code == 200
    data = r.json()
    heroes = data.get("heroes") or []
    motions = [h.get("hero") for h in heroes]
    print(f"motion-reel heroes={len(heroes)} distinct={len(set(motions))} total={data.get('total')} active={data.get('active')} reserved={data.get('reserved')}")
    assert len(heroes) >= 33
    assert len(set(motions)) >= 33, f"only {len(set(motions))} distinct hero motions"
