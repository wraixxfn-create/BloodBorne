"""Tileable procedural texture primitives for the Vespershade arena material kit.

Every function here is *periodic by construction* (FFT-domain filtering,
periodic Voronoi, np.roll based derivatives) so all generated maps tile
seamlessly in Unity. Everything is deterministic from integer seeds.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

F32 = np.float32


# ---------------------------------------------------------------------------
# Random / noise
# ---------------------------------------------------------------------------

def rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _freq_grid(h: int, w: int):
    fy = np.fft.fftfreq(h).astype(F32)[:, None]
    fx = np.fft.fftfreq(w).astype(F32)[None, :]
    return fy, fx


def band_noise(shape, feature_px: float, seed: int, aniso=(1.0, 1.0)) -> np.ndarray:
    """Gaussian-filtered white noise with features of roughly `feature_px`.

    aniso=(ay, ax): >1 stretches features along that axis (e.g. (1, 8) gives
    long horizontal streaks). Output: zero mean, unit std, perfectly tileable.
    """
    h, w = shape
    white = rng(seed).standard_normal((h, w)).astype(F32)
    fy, fx = _freq_grid(h, w)
    sigma_f = 1.0 / (np.pi * max(feature_px, 0.5))
    ay, ax = aniso
    g = np.exp(-(((fy * ay) ** 2 + (fx * ax) ** 2) / (2.0 * sigma_f ** 2))).astype(F32)
    out = np.real(np.fft.ifft2(np.fft.fft2(white) * g)).astype(F32)
    out -= out.mean()
    s = out.std()
    return out / s if s > 1e-8 else out


def fbm(shape, base_px: float, octaves: int, seed: int, gain=0.5, lacunarity=2.0, aniso=(1.0, 1.0)):
    """Fractal sum of band noises. Returns ~[-1, 1]-ish (normalised to std 0.5)."""
    total = np.zeros(shape, F32)
    amp, px, norm = 1.0, base_px, 0.0
    for o in range(octaves):
        total += amp * band_noise(shape, px, seed + 7919 * o, aniso)
        norm += amp
        amp *= gain
        px /= lacunarity
    total /= norm
    return total / (2.0 * total.std() + 1e-8)


def ridged(shape, base_px, octaves, seed, aniso=(1.0, 1.0)):
    n = fbm(shape, base_px, octaves, seed, aniso=aniso)
    return 1.0 - np.abs(n) * 2.0


def blur(img: np.ndarray, sigma_px: float) -> np.ndarray:
    """Periodic gaussian blur (FFT)."""
    if sigma_px <= 0:
        return img.copy()
    h, w = img.shape[:2]
    fy, fx = _freq_grid(h, w)
    g = np.exp(-2.0 * (np.pi ** 2) * (sigma_px ** 2) * (fy ** 2 + fx ** 2)).astype(F32)
    if img.ndim == 2:
        return np.real(np.fft.ifft2(np.fft.fft2(img) * g)).astype(F32)
    return np.stack([blur(img[..., c], sigma_px) for c in range(img.shape[2])], -1)


def remap(x, a, b, c=0.0, d=1.0):
    return c + (np.clip((x - a) / (b - a + 1e-8), 0.0, 1.0)) * (d - c)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-8), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def normalize01(x):
    lo, hi = np.percentile(x, 0.5), np.percentile(x, 99.5)
    return np.clip((x - lo) / (hi - lo + 1e-8), 0.0, 1.0).astype(F32)


def uv_grid(shape):
    h, w = shape
    v, u = np.mgrid[0:h, 0:w].astype(F32)
    return (u + 0.5) / w, (v + 0.5) / h  # u right, v down (image space)


def warp_coords(u, v, amount, feature_px, seed):
    shape = u.shape
    du = band_noise(shape, feature_px, seed) * amount
    dv = band_noise(shape, feature_px, seed + 1) * amount
    return (u + du) % 1.0, (v + dv) % 1.0


# ---------------------------------------------------------------------------
# Periodic Voronoi
# ---------------------------------------------------------------------------

def voronoi(shape, n_points: int, seed: int, relax: int = 0, coords=None, points=None):
    """Periodic Voronoi on the unit torus.

    Returns (f1, f2, cell_id, points) with distances in *tile units*.
    """
    h, w = shape
    r = rng(seed)
    if points is None:
        pts = r.random((n_points, 2))
        for _ in range(relax):  # Lloyd relaxation on a coarse grid for even cells
            gu, gv = uv_grid((128, 128))
            q = np.stack([gu.ravel(), gv.ravel()], 1)
            _, idx = cKDTree(pts, boxsize=1.0).query(q, k=1)
            new = np.zeros_like(pts)
            for i in range(len(pts)):
                m = idx == i
                if m.any():
                    # circular mean to respect wrap-around
                    ang = q[m] * 2 * np.pi
                    new[i] = (np.arctan2(np.sin(ang).mean(0), np.cos(ang).mean(0)) / (2 * np.pi)) % 1.0
                else:
                    new[i] = pts[i]
            pts = new
    else:
        pts = points
    if coords is None:
        u, v = uv_grid(shape)
    else:
        u, v = coords
    q = np.stack([u.ravel(), v.ravel()], 1) % 1.0
    tree = cKDTree(pts, boxsize=1.0 + 1e-9)
    d, idx = tree.query(q, k=2)
    f1 = d[:, 0].reshape(h, w).astype(F32)
    f2 = d[:, 1].reshape(h, w).astype(F32)
    cid = idx[:, 0].reshape(h, w)
    return f1, f2, cid, pts


# ---------------------------------------------------------------------------
# Derived maps
# ---------------------------------------------------------------------------

def height_to_normal(height: np.ndarray, strength: float) -> np.ndarray:
    """OpenGL / Unity convention (+Y = up in texture space). Periodic."""
    h = height.astype(F32)
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    drow = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    nx = -dx * strength
    ny = drow * strength  # image rows go down, texture V goes up
    nz = np.ones_like(h)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx * inv, ny * inv, nz * inv], -1).astype(F32)


def blend_normals(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Whiteout blend of two tangent-space normals."""
    n = np.stack([a[..., 0] + b[..., 0], a[..., 1] + b[..., 1], a[..., 2] * b[..., 2]], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def height_to_ao(height: np.ndarray, radii=(2, 6, 16), strength=1.0, weights=None) -> np.ndarray:
    h = height.astype(F32)
    ao = np.zeros_like(h)
    weights = weights or [1.0] * len(radii)
    for r, wgt in zip(radii, weights):
        ao += wgt * np.maximum(blur(h, r) - h, 0.0) / (r ** 0.35)
    ao /= (np.percentile(ao, 99.5) + 1e-6)
    return np.clip(1.0 - ao * strength, 0.0, 1.0).astype(F32)


def srgb_to_linear(c):
    c = np.asarray(c, F32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, F32), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def col(r, g, b):
    """sRGB 0-255 -> float sRGB array (albedo is authored & stored in sRGB)."""
    return np.array([r, g, b], F32) / 255.0


def lerp(a, b, t):
    t = np.asarray(t, F32)
    if t.ndim == 2 and np.ndim(a) >= 1 and np.shape(a)[-1:] == (3,):
        t = t[..., None]
    elif t.ndim == 2 and np.ndim(b) >= 1 and np.shape(b)[-1:] == (3,):
        t = t[..., None]
    return a + (b - a) * t


def sdf_segment(px, py, ax, ay, bx, by):
    pax, pay = px - ax, py - ay
    bax, bay = bx - ax, by - ay
    hcoef = np.clip((pax * bax + pay * bay) / (bax * bax + bay * bay + 1e-9), 0.0, 1.0)
    dx, dy = pax - bax * hcoef, pay - bay * hcoef
    return np.sqrt(dx * dx + dy * dy)


def sdf_arc(px, py, cx, cy, r, a0, a1):
    """Distance to a circular arc from angle a0 to a1 (radians, a1 > a0)."""
    ang = np.arctan2(py - cy, px - cx)
    mid = 0.5 * (a0 + a1)
    half = 0.5 * (a1 - a0)
    rel = (ang - mid + np.pi) % (2 * np.pi) - np.pi
    inside = np.abs(rel) <= half
    d_ring = np.abs(np.sqrt((px - cx) ** 2 + (py - cy) ** 2) - r)
    e0x, e0y = cx + r * np.cos(a0), cy + r * np.sin(a0)
    e1x, e1y = cx + r * np.cos(a1), cy + r * np.sin(a1)
    d_end = np.minimum(np.hypot(px - e0x, py - e0y), np.hypot(px - e1x, py - e1y))
    return np.where(inside, d_ring, d_end)
