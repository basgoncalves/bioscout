"""Millard 2012 muscle curves (OpenSim's ActiveForceLengthCurve and ForceVelocityCurve) in numpy.

OpenSim builds them as C2-continuous chains of quintic Bezier segments
(SmoothSegmentedFunctionFactory); this rebuilds the same control points from the
same properties and evaluates them, so a model's Millard2012EquilibriumMuscle
curves come out as OpenSim computes them (checked against opensim 4.6).
"""
import numpy as np

AFL_DEFAULT = dict(min_norm_active_fiber_length=0.4441, transition_norm_fiber_length=0.73,
                   max_norm_active_fiber_length=1.8123, shallow_ascending_slope=0.8616, minimum_value=0.1)
FV_DEFAULT = dict(concentric_slope_at_vmax=0.0, concentric_slope_near_vmax=0.25, isometric_slope=5.0,
                  eccentric_slope_at_vmax=0.0, eccentric_slope_near_vmax=0.15,
                  max_eccentric_velocity_force_multiplier=1.4, concentric_curviness=0.6, eccentric_curviness=0.9)


def _scale_curviness(c):
    return 0.1 + 0.8 * c


def _corner(x0, y0, dydx0, x1, y1, dydx1, c):
    """6 control points of a quintic Bezier from (x0,y0) slope dydx0 to (x1,y1) slope dydx1."""
    if abs(dydx0 - dydx1) > 1e-12:
        xc = (y1 - y0 - x1 * dydx1 + x0 * dydx0) / (dydx0 - dydx1)
        yc = (xc - x1) * dydx1 + y1
    else:
        xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    px = [x0, x0 + c * (xc - x0), x0 + c * (xc - x0), x1 + c * (xc - x1), x1 + c * (xc - x1), x1]
    py = [y0, y0 + c * (yc - y0), y0 + c * (yc - y0), y1 + c * (yc - y1), y1 + c * (yc - y1), y1]
    return np.array(px), np.array(py)


_B = np.array([[-1, 5, -10, 10, -5, 1], [5, -20, 30, -20, 5, 0], [-10, 30, -30, 10, 0, 0],
               [10, -20, 10, 0, 0, 0], [-5, 5, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0]], float)   # power basis, u^5 .. u^0


class Curve:
    """A chain of quintic Bezier segments, linearly extrapolated outside its x range."""

    def __init__(self, segs):
        self.segs = segs
        self.cx = [_B @ px for px, _ in segs]          # polynomial coefficients in u (highest power first)
        self.cy = [_B @ py for _, py in segs]
        self.x0, self.x1 = segs[0][0][0], segs[-1][0][-1]
        self.y0, self.y1 = segs[0][1][0], segs[-1][1][-1]
        px, py = segs[0]; self.s0 = (py[1] - py[0]) / (px[1] - px[0]) if px[1] != px[0] else 0.0
        px, py = segs[-1]; self.s1 = (py[5] - py[4]) / (px[5] - px[4]) if px[5] != px[4] else 0.0

    def __call__(self, x):
        x = np.asarray(x, float)
        out = np.empty_like(x)
        lo, hi = x <= self.x0, x >= self.x1
        out[lo] = self.y0 + self.s0 * (x[lo] - self.x0)
        out[hi] = self.y1 + self.s1 * (x[hi] - self.x1)
        mid = ~(lo | hi)
        if mid.any():
            xm = x[mid]; ym = np.empty_like(xm)
            ends = np.array([px[-1] for px, _ in self.segs])
            k = np.minimum(np.searchsorted(ends, xm), len(self.segs) - 1)
            for s in np.unique(k):
                sel = k == s
                ym[sel] = self._eval(s, xm[sel])
            out[mid] = ym
        return out

    def _eval(self, s, x):
        cx, cy = self.cx[s], self.cy[s]
        px = self.segs[s][0]
        u = np.clip((x - px[0]) / (px[-1] - px[0]), 0, 1)       # start: linear guess
        dcx = np.polyder(cx)
        for _ in range(30):                                    # Newton on Bx(u) = x
            f = np.polyval(cx, u) - x
            d = np.polyval(dcx, u)
            step = np.where(np.abs(d) > 1e-14, f / np.where(np.abs(d) > 1e-14, d, 1), 0.0)
            u = np.clip(u - step, 0, 1)
            if np.max(np.abs(f)) < 1e-13:
                break
        return np.polyval(cy, u)


def active_force_length(p=None):
    q = dict(AFL_DEFAULT, **(p or {}))
    x0, x1, x3 = q["min_norm_active_fiber_length"], q["transition_norm_fiber_length"], q["max_norm_active_fiber_length"]
    x2, ylow, dydx = 1.0, q["minimum_value"], q["shallow_ascending_slope"]
    c = _scale_curviness(1.0)
    xd = 0.05 * x2                          # half-width of the plateau shoulder (OpenSim's xDelta)
    xs = x2 - xd
    y0, dydx0 = 0.0, 0.0
    y1 = 1 - dydx * (xs - x1)
    dydx01 = 1.25 * (y1 - y0) / (x1 - x0)
    x01 = x0 + 0.5 * (x1 - x0); y01 = y0 + 0.5 * (y1 - y0)
    x1s = x1 + 0.5 * (xs - x1); y1s = y1 + 0.5 * (1 - y1); dydx1s = dydx
    y2, dydx2 = 1.0, 0.0
    y3, dydx3 = 0.0, 0.0
    x23 = (x2 + xd) + 0.5 * (x3 - (x2 + xd)); y23 = y2 + 0.5 * (y3 - y2)
    dydx23 = (y3 - y2) / ((x3 - xd) - (x2 + xd))
    segs = [_corner(x0, ylow, dydx0, x01, y01, dydx01, c),
            _corner(x01, y01, dydx01, x1s, y1s, dydx1s, c),
            _corner(x1s, y1s, dydx1s, x2, y2, dydx2, c),
            _corner(x2, y2, dydx2, x23, y23, dydx23, c),
            _corner(x23, y23, dydx23, x3, ylow, dydx3, c)]
    return Curve(segs)


def force_velocity(p=None):
    q = dict(FV_DEFAULT, **(p or {}))
    cC, cE = _scale_curviness(q["concentric_curviness"]), _scale_curviness(q["eccentric_curviness"])
    dC, dNC, dI, dE, dNE = (q["concentric_slope_at_vmax"], q["concentric_slope_near_vmax"], q["isometric_slope"],
                            q["eccentric_slope_at_vmax"], q["eccentric_slope_near_vmax"])
    xC, yC = -1.0, 0.0
    xNC = -0.9; yNC = yC + 0.5 * dNC * (xNC - xC) + 0.5 * dC * (xNC - xC)
    xI, yI = 0.0, 1.0
    xE, yE = 1.0, q["max_eccentric_velocity_force_multiplier"]
    xNE = 0.9; yNE = yE + 0.5 * dNE * (xNE - xE) + 0.5 * dE * (xNE - xE)
    segs = [_corner(xC, yC, dC, xNC, yNC, dNC, cC), _corner(xNC, yNC, dNC, xI, yI, dI, cC),
            _corner(xI, yI, dI, xNE, yNE, dNE, cE), _corner(xNE, yNE, dNE, xE, yE, dE, cE)]
    return Curve(segs)


def _params(el, defaults):
    out = {}
    if el is not None:
        for k in defaults:
            v = el.findtext(k)
            if v is not None and v.strip():
                out[k] = float(v)
    return out


def curves_from_osim(path):
    """{muscle name: (active force-length Curve, force-velocity Curve)} for the model's
    Millard2012EquilibriumMuscle / Millard2012AccelerationMuscle, with each muscle's own
    curve properties (OpenSim defaults for any not set). Other muscle types are left out."""
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    cache, out = {}, {}
    for tag in ("Millard2012EquilibriumMuscle", "Millard2012AccelerationMuscle"):
        for m in root.iter(tag):
            if m.get("name") is None or m.find("GeometryPath") is None:
                continue
            pa = _params(m.find("ActiveForceLengthCurve"), AFL_DEFAULT)
            pv = _params(m.find("ForceVelocityCurve"), FV_DEFAULT)
            ka, kv = ("a",) + tuple(sorted(pa.items())), ("v",) + tuple(sorted(pv.items()))
            if ka not in cache: cache[ka] = active_force_length(pa)
            if kv not in cache: cache[kv] = force_velocity(pv)
            out[m.get("name")] = (cache[ka], cache[kv])
    return out
