"""Surface: photograph the finished painting under a raking light (Canvas.finish).

finish() does not change the canvas. Like a photograph of the painting, it returns a new HxWx3
uint8 sRGB image (hand it to studio.save), so you can keep painting and finish again. The same
canvas always gives the same image: craquelure draws on its own generator seeded by the canvas
seed, never on cv.rng.
"""

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from scipy.special import ndtr

from atelier.color import linear_to_srgb

RELIEF = 3.0          # px of surface relief per unit of paint height
WEAVE_RELIEF = 2.5    # px of relief of the bare weave at weave=1
BURY = 0.35           # paint height that buries the weave to 1/e
AMBER = np.array([1.0, 0.8, 0.5])   # transmission of a fully aged varnish (linear RGB)
AMBIENT = 0.3         # share of the light that comes from the room, not the lamp: shadows are never black


def finish(cv, light=(-0.5, -0.6), varnish=0.2, weave=0.3, crackle=0.0, scale=1.0):
    """Light the paint relief and return the painting as an HxWx3 uint8 sRGB image. cv is unchanged.

    light: (x, y) direction towards the lamp in image coordinates (x right, y down); (-0.5, -0.6)
        is the classic upper left. Its length sets how low the lamp rakes: elevation
        z = sqrt(1 - x^2 - y^2). A 3-tuple (x, y, z) gives the direction explicitly.
    varnish: 0 = unvarnished (paint glossy, bare ground matte), 1 = thick old varnish: glossy
        everywhere, warm amber tint, deeper darks, finer texture filled in for the highlights.
    weave: 0..1, how much the canvas texture (tooth) shows in the light; thick paint buries it.
    crackle: 0..1 how far craquelure has gone: a little opens fine hairlines in a few patches, more
        opens the whole network, then finer cracks between, wider and darker, with cupped islands.
    scale: the canvas size relative to 2048 px wide, the S a script multiplies its sizes by. The
        relief is lit and the craquelure drawn as on a 2048 px render, so a study at scale=900/2048
        looks about as embossed as the 2048 px final. 1 = heights lit as they lie in pixels.
    """
    rng = np.random.default_rng([cv.seed, 7])
    h = cv.height.astype(np.float32)
    # Paint relief is part stroke-sized (it shrinks with the canvas, so its slopes steepen as 1/scale) and part
    # pixel-sized (bristle furrows, anti-aliased edges: the same slopes at any size); sqrt(scale) evens out the
    # mix, measured on the starter and on a sheet of large strokes. The weave's size is set by ground() in pixels.
    z = RELIEF * np.sqrt(scale) * gaussian_filter(h, 0.6) + weave * WEAVE_RELIEF * cv.tooth * np.exp(-h / BURY)
    color = cv.color.astype(np.float32)
    if crackle > 0:
        crack, cup = _craquelure(rng, cv.shape, crackle, scale)
        z = z + scale * (0.5 * crackle * cup - 1.2 * crack)
        color = color * (1 - (0.35 + 0.35 * crackle) * np.minimum(crack, 1))[..., None]

    lx, ly, lz = _unit(light)
    gy, gx = np.gradient(z)
    lamp = np.clip((lz - gx * lx - gy * ly) / np.sqrt(gx * gx + gy * gy + 1), 0, None) / lz
    shade = AMBIENT + (1 - AMBIENT) * lamp
    cavity = np.clip(1 + 0.12 * (z - gaussian_filter(z, 3.0)), 0.75, 1.05)

    hx, hy, hz = _unit((lx, ly, lz + 1))
    zs = gaussian_filter(z, 0.4 + 1.5 * varnish)
    sy, sx = np.gradient(zs)
    ndoth = np.clip((hz - sx * hx - sy * hy) / np.sqrt(sx * sx + sy * sy + 1), 0, 1)
    gloss = 0.18 * np.clip(h / 0.2, 0, 1) + 0.35 * varnish
    spec = gloss * ndoth ** (30 + 90 * varnish)

    tint = AMBER ** varnish
    color = color ** (1 + 0.2 * varnish) * tint
    out = color * (shade * cavity)[..., None] + spec[..., None] * (0.3 + 0.7 * tint)
    return np.round(linear_to_srgb(np.clip(out, 0, 1)) * 255).astype(np.uint8)


def _unit(v):
    v = np.asarray(v, np.float64)
    if len(v) == 2:
        v = np.append(v, np.sqrt(max(1 - v @ v, 0.04)))
    return v / np.linalg.norm(v)


def _craquelure(rng, shape, amount, scale=1.0):
    """Crack network (0..1, 1 = open crack) and the cupping of the islands between cracks (0..1).

    amount (0..1) opens a growing share of the primary network, in patches, and past 0.3 a finer
    secondary network between its cracks; the cracks widen with it. Sizes are for 2048 px, times scale.
    """
    H, W = shape
    crack = np.zeros(shape, np.float32)
    cup = np.zeros(shape, np.float32)
    yy, xx = np.mgrid[:H, :W].astype(np.float32)
    width = (0.6 + 0.8 * amount) * scale
    for cell, strength, share in (((75 - 40 * amount) * scale, 1.0, amount ** 0.5),
                                  ((30 - 14 * amount) * scale, 0.7, np.clip((amount - 0.3) / 0.7, 0, 1) ** 0.8)):
        if share <= 0:
            continue
        cell = max(cell, 4.0)
        warp = [0.16 * cell * _noise(rng, shape, cell / 3) + 0.3 * _noise(rng, shape, 1.0) for _ in range(2)]
        gy, gx = np.mgrid[-cell:H + cell:cell, -cell:W + cell:cell]
        seeds = np.column_stack([gx.ravel(), gy.ravel()]) + rng.uniform(0, cell, (gx.size, 2))
        q = np.column_stack([(xx + warp[0]).ravel(), (yy + warp[1]).ravel()])
        d, _ = cKDTree(seeds).query(q, k=2, workers=-1)
        border = (d[:, 1] - d[:, 0]).reshape(shape).astype(np.float32)
        patches = _noise(rng, shape, 1.5 * cell)
        patches = ndtr((patches - patches.mean()) / (patches.std() + 1e-9))       # uniform 0..1
        opened = np.clip((share - patches) / 0.1 + 0.5, 0, 1)                     # about `share` of the area
        crack = np.maximum(crack, strength * opened * np.clip(1.25 - border / width, 0, 1))
        if strength == 1.0:
            cup = opened * np.clip(1 - border / (0.5 * cell), 0, 1) ** 2
    return crack, cup


def _noise(rng, shape, sigma):
    z = gaussian_filter(rng.standard_normal(shape).astype(np.float32), sigma)
    return z / (z.std() + 1e-9)
