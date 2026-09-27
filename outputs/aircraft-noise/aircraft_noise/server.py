"""Loopback-only, offline interface. SQLite snapshots; same core as CLI."""
import io
import json
import secrets
import sqlite3
import zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone
from .core import ROOT, build_aircraft_basis, airport_data, source_records
from .packages import export_aircraft_basis

def satellite_georef():
    """Return WGS84 pixel-edge bounds from the supplied portrait GeoTIFF/TFW."""
    a,d,b,e,c,f=(float(v) for v in (ROOT/'static'/'airport-map-portrait.tfw').read_text().split())
    image_width,image_height=11692,8267
    corners=[(a*px+b*py+c,d*px+e*py+f) for px,py in
             [(-.5,-.5),(image_width-.5,-.5),(-.5,image_height-.5),(image_width-.5,image_height-.5)]]
    return {'world_file':[a,d,b,e,c,f],'width_px':image_width,'height_px':image_height,
        'crs':'EPSG:4326','bounds':{'west':min(x for x,y in corners),'east':max(x for x,y in corners),
        'north':max(y for x,y in corners),'south':min(y for x,y in corners)}}

def serve(port=8793):
    local=ROOT.parent/'.local'; local.mkdir(exist_ok=True)
    db=local/'projects.sqlite3'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, created TEXT NOT NULL, project TEXT NOT NULL, request TEXT NOT NULL)')
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,data,kind='application/json',status=200,filename=None):
            if not isinstance(data,bytes): data=json.dumps(data,allow_nan=False).encode()
            self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
            self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            route=urlparse(self.path).path
            if route=='/api/bootstrap':
                contours,runways,_=airport_data()
                from .forecast import references
                data=references()
                return self.send({'token':token,'request':json.loads((ROOT.parent/'fixtures/terminal-request.json').read_text()),
                    'contours':contours,'runways':runways,'satellite_georef':satellite_georef(),'sources':source_records(),'reference_audit':data['audit'],'frequency':data['frequency'],'matrices':data['tables'],
                    'table_index':[{'table_id':t['table_id'],'aircraft':t['aircraft'],'operation':t['operation'],'qualifier':t['qualifier']} for t in data['tables'].values()]})
            if route=='/api/history':
                with sqlite3.connect(db) as c: rows=c.execute('SELECT id,created,project,request FROM snapshots ORDER BY id DESC LIMIT 30').fetchall()
                return self.send([dict(id=r[0],created=r[1],project=r[2],request=json.loads(r[3])) for r in rows])
            files={'/':('index.html','text/html; charset=utf-8'),'/map.js':('map.js','text/javascript; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/favicon.svg':('favicon.svg','image/svg+xml'),'/airport-map-portrait.webp':('airport-map-portrait.webp','image/webp')}
            if route in files:
                name,kind=files[route]; return self.send((ROOT/'static'/name).read_bytes(),kind)
            return self.send({'error':'Not found'},status=404)
        def do_POST(self):
            if self.headers.get('X-Local-Token')!=token: return self.send({'error':'Invalid local session'},status=403)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=5_000_000: raise ValueError('Request must be under 5 MB')
                request=json.loads(self.rfile.read(size))
                route=urlparse(self.path).path
                result=build_aircraft_basis(request)
                if route=='/api/analyze': return self.send(result)
                if route=='/api/save':
                    with sqlite3.connect(db) as c:
                        c.execute('INSERT INTO snapshots (created,project,request) VALUES (?,?,?)',(datetime.now(timezone.utc).isoformat(),request['project']['project_id'],json.dumps(request)))
                    return self.send({'saved':True})
                if route=='/api/export':
                    # Revision allocation is transactional per assessment, preserving issued snapshots.
                    with sqlite3.connect(db) as c:
                        c.execute('CREATE TABLE IF NOT EXISTS revisions (assessment TEXT PRIMARY KEY, revision INTEGER NOT NULL)')
                        key=request['project']['project_id']+'/'+request['project']['assessment_id']
                        c.execute('BEGIN IMMEDIATE')
                        old=c.execute('SELECT revision FROM revisions WHERE assessment=?',(key,)).fetchone()
                        revision=max(request['revision'],(old[0]+1) if old else 1)
                        c.execute('INSERT OR REPLACE INTO revisions VALUES (?,?)',(key,revision))
                    result['revision']=revision
                    folder=export_aircraft_basis(result,local/'exports'/secrets.token_hex(12))
                    stream=io.BytesIO()
                    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
                        for p in folder.rglob('*'):
                            if p.is_file():z.write(p,p.relative_to(folder).as_posix())
                    return self.send(stream.getvalue(),'application/zip',filename=f'aircraft-basis-r{revision}.zip')
                return self.send({'error':'Not found'},status=404)
            except (ValueError,KeyError,TypeError) as e: return self.send({'error':str(e)},status=400)
            except Exception as e:
                print(type(e).__name__,str(e))
                return self.send({'error':'Local calculation failed. Review source data and console details.'},status=500)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Aircraft Noise Terminal: http://127.0.0.1:{port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
