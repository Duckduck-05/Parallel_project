# Cluster Re-activation Checklist — what to redo to get it running again

The cluster has **persistent** parts (installed once) and **ephemeral** parts that reset on
reboot / `wsl --shutdown` / new login. This lists what to **re-check/redo** each time before
a run, ordered by how often it bites.

Two network modes:
- **LAN** (preferred now): all PCs on `192.168.100.0/24`. No Tailscale needed.
- **Tailscale** (remote): `100.x` overlay. Use only if not on the same LAN.

Cluster (LAN):
| node | user | LAN IP | OS |
|---|---|---|---|
| node1 | bao | 192.168.100.10 | WSL (mirrored) |
| node2 | mpiuser | 192.168.100.71 | native Linux |
| node3 | acer | 192.168.100.198 | WSL (mirrored) |
| node4 | khainx | 192.168.100.99 | WSL (needs mirrored) |

---

## ✅ Persists across reboot (install once — only verify)
- OpenMPI **5.0.9** at `/opt/openmpi-5.0.9` (built from source, system hwloc).
- Repo at `~/parallel-tsp` (just `git pull` for latest).
- SSH keys + `~/.ssh/config` (node1) + each node's `~/.ssh/authorized_keys`.
- MCA configs: `~/.prte`, `~/.openmpi`, `~/.pmix` (`*_if_include`).
- `.wslconfig` mirrored mode (WSL nodes) — persists.
- `/etc/wsl.conf` `generateHosts=false` (node1) — keeps /etc/hosts from being wiped.
- Windows Firewall inbound rule (Hyper-V `DefaultInboundAction=Allow`) — persists.

## 🔁 EPHEMERAL — redo / verify EACH session (most common breakers)

### 1. sshd running on every node (top cause of "Connection refused/timeout")
WSL often doesn't auto-start sshd. On EACH node:
```bash
sudo systemctl start ssh        # or: sudo service ssh start
systemctl is-active ssh         # -> active
```

### 2. WSL mirrored networking actually up (WSL nodes: node1, node3, node4)
After `wsl --shutdown` or reboot, confirm the WSL has its LAN IP (not 172.x NAT):
```bash
hostname -I | tr ' ' '\n' | grep 192.168.100   # must show your .x
```
If only `172.x`: `.wslconfig` → `[wsl2]` / `networkingMode=mirrored`, then (Windows)
`wsl --shutdown`, reopen.

### 3. /etc/hosts has the cluster (only if it got wiped)
node1 has `generateHosts=false` so it survives; other nodes may need re-adding:
```bash
getent hosts node1 node2 node3 node4   # all 4 must resolve to 192.168.100.x
# if missing:
sudo tee -a /etc/hosts >/dev/null <<'EOF'
192.168.100.10   node1
192.168.100.71   node2
192.168.100.198  node3
192.168.100.99   node4
EOF
```

### 4. Python deps present (node1's mpi4py vanished once via apt autoremove)
On each node:
```bash
python3 -c "import mpi4py, numpy" || sudo apt install -y python3-mpi4py python3-numpy
```

### 5. Windows Firewall inbound (WSL nodes) — verify after Windows updates
On each WSL host, **Admin PowerShell**:
```powershell
(Get-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}').DefaultInboundAction  # Allow
# if not Allow:
New-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
```

### 6. (Tailscale mode only) bring the tunnel up
```bash
sudo tailscale up --hostname=node-bao --operator=$USER
tailscale status        # peers online?
```
⚠️ Tailscale IPs **change on re-login** → update `/etc/hosts` + `cluster/cluster_members.md`.
⚠️ macOS over Tailscale **cannot** join MPI (utun is point-to-point, OpenMPI won't use it).

---

## 🚀 Re-activation sequence (do in order)
```bash
# 0) node1: make sure WSL is up + on LAN
hostname -I | grep 192.168.100 && sudo systemctl start ssh

# 1) each member: start sshd, confirm LAN IP (see steps 1-2 above)

# 2) node1: verify ssh to everyone (no password)
for n in node2 node3 node4; do ssh -o BatchMode=yes $n hostname; done

# 3) node1: pull latest + run
cd ~/parallel-tsp && git pull
printf 'node1 slots=1\nnode2 slots=1\nnode3 slots=1\n' > /tmp/h   # online nodes only
bash cluster/run_cluster.sh /tmp/h 3 hostname                     # smoke test
bash cluster/run_cluster.sh /tmp/h 3 python3 python/tsp_island.py data/cities_50.txt --gens 500 --migrate 20
```
If a node's ssh hangs/fails: it's almost always **#1 (sshd)** or **#2 (mirrored)** or **#5
(firewall)** on that node.

---

## Quick per-node "am I ready?" check
```bash
hostname; whoami
hostname -I | tr ' ' '\n' | grep 192.168.100      # on LAN
systemctl is-active ssh                            # active
/opt/openmpi-5.0.9/bin/mpirun --version            # 5.0.9
python3 -c "import mpi4py,numpy;print('deps ok')"
ls ~/parallel-tsp/python/tsp_island.py             # repo
```

## Run on ONE machine only (no cluster — always works)
```bash
bash cluster/run_local.sh 4 data/cities_50.txt --gens 500 --migrate 20
```
