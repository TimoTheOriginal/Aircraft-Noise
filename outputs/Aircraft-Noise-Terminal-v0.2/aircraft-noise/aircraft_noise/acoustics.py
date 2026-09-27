"""Explicit table policies; no OCR-to-production conversion or extrapolation."""
import bisect
import math

def _bracket(axis, value):
    if not axis or axis != sorted(set(axis)) or not all(math.isfinite(x) for x in axis):
        raise ValueError('Axes must be finite, unique and increasing')
    if value < axis[0] or value > axis[-1]:
        raise ValueError('Out of range; extrapolation prohibited')
    i = bisect.bisect_left(axis, value)
    return (i, i, 0) if axis[i] == value else (i-1, i, (value-axis[i-1])/(axis[i]-axis[i-1]))

def lookup(table, distance, ds, policy='exact'):
    rows, cols = table['distance_axis_m'], table['ds_axis_m']
    vals = table['values_db']
    if len(vals) != len(rows) or any(len(row) != len(cols) for row in vals):
        raise ValueError('Table dimensions do not match distance-row / DS-column axes')
    a,b,wy = _bracket(rows, distance)
    c,d,wx = _bracket(cols, ds)
    if (a != b or c != d) and policy != 'approved_bilinear':
        raise ValueError('No exact cell; source-supported or approved lookup policy required')
    if policy == 'approved_bilinear' and not table.get('interpolation_approval'):
        raise ValueError('Interpolation approval evidence is missing')
    cells = {}
    for r,wr in [(a,1-wy),(b,wy)]:
        for col,wc in [(c,1-wx),(d,wx)]:
            if wr*wc > 0: cells[(r,col)] = cells.get((r,col),0)+wr*wc
    for r,c in cells:
        if not isinstance(vals[r][c], (int,float)) or isinstance(vals[r][c], bool) or not math.isfinite(vals[r][c]):
            raise ValueError('Blank, asterisk or unreadable cell requires a significance decision')
    return sum(vals[r][c]*w for (r,c),w in cells.items()), [
        {'row':r,'column':c,'distance_m':rows[r],'ds_m':cols[c],'value_db':vals[r][c],'weight':w}
        for (r,c),w in cells.items()]

def terrain(raw_distance, relative_height, rows):
    if abs(relative_height) < 10:
        return raw_distance, {'correction_m':0, 'basis':'Magnitude below 10 m', 'weights':[]}
    heights = [r[0] for r in rows]
    a,b,w = _bracket(heights,abs(relative_height))
    correction = rows[a][1]*(1-w)+rows[b][1]*w
    corrected = raw_distance-correction if relative_height > 0 else raw_distance+correction
    if corrected < 0:
        raise ValueError('Corrected distance negative; operation-specific review required')
    return corrected, {'correction_m':correction,'relative_height_m':relative_height,
                       'weights':[1-w,w],'source_rows':[rows[a],rows[b]],'basis':'Table 3.2 policy'}
