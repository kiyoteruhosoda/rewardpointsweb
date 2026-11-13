"""Write the app icons (favicon / PWA / iOS) to `frontend/public/`.

The motif is "a family (2 adults and 2 children) and the reward star they have earned". This
script builds both the SVG and the PNGs from the same coordinates, so their shapes always match.

    uv run python scripts/generate_app_icons.py

Shape positions are kept as "ratios of the icon's side length, taken as 1" (the `UNIT` constants).
The ratios do not change with size, so 192 / 512 / 180 all produce the same picture.

To change colours or layout, edit the constants here, run it, and commit the 5 files it writes
(editing `favicon.svg` by hand does not carry over to the PNGs).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public"

BLUE = "#1c80fa"  # Background. Keep in sync with theme-color in index.html / theme_color in the manifest
WHITE = "#ffffff"
STAR = "#fecf42"

CORNER = 0.20  # Corner radius (ratio of the side length)
GAP = 0.013  # Background-coloured gap separating overlapping figures
BELOW = 1.08  # Bodies extend past the bottom edge and are clipped by the rounded corners (no feet)

SUPERSAMPLE = 4  # Draw large, then downscale (PIL's polygon does not anti-alias)
ARC_STEPS = 64  # Number of segments approximating an arc (PNG only; the SVG uses arc commands)
VIEW_BOX = 512  # SVG coordinate system (ratios are multiplied by this when written)


@dataclass(frozen=True)
class Person:
    """A person made of a head (circle) and body (pillar with a semicircular top). All values are ratios of the side."""

    head_x: float
    head_y: float
    head_r: float
    body_x: float
    body_hw: float  # Half the body width (= radius of the shoulder arc)
    body_arc_y: float  # Centre of the shoulder arc. The top is body_hw above this


# Ordered back to front. People in front are drawn later and separated by a background-coloured gap.
FAMILY = (
    Person(0.645, 0.470, 0.107, 0.645, 0.192, 0.747),  # Adult (right, back)
    Person(0.340, 0.429, 0.115, 0.340, 0.207, 0.733),  # Adult (left)
    Person(0.590, 0.748, 0.063, 0.605, 0.078, 0.892),  # Child (right)
    Person(0.396, 0.679, 0.078, 0.395, 0.123, 0.879),  # Child (left, front)
)

STAR_X, STAR_Y, STAR_R = 0.781, 0.207, 0.130
STAR_INNER = 0.50  # Inner radius ratio. Smaller is sharper, larger is fatter
# Sparkle. Two round-capped lines at the upper right of the star.
SPARKS = (((0.886, 0.050), (0.856, 0.100)), ((0.947, 0.100), (0.887, 0.137)))
SPARK_WIDTH = 0.017


def star_points(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * STAR_INNER
        angle = -math.pi / 2 + i * math.pi / 5
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def dome_points(x: float, half_width: float, arc_y: float, *, bottom: float) -> list[tuple[float, float]]:
    """Body outline (semicircular top half; below, a pillar extending past the bottom edge)."""
    points = [(x - half_width, bottom)]
    for i in range(ARC_STEPS + 1):
        angle = math.pi + math.pi * i / ARC_STEPS
        points.append((x + half_width * math.cos(angle), arc_y + half_width * math.sin(angle)))
    points.append((x + half_width, bottom))
    return points


class Canvas:
    """Takes ratios (0-1) and draws onto a full-size PNG."""

    def __init__(self, size: int, scale: float) -> None:
        self._px = size * SUPERSAMPLE
        self._scale = scale
        self._image = Image.new("RGBA", (self._px, self._px), (0, 0, 0, 0))
        self._draw = ImageDraw.Draw(self._image)
        # Extend by the shrink amount so bodies still reach the bottom edge when shrunk (no feet)
        self.bottom = 0.5 + (BELOW - 0.5) / scale

    def _at(self, x: float, y: float) -> tuple[float, float]:
        """Shrink the whole motif by ``scale`` around the centre (to fit the maskable safe zone)."""
        return (
            (0.5 + (x - 0.5) * self._scale) * self._px,
            (0.5 + (y - 0.5) * self._scale) * self._px,
        )

    def background(self, corner: float) -> None:
        box = (0.0, 0.0, float(self._px - 1), float(self._px - 1))
        if corner > 0:
            self._draw.rounded_rectangle(box, radius=corner * self._px, fill=BLUE)
        else:
            self._draw.rectangle(box, fill=BLUE)

    def circle(self, cx: float, cy: float, r: float, *, color: str) -> None:
        x, y = self._at(cx, cy)
        size = r * self._scale * self._px
        self._draw.ellipse((x - size, y - size, x + size, y + size), fill=color)

    def polygon(self, points: list[tuple[float, float]], color: str) -> None:
        self._draw.polygon([self._at(x, y) for x, y in points], fill=color)

    def stroke(self, start: tuple[float, float], end: tuple[float, float], width: float) -> None:
        px_width = width * self._scale * self._px
        self._draw.line((self._at(*start), self._at(*end)), fill=STAR, width=round(px_width))
        for point in (start, end):  # Round caps
            self.circle(point[0], point[1], width / 2, color=STAR)

    def finish(self, size: int, corner: float) -> Image.Image:
        """Clip bodies sticking out past the rounded corners, then downscale."""
        if corner > 0:
            mask = Image.new("L", (self._px, self._px), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, self._px - 1, self._px - 1), radius=corner * self._px, fill=255
            )
            self._image.putalpha(mask)
        return self._image.resize((size, size), Image.Resampling.LANCZOS)


def paint(canvas: Canvas, corner: float) -> None:
    """Draw one image: background -> family (back to front) -> star."""
    canvas.background(corner)
    for index, person in enumerate(FAMILY):
        if index > 0:  # Cut a background-coloured gap where this overlaps the person behind
            canvas.circle(person.head_x, person.head_y, person.head_r + GAP, color=BLUE)
            gap_body = dome_points(person.body_x, person.body_hw + GAP, person.body_arc_y, bottom=canvas.bottom)
            canvas.polygon(gap_body, BLUE)
        canvas.polygon(dome_points(person.body_x, person.body_hw, person.body_arc_y, bottom=canvas.bottom), WHITE)
        canvas.circle(person.head_x, person.head_y, person.head_r + GAP, color=BLUE)
        canvas.circle(person.head_x, person.head_y, person.head_r, color=WHITE)

    canvas.polygon(star_points(STAR_X, STAR_Y, STAR_R), STAR)
    for start, end in SPARKS:
        canvas.stroke(start, end, SPARK_WIDTH)


def render(size: int, *, corner: float, scale: float = 1.0) -> Image.Image:
    canvas = Canvas(size, scale)
    paint(canvas, corner)
    return canvas.finish(size, corner)


def _svg_dome(person: Person, grow: float) -> str:
    left, right = person.body_x - person.body_hw - grow, person.body_x + person.body_hw + grow
    radius = person.body_hw + grow
    return (
        f"M{left:.1f} {BELOW * VIEW_BOX:.0f} L{left:.1f} {person.body_arc_y:.1f}"
        f" A{radius:.1f} {radius:.1f} 0 0 1 {right:.1f} {person.body_arc_y:.1f}"
        f" L{right:.1f} {BELOW * VIEW_BOX:.0f} Z"
    )


def _svg_person(person: Person, gap: float, *, first: bool) -> list[str]:
    head = f'<circle cx="{person.head_x:.1f}" cy="{person.head_y:.1f}"'
    lines: list[str] = []
    if not first:  # Cut a background-coloured gap where this overlaps the person behind
        lines.append(f'{head} r="{person.head_r + gap:.1f}" fill="{BLUE}"/>')
        lines.append(f'<path d="{_svg_dome(person, gap)}" fill="{BLUE}"/>')
    lines.append(f'<path d="{_svg_dome(person, 0.0)}" fill="{WHITE}"/>')
    lines.append(f'{head} r="{person.head_r + gap:.1f}" fill="{BLUE}"/>')
    lines.append(f'{head} r="{person.head_r:.1f}" fill="{WHITE}"/>')
    return lines


def svg() -> str:
    """An SVG of the same shapes as the PNGs (for the favicon; kept as vector since tabs scale it)."""
    view = float(VIEW_BOX)
    scaled = [
        Person(
            p.head_x * view,
            p.head_y * view,
            p.head_r * view,
            p.body_x * view,
            p.body_hw * view,
            p.body_arc_y * view,
        )
        for p in FAMILY
    ]
    body_lines: list[str] = []
    for index, person in enumerate(scaled):
        body_lines += ["  " + line for line in _svg_person(person, GAP * view, first=index == 0)]

    star = " ".join(f"{x * view:.1f},{y * view:.1f}" for x, y in star_points(STAR_X, STAR_Y, STAR_R))
    sparks = "\n".join(
        f'  <line x1="{a[0] * view:.1f}" y1="{a[1] * view:.1f}" x2="{b[0] * view:.1f}" y2="{b[1] * view:.1f}"'
        f' stroke="{STAR}" stroke-width="{SPARK_WIDTH * view:.1f}" stroke-linecap="round"/>'
        for a, b in SPARKS
    )
    people = "\n".join(body_lines)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW_BOX} {VIEW_BOX}">\n'
        "  <defs>\n"
        f'    <clipPath id="frame"><rect width="{VIEW_BOX}" height="{VIEW_BOX}" rx="{CORNER * view:.0f}"/></clipPath>\n'
        "  </defs>\n"
        '  <g clip-path="url(#frame)">\n'
        f'  <rect width="{VIEW_BOX}" height="{VIEW_BOX}" fill="{BLUE}"/>\n'
        f"{people}\n"
        f'  <polygon points="{star}" fill="{STAR}"/>\n'
        f"{sparks}\n"
        "  </g>\n"
        "</svg>\n"
    )


def main() -> None:
    # Regular icons. Launchers show them as is, so round the corners.
    render(192, corner=CORNER).save(OUT / "pwa-192x192.png")
    render(512, corner=CORNER).save(OUT / "pwa-512x512.png")
    # maskable. Launchers crop it to any shape, so fill to the edges and shrink the motif so the
    # heads and star fit the safe zone (inner 80%). Bodies still extend to the bottom edge.
    render(512, corner=0.0, scale=0.85).save(OUT / "pwa-maskable-512x512.png")
    # iOS rounds the corners itself and paints transparency black. Hand it no rounding, no alpha.
    render(180, corner=0.0, scale=0.94).save(OUT / "apple-touch-icon.png")
    (OUT / "favicon.svg").write_text(svg())
    print(f"wrote icons into {OUT}")


if __name__ == "__main__":
    main()
