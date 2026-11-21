"""Bản đồ HTML cục bộ (một tệp, không tải tài nguyên ngoài, không gọi mạng).

Nền tối, danh sách lỗi bên phải; nhấp lỗi -> pan/zoom; bật/tắt lớp; chú giải;
tìm số thửa. Tọa độ hiển thị ở góc dưới theo hệ phẳng của tờ.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from shapely import wkt as shapely_wkt

from ..domain.models import LabelKind, SheetResult
from .reports import DISCLAIMER


def _ring(coords, ox, oy, nd=3):
    return [[round(x - ox, nd), round(y - oy, nd)] for x, y in coords]


def _poly_rings(g, ox, oy):
    out = []
    polys = [g] if g.geom_type == "Polygon" else [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    for p in polys:
        out.append([_ring(p.exterior.coords, ox, oy)] + [_ring(r.coords, ox, oy) for r in p.interiors])
    return out


def build_payload(res: SheetResult) -> dict:
    xs, ys = [], []
    for ln in res.linework:
        b = ln.bounds; xs += [b[0], b[2]]; ys += [b[1], b[3]]
    for p in res.parcels:
        b = p.geometry.bounds; xs += [b[0], b[2]]; ys += [b[1], b[3]]
    for i in res.issues:
        if i.x is not None:
            xs.append(i.x); ys.append(i.y)
    ox, oy = (min(xs), min(ys)) if xs else (0.0, 0.0)
    issue_parcels = {pid for i in res.issues if i.severity != "info" for pid in i.parcel_ids}
    data = {
        "origin": [ox, oy],
        "lines": [_ring(l.coords, ox, oy) for l in res.linework] if res.linework else
                 [r for p in res.parcels for poly in _poly_rings(p.geometry, ox, oy) for r in poly],
        "frame": _poly_rings(res.frame, ox, oy) if res.frame is not None else [],
        "parcels": [{"id": p.internal_id, "no": p.parcel_no, "area": p.area_label, "lt": p.land_type,
                     "ag": round(p.area_geom, 2), "err": p.internal_id in issue_parcels,
                     "rings": _poly_rings(p.geometry, ox, oy)} for p in res.parcels],
        "labels": [{"t": lb.text_norm, "k": lb.kind.value, "x": round(lb.anchor[0] - ox, 3),
                    "y": round(lb.anchor[1] - oy, 3)} for lb in res.labels
                   if lb.kind in (LabelKind.PARCEL_NO, LabelKind.AREA, LabelKind.LAND_TYPE)],
        "issues": [],
    }
    for i in res.issues:
        d = {"id": i.issue_id, "code": i.code, "sev": i.severity, "msg": i.message,
             "x": None if i.x is None else round(i.x - ox, 3), "y": None if i.y is None else round(i.y - oy, 3),
             "ax": i.x, "ay": i.y}
        if i.geometry_wkt:
            try:
                d["rings"] = _poly_rings(shapely_wkt.loads(i.geometry_wkt), ox, oy)
            except Exception:
                pass
        data["issues"].append(d)
    return data


TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:">
<title>Bản đồ __TITLE__</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--line:#8b949e;--txt:#e6edf3;--muted:#8b949e;--err:#f85149;--warn:#d29922;--info:#58a6ff}
*{box-sizing:border-box}body{margin:0;font:13px/1.4 "Segoe UI",Arial,sans-serif;background:var(--bg);color:var(--txt);display:flex;flex-direction:column;height:100vh}
header{padding:6px 12px;background:var(--panel);border-bottom:1px solid #30363d}header h1{font-size:15px;margin:0}header small{color:var(--muted)}
.disc{color:#ff7b72;font-size:11px}
main{flex:1;display:flex;min-height:0}#map{flex:1;position:relative;min-width:0}svg{width:100%;height:100%;display:block;cursor:grab}
aside{width:360px;background:var(--panel);border-left:1px solid #30363d;display:flex;flex-direction:column;min-height:0}
.tools{padding:8px;border-bottom:1px solid #30363d;display:flex;flex-wrap:wrap;gap:6px}
.tools input[type=search]{flex:1;min-width:120px;background:#0d1117;color:var(--txt);border:1px solid #30363d;border-radius:4px;padding:4px 6px}
button{background:#21262d;color:var(--txt);border:1px solid #30363d;border-radius:4px;padding:4px 8px;cursor:pointer}button:focus-visible,input:focus-visible{outline:2px solid var(--info)}
#list{overflow:auto;flex:1;padding:6px}.it{border:1px solid #30363d;border-left:4px solid var(--muted);border-radius:4px;padding:6px;margin-bottom:6px;cursor:pointer}
.it.error{border-left-color:var(--err)}.it.warning{border-left-color:var(--warn)}.it.info{border-left-color:var(--info)}.it.sel{background:#1f2937}
.it b{display:block;font-size:12px}.it code{color:var(--muted);font-size:11px}
.legend{position:absolute;left:8px;bottom:8px;background:rgba(22,27,34,.92);padding:6px 8px;border-radius:4px;font-size:12px}
.legend label{display:block;cursor:pointer}.sw{display:inline-block;width:12px;height:8px;margin-right:4px;vertical-align:middle}
#coord{position:absolute;right:8px;bottom:8px;background:rgba(22,27,34,.92);padding:3px 6px;border-radius:4px;font-size:11px;color:var(--muted)}
@media (max-width:800px){main{flex-direction:column}aside{width:auto;height:40%}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body>
<header><h1>Bản đồ __TITLE__</h1><small>__SUB__</small><div class="disc">__DISC__</div></header>
<main><div id="map"><svg id="svg" role="img" aria-label="Bản đồ tờ"><g id="vp"></g></svg>
<div class="legend" id="legend"></div><div id="coord"></div></div>
<aside><div class="tools"><input type="search" id="q" placeholder="Tìm số thửa / mã lỗi" aria-label="Tìm số thửa hoặc mã lỗi">
<button id="all" title="Xem toàn tờ">Toàn tờ</button></div>
<div class="tools" id="sevf"></div><div id="list" role="list"></div></aside></main>
<script>
const D=__DATA__;const NS="http://www.w3.org/2000/svg";const svg=document.getElementById('svg'),vp=document.getElementById('vp');
const layers={};function L(name){const g=document.createElementNS(NS,'g');g.dataset.layer=name;vp.appendChild(g);layers[name]=g;return g}
function path(rings){return rings.map(r=>'M'+r.map(p=>p[0]+' '+(-p[1])).join('L')+'Z').join('')}
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);p.appendChild(e);return e}
let minx=1e18,miny=1e18,maxx=-1e18,maxy=-1e18;function ext(x,y){minx=Math.min(minx,x);maxx=Math.max(maxx,x);miny=Math.min(miny,y);maxy=Math.max(maxy,y)}
const gErrP=L('vungloi'),gLines=L('ranh'),gFrame=L('khung'),gLab=L('nhan'),gIss=L('loi');
D.parcels.forEach(p=>{if(p.err)p.rings.forEach(r=>el('path',{d:path(r),fill:'#7d1f3a',opacity:.55,stroke:'none'},gErrP))});
D.issues.forEach(i=>{if(i.rings)i.rings.forEach(r=>el('path',{d:path(r),fill:'#f85149',opacity:.35,stroke:'#f85149','vector-effect':'non-scaling-stroke'},gErrP))});
D.lines.forEach(l=>{l.forEach(p=>ext(p[0],p[1]));el('polyline',{points:l.map(p=>p[0]+','+(-p[1])).join(' '),fill:'none',stroke:'#c9d1d9','stroke-width':1,'vector-effect':'non-scaling-stroke'},gLines)});
D.frame.forEach(r=>el('path',{d:path(r),fill:'none',stroke:'#3fb950','stroke-dasharray':'6 4','stroke-width':1.5,'vector-effect':'non-scaling-stroke'},gFrame));
const col={parcel_no:'#ffa657',area:'#79c0ff',land_type:'#7ee787'};
D.labels.forEach(l=>{ext(l.x,l.y);const t=el('text',{x:l.x,y:-l.y,fill:col[l.k]||'#ccc','font-size':1.6,'text-anchor':'middle'},gLab);t.textContent=l.t});
const sevCol={error:'#f85149',warning:'#d29922',info:'#58a6ff'};const marks={};
D.issues.forEach(i=>{if(i.x==null)return;ext(i.x,i.y);marks[i.id]=el('circle',{cx:i.x,cy:-i.y,r:4,fill:'none',stroke:sevCol[i.sev],'stroke-width':2,'vector-effect':'non-scaling-stroke'},gIss)});
if(minx>maxx){minx=0;miny=0;maxx=100;maxy=100}
let vb={x:minx,y:-maxy,w:Math.max(maxx-minx,1),h:Math.max(maxy-miny,1)};const full={...vb};
function apply(){svg.setAttribute('viewBox',`${vb.x} ${vb.y} ${vb.w} ${vb.h}`);const s=vb.w/svg.clientWidth;Object.values(marks).forEach(m=>m.setAttribute('r',6*s));gLab.querySelectorAll('text').forEach(t=>t.setAttribute('font-size',Math.max(11*s,0.2)))}
apply();addEventListener('resize',apply);
svg.addEventListener('wheel',e=>{e.preventDefault();const r=svg.getBoundingClientRect();const mx=vb.x+(e.clientX-r.left)/r.width*vb.w,my=vb.y+(e.clientY-r.top)/r.height*vb.h;const k=e.deltaY>0?1.2:1/1.2;vb.x=mx-(mx-vb.x)*k;vb.y=my-(my-vb.y)*k;vb.w*=k;vb.h*=k;apply()},{passive:false});
let drag=null;svg.addEventListener('mousedown',e=>{drag={x:e.clientX,y:e.clientY,vx:vb.x,vy:vb.y};svg.style.cursor='grabbing'});
addEventListener('mouseup',()=>{drag=null;svg.style.cursor='grab'});
svg.addEventListener('mousemove',e=>{const r=svg.getBoundingClientRect();const mx=vb.x+(e.clientX-r.left)/r.width*vb.w,my=vb.y+(e.clientY-r.top)/r.height*vb.h;
document.getElementById('coord').textContent=`X=${(mx+D.origin[0]).toFixed(3)}  Y=${(-my+D.origin[1]).toFixed(3)}`;
if(drag){vb.x=drag.vx-(e.clientX-drag.x)/r.width*vb.w;vb.y=drag.vy-(e.clientY-drag.y)/r.height*vb.h;apply()}});
function zoomTo(x,y,w){const asp=svg.clientHeight/svg.clientWidth||1;vb={x:x-w/2,y:-y-w*asp/2,w:w,h:w*asp};apply()}
document.getElementById('all').onclick=()=>{vb={...full};apply()};
const LEG=[['ranh','Ranh thửa','#c9d1d9'],['khung','Khung tờ','#3fb950'],['nhan','Nhãn (số thửa/DT/loại đất)','#ffa657'],['vungloi','Vùng lỗi','#7d1f3a'],['loi','Vị trí lỗi','#f85149']];
const lg=document.getElementById('legend');LEG.forEach(([k,t,c])=>{const lb=document.createElement('label');lb.innerHTML=`<input type=checkbox checked> <span class=sw style="background:${c}"></span>${t}`;lb.querySelector('input').onchange=e=>layers[k].style.display=e.target.checked?'':'none';lg.appendChild(lb)});
const sevOn={error:true,warning:true,info:false};const SV={error:'Lỗi',warning:'Cần xem',info:'Thông tin'};const sf=document.getElementById('sevf');
Object.keys(sevOn).forEach(s=>{const n=D.issues.filter(i=>i.sev==s).length;const lb=document.createElement('label');lb.innerHTML=`<input type=checkbox ${sevOn[s]?'checked':''}> ${SV[s]} (${n})`;lb.querySelector('input').onchange=e=>{sevOn[s]=e.target.checked;render()};sf.appendChild(lb)});
const list=document.getElementById('list');const q=document.getElementById('q');q.oninput=render;
function render(){const t=q.value.trim().toLowerCase();list.innerHTML='';
const hitP=t?D.parcels.filter(p=>(p.no||'').toLowerCase()==t):[];hitP.forEach(p=>{const d=document.createElement('div');d.className='it info';d.innerHTML=`<b>Thửa ${p.no}</b>DT nhãn ${p.area??'-'} · hình học ${p.ag} m² · ${p.lt??''}`;d.onclick=()=>{const r=p.rings[0][0];let xs=r.map(a=>a[0]),ys=r.map(a=>a[1]);zoomTo((Math.min(...xs)+Math.max(...xs))/2,(Math.min(...ys)+Math.max(...ys))/2,Math.max(Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys))*2.5+5)};list.appendChild(d)});
D.issues.filter(i=>sevOn[i.sev]&&(!t||i.code.toLowerCase().includes(t)||i.msg.toLowerCase().includes(t))).forEach(i=>{
const d=document.createElement('div');d.className='it '+i.sev;d.setAttribute('role','listitem');d.tabIndex=0;
d.innerHTML=`<b>${SV[i.sev]} · ${i.code}</b>${i.msg.replace(/</g,'&lt;')}<br><code>${i.id}${i.ax!=null?` · X ${i.ax.toFixed(3)}, Y ${i.ay.toFixed(3)}`:''}</code>`;
const go=()=>{list.querySelectorAll('.sel').forEach(e=>e.classList.remove('sel'));d.classList.add('sel');if(i.x!=null)zoomTo(i.x,i.y,30)};d.onclick=go;d.onkeydown=e=>{if(e.key==='Enter')go()};list.appendChild(d)});
Object.entries(marks).forEach(([id,m])=>{const i=D.issues.find(z=>z.id==id);m.style.display=sevOn[i.sev]?'':'none'})}
render();
</script></body></html>"""


def export_html_map(res: SheetResult, path: Path, meta: dict):
    payload = build_payload(res)
    sub = (f"{res.file_name} · Kết quả: {res.status} · Lỗi {res.count('error')} · Cần xem {res.count('warning')} · "
           f"Bộ quy tắc {meta.get('rule_pack')} · {meta.get('run_at')}")
    doc = (TEMPLATE.replace("__TITLE__", html.escape(res.file_name)).replace("__SUB__", html.escape(sub))
           .replace("__DISC__", html.escape(DISCLAIMER))
           .replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(doc, encoding="utf-8")
    tmp.replace(path)
