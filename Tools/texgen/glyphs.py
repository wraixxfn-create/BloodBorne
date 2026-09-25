"""Procedural, original ritual glyph language for the Hollow Sanctum.

Glyphs are built from a fixed grammar (frame + lattice strokes + arcs + dots)
driven by a seed, so they are original by construction and never resemble
any existing game's rune set. Everything returns signed distances in the
glyph's local [-1, 1] space so callers can render grooves or emission masks.
"""

from __future__ import annotations

import numpy as np

from texlib import sdf_arc, sdf_segment, F32

# 3x3 lattice + centre the strokes snap to (local glyph space, y up)
LATTICE = [(-0.55, -0.55), (0.0, -0.62), (0.55, -0.55),
           (-0.62, 0.0), (0.0, 0.0), (0.62, 0.0),
           (-0.55, 0.55), (0.0, 0.62), (0.55, 0.55)]


def glyph_distance(px: np.ndarray, py: np.ndarray, seed: int, frame: bool = True) -> np.ndarray:
    """Min distance field of one glyph. px/py in local glyph units ([-1,1])."""
    r = np.random.default_rng(seed)
    d = np.full(px.shape, 9.0, F32)

    # --- frame -------------------------------------------------------------
    if frame:
        kind = r.integers(0, 4)
        if kind in (0, 1):
            d = np.minimum(d, np.abs(np.hypot(px, py) - 0.86))
            if kind == 1:  # broken outer ring (gaps at random quadrants)
                a0 = r.uniform(0, np.pi)
                d = np.minimum(d, sdf_arc(px, py, 0, 0, 0.97, a0, a0 + np.pi * 1.2))
        elif kind == 2:  # lozenge
            pts = [(0, 0.95), (0.8, 0), (0, -0.95), (-0.8, 0)]
            for i in range(4):
                a, b = pts[i], pts[(i + 1) % 4]
                d = np.minimum(d, sdf_segment(px, py, a[0], a[1], b[0], b[1]))
        # kind 3: frameless glyph

    # --- spine (every glyph has a vertical or tilted spine for legibility) --
    tilt = r.choice([0.0, 0.0, 0.18, -0.18])
    d = np.minimum(d, sdf_segment(px, py, -tilt, -0.66, tilt, 0.66))

    # --- lattice strokes ---------------------------------------------------
    n_strokes = r.integers(2, 5)
    for _ in range(n_strokes):
        i, j = r.choice(len(LATTICE), 2, replace=False)
        a, b = LATTICE[i], LATTICE[j]
        d = np.minimum(d, sdf_segment(px, py, a[0], a[1], b[0], b[1]))

    # --- crescents / arcs --------------------------------------------------
    for _ in range(r.integers(1, 3)):
        cx, cy = r.choice([-0.3, 0.0, 0.3]), r.choice([-0.3, 0.0, 0.3])
        rad = r.uniform(0.25, 0.5)
        a0 = r.uniform(0, 2 * np.pi)
        d = np.minimum(d, sdf_arc(px, py, cx, cy, rad, a0, a0 + r.uniform(1.6, 3.6)))

    # --- dots --------------------------------------------------------------
    for _ in range(r.integers(0, 3)):
        p = LATTICE[r.integers(0, len(LATTICE))]
        d = np.minimum(d, np.maximum(np.hypot(px - p[0], py - p[1]) - 0.06, 0.0))
    return d


def veil_sigil_distance(px: np.ndarray, py: np.ndarray, seed: int = 404) -> np.ndarray:
    """Central 'Pale Veil' seal: an original motif of three nested, offset
    crescents around a closed vertical slit, ringed by a glyph band.
    px/py in [-1, 1] disc space."""
    rad = np.hypot(px, py)
    ang = np.arctan2(py, px)
    d = np.full(px.shape, 9.0, F32)

    # concentric guide rings
    for rr in (0.97, 0.90, 0.64, 0.58, 0.30):
        d = np.minimum(d, np.abs(rad - rr))

    # radial ticks between 0.90 and 0.97 (every 7.5 deg, long every 45)
    n = 48
    k = np.round(ang / (2 * np.pi / n))
    a_snap = k * (2 * np.pi / n)
    long_tick = (np.mod(k, 6) == 0)
    inner = np.where(long_tick, 0.84, 0.90)
    tx, ty = np.cos(a_snap), np.sin(a_snap)
    along = px * tx + py * ty
    perp = np.abs(-px * ty + py * tx)
    tick = np.where((along > inner) & (along < 0.97), perp, 9.0)
    d = np.minimum(d, tick)

    # glyph band between r 0.64 and 0.90 : 12 glyphs
    n_g = 12
    seg = 2 * np.pi / n_g
    kg = np.floor((ang + np.pi) / seg)
    a_c = -np.pi + (kg + 0.5) * seg
    # local frame for each glyph cell (y points outward)
    ox, oy = np.cos(a_c), np.sin(a_c)
    lx = (px * (-oy) + py * ox) / 0.12
    ly = (px * ox + py * oy - 0.77) / 0.12
    band = np.full(px.shape, 9.0, F32)
    for g in range(n_g):
        m = kg == g
        if not m.any():
            continue
        gd = glyph_distance(lx[m], ly[m], seed + g * 31, frame=False) * 0.12
        band[m] = gd
    d = np.minimum(d, np.where((rad > 0.64) & (rad < 0.90), band, 9.0))

    # three offset crescents (rotational symmetry, 120 deg)
    for i in range(3):
        a = i * 2 * np.pi / 3 + np.pi / 2
        cx, cy = 0.13 * np.cos(a), 0.13 * np.sin(a)
        d = np.minimum(d, sdf_arc(px, py, cx, cy, 0.40, a + 0.9, a + 2 * np.pi - 0.9))

    # the closed slit (vesica) in the centre: intersection outline of two circles
    theta = float(np.arccos(0.16 / 0.21))
    d = np.minimum(d, sdf_arc(px, py, 0.16, 0.0, 0.21, np.pi - theta, np.pi + theta))
    d = np.minimum(d, sdf_arc(px, py, -0.16, 0.0, 0.21, -theta, theta))
    d = np.minimum(d, np.maximum(np.hypot(px, py) - 0.035, 0.0))
    return d
