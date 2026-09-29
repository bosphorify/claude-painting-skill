import numpy as np
from PIL import Image
from scipy.ndimage import label

from atelier import Canvas, brush, studio
from atelier.color import lightness, srgb_to_linear


def bump_canvas(pigment="lead_white", seed=4):
    cv = Canvas(200, 200, seed=seed)
    cv.ground(pigment, texture="panel", tone=0.6)
    yy, xx = np.mgrid[:200, :200]
    cv.height[:] = 2.0 * np.exp(-((xx - 100) ** 2 + (yy - 100) ** 2) / (2 * 10.0 ** 2))
    return cv


def value(img):
    return lightness(srgb_to_linear(np.asarray(img, float) / 255))


def test_finish_is_deterministic_and_leaves_the_canvas_alone():
    def painted():
        cv = Canvas(260, 200, seed=9)
        cv.ground("raw_umber", texture="linen", tone=0.3)
        cv.stroke(brush("flat_bristle"), [[20, 60], [240, 80]], "lead_white")
        cv.impasto([[20, 130], [240, 140]], "vermilion")
        return cv

    cv = painted()
    state = [a.copy() for a in (cv.color, cv.height, cv.wet, cv.tooth)]
    rng_state = cv.rng.bit_generator.state
    a = cv.finish(crackle=0.5)
    b = cv.finish(crackle=0.5)
    assert a.shape == (200, 260, 3) and a.dtype == np.uint8
    assert a.tobytes() == b.tobytes()
    assert painted().finish(crackle=0.5).tobytes() == a.tobytes()
    for before, after in zip(state, (cv.color, cv.height, cv.wet, cv.tooth)):
        np.testing.assert_array_equal(before, after)
    assert cv.rng.bit_generator.state == rng_state


def test_raking_light_models_the_relief_and_leaves_flat_paint_alone():
    cv = bump_canvas()
    lit = value(cv.finish(light=(-0.5, -0.6), varnish=0, weave=0))
    upper_left, lower_right = lit[88:96, 88:96].mean(), lit[104:112, 104:112].mean()
    assert upper_left > lower_right + 0.15
    flip = value(cv.finish(light=(0.5, 0.6), varnish=0, weave=0))
    assert flip[88:96, 88:96].mean() < flip[104:112, 104:112].mean() - 0.15
    flat = np.abs(lit[:30, :30] - value(cv.to_srgb_uint8())[:30, :30])
    assert flat.max() < 0.02


def test_gloss_puts_highlights_on_the_relief():
    cv = bump_canvas("ultramarine")
    base = value(cv.to_srgb_uint8())[:30, :30].mean()
    glossy = value(cv.finish(varnish=0.8, weave=0))
    assert glossy[60:140, 60:140].max() > base + 0.15


def test_weave_shows_through_thin_paint_but_not_through_thick():
    cv = Canvas(240, 120, seed=2)
    cv.ground("yellow_ochre", texture="linen", tone=0.5)
    cv.height[:, 120:] = 1.5
    plain = value(cv.finish(weave=0.0, varnish=0))
    woven = value(cv.finish(weave=0.8, varnish=0))
    thin, thick = (woven - plain)[10:110, 10:110], (woven - plain)[10:110, 130:230]
    assert thin.std() > 0.02
    assert thick.std() < 0.5 * thin.std()


def test_varnish_warms_and_crackle_draws_a_connected_network():
    cv = Canvas(400, 300, seed=6)
    cv.ground("lead_white", texture="panel", tone=0.0)
    clean = cv.finish(varnish=0, weave=0).astype(float)
    aged = cv.finish(varnish=0.8, weave=0).astype(float)
    assert (aged[..., 0] - aged[..., 2]).mean() > (clean[..., 0] - clean[..., 2]).mean() + 10
    cracked = cv.finish(varnish=0, weave=0, crackle=0.7)
    dark = value(clean) - value(cracked) > 0.1
    assert 0.01 < dark.mean() < 0.2
    labels, n = label(dark, structure=np.ones((3, 3)))
    biggest = np.bincount(labels.ravel())[1:].argmax() + 1
    xs = np.nonzero(labels == biggest)[1]
    assert np.ptp(xs) > 0.5 * cv.shape[1]
    assert cv.finish(varnish=0, weave=0, crackle=0).tobytes() == clean.astype(np.uint8).tobytes()


def test_crackle_grows_steadily_with_its_amount():
    cv = Canvas(400, 300, seed=6)
    cv.ground("lead_white", texture="panel", tone=0.0)
    clean = value(cv.finish(varnish=0, weave=0))
    dark = [(clean - value(cv.finish(varnish=0, weave=0, crackle=a))).mean() for a in (0.05, 0.1, 0.2, 0.4, 0.7, 1.0)]
    assert dark[0] > 0
    assert all(later > earlier for earlier, later in zip(dark, dark[1:])), dark
    assert dark[1] < 0.25 * dark[4], dark          # 0.1 is a hint of age, not most of 0.7


def test_scale_makes_a_study_as_embossed_as_the_final():
    def strokes(W):
        S, H = W / 2048, W * 3 // 4
        cv = Canvas(W, H, seed=4)
        cv.ground("raw_umber", texture="panel", tone=0.3)
        rng = np.random.default_rng(1)
        for _ in range(260):
            p0, a = rng.uniform((0, 0), (W, H)), rng.uniform(0, np.pi)
            d = np.array([np.cos(a), np.sin(a)]) * rng.uniform(60, 200) * S
            cv.stroke(brush("flat_bristle", size=rng.uniform(0.8, 2.0) * S, load=1.4), [p0, p0 + d / 2, p0 + d], "lead_white")
        return cv, S

    def relief(cv, size, **kw):
        """Mean lightness change from the relief, seen at `size` px wide like a viewer comparing the two."""
        seen = lambda a: np.asarray(Image.fromarray(a).resize(size, Image.LANCZOS))
        return np.abs(value(seen(cv.finish(varnish=0, weave=0, **kw))) - value(seen(cv.to_srgb_uint8()))).mean()

    study, s = strokes(512)
    final, f = strokes(1024)
    assert relief(study, (512, 384)) > 1.3 * relief(final, (512, 384))                   # relief in pixels
    assert 0.8 < relief(study, (512, 384), scale=s) / relief(final, (512, 384), scale=f) < 1.25


def test_studio_saves_a_finished_painting(tmp_path):
    cv = bump_canvas()
    img = cv.finish()
    final, review = studio.save(img, tmp_path / "final.png")
    np.testing.assert_array_equal(np.asarray(Image.open(final)), img)
    assert Image.open(review).size == (studio.SHEET_W, studio.SHEET_H)
