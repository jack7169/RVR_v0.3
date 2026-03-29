export interface StatusResponse {
  timestamp: string;
  gcs: {
    tailscale_ip: string;
    tailscale_status: 'connected' | 'disconnected';
    services: {
      kcptun_server: 'running' | 'stopped';
      tincd: 'running' | 'stopped';
      l2bridge_interface: 'up' | 'down';
    };
    interface: {
      name: string;
      mtu: number;
      state: 'up' | 'down';
    };
    tinc_peers: number;
    watchdog: 'active' | 'inactive';
    health: {
      status: 'OK' | 'ERROR' | 'RECOVERING' | 'unknown';
      last_check: string;
      details: string;
    };
  };
  aircraft: {
    id: string;
    profile_name: string;
    tailscale_ip: string;
    reachable: boolean;
    tailscale_peer: {
      mode: 'direct' | 'relay' | 'idle' | 'unknown';
      relay: string;
      rx_bytes: number;
      tx_bytes: number;
    };
    services: {
      kcptun_client: 'running' | 'stopped' | 'unknown';
      tincd: 'running' | 'stopped' | 'unknown';
      l2bridge_interface: 'up' | 'down' | 'unknown';
    };
  };
  connection: {
    established: boolean;
    duration_seconds: number;
  };
  network_stats: {
    timestamp_ms: number;
    l2bridge: {
      rx_bytes: number;
      tx_bytes: number;
      rx_packets: number;
      tx_packets: number;
      rx_errors: number;
      tx_errors: number;
      rx_dropped: number;
      tx_dropped: number;
      multicast: number;
    };
    tailscale: {
      interface: string;
      rx_bytes: number;
      tx_bytes: number;
      rx_packets: number;
      tx_packets: number;
    };
  };
  internet: {
    status: 'connected' | 'disconnected';
  };
  bridge_filter: {
    active: boolean;
    dropped_packets: number;
    dropped_bytes: number;
  };
  capture: {
    active: boolean;
    elapsed: number;
    file_size: number;
  };
  version: {
    current: string;
    latest: string;
    update_available: boolean;
  };
}

export interface AircraftProfile {
  name: string;
  tailscale_ip: string;
  ssh_password?: string;
  created: string;
  last_used: string;
}

export interface AircraftProfiles {
  version: number;
  active: string;
  profiles: Record<string, AircraftProfile>;
}

export interface CommandResponse {
  success: boolean;
  command?: string;
  output?: string;
  exit_code?: number;
  duration_seconds?: number;
  error?: string;
}

export interface FileInfo {
  name: string;
  path: string;
  size: number;
  modified: string;
  type: 'capture' | 'log';
}

export interface FileListResponse {
  files: FileInfo[];
}

export interface LogEntry {
  timestamp: string;
  level: 'error' | 'warn' | 'info' | 'debug';
  source: 'setup' | 'watchdog' | 'system';
  message: string;
}
