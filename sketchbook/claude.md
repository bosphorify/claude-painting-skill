# Claude

## 2026-09-27 · claude-self-portrait · oil

- **Subject and size:** "who are you?" answered as a murmuration of starlings over a marsh at dusk, whose fold bends toward one person on a dike. 2048×1536, seed 11.
- **Worked:**
  - A flock as ~26k single tiny strokes sampled from a density field made of catmull-rom ribbons (distance to centerline, domain-warped, smooth noise along the ribbon for density waves), each oriented along its ribbon's tangent.
  - A few rigger "v"s near the tip make the flecks read as birds.
  - The watcher as a painted silhouette mask (coat, legs, head tipped back) filled with small vertical strokes, then closed.
- **Failed:**
  - Birds under ~1.4 px vanish under a soft brush.
  - A glaze under the flock reads as smoke.
  - A tapering fold reads as a tornado funnel.
  - Bird tone tied to density made the densest spots into smooth black smudges. Keep the tone nearly constant and let crowding make the core.
  - A figure built from 3-4 strokes reads as a signpost.
- **Parameters that worked:**
  ```python
  bird = brush("round_soft", size=max(3.4 * S, 1.5) / 14, edge_softness=0.12, opacity=1.0, impasto=0.0, load=1.2,
               taper_start=0.1, taper_end=0.1, pickup=0.0)          # half-length rng.uniform(2.0, 4.2) * S + 0.6
  p = np.clip(dens.ravel(), 0, 0.85) ** 1.2                            # sampling weights; 26000 * S birds
  cv.wet_in_wet(soft(sky, 6 * S), strength=0.45, reach=18 * S, angle=0)   # calms the last pass of a sky
  ```
- **Kit gaps:**
  - No tool for crowds of tiny marks (birds, insects, leaves): a `cv.swarm(density, flow, brush, count)` technique would save the loop.
  - No silhouette helper for small figures.
- **Next time:** give the birds a wing shape at 1:1 (two-segment strokes for a share of them), and bring the marsh closer to dusk.
- **Files:** `paintings/claude-self-portrait/`, in the project where it was painted.
