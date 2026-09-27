import json
from pathlib import Path
root=Path('outputs/aircraft-noise')
path=root/'schemas/aircraft_request.schema.json'
schema=json.loads(path.read_text())
schema['properties']['forecast']={'type':'object','required':['enabled','lookup_policy','height_mode'],'additionalProperties':False,'properties':{
    'enabled':{'type':'boolean'},'lookup_policy':{'const':'surrounding_max'},
    'height_mode':{'enum':['uncorrected_screening','corrected']},
    'mapping_overrides':{'type':'object','additionalProperties':{'type':'object','required':['table_base','reason'],'properties':{'table_base':{'type':'string'},'reason':{'type':'string','minLength':5}},'additionalProperties':False}},
    'departure_category_overrides':{'type':'object','additionalProperties':{'enum':['domestic_jet','international','propeller_light']}}}}
path.write_text(json.dumps(schema,indent=2)+'\n')
path=root/'schemas/aircraft-basis.schema.json';s=json.loads(path.read_text());s['properties']['extensions']={'type':'object'};path.write_text(json.dumps(s,indent=2)+'\n')
q=json.loads((root/'fixtures/site-demo.json').read_text());q['data_mode']='project';q['project'].update(project_id='SITE-001',assessment_id='SITE-001-R01',assessment_purpose='Preliminary 2045 aircraft noise screening');q['receptors'][0].update(latitude=-33.89754544671029,longitude=151.13696110226067,coordinate_source='Coordinate example supplied by user; replace with project location',confirmed=False)
q['forecast']={'enabled':True,'lookup_policy':'surrounding_max','height_mode':'uncorrected_screening','mapping_overrides':{},'departure_category_overrides':{}}
(root/'fixtures/terminal-request.json').write_text(json.dumps(q,indent=2)+'\n')
