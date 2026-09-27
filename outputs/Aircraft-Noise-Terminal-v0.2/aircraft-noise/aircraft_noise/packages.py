import json
import uuid
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from .core import ROOT, digest, map_svg, VERSION

SCHEMAS=ROOT.parent/'schemas'
def validate_schema(data, filename):
    schemas={p.name:json.loads(p.read_text(encoding='utf-8')) for p in SCHEMAS.glob('*.json')}
    registry=Registry().with_resources((s['$id'],Resource.from_contents(s)) for s in schemas.values())
    errors=sorted(Draft202012Validator(schemas[filename],registry=registry,format_checker=FormatChecker()).iter_errors(data),key=lambda e:str(e.path))
    if errors:
        raise ValueError('\n'.join(f'{".".join(map(str,e.path)) or "$"}: {e.message}' for e in errors[:15]))

def save_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def export_aircraft_basis(result: dict, output_dir: Path) -> Path:
    """Create a new immutable directory. Refuse to overwrite existing package paths."""
    output_dir=Path(output_dir)
    validate_schema(result['payload'],'aircraft-basis.schema.json')
    if output_dir.exists(): raise ValueError('Export destination already exists; choose a new revision/directory')
    output_dir.mkdir(parents=True)
    (output_dir/'assets').mkdir()
    save_json(output_dir/'aircraft_basis.json',result['payload'])
    save_json(output_dir/'sources.json',result['sources'])
    (output_dir/'assets/site-map.svg').write_text(map_svg(result),encoding='utf-8')
    files=[]
    for role,path,media in [('payload','aircraft_basis.json','application/json'),('sources','sources.json','application/json'),('site_geometry','assets/site-map.svg','image/svg+xml')]:
        files.append(dict(role=role,path=path,media_type=media,sha256=digest((output_dir/path).read_bytes())))
    p=result['payload']['project']
    manifest=dict(contract_version='1.0.0',package_type='aircraft-basis',package_id=str(uuid.uuid4()),project_id=p['project_id'],assessment_id=p['assessment_id'],
                  revision=result['revision'],producer={'module':'aircraft','software_version':VERSION},created_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                  standard_edition='AS 2021:2015',data_mode=result['data_mode'],review_status='requires_confirmation',upstream=[],files=files,issues=result['issues'],approvals=[])
    validate_schema(manifest,'manifest.schema.json')
    save_json(output_dir/'manifest.json',manifest)
    validate_package(output_dir)
    return output_dir

def validate_package(path):
    path=Path(path).resolve()
    m=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    validate_schema(m,'manifest.schema.json')
    if m['package_type']!='aircraft-basis' or m['producer']['module']!='aircraft': raise ValueError('Only aircraft-basis packages are supported')
    seen=set(); roles={}
    for f in m['files']:
        name=f['path']; pp=PurePosixPath(name)
        if '\\' in name or ':' in name or pp.is_absolute() or '..' in pp.parts or str(pp)!=name or name in seen:
            raise ValueError('Invalid or duplicate package path: '+name)
        dest=(path/name).resolve()
        if not dest.is_relative_to(path): raise ValueError('Path escapes package root')
        if not dest.is_file() or digest(dest.read_bytes())!=f['sha256']: raise ValueError('Missing file or SHA-256 mismatch: '+name)
        seen.add(name); roles[f['role']]=name
    if roles.get('payload')!='aircraft_basis.json' or roles.get('sources')!='sources.json': raise ValueError('Required canonical payload/sources inventory missing')
    payload=json.loads((path/'aircraft_basis.json').read_text(encoding='utf-8'))
    validate_schema(payload,'aircraft-basis.schema.json')
    sources=json.loads((path/'sources.json').read_text(encoding='utf-8'))
    validate_schema(sources,'sources.schema.json')
    if payload['project']['project_id']!=m['project_id'] or payload['project']['assessment_id']!=m['assessment_id']: raise ValueError('Project/assessment IDs mismatch')
    ids=[s['source_id'] for s in sources]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate source IDs')
    def refs(v):
        if isinstance(v,dict):
            if 'source_refs' in v and any(x not in ids for x in v['source_refs']): raise ValueError('Unknown source reference')
            for x in v.values(): refs(x)
        elif isinstance(v,list):
            for x in v: refs(x)
    refs(payload)
    for a in payload['assets']:
        if a['path'] not in seen: raise ValueError('Asset missing from hash inventory')
    if m['review_status']=='approved':
        if m['data_mode']=='synthetic' or any(i['blocks_approval'] for i in m['issues']): raise ValueError('Blocked/synthetic package cannot be approved')
        ph=next(f['sha256'] for f in m['files'] if f['role']=='payload')
        if not m['approvals'] or any(a['reviewed_payload_sha256']!=ph for a in m['approvals']): raise ValueError('Approval not bound to exact payload')
    return {'valid':True,'package_id':m['package_id'],'review_status':m['review_status'],'files_checked':len(seen)}
