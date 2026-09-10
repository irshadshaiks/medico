import { useState, useEffect } from 'react';
import {
  ArrowLeft,
  CheckCircle2,
  Edit3,
  XCircle,
  FileText,
  Clock,
  Shield,
  Activity,
  User,
  AlertTriangle,
  Upload,
  Save,
  Check
} from 'lucide-react';
import { api } from '@/lib/api';

interface CaseFileProps {
  caseId: string;
  onBackToQueue: () => void;
}

export function DoctorCaseFile({ caseId, onBackToQueue }: CaseFileProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'statements' | 'documents' | 'audit'>('statements');

  // Edit modal / inline edit state
  const [editingSection, setEditingSection] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [doctorNotes, setDoctorNotes] = useState('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const fetchCase = async () => {
    try {
      setLoading(true);
      const res = await api.getDoctorCase(caseId);
      setData(res);
      if (res.summary?.doctor_notes) {
        setDoctorNotes(res.summary.doctor_notes);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCase();
  }, [caseId]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleVerifySection = async (section: string, status: 'verified' | 'rejected') => {
    try {
      await api.verifySection(caseId, section, status);
      await fetchCase();
      showToast(`Section '${section.replace('_', ' ')}' marked as ${status}`);
    } catch (err: any) {
      alert(err.message || 'Verification failed');
    }
  };

  const handleStartEdit = (section: string, currentContent: string) => {
    setEditingSection(section);
    setEditText(currentContent);
  };

  const handleSaveEdit = async () => {
    if (!editingSection) return;
    try {
      await api.verifySection(caseId, editingSection, 'modified', editText, 'Doctor adjusted clinical wording');
      setEditingSection(null);
      await fetchCase();
      showToast(`Section '${editingSection.replace('_', ' ')}' modified and saved`);
    } catch (err: any) {
      alert(err.message || 'Save failed');
    }
  };

  const handlePriorityChange = async (newPriority: string) => {
    try {
      await api.updatePriority(caseId, newPriority, 'Attending physician priority revision');
      await fetchCase();
      showToast(`Priority updated to ${newPriority}`);
    } catch (err: any) {
      alert(err.message || 'Failed to update priority');
    }
  };

  const handleFinalize = async () => {
    try {
      await api.finalizeCase(caseId);
      await fetchCase();
      showToast('Case file finalized and verified successfully!');
    } catch (err: any) {
      alert(err.message || 'Finalization failed');
    }
  };

  if (loading || !data) {
    return (
      <div className="min-h-screen bg-void pt-28 text-center text-dim text-sm">
        Loading patient case file...
      </div>
    );
  }

  const { case: patientCase, summary, documents, interview_transcript, audit_trail } = data;
  const verifiedSections = summary?.verified_sections || {};

  const SECTIONS = [
    { key: 'chief_complaint', label: 'Chief Complaint', body: summary?.chief_complaint_summary, tag: 'Complaint — patient' },
    { key: 'hpi', label: 'History of Present Illness (HPI)', body: summary?.hpi, tag: 'HPI — synthesized' },
    { key: 'past_medical_history', label: 'Past Medical History', body: summary?.past_medical_history, tag: 'History — patient & Rx' },
    { key: 'current_medications', label: 'Current Medications', body: summary?.current_medications, tag: 'Drugs — 2025 prescription' },
    { key: 'lab_findings', label: 'Lab & Diagnostic Findings', body: summary?.lab_findings, tag: 'HbA1c — lab report' },
    { key: 'red_flags', label: 'Red Flags & Warning Signs', body: summary?.red_flags, tag: 'Flag — emergency triage', isFlag: true },
  ];

  return (
    <div className="min-h-screen bg-void pt-20 pb-20 text-ice">
      {/* Toast */}
      {toastMessage && (
        <div className="fixed top-6 right-6 z-[120] flex items-center gap-2 rounded-xl border border-cyan/40 bg-[rgba(7,12,19,0.95)] px-4 py-3 text-sm text-cyan shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-top-4">
          <CheckCircle2 size={16} />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Header & Breadcrumb */}
      <div className="shell max-w-7xl mb-6 flex flex-wrap items-center justify-between gap-4">
        <button
          onClick={onBackToQueue}
          className="flex items-center gap-2 text-xs text-mute hover:text-ice bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg border border-hair transition-all"
        >
          <ArrowLeft size={14} />
          <span>Back to Doctor Queue</span>
        </button>

        {/* Priority Override Dropdown */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-dim">Case Priority:</span>
          <div className="flex gap-1 bg-black/40 border border-hair rounded-xl p-1">
            {(['CRITICAL', 'HIGH', 'MEDIUM', 'ROUTINE'] as const).map((tier) => (
              <button
                key={tier}
                onClick={() => handlePriorityChange(tier)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                  patientCase.priority === tier
                    ? tier === 'CRITICAL'
                      ? 'bg-red-500 text-white shadow-md'
                      : tier === 'HIGH'
                      ? 'bg-amber-500 text-black shadow-md'
                      : tier === 'MEDIUM'
                      ? 'bg-yellow-500 text-black shadow-md'
                      : 'bg-cyan text-black shadow-md'
                    : 'text-dim hover:text-ice hover:bg-white/5'
                }`}
              >
                {tier}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="shell max-w-7xl">
        {/* Patient Profile Bar */}
        <div className="rounded-2xl border border-hairStrong bg-gradient-to-b from-[rgba(11,19,30,0.92)] to-[rgba(5,9,14,0.85)] p-5 shadow-2xl backdrop-blur-xl mb-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-cyan/20 to-blue-600/30 border border-cyan/40 grid place-items-center text-base font-bold text-ice">
              {patientCase.patient_name.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-display font-semibold text-ice">
                  {patientCase.patient_name}
                </h1>
                <span className="text-sm text-dim">· {patientCase.patient_age} yrs, {patientCase.patient_gender}</span>
                <span className="chip border-hair text-dim text-xs">
                  ID: {patientCase.id}
                </span>
              </div>
              <div className="text-xs text-dim mt-0.5">
                Intake completed · Attending: Dr. A. Menon (General Medicine & Cardiology)
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <span className="text-xs text-dim block">Triage Classification</span>
              <span className="text-sm font-semibold text-amber-300">
                {patientCase.priority} (Score {patientCase.priority_score}/100)
              </span>
            </div>
            <span className="h-3 w-3 rounded-full bg-cyan shadow-[0_0_0_4px_rgba(79,216,228,0.2)]" />
          </div>
        </div>

        {/* 2-Column Clinical Workspace */}
        <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-6">
          {/* LEFT COLUMN: Structured AI Clinical Summary with per-section verification */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText size={18} className="text-cyan" />
                <h2 className="text-base font-display font-semibold text-ice">
                  Structured Clinical Summary
                </h2>
              </div>
              <span className="text-xs text-dim">
                Every action written to the audit trail
              </span>
            </div>

            {SECTIONS.map((sec) => {
              const isVerified = verifiedSections[sec.key] === true;
              const isEditing = editingSection === sec.key;

              return (
                <div
                  key={sec.key}
                  className={`cell p-5 border transition-all ${
                    sec.isFlag
                      ? 'border-amber-500/35 bg-amber-500/[0.04]'
                      : isVerified
                      ? 'border-emerald-500/30 bg-emerald-500/[0.02]'
                      : 'border-hair'
                  }`}
                >
                  <div className="flex items-center justify-between pb-2.5 border-b border-hair">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold uppercase tracking-wider text-dim">
                        {sec.label}
                      </span>
                      {isVerified ? (
                        <span className="rounded-md border border-emerald-500/50 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-300 flex items-center gap-1">
                          <Check size={12} />
                          <span>Doctor-verified</span>
                        </span>
                      ) : (
                        <span className="rounded-md border border-dashed border-amber-500/50 px-2 py-0.5 text-[11px] text-[#F5CE93]">
                          Draft — not verified
                        </span>
                      )}
                    </div>
                    <span className="chip text-[10px] border-hair text-dim">{sec.tag}</span>
                  </div>

                  {/* Body Content */}
                  <div className="mt-3">
                    {isEditing ? (
                      <div className="space-y-2">
                        <textarea
                          rows={3}
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          className="w-full rounded-xl border border-cyan bg-black/60 p-3 text-sm text-ice focus:outline-none"
                        />
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => setEditingSection(null)}
                            className="px-3 py-1 text-xs text-mute hover:text-ice"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={handleSaveEdit}
                            className="btn btn-primary text-xs py-1 px-3"
                          >
                            Save Changes
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className={`text-sm leading-relaxed ${sec.isFlag ? 'text-amber-200' : 'text-mute'}`}>
                        {sec.body || 'No records provided.'}
                      </p>
                    )}
                  </div>

                  {/* Section Verification Buttons */}
                  {!isEditing && (
                    <div className="mt-4 pt-3 border-t border-hair flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleVerifySection(sec.key, 'verified')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                          isVerified
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : 'bg-cyan text-slate-950 hover:bg-cyan-soft'
                        }`}
                      >
                        {isVerified ? 'Section Verified ✓' : 'Accept section'}
                      </button>

                      <button
                        type="button"
                        onClick={() => handleStartEdit(sec.key, sec.body || '')}
                        className="px-3 py-1.5 rounded-lg border border-hair text-xs text-mute hover:text-ice hover:bg-white/5 transition-all flex items-center gap-1"
                      >
                        <Edit3 size={12} />
                        <span>Edit</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleVerifySection(sec.key, 'rejected')}
                        className="px-3 py-1.5 rounded-lg border border-hair text-xs text-mute hover:text-red-400 hover:bg-red-500/5 transition-all flex items-center gap-1"
                      >
                        <XCircle size={12} />
                        <span>Reject</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Differential Diagnosis Card */}
            {summary?.differential_considerations && (
              <div className="cell p-5 border-hair">
                <span className="text-xs font-semibold uppercase tracking-wider text-dim block pb-2 border-b border-hair">
                  Differential Considerations (AI Clinical Clues)
                </span>
                <pre className="mt-3 text-xs text-mute font-sans whitespace-pre-line leading-relaxed">
                  {summary.differential_considerations}
                </pre>
              </div>
            )}
          </div>

          {/* RIGHT COLUMN: Evidence & Audit Trail */}
          <div className="space-y-4">
            {/* Tabs */}
            <div className="flex border-b border-hair gap-1">
              <button
                onClick={() => setActiveTab('statements')}
                className={`pb-2.5 px-3 text-xs font-semibold transition-all border-b-2 ${
                  activeTab === 'statements'
                    ? 'border-cyan text-cyan'
                    : 'border-transparent text-dim hover:text-ice'
                }`}
              >
                Original Intake Transcript ({interview_transcript.length})
              </button>
              <button
                onClick={() => setActiveTab('documents')}
                className={`pb-2.5 px-3 text-xs font-semibold transition-all border-b-2 ${
                  activeTab === 'documents'
                    ? 'border-cyan text-cyan'
                    : 'border-transparent text-dim hover:text-ice'
                }`}
              >
                Uploaded Records & OCR ({documents.length})
              </button>
              <button
                onClick={() => setActiveTab('audit')}
                className={`pb-2.5 px-3 text-xs font-semibold transition-all border-b-2 ${
                  activeTab === 'audit'
                    ? 'border-cyan text-cyan'
                    : 'border-transparent text-dim hover:text-ice'
                }`}
              >
                Audit Trail ({audit_trail.length})
              </button>
            </div>

            {/* TAB 1: Original Patient Statements */}
            {activeTab === 'statements' && (
              <div className="cell p-4 space-y-3 max-h-[600px] overflow-y-auto">
                <div className="text-xs text-dim mb-2">
                  Verbatim record of patient responses at kiosk intake prior to consultation:
                </div>
                {interview_transcript.map((msg: any, idx: number) => (
                  <div
                    key={idx}
                    className={`p-3 rounded-xl border text-xs leading-relaxed ${
                      msg.sender === 'patient'
                        ? 'border-cyan/30 bg-cyan/5 text-ice ml-4'
                        : msg.sender === 'system'
                        ? 'border-amber-500/20 bg-amber-500/5 text-amber-200'
                        : 'border-hair bg-black/40 text-mute mr-4'
                    }`}
                  >
                    <div className="flex items-center justify-between text-[10px] text-dim mb-1 font-mono uppercase">
                      <span>{msg.sender === 'patient' ? patientCase.patient_name : 'MediKiosk AI'}</span>
                      <span>{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    {msg.text}
                  </div>
                ))}
              </div>
            )}

            {/* TAB 2: Uploaded Documents & OCR */}
            {activeTab === 'documents' && (
              <div className="cell p-4 space-y-4 max-h-[600px] overflow-y-auto">
                {documents.length === 0 ? (
                  <div className="p-8 text-center text-dim text-xs">
                    No documents uploaded by patient for this case.
                  </div>
                ) : (
                  documents.map((doc: any, dIdx: number) => (
                    <div key={dIdx} className="p-4 rounded-xl border border-hair bg-black/40 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <FileText size={16} className="text-cyan" />
                          <span className="text-xs font-medium text-ice">{doc.filename}</span>
                        </div>
                        <span className="chip text-[10px] border-cyan/30 text-cyan">
                          {doc.structured_data?.doc_type || 'Lab Record'}
                        </span>
                      </div>

                      {/* Extracted Labs */}
                      {doc.structured_data?.extracted_labs?.length > 0 && (
                        <div>
                          <span className="text-[10px] uppercase font-semibold text-dim block mb-1.5">
                            Extracted Lab Parameters:
                          </span>
                          <div className="space-y-1.5">
                            {doc.structured_data.extracted_labs.map((l: any, i: number) => (
                              <div
                                key={i}
                                className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02] border border-hair text-xs"
                              >
                                <span className="text-ice">{l.test}</span>
                                <div className="flex items-center gap-2">
                                  <strong className="text-ice">{l.value}</strong>
                                  <span
                                    className={`px-1.5 py-0.5 rounded text-[10px] ${
                                      l.status.includes('Critical')
                                        ? 'bg-red-500/20 text-red-300'
                                        : l.status.includes('High') || l.status.includes('Elevated')
                                        ? 'bg-amber-500/20 text-amber-300'
                                        : 'bg-white/5 text-dim'
                                    }`}
                                  >
                                    {l.status}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Raw Extracted Text */}
                      {doc.extracted_text && (
                        <div>
                          <span className="text-[10px] uppercase font-semibold text-dim block mb-1">
                            Original Document Excerpt:
                          </span>
                          <div className="p-2.5 rounded-lg bg-black/60 text-[11px] text-mute font-mono leading-relaxed border border-hair/50">
                            {doc.extracted_text}
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {/* TAB 3: Audit Trail */}
            {activeTab === 'audit' && (
              <div className="cell p-4 space-y-3 max-h-[600px] overflow-y-auto">
                <div className="text-xs text-dim mb-2">
                  Tamper-evident verification audit trail for regulatory compliance:
                </div>
                {audit_trail.length === 0 ? (
                  <div className="p-8 text-center text-dim text-xs">
                    No doctor modifications logged yet.
                  </div>
                ) : (
                  audit_trail.map((log: any, lIdx: number) => (
                    <div
                      key={lIdx}
                      className="p-3 rounded-xl border border-hair bg-black/40 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between text-dim">
                        <span className="font-semibold text-ice">{log.doctor_name || 'Dr. A. Menon'}</span>
                        <span className="font-mono text-[10px]">{new Date(log.timestamp).toLocaleString()}</span>
                      </div>
                      <div className="text-cyan text-[11px]">
                        Action: <strong>{log.action}</strong> ({log.section})
                      </div>
                      {log.notes && (
                        <div className="text-mute text-[11px] italic">
                          "{log.notes}"
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Doctor Finalize Action Card */}
            <div className="cell p-5 border-hairStrong space-y-3">
              <h3 className="text-sm font-semibold text-ice flex items-center gap-2">
                <Shield size={16} className="text-cyan" />
                <span>Physician Consultation Finalization</span>
              </h3>
              <textarea
                rows={2}
                value={doctorNotes}
                onChange={(e) => setDoctorNotes(e.target.value)}
                placeholder="Add final clinical notes, prescription recommendations, or instructions..."
                className="w-full rounded-xl border border-hair bg-black/60 p-3 text-xs text-ice placeholder-dim focus:border-cyan focus:outline-none"
              />
              <button
                type="button"
                onClick={handleFinalize}
                className="w-full btn btn-primary justify-center py-2.5 text-xs font-semibold shadow-lg group"
              >
                <span>Finalize & Sign Consultation Record</span>
                <CheckCircle2 size={15} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
