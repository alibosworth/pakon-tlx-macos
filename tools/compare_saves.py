#!/usr/bin/env python3
"""Compare two saves of the same frame from separate scans.

Written for the x87sidecar check (docs/notes-slow-colour-saves.md): the same
strip is scanned under stock Wine and under the patched Wine, so the frames
differ by a small shift as well as by whatever the colour maths does. This
lines the pair up first (FFT phase correlation, whole pixels), crops to the
overlap, and then reports:

  - the shift found,
  - per-channel mean difference (a colour cast shows up here),
  - per-pixel absolute difference, at full resolution and after averaging
    8x8 blocks (the blocked figure ignores sub-pixel misregistration and
    grain, so it isolates tone and colour changes).

Needs numpy and Pillow.  Usage:

    compare_saves.py reference.tif candidate.tif [more pairs...]
    compare_saves.py --dirs stock/ sidecar/       # pairs files by name
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

BLOCK_SIZE = 8


def load_rgb(path):
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float64)


def find_shift(reference_rgb, candidate_rgb):
    """Whole-pixel (row, column) shift that best lines candidate up with reference."""
    reference_grey = reference_rgb.mean(axis=2)
    candidate_grey = candidate_rgb.mean(axis=2)
    reference_grey -= reference_grey.mean()
    candidate_grey -= candidate_grey.mean()
    # A window keeps the frame edges from dominating the correlation.
    window = np.outer(np.hanning(reference_grey.shape[0]), np.hanning(reference_grey.shape[1]))
    cross_power = np.fft.fft2(reference_grey * window) * np.conj(np.fft.fft2(candidate_grey * window))
    cross_power /= np.abs(cross_power) + 1e-12
    correlation = np.abs(np.fft.ifft2(cross_power))
    peak_row, peak_column = np.unravel_index(np.argmax(correlation), correlation.shape)
    height, width = correlation.shape
    if peak_row > height // 2:
        peak_row -= height
    if peak_column > width // 2:
        peak_column -= width
    return int(peak_row), int(peak_column)


def overlap(reference_rgb, candidate_rgb, row_shift, column_shift):
    """Crop both images to the region they share once candidate is shifted."""
    height, width = reference_rgb.shape[:2]
    reference_rows = slice(max(0, row_shift), height + min(0, row_shift))
    reference_columns = slice(max(0, column_shift), width + min(0, column_shift))
    candidate_rows = slice(max(0, -row_shift), height + min(0, -row_shift))
    candidate_columns = slice(max(0, -column_shift), width + min(0, -column_shift))
    return (reference_rgb[reference_rows, reference_columns],
            candidate_rgb[candidate_rows, candidate_columns])


def block_average(rgb, block_size):
    height = rgb.shape[0] // block_size * block_size
    width = rgb.shape[1] // block_size * block_size
    trimmed = rgb[:height, :width]
    return trimmed.reshape(height // block_size, block_size, width // block_size, block_size, 3).mean(axis=(1, 3))


def describe(absolute_difference):
    per_pixel = absolute_difference.max(axis=2)
    return (f"mean {absolute_difference.mean():5.2f}  "
            f"p99 {np.percentile(per_pixel, 99):5.1f}  "
            f"max {per_pixel.max():5.0f}  "
            f">2: {100 * (per_pixel > 2).mean():5.1f}%  "
            f">8: {100 * (per_pixel > 8).mean():5.1f}%")


def compare(reference_path, candidate_path):
    reference_rgb = load_rgb(reference_path)
    candidate_rgb = load_rgb(candidate_path)
    if reference_rgb.shape != candidate_rgb.shape:
        print(f"{reference_path.name}: size differs {reference_rgb.shape} vs {candidate_rgb.shape}, skipped")
        return
    row_shift, column_shift = find_shift(reference_rgb, candidate_rgb)
    reference_crop, candidate_crop = overlap(reference_rgb, candidate_rgb, row_shift, column_shift)
    # Drop a margin: film edges and rebate move with the framing.
    margin = 40
    reference_crop = reference_crop[margin:-margin, margin:-margin]
    candidate_crop = candidate_crop[margin:-margin, margin:-margin]

    channel_means_reference = reference_crop.mean(axis=(0, 1))
    channel_means_candidate = candidate_crop.mean(axis=(0, 1))
    full_difference = np.abs(candidate_crop - reference_crop)
    blocked_difference = np.abs(block_average(candidate_crop, BLOCK_SIZE) - block_average(reference_crop, BLOCK_SIZE))

    print(f"{reference_path.name}  vs  {candidate_path}")
    print(f"  shift (rows, cols): ({row_shift}, {column_shift})   overlap {reference_crop.shape[1]}x{reference_crop.shape[0]}")
    print("  channel means R/G/B  reference " + " ".join(f"{value:6.2f}" for value in channel_means_reference)
          + "   candidate " + " ".join(f"{value:6.2f}" for value in channel_means_candidate)
          + "   delta " + " ".join(f"{value:+5.2f}" for value in channel_means_candidate - channel_means_reference))
    print(f"  full-res |diff|   {describe(full_difference)}")
    print(f"  {BLOCK_SIZE}x{BLOCK_SIZE} blocks      {describe(blocked_difference)}")


def main(arguments):
    if len(arguments) == 3 and arguments[0] == "--dirs":
        reference_dir, candidate_dir = Path(arguments[1]), Path(arguments[2])
        pairs = [(path, candidate_dir / path.name) for path in sorted(reference_dir.glob("*.tif"))
                 if (candidate_dir / path.name).exists()]
    elif arguments and len(arguments) % 2 == 0:
        pairs = [(Path(arguments[index]), Path(arguments[index + 1])) for index in range(0, len(arguments), 2)]
    else:
        print(__doc__)
        return 2
    if not pairs:
        print("no matching pairs")
        return 1
    for reference_path, candidate_path in pairs:
        compare(reference_path, candidate_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
