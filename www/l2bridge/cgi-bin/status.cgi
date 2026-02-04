#!/bin/sh
#
# L2Bridge Web UI - Status API
# Returns JSON with GCS and aircraft status
#

echo "Content-Type: application/json"
echo "Cache-Control: no-cache"
echo ""

# Configuration
AIRCRAFT_FILE="/etc/l2bridge/aircraft.json"
STATE_FILE="/etc/l2bridge.conf"
HEALTH_FILE="/tmp/l2bridge.health"
SSH_KEY="/root/.ssh/id_dropbear"
CONNECTED_SINCE_FILE="/tmp/l2bridge.connected"

# Helper: escape string for JSON
json_escape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/	/\\t/g' | tr '\n' ' '
}

# Get GCS Tailscale IP
GCS_TS_IP=$(tailscale ip -4 2>/dev/null | head -1)
GCS_TS_STATUS="disconnected"
if tailscale status >/dev/null 2>&1; then
    GCS_TS_STATUS="connected"
fi

# Check local services
KCPTUN_STATUS="stopped"
pgrep -f kcptun-server >/dev/null 2>&1 && KCPTUN_STATUS="running"

TINCD_STATUS="stopped"
pgrep tincd >/dev/null 2>&1 && TINCD_STATUS="running"

IFACE_STATUS="down"
IFACE_MTU="0"
if ip link show l2bridge >/dev/null 2>&1; then
    IFACE_STATUS="up"
    IFACE_MTU=$(ip link show l2bridge 2>/dev/null | grep -o 'mtu [0-9]*' | cut -d' ' -f2)
fi

# Get Tinc peer count
TINC_PEERS=0
if pgrep tincd >/dev/null 2>&1; then
    TINC_PEERS=$(tinc -n l2bridge dump nodes 2>/dev/null | wc -l)
fi

# Check watchdog status
WATCHDOG_STATUS="inactive"
crontab -l 2>/dev/null | grep -q "l2bridge-watchdog" && WATCHDOG_STATUS="active"

# Read health file
HEALTH_STATUS="unknown"
HEALTH_LAST=""
HEALTH_DETAILS=""
if [ -f "$HEALTH_FILE" ]; then
    . "$HEALTH_FILE"
    HEALTH_STATUS="${STATUS:-unknown}"
    HEALTH_LAST="${LAST_CHECK:-}"
    HEALTH_DETAILS="${DETAILS:-}"
fi

# Get active aircraft from profiles or legacy config
AIRCRAFT_ID=""
AIRCRAFT_NAME=""
AIRCRAFT_IP=""

if [ -f "$AIRCRAFT_FILE" ]; then
    # Use jsonfilter if available, otherwise parse manually
    if command -v jsonfilter >/dev/null 2>&1; then
        AIRCRAFT_ID=$(jsonfilter -i "$AIRCRAFT_FILE" -e '@.active' 2>/dev/null)
        if [ -n "$AIRCRAFT_ID" ]; then
            AIRCRAFT_NAME=$(jsonfilter -i "$AIRCRAFT_FILE" -e "@.profiles[\"$AIRCRAFT_ID\"].name" 2>/dev/null)
            AIRCRAFT_IP=$(jsonfilter -i "$AIRCRAFT_FILE" -e "@.profiles[\"$AIRCRAFT_ID\"].tailscale_ip" 2>/dev/null)
        fi
    fi
fi

# Fallback to legacy config
if [ -z "$AIRCRAFT_IP" ] && [ -f "$STATE_FILE" ]; then
    . "$STATE_FILE"
    AIRCRAFT_IP="${AIRCRAFT_IP:-}"
    AIRCRAFT_NAME="${AIRCRAFT_NAME:-$AIRCRAFT_IP}"
fi

# Check aircraft status
AIRCRAFT_REACHABLE="false"
AIRCRAFT_KCPTUN="unknown"
AIRCRAFT_TINCD="unknown"
AIRCRAFT_IFACE="unknown"

if [ -n "$AIRCRAFT_IP" ]; then
    # Quick ping check (1 second timeout)
    if ping -c 1 -W 1 "$AIRCRAFT_IP" >/dev/null 2>&1; then
        AIRCRAFT_REACHABLE="true"

        # SSH check for detailed status (only if key exists and ping succeeded)
        if [ -f "$SSH_KEY" ]; then
            REMOTE_STATUS=$(timeout 5 dbclient -i "$SSH_KEY" -y root@"$AIRCRAFT_IP" '
                pgrep -f kcptun-client >/dev/null && echo -n "running " || echo -n "stopped "
                pgrep tincd >/dev/null && echo -n "running " || echo -n "stopped "
                ip link show l2bridge >/dev/null 2>&1 && echo "up" || echo "down"
            ' 2>/dev/null)

            if [ -n "$REMOTE_STATUS" ]; then
                AIRCRAFT_KCPTUN=$(echo "$REMOTE_STATUS" | awk '{print $1}')
                AIRCRAFT_TINCD=$(echo "$REMOTE_STATUS" | awk '{print $2}')
                AIRCRAFT_IFACE=$(echo "$REMOTE_STATUS" | awk '{print $3}')
            fi
        fi
    fi
fi

# Determine connection status
CONNECTION_ESTABLISHED="false"
CONNECTION_DURATION=0

if [ "$KCPTUN_STATUS" = "running" ] && [ "$TINCD_STATUS" = "running" ] && \
   [ "$IFACE_STATUS" = "up" ] && [ "$TINC_PEERS" -ge 2 ] 2>/dev/null; then
    CONNECTION_ESTABLISHED="true"

    # Track connection start time
    if [ ! -f "$CONNECTED_SINCE_FILE" ]; then
        date +%s > "$CONNECTED_SINCE_FILE"
    fi
    CONNECTED_SINCE=$(cat "$CONNECTED_SINCE_FILE" 2>/dev/null)
    NOW=$(date +%s)
    CONNECTION_DURATION=$((NOW - CONNECTED_SINCE))
else
    # Clear connection tracking if not connected
    rm -f "$CONNECTED_SINCE_FILE" 2>/dev/null
fi

# Output JSON response
cat << EOF
{
  "timestamp": "$(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')",
  "gcs": {
    "tailscale_ip": "${GCS_TS_IP:-}",
    "tailscale_status": "$GCS_TS_STATUS",
    "services": {
      "kcptun_server": "$KCPTUN_STATUS",
      "tincd": "$TINCD_STATUS",
      "l2bridge_interface": "$IFACE_STATUS"
    },
    "interface": {
      "name": "l2bridge",
      "mtu": ${IFACE_MTU:-0},
      "state": "$IFACE_STATUS"
    },
    "tinc_peers": $TINC_PEERS,
    "watchdog": "$WATCHDOG_STATUS",
    "health": {
      "status": "$HEALTH_STATUS",
      "last_check": "$HEALTH_LAST",
      "details": "$(json_escape "$HEALTH_DETAILS")"
    }
  },
  "aircraft": {
    "id": "${AIRCRAFT_ID:-}",
    "profile_name": "${AIRCRAFT_NAME:-None}",
    "tailscale_ip": "${AIRCRAFT_IP:-}",
    "reachable": $AIRCRAFT_REACHABLE,
    "services": {
      "kcptun_client": "$AIRCRAFT_KCPTUN",
      "tincd": "$AIRCRAFT_TINCD",
      "l2bridge_interface": "$AIRCRAFT_IFACE"
    }
  },
  "connection": {
    "established": $CONNECTION_ESTABLISHED,
    "duration_seconds": $CONNECTION_DURATION
  }
}
EOF
