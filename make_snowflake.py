"""Generate a laser-cut snowflake ornament as SVG files (units: mm).

The ornament is 5 layers, built symmetrically about the centre piece, so it looks
the same from both sides. Only 3 distinct pieces are generated; cut layers 2 and 3 twice:
  layer3_front.svg   ~54 mm, delicate star with open center       (x2)
  layer2_middle.svg  ~76 mm, rotated 30 deg so its arms sit between the centre arms  (x2)
  layer1_back.svg    ~100 mm tall, bold arms + hanging loop; the centre piece  (x1)
Stack order: 3, 2, 1, 2, 3. exploded_view.svg/.png shows it. Every piece is
mirror-symmetric, so the flipped copies are identical.

Run with:  python make_snowflake.py      (needs: pip install shapely)

Holding tabs (optional):
  python make_snowflake.py --tabs                 # 0.5 mm tabs
  python make_snowflake.py --tabs --tab-width 0.8
Each piece gets 2 tabs on its outer outline, between two arms and opposite each
other. Tabbed files are written alongside the plain ones as *_tabs.svg.
"""
import argparse
import math
import re
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union

OUT = Path(__file__).parent
MIN_WEB = 2.0  # mm; thinnest material bridge the design aims for (3 mm ply / acrylic)


def line(p, q, w):
    return LineString([p, q]).buffer(w / 2, cap_style="round", join_style="round")


def branch(x, length, angle_deg, w):
    """Pair of mirrored branches leaving the spine (along +x) at x."""
    a = math.radians(angle_deg)
    tip = (x + length * math.cos(a), length * math.sin(a))
    return unary_union([line((x, 0), tip, w), line((x, 0), (tip[0], -tip[1]), w)])


def hexagon(r, rot=0):
    return Polygon(
        [(r * math.cos(math.radians(60 * i + rot)), r * math.sin(math.radians(60 * i + rot))) for i in range(6)]
    )


def six_fold(arm):
    return unary_union([affinity.rotate(arm, 60 * i, origin=(0, 0)) for i in range(6)])


def point_up(g, extra=0):
    # arms are built along +x; SVG y grows downward, so -90 deg puts an arm at 12 o'clock
    return affinity.rotate(g, -90 + extra, origin=(0, 0))


# Alignment hole, cut in the FINAL (already rotated) frame so it is identical on every
# layer. Lining the holes up then reproduces the stacked preview exactly (a hexagon
# fixes rotation to within 60 deg, which the 6-fold layers can't tell apart).
CENTER_HOLE = hexagon(4.5, 0)


# ---------------------------------------------------------------- layer 1 (back)
def layer1():
    w = 4.2
    arm = unary_union([
        line((0, 0), (40, 0), w),
        branch(13, 13, 50, w),
        branch(25, 10, 50, w),
        branch(34, 6, 50, w * 0.9),
        Polygon([(38, 0), (42, 3.6), (46, 0), (42, -3.6)]),  # diamond tip
    ])
    g = unary_union([six_fold(arm), hexagon(12, 30)])
    g = point_up(g).difference(CENTER_HOLE)  # center window shows through layer 3's open middle
    # hanging loop on the top arm
    loop = Point(0, -50).buffer(5.5).difference(Point(0, -50).buffer(2.5))
    neck = line((0, -44), (0, -46), 4.2)
    return unary_union([g, loop, neck]).difference(Point(0, -50).buffer(2.5))


# ---------------------------------------------------------------- layer 2 (middle)
def layer2():
    w = 3.2
    kite = Polygon([(5, 0), (17, 6.5), (31, 0), (17, -6.5)])
    kite_hole = Polygon([(9.5, 0), (17, 3.6), (25.5, 0), (17, -3.6)])
    arm = unary_union([
        kite,
        line((0, 0), (36, 0), w),
        branch(29, 6.5, 55, w),
        Point(37, 0).buffer(2.4),
    ])
    g = unary_union([six_fold(arm), Point(0, 0).buffer(10.5)])
    g = g.difference(six_fold(kite_hole))
    return point_up(g, extra=30).difference(CENTER_HOLE)


# ---------------------------------------------------------------- layer 3 (front)
def layer3():
    w = 2.8
    arm = unary_union([
        line((0, 0), (22, 0), w),
        branch(9, 7.5, 60, w),
        branch(15.5, 5, 60, w),
        Point(24, 0).buffer(3.0),
    ])
    g = unary_union([six_fold(arm), Point(0, 0).buffer(7.5)])
    # small dots punched in the arm tips
    g = g.difference(six_fold(Point(24, 0).buffer(1.0)))
    return point_up(g).difference(CENTER_HOLE)  # open center, lines up with layers 1+2


# ---------------------------------------------------------------- SVG output
def ring_d(coords):
    pts = list(coords)
    return "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in pts[:-1]) + " Z"


def open_d(line):
    pts = list(line.coords)
    return "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in pts)


def rings(g):
    polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
    for p in polys:
        yield p.exterior.coords
        yield from (i.coords for i in p.interiors)


# ---------------------------------------------------------------- holding tabs
# Arm rotation of each layer relative to "one arm straight up" (layer 2 is turned 30 deg).
LAYER_ROT = {"layer1_back": 0, "layer2_middle": 30, "layer3_front": 0}


def tab_points(g, rot, centre):
    """Two points on the outer outline: between arms, opposite each other."""
    cx, cy = centre
    pts = []
    for base in (30, 210):  # bisector between two arms, and its opposite
        a = math.radians(-90 + rot + base)
        ray = LineString([(cx, cy), (cx + 500 * math.cos(a), cy + 500 * math.sin(a))])
        hit = ray.intersection(g.exterior)
        cands = [hit] if hit.geom_type == "Point" else [p for p in getattr(hit, "geoms", []) if p.geom_type == "Point"]
        pts.append(max(cands, key=lambda p: p.distance(Point(cx, cy))))  # outermost crossing
    return pts


def tabbed_outline(g, rot, centre, width):
    """Outer outline split into open paths, leaving `width`-mm gaps as holding tabs."""
    ring = LineString(g.exterior.coords)
    L = ring.length

    def flat(c, span):  # outline is ~straight over `span` mm centred on c
        a = ring.interpolate((c - span / 2) % L)
        b = ring.interpolate((c + span / 2) % L)
        return a.distance(b) >= 0.99 * span

    raw = [ring.project(p) for p in tab_points(g, rot, centre)]
    # The bisector often lands in a V-notch; slide along the outline to the nearest
    # straight stretch. The design has 180-deg symmetry, so the same shift keeps the
    # second tab exactly opposite the first.
    shift = next(s for k in range(0, 400) for s in (k * 0.05, -k * 0.05)
                 if all(flat(c + s, width + 1.5) for c in raw))
    centres = sorted((c + shift) % L for c in raw)
    gaps = [((c - width / 2) % L, (c + width / 2) % L) for c in centres]
    parts = []
    for i, (_, gap_end) in enumerate(gaps):
        nxt_start = gaps[(i + 1) % len(gaps)][0]
        if nxt_start > gap_end:
            parts.append(open_d(substring(ring, gap_end, nxt_start)))
        else:  # runs past the ring's start point
            a, b = substring(ring, gap_end, L), substring(ring, 0, nxt_start)
            parts.append(open_d(LineString(list(a.coords) + list(b.coords)[1:])))
    return parts


def svg(items, w, h, preview=False, tabs=None):
    # each layer is one <g id=name>: in cut files the outline and every hole are separate
    # paths inside it; the preview keeps one compound path so even-odd fill shows the holes.
    # With `tabs` (mm), the outline is broken into open paths around the holding tabs.
    body = []
    for name, g, dx, dy, fill in items:
        g = affinity.translate(g, dx, dy)
        if preview:
            d = " ".join(ring_d(r) for r in rings(g))
            paths = f'<path d="{d}" fill="{fill}" fill-rule="evenodd" stroke="#555" stroke-width="0.2"/>'
        elif tabs:
            # every layer is built around (0, 0), so its centre is now at (dx, dy)
            outline = tabbed_outline(g, LAYER_ROT[name], (dx, dy), tabs)
            paths = "".join(f'<path d="{d}"/>' for d in outline)
            paths += "".join(f'<path d="{ring_d(i.coords)}"/>' for i in g.interiors)
        else:
            paths = "".join(f'<path d="{ring_d(r)}"/>' for r in rings(g))
        style = "" if preview else ' fill="none" stroke="#ff0000" stroke-width="0.1"'
        body.append(f'<g id="{name}"{style}>{paths}</g>')
    bg = '<rect width="100%" height="100%" fill="#1d2b3a"/>' if preview else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">'
        f"{bg}{''.join(body)}</svg>\n"
    )


LAYER_FILL = {"layer1_back": "#e8eef5", "layer2_middle": "#8fb8de", "layer3_front": "#ffffff"}
LAYER_EDGE = {"layer1_back": "#9aa9b9", "layer2_middle": "#4f7ea8", "layer3_front": "#b4c0cc"}


def exploded_svg(layers, spacing=13, squash=0.3, turn=-18, thickness=3.0):
    """Oblique exploded view of the symmetric 5-layer stack (not for cutting)."""
    stack = [  # top of the picture = the side facing the viewer
        ("layer3_front", "Layer 3 — layer3_front.svg"),
        ("layer2_middle", "Layer 2 — layer2_middle.svg"),
        ("layer1_back", "Centre — layer1_back.svg"),
        ("layer2_middle", "Layer 2 (2nd copy, flipped)"),
        ("layer3_front", "Layer 3 (2nd copy, flipped)"),
    ]
    cx, y0 = 62, 24
    W, H = 205, y0 + spacing * (len(stack) - 1) + 34
    centres = [y0 + i * spacing for i in range(len(stack))]
    edge_px = thickness * math.sqrt(1 - squash ** 2)  # visible side of a tilted sheet
    out = [f'<rect width="100%" height="100%" fill="#1d2b3a"/>',
           f'<line x1="{cx}" y1="{centres[0] - 20}" x2="{cx}" y2="{centres[-1] + 20}" '
           f'stroke="#c9d6e3" stroke-width="0.35" stroke-dasharray="2 1.5"/>']
    # draw from the bottom of the stack up so nearer layers cover farther ones
    for (name, label), cy in reversed(list(zip(stack, centres))):
        g = layers[name]
        d = " ".join(ring_d(r) for r in rings(g))
        tf = f"translate({cx} {cy}) scale(1 {squash}) rotate({turn})"
        side = "".join(
            f'<path transform="translate(0 {t:.2f}) {tf}" d="{d}" fill="{LAYER_EDGE[name]}" fill-rule="evenodd"/>'
            for t in [edge_px * k / 6 for k in range(6, 0, -1)])
        top = (f'<path transform="{tf}" d="{d}" fill="{LAYER_FILL[name]}" fill-rule="evenodd" '
               f'stroke="{LAYER_EDGE[name]}" stroke-width="0.25" vector-effect="non-scaling-stroke"/>')
        tx = cx + 64
        lead = (f'<line x1="{cx + 56}" y1="{cy}" x2="{tx - 2}" y2="{cy}" stroke="#7d93a8" stroke-width="0.25"/>'
                f'<text x="{tx}" y="{cy + 1.4}" font-family="Helvetica, Arial, sans-serif" font-size="4.2" '
                f'fill="#e8eef5">{label}</text>')
        out.append(f'<g id="exploded_{len(out)}">{side}{top}{lead}</g>')
    out.append(f'<text x="{W / 2}" y="{H - 7}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" '
               f'font-size="3.6" fill="#9fb3c6">Glue in this order, lining up the centre hex holes. '
               f'Cut layers 2 and 3 twice.</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">'
            f"{''.join(out)}</svg>\n")


def write_png(svg_text, path, px_width):
    """Render an SVG string to PNG with resvg-py if it is installed (optional)."""
    try:
        import resvg_py  # optional: pip install resvg-py
    except ImportError:
        print(f"resvg-py not installed; skipped {path.name}")
        return
    w, h = (float(v) for v in re.search(r'width="([\d.]+)mm" height="([\d.]+)mm"', svg_text).groups())
    px = re.sub(r'width="[\d.]+mm" height="[\d.]+mm"',
                f'width="{px_width}" height="{round(px_width * h / w)}"', svg_text, count=1)  # resvg-py rejects mm
    path.write_bytes(bytes(resvg_py.svg_to_bytes(svg_string=px)))


def check(name, g):
    # rough min-feature check: eroding by MIN_WEB/2 shouldn't split the part into pieces
    eroded = g.buffer(-MIN_WEB / 2 + 0.05)
    pieces = 1 if eroded.geom_type == "Polygon" else len(eroded.geoms)
    assert g.geom_type == "Polygon", f"{name} is not one connected piece"
    minx, miny, maxx, maxy = g.bounds
    print(f"{name}: {maxx - minx:.1f} x {maxy - miny:.1f} mm, holes={len(g.interiors)}, "
          f"web check {'OK' if pieces == 1 else f'WARN ({pieces} pieces after erosion)'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tabs", action="store_true", help="also write *_tabs.svg files with holding tabs")
    ap.add_argument("--tab-width", type=float, default=0.5, metavar="MM", help="tab width in mm (default 0.5)")
    args = ap.parse_args()

    layers = {"layer1_back": layer1(), "layer2_middle": layer2(), "layer3_front": layer3()}
    variants = [("", None)] + ([("_tabs", args.tab_width)] if args.tabs else [])
    for name, g in layers.items():
        check(name, g)
        minx, miny, maxx, maxy = g.bounds
        m = 3
        W, H = maxx - minx + 2 * m, maxy - miny + 2 * m
        for suffix, tabs in variants:
            (OUT / f"{name}{suffix}.svg").write_text(
                svg([(name, g, -minx + m, -miny + m, None)], round(W, 2), round(H, 2), tabs=tabs))

    # all three nested on one sheet
    sheet = []
    x = 5
    for name, g in layers.items():
        minx, miny, maxx, maxy = g.bounds
        sheet.append((name, g, x - minx, 5 - miny, None))
        x += maxx - minx + 5
    for suffix, tabs in variants:
        (OUT / f"all_layers_sheet{suffix}.svg").write_text(svg(sheet, round(x, 1), 115, tabs=tabs))
    l1, l2, l3 = layers.values()

    # stacked colour preview (not for cutting)
    c = (60, 62)
    preview = svg([("layer1_back", l1, *c, "#e8eef5"), ("layer2_middle", l2, *c, "#8fb8de"),
                   ("layer3_front", l3, *c, "#ffffff")], 120, 120, preview=True)
    (OUT / "preview_stacked.svg").write_text(preview)
    write_png(preview, OUT / "preview_stacked.png", 900)

    # exploded view of the symmetric 5-layer assembly (not for cutting)
    exploded = exploded_svg(layers)
    (OUT / "exploded_view.svg").write_text(exploded)
    write_png(exploded, OUT / "exploded_view.png", 1400)
