# Snowflake ornament

A 3-layer snowflake ornament for laser cutting.

![Stacked preview](preview_stacked.png)

| File | Size | Layer |
|---|---|---|
| `layer1_back.svg` | 80 × 102 mm | Back: thick branching arms, diamond tips, hanging loop (5 mm hole) |
| `layer2_middle.svg` | 79 × 69 mm | Middle: arms with diamond cutouts, rotated 30° to sit between the back arms |
| `layer3_front.svg` | 48 × 54 mm | Front: thinner star with ringed tips |
| `all_layers_sheet.svg` | | All three layers on one sheet |

Cut lines are red, 0.1 mm wide, in millimetres. Import at 1:1.

## Cutting and assembly

- Designed for 3 mm plywood or acrylic (1.5–2 mm also works). No part is narrower than about 2 mm.
- The files don't allow for kerf.
- All three layers have the same hexagonal hole in the centre. Line those up (a pencil or dowel through the hole helps) and glue back to front.

## Changing the design

Edit `make_snowflake.py` and run it to regenerate the SVGs and preview:

```bash
pip install shapely
python make_snowflake.py
```
