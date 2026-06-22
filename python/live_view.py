#!/usr/bin/env python3
"""live_view.py - Trực quan hóa THỜI GIAN THỰC (real-time) cho Island-GA giải TSP.

Hai chế độ:

  run  - Chạy GA nhiều đảo NGAY TRONG TIẾN TRÌNH NÀY (không cần MPI) và vẽ trực tiếp
         lộ trình tốt nhất + đồ thị hội tụ khi GA tiến hóa từng thế hệ.
         Phù hợp để demo trên 1 máy / chiếu slide.

           python3 live_view.py run ../data/cities_30.txt --islands 4 --gens 400 --migrate 20

  tail - "Bám đuôi" file luồng JSONL do bản MPI thật (tsp_island.py --live stream.jsonl)
         ghi ra, vẽ trực tiếp tiến trình của LẦN CHẠY PHÂN TÁN THẬT trên cụm.

           # cua so 1 (tren rank 0 / may chu):
           mpirun -np 4 python3 tsp_island.py ../data/cities_30.txt --gens 400 \
                  --migrate 20 --live ../results/stream.jsonl
           # cua so 2:
           python3 live_view.py tail ../results/stream.jsonl ../data/cities_30.txt

Bố cục cửa sổ (cả 2 chế độ):
  - Trái : lộ trình (route) tốt nhất hiện tại, vẽ lại mỗi thế hệ, ô vuông đỏ = điểm xuất phát.
  - Phải : đồ thị hội tụ (độ dài tour tốt nhất theo thế hệ) lớn dần theo thời gian.
  - Tiêu đề: thế hệ hiện tại, độ dài tốt nhất, thời gian trôi qua, số đảo, chế độ di cư.

Yêu cầu: matplotlib + numpy (KHÔNG cần mpi4py cho chế độ 'run'/'tail').
"""
import argparse
import json
import os
import time

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

import ga_core as ga

try:
    import local_search as ls
except Exception:                     # local_search là tùy chọn (chỉ cần khi --twoopt)
    ls = None


# --------------------------------------------------------------------------- #
#  Lõi mô phỏng nhiều đảo NGAY TRONG TIẾN TRÌNH (cho chế độ 'run')
#  Tái dùng đúng các toán tử trong ga_core.py để khớp với bản MPI thật.
# --------------------------------------------------------------------------- #
class IslandGA:
    """Chạy `islands` đảo GA song song (tuần tự hóa từng thế hệ) + di cư vòng ring.

    Mục đích: cho trực quan hóa thấy ĐÚNG hành vi của tsp_island.py nhưng trong 1 tiến
    trình duy nhất nên animation tới được mọi đảo mà không cần MPI.
    """

    def __init__(self, coords, n_islands=4, pop=200, migrate=20,
                 seed=42, twoopt=0, tournament_k=5, mutation_rate=0.3):
        self.coords = coords
        self.D = ga.distance_matrix(coords)
        self.n = len(coords)
        self.n_islands = n_islands
        self.pop_size = pop
        self.migrate = migrate
        self.twoopt = twoopt
        self.k = tournament_k
        self.mut = mutation_rate
        self.gen = 0
        self.t0 = time.perf_counter()

        # mỗi đảo seed khác nhau -> khám phá vùng nghiệm khác nhau (như bản MPI)
        self.islands = []
        for r in range(n_islands):
            rng = np.random.default_rng(seed + r * 1000)
            pop_r = [ga.random_tour(self.n, rng) for _ in range(pop)]
            lens_r = [ga.tour_length(t, self.D) for t in pop_r]
            self.islands.append({"rng": rng, "pop": pop_r, "lengths": lens_r})

        # lịch sử độ dài tốt nhất mỗi đảo + toàn cục (để vẽ đồ thị hội tụ)
        self.history = [[] for _ in range(n_islands)]
        self.global_history = []
        self.just_migrated = False

    def _step_island(self, isl):
        """Một thế hệ tiến hóa cho 1 đảo (giống vòng lặp trong tsp_island.py)."""
        pop, lengths, rng = isl["pop"], isl["lengths"], isl["rng"]
        order = np.argsort(lengths)
        pop = [pop[i] for i in order]
        lengths = [lengths[i] for i in order]
        new_pop = pop[:1]                            # giữ tinh hoa (elitism)
        while len(new_pop) < self.pop_size:
            p1 = ga.tournament_select(pop, lengths, self.k, rng)
            p2 = ga.tournament_select(pop, lengths, self.k, rng)
            child = ga.order_crossover(p1, p2, rng)
            ga.mutate(child, self.mut, rng)
            new_pop.append(child)
        lengths = [ga.tour_length(t, self.D) for t in new_pop]

        # Memetic: đánh bóng cá thể tốt nhất bằng 2-opt (tùy chọn)
        if self.twoopt > 0 and ls is not None and (self.gen + 1) % self.twoopt == 0:
            bi = int(np.argmin(lengths))
            polished = ls.polish(new_pop[bi], self.D)
            new_pop[bi] = polished
            lengths[bi] = ga.tour_length(polished, self.D)

        isl["pop"], isl["lengths"] = new_pop, lengths

    def step(self):
        """Tiến 1 thế hệ cho TẤT CẢ các đảo, rồi di cư nếu tới chu kỳ."""
        for isl in self.islands:
            self._step_island(isl)

        # --- DI CƯ vòng ring: đảo r gửi cá thể tốt nhất sang đảo (r+1) ---
        self.just_migrated = False
        if self.migrate > 0 and self.n_islands > 1 and (self.gen + 1) % self.migrate == 0:
            best_tours = [isl["pop"][int(np.argmin(isl["lengths"]))].copy()
                          for isl in self.islands]
            for r, isl in enumerate(self.islands):
                src = (r - 1) % self.n_islands       # nhận từ hàng xóm trái
                incoming = best_tours[src]
                inc_len = ga.tour_length(incoming, self.D)
                worst = int(np.argmax(isl["lengths"]))
                if inc_len < isl["lengths"][worst]:   # chỉ nhận nếu tốt hơn cá thể tệ nhất
                    isl["pop"][worst] = incoming
                    isl["lengths"][worst] = inc_len
            self.just_migrated = True

        # ghi nhận lịch sử hội tụ
        for r, isl in enumerate(self.islands):
            self.history[r].append(min(isl["lengths"]))
        self.global_history.append(min(h[-1] for h in self.history))
        self.gen += 1

    def best(self):
        """Trả về (tour tốt nhất toàn cục, độ dài, chỉ số đảo thắng)."""
        bi = int(np.argmin([min(isl["lengths"]) for isl in self.islands]))
        isl = self.islands[bi]
        j = int(np.argmin(isl["lengths"]))
        return isl["pop"][j], isl["lengths"][j], bi


# --------------------------------------------------------------------------- #
#  Khung vẽ chung: trái = route, phải = đồ thị hội tụ
# --------------------------------------------------------------------------- #
class LiveCanvas:
    def __init__(self, coords, title_mode="run"):
        self.coords = coords
        self.title_mode = title_mode
        self.fig, (self.ax_route, self.ax_conv) = plt.subplots(
            1, 2, figsize=(13, 6), gridspec_kw={"width_ratios": [1, 1]})
        self.fig.canvas.manager.set_window_title("TSP Island-GA - Real-time")

        # cố định khung tọa độ route để không nhảy nhót mỗi khung hình
        pad = 0.05 * (coords.max(0) - coords.min(0)).max()
        self.ax_route.set_xlim(coords[:, 0].min() - pad, coords[:, 0].max() + pad)
        self.ax_route.set_ylim(coords[:, 1].min() - pad, coords[:, 1].max() + pad)
        self.ax_route.set_aspect("equal")
        self.ax_route.set_xlabel("x"); self.ax_route.set_ylabel("y")
        self.ax_conv.set_xlabel("The he (generation)")
        self.ax_conv.set_ylabel("Do dai tour tot nhat")
        self.ax_conv.grid(alpha=0.3)

        # các artist tái dùng (cập nhật dữ liệu thay vì vẽ lại từ đầu)
        self.cities_sc = self.ax_route.scatter(coords[:, 0], coords[:, 1],
                                                c="#1f77b4", s=18, zorder=3)
        (self.route_ln,) = self.ax_route.plot([], [], "-", lw=1.3,
                                              color="#ff7f0e", zorder=2)
        (self.start_mk,) = self.ax_route.plot([], [], "rs", ms=11,
                                              label="diem xuat phat", zorder=4)
        self.ax_route.legend(loc="upper right", fontsize=8)
        self.conv_lines = {}          # label -> Line2D
        self._mig_marks = []

    def draw_route(self, tour):
        loop = np.append(tour, tour[0])
        self.route_ln.set_data(self.coords[loop, 0], self.coords[loop, 1])
        self.start_mk.set_data([self.coords[tour[0], 0]], [self.coords[tour[0], 1]])

    def draw_conv(self, series_dict):
        """series_dict: {label: list_of_values}. Tự tạo/ cập nhật từng đường."""
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

    def flash_migration(self, gen):
        """Vạch dọc mờ trên đồ thị hội tụ đánh dấu thời điểm DI CƯ."""
        self._mig_marks.append(
            self.ax_conv.axvline(gen, color="green", lw=0.8, alpha=0.25, zorder=1))

    def set_title(self, gen, best_len, elapsed, extra=""):
        self.ax_route.set_title(
            f"Lo trinh tot nhat — do dai = {best_len:.1f}", fontsize=11)
        self.fig.suptitle(
            f"[{self.title_mode}] the he {gen}  |  tot nhat = {best_len:.2f}  "
            f"|  {elapsed:.1f}s  {extra}", fontsize=12)


# --------------------------------------------------------------------------- #
#  Chế độ RUN: chạy GA tại chỗ + animate
# --------------------------------------------------------------------------- #
def cmd_run(args):
    coords = ga.read_cities(args.cities)
    sim = IslandGA(coords, n_islands=args.islands, pop=args.pop,
                   migrate=args.migrate, seed=args.seed, twoopt=args.twoopt)
    mode = f"{args.islands} dao, {'di cu moi %d the he' % args.migrate if args.migrate else 'KHONG di cu'}"
    canvas = LiveCanvas(coords, title_mode="run")

    def update(_frame):
        if sim.gen >= args.gens:
            return
        sim.step()
        if sim.just_migrated:
            canvas.flash_migration(sim.gen)
        # cập nhật hình mỗi `every` thế hệ để chạy mượt khi gens lớn
        if sim.gen % args.every and sim.gen < args.gens:
            return
        tour, blen, _ = sim.best()
        canvas.draw_route(tour)
        series = {f"dao {r}": sim.history[r] for r in range(args.islands)}
        series["global best"] = sim.global_history
        canvas.draw_conv(series)
        canvas.set_title(sim.gen, blen, time.perf_counter() - sim.t0, extra="| " + mode)
        if sim.gen >= args.gens and args.save_final:
            canvas.fig.savefig(args.save_final, dpi=130)
            print(f"Da luu khung cuoi -> {args.save_final}")

    # frames = số bước; +5 để khung cuối kịp vẽ
    anim = FuncAnimation(canvas.fig, update, frames=args.gens + 5,
                         interval=args.interval, repeat=False)
    _show_or_save(anim, canvas, args)


# --------------------------------------------------------------------------- #
#  Chế độ TAIL: bám đuôi file JSONL do bản MPI thật ghi ra
# --------------------------------------------------------------------------- #
def cmd_tail(args):
    coords = ga.read_cities(args.cities)
    canvas = LiveCanvas(coords, title_mode="tail/MPI")
    state = {"pos": 0, "hist": [], "t0": time.perf_counter(),
             "done": False, "last_gen": 0}

    def read_new_lines():
        """Đọc các dòng JSONL mới kể từ vị trí offset đã đọc lần trước."""
        if not os.path.exists(args.stream):
            return []
        out = []
        with open(args.stream, "r") as f:
            f.seek(state["pos"])
            for line in f:
                if line.endswith("\n"):
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass            # dòng đang ghi dở -> bỏ qua, đọc lại sau
            state["pos"] = f.tell()
        return out

    def update(_frame):
        recs = read_new_lines()
        if not recs:
            return
        last = None
        for rec in recs:
            state["hist"].append(rec["best_len"])
            state["last_gen"] = rec.get("gen", state["last_gen"])
            if rec.get("done"):
                state["done"] = True
            last = rec
        if last is not None and "tour" in last:
            canvas.draw_route(np.asarray(last["tour"], dtype=int))
        canvas.draw_conv({"global best": state["hist"]})
        extra = "| DA XONG" if state["done"] else "| dang chay..."
        canvas.set_title(state["last_gen"], state["hist"][-1],
                         time.perf_counter() - state["t0"], extra=extra)

    anim = FuncAnimation(canvas.fig, update, interval=args.interval,
                         cache_frame_data=False)
    print(f"Dang bam duoi: {args.stream}  (Ctrl+C de thoat)")
    _show_or_save(anim, canvas, args)


def _show_or_save(anim, canvas, args):
    """Hoặc lưu video (mp4/gif) hoặc hiện cửa sổ tương tác."""
    if getattr(args, "save", None):
        fps = max(1, int(1000 / args.interval))
        print(f"Dang ghi video -> {args.save} ({fps} fps)... co the lau.")
        try:
            anim.save(args.save, fps=fps, dpi=110)
            print(f"Da luu video -> {args.save}")
        except Exception as e:
            print(f"Khong ghi duoc video ({e}). Can ffmpeg (mp4) hoac pillow (gif).")
        return
    plt.tight_layout()
    plt.show()


def main():
    ap = argparse.ArgumentParser(description="Truc quan hoa real-time Island-GA cho TSP")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="chay GA tai cho + animate (khong can MPI)")
    r.add_argument("cities")
    r.add_argument("--islands", type=int, default=4)
    r.add_argument("--gens", type=int, default=400)
    r.add_argument("--pop", type=int, default=200)
    r.add_argument("--migrate", type=int, default=20, help="0 = khong di cu")
    r.add_argument("--twoopt", type=int, default=0, help="chu ky 2-opt (Memetic); 0=tat")
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--every", type=int, default=1, help="ve lai moi N the he (lon hon = muot hon)")
    r.add_argument("--interval", type=int, default=30, help="ms giua cac khung hinh")
    r.add_argument("--save", default=None, help="luu video mp4/gif thay vi hien cua so")
    r.add_argument("--save-final", default=None, help="luu PNG khung cuoi cung")
    r.set_defaults(func=cmd_run)

    t = sub.add_parser("tail", help="bam duoi file luong cua ban MPI that")
    t.add_argument("stream", help="file JSONL do tsp_island.py --live ghi ra")
    t.add_argument("cities")
    t.add_argument("--interval", type=int, default=200, help="ms giua cac lan doc file")
    t.add_argument("--save", default=None, help="luu video (it dung o che do tail)")
    t.set_defaults(func=cmd_tail)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
