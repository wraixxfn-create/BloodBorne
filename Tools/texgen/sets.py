"""Texture set recipes for the Hollow Sanctum material kit.

Each recipe returns a dict of float32 maps:
  base      HxWx3 (sRGB, 0-1)  [+ optional 'base_alpha' HxW]
  normal    HxWx3 tangent space, OpenGL (+Y) convention, -1..1
  roughness HxW   (0 = mirror, 1 = fully rough)  -- authored as ROUGHNESS
  metallic  HxW   (only for sets containing metal)
  ao        HxW
  emission  HxW   (ritual only; single-channel mask)

Colour targets are PBR-plausible (dielectric albedo ~30-240 sRGB, metals use
measured-ish F0 tints) so the dark mood comes from lighting, not crushed
albedo.
"""

from __future__ import annotations

import numpy as np

from texlib import (F32, band_noise, fbm, ridged, blur, voronoi, uv_grid, warp_coords,
                    height_to_normal, blend_normals, height_to_ao, smoothstep, remap,
                    normalize01, col, lerp, rng)
from glyphs import glyph_distance, veil_sigil_distance


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ashlar_layout(shape, seed, rows=7, min_w=0.22, max_w=0.46, warp=0.0035):
    """Running-bond ashlar courses on the unit torus.

    Returns block id map, distance-to-joint (tile units), local block uv and
    per-block random table.
    """
    h, w = shape
    r = rng(seed)
    u, v = uv_grid(shape)
    u, v = warp_coords(u, v, warp, 22, seed + 3)

    heights = r.uniform(0.75, 1.25, rows)
    heights /= heights.sum()
    row_edges = np.concatenate([[0.0], np.cumsum(heights)])
    row = np.clip(np.searchsorted(row_edges, v, side="right") - 1, 0, rows - 1)
    v0 = row_edges[row]
    v1 = row_edges[row + 1]

    block_edges = []
    offsets = r.random(rows)
    for _ in range(rows):
        widths = []
        while sum(widths) < 1.0 - min_w:
            widths.append(r.uniform(min_w, max_w))
        widths = np.array(widths)
        widths /= widths.sum()
        block_edges.append(np.concatenate([[0.0], np.cumsum(widths)]))

    bid = np.zeros(shape, np.int32)
    du = np.zeros(shape, F32)
    bu = np.zeros(shape, F32)
    base_id = 0
    for i in range(rows):
        m = row == i
        uu = (u[m] - offsets[i]) % 1.0
        edges = block_edges[i]
        k = np.clip(np.searchsorted(edges, uu, side="right") - 1, 0, len(edges) - 2)
        left, right = edges[k], edges[k + 1]
        du[m] = np.minimum(uu - left, right - uu)
        bu[m] = (uu - left) / (right - left)
        bid[m] = base_id + k
        base_id += len(edges) - 1
    dv = np.minimum(v - v0, v1 - v)
    bv = (v - v0) / (v1 - v0)
    dist = np.minimum(du, dv).astype(F32)
    table = r.random((base_id, 8)).astype(F32)
    return bid, dist, bu, bv.astype(F32), table


def _crack_network(shape, seed, cells, width_px, coverage=0.55, jag=0.012, jag_px=10):
    """Branching crack mask (1 = crack centre) from warped Voronoi edges."""
    u, v = uv_grid(shape)
    u, v = warp_coords(u, v, jag, jag_px, seed)
    u, v = warp_coords(u, v, jag * 0.25, 4, seed + 9)
    f1, f2, cid, _ = voronoi(shape, cells, seed + 1, coords=(u, v))
    edge = (f2 - f1) * shape[0]  # px distance to cell boundary (approx x2)
    keep = band_noise(shape, shape[0] / 6, seed + 2) * 0.5 + 0.5
    keep = smoothstep(1.0 - coverage - 0.1, 1.0 - coverage + 0.1, keep)
    wmod = (band_noise(shape, 40, seed + 4) * 0.35 + 1.0) * width_px
    crack = np.clip(1.0 - edge / np.maximum(wmod, 0.3), 0.0, 1.0) * keep
    return crack.astype(F32)


def _finish(base, normal, rough, ao, metallic=None, emission=None, base_alpha=None):
    out = {"base": np.clip(base, 0, 1).astype(F32),
           "normal": normal.astype(F32),
           "roughness": np.clip(rough, 0.02, 1.0).astype(F32),
           "ao": np.clip(ao, 0, 1).astype(F32)}
    if metallic is not None:
        out["metallic"] = np.clip(metallic, 0, 1).astype(F32)
    if emission is not None:
        out["emission"] = np.clip(emission, 0, 1).astype(F32)
    if base_alpha is not None:
        out["base_alpha"] = np.clip(base_alpha, 0, 1).astype(F32)
    return out


# ---------------------------------------------------------------------------
# 1. OLD STONE - salt-bitten ashlar masonry (walls, pillars, floor, trim)
# ---------------------------------------------------------------------------

def old_stone(size=1024, seed=1101):
    shape = (size, size)
    px = size  # pixels per tile
    bid, dist, bu, bv, T = _ashlar_layout(shape, seed)
    dpx = dist * px

    mortar_half = 3.2 + band_noise(shape, 30, seed + 10) * 0.9
    chip = np.maximum(band_noise(shape, 9, seed + 11), 0) * 5.0 * (T[bid, 5] > 0.35)
    bevel = 7.0 + T[bid, 4] * 6.0
    prof = np.clip((dpx - mortar_half - chip) / bevel, 0.0, 1.0)
    prof = 1.0 - (1.0 - prof) ** 2.2

    fine = fbm(shape, 14, 4, seed + 20)
    med = fbm(shape, 70, 3, seed + 21)
    pits = np.maximum(band_noise(shape, 2.2, seed + 22) - 1.9, 0) * 0.5
    tilt = ((bu - 0.5) * (T[bid, 0] - 0.5) + (bv - 0.5) * (T[bid, 1] - 0.5)) * 0.10
    erosion = T[bid, 2] * 0.06 * ridged(shape, 40, 3, seed + 23)
    face = 0.78 + tilt + 0.05 * fine + 0.05 * med - erosion - pits
    mortar = 0.18 + 0.035 * fbm(shape, 6, 3, seed + 24)
    height = np.where(dpx < mortar_half, mortar, mortar + (face - mortar) * prof).astype(F32)

    n = height_to_normal(height, strength=size / 64.0)
    n_micro = height_to_normal(fbm(shape, 3, 2, seed + 25), strength=1.2)
    normal = blend_normals(n, n_micro)
    ao = height_to_ao(height, radii=(2, 6, 18), strength=0.85)

    # --- albedo: cold blue-grey limestone with warm ochre-stained blocks ----
    cold = col(104, 104, 112)
    warm = col(116, 106, 94)
    dark = col(70, 70, 78)
    t_warm = T[bid, 3] ** 2.5
    base = lerp(cold, warm, t_warm)
    tone = 0.86 + T[bid, 6] * 0.24
    base = base * tone[..., None]
    base = lerp(base, dark, np.clip(0.5 - med * 0.9, 0, 1) * 0.55)
    base = base * (1.0 + fine[..., None] * 0.08)
    # salt efflorescence blooms creeping up from each joint (sea-salt erosion)
    salt_src = np.exp(-np.maximum(dpx - mortar_half, 0) / 10.0) * (bv > 0.55)
    salt = np.clip(salt_src * (band_noise(shape, 18, seed + 30) * 0.5 + 0.35), 0, 1) * (T[bid, 7] > 0.55)
    base = lerp(base, col(150, 148, 144), salt * 0.55)
    mortar_col = col(82, 78, 72) * (1.0 + 0.1 * fbm(shape, 5, 2, seed + 31))[..., None]
    base = lerp(mortar_col, base, smoothstep(0.0, 0.35, prof))
    base = base * (0.62 + 0.38 * ao)[..., None]
    base = lerp(base, col(126, 124, 124), np.clip(chip / 5.0, 0, 1) * 0.35)  # fresh chips

    rough = 0.80 + 0.07 * fine - 0.04 * med + salt * 0.10
    rough = np.where(dpx < mortar_half + 1, 0.93, rough)
    return _finish(base, normal, rough, ao)


# ---------------------------------------------------------------------------
# 2. CRACKED STONE - monolithic, spalled, fractured (statues, broken pillars)
# ---------------------------------------------------------------------------

def cracked_stone(size=1024, seed=2202):
    shape = (size, size)
    big = fbm(shape, 160, 4, seed)
    fine = fbm(shape, 10, 4, seed + 1)
    lam = band_noise(shape, 30, seed + 2, aniso=(1.0, 9.0))  # sedimentary bands

    cracks_major = _crack_network(shape, seed + 10, 9, 6.0, coverage=0.7, jag=0.02, jag_px=48)
    cracks_minor = _crack_network(shape, seed + 20, 38, 2.4, coverage=0.5, jag=0.008, jag_px=20)
    cracks = np.maximum(cracks_major, cracks_minor * 0.8)

    spall_n = band_noise(shape, 55, seed + 30) + 0.35 * band_noise(shape, 12, seed + 31)
    spall = smoothstep(1.25, 1.4, spall_n)
    spall_rim = smoothstep(1.05, 1.25, spall_n) - spall

    pitting = np.maximum(band_noise(shape, 2.0, seed + 40) - 1.6, 0.0)
    height = (0.7 + 0.06 * big + 0.035 * fine + 0.02 * lam
              - 0.22 * cracks ** 0.7 - 0.10 * spall - 0.06 * pitting).astype(F32)
    height += 0.012 * fbm(shape, 3, 2, seed + 41) * spall  # rough fracture bed

    normal = blend_normals(height_to_normal(height, size / 40.0),
                           height_to_normal(fbm(shape, 2.5, 2, seed + 42), 1.0))
    ao = height_to_ao(height, radii=(1.5, 5, 16), strength=0.95)

    base = lerp(col(122, 120, 122), col(106, 104, 110), normalize01(big))
    base = base * (1.0 + 0.07 * fine + 0.05 * lam)[..., None]
    # fresh stone inside spalls is paler & warmer, rim is stained
    base = lerp(base, col(136, 132, 126), spall * 0.55)
    base = lerp(base, col(82, 80, 80), spall_rim * 0.35)
    # dark biological staining creeping out from the cracks
    stain = np.clip(blur(cracks, 6) * 2.5, 0, 1) * (band_noise(shape, 26, seed + 50) * 0.4 + 0.6)
    base = lerp(base, col(58, 60, 56), np.clip(stain, 0, 1) * 0.55)
    base = lerp(base, col(26, 25, 26), cracks ** 0.8)
    base = base * (0.6 + 0.4 * ao)[..., None]

    rough = 0.84 + 0.06 * fine + 0.08 * spall + 0.1 * cracks
    return _finish(base, normal, rough, ao)


# ---------------------------------------------------------------------------
# 3. DARK WOOD - aged, checked, ebonised timber (beams, scaffold, doors)
# ---------------------------------------------------------------------------

def dark_wood(size=1024, seed=3303):
    shape = (size, size)
    u, v = uv_grid(shape)
    r = rng(seed)
    # grain runs along U. ring phase = integer rings per tile + periodic warp
    warp = (fbm(shape, 180, 3, seed, aniso=(1.0, 6.0)) * 2.6
            + fbm(shape, 40, 2, seed + 1, aniso=(1.0, 10.0)) * 0.5)
    phase = v * 22.0 + warp
    # knots: periodic gaussian bumps distort the grain around them
    for k in range(2):
        cx, cy = r.random(2)
        dx = (u - cx + 0.5) % 1.0 - 0.5
        dy = (v - cy + 0.5) % 1.0 - 0.5
        rad = np.sqrt((dx * 3.2) ** 2 + dy ** 2)  # elongated along grain
        s = r.uniform(0.018, 0.03)
        phase += 2.4 * np.exp(-(rad / (s * 2.2)) ** 2)
    ring = phase % 1.0
    late = smoothstep(0.62, 0.92, ring) * (1.0 - smoothstep(0.92, 1.0, ring))
    fibres = band_noise(shape, 1.6, seed + 2, aniso=(1.0, 28.0))
    pores = np.maximum(band_noise(shape, 1.2, seed + 3, aniso=(1.0, 6.0)) - 1.4, 0)

    checks = _crack_network(shape, seed + 10, 14, 1.6, coverage=0.35, jag=0.002)
    # re-orient cracks along grain: keep crack pixels only where aligned streaks exist
    streak = band_noise(shape, 3.0, seed + 11, aniso=(1.0, 60.0))
    checks = np.clip(smoothstep(1.9, 2.4, streak) + checks * 0.25, 0, 1)
    worm = smoothstep(2.7, 3.0, band_noise(shape, 1.3, seed + 12))
    rot = smoothstep(0.35, 0.9, fbm(shape, 120, 3, seed + 13, aniso=(1.0, 3.0)))

    height = (0.6 - 0.05 * late + 0.025 * fibres - 0.04 * pores
              - 0.35 * checks - 0.25 * worm - 0.05 * rot * fbm(shape, 6, 2, seed + 14)).astype(F32)
    normal = blend_normals(height_to_normal(height, size / 90.0),
                           height_to_normal(fibres * 0.5, 0.8))
    ao = height_to_ao(height, radii=(1.5, 4, 12), strength=0.8)

    early_c = col(66, 48, 36)
    late_c = col(34, 24, 18)
    base = lerp(early_c, late_c, late)
    base = base * (1.0 + 0.06 * fibres)[..., None]
    base = lerp(base, col(96, 88, 78), rot * 0.45)          # grey fungal bleaching
    base = lerp(base, col(18, 13, 10), np.maximum(checks, worm))
    tone = normalize01(fbm(shape, 300, 2, seed + 20))
    base = base * (0.85 + 0.25 * tone)[..., None]
    base = base * (0.65 + 0.35 * ao)[..., None]

    rough = 0.72 + 0.08 * late + 0.10 * rot + 0.2 * np.maximum(checks, worm) + 0.03 * fibres
    return _finish(base, normal, rough, ao)


# ---------------------------------------------------------------------------
# 4. AGED METAL - blackened wrought iron with rust blooms (chains, doors)
# ---------------------------------------------------------------------------

def aged_metal(size=512, seed=4404):
    shape = (size, size)
    f1, f2, cid, _ = voronoi(shape, 60, seed, relax=1)
    dents = -(f1 * np.sqrt(60)) ** 2  # hammered facets
    dents = blur(dents.astype(F32), 1.2)
    fine = fbm(shape, 6, 3, seed + 1)
    pits = smoothstep(1.7, 2.3, band_noise(shape, 1.4, seed + 2))
    rust_n = fbm(shape, 60, 4, seed + 3) + 0.25 * fbm(shape, 8, 2, seed + 4)
    rust = smoothstep(0.45, 0.95, rust_n) * (0.6 + 0.4 * normalize01(fbm(shape, 5, 2, seed + 8)))
    scale_n = fbm(shape, 25, 3, seed + 5)
    blackened = smoothstep(-0.9, 0.6, scale_n)

    height = (0.6 + 0.05 * normalize01(dents) + 0.01 * fine - 0.08 * pits
              + 0.035 * rust * fbm(shape, 3, 2, seed + 6)).astype(F32)
    normal = blend_normals(height_to_normal(height, size / 26.0),
                           height_to_normal(fine * 0.3, 0.6))
    ao = height_to_ao(height, radii=(1.5, 4, 10), strength=0.7)

    bare = col(140, 138, 134)            # iron F0 ~0.53 linear, a bit darkened by wear
    patina = col(58, 56, 55)             # thin magnetite film
    rust_c = lerp(col(92, 46, 26), col(58, 32, 20), normalize01(fbm(shape, 10, 2, seed + 7)))
    base = lerp(bare, patina, 0.35 + blackened * 0.6)
    base = lerp(base, rust_c, rust)
    base = lerp(base, col(30, 20, 15), pits)
    base = base * (0.7 + 0.3 * ao)[..., None]

    metallic = np.clip(1.0 - rust - pits * 0.8, 0, 1) * (1.0 - blackened * 0.3)
    rough = 0.38 + 0.22 * blackened + 0.5 * rust + 0.05 * fine + 0.3 * pits
    return _finish(base, normal, rough, ao, metallic=metallic)


# ---------------------------------------------------------------------------
# 5. OXIDIZED METAL - cast bronze under verdigris runs (braziers, fittings)
# ---------------------------------------------------------------------------

def oxidized_metal(size=512, seed=5505):
    shape = (size, size)
    cast = fbm(shape, 30, 4, seed)
    fine = fbm(shape, 4, 3, seed + 1)
    pits = smoothstep(1.8, 2.4, band_noise(shape, 1.5, seed + 2))
    # verdigris: cavities + streaks running downward (+V in image = down)
    runs = band_noise(shape, 6, seed + 3, aniso=(14.0, 1.0))
    patch = fbm(shape, 70, 4, seed + 4)
    height0 = 0.6 + 0.04 * cast + 0.01 * fine - 0.06 * pits
    cav = 1.0 - height_to_ao(height0.astype(F32), radii=(2, 6), strength=1.0)
    verd = np.clip(smoothstep(0.35, 0.95, patch + 0.3 * runs) * 0.85 + cav * 1.4, 0, 1)
    crust = verd * (0.5 + 0.5 * normalize01(fbm(shape, 3, 2, seed + 5)))
    cuprite = smoothstep(-0.8, 0.8, fbm(shape, 70, 3, seed + 6)) * (1 - verd)

    height = (height0 + 0.05 * crust).astype(F32)
    normal = blend_normals(height_to_normal(height, size / 30.0),
                           height_to_normal(fine * 0.4, 0.7))
    ao = height_to_ao(height, radii=(1.5, 4, 12), strength=0.75)

    bronze = col(150, 108, 72)
    cup = col(74, 46, 32)
    green = lerp(col(66, 100, 88), col(112, 140, 126), normalize01(runs))
    base = lerp(bronze, cup, cuprite * 0.6)
    base = lerp(base, green, verd)
    base = lerp(base, col(40, 30, 24), pits * (1 - verd))
    base = base * (0.72 + 0.28 * ao)[..., None]

    metallic = np.clip((1.0 - verd) * (1.0 - cuprite * 0.85) - pits * 0.5, 0, 1)
    rough = 0.34 + 0.3 * cuprite + 0.55 * verd + 0.04 * fine + 0.2 * pits
    return _finish(base, normal, rough, ao, metallic=metallic)


# ---------------------------------------------------------------------------
# 6. STAINED GLASS - leaded mosaic; alpha = per-cell palette key
# ---------------------------------------------------------------------------

def stained_glass(size=1024, seed=6606):
    shape = (size, size)
    u, v = uv_grid(shape)
    uw, vw = warp_coords(u, v, 0.004, 40, seed)
    f1, f2, cid, pts = voronoi(shape, 34, seed + 1, relax=2, coords=(uw, vw))
    edge_px = (f2 - f1) * size * 0.5
    lead_w = 5.5
    lead = 1.0 - smoothstep(lead_w - 1.2, lead_w + 0.6, edge_px)
    lead_profile = np.sqrt(np.clip(1.0 - (edge_px / lead_w) ** 2, 0, 1))
    r = rng(seed + 2)
    key = r.random(len(pts)).astype(F32)
    cell_key = key[cid]
    streak = band_noise(shape, 14, seed + 3, aniso=(1.0, 5.0))
    seeds = smoothstep(2.4, 2.9, band_noise(shape, 1.8, seed + 4))
    ripple = fbm(shape, 22, 3, seed + 5)
    cell_tilt = (r.random((len(pts), 2)).astype(F32) - 0.5)[cid]
    glass_h = 0.5 + 0.02 * ripple + (uw - 0.5) * 0 + 0.012 * (cell_tilt[..., 0] * np.sin(uw * 40) + cell_tilt[..., 1] * np.cos(vw * 40))
    height = np.where(lead > 0.5, 0.5 + 0.35 * lead_profile, glass_h - 0.01 * seeds).astype(F32)
    normal = height_to_normal(height, size / 90.0)
    ao = height_to_ao(height, radii=(1.5, 5), strength=0.6)

    grime = np.clip(np.exp(-np.maximum(edge_px - lead_w, 0) / 9.0) * (band_noise(shape, 20, seed + 6) * 0.3 + 0.8), 0, 1)
    glass = col(238, 236, 230) * (0.92 + 0.08 * streak)[..., None] * (0.82 + 0.18 * cell_key)[..., None]
    glass = lerp(glass, col(150, 146, 136), grime * 0.55)
    glass = lerp(glass, col(255, 255, 255), seeds * 0.5)
    lead_col = col(72, 72, 74) * (0.85 + 0.15 * normalize01(fbm(shape, 4, 2, seed + 7)))[..., None]
    base = lerp(glass, lead_col, lead)

    metallic = lead * 0.9
    rough = np.where(lead > 0.5, 0.55, 0.06 + 0.35 * grime + 0.03 * streak)
    return _finish(base, normal, rough, ao, metallic=metallic, base_alpha=cell_key)


# ---------------------------------------------------------------------------
# 7. CANDLE WAX - layered drips, aged ivory (tinted per variant)
# ---------------------------------------------------------------------------

def candle_wax(size=512, seed=7707):
    shape = (size, size)
    u, v = uv_grid(shape)
    drips = band_noise(shape, 5.0, seed, aniso=(18.0, 1.0))           # vertical runs
    drip_len = band_noise(shape, 40, seed + 1, aniso=(2.0, 1.0))
    ridges = smoothstep(0.5, 1.4, drips) * smoothstep(-0.8, 0.6, drip_len)
    # rounded drip tips: blur vertically-biased
    ridges = blur(ridges.astype(F32), 2.0)
    lumps = fbm(shape, 18, 3, seed + 2)
    micro = fbm(shape, 2.5, 2, seed + 3)
    height = (0.5 + 0.12 * ridges + 0.03 * lumps + 0.004 * micro).astype(F32)
    normal = height_to_normal(height, size / 40.0)
    ao = height_to_ao(height, radii=(2, 6), strength=0.55)

    ivory = col(226, 212, 180)
    aged = col(196, 172, 124)
    base = lerp(ivory, aged, smoothstep(-0.8, 0.9, fbm(shape, 60, 3, seed + 4)) * 0.55)
    base = lerp(base, ivory * 1.04, ridges * 0.35)
    soot = smoothstep(2.3, 2.8, band_noise(shape, 1.6, seed + 5))
    base = lerp(base, col(60, 54, 48), soot * 0.6)
    base = base * (0.85 + 0.15 * ao)[..., None]
    rough = 0.48 - 0.12 * ridges + 0.06 * lumps + 0.3 * soot
    return _finish(base, normal, rough, ao)


# ---------------------------------------------------------------------------
# 8. DUST - fine settled powder with clumps & fibres (layer + standalone)
# ---------------------------------------------------------------------------

def dust(size=512, seed=8808):
    shape = (size, size)
    grain = band_noise(shape, 1.0, seed)
    clumps = fbm(shape, 24, 4, seed + 1)
    density = normalize01(fbm(shape, 60, 4, seed + 2) + 0.3 * clumps)
    fib = np.zeros(shape, F32)
    r = rng(seed + 3)
    u, v = uv_grid(shape)
    from texlib import sdf_segment
    for _ in range(26):  # stray fibres / hair
        ax, ay = r.random(2)
        ang = r.uniform(0, np.pi)
        ln = r.uniform(0.02, 0.07)
        bx, by = ax + np.cos(ang) * ln, ay + np.sin(ang) * ln
        dx = (u - ax + 0.5) % 1.0 - 0.5 + ax
        dy = (v - ay + 0.5) % 1.0 - 0.5 + ay
        d = sdf_segment(dx, dy, ax, ay, bx, by) * size
        fib = np.maximum(fib, np.clip(1.0 - d / 0.9, 0, 1) * r.uniform(0.3, 0.8))
    height = (0.5 + 0.05 * clumps + 0.01 * grain + 0.03 * fib).astype(F32)
    normal = height_to_normal(height, size / 60.0)
    ao = height_to_ao(height, radii=(1.5, 5), strength=0.4)
    base = lerp(col(128, 120, 108), col(152, 146, 134), normalize01(clumps))
    base = base * (1.0 + 0.05 * grain)[..., None]
    base = lerp(base, col(92, 86, 80), fib * 0.6)
    rough = 0.93 + 0.04 * grain
    return _finish(base, normal, rough, ao, base_alpha=density)


# ---------------------------------------------------------------------------
# 9. RITUAL SURFACE - dark polished basalt with carved, seeping glyphs
# ---------------------------------------------------------------------------

def ritual_surface(size=1024, seed=9909):
    shape = (size, size)
    u, v = uv_grid(shape)
    cells = 4
    cu = np.floor(u * cells).astype(int)
    cv = np.floor(v * cells).astype(int)
    lx = ((u * cells) % 1.0 - 0.5) * 2.0
    ly = -((v * cells) % 1.0 - 0.5) * 2.0
    d = np.full(shape, 9.0, F32)
    r = rng(seed)
    cell_seeds = r.integers(0, 1_000_000, (cells, cells))
    lx_s, ly_s = lx / 0.78, ly / 0.78  # glyph occupies 78% of cell
    for i in range(cells):
        for j in range(cells):
            m = (cu == i) & (cv == j)
            d[m] = glyph_distance(lx_s[m], ly_s[m], int(cell_seeds[j, i])) * 0.78
    d_px = d * (size / cells) * 0.5
    groove_w = 4.5
    groove = 1.0 - smoothstep(groove_w * 0.4, groove_w, d_px)
    # tile border inscribed lines (slab joints) every cell
    ju = np.minimum((u * cells) % 1.0, 1 - (u * cells) % 1.0) * size / cells
    jv = np.minimum((v * cells) % 1.0, 1 - (v * cells) % 1.0) * size / cells
    joint = 1.0 - smoothstep(1.0, 2.6, np.minimum(ju, jv))

    veins = _crack_network(shape, seed + 5, 22, 1.1, coverage=0.4, jag=0.01)
    speck = smoothstep(2.2, 2.8, band_noise(shape, 1.0, seed + 6))
    big = fbm(shape, 200, 3, seed + 7)
    fine = fbm(shape, 6, 3, seed + 8)
    wear = normalize01(blur((band_noise(shape, 120, seed + 9) > 0.4).astype(F32), 30))

    height = (0.7 + 0.02 * big + 0.006 * fine - 0.25 * groove - 0.18 * joint - 0.08 * veins).astype(F32)
    normal = blend_normals(height_to_normal(height, size / 55.0),
                           height_to_normal(fine * 0.25, 0.5))
    ao = height_to_ao(height, radii=(1.5, 4, 14), strength=0.9)

    basalt = lerp(col(40, 40, 46), col(52, 50, 58), normalize01(big))
    base = basalt * (1.0 + 0.05 * fine)[..., None]
    base = lerp(base, col(92, 100, 104), speck * 0.5)        # mica glints
    base = lerp(base, col(58, 70, 72), groove * 0.7)        # pale ash residue in cuts
    base = lerp(base, col(22, 22, 26), joint * 0.8)
    base = base * (0.7 + 0.3 * ao)[..., None]

    rough = 0.42 - 0.14 * wear + 0.04 * fine - 0.18 * speck + 0.4 * groove + 0.45 * joint
    emission = np.clip(groove * 0.95 + veins * 0.45, 0, 1) * (0.8 + 0.2 * normalize01(fbm(shape, 40, 2, seed + 10)))
    return _finish(base, normal, rough, ao, emission=emission)


def ritual_sigil(size=1024):
    """UV-mapped emission mask for the central disc (cylinder cap UVs)."""
    u, v = uv_grid((size, size))
    px, py = u * 2 - 1, -(v * 2 - 1)
    d = veil_sigil_distance(px, py)
    dpx = d * size * 0.5
    line = 1.0 - smoothstep(1.4, 3.2, dpx)
    glow = np.exp(-dpx / 10.0) * 0.25
    mask = np.clip(line + glow, 0, 1) * (np.hypot(px, py) < 0.995)
    return mask.astype(F32)


def ritual_glyph_strip(width=1024, height=256, seed=9950):
    """UV-mapped emission mask for the 2.2 x 0.65 m ritual plates."""
    u, v = uv_grid((height, width))
    xs = u * (width / height)  # square glyph cells
    n = int(round(width / height))
    cell = np.clip(np.floor(xs).astype(int), 0, n - 1)
    lx = ((xs % 1.0) - 0.5) * 2.0 / 0.72
    ly = -(v - 0.5) * 2.0 / 0.72
    d = np.full(u.shape, 9.0, F32)
    for i in range(n):
        m = cell == i
        d[m] = glyph_distance(lx[m], ly[m], seed + i * 13) * 0.72
    dpx = d * height * 0.5
    line = 1.0 - smoothstep(1.2, 3.0, dpx)
    # border rails
    rail = np.minimum(np.abs(v - 0.06), np.abs(v - 0.94)) * height
    line = np.maximum(line, 1.0 - smoothstep(0.8, 2.2, rail))
    glow = np.exp(-dpx / 8.0) * 0.2
    return np.clip(line + glow, 0, 1).astype(F32)


# ---------------------------------------------------------------------------
# Shared macro variation (anti-tiling)
# ---------------------------------------------------------------------------

def macro_variation(size=256, seed=1010):
    shape = (size, size)
    rch = normalize01(fbm(shape, 60, 4, seed))                          # large blotches
    gch = normalize01(fbm(shape, 14, 4, seed + 1))                      # medium mottling
    bch = normalize01(band_noise(shape, 4, seed + 2, aniso=(16.0, 1.0))  # vertical leak streaks
                      * (fbm(shape, 30, 2, seed + 3) * 0.6 + 0.7))
    return np.stack([rch, gch, bch], -1).astype(F32)
