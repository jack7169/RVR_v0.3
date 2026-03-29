import { useEffect, useState } from 'react';
import { listAircraft, setActiveAircraft } from '../api/client';
import type { AircraftProfiles } from '../api/types';
import { cn } from '../lib/utils';
import { useToast } from './ui/Toast';
import { AircraftModal } from './AircraftModal';

interface HeaderProps {
  connected: boolean;
  onProfileChange: () => void;
}

export function Header({ connected, onProfileChange }: HeaderProps) {
  const [profiles, setProfiles] = useState<AircraftProfiles | null>(null);
  const [showModal, setShowModal] = useState(false);
  const { toast } = useToast();

  const loadProfiles = async () => {
    try {
      const data = await listAircraft();
      setProfiles(data);
    } catch {
      // Profiles may not exist yet
    }
  };

  useEffect(() => { loadProfiles(); }, []);

  const handleSelect = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    if (!id) return;
    try {
      await setActiveAircraft(id);
      await loadProfiles();
      onProfileChange();
      toast('Aircraft switched', 'success');
    } catch {
      toast('Failed to switch aircraft', 'error');
    }
  };

  return (
    <>
      <header className="bg-bg-secondary border-b border-border px-4 py-3 sticky top-0 z-100">
        <div className="max-w-5xl mx-auto flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className={cn(
              'w-3 h-3 rounded-full animate-[pulse-dot_2s_infinite]',
              connected ? 'bg-success' : 'bg-error',
            )} />
            <h1 className="text-lg font-semibold">L2 Bridge Control Panel</h1>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-text-secondary text-sm">Aircraft:</label>
            <select
              value={profiles?.active || ''}
              onChange={handleSelect}
              className="bg-bg-input border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary"
            >
              <option value="">-- Select --</option>
              {profiles && Object.entries(profiles.profiles).map(([id, p]) => (
                <option key={id} value={id}>{p.name}</option>
              ))}
            </select>
            <button
              onClick={() => setShowModal(true)}
              className="text-xs bg-border/30 hover:bg-border/50 px-3 py-1.5 rounded-lg transition-colors"
            >
              Manage
            </button>
          </div>
        </div>
      </header>

      <AircraftModal
        open={showModal}
        onClose={() => setShowModal(false)}
        profiles={profiles}
        onRefresh={() => { loadProfiles(); onProfileChange(); }}
      />
    </>
  );
}
