"""Automated headless browser capture for Product Hunt gallery slides."""

import re
import subprocess
from pathlib import Path

GALLERY_HTML = Path(__file__).parent / "gallery.html"
OUT_DIR = Path(__file__).parent

SLIDES = [
    ("slide-1", "slide_1_hero_cover.png"),
    ("slide-2", "slide_2_architecture_comparison.png"),
    ("slide-3", "slide_3_empirical_benchmarks.png"),
    ("slide-4", "slide_4_enterprise_production.png"),
    ("slide-5", "slide_5_fullstack_polyglot.png"),
    ("slide-6", "slide_6_zero_json_cli.png"),
]

def main():
    content = GALLERY_HTML.read_text(encoding="utf-8")
    
    # Extract head content (fonts, css)
    head_match = re.search(r"<head>(.*?)</head>", content, re.DOTALL)
    head_inner = head_match.group(1) if head_match else ""

    # Override body & slide style for exact 1280x720 capture without margins or borders
    capture_style = """
    <style>
      body {
        margin: 0 !important;
        padding: 0 !important;
        width: 1280px !important;
        height: 720px !important;
        overflow: hidden !important;
        background: #0f172a !important;
      }
      .ph-slide {
        width: 1280px !important;
        height: 720px !important;
        border-radius: 0 !important;
        border: none !important;
        box-shadow: none !important;
        margin: 0 !important;
      }
      .slide-label {
        display: none !important;
      }
    </style>
    """

    for slide_id, filename in SLIDES:
        pattern = rf'(<div class="ph-slide" id="{slide_id}">[\s\S]*?</div>\s*</div>)'
        m = re.search(pattern, content)
        if not m:
            # Fallback pattern matching just the slide div
            pattern2 = rf'(<div class="ph-slide" id="{slide_id}">[\s\S]*?)(?=<div class="ph-slide"|</body>)'
            m = re.search(pattern2, content)
        
        slide_html = m.group(1) if m else ""
        
        tmp_file = OUT_DIR / f"tmp_{slide_id}.html"
        full_page = f"""<!DOCTYPE html>
<html>
<head>
{head_inner}
{capture_style}
</head>
<body>
{slide_html}
</body>
</html>
"""
        tmp_file.write_text(full_page, encoding="utf-8")
        out_png = OUT_DIR / filename

        print(f"Rendering {slide_id} -> {filename}...")
        cmd = [
            "brave-browser",
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--window-size=1280,720",
            f"--screenshot={out_png.resolve()}",
            f"file://{tmp_file.resolve()}",
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        tmp_file.unlink(missing_ok=True)
        print(f"✔ Created: {out_png.name} ({out_png.stat().st_size // 1024} KB)")

    # Also capture live dashboard
    live_out = OUT_DIR / "live_dashboard_showcase.png"
    print("Rendering live dashboard -> live_dashboard_showcase.png...")
    cmd_live = [
        "brave-browser",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--window-size=1440,900",
        f"--screenshot={live_out.resolve()}",
        "https://chetan0246.github.io/triad-swarm/",
    ]
    subprocess.run(cmd_live, check=True, capture_output=True)
    print(f"✔ Created: {live_out.name} ({live_out.stat().st_size // 1024} KB)")

if __name__ == "__main__":
    main()
