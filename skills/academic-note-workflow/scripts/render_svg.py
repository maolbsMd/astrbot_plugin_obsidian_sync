#!/usr/bin/env python3
import sys
import subprocess

def render(svg_path, png_path, dpi=300):
    # 方案1: 极速超轻量 rsvg-convert (几兆体积，毫秒渲染)
    if subprocess.call(["which", "rsvg-convert"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        cmd = ["rsvg-convert", "-d", str(dpi), "-p", str(dpi), svg_path, "-o", png_path]
        ret = subprocess.call(cmd)
        if ret == 0:
            return True

    # 方案2: 无头 Chromium 兜底方案
    if subprocess.call(["which", "chromium"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        cmd = ["chromium", "--headless", "--disable-gpu", "--no-sandbox", f"--screenshot={png_path}", svg_path]
        ret = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ret == 0:
            return True

    return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: render_svg.py <input.svg> <output.png>")
        sys.exit(1)
    success = render(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)
