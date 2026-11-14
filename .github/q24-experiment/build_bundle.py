# ruff: noqa
# Temporary: the experiment of open question Q-24. Removed again once it has run on macOS 15.
"""Q-24 throwaway experiment: build an unsigned app bundle around a Python script.

Run with the Python that has pywebview and pyobjc installed.

Modes:
  symlink  Contents/MacOS/<name> is a symlink to the Python program, started by a
           small shell script (the bundle's executable). The process then lives
           inside the bundle.
  outside  The shell script starts the Python program at its own place, outside
           the bundle. For comparison only.
"""

import argparse
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ICON_SIZES = [16, 32, 128, 256, 512]


def render_png(svg_file: Path, size: int, out: Path) -> None:
    """Render an SVG file to a square PNG with AppKit only."""
    import AppKit
    import Foundation

    image = AppKit.NSImage.alloc().initWithContentsOfFile_(str(svg_file))
    if image is None:
        raise SystemExit(f"AppKit could not read {svg_file}")
    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, AppKit.NSDeviceRGBColorSpace, 0, 0
    )
    context = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(context)
    image.drawInRect_fromRect_operation_fraction_(
        Foundation.NSMakeRect(0, 0, size, size),
        Foundation.NSZeroRect,
        AppKit.NSCompositingOperationSourceOver,
        1.0,
    )
    AppKit.NSGraphicsContext.restoreGraphicsState()
    data = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {})
    data.writeToFile_atomically_(str(out), True)


def build_icns(svg_source: Path, colours: dict[str, str], out: Path, work: Path) -> None:
    """Replace the token colours in the SVG, render every size, and pack an .icns."""
    text = svg_source.read_text()
    for token, value in colours.items():
        text = text.replace(f"var({token})", value)
    if re.search(r"var\(", text):
        raise SystemExit("the SVG still contains a CSS variable")
    plain = work / "icon-plain.svg"
    plain.write_text(text)
    iconset = work / "icon.iconset"
    iconset.mkdir()
    for size in ICON_SIZES:
        render_png(plain, size, iconset / f"icon_{size}x{size}.png")
        render_png(plain, size * 2, iconset / f"icon_{size}x{size}@2x.png")
    shutil.copy(iconset / "icon_512x512.png", work / "preview-512.png")
    subprocess.run(["/usr/bin/iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="the .app folder to create")
    parser.add_argument("--name", required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--python", required=True, help="the Python program to run")
    parser.add_argument("--site", required=True, help="the site-packages folder to add")
    parser.add_argument("--script", required=True, help="the Python script the app runs")
    parser.add_argument("--data", required=True, help="the data folder of this app")
    parser.add_argument("--icon-svg", required=True)
    parser.add_argument("--mode", choices=["symlink", "outside"], default="symlink")
    args = parser.parse_args()

    app = Path(args.out)
    if app.exists():
        shutil.rmtree(app)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as work:
        build_icns(
            Path(args.icon_svg),
            {"--ytm-color-accent": "#1F5FD1", "--ytm-color-on-accent": "#FFFFFF"},
            resources / "app.icns",
            Path(work),
        )
        shutil.copy(Path(work) / "preview-512.png", app.parent / f"{app.stem}-icon-512.png")

    info = {
        "CFBundleName": args.name,
        "CFBundleDisplayName": args.name,
        "CFBundleIdentifier": args.bundle_id,
        "CFBundleExecutable": "launch",
        "CFBundleIconFile": "app",
        "CFBundlePackageType": "APPL",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSMinimumSystemVersion": "15.0",
        "NSHighResolutionCapable": True,
    }
    with (app / "Contents" / "Info.plist").open("wb") as handle:
        plistlib.dump(info, handle)

    if args.mode == "symlink":
        program = macos / args.name
        program.symlink_to(args.python)
    else:
        program = Path(args.python)

    launcher = macos / "launch"
    launcher.write_text(
        "#!/bin/sh\n"
        f"export Q24_DATA={sh_quote(args.data)}\n"
        f"export Q24_BUNDLE={sh_quote(str(app))}\n"
        f"export Q24_SITE={sh_quote(args.site)}\n"
        f"export Q24_NAME={sh_quote(args.name)}\n"
        f'exec {sh_quote(str(program))} {sh_quote(args.script)} "$@"\n'
    )
    launcher.chmod(0o755)
    sys.stdout.write(f"built {app} ({args.mode})\n")


if __name__ == "__main__":
    main()
