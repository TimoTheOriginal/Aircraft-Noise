import copy
import hashlib
import json
import math
from pathlib import Path
from functools import lru_cache
from .geometry import contour_polygons, classify, runway_geometry, contour_relationships, GEOD
from .acoustics import lookup, terrain

ROOT = Path(__file__).resolve().parent
DATA = ROOT/'data'
VERSION = '0.2.0'

def digest(data): return hashlib.sha256(data).hexdigest()
def quantity(value, unit, descriptor=None, status='requires_confirmation', provenance='calculated', refs=None, formula=None):
    return dict(value=value, unit=unit, descriptor=descriptor, status=status, provenance=provenance,
                source_refs=refs or [], formula_ref=formula, assumptions=[])
def issue(code, message, ids=None, severity='warning'):
    return dict(issue_id=code+('-'+'-'.join(ids) if ids else ''), severity=severity, code=code,
                message=message, affected_ids=ids or [], blocks_approval=True, owner_module='aircraft')

@lru_cache(maxsize=1)
def airport_data():
    contours = json.loads((DATA/'ANEF2045_contours_WGS84.geojson').read_text())
    runways = json.loads((DATA/'ANEF2045_runways_helipad_WGS84.geojson').read_text())
    return contours, runways, contour_polygons(contours)

def source_records():
    result=[]
    for sid, filename, kind in [('contours','ANEF2045_contours_WGS84.geojson','digitised_map'),
                               ('runways','ANEF2045_runways_helipad_WGS84.geojson','runway_coordinates'),
                               ('georeferencing','ANEF2045_georeferencing_notes.txt','georeferencing_notes')]:
        result.append(dict(source_id=sid, title=filename, filename=filename, sha256=digest((DATA/filename).read_bytes()),
                           edition_or_revision='ANEF 2045 supplied extraction', source_type=kind,
                           locator={'method':'supplied local file','reviewer':None,'confidence':'chart-scale; independent checks pending'},
                           verification_status='requires_confirmation'))
    if (DATA/'standard_source_record.json').exists():
        result.append(json.loads((DATA/'standard_source_record.json').read_text()))
    if (DATA/'reference_data.json').exists():
        from .forecast import references
        result.extend(references()['sources'])
    return result

def validate_request(request):
    from .packages import validate_schema
    validate_schema(request,'aircraft_request.schema.json')
    ids=[r['receptor_id'] for r in request['receptors']]
    if len(ids)!=len(set(ids)): raise ValueError('receptors: duplicate receptor_id')
    for r in request['receptors']:
        if not math.isfinite(r['latitude']) or not math.isfinite(r['longitude']): raise ValueError('Coordinates must be finite')
    cases=request.get('operation_cases',[])
    if len({c['operation_case_id'] for c in cases}) != len(cases): raise ValueError('operation_cases: duplicate case ID')
    for c in cases:
        if c['receptor_id'] not in ids: raise ValueError('operation_cases.receptor_id: unknown receptor')
    source_ids=[s['source_id'] for s in request.get('sources',[])]
    if len(source_ids)!=len(set(source_ids)) or set(source_ids)&{s['source_id'] for s in source_records()}:
        raise ValueError('sources: duplicate or reserved source ID')

def build_aircraft_basis(request: dict) -> dict:
    """Deterministic, no network, no timestamps/UUIDs inserted into calculation payload."""
    validate_request(request)
    req=copy.deepcopy(request)
    contours, runway_features, polygons=airport_data()
    sources=source_records()+req.get('sources',[])
    source_map={s['source_id']:s for s in sources}
    issues=[issue('MAP_REVIEW','Supplied chart graphics and viewport extent need independent control-point and coverage verification.'),
            issue('STANDARD_REVIEW','Original AS 2021:2015 pages and independent table transcription checks are not supplied.'),
            issue('OPERATIONS_REVIEW','Confirm forecast movement register and all relevant runway directions before selecting a design maximum.')]
    if req['data_mode']=='synthetic': issues.append(issue('SYNTHETIC','Synthetic test inputs; not a real acoustic assessment.'))
    bands=[]; geometry=[]
    for r in req['receptors']:
        band=classify(r['longitude'],r['latitude'],polygons,[150.798484,-34.0805913,151.297375,-33.7881569],req['uncertainty_m'])
        band['receptor_id']=r['receptor_id']; band['status']='requires_confirmation'
        band['source_refs']=['contours','georeferencing']
        band['contour_relationships']=contour_relationships(r['longitude'],r['latitude'],polygons,req['uncertainty_m'])
        band['nearest_contour']=band['contour_relationships'][0] if band['contour_relationships'] else None
        if band['boundary_uncertain']: issues.append(issue('BOUNDARY_REVIEW','Near a contour or outside coverage; confirm exposure manually.',[r['receptor_id']]))
        if not r['confirmed']: issues.append(issue('SITE_UNCONFIRMED','Confirm the receptor location and coordinate source.',[r['receptor_id']]))
        # Sydney UTM geometry is not meaningful for remote, global coordinates.
        _,_,airport_distance=GEOD.inv(r['longitude'],r['latitude'],151.18,-33.945)
        if airport_distance <= 100000:
            rows=[dict(receptor_id=r['receptor_id'],**runway_geometry(r['longitude'],r['latitude'],f)) for f in runway_features['features'] if f['properties']['feature_type']=='runway']
            rows.sort(key=lambda x:x['distance_to_segment_m'])
            for i,row in enumerate(rows): row['nearest']=i==0
            geometry.extend(rows)
        else:
            issues.append(issue('AIRPORT_DOMAIN','Site is more than 100 km from Sydney; runway geometry not assessed.',[r['receptor_id']]))
        bands.append(band)
    override=req.get('anef_override')
    decisions=[]
    if override:
        decisions.append({'scope':'anef','old_value':copy.deepcopy(bands),'new_value':override,'reason':override['reason'],
                          'reviewer':override['reviewer'],'timestamp':override['timestamp'],'decision':'manual_override_requires_review'})
        for band in bands:
            if band['receptor_id']==override['receptor_id']:
                band['manual_override']=override
                issues.append(issue('MANUAL_OVERRIDE','Manual ANEF override recorded separately; computed band retained.',[band['receptor_id']]))
    operations=[]
    for c in req.get('operation_cases',[]):
        cid=c['operation_case_id']; local=[]; level=None; trace=[]; corrected={'dl_m':None,'dt_m':None}; correction=None
        g=next((g for g in geometry if g['receptor_id']==c['receptor_id'] and g['runway_id']==c['runway_id']),None)
        try:
            if c.get('excluded'):
                raise ValueError('Excluded candidate retained: '+c.get('exclusion_reason','missing evidence'))
            if not c.get('mapping_evidence') or not c.get('relevance_evidence'):
                raise ValueError('Aircraft mapping and operation relevance evidence required')
            if c.get('aircraft_kind','fixed_wing')!='fixed_wing': raise ValueError('Helicopter/specialist aircraft require separate evidence and model')
            if c.get('path','straight')!='straight': raise ValueError('Curved-path case needs reviewed multi-position track implementation')
            if not g or g['position']=='beside_runway': raise ValueError('Unsupported beside-runway geometry or site outside airport domain')
            expected=g['near_end'] if c['operation']=='arrival' else (g['end_2'] if g['near_end']==g['end_1'] else g['end_1'])
            if c['direction']!=expected: raise ValueError('Direction is inconsistent with supported straight arrival/departure geometry')
            table=req.get('noise_tables',{}).get(c['table_id'])
            if not table: raise ValueError('Missing aircraft noise table')
            refs=table.get('source_refs',[])
            if not refs or any(x not in source_map for x in refs): raise ValueError('Table source references missing or unknown')
            if req['data_mode']=='project' and (table.get('verification_status')!='verified' or any(source_map[x]['verification_status']!='verified' for x in refs)):
                raise ValueError('Production noise table/source has not been independently verified')
            r=next(r for r in req['receptors'] if r['receptor_id']==c['receptor_id'])
            elev=r.get('elevation_m'); ae=req.get('airport_elevation_m')
            if elev is None or ae is None or not r.get('vertical_datum') or r['vertical_datum']!=req.get('airport_vertical_datum'):
                raise ValueError('Site and airport elevations with matching vertical datums required')
            corrected={'dl_m':g['dl_m'],'dt_m':g['dt_m']}
            key='dl_m' if c['operation']=='arrival' else 'dt_m'
            terrain_table=req.get('terrain_tables',{}).get(c.get('terrain_category',''),{})
            if abs(elev-ae)>=10 and req['data_mode']=='project' and terrain_table.get('verification_status')!='verified':
                raise ValueError('Verified operation-specific terrain correction column required')
            corrected[key],correction=terrain(g[key],elev-ae,terrain_table.get('rows',[]))
            level,trace=lookup(table,corrected[key],g['ds_m'],c.get('lookup_policy','exact'))
        except (ValueError,KeyError,IndexError,TypeError) as e:
            local.append(issue('CASE_NOT_ASSESSED',str(e),[cid]))
        issues.extend(local)
        operations.append({**c,'raw_geometry':g,'corrected_geometry':corrected,'terrain_correction':correction,
            'exterior_level':quantity(level,'dB(A)','average maximum A-weighted / Slow',
                'not_assessed' if level is None else 'requires_confirmation',refs=req.get('noise_tables',{}).get(c['table_id'],{}).get('source_refs',[]),formula='aircraft-table-lookup-v1'),
            'lookup_trace':trace,'spectrum_ref':c.get('spectrum_ref'),'issues':local})
    forecast_register=[];pending={}
    if req.get('forecast',{}).get('enabled'):
        if req.get('operation_cases'):raise ValueError('Automatic forecast and manually supplied operation cases cannot be combined in one request')
        from .forecast import assess_forecast
        operations,forecast_issues,forecast_register,pending=assess_forecast(req,geometry)
        issues.extend(forecast_issues)
    governing=[]
    for r in req['receptors']:
        candidates=[c for c in operations if c['receptor_id']==r['receptor_id'] and c['exterior_level']['value'] is not None]
        highest=max((c['exterior_level']['value'] for c in candidates),default=None)
        governing.append({'receptor_id':r['receptor_id'],'operation_case_ids':[c['operation_case_id'] for c in candidates if c['exterior_level']['value']==highest],
            'level':quantity(highest,'dB(A)','highest assessed average maximum / Slow',status='not_assessed' if highest is None else 'requires_confirmation'),
            'selection_basis':'Maximum of relevant assessed candidates; unresolved operations may govern. No energy summation.', 'status':'requires_confirmation'})
    spectra=req.get('spectra',[])
    for s in spectra:
        if len(s['centre_frequencies_hz'])!=len(s['levels_db']): raise ValueError('spectra: frequency and level arrays differ in length')
    if not spectra: issues.append(issue('SPECTRA_MISSING','No separately sourced spectra; overall dB(A) is not converted to spectral bands.'))
    catalogue=copy.deepcopy(req.get('criterion_catalogue',[]))
    if not catalogue: issues.append(issue('CRITERIA_UNVERIFIED','No independently verified Table 3.3 catalogue supplied.'))
    for entry in catalogue:
        if req['data_mode']=='project' and any(x not in source_map or source_map[x]['verification_status']!='verified' for x in entry['source_refs']):
            entry['level']['status']='requires_confirmation'
    if req.get('footprint'):
        issues.append(issue('FOOTPRINT_PENDING','Footprint retained but not classified; assess multiple confirmed receptors and review contour crossings.'))
    payload={'project':req['project'], 'site':{'crs':'EPSG:4326','receptors':req['receptors'],'footprint':req.get('footprint'),
        'airport_elevation_m':req.get('airport_elevation_m'),'airport_vertical_datum':req.get('airport_vertical_datum'),'runway_geometry':geometry},
        'anef':{'receptors':bands,'site_acceptability':{'status':'not_assessed','source_refs':['standard-text'],'reason':'Verified Table 2.1 with notes and building-use interpretation required.'},
            'transform_audit':{'source_refs':['georeferencing'],'metric_crs':'EPSG:32756','uncertainty_m':req['uncertainty_m'],
                'coverage_basis':'GeoPDF viewport bounds from supplied notes; map panel extent unverified','status':'requires_confirmation'}},
        'operation_cases':operations,'governing_exterior':governing,'criterion_catalogue':catalogue,'spectra':spectra,
        'assumptions':['Contour band project label uses higher enclosing contour; it is not an interpolated ANEF value.',
                       'All chart geometry remains provisional until independently checked.', 'Nearest runway is minimum distance to finite runway centreline segment; it is not a governing acoustic case.'],
        'calculation_records':[{'formula_id':'runway-vector-v1','metric_crs':'EPSG:32756','applicability':'Straight centreline geometry within 100 km of Sydney','rounding':'Full precision retained; display only rounded','test_ids':['GeometryTests']},
                               {'formula_id':'contour-cover-v1','applicability':'Closed valid supplied contour rings; disconnected rings unioned','rounding':'No ANEF interpolation','test_ids':['ContourTests']}],
        'review_decisions':decisions,'assets':[{'asset_id':'site-map','role':'site_geometry','path':'assets/site-map.svg','caption':'PRELIMINARY · '+req['data_mode'].upper()+' · supplied ANEF 2045 contours and receptors','source_refs':['contours','runways']}]}
    if req.get('forecast',{}).get('enabled'):
        from .forecast import rank_cases, POLICY_EVIDENCE
        payload['extensions']={'forecast_2045':{'mapping_register':forecast_register,'pending_case_counts':pending,
            'ranking_basis':'Descending operation/load cases, as workbook LARGE. Ties retained; not three unique aircraft or frequency-weighted levels.',
            'lookup_policy_evidence':POLICY_EVIDENCE,
            'rankings':[{'receptor_id':r['receptor_id'],'ranked_cases':rank_cases(operations,r['receptor_id']),
                         'top_three':rank_cases(operations,r['receptor_id'])[:3]} for r in req['receptors']]}}
    return {'payload':payload,'sources':sources,'issues':issues,'data_mode':req['data_mode'],'revision':req['revision'],'request':req}

def map_svg(result):
    from html import escape
    contours,runways,_=airport_data()
    w,h=1000,680
    def xy(p): return ((p[0]-150.98)/.29*w,(-33.80-p[1])/.28*h)
    colors={20:'#4d9ba7',25:'#56e5bc',30:'#efc36b',35:'#dd8c75'}
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="ANEF contours and site receptors"><rect width="100%" height="100%" fill="#080f17"/>']
    for f in contours['features']:
        for ring in f['geometry']['coordinates']:
            points=' '.join(f'{x:.2f},{y:.2f}' for x,y in map(xy,ring))
            parts.append(f'<polyline points="{points}" fill="none" stroke="{colors[f["properties"]["anef"]]}" stroke-width="1.5"/>')
    for f in runways['features']:
        if f['properties']['feature_type']=='runway':
            points=' '.join(f'{x:.2f},{y:.2f}' for x,y in map(xy,f['geometry']['coordinates']))
            parts.append(f'<polyline points="{points}" stroke="#eee" stroke-width="4"/>')
    for r in result['payload']['site']['receptors']:
        x,y=xy([r['longitude'],r['latitude']])
        if 0<=x<=w and 0<=y<=h:
            parts.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#efc36b"/><text x="{x+12}" y="{y-12}" fill="white" font-family="monospace">{escape(r["receptor_id"])}</text>')
        else: parts.append(f'<text x="20" y="70" fill="#efc36b" font-family="monospace">{escape(r["receptor_id"])} outside plot extent</text>')
    parts.append(f'<text x="20" y="30" fill="#fff" font-family="monospace">PRELIMINARY / {result["data_mode"].upper()} / ANEF 2045 · N ↑ · EPSG:4326</text></svg>')
    return ''.join(parts)
