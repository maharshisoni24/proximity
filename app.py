import heapq, io, os
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, UploadFile
from scipy.spatial import cKDTree
app = FastAPI()
df = pd.read_csv(os.getenv("LOCATIONS_CSV", "locations.csv"))
df.columns = df.columns.str.strip()
ids = df["ID"].to_numpy(dtype=np.int64)
pts = df[["Latitude", "Longitude"]].to_numpy(dtype=float)
cats = df["Category"].astype(str).str.strip().str.lower().to_numpy()
N = len(ids)
tree = cKDTree(pts)
order = np.argsort(ids)
sorted_ids = ids[order]

def build_csr(raw: bytes):
    try:
        e = pd.read_csv(io.BytesIO(raw), sep=r"\s+", header=None, usecols=[0, 1], dtype=np.int64)
    except Exception:
        e = pd.DataFrame(columns=[0, 1], dtype=np.int64)
    a, b = e[0].to_numpy(), e[1].to_numpy()
    def to_idx(v):
        pos = np.searchsorted(sorted_ids, v).clip(max=N - 1)
        return order[pos], sorted_ids[pos] == v
    ia, va = to_idx(a); ib, vb = to_idx(b)
    keep = va & vb & (ia != ib)
    ia, ib = ia[keep], ib[keep]
    w = np.hypot(*(pts[ia] - pts[ib]).T)
    src = np.concatenate([ia, ib]); dst = np.concatenate([ib, ia]); ww = np.concatenate([w, w])
    o = np.argsort(src, kind="stable")
    src, dst, ww = src[o], dst[o], ww[o]
    indptr = np.searchsorted(src, np.arange(N + 1))
    return indptr, dst, ww

def dijkstra(indptr, dst, ww, virt_dst, virt_ww, mask, k=10):
    # Node index N is the virtual query-point source.
    # virt_dst/virt_ww are its edges to real graph nodes.
    heap = [(w, int(v)) for v, w in zip(virt_dst, virt_ww)]
    heapq.heapify(heap)
    dist = {}; found = []
    while heap and len(found) < k:
        d, u = heapq.heappop(heap)
        if u in dist: continue
        dist[u] = d
        if mask[u]: found.append(u)
        s, t = indptr[u], indptr[u + 1]
        for v, w in zip(dst[s:t].tolist(), ww[s:t].tolist()):
            if v not in dist: heapq.heappush(heap, (d + w, v))
    return found

@app.post("/search/")
async def search(
    lat:  float      = Form(...),
    long: float      = Form(...),
    cat:  str        = Form(...),
    rad:  float      = Form(...),
    link: UploadFile = File(...),
):
    q = np.array([lat, long]); cat = cat.strip().lower()

    # Radius filter: candidates must be within rad (Euclidean) AND match category.
    mask = np.zeros(N, dtype=bool)
    cand = np.array(tree.query_ball_point(q, rad), dtype=np.int64)
    if cand.size:
        mask[cand[cats[cand] == cat]] = True

    indptr, dst, ww = build_csr(await link.read())

    # Virtual source: find up to 50 nearest nodes, keep those with ≥1 edge,
    # and connect each with an edge weighted by true Euclidean distance to q.
    # This ensures path costs include the first-hop query→node distance.
    near_dists, near_idxs = tree.query(q, k=min(50, N))
    near_dists  = np.atleast_1d(near_dists)
    near_idxs   = np.atleast_1d(near_idxs)
    connected   = np.array([i for i in near_idxs if indptr[i + 1] > indptr[i]], dtype=np.int64)
    if connected.size == 0:
        connected = near_idxs[:1]   # fallback: at least try the nearest node
    virt_dst = connected
    virt_ww  = np.hypot(*(pts[connected] - q).T)

    found = dijkstra(indptr, dst, ww, virt_dst, virt_ww, mask)
    return {"ids": [int(ids[i]) for i in found]}
