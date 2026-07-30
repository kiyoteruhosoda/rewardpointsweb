"""アプリアイコン（favicon / PWA / iOS）を `frontend/public/` へ書き出す。

図柄は左右対称。金貨（貯まるポイント）の中で、大きなハート（親）が小さなハート（子）を
包む。SVG も PNG もこのスクリプトが同じ座標から作るので、両者の形は必ず一致する。

    uv run python scripts/generate_app_icons.py

色や大きさを変えたいときはここの定数を直し、書き出した 5 ファイルをコミットする
（`favicon.svg` を手で編集しても PNG は追随しない）。
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public"

INDIGO = (79, 70, 229, 255)  # #4f46e5（テーマ色。index.html の theme-color と揃える）
COIN = (251, 191, 36, 255)  # #fbbf24
RIM = (245, 158, 11, 255)  # #f59e0b

SUPERSAMPLE = 4  # 大きく描いてから縮める（PIL の polygon はアンチエイリアスしないため）
STEPS = 240  # ハートの輪郭を何角形で近似するか
SVG_STEP = 3  # SVG は 3 点に 1 つへ間引く（アイコンの大きさでは差が出ず、読める長さに収まる）


def heart_outline() -> list[tuple[float, float]]:
    """左右対称なハートの輪郭を単位系で作る（中心が原点、幅・高さとも 1 に収まる）。"""
    raw: list[tuple[float, float]] = []
    for i in range(STEPS):
        angle = 2 * math.pi * i / STEPS
        sin = math.sin(angle)
        x = 16 * sin * sin * sin
        # 画像の y 軸は下向きなので符号を反転する
        y = -(13 * math.cos(angle) - 5 * math.cos(2 * angle) - 2 * math.cos(3 * angle) - math.cos(4 * angle))
        raw.append((x, y))

    span = max(max(abs(x) for x, _ in raw), max(abs(y) for _, y in raw)) * 2
    mid_y = (max(y for _, y in raw) + min(y for _, y in raw)) / 2
    return [(x / span, (y - mid_y) / span) for x, y in raw]


HEART = heart_outline()


def heart_at(cx: float, cy: float, size: float, step: int = 1) -> list[tuple[float, float]]:
    return [(cx + x * size, cy + y * size) for x, y in HEART[::step]]


def render(size: int, *, corner_ratio: float, coin_ratio: float) -> Image.Image:
    """1 枚描く。``corner_ratio`` が 0 なら角丸なし（端まで塗る）。"""
    canvas = size * SUPERSAMPLE
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    corner = corner_ratio * canvas
    if corner > 0:
        draw.rounded_rectangle((0, 0, canvas - 1, canvas - 1), radius=corner, fill=INDIGO)
    else:
        draw.rectangle((0, 0, canvas - 1, canvas - 1), fill=INDIGO)

    center = canvas / 2
    coin = coin_ratio * canvas
    draw.ellipse((center - coin, center - coin, center + coin, center + coin), fill=RIM)
    face = coin * 0.88
    draw.ellipse((center - face, center - face, center + face, center + face), fill=COIN)

    parent = face * 1.34
    draw.polygon(heart_at(center, center, parent), fill=INDIGO)
    draw.polygon(heart_at(center, center + parent * 0.10, parent * 0.46), fill=COIN)

    return image.resize((size, size), Image.Resampling.LANCZOS)


def svg() -> str:
    """PNG と同じ図形の SVG（favicon 用。ブラウザのタブでは拡大縮小されるため）。"""
    center, coin = 256.0, 170.0
    face = coin * 0.88
    parent = face * 1.34
    parent_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in heart_at(center, center, parent, SVG_STEP))
    child_points = " ".join(
        f"{x:.1f},{y:.1f}" for x, y in heart_at(center, center + parent * 0.10, parent * 0.46, SVG_STEP)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n'
        '  <rect width="512" height="512" rx="113" fill="#4f46e5"/>\n'
        '  <circle cx="256" cy="256" r="170" fill="#f59e0b"/>\n'
        '  <circle cx="256" cy="256" r="150" fill="#fbbf24"/>\n'
        f'  <polygon fill="#4f46e5" points="{parent_points}"/>\n'
        f'  <polygon fill="#fbbf24" points="{child_points}"/>\n'
        "</svg>\n"
    )


def main() -> None:
    # 通常のアイコン。ランチャーはこれをそのまま出すので角を丸めておく。
    render(192, corner_ratio=0.22, coin_ratio=0.332).save(OUT / "pwa-192x192.png")
    render(512, corner_ratio=0.22, coin_ratio=0.332).save(OUT / "pwa-512x512.png")
    # maskable。ランチャーが好きな形に切り抜くので端まで塗り、図柄はセーフゾーン
    # （内側 80%）に収める。角丸のアイコンを流用すると切り抜きで縁が欠ける。
    render(512, corner_ratio=0.0, coin_ratio=0.293).save(OUT / "pwa-maskable-512x512.png")
    # iOS は自前で角を丸め、透過を黒く塗る。角丸なし・透過なしで渡す。
    render(180, corner_ratio=0.0, coin_ratio=0.332).save(OUT / "apple-touch-icon.png")
    (OUT / "favicon.svg").write_text(svg())
    print(f"wrote icons into {OUT}")


if __name__ == "__main__":
    main()
