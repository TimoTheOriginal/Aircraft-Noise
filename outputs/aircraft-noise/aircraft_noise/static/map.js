'use strict';
// Local display projection only; authoritative distances come from the UTM core.
// Contours progress from cool to warm as ANEF increases.
const mapColours={20:'#66d9ef',25:'#8fe388',30:'#f0c674',35:'#ff8f8f'};
let mapView=null;
function mapXY(p){return [(p[0]-151.17)*111320*Math.cos(33.94*Math.PI/180),-(p[1]+33.94)*111320];}
function mapLines(s){return s.boot.contours.features.flatMap(f=>f.geometry.coordinates.map(r=>({level:f.properties.anef,points:r.map(mapXY)})));}
function resetSiteMap(s,site){
 const lines=mapLines(s),pts=lines.flatMap(l=>l.points),r=s.request.receptors[0],p=mapXY([r.longitude,r.latitude]);
 const near=s.result?.payload.anef.receptors[0].nearest_contour;
 if(site&&near){const n=mapXY(near.nearest_point_lon_lat);mapView={x:(p[0]+n[0])/2,y:(p[1]+n[1])/2,span:Math.max(3000,Math.hypot(p[0]-n[0],p[1]-n[1])*3)};return;}
 if(near)pts.push(p);
 const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
 mapView={x:(x0+x1)/2,y:(y0+y1)/2,span:Math.max(x1-x0,(y1-y0)*1.8)*1.12};
}
function siteMapKey(key,s){
 if(key==='0'||key==='1'){resetSiteMap(s,key==='1');return;}
 const d=mapView.span*.12;
 if(key==='ArrowLeft')mapView.x-=d;if(key==='ArrowRight')mapView.x+=d;
 if(key==='ArrowUp')mapView.y-=d;if(key==='ArrowDown')mapView.y+=d;
 if(key==='+'||key==='=')mapView.span=Math.max(250,mapView.span/1.5);
 if(key==='-')mapView.span=Math.min(250000,mapView.span*1.5);
}
function drawSiteMap(s){
 if(!mapView)resetSiteMap(s,false);
 const W=1000,H=560,k=W/mapView.span,xy=p=>[(p[0]-mapView.x)*k+W/2,(p[1]-mapView.y)*k+H/2];
 const pt=p=>xy(p).map(v=>v.toFixed(2)).join(','),safe=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 // Exact pixel-edge bounds are calculated server-side from the supplied
 // Airport Map Portrait.tfw and the source GeoTIFF dimensions, returned with bootstrap data.
 const bounds=s.boot.satellite_georef.bounds;
 const satNW=xy(mapXY([bounds.west,bounds.north]));
 const satSE=xy(mapXY([bounds.east,bounds.south]));
 const satX=Math.min(satNW[0],satSE[0]),satY=Math.min(satNW[1],satSE[1]);
 const satW=Math.abs(satSE[0]-satNW[0]),satH=Math.abs(satSE[1]-satNW[1]);
 const out=[`<svg viewBox="0 0 1000 560" role="img" aria-labelledby="map-title map-desc"><title id="map-title">Site relative to ANEF 2045 contours and Sydney runways</title><desc id="map-desc">North is up. The supplied georeferenced portrait map is shown as context. Contours are labelled 20, 25, 30 and 35. The white cross marks the site; the dashed white line connects to the closest contour point.</desc><defs><pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M 50 0 L 0 0 0 50" fill="none" stroke="#9bc4d2" stroke-opacity=".16" stroke-width="1"/></pattern></defs><rect width="1000" height="560" fill="#080f17"/><image href="/airport-map-portrait.webp" x="${satX}" y="${satY}" width="${satW}" height="${satH}" preserveAspectRatio="none" opacity=".72"/><rect x="${satX+satW*.75}" y="${satY+satH*.74}" width="${satW*.25}" height="${satH*.26}" fill="#080f17"/><rect width="1000" height="560" fill="#00131d" opacity=".30"/><rect width="1000" height="560" fill="url(#grid)"/>`];
 for(const l of mapLines(s)){
  out.push(`<polyline points="${l.points.map(pt).join(' ')}" fill="none" stroke="${mapColours[l.level]}" stroke-width="1.8"/>`);
  const visible=l.points.map(xy).filter(p=>p[0]>40&&p[0]<950&&p[1]>55&&p[1]<485);
  if(visible.length){const p=visible[Math.floor(visible.length*.4)];out.push(`<text x="${p[0]}" y="${p[1]-5}" class="map-label" fill="${mapColours[l.level]}">${l.level}</text>`);}
 }
 for(const f of s.boot.runways.features.filter(f=>f.properties.feature_type==='runway')){
  out.push(`<polyline points="${f.geometry.coordinates.map(mapXY).map(pt).join(' ')}" fill="none" stroke="#c8c8c8" stroke-width="5"/>`);
  const p=xy(mapXY(f.geometry.coordinates[0]));out.push(`<text x="${p[0]+8}" y="${p[1]+18}" class="map-label" fill="#c8c8c8">${safe(f.properties.runway_pair)}</text>`);
 }
 const r=s.request.receptors[0],p=xy(mapXY([r.longitude,r.latitude])),near=s.result?.payload.anef.receptors[0].nearest_contour;
 if(near){const n=xy(mapXY(near.nearest_point_lon_lat));out.push(`<path d="M${p.join(' ')} L${n.join(' ')}" stroke="#fff" stroke-width="1.5" stroke-dasharray="6 5"/><circle cx="${n[0]}" cy="${n[1]}" r="4" fill="#fff"/>`);}
 if(p[0]>=12&&p[0]<=988&&p[1]>=12&&p[1]<=515)out.push(`<circle cx="${p[0]}" cy="${p[1]}" r="10" fill="#080f17" stroke="#fff" stroke-width="2"/><path d="M${p[0]-16} ${p[1]}h32 M${p[0]} ${p[1]-16}v32" stroke="#fff" stroke-width="2"/><text x="${Math.min(880,p[0]+20)}" y="${Math.max(28,p[1]-16)}" class="map-label" fill="#fff">SITE</text>`);
 else out.push('<text x="24" y="32" fill="#f0c674" class="map-label">SITE OUTSIDE VIEW — 1: site view / 0: fit</text>');
 const metres=mapView.span/5,scale=10**Math.floor(Math.log10(metres)),bar=Math.floor(metres/scale)*scale;
 out.push(`<path d="M30 485v8h${bar*k}v-8" stroke="#fff" fill="none" stroke-width="2"/><text x="30" y="477" fill="#c8c8c8" class="map-label">~${bar>=1000?bar/1000+' km':bar+' m'}</text><text x="950" y="32" fill="#fff" class="map-label">N ↑</text><rect x="0" y="520" width="1000" height="40" fill="#080f17"/>`);
 [20,25,30,35].forEach((v,i)=>out.push(`<text x="${24+i*145}" y="547" fill="${mapColours[v]}" class="map-label">— ANEF ${v}</text>`));
 out.push('<text x="620" y="547" fill="#fff" class="map-label">+ SITE  ··· nearest line</text></svg><p class="dim">Portrait map positioned from supplied Airport Map Portrait.tfw (WGS84). Contours/runways use supplied WGS84 vectors; numerical distances use EPSG:32756.</p>');
 document.getElementById('site-map').innerHTML=out.join('');
}
