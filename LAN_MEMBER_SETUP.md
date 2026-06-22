# LAN setup — what each member does (so node1 can launch MPI on you)

LAN: `192.168.100.0/24`. Launcher = node1 (bao, 192.168.100.10).
Your job: let node1 SSH into your machine without a password, and (WSL only) let LAN
traffic reach into WSL.

| node | user | IP | OS |
|---|---|---|---|
| node2 | duc  | 192.168.100.71  | native Linux |
| node3 | tin  | 192.168.100.198 | WSL |
| node4 | khai | 192.168.100.99  | WSL |

---

## STEP 1 — (everyone) authorize node1's key + map names
Run in your **Ubuntu / WSL terminal**:

```bash
# make sure ssh server is installed & running
sudo apt install -y openssh-server
sudo systemctl enable --now ssh

# trust node1's key (lets node1 log in without password)
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cat >> ~/.ssh/authorized_keys <<'EOF'
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC+M1NQFEtVe3wIbTKRxo9hna2aXPcwEklhuPMMNl+Dyy1eWUp1P3D564ynV8z/ERIM+0yIPR9vnDF8j1gEromBAL1Yjn8Fbrfw0o8A4Pd3ei64bDcc8UhUWt/p2637nXYqSp0zFhOttnsLrQKi2OTzQel4pya2ur79qwpgMFfkZn8/UqRxTz4T0oxnhTZdyFrzTTpY9poPHiZIZxKvkJ4MSStTY8OLWHvVODzUNnkOEoMzxzNn3tIXw/qir55Cb6VBJq79AoufZ9wytWPdlNhjs9Xt1AxvhXJAixXHm57S88u5vQ74OaRA2zUTjns7SsQtB0EDegzy+k5vwvdMOJTJCSwkpvq4d/C1X/RpMNfGg03kn+yGrvzzDiEoG4Qe8pmDpbcK5j1KMSXDSeZ/AVUibTr3Go0GC1ks44cHBgmBg1Gq6HSolVl1r/tS/XITj11L962BxcMNNAY/7lkbqrvClVgacViE3w5GTCywUKwDDvMPx+UQIwn+ZHRXD+Ns3BU= baolo@DESKTOP-9PH6P60
EOF
chmod 600 ~/.ssh/authorized_keys

# map cluster names to LAN IPs
sudo tee -a /etc/hosts >/dev/null <<'EOF'
192.168.100.10   node1
192.168.100.71   node2
192.168.100.198  node3
192.168.100.99   node4
EOF

# allow ssh through the Linux firewall (if ufw is on)
sudo ufw allow 22/tcp 2>/dev/null || true
```

---

## STEP 2 — (WSL members ONLY: tin & khai) open Windows inbound
node1 currently **cannot even ping you** — Windows blocks LAN traffic into mirrored WSL.
Fix on the **Windows side** (NOT inside WSL):

1. Click Start → type **PowerShell** → right-click **Run as administrator**.
2. Paste:
   ```powershell
   New-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
   ```
3. If that command errors (older Windows), instead allow port 22:
   ```powershell
   New-NetFirewallRule -DisplayName "WSL SSH in" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22
   ```

> Also confirm your WSL is in **mirrored** mode (you already have a `192.168.100.x` IP, so
> it is). If `hostname -I` shows only `172.x`, add to `C:\Users\<you>\.wslconfig`:
> `[wsl2]` / `networkingMode=mirrored`, then `wsl --shutdown` and reopen.

duc (native Linux): skip Step 2.

---

## STEP 3 — confirm you're ready (run in your terminal)
```bash
hostname -I | tr ' ' '\n' | grep 192.168.100      # shows your LAN IP
/opt/openmpi-5.0.9/bin/mpirun --version           # Open MPI 5.0.9
python3 -c "import mpi4py, numpy; print('deps ok')"
ls ~/parallel-tsp/python/tsp_island.py            # repo present
```
If any line fails: OpenMPI/deps/repo not set up — ping the group (it's the earlier
`cluster/DISTRIBUTE.md` setup).

---

## Then tell node1 (bao)
bao tests from node1:
```bash
ssh node2 hostname   # → should print your hostname, NO password
ssh node3 hostname
ssh node4 hostname
```
All three printing a hostname with no password = SSH done → ready to run the cluster:
```bash
bash cluster/run_cluster.sh cluster/hosts.cur 4 hostname
```
