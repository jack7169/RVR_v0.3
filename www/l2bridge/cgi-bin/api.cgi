#!/bin/sh
#
# L2Bridge Web UI - Command and Profile API
# Handles l2bridge commands and aircraft profile management
#

# Configuration
AIRCRAFT_FILE="/etc/l2bridge/aircraft.json"
CONFIG_DIR="/etc/l2bridge"
LOCK_FILE="/tmp/l2bridge-webui.lock"
L2BRIDGE="/usr/bin/l2bridge"

# Helper: output JSON response
json_response() {
    echo "Content-Type: application/json"
    echo ""
    echo "$1"
}

# Helper: output error
json_error() {
    json_response "{\"success\": false, \"error\": \"$1\"}"
    exit 0
}

# Helper: escape string for JSON
json_escape() {
    printf '%s' "$1" | awk '
    BEGIN { ORS="" }
    {
        gsub(/\\/, "\\\\")      # Escape backslashes first
        gsub(/"/, "\\\"")       # Escape double quotes
        gsub(/\t/, "\\t")       # Escape tabs
        gsub(/\r/, "")          # Remove carriage returns
        if (NR > 1) print "\\n" # Add escaped newline between lines
        print
    }
    '
}

# Helper: validate Tailscale IP format (100.x.x.x)
validate_ip() {
    echo "$1" | grep -qE '^100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'
}

# Helper: validate profile ID (alphanumeric, dash, underscore)
validate_id() {
    echo "$1" | grep -qE '^[a-zA-Z0-9_-]+$'
}

# Helper: acquire lock for command execution
acquire_lock() {
    if [ -f "$LOCK_FILE" ]; then
        local pid=$(cat "$LOCK_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            json_error "Another command is currently running"
        fi
    fi
    echo $$ > "$LOCK_FILE"
    trap "rm -f '$LOCK_FILE'" EXIT
}

# Helper: release lock
release_lock() {
    rm -f "$LOCK_FILE"
}

# Initialize aircraft config file if it doesn't exist
init_aircraft_file() {
    mkdir -p "$CONFIG_DIR"
    if [ ! -f "$AIRCRAFT_FILE" ]; then
        printf '{\n  "version": 1,\n  "active": "",\n  "profiles": {}\n}\n' > "$AIRCRAFT_FILE"
    fi
}

# Read POST data
read_post_data() {
    if [ "$REQUEST_METHOD" = "POST" ]; then
        read -r POST_DATA
        echo "$POST_DATA"
    fi
}

# Parse JSON field (simple extraction without jsonfilter dependency)
# Usage: parse_json "field" "json_string"
parse_json() {
    local field="$1"
    local json="$2"
    echo "$json" | sed -n "s/.*\"$field\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p"
}

# Execute l2bridge command
run_l2bridge_command() {
    local cmd="$1"
    local aircraft_ip="$2"
    local start_time=$(date +%s)

    acquire_lock

    local output
    local exit_code

    if [ -n "$aircraft_ip" ]; then
        output=$("$L2BRIDGE" "$cmd" "$aircraft_ip" 2>&1)
        exit_code=$?
    else
        output=$("$L2BRIDGE" "$cmd" 2>&1)
        exit_code=$?
    fi

    release_lock

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    local escaped_output=$(json_escape "$output")
    local success="false"
    [ $exit_code -eq 0 ] && success="true"

    json_response "{\"success\": $success, \"command\": \"$cmd\", \"output\": \"$escaped_output\", \"exit_code\": $exit_code, \"duration_seconds\": $duration}"
}

# List all aircraft profiles
list_aircraft() {
    init_aircraft_file
    echo "Content-Type: application/json"
    echo ""
    cat "$AIRCRAFT_FILE"
}

# Add new aircraft profile
add_aircraft() {
    local id="$1"
    local name="$2"
    local ip="$3"

    # Validate inputs
    [ -z "$id" ] && json_error "Profile ID is required"
    [ -z "$name" ] && json_error "Profile name is required"
    [ -z "$ip" ] && json_error "Tailscale IP is required"
    validate_id "$id" || json_error "Invalid profile ID format"
    validate_ip "$ip" || json_error "Invalid Tailscale IP format (must be 100.x.x.x)"

    init_aircraft_file

    # Check if ID already exists
    if grep -q "\"$id\":" "$AIRCRAFT_FILE"; then
        json_error "Profile ID already exists"
    fi

    local created=$(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')

    # Get current active
    local current_active=""
    current_active=$(sed -n 's/.*"active":[[:space:]]*"\([^"]*\)".*/\1/p' "$AIRCRAFT_FILE" | head -1)

    # Simple approach: rebuild the entire file
    # Extract existing profiles as id|name|ip|created|last_used lines
    local tmp_profiles=$(mktemp)
    awk '
    /"[a-zA-Z0-9_-]+":[[:space:]]*\{/ {
        # Extract profile id
        gsub(/.*"/, "")
        gsub(/".*/, "")
        current_id = $0
    }
    /"name":/ {
        gsub(/.*"name":[[:space:]]*"/, "")
        gsub(/".*/, "")
        profiles[current_id]["name"] = $0
    }
    /"tailscale_ip":/ {
        gsub(/.*"tailscale_ip":[[:space:]]*"/, "")
        gsub(/".*/, "")
        profiles[current_id]["ip"] = $0
    }
    /"created":/ {
        gsub(/.*"created":[[:space:]]*"/, "")
        gsub(/".*/, "")
        profiles[current_id]["created"] = $0
    }
    /"last_used":/ {
        gsub(/.*"last_used":[[:space:]]*"/, "")
        gsub(/".*/, "")
        profiles[current_id]["last_used"] = $0
        # Output complete profile
        print current_id "|" profiles[current_id]["name"] "|" profiles[current_id]["ip"] "|" profiles[current_id]["created"] "|" profiles[current_id]["last_used"]
    }
    ' "$AIRCRAFT_FILE" > "$tmp_profiles"

    # Add new profile to list
    echo "$id|$name|$ip|$created|$created" >> "$tmp_profiles"

    # Rebuild JSON file
    printf '{\n  "version": 1,\n  "active": "%s",\n  "profiles": {\n' "$current_active" > "$AIRCRAFT_FILE"

    local first=1
    while IFS='|' read -r pid pname pip pcreated plast; do
        [ -z "$pid" ] && continue
        [ $first -eq 0 ] && printf ',\n' >> "$AIRCRAFT_FILE"
        printf '    "%s": {\n' "$pid" >> "$AIRCRAFT_FILE"
        printf '      "name": "%s",\n' "$pname" >> "$AIRCRAFT_FILE"
        printf '      "tailscale_ip": "%s",\n' "$pip" >> "$AIRCRAFT_FILE"
        printf '      "created": "%s",\n' "$pcreated" >> "$AIRCRAFT_FILE"
        printf '      "last_used": "%s"\n' "$plast" >> "$AIRCRAFT_FILE"
        printf '    }' >> "$AIRCRAFT_FILE"
        first=0
    done < "$tmp_profiles"

    printf '\n  }\n}\n' >> "$AIRCRAFT_FILE"
    rm -f "$tmp_profiles"

    json_response "{\"success\": true, \"message\": \"Aircraft profile added\", \"id\": \"$id\"}"
}

# Update aircraft profile
update_aircraft() {
    local id="$1"
    local name="$2"
    local ip="$3"

    [ -z "$id" ] && json_error "Profile ID is required"
    validate_id "$id" || json_error "Invalid profile ID format"

    init_aircraft_file

    # Check if profile exists
    if ! grep -q "\"$id\"" "$AIRCRAFT_FILE"; then
        json_error "Profile not found"
    fi

    [ -n "$ip" ] && { validate_ip "$ip" || json_error "Invalid Tailscale IP format"; }

    # Update using sed (simple field replacement)
    local tmp_file=$(mktemp)
    cp "$AIRCRAFT_FILE" "$tmp_file"

    if [ -n "$name" ]; then
        # This is a simplified update - in production, use proper JSON tools
        sed -i "s/\"name\": \"[^\"]*\"/\"name\": \"$name\"/" "$tmp_file"
    fi

    if [ -n "$ip" ]; then
        sed -i "s/\"tailscale_ip\": \"[^\"]*\"/\"tailscale_ip\": \"$ip\"/" "$tmp_file"
    fi

    mv "$tmp_file" "$AIRCRAFT_FILE"

    json_response "{\"success\": true, \"message\": \"Aircraft profile updated\"}"
}

# Delete aircraft profile
delete_aircraft() {
    local id="$1"

    [ -z "$id" ] && json_error "Profile ID is required"
    validate_id "$id" || json_error "Invalid profile ID format"

    init_aircraft_file

    # Check if profile exists
    if ! grep -q "\"$id\":" "$AIRCRAFT_FILE"; then
        json_error "Profile not found"
    fi

    # Get current active, clear if it's the one being deleted
    local current_active=""
    current_active=$(sed -n 's/.*"active":[[:space:]]*"\([^"]*\)".*/\1/p' "$AIRCRAFT_FILE" | head -1)
    [ "$current_active" = "$id" ] && current_active=""

    # Extract all profiles except the one being deleted
    local tmp_profiles=$(mktemp)
    awk -v delete_id="$id" '
    /"[a-zA-Z0-9_-]+":[[:space:]]*\{/ {
        gsub(/.*"/, "")
        gsub(/".*/, "")
        current_id = $0
    }
    /"name":/ {
        gsub(/.*"name":[[:space:]]*"/, "")
        gsub(/".*/, "")
        profiles[current_id]["name"] = $0
    }
    /"tailscale_ip":/ {
        gsub(/.*"tailscale_ip":[[:space:]]*"/, "")
        gsub(/".*/, "")
        profiles[current_id]["ip"] = $0
    }
    /"created":/ {
        gsub(/.*"created":[[:space:]]*"/, "")
        gsub(/".*/, "")
        profiles[current_id]["created"] = $0
    }
    /"last_used":/ {
        gsub(/.*"last_used":[[:space:]]*"/, "")
        gsub(/".*/, "")
        profiles[current_id]["last_used"] = $0
        if (current_id != delete_id) {
            print current_id "|" profiles[current_id]["name"] "|" profiles[current_id]["ip"] "|" profiles[current_id]["created"] "|" profiles[current_id]["last_used"]
        }
    }
    ' "$AIRCRAFT_FILE" > "$tmp_profiles"

    # Rebuild JSON file
    printf '{\n  "version": 1,\n  "active": "%s",\n  "profiles": {\n' "$current_active" > "$AIRCRAFT_FILE"

    local first=1
    while IFS='|' read -r pid pname pip pcreated plast; do
        [ -z "$pid" ] && continue
        [ $first -eq 0 ] && printf ',\n' >> "$AIRCRAFT_FILE"
        printf '    "%s": {\n' "$pid" >> "$AIRCRAFT_FILE"
        printf '      "name": "%s",\n' "$pname" >> "$AIRCRAFT_FILE"
        printf '      "tailscale_ip": "%s",\n' "$pip" >> "$AIRCRAFT_FILE"
        printf '      "created": "%s",\n' "$pcreated" >> "$AIRCRAFT_FILE"
        printf '      "last_used": "%s"\n' "$plast" >> "$AIRCRAFT_FILE"
        printf '    }' >> "$AIRCRAFT_FILE"
        first=0
    done < "$tmp_profiles"

    printf '\n  }\n}\n' >> "$AIRCRAFT_FILE"
    rm -f "$tmp_profiles"

    json_response "{\"success\": true, \"message\": \"Aircraft profile deleted\"}"
}

# Set active aircraft
set_active_aircraft() {
    local id="$1"

    [ -z "$id" ] && json_error "Profile ID is required"
    validate_id "$id" || json_error "Invalid profile ID format"

    init_aircraft_file

    # Verify profile exists
    if ! grep -q "\"$id\"" "$AIRCRAFT_FILE"; then
        json_error "Profile not found"
    fi

    # Update active field
    sed -i "s/\"active\"[[:space:]]*:[[:space:]]*\"[^\"]*\"/\"active\": \"$id\"/" "$AIRCRAFT_FILE"

    # Get the IP for this profile and update legacy config
    local ip=""
    if command -v jsonfilter >/dev/null 2>&1; then
        ip=$(jsonfilter -i "$AIRCRAFT_FILE" -e "@.profiles[\"$id\"].tailscale_ip" 2>/dev/null)
    else
        # Fallback parsing
        ip=$(awk -v id="$id" '
            /"'"$id"'"/ { found=1 }
            found && /"tailscale_ip"/ { gsub(/.*"tailscale_ip"[[:space:]]*:[[:space:]]*"/, ""); gsub(/".*/, ""); print; exit }
        ' "$AIRCRAFT_FILE")
    fi

    # Update legacy state file for compatibility with l2bridge script
    if [ -n "$ip" ]; then
        echo "AIRCRAFT_IP=\"$ip\"" > /etc/l2bridge.conf
    fi

    # Update last_used timestamp
    local now=$(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')

    json_response "{\"success\": true, \"message\": \"Active aircraft set to $id\", \"tailscale_ip\": \"$ip\"}"
}

# Main request handling
main() {
    local post_data=$(read_post_data)
    local action=""
    local aircraft_ip=""

    # Parse action from POST data or query string
    if [ -n "$post_data" ]; then
        # Try jsonfilter first
        if command -v jsonfilter >/dev/null 2>&1; then
            action=$(echo "$post_data" | jsonfilter -e '@.action' 2>/dev/null)
            aircraft_ip=$(echo "$post_data" | jsonfilter -e '@.aircraft_ip' 2>/dev/null)
        fi
        # Fallback to simple parsing
        [ -z "$action" ] && action=$(parse_json "action" "$post_data")
        [ -z "$aircraft_ip" ] && aircraft_ip=$(parse_json "aircraft_ip" "$post_data")
    fi

    # Handle GET requests
    if [ "$REQUEST_METHOD" = "GET" ]; then
        action=$(echo "$QUERY_STRING" | sed -n 's/.*action=\([^&]*\).*/\1/p')
    fi

    [ -z "$action" ] && json_error "No action specified"

    case "$action" in
        # L2Bridge commands
        start|stop|restart|setup|debug)
            run_l2bridge_command "$action" "$aircraft_ip"
            ;;
        status)
            run_l2bridge_command "status" ""
            ;;
        config)
            run_l2bridge_command "config" ""
            ;;
        logs)
            run_l2bridge_command "logs" "50"
            ;;

        # Aircraft profile management
        list_aircraft)
            list_aircraft
            ;;
        add_aircraft)
            local id=$(parse_json "id" "$post_data")
            local name=$(parse_json "name" "$post_data")
            local ip=$(parse_json "tailscale_ip" "$post_data")
            add_aircraft "$id" "$name" "$ip"
            ;;
        update_aircraft)
            local id=$(parse_json "id" "$post_data")
            local name=$(parse_json "name" "$post_data")
            local ip=$(parse_json "tailscale_ip" "$post_data")
            update_aircraft "$id" "$name" "$ip"
            ;;
        delete_aircraft)
            local id=$(parse_json "id" "$post_data")
            delete_aircraft "$id"
            ;;
        set_active)
            local id=$(parse_json "id" "$post_data")
            set_active_aircraft "$id"
            ;;

        *)
            json_error "Unknown action: $action"
            ;;
    esac
}

main
