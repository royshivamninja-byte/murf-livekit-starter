'use client';

import { useCallback, useEffect, useState } from 'react';
import { ChevronDownIcon, LifeBuoyIcon, RefreshCwIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

type Status = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED';
type Escalation = {
  id: number;
  reference_id: string;
  customer_name: string;
  issue_type: 'PAYMENT_REFUND' | 'ORDER_DISPUTE';
  summary: string;
  checked_information: string;
  urgency: 'LOW' | 'MEDIUM' | 'HIGH' | 'EMERGENCY';
  language: string;
  preferred_followup: string;
  status: Status;
  created_at: string;
  updated_at: string;
};

const issueLabel = (issue: Escalation['issue_type']) =>
  issue === 'PAYMENT_REFUND' ? 'Payment / Refund' : 'Order Dispute';

export function EscalationDashboard() {
  const [records, setRecords] = useState<Escalation[]>([]);
  const [expanded, setExpanded] = useState<string>();
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      const response = await fetch('/api/escalations', { cache: 'no-store' });
      if (!response.ok) throw new Error('Requests could not be loaded.');
      const payload = (await response.json()) as { escalations: Escalation[] };
      setRecords(payload.escalations);
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Requests could not be loaded.');
    }
  }, []);

  useEffect(() => void load(), [load]);

  const updateStatus = async (referenceId: string, status: Status) => {
    setError('');
    setNotice('');
    const response = await fetch(`/api/escalations/${encodeURIComponent(referenceId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    const result = (await response.json()) as {
      resolution_call?: { state: string; callSid?: string; error?: string };
    };
    if (!response.ok) {
      setError('Status could not be updated.');
      return;
    }
    if (status === 'RESOLVED' && result.resolution_call) {
      if (result.resolution_call.state === 'FAILED') {
        setError(
          `Resolved, but the notification call failed: ${result.resolution_call.error ?? 'Unknown error'}`
        );
      } else {
        setNotice(`Resolved. Notification call started (${result.resolution_call.state}).`);
      }
    }
    await load();
  };

  return (
    <section className="mx-auto mt-12 max-w-5xl rounded-[2rem] border border-stone-200 bg-white/85 p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900/85">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-full bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300">
            <LifeBuoyIcon className="size-5" />
          </span>
          <div>
            <h2 className="font-bold text-stone-900 dark:text-stone-100">Human Help Requests</h2>
            <p className="text-sm text-stone-500">
              Support escalations created with customer permission
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCwIcon /> Refresh
        </Button>
      </div>
      {error && (
        <p role="alert" className="mb-4 text-sm text-red-700">
          {error}
        </p>
      )}
      {notice && <p className="mb-4 text-sm text-emerald-700">{notice}</p>}
      {!error && records.length === 0 && (
        <p className="rounded-xl bg-stone-50 p-4 text-sm text-stone-500 dark:bg-stone-800">
          No human-help requests yet.
        </p>
      )}
      <div className="space-y-2">
        {records.map((record) => (
          <article
            key={record.reference_id}
            className="overflow-hidden rounded-xl border border-stone-200 dark:border-stone-700"
          >
            <button
              className="grid w-full grid-cols-[1.2fr_1.4fr_0.8fr_1fr_auto] items-center gap-3 p-4 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-800"
              onClick={() =>
                setExpanded(expanded === record.reference_id ? undefined : record.reference_id)
              }
              aria-expanded={expanded === record.reference_id}
            >
              <strong>{record.reference_id}</strong>
              <span>{issueLabel(record.issue_type)}</span>
              <span>{record.urgency}</span>
              <span>{record.status.replace('_', ' ')}</span>
              <ChevronDownIcon
                className={`size-4 transition ${expanded === record.reference_id ? 'rotate-180' : ''}`}
              />
            </button>
            {expanded === record.reference_id && (
              <div className="grid gap-4 border-t border-stone-200 bg-stone-50 p-5 text-sm sm:grid-cols-2 dark:border-stone-700 dark:bg-stone-950">
                <Detail label="Customer" value={record.customer_name} />
                <Detail label="Issue" value={issueLabel(record.issue_type)} />
                <Detail label="Summary" value={record.summary} />
                <Detail label="What Mitra checked" value={record.checked_information} />
                <Detail label="Urgency" value={record.urgency} />
                <Detail label="Language" value={record.language} />
                <Detail label="Preferred follow-up" value={record.preferred_followup} />
                <div>
                  <p className="mb-1 font-bold">Status</p>
                  <Select
                    value={record.status}
                    onValueChange={(value) =>
                      void updateStatus(record.reference_id, value as Status)
                    }
                  >
                    <SelectTrigger aria-label={`Status for ${record.reference_id}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="OPEN">Open</SelectItem>
                      <SelectItem value="IN_PROGRESS">In progress</SelectItem>
                      <SelectItem value="RESOLVED">Resolved</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-bold">{label}</p>
      <p className="mt-1 whitespace-pre-wrap text-stone-600 dark:text-stone-300">
        {value || 'Not provided'}
      </p>
    </div>
  );
}
