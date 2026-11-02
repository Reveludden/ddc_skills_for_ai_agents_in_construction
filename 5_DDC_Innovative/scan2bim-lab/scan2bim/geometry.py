"""Grundgeometri: nedsampling, normaler, sammanhängande komponenter.

Egen implementation (numpy/scipy). Inga delar kopierade från andra program.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


def voxel_downsample(points: np.ndarray, voxel: float) -> np.ndarray:
    """Behåll medelpunkten per voxel (kub med sidan `voxel` meter)."""
    if voxel <= 0 or len(points) == 0:
        return points
    keys = np.floor(points / voxel).astype(np.int64)
    _, inverse, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.ravel()
    sums = np.zeros((len(counts), 3))
    np.add.at(sums, inverse, points)
    return sums / counts[:, None]


def estimate_normals(points: np.ndarray, k: int = 16, tree: cKDTree | None = None):
    """Normal och krökning per punkt via PCA på de k närmaste grannarna.

    Returnerar (normals, curvature). Normalernas tecken är obestämt.
    Krökning = minsta egenvärdet / summan av egenvärdena (0 = plant).
    """
    tree = tree or cKDTree(points)
    k = min(k, len(points))
    _, idx = tree.query(points, k=k)
    nbrs = points[idx]                                  # (N, k, 3)
    centered = nbrs - nbrs.mean(axis=1, keepdims=True)
    cov = np.einsum("nki,nkj->nij", centered, centered) / k
    evals, evecs = np.linalg.eigh(cov)                  # stigande ordning
    normals = evecs[:, :, 0]
    curvature = evals[:, 0] / np.maximum(evals.sum(axis=1), 1e-12)
    return normals, curvature


def components(points: np.ndarray, radius: float) -> np.ndarray:
    """Etikett per punkt: punkter närmare än `radius` hör till samma komponent."""
    if len(points) == 0:
        return np.zeros(0, dtype=int)
    pairs = cKDTree(points).query_pairs(radius, output_type="ndarray")
    n = len(points)
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    _, labels = connected_components(graph, directed=False)
    return labels


def orthonormal_basis(axis: np.ndarray):
    """Två enhetsvektorer vinkelräta mot `axis` och mot varandra."""
    axis = axis / np.linalg.norm(axis)
    helper = np.array([1.0, 0, 0]) if abs(axis[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(axis, helper)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    return u, v
