# Kuruka RVR L2 Bridge

A Layer 2 network bridge for beyond-visual-line-of-sight (BVLOS) control of remotely piloted aircraft over Starlink satellite networks.

## Overview

This tool creates a transparent Layer 2 bridge between a Ground Control Station (GCS) and aircraft over Tailscale mesh VPN. The bridge enables existing aircraft systems to communicate without modification, supporting full 1500-byte Ethernet MTU for compatibility with cameras and other devices.

### Key Capabilities

- **ISR Camera Control** - Real-time manual control of surveillance cameras with live video streaming
- **Flight Control** - MAVLink and other protocol support for aircraft command and control
- **Drone Relay** - FPV video relay from deployed Group 1 surveillance drones through mothership aircraft
- **Zero Modification** - Transparent integration with existing aircraft systems

### Operational Advantages

| Feature | Benefit |
|---------|---------|
| Reduced RF Signature | No ground-based radio transmission required |
| GPS-Independent Navigation | LEO satellite timing signals provide alternative positioning |
| EW Resistance | Starlink's frequency-hopping spread spectrum resists jamming |
| Global Range | Operate beyond visual line of sight anywhere with Starlink coverage |

## Architecture

```
┌─────────────────┐                                    ┌─────────────────┐
│   GCS Router    │         Starlink Network           │ Aircraft Router │
│   (OpenWRT)     │                                    │   (OpenWRT)     │
│                 │                                    │                 │
│  ┌───────────┐  │                                    │  ┌───────────┐  │
│  │  br-lan   │  │                                    │  │  br-lan   │  │
│  │  bridge   │  │                                    │  │  bridge   │  │
│  └─────┬─────┘  │                                    │  └─────┬─────┘  │
│        │        │                                    │        │        │
│  ┌─────┴─────┐  │                                    │  ┌─────┴─────┐  │
│  │ l2bridge  │  │  Tinc VPN (Layer 2 switch mode)    │  │ l2bridge  │  │
│  │  (tinc)   │◄─┼────────────────────────────────────┼─►│  (tinc)   │  │
│  └─────┬─────┘  │                                    │  └─────┬─────┘  │
│        │        │                                    │        │        │
│  ┌─────┴─────┐  │  KCP (reliable UDP transport)      │  ┌─────┴─────┐  │
│  │  kcptun   │◄─┼────────────────────────────────────┼─►│  kcptun   │  │
│  │  server   │  │                                    │  │  client   │  │
│  └─────┬─────┘  │                                    │  └─────┬─────┘  │
│        │        │                                    │        │        │
│  ┌─────┴─────┐  │  Tailscale (WireGuard mesh VPN)    │  ┌─────┴─────┐  │
│  │ Tailscale │◄─┼────────────────────────────────────┼─►│ Tailscale │  │
│  └───────────┘  │                                    │  └───────────┘  │
└────────┬────────┘                                    └────────┬────────┘
         │                                                      │
    ┌────┴────┐                                            ┌────┴────┐
    │   GCS   │                                            │ Camera  │
    │ Laptop  │                                            │ Payload │
    └─────────┘                                            └─────────┘
```

### Protocol Stack

| Layer | Component | Purpose |
|-------|-----------|---------|
| L2 Switch | tinc | Ethernet frame transport, transparent bridging |
| Reliable Transport | KCPtun | ARQ-based reliable UDP, handles satellite packet loss |
| Secure Mesh | Tailscale | WireGuard encryption, NAT traversal, peer discovery |
| Physical | Starlink | LEO satellite connectivity |

## Requirements

### Hardware

- **GCS Router**: OpenWRT-compatible (tested: GL.iNet GL-BE3600)
- **Aircraft Router**: OpenWRT-compatible (tested: GL.iNet GL-A1300)
- **Starlink**: Terminal with roaming enabled on aircraft

### Software

- OpenWRT 21.02+ (23.05 recommended)
- Tailscale (pre-installed and authenticated)
- tinc 1.1+
- kcptun

## Installation

### 1. Install Tailscale on Both Routers

```bash
# On each router
opkg update
opkg install tailscale
tailscale up --accept-routes
```

Verify both routers appear in your Tailscale admin console and can ping each other.

### 2. Install L2 Bridge Tool

```bash
# Copy to GCS router
scp l2bridge root@<gcs-router>:/usr/bin/l2bridge
ssh root@<gcs-router> "chmod +x /usr/bin/l2bridge"
```

### 3. Run Setup

```bash
# On GCS router - provide aircraft's Tailscale IP
l2bridge setup <aircraft-tailscale-ip>

# Example
l2bridge setup 100.73.192.107
```

Setup automatically:
- Installs tinc and kcptun on both routers
- Generates and exchanges encryption keys
- Configures firewall rules to prevent routing loops
- Enables STP on bridges
- Installs watchdog for automatic recovery
- Starts all services

### 4. Configure Routing (if using different subnets)

If GCS and aircraft use different LAN subnets:

```bash
# On GCS (if aircraft LAN is 172.16.11.0/24)
ip route add 172.16.11.0/24 dev br-lan

# On Aircraft (if GCS LAN is 172.16.10.0/24)
ip route add 172.16.10.0/24 dev br-lan
```

Add to `/etc/rc.local` for persistence.

## Usage

### Commands

```
l2bridge <command> [options]

Setup & Control:
  setup <aircraft_ip>     Full setup of both GCS and Aircraft
  add <aircraft_ip>       Connect to an already-setup aircraft (no reinstall)
  start <aircraft_ip>     Start services on both sides
  stop [aircraft_ip]      Stop services on both sides
  restart <aircraft_ip>   Restart services on both sides
  uninstall [aircraft_ip] Remove all configuration

Monitoring:
  status                  Show local bridge status
  remote <aircraft_ip>    Show aircraft status via SSH
  logs [lines]            Show recent logs (default: 20)
  debug <aircraft_ip>     Full diagnostics on both sides
  config                  Show current configuration

Auto-Recovery:
  monitor [--daemon]      Health check and auto-repair
  watchdog-install        Install cron-based watchdog
  watchdog-remove         Remove watchdog

Web UI:
  webui-install           Install web control panel on port 8081
  webui-remove            Remove web UI
```

### Examples

```bash
# Initial setup (installs packages, creates configs on both sides)
l2bridge setup 100.73.192.107

# Switch to a different aircraft that was previously set up
l2bridge add 100.64.10.52

# Check status
l2bridge status

# View aircraft status
l2bridge remote 100.73.192.107

# Restart after issues
l2bridge restart 100.73.192.107

# View logs
l2bridge logs 50

# Full diagnostics
l2bridge debug 100.73.192.107

# Install web UI for browser-based control
l2bridge webui-install
```

### Setup vs Add

Use **`setup`** for first-time configuration of a new aircraft. It installs packages, creates all config files, init scripts, and starts services on both routers.

Use **`add`** (or `connect`) to switch to a previously configured aircraft. It skips package installation and config file creation, only exchanging tinc keys, updating kcptun IP addresses, and restarting services. This is significantly faster than a full setup.

## Configuration

### Default Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Bridge MTU | 1500 | Standard Ethernet, camera-compatible |
| KCP Segment MTU | 1200 | Fits within Tailscale's 1280 limit |
| KCPtun Port | 4000/UDP | Tunnel endpoint |
| Tinc Port | 655/TCP | VPN control (localhost only) |
| STP | Enabled | Prevents bridge loops |

### KCPtun Tuning

Optimized for low-latency real-time control:

```json
{
    "nodelay": 1,
    "interval": 10,
    "resend": 2,
    "nc": 1,
    "sndwnd": 1024,
    "rcvwnd": 1024,
    "dscp": 46
}
```

### Modifying Settings

Edit configuration section at top of `/usr/bin/l2bridge`:

```bash
KCPTUN_PORT="4000"
BRIDGE_MTU="1500"
KCP_SEGMENT_MTU="1200"
```

Re-run `l2bridge setup <aircraft_ip>` to apply changes.

## Auto-Recovery

### Boot Sequence

Services start with proper dependency ordering:
1. Wait for Tailscale (up to 60s)
2. Start KCPtun (updates config if Tailscale IP changed)
3. Wait for KCPtun (up to 30s)
4. Start Tinc

### Watchdog

The cron-based watchdog runs every minute and monitors:
- Tailscale connectivity
- KCPtun process
- Tincd process
- L2bridge interface
- Tinc peer connections

Recovery actions:

| Issue | Action |
|-------|--------|
| Tailscale down | Wait for recovery, then restart |
| Service crashed | Restart local services |
| No tinc peers | Restart both sides |

### Logs

```bash
# Setup log (comprehensive)
cat /tmp/l2bridge-setup.log

# Watchdog log
cat /tmp/l2bridge-watchdog.log

# Health status
cat /tmp/l2bridge.health

# System logs
l2bridge logs 50
```

## Web UI

The L2 Bridge includes an optional web-based control panel for monitoring and managing aircraft connections from a browser.

### Installation

```bash
# Install web UI (on GCS router)
l2bridge webui-install
```

This installs the control panel on port 8081 and configures the firewall to allow LAN access.

### Accessing the Web UI

After installation, open in Chrome:

```
http://<router-lan-ip>:8081
```

Or via Tailscale:

```
http://<router-tailscale-ip>:8081
```

### Features

| Feature | Description |
|---------|-------------|
| **Status Dashboard** | Real-time GCS and aircraft status with service indicators |
| **Connection Monitor** | Connection state, duration timer, health status |
| **Network Statistics** | Live upload/download rates, packets/sec, and cumulative totals |
| **Tailscale Link Mode** | Shows whether the Tailscale connection is direct peer-to-peer or relayed through DERP |
| **Bridge Controls** | Start, Stop, Restart, Setup, Connect, and Debug buttons |
| **Aircraft Profiles** | Save multiple aircraft with names and optional SSH passwords |
| **Profile Switching** | Switch between aircraft from dropdown selector |
| **Live Logs** | Real-time streaming of l2bridge, tinc, and kcptun logs |

### Aircraft Profile Management

The web UI allows saving aircraft Tailscale IPs with friendly names and optional SSH passwords:

1. Click **Manage** next to the aircraft selector
2. Enter a Profile ID (e.g., `alpha`), Display Name (e.g., `Aircraft Alpha`), and Tailscale IP
3. Optionally enter the aircraft's SSH password for automated first-time setup
4. Click **Add Aircraft**
5. Select the aircraft from the dropdown to make it active

Stored SSH passwords are used automatically during setup so that SSH key installation doesn't require manual password entry. Passwords can be cleared from profiles at any time via the lock icon. Profiles are stored in `/etc/l2bridge/aircraft.json` and persist across reboots.

### Switching Aircraft

To connect to a different aircraft:

1. Select the aircraft from the dropdown in the header
2. The l2bridge configuration is automatically updated
3. Use **Connect** to switch to a previously set up aircraft, or **Setup** for first-time configuration

**Connect** exchanges keys and updates IP addresses without reinstalling packages — equivalent to `l2bridge add <ip>` on the command line.

### Network Statistics

The dashboard displays live network statistics for the l2bridge interface:

- **Upload/Download rates** — real-time bytes per second
- **Packets per second** — inbound and outbound
- **Total transferred** — cumulative bytes and packet counts
- **Errors and drops** — transmission errors and dropped packets

### Tailscale Link Status

The Aircraft Status card shows the Tailscale connection mode:

- **Direct** — peer-to-peer WireGuard connection (lowest latency)
- **Relay** — traffic routed through a DERP relay server (higher latency, shown with relay name)
- **Idle** — no active traffic between peers

### Removing the Web UI

```bash
l2bridge webui-remove
```

This removes web files and uhttpd configuration but preserves aircraft profiles.

## Troubleshooting

### Bridge Connected but No IP Connectivity

**Symptom**: Tinc shows peers connected, but ping fails.

**Check ARP** (Layer 2):
```bash
arping -I br-lan <remote-ip> -c 3
```

If arping works but ping doesn't, it's a **routing issue**:
```bash
# Add route to remote subnet
ip route add <remote-subnet>/24 dev br-lan
```

### STP Port Blocking

**Check port state**:
```bash
cat /sys/class/net/br-lan/brif/l2bridge/state
# 0=disabled, 1=listening, 2=learning, 3=forwarding, 4=blocking
```

State should be `3` (forwarding). If blocking, wait for STP convergence (~45s) or check for loops.

### Services Not Starting on Boot

**Check Tailscale**:
```bash
tailscale status
```

**Check service order**:
```bash
logread | grep -E "kcptun|tinc"
```

**Manual restart**:
```bash
l2bridge restart <aircraft_ip>
```

### High Latency

Typical latency breakdown:
- Starlink base RTT: 40-60ms
- L2 bridge overhead: ~17ms
- Total: 60-80ms typical

If higher:
1. Check Starlink obstructions
2. Check packet loss: `ping -c 100 <aircraft-tailscale-ip>`
3. Verify KCP parameters

### Verifying Bridge Operation

```bash
# Check MACs learned across bridge
brctl showmacs br-lan

# Should see remote MACs with "is local? = no"
# port 4 = l2bridge interface typically
```

## Network Planning

### Same Subnet (Recommended)

For true transparent bridging, use the same subnet on both sides:
- GCS: 192.168.1.1/24
- Aircraft: 192.168.1.2/24

Devices on either LAN will discover each other automatically via broadcast.

### Different Subnets

If using different subnets (e.g., for isolation):
- GCS LAN: 172.16.10.0/24
- Aircraft LAN: 172.16.11.0/24

Requires static routes on both routers (see Installation step 4).

## Performance

### Measured Latency

| Path | Typical RTT |
|------|-------------|
| Tailscale direct | 40-60ms |
| L2 bridge end-to-end | 60-80ms |
| Glass-to-glass video | <100ms |

### Throughput

Limited by Starlink uplink (~20-40 Mbps typical). Bridge adds minimal overhead with compression/encryption disabled (relies on Tailscale's WireGuard).

## Security

- **Tailscale**: WireGuard encryption for all traffic
- **KCPtun**: Encryption disabled (`crypt: none`) to reduce latency; relies on Tailscale
- **Tinc**: Compression disabled for CPU efficiency
- **SSH**: Dropbear ed25519 keys for router-to-router auth
- **Firewall**: Blocks WireGuard traffic from crossing bridge (prevents loops)

## File Locations

### GCS Router

```
/usr/bin/l2bridge              # Main script
/etc/l2bridge.conf             # Saved aircraft IP (legacy)
/etc/l2bridge/aircraft.json    # Aircraft profiles (web UI)
/etc/tinc/l2bridge/            # Tinc configuration
/etc/kcptun/server.json        # KCPtun config
/etc/init.d/kcptun-server      # Init script
/etc/init.d/tinc-l2bridge      # Init script
/etc/l2bridge-watchdog.sh      # Watchdog script
/tmp/l2bridge-setup.log        # Setup log
/tmp/l2bridge.health           # Health status
/tmp/l2bridge-watchdog.log     # Watchdog log

# Web UI (after webui-install)
/www/l2bridge/index.html       # Web interface
/www/l2bridge/cgi-bin/         # API endpoints
```

### Aircraft Router

```
/etc/tinc/l2bridge/            # Tinc configuration
/etc/kcptun/client.json        # KCPtun config
/etc/init.d/kcptun-client      # Init script
/etc/init.d/tinc-l2bridge      # Init script
```

## Tested Hardware

| Device | Role | Notes |
|--------|------|-------|
| GL.iNet GL-BE3600 | GCS | Wi-Fi 7, recommended |
| GL.iNet GL-A1300 | Aircraft | Compact, OpenWRT 21.02 |
| Starlink Standard | Aircraft | Roaming enabled |

## License

MIT License

## Contributing

Issues and pull requests welcome.

## Acknowledgments

- [tinc VPN](https://www.tinc-vpn.org/) - Layer 2/3 mesh VPN
- [KCPtun](https://github.com/xtaci/kcptun) - KCP-based secure tunnel
- [Tailscale](https://tailscale.com/) - WireGuard mesh VPN
