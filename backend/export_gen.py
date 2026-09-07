import json
import re
from typing import List, Dict, Any

FONT_URL = "https://fonts.googleapis.com/css2?family={h}:wght@500;600;700;800&family={b}:wght@400;500;600&display=swap"
ICON_SVG = "<svg width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'><path d='M12 2l3 7h7l-5.5 4.5L18 21l-6-4-6 4 1.5-7.5L2 9h7z'/></svg>"


def esc(s) -> str:
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def css(theme: dict) -> str:
    dark = theme.get("mode") == "dark"
    def darkish(h):
        try:
            return int(h[1:3], 16) * .299 + int(h[3:5], 16) * .587 + int(h[5:7], 16) * .114 < 128
        except Exception:
            return False
    bg = theme.get("bg", "#0A0A0F") if darkish(theme.get("bg", "")) else "#0A0A0F"
    sf = theme.get("surface", "#141420") if darkish(theme.get("surface", "")) else "#141420"
    bd = theme.get("border", "#262637") if darkish(theme.get("border", "")) else "#262637"
    grain = "" if theme.get("grain") is False else "body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:9998;opacity:.07;mix-blend-mode:overlay;background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")}"
    return f"""
:root{{--p:{theme['primary']};--s:{theme['secondary']};--bg:{bg if dark else theme['bg']};--sf:{sf if dark else theme['surface']};--fg:{'#F8FAFC' if dark else theme['fg']};--mut:{'#A1A7B8' if dark else theme['muted']};--bd:{bd if dark else theme['border']};--glass:{'rgba(255,255,255,.04)' if dark else 'rgba(255,255,255,.6)'};--r:{theme['radius']}px}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font-family:'{theme['font_body']}',system-ui,sans-serif;-webkit-font-smoothing:antialiased}}{grain}
h1,h2,h3,h4{{font-family:'{theme['font_heading']}',sans-serif;letter-spacing:-0.02em;margin:0;line-height:1.1}}
a{{color:inherit;text-decoration:none}}.wrap{{max-width:1120px;margin:0 auto;padding:0 24px}}
section{{padding:80px 0;position:relative}}section.sm{{padding:44px 0}}section.lg{{padding:120px 0}}section.muted{{background:var(--sf) radial-gradient(900px 300px at 85% 0%,color-mix(in srgb,var(--p) 9%,transparent),transparent)}}section.accent{{background:var(--p);color:#fff}}section.dark{{background:#0F172A;color:#fff}}
section.accent .mut,section.dark .mut{{color:rgba(255,255,255,.8)}}.center{{text-align:center}}.mut{{color:var(--mut)}}.kicker{{color:var(--p);font-size:12px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:12px}}
.btn{{display:inline-block;background:var(--p);color:#fff;padding:14px 26px;border-radius:999px;font-weight:600;transition:transform .15s;box-shadow:0 10px 30px -12px var(--p)}}.btn:hover{{transform:translateY(-2px)}}
.btn2{{display:inline-block;border:1px solid var(--bd);background:var(--glass);backdrop-filter:blur(12px);padding:13px 26px;border-radius:999px;font-weight:600;margin-left:10px}}
.grid{{display:grid;gap:24px}}.g2{{grid-template-columns:repeat(2,1fr)}}.g3{{grid-template-columns:repeat(3,1fr)}}.g4{{grid-template-columns:repeat(4,1fr)}}
@media(max-width:860px){{.g2,.g3,.g4{{grid-template-columns:1fr}}}}
.card{{background:var(--glass);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid var(--bd);border-radius:var(--r);padding:28px;transition:transform .3s,border-color .3s,box-shadow .3s}}.card:hover{{transform:translateY(-4px);border-color:color-mix(in srgb,var(--p) 45%,var(--bd));box-shadow:0 0 0 1px color-mix(in srgb,var(--p) 25%,transparent),0 30px 80px -40px var(--p)}}
nav{{display:flex;align-items:center;justify-content:space-between;padding:18px 0}}nav .links a{{margin:0 14px;color:var(--mut);font-weight:500}}
.brand{{font-family:'{theme['font_heading']}';font-weight:800;font-size:20px}}
.hero h1{{font-size:clamp(40px,6vw,68px);font-weight:800}}.hero p{{font-size:20px;max-width:640px;margin:20px auto 0}}.hero .center p{{margin-left:auto;margin-right:auto}}
.hero.cover{{padding:150px 0 120px;color:#fff;overflow:hidden;isolation:isolate}}.hero.cover>img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:-2}}.hero.cover::before{{content:'';position:absolute;inset:0;z-index:-1;background:linear-gradient(105deg,var(--bg) 0%,color-mix(in srgb,var(--bg) 82%,transparent) 45%,color-mix(in srgb,var(--bg) 30%,transparent) 100%),linear-gradient(180deg,transparent 40%,var(--bg) 100%)}}.hero.cover .mut{{color:rgba(255,255,255,.8)}}
.badge{{display:inline-block;background:color-mix(in srgb,var(--s) 15%,transparent);border:1px solid color-mix(in srgb,var(--s) 35%,transparent);color:var(--s);padding:6px 14px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}}
.ico{{width:44px;height:44px;border-radius:12px;background:color-mix(in srgb,var(--p) 15%,transparent);color:var(--p);display:flex;align-items:center;justify-content:center;margin-bottom:16px;box-shadow:0 0 24px -6px var(--p)}}
.price{{font-size:44px;font-weight:800}}.hl{{border-color:var(--p);box-shadow:0 20px 60px -30px var(--p)}}.stat{{font-size:40px;font-weight:800;color:var(--p);font-family:'{theme['font_heading']}'}}
ul{{list-style:none;padding:0;margin:0}}li{{padding:6px 0;color:var(--mut)}}
.faq details{{border-bottom:1px solid var(--bd);padding:18px 0}}.faq summary{{font-weight:600;cursor:pointer;font-size:18px}}
.bar{{height:180px;display:flex;align-items:flex-end;gap:10px}}.bar span{{flex:1;background:linear-gradient(180deg,var(--p),var(--s));border-radius:8px 8px 0 0}}
img.g{{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:var(--r);border:1px solid var(--bd);transition:transform .5s}}img.g:hover{{transform:scale(1.02)}}img.tm{{width:100%;aspect-ratio:1;object-fit:cover;border-radius:calc(var(--r) - 6px);margin-bottom:14px}}
.yt{{width:100%;aspect-ratio:16/9;border:1px solid var(--bd);border-radius:var(--r);margin-top:28px;background:#000}}
footer{{padding:56px 0;border-top:1px solid var(--bd)}}footer h4{{font-size:14px;margin-bottom:12px}}
.logos{{display:flex;flex-wrap:wrap;gap:36px;justify-content:center;font-weight:700;color:var(--mut);font-size:20px}}
.chat-fab{{position:fixed;right:24px;bottom:24px;background:var(--p);color:#fff;border-radius:999px;padding:14px 20px;font-weight:600;box-shadow:0 12px 40px -10px var(--p)}}
""" + FX_CSS


def render_block(b: dict, pages_nav: str, cols: List[dict] = None) -> str:
    t, p, s = b.get("type"), b.get("props", {}), b.get("style", {}) or {}
    cls = " ".join(filter(None, [s.get("bg") if s.get("bg") in ("muted", "accent", "dark") else "", s.get("padding") if s.get("padding") in ("sm", "lg") else "", "center" if s.get("align") == "center" else ""]))
    if t == "collection_list":
        col = next((c for c in (cols or []) if c["slug"] == p.get("collection")), None)
        items = (col or {}).get("items", [])[: int(p.get("limit") or 6)]
        cards = "".join(f"<a class='card' href='{col['slug']}/{it['slug']}.html' style='display:block'>" + (f"<img class='g' src='{esc(it['cover'])}' alt='' style='aspect-ratio:16/9;margin-bottom:14px'>" if it.get("cover") else "") +
                        f"<p class='mut' style='font-size:12px'>{esc(it.get('date'))}</p><h3 style='font-size:20px;margin-top:6px'>{esc(it['title'])}</h3><p class='mut' style='margin-top:8px'>{esc(it.get('excerpt'))}</p></a>" for it in items)
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='grid g3' style='margin-top:32px'>{cards or '<p class=mut>No published items yet.</p>'}</div></div></section>"
    if t == "collection_detail":
        return ""
    if t == "navbar":
        links = "".join(f"<a href='{esc(l.get('href','#'))}'>{esc(l.get('label'))}</a>" for l in p.get("links", []))
        logo = f"<img src='{esc(p['logo'])}' alt='' style='height:32px;width:auto;object-fit:contain'>" if p.get("logo") else ""
        return f"<div class='wrap'><nav><span class='brand' style='display:flex;align-items:center;gap:10px'>{logo}{esc(p.get('brand'))}</span><span class='links'>{links}</span><a class='btn' href='#'>{esc(p.get('cta','Get started'))}</a></nav></div>"
    if t == "hero":
        centered = p.get("variant") == "centered" or s.get("align") == "center"
        split = p.get("variant") == "split" and p.get("image")
        inner = (f"<span class='badge'>{esc(p['badge'])}</span><br><br>" if p.get("badge") else "") + \
                f"<h1>{esc(p.get('title'))}</h1><p class='mut'>{esc(p.get('subtitle'))}</p><div style='margin-top:28px'><a class='btn' href='#'>{esc(p.get('cta','Get started'))}</a>" + \
                (f"<a class='btn2' href='#'>{esc(p['cta2'])}</a>" if p.get("cta2") else "") + "</div>"
        if p.get("variant") == "cover" and p.get("image"):
            return f"<section class='hero cover {'center' if centered else ''}'><img src='{esc(p['image'])}' alt=''><div class='wrap'>{inner}</div></section>"
        if split:
            return f"<section class='hero lg {cls}'><div class='wrap grid g2' style='align-items:center'><div>{inner}</div><img class='g' src='{esc(p['image'])}' alt=''></div></section>"
        return f"<section class='hero lg {cls} {'center' if centered else ''}'><div class='wrap'>{inner}</div></section>"
    if t == "stats":
        items = "".join(f"<div class='card'><div class='stat'>{esc(i.get('value'))}</div><p class='mut' style='margin-top:8px'>{esc(i.get('label'))}</p></div>" for i in p.get("items", []))
        return f"<section class='{cls}'><div class='wrap'><p class='kicker'>{esc(p.get('heading'))}</p><div class='grid g4'>{items}</div></div></section>"
    if t == "team":
        items = "".join(f"<div class='card' style='padding:16px'>" + (f"<img class='tm' src='{esc(m.get('photo'))}' alt=''>" if m.get("photo") else "") + f"<h3 style='font-size:18px'>{esc(m.get('name'))}</h3><p class='kicker' style='margin:6px 0 0'>{esc(m.get('role'))}</p></div>" for m in p.get("members", []))
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='grid g4' style='margin-top:40px'>{items}</div></div></section>"
    if t == "logos":
        return f"<section class='sm {cls}'><div class='wrap center'><p class='mut' style='font-size:13px;letter-spacing:.1em;text-transform:uppercase'>{esc(p.get('heading'))}</p><div class='logos' style='margin-top:20px'>{''.join(f'<span>{esc(n)}</span>' for n in p.get('names', []))}</div></div></section>"
    if t == "features":
        items = "".join(f"<div class='card'><div class='ico'>{ICON_SVG}</div><h3 style='font-size:20px'>{esc(i.get('title'))}</h3><p class='mut' style='margin-top:8px'>{esc(i.get('desc'))}</p></div>" for i in p.get("items", []))
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><p class='mut' style='font-size:18px;margin-top:10px;max-width:600px'>{esc(p.get('subheading'))}</p><div class='grid g3' style='margin-top:40px'>{items}</div></div></section>"
    if t == "gallery":
        imgs = "".join(f"<img class='g' src='{esc(u)}' alt=''>" for u in p.get("images", []))
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='grid g3' style='margin-top:32px'>{imgs}</div></div></section>"
    if t == "video":
        u = p.get("url") or ""
        media = f"<iframe class='yt' src='{esc(u)}' allow='autoplay; encrypted-media; picture-in-picture' allowfullscreen></iframe>" if ("youtube.com" in u or "youtu.be" in u) else f"<video src='{esc(u)}' controls style='width:100%;margin-top:28px;border-radius:var(--r);border:1px solid var(--bd)'></video>"
        return f"<section class='{cls}'><div class='wrap center'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2>{media}<p class='mut'>{esc(p.get('caption'))}</p></div></section>"
    if t == "testimonials":
        items = "".join(f"<div class='card'><p style='font-size:18px'>“{esc(i.get('quote'))}”</p><p style='margin-top:18px;font-weight:600'>{esc(i.get('name'))}</p><p class='mut' style='font-size:14px'>{esc(i.get('role'))}</p></div>" for i in p.get("items", []))
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='grid g3' style='margin-top:40px'>{items}</div></div></section>"
    if t == "pricing":
        plans = "".join(f"<div class='card {'hl' if pl.get('highlight') else ''}'><p class='mut' style='font-weight:600'>{esc(pl.get('name'))}</p><div class='price'>{esc(pl.get('price'))}<span class='mut' style='font-size:16px;font-weight:500'>/{esc(pl.get('period','mo'))}</span></div><ul>{''.join(f'<li>✓ {esc(f)}</li>' for f in pl.get('features', []))}</ul><a class='btn' style='margin-top:20px' href='#'>Choose {esc(pl.get('name'))}</a></div>" for pl in p.get("plans", []))
        return f"<section class='{cls}'><div class='wrap'><h2 class='center' style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='grid g3' style='margin-top:40px'>{plans}</div></div></section>"
    if t == "faq":
        items = "".join(f"<details><summary>{esc(i.get('q'))}</summary><p class='mut'>{esc(i.get('a'))}</p></details>" for i in p.get("items", []))
        return f"<section class='{cls}'><div class='wrap' style='max-width:760px'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='faq' style='margin-top:24px'>{items}</div></div></section>"
    if t == "chart":
        mx = max([x.get("v", 1) for x in p.get("series", [])] + [1])
        bars = "".join(f"<span title='{esc(x.get('m'))}' style='height:{(x.get('v', 0) / mx) * 100}%'></span>" for x in p.get("series", []))
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='bar' style='margin-top:32px'>{bars}</div>" + (f"<p class='mut' style='margin-top:16px'>{esc(p['caption'])}</p>" if p.get("caption") else "") + "</div></section>"
    if t == "cta":
        return f"<section class='accent center {s.get('padding','') if s.get('padding') in ('sm','lg') else ''}'><div class='wrap'><h2 style='font-size:44px'>{esc(p.get('title'))}</h2><p class='mut' style='font-size:18px;margin-top:12px'>{esc(p.get('subtitle'))}</p><a class='btn' style='background:#fff;color:var(--p);margin-top:28px' href='#'>{esc(p.get('cta','Get started'))}</a></div></section>"
    if t == "contact":
        return f"<section class='{cls}'><div class='wrap grid g2'><div><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><p class='mut' style='margin-top:10px'>{esc(p.get('subtitle'))}</p><p style='margin-top:20px'>{esc(p.get('email'))}<br>{esc(p.get('phone'))}<br>{esc(p.get('address'))}</p></div><form class='card'><input placeholder='Name' style='width:100%;padding:12px;border:1px solid var(--bd);border-radius:10px;margin-bottom:10px'><input placeholder='Email' style='width:100%;padding:12px;border:1px solid var(--bd);border-radius:10px;margin-bottom:10px'><textarea placeholder='Message' rows='4' style='width:100%;padding:12px;border:1px solid var(--bd);border-radius:10px'></textarea><button class='btn' style='border:0;margin-top:12px;width:100%'>Send</button></form></div></section>"
    if t == "footer":
        cols = "".join(f"<div><h4>{esc(c.get('title'))}</h4><ul>{''.join(f'<li>{esc(l)}</li>' for l in c.get('links', []))}</ul></div>" for c in p.get("columns", []))
        logo = f"<img src='{esc(p['logo'])}' alt='' style='height:32px;width:auto;object-fit:contain;display:block;margin-bottom:12px'>" if p.get("logo") else ""
        return f"<footer><div class='wrap grid g4'><div>{logo}<span class='brand'>{esc(p.get('brand'))}</span><p class='mut' style='margin-top:8px'>{esc(p.get('tagline'))}</p></div>{cols}</div></footer>"
    return ""


FX_CSS = """
.fx-reveal{opacity:0;transform:translateY(24px);transition:opacity .6s cubic-bezier(.22,1,.36,1),transform .6s cubic-bezier(.22,1,.36,1)}.fx-reveal.in{opacity:1;transform:none}
.fx-hover{transition:transform .25s}.fx-hover:hover{transform:scale(1.01)}.fx-hover img{transition:transform .5s}.fx-hover:hover img{transform:scale(1.03)}
@keyframes fxfloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}.fx-float{animation:fxfloat 4s ease-in-out infinite}
.fx-parallax{will-change:transform}
.os-cur{position:fixed;top:0;left:0;pointer-events:none;z-index:99999;border-radius:50%}
"""
FX_JS = """<script>(function(){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{rootMargin:'-60px'});document.querySelectorAll('.fx-reveal').forEach(function(el){io.observe(el)});
var px=document.querySelectorAll('.fx-parallax');if(px.length){addEventListener('scroll',function(){px.forEach(function(el){var r=el.getBoundingClientRect();var p=(r.top+r.height/2-innerHeight/2)/innerHeight;el.style.transform='translateY('+(-p*40)+'px)'})},{passive:true})}
if(!matchMedia('(pointer: coarse)').matches&&document.body.dataset.cursor!=='off'){var c=getComputedStyle(document.documentElement).getPropertyValue('--p')||'#F97316';var d=document.createElement('div'),g=document.createElement('div');d.className='os-cur';g.className='os-cur';d.style.cssText+='width:8px;height:8px;background:'+c;g.style.cssText+='width:36px;height:36px;border:1px solid '+c+';opacity:.7;transition:transform .2s';document.body.append(d,g);document.documentElement.style.cursor='none';
var t={x:innerWidth/2,y:innerHeight/2},p={x:t.x,y:t.y},q={x:t.x,y:t.y},h=false;addEventListener('mousemove',function(e){t.x=e.clientX;t.y=e.clientY;h=!!e.target.closest('a,button,input,textarea')},{passive:true});
(function loop(){p.x+=(t.x-p.x)*.35;p.y+=(t.y-p.y)*.35;q.x+=(t.x-q.x)*.12;q.y+=(t.y-q.y)*.12;d.style.transform='translate3d('+(p.x-4)+'px,'+(p.y-4)+'px,0)';g.style.transform='translate3d('+(q.x-18)+'px,'+(q.y-18)+'px,0) scale('+(h?1.6:1)+')';requestAnimationFrame(loop)})()}})();</script>"""


CURSOR_FX_JS = """<script>(function(){var fx=document.body.dataset.cursorFx||'none';if(fx==='none')return;if(matchMedia('(pointer: coarse)').matches||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
var cv=document.createElement('canvas');cv.style.cssText='position:fixed;inset:0;pointer-events:none;z-index:99998';document.body.appendChild(cv);var cx=cv.getContext('2d'),dpr=Math.min(devicePixelRatio||1,2);
var DN=Math.max(.2,Math.min(3,parseFloat(document.body.dataset.cursorDensity||'1')||1)),SPD=Math.max(.2,Math.min(3,parseFloat(document.body.dataset.cursorSpeed||'1')||1));
function rz(){dpr=Math.min(devicePixelRatio||1,2);cv.width=innerWidth*dpr;cv.height=innerHeight*dpr;cv.style.width=innerWidth+'px';cv.style.height=innerHeight+'px';cx.setTransform(dpr,0,0,dpr,0,0)}rz();addEventListener('resize',rz);
var P=[],T=Math.PI*2,last=null;function r(a,b){return a+Math.random()*(b-a)}
var SP={fairy:2,bubbles:1,smoke:2,fire:3,wind:1,frost:1,plasma:1,ink:1,comet:3,matrix:1};
function mk(x,y,vx,vy){var s=Math.hypot(vx,vy);switch(fx){
case 'fairy':return{x:x+r(-6,6),y:y+r(-6,6),vx:r(-.4,.4),vy:r(-.9,-.2),l:1,d:r(.012,.024),s:r(3,7),rt:r(0,T),vr:r(-.09,.09),h:r(38,300)};
case 'bubbles':return{x:x+r(-10,10),y:y+r(-8,8),vx:r(-.35,.35),vy:r(-1.2,-.45),l:1,d:r(.006,.014),s:r(4,13),h:r(170,215),w:r(0,T)};
case 'smoke':return{x:x+r(-8,8),y:y+r(-8,8),vx:r(-.35,.35),vy:r(-.7,-.15),l:1,d:r(.006,.013),s:r(16,34),g:r(.35,.9)};
case 'fire':return{x:x+r(-5,5),y:y+r(-4,4),vx:r(-.5,.5),vy:r(-2.2,-.8),l:1,d:r(.02,.045),s:r(2.5,7)};
case 'wind':return{x:x+r(-14,14),y:y+r(-10,10),vx:r(.4,1.8),vy:r(.15,.8),l:1,d:r(.005,.011),s:r(4,9),rt:r(0,T),vr:r(-.06,.06),sw:r(0,T),h:r(320,360)};
case 'frost':return{x:x+r(-12,12),y:y+r(-10,10),vx:r(-.3,.3),vy:r(.3,1.1),l:1,d:r(.005,.011),s:r(4,10),rt:r(0,T),vr:r(-.04,.04),sw:r(0,T)};
case 'plasma':return{x:x,y:y,vx:0,vy:0,l:1,d:r(.07,.14),s:Math.max(18,Math.min(90,s*4)),sd:Math.random()*999,h:r(170,300)};
case 'ink':return{x:x+r(-7,7),y:y+r(-7,7),vx:vx*.08+r(-.3,.3),vy:vy*.08+r(.1,.7),l:1,d:r(.004,.009),s:r(6,20),g:r(.1,.5),h:r(190,270)};
case 'comet':return{x:x+r(-3,3),y:y+r(-3,3),vx:-vx*r(.05,.2)+r(-.4,.4),vy:-vy*r(.05,.2)+r(-.4,.4),l:1,d:r(.012,.03),s:r(1,3.4),h:r(35,60)};
case 'matrix':return{x:Math.round((x+r(-16,16))/12)*12,y:y+r(-8,8),vx:0,vy:r(2.2,5.2),l:1,d:r(.012,.026),s:13,gl:Math.random()<.5?'0':'1'};}return null}
function st(p){p.x+=p.vx;p.y+=p.vy;p.l-=p.d;if(p.rt!==undefined)p.rt+=p.vr;
if(fx==='fairy'){p.vy-=.006}else if(fx==='bubbles'){p.w+=.13;p.x+=Math.sin(p.w)*.5}else if(fx==='smoke'){p.s+=p.g;p.vy-=.004}else if(fx==='fire'){p.vy-=.03;p.s*=.985}else if(fx==='wind'){p.sw+=.06;p.y+=Math.sin(p.sw)*.7}else if(fx==='frost'){p.sw+=.05;p.x+=Math.sin(p.sw)*.6}else if(fx==='ink'){p.s+=p.g;p.vy+=.02}else if(fx==='comet'){p.vx*=.97;p.vy*=.97}}
function star(rr,n){cx.beginPath();for(var i=0;i<n*2;i++){var rad=i%2===0?rr:rr*.36,a=i*Math.PI/n;i?cx.lineTo(Math.cos(a)*rad,Math.sin(a)*rad):cx.moveTo(Math.cos(a)*rad,Math.sin(a)*rad)}cx.closePath()}
function dr(p){var a=Math.max(0,Math.min(1,p.l));cx.save();
if(fx==='fairy'){cx.translate(p.x,p.y);cx.rotate(p.rt);cx.shadowBlur=14;cx.shadowColor='hsla('+p.h+',95%,70%,'+a+')';cx.fillStyle='hsla('+p.h+',95%,72%,'+a+')';star(p.s,4);cx.fill()}
else if(fx==='bubbles'){cx.globalAlpha=a*.85;var g=cx.createRadialGradient(p.x-p.s*.3,p.y-p.s*.35,p.s*.1,p.x,p.y,p.s);g.addColorStop(0,'rgba(255,255,255,.9)');g.addColorStop(.45,'hsla('+p.h+',90%,72%,.35)');g.addColorStop(1,'hsla('+(p.h+40)+',90%,60%,.12)');cx.fillStyle=g;cx.beginPath();cx.arc(p.x,p.y,p.s,0,T);cx.fill();cx.strokeStyle='hsla('+p.h+',95%,85%,'+(a*.6)+')';cx.stroke()}
else if(fx==='smoke'){var g2=cx.createRadialGradient(p.x,p.y,0,p.x,p.y,p.s);g2.addColorStop(0,'rgba(180,195,215,'+(a*.16)+')');g2.addColorStop(1,'rgba(120,140,170,0)');cx.fillStyle=g2;cx.beginPath();cx.arc(p.x,p.y,p.s,0,T);cx.fill()}
else if(fx==='fire'){var h=18+40*a;cx.shadowBlur=16;cx.shadowColor='hsla('+h+',100%,60%,'+a+')';cx.fillStyle='hsla('+h+',100%,'+(45+35*a)+'%,'+a+')';cx.beginPath();cx.ellipse(p.x,p.y,p.s*.7,p.s*1.25,0,0,T);cx.fill()}
else if(fx==='wind'){cx.translate(p.x,p.y);cx.rotate(p.rt);cx.globalAlpha=a;cx.fillStyle='hsla('+p.h+',85%,82%,'+a+')';cx.beginPath();cx.ellipse(0,0,p.s,p.s*.45,0,0,T);cx.fill()}
else if(fx==='frost'){cx.translate(p.x,p.y);cx.rotate(p.rt);cx.shadowBlur=10;cx.shadowColor='rgba(186,230,253,'+a+')';cx.strokeStyle='rgba(224,242,254,'+a+')';cx.lineWidth=1.3;for(var i=0;i<6;i++){var ang=i*Math.PI/3;cx.beginPath();cx.moveTo(0,0);cx.lineTo(Math.cos(ang)*p.s,Math.sin(ang)*p.s);cx.stroke()}}
else if(fx==='plasma'){cx.globalAlpha=a;cx.shadowBlur=18;cx.shadowColor='hsla('+p.h+',100%,65%,1)';cx.strokeStyle='hsla('+p.h+',100%,80%,'+a+')';cx.lineWidth=1.8;cx.beginPath();cx.moveTo(p.x,p.y);var X=p.x,Y=p.y;for(var j=0;j<5;j++){X+=Math.sin(p.sd+j*2.1)*(p.s/4)+r(-6,6);Y+=Math.cos(p.sd+j*1.7)*(p.s/4)+r(-6,6);cx.lineTo(X,Y)}cx.stroke()}
else if(fx==='ink'){cx.globalAlpha=a*.5;cx.fillStyle='hsla('+p.h+',85%,58%,1)';cx.beginPath();cx.arc(p.x,p.y,p.s,0,T);cx.fill()}
else if(fx==='comet'){cx.globalAlpha=a;cx.shadowBlur=8;cx.shadowColor='hsla('+p.h+',100%,75%,1)';cx.fillStyle='hsla('+p.h+',100%,75%,1)';cx.beginPath();cx.arc(p.x,p.y,p.s,0,T);cx.fill()}
else if(fx==='matrix'){cx.globalAlpha=a;cx.font='700 13px ui-monospace,monospace';cx.shadowBlur=10;cx.shadowColor='rgba(34,197,94,.9)';cx.fillStyle=a>.85?'#DCFCE7':'#22C55E';cx.fillText(p.gl,p.x,p.y)}
cx.restore()}
addEventListener('mousemove',function(e){var vx=last?e.clientX-last.x:0,vy=last?e.clientY-last.y:0;last={x:e.clientX,y:e.clientY};var n=Math.max(1,Math.round((SP[fx]||1)*DN));for(var i=0;i<n;i++){if(P.length>=260)break;var p=mk(e.clientX,e.clientY,vx,vy);if(p){p.s*=(.6+.4*DN);p.vx*=SPD;p.vy*=SPD;p.d*=SPD;P.push(p)}}},{passive:true});
(function loop(){cx.clearRect(0,0,innerWidth,innerHeight);cx.globalCompositeOperation=(fx==='ink'||fx==='smoke')?'source-over':'lighter';for(var i=P.length-1;i>=0;i--){var p=P[i];st(p);if(p.l<=0||p.y<-80||p.y>innerHeight+120){P.splice(i,1);continue}dr(p)}cx.globalCompositeOperation='source-over';requestAnimationFrame(loop)})()})();</script>"""


def fx_class(b: dict, theme: dict) -> str:
    if theme.get("motion") is False:
        return ""
    fx = (b.get("style") or {}).get("effects") or {}
    out = [] if fx.get("reveal") is False else ["fx-reveal"]
    for k in ("hover", "float", "parallax"):
        if fx.get(k):
            out.append(f"fx-{k}")
    return " ".join(out)


def _doc(app_doc, theme, title, body, css_path="styles.css"):
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)} · {esc(app_doc['name'])}</title><link rel='stylesheet' href='{FONT_URL.format(h=theme['font_heading'].replace(' ', '+'), b=theme['font_body'].replace(' ', '+'))}'>"
            f"<link rel='stylesheet' href='{css_path}'></head><body data-cursor='{'off' if theme.get('cursor') is False else 'on'}' data-cursor-fx='{theme.get('cursor_effect') or 'none'}' data-cursor-density='{theme.get('cursor_density') or 1}' data-cursor-speed='{theme.get('cursor_speed') or 1}'>{body}{'' if (theme.get('motion') is False and theme.get('cursor') is False) else FX_JS}{'' if (theme.get('cursor_effect') or 'none') == 'none' else CURSOR_FX_JS}</body></html>")


def render_page(app_doc: dict, theme: dict, page: dict, pages: List[dict], cols: List[dict] = None) -> str:
    body = "".join(f"<div class='{fx_class(b, theme)}'>{render_block(b, '', cols)}</div>" for b in page.get("blocks", []))
    body = re.sub(r"href='(/[a-z0-9-]*)'", lambda m: f"href='{'index' if m.group(1)=='/' else m.group(1).strip('/')}.html'", body)
    return _doc(app_doc, theme, page["name"], body)


def render_item_page(app_doc: dict, theme: dict, col: dict, item: dict, pages: List[dict]) -> str:
    home = next((pg for pg in pages if pg.get("slug") == "/"), None)
    nav = next((b for b in (home or {}).get("blocks", []) if b.get("type") == "navbar"), None)
    footer = next((b for b in (home or {}).get("blocks", []) if b.get("type") == "footer"), None)
    paras = "".join(f"<p style='font-size:18px;line-height:1.7;margin-top:18px'>{esc(x)}</p>" for x in (item.get("body") or "").split("\n") if x.strip())
    body = (render_block(nav, "") if nav else "") + \
        f"<section class='lg'><div class='wrap' style='max-width:800px'><p class='badge'>{esc(col['name'])}</p><h1 style='font-size:clamp(36px,5vw,56px);margin-top:16px'>{esc(item['title'])}</h1><p class='mut' style='margin-top:12px'>{esc(item.get('date'))}{(' · ' + ', '.join(item.get('tags', []))) if item.get('tags') else ''}</p>" + \
        (f"<img class='g' src='{esc(item['cover'])}' alt='' style='aspect-ratio:16/9;margin-top:28px'>" if item.get("cover") else "") + \
        f"<p class='mut' style='font-size:20px;margin-top:28px'>{esc(item.get('excerpt'))}</p>{paras}<p style='margin-top:40px'><a class='btn2' href='../index.html'>← Back</a></p></div></section>" + \
        (render_block(footer, "") if footer else "")
    body = re.sub(r"href='(/[a-z0-9-]*)'", lambda m: f"href='../{'index' if m.group(1)=='/' else m.group(1).strip('/')}.html'", body)
    return _doc(app_doc, theme, item["title"], body, "../styles.css")


# ---------- Lovable-style starter code from app_spec ----------
PY_TYPES = {"string": "str", "text": "str", "email": "EmailStr", "number": "float", "boolean": "bool", "date": "str", "enum": "str", "ref": "str"}


def _pascal(s: str) -> str:
    return "".join(w.capitalize() for w in re.sub(r"[^a-zA-Z0-9]+", " ", s or "Item").split()) or "Item"


def _snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "item").lower()).strip("_") or "item"


def starter_backend(spec: dict) -> str:
    models = spec.get("models") or []
    lines = ["from fastapi import FastAPI, APIRouter, HTTPException", "from fastapi.middleware.cors import CORSMiddleware",
             "from motor.motor_asyncio import AsyncIOMotorClient", "from pydantic import BaseModel, EmailStr", "from typing import Optional, List",
             "import os, uuid", "from dotenv import load_dotenv", "", "load_dotenv()",
             "client = AsyncIOMotorClient(os.environ['MONGO_URL'])", "db = client[os.environ['DB_NAME']]",
             f"app = FastAPI(title={json.dumps(spec.get('name', 'App'))})", "api = APIRouter(prefix='/api')", ""]
    for m in models:
        cls = _pascal(m.get("name"))
        lines.append(f"class {cls}In(BaseModel):")
        fields = m.get("fields") or [{"name": "title", "type": "string", "required": True}]
        for f in fields:
            t = PY_TYPES.get(f.get("type", "string"), "str")
            lines.append(f"    {_snake(f.get('name'))}: {t if f.get('required') else f'Optional[{t}] = None'}")
        lines.append("")
        coll = _snake(m.get("name"))
        lines += [
            f"@api.get('/{coll}')", f"async def list_{coll}():", f"    return await db.{coll}.find({{}}, {{'_id': 0}}).to_list(500)", "",
            f"@api.post('/{coll}')", f"async def create_{coll}(body: {cls}In):",
            f"    doc = {{'id': uuid.uuid4().hex, **body.model_dump()}}", f"    await db.{coll}.insert_one(dict(doc))", "    return doc", "",
            f"@api.get('/{coll}/{{item_id}}')", f"async def get_{coll}(item_id: str):",
            f"    doc = await db.{coll}.find_one({{'id': item_id}}, {{'_id': 0}})", "    if not doc: raise HTTPException(404)", "    return doc", "",
            f"@api.put('/{coll}/{{item_id}}')", f"async def update_{coll}(item_id: str, body: {cls}In):",
            f"    await db.{coll}.update_one({{'id': item_id}}, {{'$set': body.model_dump(exclude_unset=True)}})",
            f"    return await db.{coll}.find_one({{'id': item_id}}, {{'_id': 0}})", "",
            f"@api.delete('/{coll}/{{item_id}}')", f"async def delete_{coll}(item_id: str):",
            f"    await db.{coll}.delete_one({{'id': item_id}})", "    return {'ok': True}", "",
        ]
    lines += ["app.include_router(api)", "app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])", ""]
    return "\n".join(lines)


def starter_screen(screen: dict, spec: dict) -> str:
    name = _pascal(screen.get("name"))
    comps = screen.get("components") or []
    body = []
    for c in comps:
        t, label = c.get("type", "cards"), c.get("label") or c.get("type", "").title()
        model = _snake(c.get("model") or (spec.get("models") or [{}])[0].get("name", "items"))
        if t in ("table", "list", "cards", "kanban"):
            body.append(f"""      <section className="card">
        <h2>{label}</h2>
        <DataList collection="{model}" fields={{{json.dumps(c.get('fields') or [])}}} />
      </section>""")
        elif t == "form":
            body.append(f"""      <section className="card">
        <h2>{label}</h2>
        <DataForm collection="{model}" fields={{{json.dumps(c.get('fields') or [])}}} />
      </section>""")
        elif t == "stats":
            body.append(f"""      <section className="stats">{''.join(f'<div className="stat"><span>{esc(f)}</span><strong>—</strong></div>' for f in (c.get('fields') or ['Total', 'Active', 'Revenue']))}</section>""")
        else:
            body.append(f"""      <section className="card"><h2>{label}</h2><p className="muted">{esc(screen.get('description'))}</p></section>""")
    return f"""import {{ DataList, DataForm }} from "../components/Data";

export default function {name}() {{
  return (
    <main className="page">
      <h1>{esc(screen.get('name'))}</h1>
      <p className="muted">{esc(screen.get('description'))}</p>
{chr(10).join(body)}
    </main>
  );
}}
"""


def starter_frontend_files(spec: dict, theme: dict = None) -> Dict[str, str]:
    theme = theme or {}
    screens = spec.get("screens") or []
    files = {}
    imports, routes, nav = [], [], []
    for s in screens:
        n = _pascal(s.get("name"))
        route = s.get("route") or f"/{_snake(s.get('name'))}"
        files[f"frontend/src/pages/{n}.jsx"] = starter_screen(s, spec)
        imports.append(f'import {n} from "./pages/{n}";')
        routes.append(f'        <Route path="{route}" element={{<{n} />}} />')
        if s.get("nav", True):
            nav.append(f'<NavLink to="{route}" end>{esc(s.get("name"))}</NavLink>')
    files["frontend/src/App.jsx"] = f"""import {{ useEffect, useState }} from "react";
import {{ BrowserRouter, Routes, Route, NavLink, useLocation }} from "react-router-dom";
{chr(10).join(imports)}
import "./styles.css";

const SCREENS = {json.dumps([{"name": s.get("name"), "route": s.get("route")} for s in screens])};

function Breadcrumbs() {{
  const {{ pathname }} = useLocation();
  const cur = SCREENS.find(s => s.route === pathname) || SCREENS[0];
  return <header className="topbar"><span>{esc(spec.get('name', 'App'))}</span><span className="sep">›</span><strong>{{cur?.name}}</strong></header>;
}}

export default function App() {{
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");
  useEffect(() => {{ document.documentElement.classList.toggle("dark", dark); document.documentElement.classList.toggle("light", !dark); localStorage.setItem("theme", dark ? "dark" : "light"); }}, [dark]);
  useEffect(() => {{ const io = new IntersectionObserver(es => es.forEach(e => e.isIntersecting && e.target.classList.add("in")), {{ rootMargin: "-40px" }}); document.querySelectorAll(".card,.stat").forEach(el => {{ el.classList.add("reveal"); io.observe(el); }}); return () => io.disconnect(); }});
  return (
    <BrowserRouter>
      <div className="shell">
        <aside className="sidebar"><div className="brand">{f'<img src="{esc(theme.get("logo"))}" alt="" style={{{{height:28,width:"auto"}}}} />' if theme.get("logo") else '<span className="dot" />'}{esc(spec.get('name', 'App'))}</div><nav>{''.join(nav)}</nav>
          <button className="toggle" onClick={{() => setDark(d => !d)}}>{{dark ? "☀ Light mode" : "☾ Dark mode"}}</button></aside>
        <div className="content">
          <Breadcrumbs />
          <Routes>
{chr(10).join(routes)}
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}}
"""
    files["frontend/src/components/Data.jsx"] = """import { useEffect, useState } from "react";
const API = process.env.REACT_APP_BACKEND_URL + "/api";

export function DataList({ collection, fields }) {
  const [rows, setRows] = useState([]);
  useEffect(() => { fetch(`${API}/${collection}`).then(r => r.json()).then(setRows).catch(() => {}); }, [collection]);
  return (
    <table className="table"><thead><tr>{fields.map(f => <th key={f}>{f}</th>)}</tr></thead>
      <tbody>{rows.map(r => <tr key={r.id}>{fields.map(f => <td key={f}>{String(r[f.toLowerCase().replace(/\\s+/g, "_")] ?? "")}</td>)}</tr>)}</tbody></table>
  );
}

export function DataForm({ collection, fields }) {
  const [form, setForm] = useState({});
  async function submit(e) {
    e.preventDefault();
    await fetch(`${API}/${collection}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    setForm({});
  }
  return (
    <form onSubmit={submit} className="form">
      {fields.map(f => <input key={f} placeholder={f} value={form[f.toLowerCase().replace(/\\s+/g, "_")] || ""} onChange={e => setForm({ ...form, [f.toLowerCase().replace(/\\s+/g, "_")]: e.target.value })} />)}
      <button>Save</button>
    </form>
  );
}
"""
    dark = theme.get("mode") == "dark"
    p, s2 = theme.get("primary", "#F97316"), theme.get("secondary", "#14B8A6")
    bg, sf, fg, mut, bd = ("#0B0F17", "#111827", "#F8FAFC", "#94A3B8", "#1F2937") if dark else (theme.get("bg", "#F8FAFC"), theme.get("surface", "#FFFFFF"), theme.get("fg", "#0F172A"), theme.get("muted", "#64748B"), theme.get("border", "#E2E8F0"))
    files["frontend/src/styles.css"] = (f":root{{--p:{p};--s:{s2};--bg:{bg};--sf:{sf};--fg:{fg};--bd:{bd};--mut:{mut};--r:{theme.get('radius', 14)}px}}"
        f"body{{margin:0;font-family:'{theme.get('font_body', 'Manrope')}',system-ui,sans-serif;color:var(--fg);background:var(--bg)}}h1,h2{{font-family:'{theme.get('font_heading', 'Plus Jakarta Sans')}',sans-serif;letter-spacing:-0.02em}}"
        ".shell{display:flex;min-height:100vh}.sidebar{position:fixed;inset:0 auto 0 0;width:240px;background:var(--sf);border-right:1px solid var(--bd);padding:20px 14px;display:flex;flex-direction:column;gap:18px}.brand{font-weight:800;font-size:17px;display:flex;align-items:center;gap:10px;padding:6px 10px}.dot{width:12px;height:12px;border-radius:4px;background:var(--p)}"
        ".sidebar nav{display:flex;flex-direction:column;gap:4px}.sidebar a{color:var(--mut);text-decoration:none;padding:10px 12px;border-radius:10px;font-size:14px;font-weight:500;transition:background .15s,color .15s}.sidebar a:hover{background:color-mix(in srgb,var(--p) 10%,transparent);color:var(--fg)}.sidebar a.active{background:var(--p);color:#fff}"
        ".content{margin-left:240px;flex:1;display:flex;flex-direction:column}.topbar{display:flex;align-items:center;gap:10px;padding:14px 32px;border-bottom:1px solid var(--bd);background:var(--sf);font-size:13px;color:var(--mut);position:sticky;top:0}.topbar strong{color:var(--p)}.sep{opacity:.5}"
        ".page{max-width:1120px;padding:36px 32px}.muted{color:var(--mut)}.card{background:var(--sf);border:1px solid var(--bd);border-radius:var(--r);padding:24px;margin-top:20px}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-top:20px}.stat{background:var(--sf);border:1px solid var(--bd);border-radius:var(--r);padding:20px}.stat span{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}.stat strong{display:block;font-size:28px;margin-top:6px}"
        ".table{width:100%;border-collapse:collapse}.table th,.table td{text-align:left;padding:10px;border-bottom:1px solid var(--bd)}.table th{color:var(--mut);font-size:12px;font-weight:600}.form{display:grid;gap:10px}.form input{padding:12px;border:1px solid var(--bd);border-radius:10px;background:var(--bg);color:var(--fg)}.form button{background:var(--p);color:#fff;border:0;padding:12px;border-radius:999px;font-weight:600;cursor:pointer}"
        "@media(max-width:860px){.sidebar{position:static;width:auto;inset:auto;border-right:0;border-bottom:1px solid var(--bd)}.sidebar nav{flex-direction:row;flex-wrap:wrap}.shell{flex-direction:column}.content{margin-left:0}}"
        ".dark{--bg:#0A0A0F;--sf:#141420;--fg:#F8FAFC;--mut:#A1A7B8;--bd:#262637}.toggle{margin-top:auto;border:1px solid var(--bd);background:transparent;color:var(--mut);border-radius:999px;padding:8px 12px;font-size:12px;cursor:pointer}"
        ".reveal{opacity:0;transform:translateY(16px);transition:opacity .45s cubic-bezier(.22,1,.36,1),transform .45s cubic-bezier(.22,1,.36,1)}.reveal.in{opacity:1;transform:none}.card,.stat{transition:transform .2s,box-shadow .2s}.card:hover,.stat:hover{transform:scale(1.015) translateY(-2px);box-shadow:0 20px 50px -30px var(--p)}"
        "@keyframes idle{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}.stat:first-child{animation:idle 5s ease-in-out infinite}")
    files["frontend/src/theme.json"] = json.dumps({"mode": theme.get("mode", "light"), "primary": p, "secondary": s2, "layout": "fixed-left-sidebar"}, indent=2)
    files["frontend/package.json"] = json.dumps({"name": _snake(spec.get("name", "app")), "private": True, "dependencies": {"react": "^19.0.0", "react-dom": "^19.0.0", "react-router-dom": "^7.0.0", "react-scripts": "5.0.1"}, "scripts": {"start": "react-scripts start", "build": "react-scripts build"}}, indent=2)
    files["frontend/src/index.js"] = 'import React from "react";\nimport ReactDOM from "react-dom/client";\nimport App from "./App";\nReactDOM.createRoot(document.getElementById("root")).render(<App />);\n'
    files["frontend/public/index.html"] = "<!doctype html><html class='light'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>App</title></head><body><div id='root'></div></body></html>"
    files["frontend/.env.example"] = "REACT_APP_BACKEND_URL=http://localhost:8001\n"
    return files


SQL_TYPES = {"string": "text", "text": "text", "email": "text", "number": "numeric", "boolean": "boolean", "date": "timestamptz", "enum": "text", "ref": "uuid"}


def supabase_schema(spec: dict) -> str:
    out = ["-- Postgres / Supabase schema generated by OmniStack AI", "create extension if not exists \"pgcrypto\";", ""]
    for m in spec.get("models") or []:
        t = _snake(m.get("name"))
        cols = ["  id uuid primary key default gen_random_uuid()", "  created_at timestamptz not null default now()"]
        for f in m.get("fields") or []:
            cols.append(f"  {_snake(f.get('name'))} {SQL_TYPES.get(f.get('type', 'string'), 'text')}{' not null' if f.get('required') else ''}")
        out.append(f"create table if not exists {t} (\n" + ",\n".join(cols) + "\n);")
        out.append(f"alter table {t} enable row level security;")
        out.append(f"create policy \"{t}_owner\" on {t} for all using (auth.uid() is not null);\n")
    return "\n".join(out)


def starter_app_files(spec: dict, theme: dict = None) -> Dict[str, str]:
    files = starter_frontend_files(spec, theme)
    files["backend/server.py"] = starter_backend(spec)
    files["backend/schema.sql"] = supabase_schema(spec)
    files["backend/requirements.txt"] = "fastapi\nuvicorn\nmotor\npydantic[email]\npython-dotenv\n"
    files["backend/.env.example"] = "MONGO_URL=mongodb://localhost:27017\nDB_NAME=app\n"
    files["blueprint.json"] = json.dumps(spec, indent=2)
    files["README.md"] = (f"# {spec.get('name', 'App')}\n\n{spec.get('tagline', '')}\n\n## Run\n- backend: `cd backend && pip install -r requirements.txt && uvicorn server:app --reload --port 8001`\n"
                          f"- frontend: `cd frontend && npm i && npm start`\n\n## Screens\n" + "\n".join(f"- {s.get('name')} `{s.get('route')}` — {s.get('description', '')}" for s in spec.get("screens", []))
                          + "\n\n## API\n" + "\n".join(f"- {a.get('method')} `{a.get('path')}` — {a.get('description', '')}" for a in spec.get("api", [])) + "\n")
    return files
