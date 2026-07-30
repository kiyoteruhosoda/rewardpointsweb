"""アプリアイコン（favicon / PWA / iOS）を `frontend/public/` へ書き出す。

図柄は「親子（大人 2 人と子ども 2 人）と、貯まったごほうびの星」。SVG も PNG も
このスクリプトが同じ座標から作るので、両者の形は必ず一致する。

    uv run python scripts/generate_app_icons.py

図形の位置は「アイコンの一辺を 1 とした比率」で持つ（`UNIT` 系の定数）。大きさを
変えても比率は変わらないため、192 / 512 / 180 のどれでも同じ絵になる。

色や配置を変えたいときはここの定数を直して実行し、書き出した 5 ファイルをコミット
する（`favicon.svg` を手で編集しても PNG は追随しない）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public"

BLUE = "#1c80fa"  # 背景。index.html の theme-color / manifest の theme_color と揃える
WHITE = "#ffffff"
STAR = "#fecf42"

CORNER = 0.20  # 角丸の半径（一辺に対する比率）
GAP = 0.013  # 重なった人物を切り分ける背景色の隙間
BELOW = 1.08  # 体は下端より先まで描いて角丸で切る（足元を作らない）

SUPERSAMPLE = 4  # 大きく描いてから縮める（PIL の polygon はアンチエイリアスしない）
ARC_STEPS = 64  # 円弧を何本の線分で近似するか（SVG は円弧コマンドを使うので PNG 用）
VIEW_BOX = 512  # SVG の座標系（比率にこの値を掛けて書き出す）


@dataclass(frozen=True)
class Person:
    """頭（円）と体（上が半円の柱）でできた人。数値はすべて一辺に対する比率。"""

    head_x: float
    head_y: float
    head_r: float
    body_x: float
    body_hw: float  # 体の半分の幅（＝肩の円弧の半径）
    body_arc_y: float  # 肩の円弧の中心。頂点はここから body_hw だけ上


# 奥から手前の順。手前の人ほど後に描き、背景色の隙間で切り分ける。
FAMILY = (
    Person(0.645, 0.470, 0.107, 0.645, 0.192, 0.747),  # 大人（右・奥）
    Person(0.340, 0.429, 0.115, 0.340, 0.207, 0.733),  # 大人（左）
    Person(0.590, 0.748, 0.063, 0.605, 0.078, 0.892),  # 子ども（右）
    Person(0.396, 0.679, 0.078, 0.395, 0.123, 0.879),  # 子ども（左・手前）
)

STAR_X, STAR_Y, STAR_R = 0.781, 0.207, 0.130
STAR_INNER = 0.50  # 内側の半径の比。小さくすると鋭く、大きくすると太る
# きらめき。星の右上に 2 本、丸い端の線で入れる。
SPARKS = (((0.886, 0.050), (0.856, 0.100)), ((0.947, 0.100), (0.887, 0.137)))
SPARK_WIDTH = 0.017


def star_points(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * STAR_INNER
        angle = -math.pi / 2 + i * math.pi / 5
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def dome_points(x: float, half_width: float, arc_y: float, bottom: float) -> list[tuple[float, float]]:
    """体の輪郭（上半分が半円、下は下端の先まで伸びる柱）。"""
    points = [(x - half_width, bottom)]
    for i in range(ARC_STEPS + 1):
        angle = math.pi + math.pi * i / ARC_STEPS
        points.append((x + half_width * math.cos(angle), arc_y + half_width * math.sin(angle)))
    points.append((x + half_width, bottom))
    return points


class Canvas:
    """比率（0〜1）で受け取り、実寸の PNG へ描く。"""

    def __init__(self, size: int, scale: float) -> None:
        self._px = size * SUPERSAMPLE
        self._scale = scale
        self._image = Image.new("RGBA", (self._px, self._px), (0, 0, 0, 0))
        self._draw = ImageDraw.Draw(self._image)
        # 縮小しても体が下端に届くよう、縮小の分だけ長く伸ばす（足元を作らない）
        self.bottom = 0.5 + (BELOW - 0.5) / scale

    def _at(self, x: float, y: float) -> tuple[float, float]:
        """図柄全体を中心から ``scale`` 倍に縮める（maskable の安全域に収めるため）。"""
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

    def circle(self, cx: float, cy: float, r: float, color: str) -> None:
        x, y = self._at(cx, cy)
        size = r * self._scale * self._px
        self._draw.ellipse((x - size, y - size, x + size, y + size), fill=color)

    def polygon(self, points: list[tuple[float, float]], color: str) -> None:
        self._draw.polygon([self._at(x, y) for x, y in points], fill=color)

    def stroke(self, start: tuple[float, float], end: tuple[float, float], width: float) -> None:
        px_width = width * self._scale * self._px
        self._draw.line((self._at(*start), self._at(*end)), fill=STAR, width=round(px_width))
        for point in (start, end):  # 丸い端
            self.circle(point[0], point[1], width / 2, STAR)

    def finish(self, size: int, corner: float) -> Image.Image:
        """角丸の外へはみ出した体を切り落としてから縮小する。"""
        if corner > 0:
            mask = Image.new("L", (self._px, self._px), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, self._px - 1, self._px - 1), radius=corner * self._px, fill=255
            )
            self._image.putalpha(mask)
        return self._image.resize((size, size), Image.Resampling.LANCZOS)


def paint(canvas: Canvas, corner: float) -> None:
    """背景 → 家族（奥から手前）→ 星、の順で 1 枚ぶん描く。"""
    canvas.background(corner)
    for index, person in enumerate(FAMILY):
        if index > 0:  # 奥の人と重なるところに背景色の隙間を作る
            canvas.circle(person.head_x, person.head_y, person.head_r + GAP, BLUE)
            gap_body = dome_points(person.body_x, person.body_hw + GAP, person.body_arc_y, canvas.bottom)
            canvas.polygon(gap_body, BLUE)
        canvas.polygon(dome_points(person.body_x, person.body_hw, person.body_arc_y, canvas.bottom), WHITE)
        canvas.circle(person.head_x, person.head_y, person.head_r + GAP, BLUE)
        canvas.circle(person.head_x, person.head_y, person.head_r, WHITE)

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
    if not first:  # 奥の人と重なるところに背景色の隙間を作る
        lines.append(f'{head} r="{person.head_r + gap:.1f}" fill="{BLUE}"/>')
        lines.append(f'<path d="{_svg_dome(person, gap)}" fill="{BLUE}"/>')
    lines.append(f'<path d="{_svg_dome(person, 0.0)}" fill="{WHITE}"/>')
    lines.append(f'{head} r="{person.head_r + gap:.1f}" fill="{BLUE}"/>')
    lines.append(f'{head} r="{person.head_r:.1f}" fill="{WHITE}"/>')
    return lines


def svg() -> str:
    """PNG と同じ図形の SVG（favicon 用。タブでは拡大縮小されるためベクターで持つ）。"""
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
    # 通常のアイコン。ランチャーはこれをそのまま出すので角を丸めておく。
    render(192, corner=CORNER).save(OUT / "pwa-192x192.png")
    render(512, corner=CORNER).save(OUT / "pwa-512x512.png")
    # maskable。ランチャーが好きな形に切り抜くので端まで塗り、頭と星がセーフゾーン
    # （内側 80%）に収まるよう図柄を縮める。体は今までどおり下端まで伸ばす。
    render(512, corner=0.0, scale=0.85).save(OUT / "pwa-maskable-512x512.png")
    # iOS は自前で角を丸め、透過を黒く塗る。角丸なし・透過なしで渡す。
    render(180, corner=0.0, scale=0.94).save(OUT / "apple-touch-icon.png")
    (OUT / "favicon.svg").write_text(svg())
    print(f"wrote icons into {OUT}")


if __name__ == "__main__":
    main()
