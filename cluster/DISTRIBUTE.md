# One-time cluster setup — 4 nodes over Tailscale

Wires all machines into a working MPI cluster. **One-time** — afterwards a run is just:
power on → `tailscale up` → `bash cluster/run_cluster.sh cluster/hosts.cur 4 <cmd>` from node1.

> Project path MUST be identical on every node: `~/parallel-tsp`.
> **Every node must run OpenMPI 5.0.9** (launch layer PMIx must match, not just "5.0.x").

Tailscale IPs (read fresh — they change on re-login):

| Node  | Member  | Tailscale name | IP              | ssh user |
|-------|---------|----------------|-----------------|----------|
| node1 | Leader  | node-bao       | 100.112.94.39   | bao      |
| node2 | duc     | node-duck      | 100.97.106.69   | duc      |
| node3 | tin     | mac-of-nituv   | 100.114.226.96  | tinvu    |
| node4 | khainx  | node-khainx    | 100.124.102.116 | khainx   |

---

## 0. Prereqs (every node)
- **Tailscale up with a real tunnel** — `tailscale status` must show the others AND they
  must be able to reach YOU. On WSL this needs systemd (see TEAM guide Part A); a
  `--tun=userspace-networking` fallback lets you reach out but **blocks inbound**, which
  breaks MPI (node1 must ssh INTO you). Verify inbound works: from node1
  `tailscale ping <your-ip>` gets a reply.
- `sshd` running: `sudo systemctl enable --now ssh` (macOS: System Settings → General →
  Sharing → **Remote Login** ON).
- Firewall not blocking the tailnet: `sudo ufw allow in on tailscale0` (or `ufw disable` on lab).
- OpenMPI 5.0.9 installed.

---

## 1. Clone the project (every node, same path)

```bash
git clone -b bao-dev https://github.com/Duckduck-05/Parallel_project.git ~/parallel-tsp
```

---

## 2. /etc/hosts  (every node, on their OWN machine)

Map node names → Tailscale IPs. Copy the ready block from the repo:

```bash
grep -E '^[0-9].*node[0-9]' ~/parallel-tsp/cluster/hosts.tailscale | sudo tee -a /etc/hosts
getent hosts node1 node2 node3 node4   # all four must resolve
```

---

## 3. authorized_keys  (every node — THIS is "Part 2")

Every node must trust all members' keys so `mpirun` can SSH between machines.
Append the shared key list from the repo into your own `~/.ssh/authorized_keys`:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
grep '^ssh-' ~/parallel-tsp/cluster/authorized_keys >> ~/.ssh/authorized_keys
sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys   # dedupe
chmod 600 ~/.ssh/authorized_keys
```

`cluster/authorized_keys` holds all members' public keys (node1–node4). This is what lets
node1 log into node2/3/4 without a password.

---

## 4. Python deps  (every node — numpy + mpi4py)

`tsp_island.py` needs `numpy` + `mpi4py`. **mpi4py must be built against THIS node's
OpenMPI 5.0.9** (a plain `pip install mpi4py`, or apt's, may link the wrong MPI):

```bash
python3 -m pip install --user --break-system-packages numpy
MPICC=$(command -v mpicc) python3 -m pip install --user --break-system-packages --no-binary mpi4py mpi4py
python3 -c "import numpy, mpi4py; print(numpy.__version__, mpi4py.__version__)"
```

> Ensure `python3` and `mpicc` here are the **5.0.9** ones. On macOS that means brew
> (`/opt/homebrew/bin`) — put it first on PATH (e.g. add to `~/.zshenv`).

---

## 5. Verify from node1

Each must print the node's hostname with **no password prompt**:

```bash
ssh node2 hostname
ssh node3 hostname
ssh node4 hostname
```

Timeout → that node isn't reachable inbound (step 0). Password prompt → step 3 not done
on that node. Different usernames per node are handled by node1's `~/.ssh/config`.

---

## 6. Run

From node1, use the launcher (it sets the 5.0.9 paths + remote `cd` + daemon path):

```bash
bash cluster/run_cluster.sh cluster/hosts.cur 4 hostname            # smoke test
bash cluster/run_cluster.sh cluster/hosts.cur 4 \
    python3 python/tsp_island.py data/cities_50.txt --gens 500 --migrate 20
```

Fewer nodes online? Edit `cluster/hosts.cur` (comment the offline ones) and use that `-np`.

---

## Platform notes / gotchas
- **OpenMPI must be 5.0.9 everywhere.** node1 was apt 5.0.10 → rebuilt 5.0.9 from source
  into `/opt/openmpi-5.0.9` (mismatched build = PMIx "version mismatch", won't launch).
- **prted path**: `run_cluster.sh` passes `--prte_launch_agent /opt/openmpi-5.0.9/bin/prted`.
  Linux source builds live there. **macOS (brew) is at `/opt/homebrew/bin/prted`** — make
  the path resolve on the mac once: `sudo mkdir -p /opt/openmpi-5.0.9/bin && sudo ln -sf
  /opt/homebrew/bin/prted /opt/openmpi-5.0.9/bin/prted`.
- Linux non-interactive ssh does **not** read `~/.bashrc`; macOS zsh **does** read
  `~/.zshenv` — that's why the launch agent uses an absolute path instead of PATH.
- Usernames differ per machine; node1's `~/.ssh/config` maps `Host nodeN → User <name>`.
