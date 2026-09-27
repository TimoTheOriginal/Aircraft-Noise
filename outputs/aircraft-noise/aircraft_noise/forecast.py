"""Source-linked ANEF2045 candidate selection and preliminary table screening."""
import copy
import json
import math
from functools import lru_cache
from pathlib import Path
from .acoustics import _bracket, terrain

DATA=Path(__file__).resolve().parent/'data'
POLICY='bilinear_interpolation'
POLICY_EVIDENCE=('Two-axis linear interpolation between the four bracketing aircraft-noise cells. '
    'This is an engineering implementation choice: AS 2021:2015 Clause 3.1.4 says to read off the '
    'appropriate value but does not prescribe interpolation for Tables 3.4–3.58. The Standard '
    'expressly permits interpolation only for the Table 3.2 land-height corrections.')
# Only direct table-model identities / forecast-code spelling expansion. Newer
# and unmatched variants remain explicitly unresolved, not silently proxied.
MAPPINGS={'7773ER':('3.19','777-300ER forecast code; Table3.1 maps 777-3ZGER to 777-300'),
          '7878R':('3.20','787-8 forecast-code expansion'),
          '747400':('3.16','747-400 forecast-code expansion'),
          '7673ER':('3.18','767-300ER forecast-code expansion to representative 767-300'),
          'A330-301':('3.7','Exact representative aircraft'),
          'A321-232':('3.6','Exact representative aircraft'),
          '737800':('3.15','737-800 forecast-code expansion'),
          '737700':('3.14','737-700 forecast-code expansion'),
          'A320-232':('3.5','Exact representative aircraft'),
          'DHC830-C':('3.40','DHC8-300 forecast-code expansion to Dash8-300'),
          'SF340-C':('3.49','Saab340 forecast-code expansion'),
          'DHC6':('3.38','DHC6 / Dash6 representative identity'),
          'CNA441':('3.42','Cessna441 mapped by Table3.1 to Cessna ConquestII')}

@lru_cache(maxsize=1)
def references():
    return json.loads((DATA/'reference_data.json').read_text(encoding='utf-8'))

def parse_coordinates(text):
    if not isinstance(text,str) or text.count(',')!=1:
        raise ValueError('Enter latitude, longitude; for example -33.95931060086562, 151.06228141530434')
    try:lat,lon=(float(v.strip()) for v in text.split(','))
    except ValueError:raise ValueError('Latitude and longitude must be numbers separated by one comma')
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180:
        raise ValueError('Latitude must be -90..90 and longitude -180..180, in WGS84')
    return lat,lon

def interpolate_noise(table,distance,ds):
    """Bilinear interpolation over the bracketing cells, without extrapolation."""
    a,b,wy=_bracket(table['distance_axis_m'],distance)
    c,d,wx=_bracket(table['ds_axis_m'],ds)
    trace=[]
    row_weights={a:1-wy}; row_weights[b]=row_weights.get(b,0)+wy
    column_weights={c:1-wx}; column_weights[d]=column_weights.get(d,0)+wx
    for row,row_weight in sorted(row_weights.items()):
        for column,column_weight in sorted(column_weights.items()):
            weight=row_weight*column_weight
            if weight == 0: continue
            val=table['values_db'][row][column]
            trace.append({'row':row,'column':column,'distance_m':table['distance_axis_m'][row],
                'ds_m':table['ds_axis_m'][column],'value_db':val,'cell':table['cell_refs'][row][column],
                'weight':weight,'sheet':table['source_sheet'],'source_id':'noise-extraction'})
    missing=[x for x in trace if not isinstance(x['value_db'],(int,float)) or isinstance(x['value_db'],bool) or not math.isfinite(x['value_db'])]
    if missing:
        return None,trace,'Table neighbourhood includes blank/asterisk cells; no zero substitution. Clause3.1.4 Note3 significance review required.'
    value=sum(x['value_db']*x['weight'] for x in trace)
    for x in trace:x['selected']=True
    return value,trace,None

def mapping_register(overrides):
    data=references(); out=[]
    if set(overrides)-set(data['audit']['frequency_codes']):
        raise ValueError('Mapping override contains an unknown forecast aircraft code')
    for code in data['audit']['frequency_codes']:
        val=MAPPINGS.get(code); override=overrides.get(code)
        if override:
            if not isinstance(override,dict) or not override.get('reason') or not override.get('table_base'):
                raise ValueError('Mapping override requires table_base and reason')
            val=(override['table_base'],'Manual preliminary mapping: '+override['reason'])
            if val[0]+'(A)' not in data['tables']:raise ValueError('Unknown mapping table '+val[0])
        out.append({'aircraft_code':code,'table_base':val[0] if val else None,'basis':val[1] if val else 'No directly supported mapping in supplied 2015 references; acoustic justification required.',
                    'status':'requires_confirmation' if val else 'not_assessed','manual_override':override})
    return out

def assess_forecast(req,geometry):
    from .core import quantity, issue
    settings=req['forecast']; data=references()
    if settings['lookup_policy']!=POLICY:raise ValueError('Forecast route supports bilinear_interpolation')
    register=mapping_register(settings.get('mapping_overrides',{})); mapping={r['aircraft_code']:r for r in register}
    operations=[]; issues=[]
    diff_index={(d['table'],d['extraction_cell']):d for d in data['audit']['differences']}
    for receptor in req['receptors']:
        for f in data['frequency']:
            g=next((g for g in geometry if g['receptor_id']==receptor['receptor_id'] and f['runway_direction'] in [g['end_1'],g['end_2']]),None)
            m=mapping[f['aircraft_code']];base=m['table_base'];op=f['operation']
            tids=([base+'(A)'] if op=='arrival' else [t for t in [base+'(B)',base+'(C)'] if t in data['tables']]) if base else [None]
            for tid in tids:
                cid=f"{receptor['receptor_id']}-{f['aircraft_code']}-{f['runway_direction']}-{op}-{tid or 'UNMAPPED'}"
                level=None;trace=[];reason=None;code='CASE_NOT_ASSESSED';corrected={'dl_m':g['dl_m'] if g else None,'dt_m':g['dt_m'] if g else None};correction=None
                table=data['tables'].get(tid); conflicts=[]
                if not f['has_positive_movement']:
                    code='MOVEMENT_UNRESOLVED';reason='No positive numeric movement in the supplied day/night cells. Dashes remain unresolved, not zero.'
                elif not g or g['position']=='beside_runway':
                    code='GEOMETRY_UNSUPPORTED';reason='Straight beyond-runway geometry unavailable; no forced DL/DT.'
                else:
                    direction=g['near_end'] if op=='arrival' else (g['end_2'] if g['near_end']==g['end_1'] else g['end_1'])
                    if direction!=f['runway_direction']:
                        code='DIRECTION_NOT_MODELLED';reason='Opposite-direction operation retained; not represented by this straight beyond-end path.'
                    elif not table:
                        code='AIRCRAFT_MAPPING_REQUIRED';reason=m['basis']
                    else:
                        try:
                            key='dl_m' if op=='arrival' else 'dt_m'
                            if settings['height_mode']=='corrected':
                                site=receptor.get('elevation_m');airport=req.get('airport_elevation_m')
                                if site is None or airport is None or not receptor.get('vertical_datum') or receptor['vertical_datum']!=req.get('airport_vertical_datum'):
                                    raise ValueError('Corrected mode requires site/airport elevations and matching vertical datums')
                                category=settings.get('departure_category_overrides',{}).get(f['aircraft_code'])
                                if op=='arrival': column=1
                                elif abs(site-airport)<10: column=2 # column unused below trigger
                                elif category in ['domestic_jet','international','propeller_light']:
                                    column={'domestic_jet':2,'international':3,'propeller_light':4}[category]
                                else:raise ValueError('Set the aircraft-specific departure terrain category before correcting DT')
                                corrected[key],correction=terrain(g[key],site-airport,[[r[0],r[column]] for r in data['height_rows']])
                                correction['source_refs']=['noise-extraction'];correction['source_sheet']='Land Height';correction['source_column']='ABCDE'[column]
                            else:correction={'status':'not_applied','reason':'Uncorrected screening; elevations not assumed equal. Raw DL/DT used.'}
                            level,trace,reason=interpolate_noise(table,corrected[key],g['ds_m'])
                            if reason:code='TABLE_CELL_UNAVAILABLE'
                            conflicts=[diff_index[(tid,t['cell'])] for t in trace if (tid,t['cell']) in diff_index]
                        except (ValueError,IndexError) as e:
                            reason=str(e);code='TABLE_DOMAIN_OR_TERRAIN'
                local=[issue(code,reason,[cid])] if reason else []
                if conflicts:local.append(issue('SOURCE_CELL_CONFLICT','Selected neighbourhood differs between workbooks; extraction2 values retained as requested.',[cid]))
                operations.append({'operation_case_id':cid,'receptor_id':receptor['receptor_id'],'aircraft':f['aircraft_code'],
                    'representative_aircraft':table['aircraft'] if table else None,'runway_id':g['runway_id'] if g else None,'direction':f['runway_direction'],
                    'operation':op,'load':table['qualifier'] or 'unspecified table load' if table else None,'table_id':tid,
                    'mapping_evidence':m['basis'],'frequency':copy.deepcopy(f),'raw_geometry':g,'corrected_geometry':corrected,'terrain_correction':correction,
                    'exterior_level':quantity(level,'dB(A)','average maximum A-weighted / Slow',status='requires_confirmation' if level is not None else 'not_assessed',refs=['noise-extraction'],formula='bilinear-interpolation-v1'),
                    'lookup_policy':POLICY,'lookup_policy_evidence':POLICY_EVIDENCE,'lookup_trace':trace,'source_discrepancies':conflicts,
                    'table_locator':{'sheet':'Aircraft Matrices','table':tid,'printed_page':table['printed_page'],'pdf_page':table['pdf_page'],'identifier_recovery':table['identifier_recovery']} if table else None,
                    'spectrum_ref':None,'issues':local})
    known=[c for c in operations if c['exterior_level']['value'] is not None]
    unresolved=CounterCodes(operations)
    issues.append(issue('PRELIMINARY_TABLE_POLICY',POLICY_EVIDENCE))
    if settings['height_mode']=='uncorrected_screening':issues.append(issue('ELEVATIONS_NOT_APPLIED','Ranking uses raw DL/DT for uncorrected screening. Supply elevations and departure categories for height-corrected results.'))
    if unresolved:issues.append(issue('FORECAST_CASES_PENDING',f'{len(operations)-len(known)} of {len(operations)} retained operation/load cases have no level. See case register for directions, mappings, movement markers and table domains.'))
    issues.append(issue('REFERENCE_RECONCILIATION',f"{data['audit']['comparison']['different']} differing cells across supplied workbooks. Extraction2 is the numeric source; relevant differences appear in each lookup trace."))
    return operations,issues,register,unresolved

def CounterCodes(cases):
    out={}
    for c in cases:
        if c['exterior_level']['value'] is None:
            code=c['issues'][0]['code'] if c['issues'] else 'UNKNOWN';out[code]=out.get(code,0)+1
    return out

def rank_cases(cases,receptor_id):
    valid=[c for c in cases if c['receptor_id']==receptor_id and c['exterior_level']['value'] is not None]
    ordered=sorted(valid,key=lambda c:(-c['exterior_level']['value'],c['operation_case_id']))
    return [{'position':i+1,'operation_case_id':c['operation_case_id'],'aircraft':c['aircraft'],'direction':c['direction'],
             'operation':c['operation'],'load':c['load'],'table_id':c['table_id'],'level_db_a':c['exterior_level']['value'],
             'tied_level':sum(x['exterior_level']['value']==c['exterior_level']['value'] for x in ordered)>1} for i,c in enumerate(ordered)]
