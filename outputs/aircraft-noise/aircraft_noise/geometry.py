"""WGS84 inputs; metric work in WGS84 / UTM zone 56S (EPSG:32756)."""
import math
from pyproj import Transformer, Geod
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import transform, unary_union, nearest_points

TO_METRES = Transformer.from_crs(4326, 32756, always_xy=True)
TO_WGS84 = Transformer.from_crs(32756, 4326, always_xy=True)
GEOD = Geod(ellps='WGS84')

def metric(geometry):
    return transform(TO_METRES.transform, geometry)

def runway_geometry(lon, lat, feature):
    a, b = feature['geometry']['coordinates']
    x0, y0 = TO_METRES.transform(*a)
    x1, y1 = TO_METRES.transform(*b)
    x, y = TO_METRES.transform(lon, lat)
    length = math.hypot(x1-x0, y1-y0)
    ux, uy = (x1-x0)/length, (y1-y0)/length
    t = (x-x0)*ux + (y-y0)*uy
    q = (x0+t*ux, y0+t*uy)
    ds = math.hypot(x-q[0], y-q[1])
    inside = 0 <= t <= length
    return {'runway_id': feature['properties']['runway_pair'],
            'end_1': feature['properties']['end_1'], 'end_2': feature['properties']['end_2'],
            'length_m': length, 'signed_projection_m': t, 'ds_m': ds,
            'dl_m': None if inside else min(abs(t),abs(t-length)),
            'dt_m': None if inside else max(abs(t),abs(t-length)),
            'distance_to_segment_m': math.hypot(ds, max(-t, t-length, 0)),
            'projection_lon_lat': list(TO_WGS84.transform(*q)),
            'near_end': None if inside else feature['properties']['end_1' if t < 0 else 'end_2'],
            'position': 'beside_runway' if inside else 'beyond_end_1' if t < 0 else 'beyond_end_2',
            'metric_crs': 'EPSG:32756', 'source_refs': ['runways'],
            'status': 'requires_confirmation'}

def contour_polygons(contours):
    result = {}
    for f in contours['features']:
        rings = f['geometry']['coordinates']
        if f['geometry']['type'] != 'MultiLineString':
            raise ValueError('Contour input must contain closed MultiLineStrings')
        polys = []
        for ring in rings:
            if ring[0] != ring[-1]:
                raise ValueError('Unclosed contour: review source before classification')
            poly = Polygon(ring)
            if not poly.is_valid:
                # Never repair digitisation silently.
                raise ValueError('Invalid contour topology: review source before classification')
            polys.append(metric(poly))
        result[int(f['properties']['anef'])] = unary_union(polys)
    return result

def classify(lon, lat, polygons, coverage, uncertainty_m):
    # Extent comes from supplied transform notes; it is provisional viewport coverage.
    within = box(*coverage).covers(Point(lon, lat))
    if not within:
        return {'actual_band': {'lower': None, 'upper': None}, 'band_text': 'UNKNOWN',
                'project_contour_label': None, 'coverage_status': 'outside_coverage',
                'on_contour': [], 'boundary_distance_m': None, 'boundary_uncertain': True,
                'report_required': None, 'report_reason': 'Outside supplied viewport; exposure unknown.'}
    p = metric(Point(lon, lat))
    distances = {n: poly.boundary.distance(p) for n, poly in polygons.items()}
    near = [n for n, d in distances.items() if d <= uncertainty_m]
    on = [n for n, d in distances.items() if d <= 0.01]
    contained = [n for n, poly in polygons.items() if poly.covers(p)]
    low = max(contained) if contained else None
    high = min([n for n in polygons if low is None or n > low], default=None)
    if on:
        low = high = max(on)
    band = f'< {high}' if low is None else f'≥ {low}' if high is None else f'{low}–{high}'
    return {'actual_band': {'lower': low, 'upper': high}, 'band_text': band,
            'project_contour_label': high if low is not None and high else low,
            'coverage_status': 'within_provisional_viewport', 'on_contour': on,
            'near_contours': near, 'boundary_distance_m': min(distances.values()),
            'boundary_uncertain': bool(near), 'report_required': True if low is None else None,
            'report_reason': 'Below 20: report required by project workflow, not a universal AS rule.' if low is None else 'Determine reporting scope with consultant; below-20 rule does not decide this band.'}

def curved_distance(radius_m, angle_degrees, straight_m):
    if radius_m <= 0 or not 0 <= angle_degrees <= 360 or straight_m < 0:
        raise ValueError('Curve radius, angle or straight distance outside domain')
    return straight_m + 2*math.pi*radius_m*angle_degrees/360

def contour_relationships(lon,lat,polygons,tolerance_m):
    _,_,distance=GEOD.inv(lon,lat,151.18,-33.945)
    if distance>100000:return []
    p=metric(Point(lon,lat));rows=[]
    for value,poly in polygons.items():
        nearest=nearest_points(p,poly.boundary)[1];d=p.distance(nearest)
        relation='on' if d<=.01 else 'inside' if poly.covers(p) else 'outside'
        rows.append({'contour':value,'distance_m':d,'relation':relation,
                     'signed_distance_m':0 if relation=='on' else -d if relation=='inside' else d,
                     'nearest_point_lon_lat':list(TO_WGS84.transform(nearest.x,nearest.y)),
                     'within_tolerance':d<=tolerance_m,'source_refs':['contours','georeferencing']})
    return sorted(rows,key=lambda r:(r['distance_m'],r['contour']))
