import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from shapely.geometry import box, MultiPolygon
from aircraft_noise.core import build_aircraft_basis, airport_data
from aircraft_noise.geometry import runway_geometry, classify, metric, curved_distance, TO_WGS84
from aircraft_noise.acoustics import lookup, terrain
from aircraft_noise.packages import export_aircraft_basis, validate_package, validate_schema

ROOT=Path(__file__).resolve().parents[1]
def request(name='site-demo.json'):return json.loads((ROOT/'fixtures'/name).read_text())

class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.f={'properties':{'runway_pair':'A/B','end_1':'A','end_2':'B'},'geometry':{'coordinates':[list(TO_WGS84.transform(320000,6240000)),list(TO_WGS84.transform(320000,6241000))]}}
    def at(self,x,y):return runway_geometry(*TO_WGS84.transform(x,y),self.f)
    def test_both_ends_and_sides(self):
        for x in [319800,320200]:
            for y,near in [(6239000,'A'),(6242000,'B')]:
                g=self.at(x,y)
                self.assertAlmostEqual(g['ds_m'],200,places=5);self.assertAlmostEqual(g['dl_m'],1000,places=5)
                self.assertAlmostEqual(g['dt_m'],2000,places=5);self.assertEqual(g['near_end'],near)
                self.assertAlmostEqual(g['distance_to_segment_m'],math.hypot(1000,200),places=5)
    def test_beside_does_not_invent_dl_dt(self):
        g=self.at(320200,6240500);self.assertEqual(g['position'],'beside_runway');self.assertIsNone(g['dl_m']);self.assertAlmostEqual(g['distance_to_segment_m'],200,places=5)
    def test_curve_equation_and_invalid_domain(self):
        self.assertAlmostEqual(curved_distance(1000,90,200),200+500*math.pi)
        with self.assertRaises(ValueError):curved_distance(-1,90,0)

class ContourTests(unittest.TestCase):
    def setUp(self):
        self.polys={20:metric(box(151,-34,151.2,-33.8)),25:metric(box(151.05,-33.95,151.15,-33.85)),30:metric(box(151.08,-33.92,151.12,-33.88))}
        self.cover=[150.9,-34.1,151.3,-33.7]
    def at(self,x,y):return classify(x,y,self.polys,self.cover,10)
    def test_between_20_25(self):
        b=self.at(151.02,-33.9);self.assertEqual(b['actual_band'],{'lower':20,'upper':25});self.assertEqual(b['project_contour_label'],25)
    def test_highest_open_band(self):self.assertEqual(self.at(151.1,-33.9)['actual_band'],{'lower':30,'upper':None})
    def test_below_20_workflow_rule(self):
        b=self.at(150.95,-33.9);self.assertTrue(b['report_required']);self.assertIn('not a universal AS',b['report_reason'])
    def test_outside_is_unknown_not_below(self):
        b=self.at(0,0);self.assertEqual(b['coverage_status'],'outside_coverage');self.assertIsNone(b['report_required'])
    def test_boundary_vertex(self):
        b=self.at(151.05,-33.95);self.assertIn(25,b['on_contour']);self.assertTrue(b['boundary_uncertain']);self.assertEqual(b['project_contour_label'],25)
    def test_disconnected_lobe(self):
        self.polys[25]=MultiPolygon([self.polys[25],metric(box(151.01,-33.84,151.03,-33.82))]);self.assertEqual(self.at(151.02,-33.83)['actual_band']['lower'],25)
    def test_supplied_contours_closed_valid(self):
        _,_,polys=airport_data();self.assertEqual(set(polys),{20,25,30,35});self.assertTrue(all(p.is_valid for p in polys.values()))

class AcousticTests(unittest.TestCase):
    def setUp(self):self.t={'distance_axis_m':[100,300,1000],'ds_axis_m':[0,70],'values_db':[[80,75],[78,73],[72,70]]}
    def test_exact_axes_not_transposed(self):self.assertEqual(lookup(self.t,300,70)[0],73)
    def test_irregular_interpolation(self):
        self.t['interpolation_approval']='Synthetic reviewer policy';v,trace=lookup(self.t,650,35,'approved_bilinear');self.assertAlmostEqual(v,73.25);self.assertAlmostEqual(sum(c['weight'] for c in trace),1)
    def test_interpolation_not_implicit(self):
        with self.assertRaises(ValueError):lookup(self.t,200,0)
        with self.assertRaises(ValueError):lookup(self.t,200,0,'approved_bilinear')
    def test_no_extrapolation(self):
        with self.assertRaises(ValueError):lookup(self.t,2000,0)
    def test_blank_asterisk_not_zero(self):
        for v in [None,'*','',float('nan')]:
            self.t['values_db'][0][0]=v
            with self.assertRaises(ValueError):lookup(self.t,100,0)
    def test_terrain_threshold_sign_interpolation(self):
        rows=[[10,190],[20,380]]
        self.assertEqual(terrain(2000,9.999,rows)[0],2000)
        self.assertEqual(terrain(2000,10,rows)[0],1810)
        self.assertEqual(terrain(2000,15,rows)[0],1715)
        self.assertEqual(terrain(2000,-15,rows)[0],2285)
        with self.assertRaises(ValueError):terrain(2000,30,rows)
        with self.assertRaises(ValueError):terrain(100,10,rows)

class ServiceTests(unittest.TestCase):
    def test_deterministic_offline(self):
        q=request()
        with patch('socket.socket',side_effect=AssertionError('Network forbidden')):
            self.assertEqual(build_aircraft_basis(q),build_aircraft_basis(q))
    def test_synthetic_exact_level_no_rooms(self):
        p=build_aircraft_basis(request('synthetic-request.json'))['payload'];self.assertEqual(p['governing_exterior'][0]['level']['value'],81.25)
    def test_project_rejects_unverified_table(self):
        q=request('synthetic-request.json');q['data_mode']='project';p=build_aircraft_basis(q)['payload'];self.assertIsNone(p['operation_cases'][0]['exterior_level']['value'])
    def test_wrong_direction_unsupported(self):
        q=request('synthetic-request.json');q['operation_cases'][0]['direction']='34L';self.assertIsNone(build_aircraft_basis(q)['payload']['governing_exterior'][0]['level']['value'])
    def test_unsupported_aircraft_and_path(self):
        for prop,val in [('aircraft_kind','helicopter'),('path','curved')]:
            q=request('synthetic-request.json');q['operation_cases'][0][prop]=val;self.assertIsNone(build_aircraft_basis(q)['payload']['governing_exterior'][0]['level']['value'])
    def test_missing_data_not_zero(self):
        p=build_aircraft_basis(request())['payload'];self.assertIsNone(p['governing_exterior'][0]['level']['value']);self.assertEqual(p['spectra'],[])
    def test_bad_axis_order_and_crs(self):
        q=request();q['receptors'][0]['latitude']=151.1
        with self.assertRaises(ValueError):build_aircraft_basis(q)
        q=request();q['crs']='EPSG:3857'
        with self.assertRaises(ValueError):build_aircraft_basis(q)
    def test_global_coordinate_unknown(self):
        q=request();q['receptors'][0].update(latitude=90,longitude=180);p=build_aircraft_basis(q)['payload'];self.assertEqual(p['anef']['receptors'][0]['coverage_status'],'outside_coverage');self.assertEqual(p['site']['runway_geometry'],[])
    def test_terrain_does_not_mutate_raw(self):
        q=request('synthetic-request.json');q['receptors'][0]['elevation_m']=10;q['operation_cases'][0]['terrain_category']='landing';q['terrain_tables']={'landing':{'rows':[[10,190],[20,380]],'verification_status':'synthetic','source_refs':['synthetic-table']}}
        p=build_aircraft_basis(q)['payload'];c=p['operation_cases'][0];self.assertAlmostEqual(c['raw_geometry']['dl_m']-c['corrected_geometry']['dl_m'],190)
    def test_nearest_need_not_govern(self):
        q=request('synthetic-request.json');p=build_aircraft_basis(q)['payload'];g=next(g for g in p['site']['runway_geometry'] if g['runway_id']=='16L/34R')
        q['noise_tables']['SYN-02']={**q['noise_tables']['SYN-01'],'distance_axis_m':[g['dl_m']],'ds_axis_m':[g['ds_m']],'values_db':[[90]]}
        q['operation_cases'].append({**q['operation_cases'][0],'operation_case_id':'FAR-RUNWAY','table_id':'SYN-02','runway_id':'16L/34R','direction':'16L'})
        p=build_aircraft_basis(q)['payload'];self.assertEqual(p['governing_exterior'][0]['operation_case_ids'],['FAR-RUNWAY']);self.assertEqual(len(p['operation_cases']),2)
    def test_invalid_spectral_arrays(self):
        q=request();q['spectra']=[{'spectrum_id':'S','operation_case_id':'C','band_type':'octave','centre_frequencies_hz':[125,250],'levels_db':[70],'weighting':'Z','level_basis':'absolute','source_refs':[],'status':'requires_confirmation'}]
        with self.assertRaises(ValueError):build_aircraft_basis(q)

class ContractTests(unittest.TestCase):
    def test_export_consumer_hash_validation_and_immutable_path(self):
        with tempfile.TemporaryDirectory() as d:
            p=export_aircraft_basis(build_aircraft_basis(request('synthetic-request.json')),Path(d)/'package');self.assertTrue(validate_package(p)['valid'])
            with self.assertRaises(ValueError):export_aircraft_basis(build_aircraft_basis(request()),p)
            (p/'aircraft_basis.json').write_text('{}')
            with self.assertRaises(ValueError):validate_package(p)
    def test_path_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            p=export_aircraft_basis(build_aircraft_basis(request()),Path(d)/'package');m=json.loads((p/'manifest.json').read_text());m['files'][0]['path']='../escape.json';(p/'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError):validate_package(p)
    def test_synthetic_approval_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=export_aircraft_basis(build_aircraft_basis(request()),Path(d)/'package');m=json.loads((p/'manifest.json').read_text());m['review_status']='approved';(p/'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError):validate_package(p)
    def test_schema_missing_inputs_actionable(self):
        with self.assertRaisesRegex(ValueError,'receptors'):validate_schema({'project':{}},'aircraft_request.schema.json')

if __name__=='__main__':unittest.main(verbosity=2)
