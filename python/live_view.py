#!/usr/bin/env python3
"""live_view.py - Real-time visualization for the Island-GA solving the TSP.

The GA itself runs entirely in C++ (cpp/tsp_island). This file only DRAWS what that
solver streams out; it contains no algorithm of its own.

tsp_island --live <base> makes EVERY rank write its OWN stream file (<base>.rank0,
<base>.rank1, ...) - each line is that rank's own current best, every generation. This
viewer reads all of them together so you SEE the islands searching in parallel: one
small route panel per island + a shared convergence chart (every island's curve + the
true global best = min across islands), with green markers at each --sync generation.

Two modes:

  run  - Launch the C++ MPI solver on THIS machine (mpirun --oversubscribe) with a
         temporary --live stream base, then animate all islands live as they evolve.
         Good for a one-machine demo / slides.

           python3 live_view.py run ../data/cities_30.txt --islands 4 --gens 400 --sync 20

  tail - "Tail" the stream files produced by a REAL distributed run on the cluster
         (cpp/tsp_island --live stream.jsonl) and draw their progress live.

           # window 1 (on rank 0 / the head node):
           mpirun --hostfile ../cluster/hosts -np 4 ./tsp_island ../data/cities_30.txt \
                  --gens 400 --sync 20 --live ../results/stream.jsonl
           # window 2 (note --islands must match the -np above):
           python3 live_view.py tail ../results/stream.jsonl ../data/cities_30.txt --islands 4

Window layout (both modes):
  - Left grid : one small panel per island, its OWN current best route, redrawn each
                generation (colored border per island, small square = start city).
  - Right     : convergence graph - one faint line per island + the bold global-best
                line, green vertical markers at each --sync generation.
  - Title     : current generation, true global best, elapsed time, migration mode.

Requires: matplotlib + numpy (NO mpi4py).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


def read_cities(path):
    """Read a city-coordinate file. Each line: 'x y' (blank / '#' lines skipped)."""
    pts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            x, y = line.split()[:2]
            pts.append((float(x), float(y)))
    return np.array(pts, dtype=float)


def find_binary(explicit):
    """Locate the C++ solver binary (cpp/tsp_island[.exe])."""
    if explicit:
        return explicit
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    for cand in ("tsp_island", "tsp_island.exe"):
        p = os.path.join(root, "cpp", cand)
        if os.path.exists(p):
            return p
    return os.path.join(root, "cpp", "tsp_island")   # best guess; error surfaces on launch


# --------------------------------------------------------------------------- #
#  Multi-island canvas: a small route panel PER ISLAND (proves they search in
#  parallel, each with its own tour) + one shared convergence panel with every
#  island's curve + the bold global-best curve + green markers at each sync.
# --------------------------------------------------------------------------- #
_PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf",
            "#8c564b", "#e377c2"]


class MultiCanvas:
    def __init__(self, coords, n_islands, title_mode="run", sync=20):
        self.coords = coords
        self.n = n_islands
        self.title_mode = title_mode
        self.sync = sync
        ncols = 2 if n_islands <= 4 else 3
        nrows = (n_islands + ncols - 1) // ncols

        self.fig = plt.figure(figsize=(6 + 3 * ncols, max(5, 2.6 * nrows)))
        try:
            self.fig.canvas.manager.set_window_title("TSP Island-GA - Real-time (parallel islands)")
        except Exception:
            pass
        gs = self.fig.add_gridspec(nrows, ncols + 2, wspace=0.35, hspace=0.45)

        pad = 0.06 * (coords.max(0) - coords.min(0)).max()
        xlim = (coords[:, 0].min() - pad, coords[:, 0].max() + pad)
        ylim = (coords[:, 1].min() - pad, coords[:, 1].max() + pad)

        self.route_ax, self.route_ln, self.start_mk, self.route_title = [], [], [], []
        for i in range(n_islands):
            r, c = divmod(i, ncols)
            ax = self.fig.add_subplot(gs[r, c])
            ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect("equal")
            ax.set_xticks([]); ax.set_yticks([])
            color = _PALETTE[i % len(_PALETTE)]
            for spine in ax.spines.values():
                spine.set_edgecolor(color); spine.set_linewidth(2.2)
            ax.scatter(coords[:, 0], coords[:, 1], c="#888", s=10, zorder=3)
            (ln,) = ax.plot([], [], "-", lw=1.4, color=color, zorder=2)
            (mk,) = ax.plot([], [], "s", ms=8, color=color, mec="black", mew=0.6, zorder=4)
            t = ax.set_title(f"island {i}", fontsize=9, color=color, fontweight="bold")
            self.route_ax.append(ax); self.route_ln.append(ln)
            self.start_mk.append(mk); self.route_title.append(t)

        self.ax_conv = self.fig.add_subplot(gs[:, ncols:])
        self.ax_conv.set_xlabel("Generation"); self.ax_conv.set_ylabel("Best tour length")
        self.ax_conv.grid(alpha=0.3)
        self.island_lines = [self.ax_conv.plot([], [], lw=1.0, alpha=0.55,
                              color=_PALETTE[i % len(_PALETTE)], label=f"island {i}")[0]
                              for i in range(n_islands)]
        (self.gbest_ln,) = self.ax_conv.plot([], [], lw=2.6, color="black",
                                             label="global best", zorder=5)
        self.ax_conv.legend(loc="upper right", fontsize=8, ncol=2)
        self._sync_drawn_up_to = 0

    def draw_island(self, i, tour, best_len):
        loop = np.append(tour, tour[0])
        self.route_ln[i].set_data(self.coords[loop, 0], self.coords[loop, 1])
        self.start_mk[i].set_data([self.coords[tour[0], 0]], [self.coords[tour[0], 1]])
        self.route_title[i].set_text(f"island {i}  |  {best_len:.1f}")

    def draw_conv(self, island_hists, gbest_hist):
        xmax = max((len(h) for h in island_hists), default=1)
        for ln, h in zip(self.island_lines, island_hists):
            ln.set_data(range(len(h)), h)
        self.gbest_ln.set_data(range(len(gbest_hist)), gbest_hist)
        if self.sync > 0:
            while self._sync_drawn_up_to + self.sync < xmax:
                self._sync_drawn_up_to += self.sync
                self.ax_conv.axvline(self._sync_drawn_up_to, color="green",
                                      lw=0.7, alpha=0.25, zorder=1)
        allvals = [v for h in island_hists for v in h] + list(gbest_hist)
        if allvals:
            ymin, ymax = min(allvals), max(allvals)
            if ymin < ymax:
                m = 0.05 * (ymax - ymin)
                self.ax_conv.set_xlim(0, max(xmax, 1))
                self.ax_conv.set_ylim(ymin - m, ymax + m)

    def set_title(self, gen, gbest, elapsed, extra=""):
        self.fig.suptitle(
            f"[{self.title_mode}] {self.n} islands running in PARALLEL  |  generation {gen}  "
            f"|  global best = {gbest:.2f}  |  {elapsed:.1f}s  {extra}", fontsize=12)


# --------------------------------------------------------------------------- #
#  JSONL stream tailing (shared by both modes)
# --------------------------------------------------------------------------- #
class MultiTailer:
    """Follows ONE JSONL stream file PER ISLAND (<base>.rank0, .rank1, ...) and animates
    all of them together: each island's own route in its own panel, plus a shared
    convergence chart (every island's curve + the true global-best = min over islands).
    Optionally owns a subprocess (the C++ solver) that writes the streams."""

    def __init__(self, stream_base, coords, n_islands, title_mode, interval, step=5,
                 sync=20, proc=None):
        self.streams = [f"{stream_base}.rank{i}" for i in range(n_islands)]
        self.canvas = MultiCanvas(coords, n_islands, title_mode=title_mode, sync=sync)
        self.interval = interval
        self.step = max(1, step)
        self.proc = proc
        self.pos = [0] * n_islands
        self.bufs = [[] for _ in range(n_islands)]   # one record list per island
        self.idx = 0
        self.t0 = time.perf_counter()

    def _read_new(self, i):
        path = self.streams[i]
        if not os.path.exists(path):
            return []
        out = []
        with open(path, "r") as f:
            f.seek(self.pos[i])
            for line in f:
                if line.endswith("\n"):
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            self.pos[i] = f.tell()
        return out

    def _update(self, _frame):
        for i in range(len(self.bufs)):
            self.bufs[i].extend(self._read_new(i))
        min_len = min((len(b) for b in self.bufs), default=0)
        if min_len == 0:
            return                                  # at least one island hasn't written yet
        self.idx = min(self.idx + self.step, min_len - 1)

        island_hists = [[r["best_len"] for r in b[:self.idx + 1]] for b in self.bufs]
        gbest_hist = np.minimum.reduce(island_hists) if island_hists else []
        for i, b in enumerate(self.bufs):
            rec = b[self.idx]
            if "tour" in rec:
                self.canvas.draw_island(i, np.asarray(rec["tour"], dtype=int), rec["best_len"])
        self.canvas.draw_conv(island_hists, gbest_hist)

        caught_up = self.idx >= min_len - 1
        done = caught_up and all(b[-1].get("done", False) for b in self.bufs)
        extra = "| DONE" if done else ("| running..." if caught_up else "| replaying search...")
        gen = self.bufs[0][self.idx].get("gen", self.idx)
        self.canvas.set_title(gen, gbest_hist[-1] if len(gbest_hist) else float("nan"),
                              time.perf_counter() - self.t0, extra=extra)

    def run(self, save=None):
        anim = FuncAnimation(self.canvas.fig, self._update,
                             interval=self.interval, cache_frame_data=False)
        if save:
            fps = max(1, int(1000 / self.interval))
            print(f"Recording video -> {save} ({fps} fps)... this can take a while.")
            try:
                anim.save(save, fps=fps, dpi=110)
                print(f"Saved video -> {save}")
            except Exception as e:
                print(f"Could not write video ({e}). Need ffmpeg (mp4) or pillow (gif).")
        else:
            plt.tight_layout()
            plt.show()
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()


# --------------------------------------------------------------------------- #
#  RUN: launch the C++ solver locally, then tail its stream
# --------------------------------------------------------------------------- #
def cmd_run(args):
    coords = read_cities(args.cities)
    binary = find_binary(args.binary)
    if not os.path.exists(binary):
        sys.exit(f"C++ solver not found: {binary}\nBuild it first: cd cpp && make")
    stream = tempfile.mktemp(suffix=".jsonl")     # base path; solver writes <stream>.rank<i>
    cmd = ["mpirun", "--oversubscribe", "-np", str(args.islands), binary, args.cities,
           "--gens", str(args.gens), "--pop", str(args.pop),
           "--sync", str(args.sync), "--migrants", str(args.migrants),
           "--twoopt", str(args.twoopt), "--seed", str(args.seed), "--live", stream]
    print("Launching:", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mode = f"{args.islands} islands, " + (
        f"sync every {args.sync} gens" if args.sync else "NO sharing")
    tailer = MultiTailer(stream, coords, args.islands, title_mode="run/C++",
                         interval=args.interval, step=args.step, sync=args.sync, proc=proc)
    print(f"Streaming from {stream}.rank*  ({mode})  (close the window to stop)")
    tailer.run(save=args.save)


# --------------------------------------------------------------------------- #
#  TAIL: follow the stream files written by a real cluster run
# --------------------------------------------------------------------------- #
def cmd_tail(args):
    coords = read_cities(args.cities)
    tailer = MultiTailer(args.stream, coords, args.islands, title_mode="tail/MPI",
                         interval=args.interval, step=args.step, sync=args.sync)
    print(f"Tailing: {args.stream}.rank0..{args.islands - 1}  (Ctrl+C to quit)")
    tailer.run(save=args.save)


def cmd_race(args):
    """Islands race: overlay every island's convergence curve + the global best, with
    vertical markers at each sync. Shows the parallel search + result sharing directly.
    Reads the per-rank history files the solver writes with --out (<prefix>.rankN.history)."""
    import glob
    files = sorted(glob.glob(args.prefix + ".rank*.history"),
                   key=lambda p: int(p.split(".rank")[1].split(".")[0]))
    if not files:
        sys.exit(f"No per-rank history files {args.prefix}.rank*.history\n"
                 f"Run the solver with --out {args.prefix} first.")
    hs = [np.atleast_1d(np.loadtxt(f)) for f in files]
    G = min(len(h) for h in hs)
    hs = [h[:G] for h in hs]
    gbest = np.minimum.reduce(hs)              # global best per generation = min over islands

    fig, ax = plt.subplots(figsize=(11, 6))
    try:
        fig.canvas.manager.set_window_title("Islands race")
    except Exception:
        pass
    ax.set_xlabel("Generation"); ax.set_ylabel("Best tour length"); ax.grid(alpha=0.3)
    if args.sync > 0:
        for k in range(args.sync, G, args.sync):
            ax.axvline(k, color="green", lw=0.6, alpha=0.18, zorder=1)
    lines = [ax.plot([], [], lw=1.1, alpha=0.75, label=f"island {i}", zorder=2)[0]
             for i in range(len(hs))]
    (gln,) = ax.plot([], [], lw=2.6, color="black", label="global best", zorder=5)
    # Zoom the y-axis to the convergence band (near the optimum) so the island spread and the
    # per-sync jumps are visible. The long descent from the random start enters from the top.
    bot = float(gbest.min())
    top = bot * args.zoom
    ax.set_ylim(bot - 0.04 * (top - bot), top)
    # Start the x-axis where the islands enter the band, so the plot is not half empty.
    start = int(np.argmax(gbest <= top)) if bool((gbest <= top).any()) else 0
    ax.set_xlim(max(0, start - max(1, (G - start) // 20)), G)
    ax.legend(loc="upper right", fontsize=8, ncol=2)

    # Skip the long descent that happens above the zoom band so the animation is lively.
    nframes = (G - start + args.step - 1) // args.step

    def upd(f):
        i = min(start + (f + 1) * args.step, G)
        xs = np.arange(i)
        for ln, h in zip(lines, hs):
            ln.set_data(xs, h[:i])
        gln.set_data(xs, gbest[:i])
        ax.set_title(f"Islands race - {len(hs)} islands, sync every {args.sync} gens   "
                     f"|  gen {i}   global best {gbest[i - 1]:.1f}")
        return lines + [gln]

    anim = FuncAnimation(fig, upd, frames=nframes, interval=args.interval,
                         blit=False, repeat=False, cache_frame_data=False)
    if args.save:
        fps = max(1, int(1000 / args.interval))
        print(f"Rendering {args.save} ({nframes} frames)... this can take a moment.")
        anim.save(args.save, writer="pillow", fps=fps, dpi=args.dpi)
        print(f"Saved {args.save}")
    else:
        plt.tight_layout(); plt.show()


def main():
    ap = argparse.ArgumentParser(description="Real-time visualization for the Island-GA TSP")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="launch the C++ solver locally + animate")
    r.add_argument("cities")
    r.add_argument("--islands", type=int, default=4)
    r.add_argument("--gens", type=int, default=400)
    r.add_argument("--pop", type=int, default=200)
    r.add_argument("--sync", type=int, default=20, help="migration interval; 0 = no sharing")
    r.add_argument("--migrants", type=int, default=3, help="individuals recombined with the global best per sync")
    r.add_argument("--twoopt", type=int, default=0, help="2-opt period (Memetic); 0 = off")
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--interval", type=int, default=60, help="ms between animation frames")
    r.add_argument("--step", type=int, default=5, help="generations advanced per frame (lower = slower replay)")
    r.add_argument("--binary", default=None, help="path to the C++ solver (default: cpp/tsp_island)")
    r.add_argument("--save", default=None, help="save a video (mp4/gif) instead of showing")
    r.set_defaults(func=cmd_run)

    t = sub.add_parser("tail", help="follow the stream files of a real MPI run")
    t.add_argument("stream", help="base path passed to --live; solver writes <stream>.rank<i>")
    t.add_argument("cities")
    t.add_argument("--islands", type=int, required=True, help="must match the -np used to launch the solver")
    t.add_argument("--sync", type=int, default=20, help="sync interval (for the vertical markers)")
    t.add_argument("--interval", type=int, default=60, help="ms between animation frames")
    t.add_argument("--step", type=int, default=5, help="generations advanced per frame (lower = slower replay)")
    t.add_argument("--save", default=None, help="save a video (rarely used in tail mode)")
    t.set_defaults(func=cmd_tail)

    rc = sub.add_parser("race", help="islands race: overlay per-island convergence + sync markers")
    rc.add_argument("prefix", help="--out prefix used by the solver (reads <prefix>.rankN.history)")
    rc.add_argument("--sync", type=int, default=25, help="sync interval (for the vertical markers)")
    rc.add_argument("--interval", type=int, default=60, help="ms between frames")
    rc.add_argument("--step", type=int, default=5, help="generations advanced per frame")
    rc.add_argument("--save", default=None, help="save a GIF instead of showing (e.g. results/islands_race.gif)")
    rc.add_argument("--dpi", type=int, default=90, help="GIF resolution when --save is used")
    rc.add_argument("--zoom", type=float, default=1.5,
                    help="y-axis top = best*zoom; smaller zooms into the convergence band")
    rc.set_defaults(func=cmd_race)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
