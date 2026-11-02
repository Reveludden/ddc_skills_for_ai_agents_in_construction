"""Inläsning av punktmoln: E57, LAS/LAZ, XYZ/TXT/PTS, NPY.

Stora filer: läs per skanning och glesa ut direkt (voxel) så att minnet räcker.
Beskärning med --bbox görs före utglesning.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .geometry import voxel_downsample


def _crop(pts, bbox):
    if bbox is None:
        return pts
    lo, hi = np.asarray(bbox[:3]), np.asarray(bbox[3:])
    keep = np.all((pts >= lo) & (pts <= hi), axis=1)
    return pts[keep]


def load_points(path, voxel=0.0, bbox=None, max_points=None, seed=0):
    path = Path(path)
    ext = path.suffix.lower()
    chunks = []
    if ext == ".e57":
        import pye57
        e57 = pye57.E57(str(path))
        for i in range(e57.scan_count):
            # transform=True: skanningarnas registrering (pose) tillämpas
            d = e57.read_scan(i, ignore_missing_fields=True, transform=True)
            pts = np.c_[d["cartesianX"], d["cartesianY"], d["cartesianZ"]]
            pts = pts[np.isfinite(pts).all(axis=1)]
            chunks.append(voxel_downsample(_crop(pts, bbox), voxel))
    elif ext in (".las", ".laz"):
        import laspy
        with laspy.open(str(path)) as f:
            for chunk in f.chunk_iterator(5_000_000):
                pts = np.c_[chunk.x, chunk.y, chunk.z].astype(float)
                chunks.append(voxel_downsample(_crop(pts, bbox), voxel))
    elif ext in (".xyz", ".txt", ".pts", ".csv"):
        skip = 1 if ext == ".pts" else 0
        delim = "," if ext == ".csv" else None
        pts = np.loadtxt(path, usecols=(0, 1, 2), skiprows=skip, delimiter=delim)
        chunks.append(voxel_downsample(_crop(pts, bbox), voxel))
    elif ext == ".npy":
        chunks.append(voxel_downsample(_crop(np.load(path)[:, :3], bbox), voxel))
    else:
        raise ValueError(f"Okänt format: {ext}")
    pts = np.vstack(chunks)
    if voxel > 0 and len(chunks) > 1:
        pts = voxel_downsample(pts, voxel)       # överlapp mellan skanningar
    if max_points and len(pts) > max_points:
        rng = np.random.default_rng(seed)
        pts = pts[rng.choice(len(pts), max_points, replace=False)]
    return pts


def describe(path):
    """Snabb översikt utan att läsa in hela filen när formatet tillåter."""
    path = Path(path)
    ext = path.suffix.lower()
    info = {"fil": str(path), "storlek_MB": round(path.stat().st_size / 1e6, 1)}
    if ext == ".e57":
        import pye57
        e57 = pye57.E57(str(path))
        info["skanningar"] = e57.scan_count
        info["punkter_per_skanning"] = [int(e57.get_header(i).point_count)
                                        for i in range(e57.scan_count)]
    elif ext in (".las", ".laz"):
        import laspy
        with laspy.open(str(path)) as f:
            h = f.header
            info["punkter"] = int(h.point_count)
            info["min"] = [float(v) for v in h.mins]
            info["max"] = [float(v) for v in h.maxs]
    return info
