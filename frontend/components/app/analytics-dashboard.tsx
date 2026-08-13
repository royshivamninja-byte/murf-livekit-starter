'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bar, Doughnut, Line } from 'react-chartjs-2';
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js';
import {
  ActivityIcon,
  CheckCircle2Icon,
  Clock3Icon,
  PhoneCallIcon,
  RefreshCwIcon,
  XCircleIcon,
} from 'lucide-react';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
  Filler
);

type Summary = {
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  success_rate: number;
  average_latency_ms: number;
};
type CallRecord = {
  call_id: string;
  started_at: string;
  duration_seconds: number;
  channel: 'BROWSER' | 'SIP';
  language: string;
  outcome: 'SUCCESS' | 'FAILED';
  failure_type: string | null;
  track_outcome: string | null;
  latency_ms: number | null;
};
type Trend = { date: string; total_calls: number; successful_calls: number; failed_calls: number };
type Filters = {
  date_from: string;
  date_to: string;
  language: string;
  channel: string;
  outcome: string;
};

const EMPTY_SUMMARY: Summary = {
  total_calls: 0,
  successful_calls: 0,
  failed_calls: 0,
  success_rate: 0,
  average_latency_ms: 0,
};
const FAILURE_LABELS: Record<string, string> = {
  USER_HANGUP: 'User Hang-up',
  USER_DECLINED: 'User Declined',
  INCOMPLETE_ENQUIRY: 'Incomplete Enquiry',
  TOOL_FAILURE: 'Tool Failure',
  API_ERROR: 'API Error',
  NO_RESPONSE: 'No Response',
  OTHER: 'Other',
};
const initialFilters: Filters = {
  date_from: '',
  date_to: '',
  language: '',
  channel: '',
  outcome: '',
};

export function AnalyticsDashboard() {
  const [filters, setFilters] = useState(initialFilters);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [calls, setCalls] = useState<CallRecord[]>([]);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [failures, setFailures] = useState<Record<string, number>>({});
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const query = useMemo(() => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => value && params.set(key, value));
    return params.toString();
  }, [filters]);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const suffix = query ? `?${query}` : '';
      const responses = await Promise.all(
        ['summary', 'calls', 'trends', 'failures'].map((name) =>
          fetch(`/api/analytics/${name}${suffix}`, { cache: 'no-store' })
        )
      );
      if (responses.some((response) => !response.ok))
        throw new Error('Analytics could not be loaded.');
      const [summaryData, callsData, trendsData, failuresData] = await Promise.all(
        responses.map((response) => response.json())
      );
      setSummary(summaryData as Summary);
      setCalls((callsData as { calls: CallRecord[] }).calls);
      setTrends((trendsData as { trends: Trend[] }).trends);
      setFailures((failuresData as { failures: Record<string, number> }).failures);
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Analytics could not be loaded.');
    } finally {
      setRefreshing(false);
    }
  }, [query]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 7000);
    return () => window.clearInterval(timer);
  }, [load]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 250 },
    plugins: { legend: { labels: { usePointStyle: true, boxWidth: 8 } } },
  } as const;
  const failureKeys = Object.keys(FAILURE_LABELS);

  return (
    <section
      id="analytics"
      className="mx-auto mt-12 max-w-7xl rounded-[2rem] border border-stone-200 bg-white/90 p-5 shadow-xl shadow-stone-900/5 sm:p-8 dark:border-stone-800 dark:bg-stone-900/90"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-end gap-4">
          <div>
            <p className="font-mono text-xs font-bold tracking-[0.18em] text-orange-700 uppercase">
              Live operations
            </p>
            <h2 className="mt-2 text-3xl font-bold text-stone-950 dark:text-stone-50">
              Call Analytics
            </h2>
            <p className="mt-2 text-sm text-stone-500">
              Real browser and SIP calls · refreshes every 7 seconds
            </p>
          </div>
          <button
            type="button"
            onClick={() => void load()}
            disabled={refreshing}
            className="inline-flex h-10 shrink-0 items-center gap-2 rounded-xl border border-orange-200 bg-orange-50 px-3 text-sm font-bold text-orange-700 transition hover:bg-orange-100 disabled:cursor-wait disabled:opacity-60 dark:border-orange-900 dark:bg-orange-950/50 dark:text-orange-300"
          >
            <RefreshCwIcon className={`size-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <Filter label="From">
            <input
              type="date"
              value={filters.date_from}
              onChange={(event) => setFilters({ ...filters, date_from: event.target.value })}
            />
          </Filter>
          <Filter label="To">
            <input
              type="date"
              value={filters.date_to}
              onChange={(event) => setFilters({ ...filters, date_to: event.target.value })}
            />
          </Filter>
          <Filter label="Language">
            <select
              value={filters.language}
              onChange={(event) => setFilters({ ...filters, language: event.target.value })}
            >
              <option value="">All</option>
              <option>English</option>
              <option>Hindi</option>
              <option>Unknown</option>
            </select>
          </Filter>
          <Filter label="Channel">
            <select
              value={filters.channel}
              onChange={(event) => setFilters({ ...filters, channel: event.target.value })}
            >
              <option value="">All</option>
              <option value="BROWSER">Browser</option>
              <option value="SIP">SIP</option>
            </select>
          </Filter>
          <Filter label="Outcome">
            <select
              value={filters.outcome}
              onChange={(event) => setFilters({ ...filters, outcome: event.target.value })}
            >
              <option value="">All</option>
              <option value="SUCCESS">Success</option>
              <option value="FAILED">Failed</option>
            </select>
          </Filter>
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="mt-5 rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300"
        >
          {error}
        </p>
      )}

      <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric
          icon={<PhoneCallIcon />}
          label="Total Calls"
          value={summary.total_calls.toLocaleString()}
        />
        <Metric
          icon={<CheckCircle2Icon />}
          label="Successful"
          value={summary.successful_calls.toLocaleString()}
          tone="green"
        />
        <Metric
          icon={<XCircleIcon />}
          label="Failed"
          value={summary.failed_calls.toLocaleString()}
          tone="red"
        />
        <Metric icon={<ActivityIcon />} label="Success Rate" value={`${summary.success_rate}%`} />
        <Metric
          icon={<Clock3Icon />}
          label="Avg Response Latency"
          value={`${(summary.average_latency_ms / 1000).toFixed(2)}s`}
        />
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        <ChartCard title="Calls over time" subtitle="Daily call volume" className="xl:col-span-2">
          <Line
            options={chartOptions}
            data={{
              labels: trends.map((item) => formatDate(item.date)),
              datasets: [
                {
                  label: 'Total calls',
                  data: trends.map((item) => item.total_calls),
                  borderColor: '#ea580c',
                  backgroundColor: 'rgba(234,88,12,.12)',
                  fill: true,
                  tension: 0.35,
                },
              ],
            }}
          />
        </ChartCard>
        <ChartCard title="Successful vs failed" subtitle="Completion outcome">
          <Doughnut
            options={{ ...chartOptions, cutout: '70%' }}
            data={{
              labels: ['Successful', 'Failed'],
              datasets: [
                {
                  data: [summary.successful_calls, summary.failed_calls],
                  backgroundColor: ['#059669', '#dc2626'],
                  borderWidth: 0,
                },
              ],
            }}
          />
        </ChartCard>
        <ChartCard title="Failure breakdown" subtitle="Why calls did not complete">
          <Bar
            options={{
              ...chartOptions,
              scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            }}
            data={{
              labels: failureKeys.map((key) => FAILURE_LABELS[key]),
              datasets: [
                {
                  label: 'Failed calls',
                  data: failureKeys.map((key) => failures[key] ?? 0),
                  backgroundColor: '#f97316',
                  borderRadius: 6,
                },
              ],
            }}
          />
        </ChartCard>
      </div>

      <div className="mt-6 overflow-hidden rounded-2xl border border-stone-200 dark:border-stone-700">
        <div className="border-b border-stone-200 px-5 py-4 dark:border-stone-700">
          <h3 className="font-bold">Recent call history</h3>
          <p className="text-sm text-stone-500">Latest 100 matching calls</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-stone-50 font-mono text-[11px] tracking-wider text-stone-500 uppercase dark:bg-stone-800">
              <tr>
                {[
                  'Time',
                  'Duration',
                  'Channel',
                  'Language',
                  'Outcome',
                  'Failure Type',
                  'Track Outcome',
                  'Latency',
                ].map((heading) => (
                  <th key={heading} className="px-4 py-3">
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
              {calls.map((call) => (
                <tr key={call.call_id} className="hover:bg-orange-50/50 dark:hover:bg-stone-800/60">
                  <td className="px-4 py-3">{new Date(call.started_at).toLocaleString()}</td>
                  <td className="px-4 py-3 font-mono">{formatDuration(call.duration_seconds)}</td>
                  <td className="px-4 py-3">{titleCase(call.channel)}</td>
                  <td className="px-4 py-3">{call.language}</td>
                  <td
                    className={`px-4 py-3 font-bold ${call.outcome === 'SUCCESS' ? 'text-emerald-700' : 'text-red-700'}`}
                  >
                    {call.outcome}
                  </td>
                  <td className="px-4 py-3">
                    {call.failure_type ? titleCase(call.failure_type) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {call.track_outcome ? titleCase(call.track_outcome) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {call.latency_ms == null ? '—' : `${(call.latency_ms / 1000).toFixed(2)}s`}
                  </td>
                </tr>
              ))}
              {!calls.length && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-stone-500">
                    No completed calls match these filters yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function Filter({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="text-xs font-bold text-stone-600 dark:text-stone-300">
      <span className="mb-1 block">{label}</span>
      <span className="block [&>input]:h-10 [&>input]:w-full [&>input]:rounded-lg [&>input]:border [&>input]:bg-transparent [&>input]:px-2 [&>select]:h-10 [&>select]:w-full [&>select]:rounded-lg [&>select]:border [&>select]:bg-white [&>select]:px-2 dark:[&>select]:bg-stone-900">
        {children}
      </span>
    </label>
  );
}
function Metric({
  icon,
  label,
  value,
  tone = 'orange',
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: 'orange' | 'green' | 'red';
}) {
  const colors = {
    orange: 'bg-orange-100 text-orange-700 dark:bg-orange-950',
    green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950',
    red: 'bg-red-100 text-red-700 dark:bg-red-950',
  };
  return (
    <article className="rounded-2xl border border-stone-200 bg-stone-50/70 p-4 dark:border-stone-700 dark:bg-stone-800/60">
      <span className={`grid size-9 place-items-center rounded-xl [&>svg]:size-4 ${colors[tone]}`}>
        {icon}
      </span>
      <p className="mt-4 font-mono text-[10px] font-bold tracking-wider text-stone-500 uppercase">
        {label}
      </p>
      <p className="mt-1 text-3xl font-bold">{value}</p>
    </article>
  );
}
function ChartCard({
  title,
  subtitle,
  children,
  className = '',
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <article
      className={`rounded-2xl border border-stone-200 p-5 dark:border-stone-700 ${className}`}
    >
      <h3 className="font-bold">{title}</h3>
      <p className="text-sm text-stone-500">{subtitle}</p>
      <div className="mt-4 h-72">{children}</div>
    </article>
  );
}
const titleCase = (value: string) =>
  value.toLowerCase().replace(/(^|_)\w/g, (match) => match.replace('_', ' ').toUpperCase());
const formatDate = (value: string) =>
  new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
const formatDuration = (seconds: number) =>
  `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
