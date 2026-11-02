"""Hela kedjan: punkter -> normaler -> plan -> rör -> kopplingskandidater."""
from __future__ import annotations

import time

import numpy as np
from scipy.spatial import cKDTree

from .geometry import estimate_normals, voxel_downsample
from .pipes import connection_candidates, detect_pipes
from .planes import detect_planes


def run(points, *, voxel=0.008, k_normals=16, noise=0.002, seed=0, density_ratio=0.3,
        plane_kwargs=None, pipe_kwargs=None):
    t0 = time.time()
    pts = voxel_downsample(points, voxel)
    normals, _ = estimate_normals(pts, k=k_normals, tree=cKDTree(pts))
    t1 = time.time()
    planes, on_plane = detect_planes(pts, normals, seed=seed, **(plane_kwargs or {}))
    t2 = time.time()
    rest = ~on_plane
    # Täthetskrav: andel av den täthet en voxel-glesad yta har (1/voxel^2).
    pk = {"min_density": density_ratio / voxel ** 2 if voxel > 0 else 0.0,
          **(pipe_kwargs or {})}
    pipes, _ = detect_pipes(pts[rest], normals[rest], noise=noise, seed=seed, **pk)
    t3 = time.time()
    conns = connection_candidates(pipes)
    return {
        "planes": planes, "pipes": pipes, "connections": conns,
        "stats": {"punkter_in": int(len(points)), "punkter_efter_voxel": int(len(pts)),
                  "punkter_pa_plan": int(on_plane.sum()),
                  "punkter_kvar_for_ror": int(rest.sum()),
                  "tid_normaler_s": round(t1 - t0, 2), "tid_plan_s": round(t2 - t1, 2),
                  "tid_ror_s": round(t3 - t2, 2), "voxel_m": voxel},
    }


def to_json(result):
    return {
        "plan": [p.to_dict() for p in result["planes"]],
        "ror": [p.to_dict() for p in result["pipes"]],
        "kopplingskandidater": result["connections"],
        "statistik": result["stats"],
    }
