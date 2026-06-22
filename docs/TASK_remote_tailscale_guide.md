# Remote Cluster over Tailscale — OpenMPI on 3–4 PCs in Different Locations

This guide replaces the "3 PCs on the same WiFi" requirement (Tasks 2–4) with a
**Tailscale overlay VPN** so the machines can sit anywhere — different houses,
different WiFi, behind NAT — and still behave like one LAN for MPI.

> **Why it works:** MPI needs only three things from the network: every node is
> reachable by a stable IP, passwordless SSH between nodes, and the project code at
> the **same path** on every node. Tailscale gives each PC a fixed `100.x.y.z` IP that
> works through NAT, so nothing about MPI itself changes — you just use Tailscale IPs
> instead of LAN IPs.

**Trade-off:** WAN latency is higher than LAN, so raw `speedup` numbers will be noisier.
Fine for this project — migration happens only every `--migrate` generations and sends
tiny messages. If you need the cleanest speedup graph, use cloud VMs in one region instead.

Works on Linux, Windows (WSL2), and macOS. Steps below assume **Ubuntu** on each node
(matching the rest of the project). Pick one machine as `node1` (the launcher).

---

## 0. Prerequisites (each PC)

```bash
# OpenMPI + build tools + python deps (same as cluster/01_install.sh)
bash cluster/01_install.sh
```

All nodes must run the **same OpenMPI major version**. Check with:

```bash
mpirun --version
```

If versions differ, MPI will fail to launch across nodes. Reinstall the matching version.

---

## 1. Install Tailscale (each PC)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

`tailscale up` prints a login URL. Open it in a browser and sign in with the **same
account** on all 3–4 PCs. After login, each node joins your private "tailnet".

Find each node's Tailscale IP:

```bash
tailscale ip -4        # e.g. 100.101.102.103
```

Verify connectivity from `node1` to the others (use their Tailscale IPs):

```bash
ping 100.x.x.x         # node2 Tailscale IP
ping 100.y.y.y         # node3 Tailscale IP
```

> **Tip — MagicDNS:** In the Tailscale admin console (Settings → DNS) enable
> **MagicDNS**. Then each machine is reachable by its device name (e.g. `ping node2`)
> instead of the numeric IP. Cleaner, but the numeric IPs always work.

---

## 2. Map names to Tailscale IPs (each PC)

So `ssh node2` and the hostfile resolve correctly on every machine. Edit `/etc/hosts`
on **all** nodes (skip this section if you enabled MagicDNS):

```bash
sudo nano /etc/hosts
```

Add the same block to every node (use YOUR Tailscale IPs):

```
100.101.102.103   node1
100.104.105.106   node2
100.107.108.109   node3
# 100.110.111.112 node4   # if using a 4th PC
```

Test from each node:

```bash
ping node1 && ping node2 && ping node3
```

---

## 3. Passwordless SSH (each PC)

Same as the original Task 3 — works unchanged over Tailscale. Run on **every** node:

```bash
cd cluster
bash 02_ssh_setup.sh
```

This creates an SSH key (no passphrase, so MPI can log in unattended) and copies it to
all nodes listed in the script's `NODES=(node1 node2 node3)` array.

> If you use a **4th PC** or different node names, edit the `NODES=(...)` array in
> `cluster/02_ssh_setup.sh` first.

Verify — each line must print the node name with **no password prompt**:

```bash
ssh node2 hostname
ssh node3 hostname
```

> **Firewall note:** Tailscale tunnels SSH traffic, so a home router blocking inbound
> port 22 does **not** matter — connections ride the tailnet. If SSH still hangs, make
> sure `sshd` is running (`sudo systemctl enable --now ssh`) and Tailscale is up on both
> ends (`tailscale status`).

---

## 4. Hostfile + sync code

The hostfile is identical to the LAN version — it references node names, which now
resolve to Tailscale IPs. `cluster/hosts`:

```
node1 slots=2
node2 slots=2
node3 slots=2
# node4 slots=2
```

- `slots=N` = max processes per node. Set to that machine's core count (`nproc`).

Put the project at `~/parallel-tsp` on **node1**, then sync to the others:

```bash
cd ~/parallel-tsp/cluster
bash 03_sync_code.sh
```

The path **must be identical** on every node (`~/parallel-tsp`), or `mpirun` won't find
the program on remote machines. Re-run `03_sync_code.sh` after every code change.

> rsync runs over SSH, which runs over Tailscale — no extra config needed.

---

## 5. DEMO — prove the remote cluster works

From `node1`, in `cluster/`:

```bash
# Print all node names — confirms MPI reaches every machine:
mpirun --hostfile hosts -np 3 hostname

# Run the bundled hello program across the cluster:
mpicc hello.c -o hello
mpirun --hostfile hosts -np 6 ./hello
```

Seeing `node1`, `node2`, `node3` (and `node4`) in the output = **remote cluster works**.

Run the actual project across the tailnet:

```bash
cd ~/parallel-tsp
mpirun --hostfile cluster/hosts -np 3 \
    python3 python/tsp_island.py data/cities_50.txt --gens 500 --migrate 20
```

---

## 6. Benchmark over the remote cluster

Same as Task 9, just point it at the hostfile:

```bash
cd python
python3 benchmark.py ../data/cities_50.txt --procs 1 2 3 --total 240 --gens 400 \
    --hostfile ../cluster/hosts
```

Expect lower/noisier speedup than LAN due to WAN latency — explain this in the report
(communication cost rises → Amdahl's serial fraction effectively grows). That comparison
is itself a useful result to discuss.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ping node2` fails | Tailscale down on a node — run `sudo tailscale up`, check `tailscale status` |
| MPI hangs on multi-node launch | SSH still prompts for password (redo Step 3), or OpenMPI versions differ |
| `mpirun` "file not found" on remote | Project path differs between nodes — must be `~/parallel-tsp` everywhere |
| Very slow / stalls mid-run | WAN latency or a node dropped off the tailnet (`tailscale status`); reduce migration frequency (`--migrate 50`) |
| `command not found: python3` on a node | That node skipped `01_install.sh` — run it there |
| Works on LAN, not over Tailscale | Using LAN IPs in `/etc/hosts`; replace with `tailscale ip -4` values |

---

## When to use cloud VMs instead

If the grader cares about clean, near-linear speedup numbers, spin up 3–4 Ubuntu VMs in
**one cloud region** (Oracle Cloud free tier = 4 ARM VMs free) — they share a low-latency
private subnet, so Steps 3–6 apply unchanged with the provider's private IPs and no
Tailscale needed. Use Tailscale when the requirement is specifically "real, physically
separate PCs."
