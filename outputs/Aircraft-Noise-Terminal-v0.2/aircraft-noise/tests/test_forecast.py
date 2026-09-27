import json
import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from shapely.geometry import box
from aircraft_noise.forecast import references,parse_coordinates,surrounding_max,rank_cases,mapping_register
from aircraft_noise.core import build_aircraft_basis
from aircraft_noise.geometry import metric,contour_relationships
from aircraft_noise.packages import export_aircraft_basis,validate_package

ROOT=Path(__file__).resolve().parents[1]
def request():return json.loads((ROOT/'fixtures/terminal-request.json').read_text())

class ForecastTests(unittest.TestCase):
    def test_one_coordinate_string_precision_and_validation(self):
        self.assertEqual(parse_coordinates('-33.89754544671029, 151.13696110226067'),(-33.89754544671029,151.13696110226067))
        for v in ['1 2','1,2,3','nan,1','151,-33','1,inf',',1','90.1,0']:
            with self.assertRaises(ValueError):parse_coordinates(v)
    def test_select_only_2045_sheet(self):
        d=references();self.assertEqual(d['audit']['frequency_sheet'],'Aircraft Type Frequency ANEF -2');self.assertEqual(len(d['frequency']),228);self.assertEqual(len(d['audit']['frequency_codes']),19)
    def test_fractional_frequency_and_dash_retained(self):
        d=references();f=next(f for f in d['frequency'] if f['aircraft_code']=='747400' and f['runway_direction']=='34L' and f['operation']=='departure')
        self.assertEqual(f['day_raw'],.4864);self.assertEqual(f['night_raw'],.5049)
        dash=next(f for f in d['frequency'] if f['aircraft_code']=='747400' and f['runway_direction']=='16L' and f['operation']=='departure')
        self.assertEqual(dash['day_raw'],'-');self.assertIsNone(dash['known_movement_sum'])
    def test_all_matrices_unique_axes_including_recovered_identifiers(self):
        for t in references()['tables'].values():
            self.assertEqual(len(t['distance_axis_m']),51);self.assertEqual(t['distance_axis_m'],sorted(set(t['distance_axis_m'])))
            self.assertEqual(t['ds_axis_m'],sorted(set(t['ds_axis_m'])))
        self.assertEqual(sum(bool(t['identifier_recovery']) for t in references()['tables'].values()),5)
    def test_surrounding_max_nonmonotonic_cell_not_nearest(self):
        t={'distance_axis_m':[100,300],'ds_axis_m':[0,100],'values_db':[[80,95],[70,90]],'cell_refs':[['A1','B1'],['A2','B2']],'source_sheet':'test'}
        v,trace,err=surrounding_max(t,110,5);self.assertEqual(v,95);self.assertEqual(len(trace),4);self.assertIsNone(err)
        self.assertEqual(surrounding_max(t,100,0)[0],80);self.assertEqual(len(surrounding_max(t,100,0)[1]),1)
    def test_no_extrapolation_or_missing_corner_zero(self):
        t=copy.deepcopy(references()['tables']['3.16(B)'])
        with self.assertRaises(ValueError):surrounding_max(t,8000,2700)
        t['values_db'][26][16]='***';v,tr,error=surrounding_max(t,8087,2384);self.assertIsNone(v);self.assertIn('asterisk',error)
    def test_example_three_highest_and_cell_evidence(self):
        r=build_aircraft_basis(request());rank=r['payload']['extensions']['forecast_2045']['rankings'][0]['top_three']
        self.assertEqual([x['level_db_a'] for x in rank],[64,63,62]);self.assertEqual([x['table_id'] for x in rank],['3.16(B)','3.18(B)','3.16(C)'])
        c=next(c for c in r['payload']['operation_cases'] if c['operation_case_id']==rank[0]['operation_case_id'])
        self.assertEqual([t['cell'] for t in c['lookup_trace']],['AQ642','AR642','AQ643','AR643']);self.assertEqual(c['source_discrepancies'],[])
    def test_unmapped_new_variants_not_silently_substituted(self):
        maps=mapping_register({});self.assertIsNone(next(m for m in maps if m['aircraft_code']=='A350-941')['table_base']);self.assertIsNone(next(m for m in maps if m['aircraft_code']=='7378MAX')['table_base'])
        with self.assertRaises(ValueError):mapping_register({'TYPO':{'table_base':'3.15','reason':'test'}})
    def test_overrides_require_reason_and_known_table(self):
        with self.assertRaises(ValueError):mapping_register({'7879':{'table_base':'3.20'}})
        with self.assertRaises(ValueError):mapping_register({'7879':{'table_base':'3.99','reason':'test'}})
    def test_ranking_ties_retained_and_not_frequency_weighted(self):
        def c(i,v):return {'receptor_id':'R','operation_case_id':i,'exterior_level':{'value':v},'aircraft':i,'direction':'34L','operation':'departure','load':'short','table_id':'T'}
        rank=rank_cases([c('B',70),c('A',70),c('C',65),c('D',None)],'R')
        self.assertEqual([x['operation_case_id'] for x in rank],['A','B','C']);self.assertTrue(rank[0]['tied_level']);self.assertTrue(rank[1]['tied_level'])
    def test_nearest_contour_outside_and_inside(self):
        r=build_aircraft_basis(request())['payload']['anef']['receptors'][0]['nearest_contour'];self.assertEqual(r['contour'],20);self.assertEqual(r['relation'],'outside');self.assertAlmostEqual(r['distance_m'],474.0347486,places=3)
        polys={20:metric(box(151,-34,151.2,-33.8))}
        inside=contour_relationships(151.1,-33.9,polys,30)[0];self.assertEqual(inside['relation'],'inside');self.assertLess(inside['signed_distance_m'],0)
        on=contour_relationships(151,-34,polys,30)[0];self.assertEqual(on['relation'],'on');self.assertEqual(on['signed_distance_m'],0)
    def test_elevation_unapplied_explicit_and_corrected_raw_preserved(self):
        q=request();base=build_aircraft_basis(q);cid=base['payload']['extensions']['forecast_2045']['rankings'][0]['top_three'][0]['operation_case_id']
        case=next(c for c in base['payload']['operation_cases'] if c['operation_case_id']==cid);self.assertEqual(case['terrain_correction']['status'],'not_applied')
        q['receptors'][0].update(elevation_m=20,vertical_datum='TEST');q.update(airport_elevation_m=0,airport_vertical_datum='TEST');q['forecast']['height_mode']='corrected';q['forecast']['departure_category_overrides']={'747400':'international'}
        r=build_aircraft_basis(q);c=next(c for c in r['payload']['operation_cases'] if c['operation_case_id']==cid)
        self.assertEqual(c['raw_geometry'],case['raw_geometry']);self.assertAlmostEqual(c['raw_geometry']['dt_m']-c['corrected_geometry']['dt_m'],150)
    def test_new_forecast_package_portable_and_offline(self):
        with patch('socket.socket',side_effect=AssertionError('Network used')):
            a=build_aircraft_basis(request());b=build_aircraft_basis(request());self.assertEqual(a,b)
        with tempfile.TemporaryDirectory() as d:
            p=export_aircraft_basis(a,Path(d)/'package');self.assertTrue(validate_package(p)['valid'])
            saved=json.loads((p/'aircraft_basis.json').read_text());self.assertEqual(saved['extensions']['forecast_2045']['rankings'][0]['top_three'][0]['level_db_a'],64)
    def test_no_application_buttons_or_click_menus(self):
        html=(ROOT/'aircraft_noise/static/index.html').read_text();self.assertNotIn('<button',html);self.assertNotIn('type="submit"',html);self.assertEqual(html.count('<input'),1)

if __name__=='__main__':unittest.main()
