"""Diagnose what the FLIR C5 actually exposes over its USB-C connection.

Before we can write our own radiometric-video recorder (instead of paying for
FLIR Tools+/Thermal Studio to do it), we have to know *what the camera puts on
the USB bus* and *in what pixel format* - because we can only record what is
actually being transmitted:

  - UVC (USB Video Class) camera exposing a 16-bit / Y16 / gray16 stream
        -> the raw radiometric counts are on the wire. We can grab frames with
           OpenCV/ffmpeg and apply the same Planck-law conversion flirpy uses
           in extract_seq.py. This is the good case.
  - UVC camera offering only 8-bit formats (YUY2 / MJPEG / RGB24 / NV12)
        -> the live stream is the *colorized* image only. We can record it, but
           per-pixel temperature is NOT recoverable from it.
  - USB Mass Storage / Disk device
        -> file-transfer mode; no live stream. Either switch the camera's USB
           mode (if it has a PC/stream setting) or fall back to copying files.
  - Vendor-specific device bound to a FLIR driver
        -> proprietary protocol; needs the FLIR SDK or reverse engineering, not
           a plain UVC grab.

This script is READ-ONLY: it enumerates devices and lists stream formats. It
does not open or record any stream unless you explicitly pass --probe-capture.

Run it with the C5 connected and switched into its USB / PC-connection mode
(check the camera's Settings -> USB mode; some FLIR cameras default to
mass-storage and have to be told to stream):

    .\\.venv\\Scripts\\python.exe inspect_usb_stream.py
    .\\.venv\\Scripts\\python.exe inspect_usb_stream.py --device-name "FLIR"
    .\\.venv\\Scripts\\python.exe inspect_usb_stream.py --probe-capture
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from typing import Optional

# Pixel-format / codec tokens that indicate a genuine 16-bit (radiometric) feed.
# NOTE: we deliberately do NOT match a bare "16", because the C5 sensor is
# 160x120 - the resolution string itself contains "16" and would false-positive.
_RADIOMETRIC_TOKENS = ("y16", "gray16", "gray16le", "p16", "r16", "yuv420p16", "16-bit")

_NAME_HINTS = ("flir", "thermal", "c5", "teledyne")

_VIDEO_DEVICE_RE = re.compile(r'"([^"]+)"\s*\(video\)', re.IGNORECASE)


def run(cmd: list[str], timeout: int = 30) -> tuple[str, str, Optional[int]]:
    """Run a command, returning (stdout, stderr, returncode). returncode is None
    if the executable was missing or the call timed out - callers treat that as
    'tool unavailable' rather than crashing the whole diagnostic."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            errors="replace",
        )
        return proc.stdout or "", proc.stderr or "", proc.returncode
    except FileNotFoundError:
        return "", f"(executable not found: {cmd[0]})", None
    except subprocess.TimeoutExpired:
        return "", f"(timed out after {timeout}s: {' '.join(cmd)})", None


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# --------------------------------------------------------------------------- #
# 1. How does Windows enumerate the device?  (UVC camera vs disk vs vendor)    #
# --------------------------------------------------------------------------- #

_PNP_PS = r"""
$ErrorActionPreference = 'SilentlyContinue'

Write-Output '--- Devices whose name/ID mentions FLIR / thermal / C5 ---'
Get-CimInstance Win32_PnPEntity |
  Where-Object { $_.Name -match 'FLIR|thermal|C5|Teledyne' -or $_.PNPDeviceID -match 'FLIR' } |
  Select-Object Name, Status, PNPClass, Service, PNPDeviceID | Format-List

Write-Output '--- Camera-class devices (UVC shows up here) ---'
Get-PnpDevice -Class Camera -PresentOnly |
  Select-Object FriendlyName, Status, InstanceId | Format-List

Write-Output '--- Image-class devices (WIA / still-image cameras) ---'
Get-PnpDevice -Class Image -PresentOnly |
  Select-Object FriendlyName, Status, InstanceId | Format-List

Write-Output '--- USB mass-storage / disk drives ---'
Get-CimInstance Win32_DiskDrive |
  Where-Object { $_.InterfaceType -eq 'USB' } |
  Select-Object Model, InterfaceType, MediaType, Size | Format-List
"""


def enumerate_devices() -> None:
    section("1. Windows device enumeration")
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        print("powershell not found on PATH - open Device Manager by hand and")
        print("look for the FLIR under Cameras, Imaging devices, or Disk drives.")
        return
    out, err, code = run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _PNP_PS],
        timeout=45,
    )
    text = (out + ("\n" + err if err.strip() else "")).strip()
    print(text if text else "(no output)")
    print(
        "\nRead the CLASS above:\n"
        "  * PNPClass/Class = Camera  -> UVC device; check its stream formats in section 2.\n"
        "  * Class = Image            -> still-image (WIA) device; likely no live video.\n"
        "  * a USB Disk drive appears -> it is (also) in mass-storage/file mode.\n"
        "  * Service is a FLIR driver -> possibly a proprietary (non-UVC) protocol."
    )


# --------------------------------------------------------------------------- #
# 2. If it is a UVC camera, what stream formats does it offer?  (Y16 = win)    #
# --------------------------------------------------------------------------- #

def list_video_devices(ffmpeg: str) -> list[str]:
    # -list_devices prints the device table to stderr and exits non-zero.
    _, err, _ = run([ffmpeg, "-hide_banner", "-f", "dshow", "-list_devices", "true",
                     "-i", "dummy"], timeout=30)
    print(err.strip() or "(ffmpeg produced no device list)")
    return _VIDEO_DEVICE_RE.findall(err)


def list_device_formats(ffmpeg: str, name: str) -> None:
    print(f"\n--- stream formats for video device: {name!r} ---")
    _, err, _ = run([ffmpeg, "-hide_banner", "-f", "dshow", "-list_options", "true",
                     "-i", f"video={name}"], timeout=30)
    lines = [ln for ln in err.splitlines() if "pixel_format" in ln or "vcodec" in ln]
    print("\n".join(lines) if lines else err.strip() or "(no format lines)")

    blob = err.lower()
    hits = [tok for tok in _RADIOMETRIC_TOKENS if tok in blob]
    if hits:
        print(f"\n  >>> 16-bit / radiometric format tokens present: {', '.join(hits)}")
        print("  >>> This is the GOOD case - raw counts appear to be on the wire.")
    else:
        print("\n  >>> No 16-bit/Y16 token found - this stream looks 8-bit (colorized) only.")
        print("  >>> Recording it would NOT preserve per-pixel temperature.")


def inspect_uvc_formats(device_filter: Optional[str]) -> None:
    section("2. UVC stream formats (needs ffmpeg)")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not found on PATH. It is the single most useful tool here.")
        print("Install it, then re-run:")
        print("    winget install --id=Gyan.FFmpeg -e")
        print("(or download from https://www.gyan.dev/ffmpeg/builds/ and add bin\\ to PATH)")
        return

    names = list_video_devices(ffmpeg)
    if not names:
        print("\nNo DirectShow *video* devices found. If the C5 is plugged in, it is")
        print("probably NOT presenting as a UVC camera (see section 1 for what it is).")
        return

    if device_filter:
        targets = [n for n in names if device_filter.lower() in n.lower()]
    else:
        targets = [n for n in names if any(h in n.lower() for h in _NAME_HINTS)]

    if not targets:
        print(f"\nNone of the video devices matched a FLIR-ish name. All devices: {names}")
        print("Re-run with --device-name \"<part of the name above>\" to inspect one.")
        targets = names  # inspect them all so we do not stall the investigation

    for name in targets:
        list_device_formats(ffmpeg, name)


# --------------------------------------------------------------------------- #
# 3. Optional: actually open a capture and report the frame's dtype/shape.     #
# --------------------------------------------------------------------------- #

def probe_capture(max_index: int = 5) -> None:
    section("3. OpenCV capture probe (--probe-capture)")
    try:
        import cv2  # type: ignore
        import numpy as np  # noqa: F401
    except ImportError:
        print("OpenCV not installed in this venv. To enable this probe:")
        print("    .\\.venv\\Scripts\\pip install opencv-python")
        return

    # CAP_DSHOW is the right backend on Windows; also try CAP_MSMF as a fallback.
    for backend_name, backend in (("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF)):
        for index in range(max_index):
            cap = cv2.VideoCapture(index, backend)
            if not cap.isOpened():
                cap.release()
                continue
            # Ask for a 16-bit path explicitly; the camera may ignore it.
            cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
            ok, frame = cap.read()
            if ok and frame is not None:
                print(f"[{backend_name} index {index}] frame shape={frame.shape} "
                      f"dtype={frame.dtype}")
                if frame.dtype != "uint8":
                    print("   >>> non-8-bit frame -> likely raw radiometric data!")
                elif frame.ndim == 2:
                    print("   >>> single-channel 8-bit (could be raw or grayscale).")
                else:
                    print("   >>> 3-channel 8-bit -> colorized image, not radiometric.")
            else:
                print(f"[{backend_name} index {index}] opened but no frame read.")
            cap.release()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--device-name", default=None,
                        help="Substring of the video device name to inspect (from section 1/2).")
    parser.add_argument("--probe-capture", action="store_true",
                        help="Also open capture devices and report frame dtype/shape (may blink the camera).")
    args = parser.parse_args()

    print("FLIR C5 USB stream diagnostic (read-only)")
    print("Make sure the C5 is connected and in its USB / PC-connection mode.")

    enumerate_devices()
    inspect_uvc_formats(args.device_name)
    if args.probe_capture:
        probe_capture()

    section("What to do with this")
    print(
        "Paste this whole output back and we'll classify the camera into one of the\n"
        "four cases in the module docstring, then design the recorder for that case:\n"
        "  - 16-bit UVC stream  -> OpenCV/ffmpeg grab + flirpy Planck conversion.\n"
        "  - 8-bit UVC only      -> colorized recording only (no temperatures).\n"
        "  - mass storage        -> file-based workflow (extract_seq.py / extract_metadata.py).\n"
        "  - vendor-specific     -> FLIR SDK or protocol reverse-engineering."
    )


if __name__ == "__main__":
    main()
