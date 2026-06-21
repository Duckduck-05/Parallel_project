# Cluster members (Tailscale)

Leader collects each teammate's 3 things (see `docs/TEAM_wsl_tailscale_setup.md` Part E),
records them here, then regenerates `hosts.tailscale` + `authorized_keys` and distributes.

| Node  | Member    | Tailscale name | Tailscale IP   | OpenMPI | SSH key comment    | Status |
|-------|-----------|----------------|----------------|---------|--------------------|--------|
| node1 | Leader    | node-bao       | 100.112.94.39  | 5.0.10  | baolo@DESKTOP-9PH6P60 | READY  |
| node2 | Member 2  | node-duck      | 100.97.106.69  | 5.0.9   | chuanhduc09@gmail.com | READY  |
| node3 | Member 3  | mac-of-nituv   | 100.114.226.96 | 5.0.9   | Tinbgbg05@gmail.com| READY  |
| node4 | Member 4  | node-khainx    | 100.124.102.116| 5.0.9   | khainx@LAPTOP-B2AUBVCH | READY  |

> OpenMPI must match across all nodes. Member 3 + Member 4 = 5.0.9 (match). Confirm
> node1/node2 also 5.0.9 before launching multi-node.
