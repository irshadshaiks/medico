import { useState, useEffect } from 'react';
import {
  Stethoscope,
  Search,
  Filter,
  AlertTriangle,
  Clock,
  ChevronRight,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
  Home,
  UserPlus
} from 'lucide-react';
import { api } from '@/lib/api';

interface CaseItem {
  id: string;
  patient_name: string;
  patient_age: number;
  patient_gender: string;
  chief_complaint: string;
  status: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'ROUTINE';
  priority_score: number;
  priority_reason: string;
  created_at: string;
}

export function DoctorDashboard({
  onSelectCase,
  onBackHome,
  onNewIntake
}: {
  onSelectCase: (caseId: string) => void;
  onBackHome: () => void;
  onNewIntake: () => void;
}) {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [stats, setStats] = useState({ priority: 0, needs_review: 0, routine: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'priority' | 'review' | 'routine'>('all');
  const [changingPriorityId, setChangingPriorityId] = useState<string | null>(null);

  const fetchQueue = async () => {
    try {
      setLoading(true);
      const res = await api.getDoctorQueue(searchQuery);
      setCases(res.cases || []);
      setStats(res.stats || { priority: 0, needs_review: 0, routine: 0, total: 0 });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, [searchQuery]);

  const handlePriorityChange = async (caseId: string, newPriority: string) => {
    try {
      setChangingPriorityId(caseId);
      await api.updatePriority(caseId, newPriority, `Attending physician re-triaged to ${newPriority}`);
      await fetchQueue();
    } catch (err: any) {
      alert(err.message || 'Error updating priority');
    } finally {
      setChangingPriorityId(null);
    }
  };

  const filteredCases = cases.filter((c) => {
    if (activeFilter === 'priority') return c.priority === 'CRITICAL' || c.priority === 'HIGH';
    if (activeFilter === 'review') return c.status === 'submitted' || c.status === 'in_review';
    if (activeFilter === 'routine') return c.priority === 'ROUTINE';
    return true;
  });

  return (
    <div className="min-h-screen bg-void pt-20 pb-20 text-ice">
      {/* Top Breadcrumbs & Controls */}
      <div className="shell max-w-6xl mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onBackHome}
            className="flex items-center gap-1.5 text-xs text-mute hover:text-ice bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg border border-hair transition-all"
          >
            <Home size={14} />
            <span>Home</span>
          </button>
          <span className="text-dim">/</span>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan">
            <Stethoscope size={14} />
            <span>Doctor Triage Workstation</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onNewIntake}
            className="btn btn-ghost py-1.5 px-3 text-xs text-cyan border border-cyan/30 rounded-lg hover:bg-cyan/10 flex items-center gap-1.5"
          >
            <UserPlus size={14} />
            <span>New Patient Intake</span>
          </button>
          <button
            onClick={fetchQueue}
            className="btn btn-ghost py-1.5 px-3 text-xs text-mute hover:text-ice border border-hair rounded-lg flex items-center gap-1.5"
            title="Refresh queue"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Main Container */}
      <div className="shell max-w-6xl">
        {/* Outpatient Header Strip */}
        <div className="overflow-hidden rounded-2xl border border-hairStrong bg-gradient-to-b from-[rgba(11,19,30,0.92)] to-[rgba(5,9,14,0.85)] shadow-2xl backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hair bg-white/[0.012] px-6 py-3.5">
            <div className="flex items-center gap-2.5">
              <span className="h-2 w-2 rounded-full bg-cyan shadow-[0_0_0_4px_rgba(79,216,228,0.16)]" />
              <span className="text-sm font-medium text-mute">Outpatient Queue — General Medicine & Cardiology</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-dim">
              <span>Attending Physician:</span>
              <strong className="text-ice font-semibold">Dr. A. Menon</strong>
            </div>
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 border-b border-hair">
            <div
              onClick={() => setActiveFilter('priority')}
              className={`p-5 cursor-pointer transition-colors border-r border-hair ${
                activeFilter === 'priority' ? 'bg-red-500/10' : 'hover:bg-white/[0.02]'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs text-dim uppercase tracking-wider font-semibold">Priority Triage</span>
                <span className="h-2 w-2 rounded-full bg-flag animate-ping" />
              </div>
              <b className="mt-1 block font-display text-3xl font-medium text-flag tracking-tight">
                {stats.priority}
              </b>
              <span className="text-xs text-mute">Critical & High Urgency</span>
            </div>

            <div
              onClick={() => setActiveFilter('review')}
              className={`p-5 cursor-pointer transition-colors border-r border-hair ${
                activeFilter === 'review' ? 'bg-amber-500/10' : 'hover:bg-white/[0.02]'
              }`}
            >
              <span className="text-xs text-dim uppercase tracking-wider font-semibold">Needs Review</span>
              <b className="mt-1 block font-display text-3xl font-medium text-ice tracking-tight">
                {stats.needs_review}
              </b>
              <span className="text-xs text-mute">Awaiting Doctor Verification</span>
            </div>

            <div
              onClick={() => setActiveFilter('routine')}
              className={`p-5 cursor-pointer transition-colors border-r border-hair ${
                activeFilter === 'routine' ? 'bg-blue-500/10' : 'hover:bg-white/[0.02]'
              }`}
            >
              <span className="text-xs text-dim uppercase tracking-wider font-semibold">Routine Queue</span>
              <b className="mt-1 block font-display text-3xl font-medium text-ice tracking-tight">
                {stats.routine}
              </b>
              <span className="text-xs text-mute">Stable OPD Baseline</span>
            </div>

            <div
              onClick={() => setActiveFilter('all')}
              className={`p-5 cursor-pointer transition-colors ${
                activeFilter === 'all' ? 'bg-cyan/10' : 'hover:bg-white/[0.02]'
              }`}
            >
              <span className="text-xs text-dim uppercase tracking-wider font-semibold">Total Waiting</span>
              <b className="mt-1 block font-display text-3xl font-medium text-cyan tracking-tight">
                {stats.total}
              </b>
              <span className="text-xs text-mute">All Active Consultations</span>
            </div>
          </div>

          {/* Search & Filter Controls */}
          <div className="p-4 border-b border-hair flex flex-wrap items-center justify-between gap-3 bg-[rgba(6,10,16,0.4)]">
            <div className="relative flex-1 min-w-[260px] max-w-md">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-dim" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search patient, symptoms, or priority..."
                className="w-full rounded-xl border border-hair bg-[rgba(6,10,16,0.7)] pl-10 pr-4 py-2 text-sm text-ice placeholder-dim focus:border-cyan focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-dim mr-1">Filter:</span>
              {(['all', 'priority', 'review', 'routine'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveFilter(tab)}
                  className={`px-3 py-1.5 rounded-lg capitalize border transition-all ${
                    activeFilter === tab
                      ? 'border-cyan bg-cyan/15 text-cyan font-medium'
                      : 'border-hair text-mute hover:text-ice'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>

          {/* Patient Queue Cards List */}
          <div className="p-5 space-y-3.5">
            {filteredCases.length === 0 ? (
              <div className="p-12 text-center text-dim text-sm">
                No patients found matching the selected filter.
              </div>
            ) : (
              filteredCases.map((item) => {
                const isCritical = item.priority === 'CRITICAL';
                const isHigh = item.priority === 'HIGH';
                const isMedium = item.priority === 'MEDIUM';

                return (
                  <div
                    key={item.id}
                    className={`rounded-xl border p-4.5 transition-all hover:border-hairStrong ${
                      isCritical
                        ? 'border-[rgba(242,169,59,0.35)] bg-[rgba(242,169,59,0.055)] shadow-[0_10px_30px_-15px_rgba(242,169,59,0.15)]'
                        : isHigh
                        ? 'border-amber-500/20 bg-amber-500/[0.03]'
                        : 'border-hair bg-[rgba(12,22,33,0.5)]'
                    }`}
                  >
                    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                      {/* Left info: Avatar, Name, Age, Complaint */}
                      <div className="flex items-start gap-3.5 min-w-0 flex-1">
                        <div
                          className={`grid h-10 w-10 flex-none place-items-center rounded-xl border text-xs font-semibold ${
                            isCritical
                              ? 'border-flag/40 bg-gradient-to-br from-flag/20 to-flag/5 text-[#FFD79A]'
                              : 'border-hair bg-gradient-to-br from-cyan/20 to-blue-500/20 text-ice'
                          }`}
                        >
                          {item.patient_name
                            .split(' ')
                            .map((n) => n[0])
                            .slice(0, 2)
                            .join('')}
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2.5 flex-wrap">
                            <span className="text-base font-semibold text-ice">
                              {item.patient_name}, {item.patient_age}
                            </span>
                            <span className="text-xs text-dim">({item.patient_gender})</span>
                            <span
                              className={`chip text-[11px] font-medium ${
                                isCritical
                                  ? 'border-flag/50 bg-flag/15 text-[#FFD79A]'
                                  : isHigh
                                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
                                  : isMedium
                                  ? 'border-yellow-500/30 text-yellow-300'
                                  : 'border-blue-500/30 text-blue-300'
                              }`}
                            >
                              {item.priority} (Score {item.priority_score})
                            </span>
                          </div>

                          <div className="mt-1 text-xs text-dim line-clamp-1">
                            {item.chief_complaint}
                          </div>

                          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-mute">
                            <span className="text-amber-300/90 font-medium">
                              {item.priority_reason}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Right controls: Priority Override + Open File */}
                      <div className="flex flex-wrap items-center gap-2.5 lg:flex-none">
                        {/* Interactive Priority Override Dropdown */}
                        <div className="flex items-center gap-1.5 bg-black/40 border border-hair rounded-lg px-2 py-1">
                          <span className="text-[10px] uppercase font-semibold text-dim">Set Priority:</span>
                          {(['CRITICAL', 'HIGH', 'MEDIUM', 'ROUTINE'] as const).map((pTier) => (
                            <button
                              key={pTier}
                              disabled={changingPriorityId === item.id}
                              onClick={() => handlePriorityChange(item.id, pTier)}
                              className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-all ${
                                item.priority === pTier
                                  ? pTier === 'CRITICAL'
                                    ? 'bg-red-500 text-white shadow-sm'
                                    : pTier === 'HIGH'
                                    ? 'bg-amber-500 text-black'
                                    : pTier === 'MEDIUM'
                                    ? 'bg-yellow-500 text-black'
                                    : 'bg-cyan text-black'
                                  : 'text-dim hover:text-ice hover:bg-white/5'
                              }`}
                            >
                              {pTier[0]}
                            </button>
                          ))}
                        </div>

                        {/* Open Case File Button */}
                        <button
                          onClick={() => onSelectCase(item.id)}
                          className="btn btn-primary text-xs py-2 px-3.5 shadow-md flex items-center gap-1 group"
                        >
                          <span>Open Case File</span>
                          <ChevronRight size={14} className="transition-transform group-hover:translate-x-0.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
