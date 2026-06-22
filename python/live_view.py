#!/usr/bin/env python3
"""live_view.py - Real-time visualization for the Island-GA solving the TSP.

The GA itself runs entirely in C++ (cpp/tsp_island). This file only DRAWS what that
solver streams out; it contains no algorithm of its own.

Two modes:

  run  - Launch the C++ MPI solver on THIS machine (mpirun --oversubscribe) with a
         temporary --live stream file, then animate the best route + convergence graph
         live as the solver evolves. Good for a one-machine demo / slides.

           python3 live_view.py run ../data/cities_30.txt --islands 4 --gens 400 --sync 20

  tail - "Tail" a JSONL stream file produced by a REAL distributed run on the cluster
         (cpp/tsp_island --live stream.jsonl) and draw its progress live.

           # window 1 (on rank 0 / the head node):
           mpirun --hostfile ../cluster/hosts -np 4 ./tsp_island ../data/cities_30.txt \
                  --gens 400 --sync 20 --live ../results/stream.jsonl
           # window 2:
           python3 live_view.py tail ../results/stream.jsonl ../data/cities_30.txt

Window layout (both modes):
  - Left  : current best route, redrawn each generation, red square = start city.
  - Right : convergence graph (best tour length per generation) growing over time.
  - Title : current generation, best length, elapsed time, and the migration mode.

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
#  Shared canvas: left = route, right = convergence graph
# --------------------------------------------------------------------------- #
class LiveCanvas:
    def __init__(self, coords, title_mode="run"):
        self.coords = coords
        self.title_mode = title_mode
        self.fig, (self.ax_route, self.ax_conv) = plt.subplots(
            1, 2, figsize=(13, 6), gridspec_kw={"width_ratios": [1, 1]})
        try:
            self.fig.canvas.manager.set_window_title("TSP Island-GA - Real-time")
        except Exception:
            pass

        # fix the route axes so it does not jump around every frame
        pad = 0.05 * (coords.max(0) - coords.min(0)).max()
        self.ax_route.set_xlim(coords[:, 0].min() - pad, coords[:, 0].max() + pad)
        self.ax_route.set_ylim(coords[:, 1].min() - pad, coords[:, 1].max() + pad)
        self.ax_route.set_aspect("equal")
        self.ax_route.set_xlabel("x"); self.ax_route.set_ylabel("y")
        self.ax_conv.set_xlabel("Generation")
        self.ax_conv.set_ylabel("Best tour length")
        self.ax_conv.grid(alpha=0.3)

        # reusable artists (update data instead of redrawing from scratch)
        self.cities_sc = self.ax_route.scatter(coords[:, 0], coords[:, 1],
                                                c="#1f77b4", s=18, zorder=3)
        (self.route_ln,) = self.ax_route.plot([], [], "-", lw=1.3,
                                              color="#ff7f0e", zorder=2)
        (self.start_mk,) = self.ax_route.plot([], [], "rs", ms=11,
                                              label="start city", zorder=4)
        self.ax_route.legend(loc="upper right", fontsize=8)
        self.conv_lines = {}          # label -> Line2D
        self._mig_marks = []

    def draw_route(self, tour):
        loop = np.append(tour, tour[0])
        self.route_ln.set_data(self.coords[loop, 0], self.coords[loop, 1])
        self.start_mk.set_data([self.coords[tour[0], 0]], [self.coords[tour[0], 1]])

    def draw_conv(self, series_dict):
        """series_dict: {label: list_of_values}. Creates / updates one line each."""
        ymin = float("inf"); ymax = float("-inf"); xmax = 1
        for label, ys in series_dict.items():
            if not ys:
                continue
            xs = range(len(ys))
            if label not in self.conv_lines:
                bold = label == "global best"
                (ln,) = self.ax_conv.plot([], [], lw=2.2 if bold else 1.0,
                                          label=label,
                                          color="#d62728" if bold else None,
                                          zorder=5 if bold else 2,
                                          alpha=1.0 if bold else 0.6)
                self.conv_lines[label] = ln
                self.ax_conv.legend(loc="upper right", fontsize=8)
            self.conv_lines[label].set_data(list(xs), ys)
            ymin = min(ymin, min(ys)); ymax = max(ymax, max(ys))
            xmax = max(xmax, len(ys))
        if ymin < ymax:
            m = 0.05 * (ymax - ymin)
            self.ax_conv.set_xlim(0, xmax)
            self.ax_conv.set_ylim(ymin - m, ymax + m)

    def set_title(self, gen, best_len, elapsed, extra=""):
        self.ax_route.set_title(
            f"Best route - length = {best_len:.1f}", fontsize=11)
        self.fig.suptitle(
            f"[{self.title_mode}] generation {gen}  |  best = {best_len:.2f}  "
            f"|  {elapsed:.1f}s  {extra}", fontsize=12)


# --------------------------------------------------------------------------- #
#  JSONL stream tailing (shared by both modes)
# --------------------------------------------------------------------------- #
class StreamTailer:
    """Follows a JSONL stream file and animates it. Optionally owns a subprocess
    (the C++ solver) that writes the stream."""

    def __init__(self, stream_path, coords, title_mode, interval, step=5, proc=None):
        self.stream = stream_path
        self.canvas = LiveCanvas(coords, title_mode=title_mode)
        self.interval = interval
        self.step = max(1, step)          # records advanced per tick (playback pace)
        self.proc = proc
        self.pos = 0
        self.buf = []                     # every record seen, in order
        self.idx = 0                      # playback cursor -> we replay from gen 1, not the latest
        self.t0 = time.perf_counter()
        self.last_gen = 0

    def _read_new(self):
        if not os.path.exists(self.stream):
            return []
        out = []
        with open(self.stream, "r") as f:
            f.seek(self.pos)
            for line in f:
                if line.endswith("\n"):
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass            # half-written line -> skip, retry next tick
            self.pos = f.tell()
        return out

    def _update(self, _frame):
        self.buf.extend(self._read_new())     # ingest any new records (stream may still be growing)
        if not self.buf:
            return                            # nothing written yet -> wait
        # Advance the playback cursor a few records per tick so we WATCH the search
        # progress from the first generation, instead of snapping to the latest frame.
        self.idx = min(self.idx + self.step, len(self.buf) - 1)
        rec = self.buf[self.idx]
        if "tour" in rec:
            self.canvas.draw_route(np.asarray(rec["tour"], dtype=int))
        hist = [r["best_len"] for r in self.buf[:self.idx + 1]]
        self.canvas.draw_conv({"global best": hist})
        caught_up = self.idx >= len(self.buf) - 1
        done = caught_up and self.buf[-1].get("done", False)
        extra = "| DONE" if done else ("| running..." if caught_up else "| replaying search...")
        self.canvas.set_title(rec.get("gen", self.idx), rec["best_len"],
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
    stream = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False).name
    cmd = ["mpirun", "--oversubscribe", "-np", str(args.islands), binary, args.cities,
           "--gens", str(args.gens), "--pop", str(args.pop),
           "--sync", str(args.sync), "--migrants", str(args.migrants),
           "--twoopt", str(args.twoopt), "--seed", str(args.seed), "--live", stream]
    print("Launching:", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mode = f"{args.islands} islands, " + (
        f"sync every {args.sync} gens" if args.sync else "NO sharing")
    tailer = StreamTailer(stream, coords, title_mode="run/C++", interval=args.interval,
                          step=args.step, proc=proc)
    print(f"Streaming from {stream}  (close the window to stop)")
    tailer.run(save=args.save)


# --------------------------------------------------------------------------- #
#  TAIL: follow the stream file written by a real cluster run
# --------------------------------------------------------------------------- #
def cmd_tail(args):
    coords = read_cities(args.cities)
    tailer = StreamTailer(args.stream, coords, title_mode="tail/MPI",
                          interval=args.interval, step=args.step)
    print(f"Tailing: {args.stream}  (Ctrl+C to quit)")
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
    ax.set_xlim(0, G)
    # Zoom the y-axis to the convergence band (near the optimum) so the island spread and the
    # per-sync jumps are visible. The long descent from the random start enters from the top.
    bot = float(gbest.min())
    top = bot * args.zoom
    ax.set_ylim(bot - 0.04 * (top - bot), top)
    ax.legend(loc="upper right", fontsize=8, ncol=2)

    # Skip the long descent that happens above the zoom band so the animation is lively.
    start = int(np.argmax(gbest <= top)) if bool((gbest <= top).any()) else 0
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

    t = sub.add_parser("tail", help="follow the stream file of a real MPI run")
    t.add_argument("stream", help="JSONL file written by tsp_island --live")
    t.add_argument("cities")
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
