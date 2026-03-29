import { useState } from 'react';
import type { AircraftProfiles } from '../api/types';
import { addAircraft, deleteAircraft, setActiveAircraft, updateAircraft } from '../api/client';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { useToast } from './ui/Toast';

interface Props {
  open: boolean;
  onClose: () => void;
  profiles: AircraftProfiles | null;
  onRefresh: () => void;
}

export function AircraftModal({ open, onClose, profiles, onRefresh }: Props) {
  const [showAdd, setShowAdd] = useState(false);
  const [formId, setFormId] = useState('');
  const [formName, setFormName] = useState('');
  const [formIp, setFormIp] = useState('');
  const [formPassword, setFormPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const handleAdd = async () => {
    if (!formId || !formName || !formIp) {
      toast('All fields required', 'error');
      return;
    }
    setLoading(true);
    try {
      const res = await addAircraft(formId, formName, formIp, formPassword);
      if (res.success) {
        toast('Aircraft added', 'success');
        setShowAdd(false);
        setFormId(''); setFormName(''); setFormIp(''); setFormPassword('');
        onRefresh();
      } else {
        toast(res.error || 'Failed', 'error');
      }
    } catch {
      toast('Failed to add aircraft', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteAircraft(id);
      toast('Aircraft deleted', 'success');
      onRefresh();
    } catch {
      toast('Delete failed', 'error');
    }
  };

  const handleSetActive = async (id: string) => {
    try {
      await setActiveAircraft(id);
      toast('Aircraft activated', 'success');
      onRefresh();
    } catch {
      toast('Failed to set active', 'error');
    }
  };

  const handleClearPassword = async (id: string) => {
    try {
      await updateAircraft(id, undefined, undefined, '__CLEAR__');
      toast('Password cleared', 'success');
      onRefresh();
    } catch {
      toast('Failed', 'error');
    }
  };

  const entries = profiles ? Object.entries(profiles.profiles) : [];

  return (
    <Modal open={open} onClose={onClose} title="Aircraft Management" wide>
      <div className="space-y-3">
        {entries.map(([id, p]) => (
          <div key={id} className="flex items-center justify-between bg-bg-input rounded-lg px-4 py-3">
            <div>
              <div className="font-medium text-sm">
                {p.name}
                {profiles?.active === id && <span className="ml-2 text-xs text-success">(active)</span>}
              </div>
              <div className="text-xs text-text-secondary font-mono">{p.tailscale_ip}</div>
            </div>
            <div className="flex gap-1">
              {profiles?.active !== id && (
                <Button size="sm" variant="primary" onClick={() => handleSetActive(id)}>Activate</Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => handleClearPassword(id)}>Clear Password</Button>
              <Button size="sm" variant="danger" onClick={() => handleDelete(id)}>Delete</Button>
            </div>
          </div>
        ))}
        {entries.length === 0 && (
          <div className="text-sm text-text-secondary italic">No aircraft profiles configured</div>
        )}
      </div>

      <div className="mt-4 border-t border-border pt-4">
        {!showAdd ? (
          <Button size="sm" onClick={() => setShowAdd(true)}>Add Aircraft</Button>
        ) : (
          <div className="space-y-3">
            <div className="text-sm font-semibold">New Aircraft</div>
            <div className="grid grid-cols-2 gap-3">
              <input placeholder="Profile ID" value={formId} onChange={e => setFormId(e.target.value)}
                className="bg-bg-input border border-border rounded-lg px-3 py-2 text-sm text-text-primary" />
              <input placeholder="Display Name" value={formName} onChange={e => setFormName(e.target.value)}
                className="bg-bg-input border border-border rounded-lg px-3 py-2 text-sm text-text-primary" />
              <input placeholder="Tailscale IP (100.x.x.x)" value={formIp} onChange={e => setFormIp(e.target.value)}
                className="bg-bg-input border border-border rounded-lg px-3 py-2 text-sm text-text-primary" />
              <input placeholder="SSH Password (optional)" type="password" value={formPassword} onChange={e => setFormPassword(e.target.value)}
                className="bg-bg-input border border-border rounded-lg px-3 py-2 text-sm text-text-primary" />
            </div>
            <div className="flex gap-2">
              <Button size="sm" loading={loading} onClick={handleAdd}>Save</Button>
              <Button size="sm" variant="ghost" onClick={() => setShowAdd(false)}>Cancel</Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
