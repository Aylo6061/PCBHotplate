"""Heater trace generator.

The heater area is discretised into a grid of cells with pitch (width + space);
a cell centre is a point on the trace centreline.  The trace is a Hamiltonian
path over the free cells from pad A to pad B, built as follows:

1. corridor  - shortest (fewest-turn) path Q from A to B through free cells
2. dominoes  - maximum matching of the remaining free cells into 2-cell dominoes
3. splicing  - repeatedly merge components (Q, dominoes, cycles) across 2x2
               squares: two opposite edges of a square belonging to different
               components are swapped for the other two edges.  This preserves
               vertex degrees, so Q stays a path from A to B and swallows
               everything else.
"""
from __future__ import annotations

import heapq
import itertools
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .model import Design, Rect
from . import resistance as res

log = logging.getLogger("heaterapp.generator")

Cell = tuple[int, int]
Point = tuple[float, float]
DIRS: tuple[Cell, ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))
INF = float("inf")


class GenError(Exception):
    pass


# --------------------------------------------------------------------------- grid

@dataclass
class Grid:
    x0: float
    y0: float
    px: float
    py: float
    nx: int
    ny: int
    free: set[Cell]

    def center(self, c: Cell) -> Point:
        return (self.x0 + (c[0] + 0.5) * self.px, self.y0 + (c[1] + 0.5) * self.py)

    def in_bounds(self, c: Cell) -> bool:
        return 0 <= c[0] < self.nx and 0 <= c[1] < self.ny

    def is_boundary(self, c: Cell) -> bool:
        for dx, dy in DIRS:
            n = (c[0] + dx, c[1] + dy)
            if n not in self.free:
                return True
        return False

    def nearest_free(self, x: float, y: float, boundary_only: bool = False) -> Optional[Cell]:
        best, best_d = None, INF
        for c in self.free:
            if boundary_only and not self.is_boundary(c):
                continue
            cx, cy = self.center(c)
            d = (cx - x) ** 2 + (cy - y) ** 2
            if d < best_d:
                best, best_d = c, d
        return best


def build_grid(heater: Rect, keepouts: list[Rect], width: float, space: float) -> Grid:
    pitch = width + space
    nx = int(math.floor(heater.w / pitch + 1e-9))
    ny = int(math.floor(heater.h / pitch + 1e-9))
    if nx < 1 or ny < 1:
        raise GenError(f"Heater area ({heater.w:.2f} x {heater.h:.2f} mm) is smaller than one "
                       f"trace pitch ({pitch:.3f} mm)")
    px = heater.w / nx
    py = heater.h / ny
    half = width / 2 + space  # trace half-width plus required clearance
    free: set[Cell] = set()
    for iy in range(ny):
        cy = heater.y + (iy + 0.5) * py
        for ix in range(nx):
            cx = heater.x + (ix + 0.5) * px
            blocked = False
            for k in keepouts:
                if k.intersects_box(cx - half, cy - half, cx + half, cy + half):
                    blocked = True
                    break
            if not blocked:
                free.add((ix, iy))
    return Grid(heater.x, heater.y, px, py, nx, ny, free)


# ----------------------------------------------------------------------- corridor

def _pocket_step(free: set[Cell], x: Cell, exclude: set[Cell]) -> Optional[Cell]:
    """Neighbour of endpoint `x` that looks like a dead-end pocket (fewest free
    neighbours).  Cells behind an endpoint can only be covered if the path
    starts by going through them, so the corridor is forced that way."""
    cands = [(x[0] + dx, x[1] + dy) for dx, dy in DIRS]
    cands = [c for c in cands if c in free and c not in exclude]
    if len(cands) < 2:
        return None
    deg = {c: sum(1 for dx, dy in DIRS if (c[0] + dx, c[1] + dy) in free) for c in cands}
    lo = min(deg.values())
    if lo == max(deg.values()):
        return None
    return min(cands, key=lambda c: (deg[c], c))


def corridor(free: set[Cell], a: Cell, b: Cell, hug_boundary: bool = False,
             force_ends: bool = False) -> Optional[list[Cell]]:
    """Shortest path a->b through free cells, preferring fewer turns.  With
    `hug_boundary` interior cells cost extra so the path follows edges/keepouts.
    With `force_ends` the first/last step is routed through pocket cells next
    to the endpoints (see _pocket_step)."""
    if force_ends:
        u = _pocket_step(free, a, {b})
        v = _pocket_step(free, b, {a})
        if u == v:
            v = None
        if u is not None or v is not None:
            allowed = free - ({a} if u else set()) - ({b} if v else set())
            mid = corridor(allowed, u or a, v or b, hug_boundary)
            if mid is not None:
                return ([a] if u else []) + mid + ([b] if v else [])
    TURN = 1e-3
    interior_cost = 0.0
    if hug_boundary:
        interior_cost = 0.5
        boundary = {c for c in free if any((c[0] + dx, c[1] + dy) not in free for dx, dy in DIRS)}
    start = (a, -1)
    best: dict[tuple[Cell, int], float] = {start: 0.0}
    prev: dict[tuple[Cell, int], tuple[Cell, int]] = {}
    done: set[tuple[Cell, int]] = set()
    pq: list[tuple[float, Cell, int]] = [(0.0, a, -1)]
    while pq:
        d, c, dr = heapq.heappop(pq)
        state = (c, dr)
        if state in done:
            continue
        done.add(state)
        if c == b:
            path = [c]
            while state in prev:
                state = prev[state]
                path.append(state[0])
            path.reverse()
            return path
        for i, (dx, dy) in enumerate(DIRS):
            n = (c[0] + dx, c[1] + dy)
            if n not in free:
                continue
            ns = (n, i)
            if ns in done:
                continue
            nd = d + 1.0 + (0.0 if dr in (-1, i) else TURN)
            if interior_cost and n not in boundary:
                nd += interior_cost
            if nd < best.get(ns, INF):
                best[ns] = nd
                prev[ns] = state
                heapq.heappush(pq, (nd, n, i))
    return None


def _component(free: set[Cell], start: Cell) -> set[Cell]:
    seen = {start}
    q = deque([start])
    while q:
        c = q.popleft()
        for dx, dy in DIRS:
            n = (c[0] + dx, c[1] + dy)
            if n in free and n not in seen:
                seen.add(n)
                q.append(n)
    return seen


# ------------------------------------------------------------ corridor planning

def _thick_nodes(free: set[Cell]) -> tuple[dict[Cell, object], dict[object, int], dict[object, tuple[Cell, Cell]]]:
    """Group cells into nodes: 'T' thick regions (joined through fully-free 2x2
    squares, i.e. coverable by ring splicing), 'K' chains of 1-wide cells with
    two ends, and 'C' single thin cells (junctions / dead ends).
    Returns node-of-cell, node sizes and chain end cells."""
    uf = _UnionFind()
    thick: set[Cell] = set()
    for (ix, iy) in free:
        sq = ((ix, iy), (ix + 1, iy), (ix, iy + 1), (ix + 1, iy + 1))
        if all(c in free for c in sq):
            for c in sq:
                uf.add(c)
            for c in sq[1:]:
                uf.union(sq[0], c)
            thick.update(sq)
    thin = free - thick
    deg = {c: sum(1 for dx, dy in DIRS if (c[0] + dx, c[1] + dy) in free) for c in thin}
    # chains: maximal runs of degree-2 thin cells
    cuf = _UnionFind()
    for c in thin:
        if deg[c] == 2:
            cuf.add(c)
            for dx, dy in DIRS:
                n = (c[0] + dx, c[1] + dy)
                if n in thin and deg[n] == 2:
                    cuf.add(n)
                    cuf.union(c, n)
    node_of: dict[Cell, object] = {}
    size: dict[object, int] = {}
    for c in free:
        if c in thick:
            n = ("T", uf.find(c))
        elif deg[c] == 2:
            n = ("K", cuf.find(c))
        else:
            n = ("C", c)
        node_of[c] = n
        size[n] = size.get(n, 0) + 1
    ends: dict[object, tuple[Cell, Cell]] = {}
    for c in thin:
        n = node_of[c]
        if n[0] != "K":
            continue
        # an end has a neighbour outside the chain
        if any(node_of.get((c[0] + dx, c[1] + dy)) not in (None, n) for dx, dy in DIRS):
            e = ends.get(n)
            ends[n] = (c, c) if e is None else (e[0], c)
    return node_of, size, ends


def plan_corridor(free: set[Cell], a: Cell, b: Cell, budget: int = 60000) -> Optional[list[Cell]]:
    """Corridor from A to B that deliberately threads through regions reachable
    only via 1-cell-wide necks (which ring splicing can never cross), so those
    regions can still be swallowed by the merge step.  Returns None when no
    such plan is needed or it cannot be routed."""
    node_of, size, ends = _thick_nodes(free)
    if len(size) <= 1:
        return None
    # transitions between nodes: node -> neighbour node -> [(u, v) cell pairs]
    trans: dict[object, dict[object, list[tuple[Cell, Cell]]]] = {}
    for u in free:
        nu = node_of[u]
        for dx, dy in DIRS:
            v = (u[0] + dx, u[1] + dy)
            if v in free and node_of[v] != nu:
                trans.setdefault(nu, {}).setdefault(node_of[v], []).append((u, v))
    # keep at most two representative pairs per neighbour to bound branching
    for nu, d in trans.items():
        for nv, pairs in d.items():
            pairs.sort()
            if len(pairs) > 2:
                d[nv] = [pairs[0], pairs[-1]]

    na, nb = node_of[a], node_of[b]
    candidates: list[tuple[int, int, list[tuple[Cell, Cell]]]] = []  # (score, order, seq)
    expansions = 0
    KEEP = 8

    def exit_cell(node, at: Cell) -> Optional[Cell]:
        """Where we must leave `node` from, given we entered at `at`."""
        kind = node[0]
        if kind == "T":
            return None  # anywhere
        if kind == "C":
            return at
        e1, e2 = ends.get(node, (at, at))
        if e1 == e2:
            return e1
        return e2 if at == e1 else e1

    def dfs(node, at: Cell, used_cells: frozenset, used_pairs: frozenset, visited: frozenset,
            seq: list, score: int) -> None:
        nonlocal expansions
        expansions += 1
        if expansions > budget:
            return
        if node == nb and seq:
            candidates.append((score, -expansions, list(seq)))
            candidates.sort(reverse=True)
            del candidates[KEEP:]
        must_leave_from = exit_cell(node, at)
        options = []
        for nv, pairs in trans.get(node, {}).items():
            gain = size[nv] if nv not in visited else 0
            for (u, v) in pairs:
                if (u, v) in used_pairs or (v, u) in used_pairs or v in used_cells:
                    continue
                if must_leave_from is not None and u != must_leave_from:
                    continue
                if nv[0] != "T" and nv in visited:
                    continue  # thin nodes can only be crossed once
                options.append((-gain, nv, u, v))
        options.sort()
        for neg_gain, nv, u, v in options:
            new_used = used_cells | {u, v} if (node[0] != "T" or nv[0] != "T") else used_cells
            seq.append((u, v))
            dfs(nv, v, new_used, used_pairs | {(u, v)}, visited | {nv}, seq, score - neg_gain)
            seq.pop()

    dfs(na, a, frozenset({a}), frozenset(), frozenset({na}), [], size[na])
    log.debug("plan: nodes=%d expansions=%d candidates=%s", len(size), expansions,
              [(c[0], len(c[2])) for c in candidates])
    if not candidates:
        return None

    def build(seq: list[tuple[Cell, Cell]], hug: bool) -> Optional[list[Cell]]:
        """Q leg by leg, each leg confined to the node being crossed."""
        used: set[Cell] = {a}
        q: list[Cell] = [a]
        cur = a
        for (u, v) in seq:
            node = node_of[cur]
            allowed = {c for c in free if node_of[c] == node and c not in used} | {cur}
            leg = [cur] if cur == u else corridor(allowed, cur, u, hug_boundary=hug, force_ends=(cur == a))
            if leg is None or v in used:
                return None
            q.extend(leg[1:])
            used.update(leg)
            q.append(v)
            used.add(v)
            cur = v
        node = node_of[cur]
        allowed = {c for c in free if node_of[c] == node and c not in used} | {cur}
        leg = [cur] if cur == b else corridor(allowed, cur, b, hug_boundary=hug, force_ends=True)
        if leg is None:
            return None
        q.extend(leg[1:])
        if len(set(q)) != len(q):
            return None
        return q

    for score, _, seq in candidates:
        for hug in (True, False):
            q = build(seq, hug)
            if q is not None:
                log.debug("plan: using score=%d seq=%s hug=%s", score, seq, hug)
                return q
    log.debug("plan: no candidate sequence could be routed")
    return None


# ----------------------------------------------------------------------- matching

def _neighbors(c: Cell, cells: set[Cell]) -> list[Cell]:
    out = []
    for dx, dy in DIRS:
        n = (c[0] + dx, c[1] + dy)
        if n in cells:
            out.append(n)
    return out


def max_matching(cells: set[Cell], row_offset: int = 0, col_anchor: int = 0) -> dict[Cell, Cell]:
    """Hopcroft-Karp maximum matching on the grid graph induced by `cells`.
    Returns a symmetric dict cell -> partner.  Seeded with a greedy pairing:
    even-column-aligned horizontal dominoes, then leftovers paired vertically within
    the row pairs starting at `row_offset` (so they line up with the rings the
    merge step builds)."""
    match: dict[Cell, Cell] = {}
    ordered = sorted(cells, key=lambda t: (t[1], t[0]))
    # Horizontal dominoes anchored on even columns so that dominoes in
    # neighbouring rows line up (misaligned dominoes can never be spliced).
    for c in ordered:
        if c in match or c[0] % 2 != col_anchor:
            continue
        r = (c[0] + 1, c[1])
        if r in cells and r not in match:
            match[c] = r
            match[r] = c
    for c in ordered:
        if c in match or (c[1] - row_offset) % 2 != 0:
            continue
        d = (c[0], c[1] + 1)
        if d in cells and d not in match:
            match[c] = d
            match[d] = c

    left = [c for c in cells if (c[0] + c[1]) % 2 == 0]
    adj = {c: _neighbors(c, cells) for c in cells}

    while True:
        # BFS layering from free left vertices
        dist: dict[Cell, float] = {}
        q: deque[Cell] = deque()
        for u in left:
            if u not in match:
                dist[u] = 0
                q.append(u)
        found = False
        while q:
            u = q.popleft()
            for v in adj[u]:
                w = match.get(v)
                if w is None:
                    found = True
                elif w not in dist:
                    dist[w] = dist[u] + 1
                    q.append(w)
        if not found:
            break

        def augment(root: Cell) -> bool:
            stack: list[list] = [[root, iter(adj[root]), None]]
            while stack:
                frame = stack[-1]
                u = frame[0]
                advanced = False
                for v in frame[1]:
                    w = match.get(v)
                    if w is None:
                        frame[2] = v
                        for fu, _, fv in stack:
                            match[fu] = fv
                            match[fv] = fu
                        return True
                    if dist.get(w) == dist[u] + 1:
                        frame[2] = v
                        stack.append([w, iter(adj[w]), None])
                        advanced = True
                        break
                if not advanced:
                    dist[u] = INF
                    stack.pop()
            return False

        for u in left:
            if u not in match:
                augment(u)
    return match


# ------------------------------------------------------------------------ merging

class _UnionFind:
    def __init__(self) -> None:
        self.p: dict[Cell, Cell] = {}

    def add(self, c: Cell) -> None:
        self.p.setdefault(c, c)

    def find(self, c: Cell) -> Cell:
        root = c
        while self.p[root] != root:
            root = self.p[root]
        while self.p[c] != root:
            self.p[c], c = root, self.p[c]
        return root

    def union(self, a: Cell, b: Cell) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


class _EdgeSet:
    """Multigraph on cells; dominoes are stored as a double edge."""

    def __init__(self) -> None:
        self.adj: dict[Cell, dict[Cell, int]] = {}

    def add(self, u: Cell, v: Cell) -> None:
        for a, b in ((u, v), (v, u)):
            d = self.adj.setdefault(a, {})
            d[b] = d.get(b, 0) + 1

    def remove(self, u: Cell, v: Cell) -> None:
        for a, b in ((u, v), (v, u)):
            n = self.adj[a][b] - 1
            if n == 0:
                del self.adj[a][b]
            else:
                self.adj[a][b] = n

    def has(self, u: Cell, v: Cell) -> bool:
        return v in self.adj.get(u, {})

    def degree(self, u: Cell) -> int:
        return sum(self.adj.get(u, {}).values())


def _merge_components(edges: _EdgeSet, uf: _UnionFind, nx: int, ny: int, q_root: Cell,
                      offset: int) -> None:
    covered = edges.adj

    def try_square(ix: int, iy: int, allow_q: bool) -> bool:
        p, q, r, s = (ix, iy), (ix + 1, iy), (ix, iy + 1), (ix + 1, iy + 1)
        if p not in covered or q not in covered or r not in covered or s not in covered:
            return False
        # horizontal opposite edges p-q and r-s -> replace with p-r, q-s
        if edges.has(p, q) and edges.has(r, s):
            fp, fr = uf.find(p), uf.find(r)
            if fp != fr and (allow_q or (fp != q_root and fr != q_root)):
                edges.remove(p, q)
                edges.remove(r, s)
                edges.add(p, r)
                edges.add(q, s)
                uf.union(p, r)
                return True
        # vertical opposite edges p-r and q-s -> replace with p-q, r-s
        if edges.has(p, r) and edges.has(q, s):
            fp, fq = uf.find(p), uf.find(q)
            if fp != fq and (allow_q or (fp != q_root and fq != q_root)):
                edges.remove(p, r)
                edges.remove(q, s)
                edges.add(p, q)
                edges.add(r, s)
                uf.union(p, q)
                return True
        return False

    def sweep(rows: range, allow_q: bool) -> bool:
        changed = False
        for iy in rows:
            for ix in range(nx - 1):
                if try_square(ix, iy, allow_q):
                    changed = True
        return changed

    # Phase A: rings within row pairs (excluding the corridor)
    while sweep(range(offset, ny - 1, 2), allow_q=False):
        pass
    # Phase B: chain rings vertically, first square found (leftmost) wins
    sweep(range(1 - offset, ny - 1, 2), allow_q=False)
    # Phase C: everything, including the corridor, until stable
    while sweep(range(ny - 1), allow_q=True):
        pass


def _ring_offset(cells: set[Cell], nx: int, ny: int) -> int:
    """Row-pair offset (0 or 1) that puts the most fully-free 2x2 squares
    inside row pairs, i.e. the pairing that yields the longest rings."""
    def score(offset: int) -> int:
        n = 0
        for iy in range(offset, ny - 1, 2):
            for ix in range(nx - 1):
                if ((ix, iy) in cells and (ix + 1, iy) in cells
                        and (ix, iy + 1) in cells and (ix + 1, iy + 1) in cells):
                    n += 1
        return n
    return 0 if score(0) >= score(1) else 1

def _parity_bound(free: set[Cell], a: Cell, b: Cell) -> int:
    """Minimum number of cells any A->B path must leave uncovered, from the
    checkerboard colouring (path cells alternate colours)."""
    n0 = sum(1 for c in free if (c[0] + c[1]) % 2 == 0)
    n1 = len(free) - n0
    ca, cb = (a[0] + a[1]) % 2, (b[0] + b[1]) % 2
    if ca != cb:
        longest = 2 * min(n0, n1)
    else:
        same, other = (n0, n1) if ca == 0 else (n1, n0)
        longest = 2 * min(same - 1, other) + 1
    return max(0, len(free) - longest)


def _solve(free: set[Cell], a: Cell, b: Cell, nx: int, ny: int, mode: str, anchor: int,
           flip_offset: bool) -> tuple[list[Cell], set[Cell]]:
    """One corridor + matching + merge attempt. Returns the A->B cell path and
    the set of cells it covers.  `mode`: "planned" | "plain" | "hug"."""
    q = None
    if mode == "planned":
        q = plan_corridor(free, a, b)
    if q is None:
        q = corridor(free, a, b, hug_boundary=(mode == "hug"), force_ends=True)
    assert q is not None
    edges = _EdgeSet()
    uf = _UnionFind()
    for c in q:
        uf.add(c)
    for i in range(len(q) - 1):
        edges.add(q[i], q[i + 1])
        uf.union(q[i], q[i + 1])
    rest = free - set(q)
    offset = _ring_offset(rest, nx, ny)
    if flip_offset:
        offset = 1 - offset
    match = max_matching(rest, offset, anchor)
    for u, v in match.items():
        if u < v:
            uf.add(u)
            uf.add(v)
            uf.union(u, v)
            edges.add(u, v)
            edges.add(u, v)
    _merge_components(edges, uf, nx, ny, uf.find(a), offset)

    # Walk the corridor component from A.
    path: list[Cell] = [a]
    prev: Optional[Cell] = None
    cur = a
    seen = {a}
    while True:
        nxt = None
        for n in edges.adj.get(cur, {}):
            if n != prev and n not in seen:
                nxt = n
                break
        if nxt is None:
            break
        path.append(nxt)
        seen.add(nxt)
        prev, cur = cur, nxt
    if cur != b:
        raise GenError("Internal error: path did not terminate at pad B")
    root = uf.find(a)
    comp_size = sum(1 for c in uf.p if uf.find(c) == root)
    if comp_size != len(path):
        raise GenError("Internal error: path does not cover its component")
    return path, seen


# ------------------------------------------------------------------------- output

@dataclass
class GenResult:
    width: float
    pitch_x: float
    pitch_y: float
    nx: int
    ny: int
    grid: Grid
    cells_path: list[Cell]               # A-end .. B-end
    path: list[Point]                    # simplified centreline polyline (mm)
    lead_a: Optional[list[Point]]        # [cell centre, pad] if pad is off-grid
    lead_b: Optional[list[Point]]
    pad_a: Point
    pad_b: Point
    covered: int
    free_cells: int
    length_mm: float
    warnings: list[str] = field(default_factory=list)
    uncovered: list[Cell] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        return self.covered / self.free_cells if self.free_cells else 0.0

    def segments(self) -> list[tuple[Point, Point]]:
        segs = []
        for poly in (self.lead_a, self.path, self.lead_b):
            if poly:
                for i in range(len(poly) - 1):
                    segs.append((poly[i], poly[i + 1]))
        return segs


def _simplify(points: list[Point]) -> list[Point]:
    if len(points) < 3:
        return list(points)
    out = [points[0]]
    for i in range(1, len(points) - 1):
        (x0, y0), (x1, y1), (x2, y2) = out[-1], points[i], points[i + 1]
        cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
        if abs(cross) > 1e-9:
            out.append(points[i])
    out.append(points[-1])
    return out


def _seg_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    def orient(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4)


def _transpose(cells, swap: bool):
    if not swap:
        return cells
    return [(c[1], c[0]) for c in cells]


def generate(design: Design, width: float) -> GenResult:
    """Generate the trace for `design` at the given trace width."""
    p = design.params
    if design.heater is None or not design.heater.is_valid():
        raise GenError("Draw a heater area first")
    if design.pad_a is None or design.pad_b is None:
        raise GenError("Place both endpoints (pads A and B)")
    space = p.min_space
    heater = design.heater
    grid = build_grid(heater, design.keepouts, width, space)
    if not grid.free:
        raise GenError("Keepouts cover the whole heater area")

    warnings: list[str] = []

    def snap(pt: Point, label: str) -> tuple[Cell, Optional[list[Point]]]:
        inside = heater.contains(pt[0], pt[1])
        c = grid.nearest_free(pt[0], pt[1], boundary_only=not inside)
        if c is None:
            raise GenError(f"No free cell for pad {label}")
        if inside:
            return c, None
        return c, [grid.center(c), pt]

    a, lead_a = snap(design.pad_a, "A")
    b, lead_b = snap(design.pad_b, "B")
    if a == b:
        raise GenError("Pads A and B snap to the same cell; move them apart")

    # Work in a transposed frame for vertical orientation so the merging
    # heuristics (which favour long runs along X) produce runs along Y.
    swap = p.orientation == "vertical"
    if swap:
        free = {(c[1], c[0]) for c in grid.free}
        a_t, b_t = (a[1], a[0]), (b[1], b[0])
        nx_t, ny_t = grid.ny, grid.nx
    else:
        free = set(grid.free)
        a_t, b_t = a, b
        nx_t, ny_t = grid.nx, grid.ny

    reachable = _component(free, a_t)
    if b_t not in reachable:
        raise GenError("Pads A and B are not connected through the free area")
    islands = free - reachable
    if islands:
        warnings.append(f"{len(islands)} cells are cut off from the pads by keepouts and cannot be "
                        f"reached (highlighted)")
    free_all = free
    free = reachable

    bound = _parity_bound(free, a_t, b_t)
    best: Optional[tuple[list[Cell], set[Cell]]] = None
    # A handful of cheap variants (corridor style, domino alignment, ring
    # pairing) rescue cases where the matching strands a strip; stop as soon as
    # the parity bound is reached.
    for mode, anchor, flip_offset in itertools.product(("planned", "plain", "hug"), (0, 1), (False, True)):
        cells_t, seen = _solve(free, a_t, b_t, nx_t, ny_t, mode, anchor, flip_offset)
        if best is None or len(cells_t) > len(best[0]):
            best = (cells_t, seen)
        if len(free) - len(cells_t) <= bound:
            break
    assert best is not None
    cells_path, seen = best

    uncovered_t = [c for c in free_all if c not in seen]
    cells_path = _transpose(cells_path, swap)
    uncovered = _transpose(uncovered_t, swap)

    covered = len(cells_path)
    if len(uncovered) > len(islands):
        pct = 100 * covered / len(free_all)
        if len(uncovered) - len(islands) <= bound:
            warnings.append(f"{len(uncovered)} cell(s) left uncovered by checkerboard parity "
                            f"({pct:.2f}% coverage) - unavoidable for these pad positions")
        else:
            warnings.append(f"{len(uncovered) - len(islands)} of {len(free)} reachable cells could not be "
                            f"covered ({pct:.1f}%). "
                            f"Uncovered cells are highlighted; usually a pad sits in a dead-end pocket or "
                            f"a keepout leaves a 1-cell-wide gap - move the pad/keepout or try the other "
                            f"run direction.")

    pts = [grid.center(c) for c in cells_path]
    path = _simplify(pts)
    pad_a = design.pad_a if lead_a else pts[0]
    pad_b = design.pad_b if lead_b else pts[-1]

    length = 0.0
    for poly in (lead_a, path, lead_b):
        if poly:
            for i in range(len(poly) - 1):
                length += math.dist(poly[i], poly[i + 1])

    # Lead sanity checks
    for lead, label in ((lead_a, "A"), (lead_b, "B")):
        if not lead:
            continue
        crosses = 0
        for i in range(len(path) - 1):
            s0, s1 = path[i], path[i + 1]
            if lead[0] in (s0, s1):
                continue
            if _seg_intersect(lead[0], lead[1], s0, s1):
                crosses += 1
        if crosses:
            warnings.append(f"Lead to pad {label} crosses the heater trace ({crosses}x); move the pad")
        for k in design.keepouts:
            lx1, ly1 = min(lead[0][0], lead[1][0]), min(lead[0][1], lead[1][1])
            lx2, ly2 = max(lead[0][0], lead[1][0]), max(lead[0][1], lead[1][1])
            if k.intersects_box(lx1 - width / 2, ly1 - width / 2, lx2 + width / 2, ly2 + width / 2):
                warnings.append(f"Lead to pad {label} passes through a keepout")
                break

    return GenResult(width=width, pitch_x=grid.px, pitch_y=grid.py, nx=grid.nx, ny=grid.ny,
                     grid=grid, cells_path=cells_path, path=path, lead_a=lead_a, lead_b=lead_b,
                     pad_a=pad_a, pad_b=pad_b, covered=covered, free_cells=len(free_all),
                     length_mm=length, warnings=warnings, uncovered=uncovered)


# ----------------------------------------------------------------- full pipeline

def run(design: Design) -> GenResult:
    """Choose a trace width (solving for the target resistance when set) and
    generate the trace."""
    p = design.params
    if design.heater is None or not design.heater.is_valid():
        raise GenError("Draw a heater area first")
    w_min = p.min_width
    if w_min <= 0 or p.min_space <= 0:
        raise GenError("Trace width and spacing must be positive")

    if p.target_ohms and p.target_ohms > 0:
        area = design.heater.area - sum(_overlap_area(k, design.heater) for k in design.keepouts)
        area = max(area, design.heater.area * 0.05)
        w = max(w_min, res.solve_width(area, p.min_space, p.target_ohms, p.copper_oz))
        result = generate(design, w)
        for _ in range(2):
            r_act = res.resistance(result.length_mm, result.width, p.copper_oz)
            if abs(r_act - p.target_ohms) / p.target_ohms < 0.01:
                break
            w2 = max(w_min, res.rescale_width(result.width, p.min_space, r_act, p.target_ohms))
            if abs(w2 - result.width) < 1e-4:
                break
            result = generate(design, w2)
        r_act = res.resistance(result.length_mm, result.width, p.copper_oz)
        if r_act < p.target_ohms * 0.97 and result.width <= w_min + 1e-9:
            result.warnings.insert(0, f"Target {p.target_ohms:.3g} Ω unreachable: at minimum width the "
                                      f"heater is {r_act:.3g} Ω. Lower the target, enlarge the area, "
                                      f"or use heavier copper.")
        return result
    return generate(design, w_min)


def _overlap_area(a: Rect, b: Rect) -> float:
    w = min(a.x2, b.x2) - max(a.x, b.x)
    h = min(a.y2, b.y2) - max(a.y, b.y)
    return w * h if w > 0 and h > 0 else 0.0
