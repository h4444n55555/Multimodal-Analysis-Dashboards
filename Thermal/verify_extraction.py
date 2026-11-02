"""Independent sanity checks for the extracted radiometric temperature data.

Doesn't require any extra software (ExifTool install needs admin rights this
environment can't grant). Instead checks internal consistency of the data
flyr already extracted, and prints the value at any in-camera measurement
markers so you can compare them against FLIR's own software/camera display
for a ground-truth check.

Also saves a plot (heatmap + value distribution) as visual proof the data is
real continuous per-pixel measurements, not a flat/broken array.

Run with:
    .\\.venv\\Scripts\\python.exe verify_extraction.py --image images/FLIR0180.jpg
"""

from __future__ import annotations

import argparse
from pathlib import Path

import flyr
import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", type=Path, default=Path("images/FLIR0180.jpg"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    args = parser.parse_args()

    t = flyr.unpack(str(args.image))
    celsius = t.celsius
    kelvin = t.kelvin
    stem = args.image.stem

    print(f"=== Verifying {args.image.name} ===")

    ok = bool(np.allclose(kelvin - 273.15, celsius))
    print(f"[check 1] kelvin - 273.15 == celsius everywhere: {ok}")
    print("          (internal round-trip; a mismatch would mean the unit conversion itself is broken)")

    cam_min, cam_max = t.embedded_range("celsius")
    print(f"[check 2] camera's own auto-scale range: {cam_min:.2f} to {cam_max:.2f} C")
    print(f"          our computed array min/max:    {celsius.min():.2f} to {celsius.max():.2f} C")
    print("          (the camera computes its range in-camera from the same calibration constants;")
    print("           close agreement means the Planck conversion is using them correctly)")

    if t.measurements:
        print("[check 3] in-camera measurement markers (compare against FLIR Tools/camera display):")
        for m in t.measurements:
            if m.tool.name == "SPOT" and len(m.params) == 2:
                x, y = m.params
                print(f"          SPOT '{m.label}' at pixel ({x},{y}) = {celsius[y, x]:.2f} C")
            else:
                print(f"          {m.tool.name} '{m.label}' at params {m.params} (not a single-point readout)")
    else:
        print("[check 3] no in-camera measurement markers embedded in this image")

    fig, (ax_map, ax_hist) = plt.subplots(1, 2, figsize=(11, 4.5))
    # interpolation="nearest" so this is a strict 1 array-cell = 1 solid color
    # block rendering, with no blending between neighboring pixels - proof
    # that what's shown is exactly the per-pixel array, not a smoothed guess.
    im = ax_map.imshow(celsius, cmap="inferno", interpolation="nearest")
    fig.colorbar(im, ax=ax_map, label="Temperature (C)")
    ax_map.set_title(f"{args.image.name} - per-pixel temperature")
    ax_map.axis("off")

    ax_hist.hist(celsius.ravel(), bins=60, color="firebrick")
    ax_hist.set_title("Distribution of per-pixel values")
    ax_hist.set_xlabel("Temperature (C)")
    ax_hist.set_ylabel("Pixel count")
    ax_hist.axvline(celsius.mean(), color="black", linestyle="--", linewidth=1, label=f"mean {celsius.mean():.1f} C")
    ax_hist.legend()

    fig.tight_layout()
    out_path = args.output / f"{stem}_verification.png"
    fig.savefig(out_path, dpi=150)
    print(f"\nSaved proof plot to {out_path}")


if __name__ == "__main__":
    main()
