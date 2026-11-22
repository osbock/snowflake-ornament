"""Generate a 3-layer laser-cut snowflake ornament as SVG files (units: mm).

Layers (glue back -> front, centers aligned):
  layer1_back.svg    ~100 mm tall, bold arms + hanging loop
  layer2_middle.svg  ~76 mm, rotated 30 deg so its arms sit between the back arms
  layer3_front.svg   ~54 mm, delicate star with open center

Run with:  python make_snowflake.py      (needs: pip install shapely)
"""
import math
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

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
    g = g.difference(hexagon(4.5, 0))  # small center window shows through layer 3's open middle
    g = point_up(g)
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
    holes = unary_union([six_fold(kite_hole), hexagon(4.5, 0)])
    g = g.difference(holes)
    return point_up(g, extra=30)


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
    g = g.difference(hexagon(4.5, 0))  # open center, lines up with layers 1+2
    # small dots punched in the arm tips
    g = g.difference(six_fold(Point(24, 0).buffer(1.0)))
    return point_up(g)


# ---------------------------------------------------------------- SVG output
def ring_d(coords):
    pts = list(coords)
    return "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in pts[:-1]) + " Z"


def geom_d(g):
    polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
    parts = []
    for p in polys:
        parts.append(ring_d(p.exterior.coords))
        parts.extend(ring_d(i.coords) for i in p.interiors)
    return " ".join(parts)


def svg(items, w, h, preview=False):
    body = []
    for g, dx, dy, fill in items:
        g = affinity.translate(g, dx, dy)
        if preview:
            body.append(f'<path d="{geom_d(g)}" fill="{fill}" fill-rule="evenodd" stroke="#555" stroke-width="0.2"/>')
        else:
            body.append(f'<path d="{geom_d(g)}" fill="none" stroke="#ff0000" stroke-width="0.1"/>')
    bg = '<rect width="100%" height="100%" fill="#1d2b3a"/>' if preview else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">'
        f"{bg}{''.join(body)}</svg>\n"
    )


def check(name, g):
    # rough min-feature check: eroding by MIN_WEB/2 shouldn't split the part into pieces
    eroded = g.buffer(-MIN_WEB / 2 + 0.05)
    pieces = 1 if eroded.geom_type == "Polygon" else len(eroded.geoms)
    assert g.geom_type == "Polygon", f"{name} is not one connected piece"
    minx, miny, maxx, maxy = g.bounds
    print(f"{name}: {maxx - minx:.1f} x {maxy - miny:.1f} mm, holes={len(g.interiors)}, "
          f"web check {'OK' if pieces == 1 else f'WARN ({pieces} pieces after erosion)'}")


if __name__ == "__main__":
    layers = {"layer1_back": layer1(), "layer2_middle": layer2(), "layer3_front": layer3()}
    for name, g in layers.items():
        check(name, g)
        minx, miny, maxx, maxy = g.bounds
        m = 3
        W, H = maxx - minx + 2 * m, maxy - miny + 2 * m
        (OUT / f"{name}.svg").write_text(svg([(g, -minx + m, -miny + m, None)], round(W, 2), round(H, 2)))

    # all three nested on one sheet
    l1, l2, l3 = layers.values()
    sheet = []
    x = 5
    for g in (l1, l2, l3):
        minx, miny, maxx, maxy = g.bounds
        sheet.append((g, x - minx, 5 - miny, None))
        x += maxx - minx + 5
    (OUT / "all_layers_sheet.svg").write_text(svg(sheet, round(x, 1), 115))

    # stacked colour preview (not for cutting)
    c = (60, 62)
    (OUT / "preview_stacked.svg").write_text(svg(
        [(l1, *c, "#e8eef5"), (l2, *c, "#8fb8de"), (l3, *c, "#ffffff")], 120, 120, preview=True))
