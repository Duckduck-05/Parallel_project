# One-time distribution — node1 + node3 + node4 (member 2 joins later)

Wires the 3 online machines into a working MPI cluster. **One-time** — after this,
future runs just need all nodes powered on + `tailscale up`, then `mpirun`.

Member 2 not joined yet → this uses only node1/node3/node4 (`cluster/hosts.cur`).
Add node2 later (see last section).

> Project path MUST be identical on every node: `~/parallel-tsp`.
> OpenMPI must match: node1=5.0.10, node3=5.0.9, node4=5.0.9 — all 5.0.x ✓.

Current Tailscale IPs:

| Node  | Tailscale name | IP              |
|-------|----------------|-----------------|
| node1 | node-bao       | 100.112.94.39   |
| node3 | mac-of-nituv   | 100.114.226.96  |
| node4 | node-khainx    | 100.124.102.116 |

---

## Prereqs (every node)
- Powered on, `tailscale up`, shows online in `tailscale status`.
- `sshd` running: `sudo systemctl enable --now ssh` (macOS node3: System Settings →
  General → Sharing → **Remote Login** ON).

---

## Part 1 — /etc/hosts  (run on ALL 3 nodes: you, member3, member4)

Each person runs this on their **own** machine. Maps node names → Tailscale IPs.

```bash
sudo tee -a /etc/hosts >/dev/null <<'EOF'
100.112.94.39   node1
100.114.226.96  node3
100.124.102.116 node4
EOF
```

Test: `ping -c1 node1 && ping -c1 node3 && ping -c1 node4`

---

## Part 2 — authorized_keys  (run on ALL 3 nodes)

Each node must trust all 3 keys so `mpirun` can SSH between machines. Paste all 3
public keys into `~/.ssh/authorized_keys`:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cat >> ~/.ssh/authorized_keys <<'EOF'
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC+M1NQFEtVe3wIbTKRxo9hna2aXPcwEklhuPMMNl+Dyy1eWUp1P3D564ynV8z/ERIM+0yIPR9vnDF8j1gEromBAL1Yjn8Fbrfw0o8A4Pd3ei64bDcc8UhUWt/p2637nXYqSp0zFhOttnsLrQKi2OTzQel4pya2ur79qwpgMFfkZn8/UqRxTz4T0oxnhTZdyFrzTTpY9poPHiZIZxKvkJ4MSStTY8OLWHvVODzUNnkOEoMzxzNn3tIXw/qir55Cb6VBJq79AoufZ9wytWPdlNhjs9Xt1AxvhXJAixXHm57S88u5vQ74OaRA2zUTjns7SsQtB0EDegzy+k5vwvdMOJTJCSwkpvq4d/C1X/RpMNfGg03kn+yGrvzzDiEoG4Qe8pmDpbcK5j1KMSXDSeZ/AVUibTr3Go0GC1ks44cHBgmBg1Gq6HSolVl1r/tS/XITj11L962BxcMNNAY/7lkbqrvClVgacViE3w5GTCywUKwDDvMPx+UQIwn+ZHRXD+Ns3BU= baolo@DESKTOP-9PH6P60
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQC0pI5Ooh3p+5izg2p1CZqPE7UYK6yvg3JHs2UvOjLMqNYtDhpDugbOXHLEWQphUdgz2/5p5u1VMvvsOEUWRjohrXYemMkvKrTxBwNl38bR53idH5wj578ActJMTH4mdVThGowIrAA0jl6h23P+ZaQHe2V1OA9humfT184E9IYXAmpevIfT7HZGzWFNg/KyFPSqQbCKotb/my60HjKqqLP0WuUzkX+kZp59tOu2OT9JT/ap4JIo2A8sKe1YBf209qTUvfVp65JyQ7xWXUrzEtWF1eu4vWjcTXCpm4mrDYesxOrbCWqhdT+mAwNyEro0BqHP9iCMCcFPEg1gsKxJv2v0UZZTcuPmbRhuFauQWqGcAWG6nweBpF4AXWo/trtS4tD08Vhy8KWMMQp3oAs+XAdWSroJs+SdWxl/kAX5EK5KP2ang9UvoN1uNVUl0p5xnASzH1CEkUM8nUo4J4c14N/6/H+ZVB1iKasWxZ39XWj3T9yHsrAgxfj6hHMbsLfQTJvKn0V4cmlOLFkDO6cJHZ9AQT0hXKC6fxGdRwT4yY0hGftAZPu2RL+mS/TOnDO/wujNs4tE7Al8qUQaLssT6m4se4n5ml7R5YW0pU+Sqy4caf34AGtn2TiTIPh0FOltdt/CxMUDOKWVBBHGG1zQ/OYMMKxJbY7t6/gaDElrJSCVcQ== Tinbgbg05@gmail.com
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQC7mMF10i8Y48v7zFeHj0XN421VYbomHKaXSbWmnDMFsFxaBjUcJVBaiemTjGE8mtgtJb+6J/Gz9FLHKrePDzx5jUlZPw7xf/xkGHFuMn9ekh7yms0xdwHmr2rkQyWsUDulkV/IrHEmsnLgHdvT4D99gjfTSZfI/ZfguJ0Pj85K4JCKUspjyIplB7raukN5XnagllVsz6Rr5Szj6WJnn1dwXd3YdWuUMiOq2OeZK67/4IntWc2VhwuHYuI3xOL/lude0OcCxw3+1AD1F5EAcX5eFvGh4fbhOfg52DVwycUtaApvV52u2Y4RyfyjSpicWSGlU52YStkwxhtq7t5htWw2/Wz30HzzRpnkwe8wV24+ygqgx/u+lzjCwlf3snBK6sOEpjbXkrIs8snLhtOzB1VOLom28kOFBTXaNOEYTo/GfI3SGTdPs5l0I/IKnQEQAdIYVADdsBUHarly6xloknZXiaPhdWg8ZqxOdfDew8RxXdRV/IgFg8fCK9tYJKFa9yOoM5g82G/FwnXCU85VO6WwkOIb0TyHO5aZFg2CzakeyC3zcnFBEV8NRj9dBqimdcpNRWX3ZWctWCmYY1PZUtuQZHnIA+7qjPp0Sv0IRvmIIVP02hhAJFK7HJ9dhdJMTr0g0LogGb/Z1d0g0S5OqLlEk1PItO56o3ehy4L3dNqN+Q== khainx@LAPTOP-B2AUBVCH
EOF
chmod 600 ~/.ssh/authorized_keys
```

> Shortcut: these 3 keys also live in `cluster/authorized_keys` in the repo. After
> cloning (Part 3), instead run:
> `cat ~/parallel-tsp/cluster/authorized_keys | grep '^ssh-' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys`

---

## Part 3 — code at ~/parallel-tsp  (same path on all 3)

**node3 + node4** — clone once:

```bash
git clone -b bao-dev https://github.com/Duckduck-05/Parallel_project.git ~/parallel-tsp
```

No repo URL? Push from node1 instead (after Parts 1–2 done so SSH works):

```bash
# on node1:
cd ~/parallel-tsp
rsync -az --delete ./ node3:~/parallel-tsp/
rsync -az --delete ./ node4:~/parallel-tsp/
```

Re-run the rsync after every code change to keep nodes in sync
(or use `cluster/03_sync_code.sh` with its NODES list set to `node3 node4`).

---

## Part 4 — verify passwordless SSH  (from node1)

Each line must print the node name with **no password prompt**:

```bash
ssh node3 hostname
ssh node4 hostname
```

Hangs / asks password → Part 2 not applied on that node, or `sshd` off.

---

## Part 5 — DEMO run (from node1, all 3 online)

```bash
cd ~/parallel-tsp
mpirun --hostfile cluster/hosts.cur -np 3 hostname        # prints node1 node3 node4
mpirun --hostfile cluster/hosts.cur -np 3 \
    python3 python/tsp_island.py data/cities_50.txt --gens 500 --migrate 20
```

Seeing all 3 node names = **cluster works**.

---

## When member 2 joins
1. Get their IP/name/key → I add to `cluster/cluster_members.md`, `hosts.tailscale`,
   `cluster/authorized_keys`.
2. Add `node2 slots=2` to `cluster/hosts.cur` (or use `cluster/hosts`).
3. Add their `/etc/hosts` line + key on **all 4** nodes (repeat Parts 1–2 for the new line/key).
4. `mpirun --hostfile cluster/hosts -np 4 ...`
