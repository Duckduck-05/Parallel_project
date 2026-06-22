# Team Setup — WSL + OpenMPI + Tailscale (send this to teammates)

Goal: get your machine onto our shared Tailscale network so all our PCs act like one LAN,
then run the MPI cluster across them — no need to be in the same room or WiFi.

You need: Windows 10/11 with **WSL2 + Ubuntu**. (Native Ubuntu or Mac? Skip Part A,
the rest is the same — just no `wsl.conf` / `wsl --shutdown` step.)

Time: ~15 minutes. Run every command inside your **Ubuntu (WSL) terminal** unless noted.

---

## Part A — Enable systemd in WSL (one time)

Tailscale's background service needs systemd.

1. Open Ubuntu (WSL). Edit the WSL config:
   ```bash
   sudo nano /etc/wsl.conf
   ```
2. Make sure it contains:
   ```ini
   [boot]
   systemd=true
   ```
   Save: `Ctrl+O`, `Enter`, then `Ctrl+X`.
3. From **Windows PowerShell or CMD** (not WSL), restart WSL:
   ```powershell
   wsl --shutdown
   ```
4. Reopen Ubuntu and confirm:
   ```bash
   systemctl is-system-running
   ```
   `running` or `degraded` are both fine.

---

## Part B — Install OpenMPI + SSH server

```bash
sudo apt update
sudo apt install -y openmpi-bin libopenmpi-dev openssh-server python3-pip git
sudo systemctl enable --now ssh
```

Check it worked:
```bash
mpirun --oversubscribe -np 2 hostname     # should print your hostname twice
systemctl is-active ssh                    # should print: active
```

> **Important — OpenMPI version must match across the team.** Run `dpkg -l | grep openmpi-bin`
> and tell the group your version. If they differ, MPI won't launch across machines.

---

## Part C — Install Tailscale and join our network

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --hostname=node-<your-name>
```

Replace `<your-name>` (e.g. `--hostname=node-minh`).

This prints a login URL like `https://login.tailscale.com/a/xxxxxxxx`.
Open it in a browser and **log in with your own Google account**, then **accept the
invite** from Bao's tailnet.

> You'll get an invite email/link from Bao first. Accept it so your account joins **our**
> tailnet (not a new empty one). Don't create your own separate network.

Confirm you're connected:
```bash
tailscale ip -4        # your address, e.g. 100.x.x.x
tailscale status       # you should see node-bao and other teammates listed
```

---

## Part D — Generate your SSH key

The cluster needs passwordless SSH between machines.

```bash
[ -f ~/.ssh/id_rsa ] || ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub
```

---

## Part E — Send Bao these 3 things

Paste into the group chat:

1. **Your Tailscale IP** — output of `tailscale ip -4`
2. **Your node name** — e.g. `node-minh`
3. **Your SSH public key** — the full `ssh-rsa AAAA... your@host` line from Part D

Bao collects everyone's, then sends back the shared `/etc/hosts` block and `authorized_keys`
so all machines can SSH to each other. After that we run the cluster together.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `tailscale up` says daemon not running | systemd off — redo Part A, then `sudo systemctl start tailscaled` |
| Still fails | Userspace fallback: `sudo tailscaled --tun=userspace-networking --state=/var/lib/tailscale/tailscaled.state &` then `sudo tailscale up --hostname=node-<name>` |
| `tailscale status` doesn't show teammates | You logged into your own tailnet — accept Bao's invite, or all use the same account |
| `mpirun` not found | Part B didn't finish — rerun the `apt install` line |
| Can't ping a teammate's `100.x` IP | Their Tailscale is down (`tailscale status` on their side) |
| WSL: services don't persist after closing terminal | Keep one WSL window open during the run, or set systemd (Part A) so services auto-start |

---

### Quick reference — what each tool does
- **WSL2** — runs Ubuntu inside Windows.
- **OpenMPI** — runs our program across multiple machines (`mpirun`).
- **Tailscale** — private VPN; gives every PC a stable `100.x` IP that works across
  different networks, so MPI treats remote PCs like they're on one LAN.
- **SSH keys** — let MPI log into other nodes without typing a password.
