import { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Volume2,
  Upload,
  FileText,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  Send,
  User,
  Clock,
  Activity,
  ChevronRight,
  Home
} from 'lucide-react';
import { api } from '@/lib/api';

const INDIAN_LANGUAGES = [
  { code: 'en', name: 'English', native: 'English' },
  { code: 'hi', name: 'Hindi', native: 'हिन्दी' },
  { code: 'bn', name: 'Bengali', native: 'বাংলা' },
  { code: 'ta', name: 'Tamil', native: 'தமிழ்' },
  { code: 'te', name: 'Telugu', native: 'తెలుగు' },
  { code: 'mr', name: 'Marathi', native: 'मराठी' },
  { code: 'gu', name: 'Gujarati', native: 'ગુજરાતી' },
  { code: 'kn', name: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'ml', name: 'Malayalam', native: 'മലയാളം' },
  { code: 'pa', name: 'Punjabi', native: 'ਪੰਜਾਬੀ' },
  { code: 'or', name: 'Odia', native: 'ଓଡ଼ିଆ' },
];

interface Message {
  id: string;
  sender: 'ai' | 'patient' | 'system';
  text: string;
  options?: string[] | null;
  timestamp: string;
}

export function PatientIntake({ onComplete, onBackHome }: { onComplete: (caseId: string) => void; onBackHome: () => void }) {
  // Step flow: 1 = Consent & Language, 2 = Interview & Chat, 3 = Document Upload, 4 = Review & Submit
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);

  // Demographics & Consent
  const [selectedLang, setSelectedLang] = useState('en');
  const [patientName, setPatientName] = useState('Ravi Kumar');
  const [patientAge, setPatientAge] = useState<number>(54);
  const [patientGender, setPatientGender] = useState('Male');
  const [consentAgreed, setConsentAgreed] = useState(true);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  // Case & Chat state
  const [caseId, setCaseId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isAiTyping, setIsAiTyping] = useState(false);
  const [priorityData, setPriorityData] = useState<any>(null);

  // Documents state
  const [documents, setDocuments] = useState<any[]>([]);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Summary state
  const [summaryData, setSummaryData] = useState<any>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Auto scroll chat
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAiTyping]);

  // Voice simulation
  const toggleRecording = () => {
    if (!isRecording) {
      setIsRecording(true);
      // Simulate listening and picking up voice input
      const sampleVoiceInputs = [
        "I have heavy central chest pain radiating to my left arm since 6 AM",
        "It feels like a tight band around my chest and it is an 8 out of 10",
        "I have shortness of breath when I try to walk",
        "I take Metformin and Amlodipine regularly for diabetes and BP"
      ];
      const randomInput = sampleVoiceInputs[Math.floor(Math.random() * sampleVoiceInputs.length)];
      setTimeout(() => {
        setInputText(randomInput);
        setIsRecording(false);
      }, 2400);
    } else {
      setIsRecording(false);
    }
  };

  // Text-to-speech simulation
  const speakText = (text: string) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.95;
      setIsPlayingAudio(true);
      utterance.onend = () => setIsPlayingAudio(false);
      utterance.onerror = () => setIsPlayingAudio(false);
      window.speechSynthesis.speak(utterance);
    } else {
      setIsPlayingAudio(true);
      setTimeout(() => setIsPlayingAudio(false), 2000);
    }
  };

  // 1. Start Intake Session
  const handleStartSession = async () => {
    if (!consentAgreed) {
      alert('Please confirm the consent agreement to proceed with clinical intake.');
      return;
    }
    try {
      const res = await api.startIntake({
        patient_name: patientName,
        patient_age: patientAge,
        patient_gender: patientGender,
        language: selectedLang,
        consent_given: consentAgreed,
      });

      setCaseId(res.case_id);
      setMessages([res.first_message]);
      setStep(2);
    } catch (err: any) {
      alert(err.message || 'Failed to start intake session');
    }
  };

  // 2. Send Patient Response
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || !caseId) return;

    // Optimistically add patient message
    const pMsg: Message = {
      id: `p-${Date.now()}`,
      sender: 'patient',
      text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, pMsg]);
    setInputText('');
    setIsAiTyping(true);

    try {
      const res = await api.respondInterview(caseId, text);
      setIsAiTyping(false);
      if (res.ai_message) {
        setMessages((prev) => [...prev, res.ai_message]);
      }
      if (res.priority) {
        setPriorityData(res.priority);
      }
      if (res.is_completed) {
        // Automatically progress to document upload stage
        setTimeout(() => {
          setStep(3);
        }, 1500);
      }
    } catch (err: any) {
      setIsAiTyping(false);
      console.error(err);
    }
  };

  // 3. Document Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !caseId) return;

    setUploadingDoc(true);
    try {
      const res = await api.uploadDocument(caseId, file);
      setDocuments((prev) => [...prev, res]);
      // Update case data
      const caseData = await api.getKioskCase(caseId);
      if (caseData.summary) {
        setSummaryData(caseData.summary);
      }
      if (caseData.case) {
        setPriorityData({
          priority: caseData.case.priority,
          score: caseData.case.priority_score,
          label: caseData.case.priority_reason,
        });
      }
    } catch (err: any) {
      alert(err.message || 'Error uploading document');
    } finally {
      setUploadingDoc(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Upload sample diagnostic lab report simulation
  const handleUploadSampleDoc = async (docType: 'lab' | 'rx') => {
    if (!caseId) return;
    setUploadingDoc(true);

    let sampleContent = '';
    let sampleName = '';

    if (docType === 'lab') {
      sampleName = 'Blood_Work_12Mar2026.pdf';
      sampleContent = 'Metropolis Clinical Labs. Patient: ' + patientName + '. Fasting Blood Glucose: 168 mg/dL (High). HbA1c Glycated Hemoglobin: 8.2% (Critical High). Serum Creatinine: 1.1 mg/dL. BP 148/92 mmHg.';
    } else {
      sampleName = 'Prescription_DrBose_2025.pdf';
      sampleContent = 'Rx: Tab Metformin 500mg BD after meals. Tab Amlodipine 5mg OD morning. Indication: Type 2 Diabetes & Hypertension.';
    }

    const blob = new Blob([sampleContent], { type: 'application/pdf' });
    const file = new File([blob], sampleName, { type: 'application/pdf' });

    try {
      const res = await api.uploadDocument(caseId, file);
      setDocuments((prev) => [...prev, res]);
      const caseData = await api.getKioskCase(caseId);
      if (caseData.summary) setSummaryData(caseData.summary);
    } catch (err) {
      console.error(err);
    } finally {
      setUploadingDoc(false);
    }
  };

  // 4. View Final Summary
  const handleProceedToSummary = async () => {
    if (!caseId) return;
    try {
      const caseData = await api.getKioskCase(caseId);
      setSummaryData(caseData.summary);
      setPriorityData({
        priority: caseData.case.priority,
        score: caseData.case.priority_score,
        reasons: [caseData.case.priority_reason],
      });
      setStep(4);
    } catch (err: any) {
      alert(err.message || 'Error loading clinical summary');
    }
  };

  return (
    <div className="min-h-screen bg-void pt-20 pb-16 text-ice">
      {/* Top Breadcrumb & Return to Home */}
      <div className="shell max-w-5xl mb-6 flex items-center justify-between">
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
            <Sparkles size={14} />
            <span>MediKiosk Patient Intake</span>
          </div>
        </div>

        {/* Step Progress Tracker */}
        <div className="hidden sm:flex items-center gap-2 text-xs">
          {[
            { num: 1, label: 'Consent & Language' },
            { num: 2, label: 'AI Clinical Interview' },
            { num: 3, label: 'Documents & Lab OCR' },
            { num: 4, label: 'Clinical Draft' },
          ].map((s) => (
            <div
              key={s.num}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full border transition-all ${
                step === s.num
                  ? 'border-cyan bg-cyan/15 text-cyan font-medium'
                  : step > s.num
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                  : 'border-hair text-dim'
              }`}
            >
              <span>{s.num}.</span>
              <span>{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="shell max-w-5xl">
        {/* ================= STAGE 1: Language Consent & Patient Profile ================= */}
        {step === 1 && (
          <div className="cell p-8 lg:p-10 border-hairStrong max-w-3xl mx-auto shadow-2xl">
            <div className="flex items-center gap-3 text-cyan">
              <ShieldCheck size={28} />
              <h2 className="text-2xl font-display font-semibold text-ice">
                Language Selection & Clinical Consent
              </h2>
            </div>
            <p className="mt-2 text-sm text-mute leading-relaxed">
              MediKiosk assists attending physicians by gathering patient symptoms and extracting previous health records before consultation. Please choose your preferred language and confirm consent.
            </p>

            {/* Language grid */}
            <div className="mt-6">
              <label className="block text-xs font-semibold uppercase tracking-wider text-mute mb-2">
                1. Select Preferred Language (11 Indian Languages)
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
                {INDIAN_LANGUAGES.map((lang) => (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => setSelectedLang(lang.code)}
                    className={`flex flex-col items-start p-3 rounded-xl border text-left transition-all ${
                      selectedLang === lang.code
                        ? 'border-cyan bg-cyan/15 text-ice shadow-[0_0_20px_-5px_rgba(79,216,228,0.4)]'
                        : 'border-hair bg-[rgba(12,22,33,0.4)] text-mute hover:border-hairStrong hover:text-ice'
                    }`}
                  >
                    <span className="text-base font-semibold">{lang.native}</span>
                    <span className="text-xs text-dim">{lang.name}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Audio Consent Reader */}
            <div className="mt-6 p-4 rounded-xl border border-hair bg-[rgba(6,10,16,0.6)] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() =>
                    speakText(
                      'MediKiosk will conduct an interactive clinical interview in your chosen language and review previous medical records. This information will be structured directly for your attending physician.'
                    )
                  }
                  className="h-10 w-10 flex-none rounded-xl bg-cyan/20 border border-cyan/40 text-cyan grid place-items-center hover:bg-cyan/30 transition-all"
                  title="Listen to audio prompt"
                >
                  <Volume2 size={18} className={isPlayingAudio ? 'animate-bounce' : ''} />
                </button>
                <div>
                  <div className="text-sm font-medium text-ice">Audio Consent Voice Prompt</div>
                  <div className="text-xs text-dim">Tap to listen to the clinical consent read aloud</div>
                </div>
              </div>
              <span className="text-xs font-mono px-2 py-1 rounded bg-white/5 border border-hair text-mute uppercase">
                {selectedLang}
              </span>
            </div>

            {/* Demographics */}
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-mute mb-1">Patient Full Name</label>
                <input
                  type="text"
                  value={patientName}
                  onChange={(e) => setPatientName(e.target.value)}
                  className="w-full rounded-xl border border-hair bg-[rgba(6,10,16,0.7)] px-3.5 py-2.5 text-sm text-ice focus:border-cyan focus:outline-none"
                  placeholder="e.g. Ravi Kumar"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-mute mb-1">Age (Years)</label>
                <input
                  type="number"
                  value={patientAge}
                  onChange={(e) => setPatientAge(Number(e.target.value))}
                  className="w-full rounded-xl border border-hair bg-[rgba(6,10,16,0.7)] px-3.5 py-2.5 text-sm text-ice focus:border-cyan focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-mute mb-1">Gender</label>
                <select
                  value={patientGender}
                  onChange={(e) => setPatientGender(e.target.value)}
                  className="w-full rounded-xl border border-hair bg-[rgba(6,10,16,0.7)] px-3.5 py-2.5 text-sm text-ice focus:border-cyan focus:outline-none"
                >
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>

            {/* Consent Checkbox */}
            <div className="mt-6 flex items-start gap-3 p-3.5 rounded-xl border border-cyan/30 bg-cyan/5">
              <input
                type="checkbox"
                id="consentCheck"
                checked={consentAgreed}
                onChange={(e) => setConsentAgreed(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-hair bg-transparent text-cyan focus:ring-cyan"
              />
              <label htmlFor="consentCheck" className="text-xs text-mute leading-relaxed select-none cursor-pointer">
                I hereby grant consent for MediKiosk to record my symptoms and analyze previous clinical records for my attending doctor. I understand this does not replace physician consultation.
              </label>
            </div>

            <button
              type="button"
              onClick={handleStartSession}
              className="mt-6 w-full btn btn-primary btn-lg justify-center shadow-xl group"
            >
              Confirm Consent & Begin Interview
              <ArrowRight size={18} className="transition-transform group-hover:translate-x-1" />
            </button>
          </div>
        )}

        {/* ================= STAGE 2: Interactive AI Chat Interview ================= */}
        {step === 2 && (
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
            {/* Chat Screen */}
            <div className="cell p-0 overflow-hidden flex flex-col h-[75vh] border-hairStrong">
              {/* Chat Header */}
              <div className="p-4 border-b border-hair bg-[rgba(7,12,19,0.7)] flex items-center justify-between backdrop-blur-md">
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <div className="h-9 w-9 rounded-xl bg-cyan/20 border border-cyan/40 text-cyan grid place-items-center font-display font-semibold text-sm">
                      MK
                    </div>
                    <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-400 ring-2 ring-void" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-ice">MediKiosk Clinical Assistant</div>
                    <div className="text-xs text-dim">Pre-consultation history taking · {patientName}, {patientAge}y</div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setStep(3)}
                    className="btn btn-ghost py-1.5 px-3 text-xs text-cyan border border-cyan/30 rounded-lg hover:bg-cyan/10"
                  >
                    Skip to Documents →
                  </button>
                </div>
              </div>

              {/* Chat Message List */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={`flex flex-col ${m.sender === 'patient' ? 'items-end' : 'items-start'}`}
                  >
                    <div className="flex items-start gap-2.5 max-w-[85%]">
                      {m.sender === 'ai' && (
                        <div className="h-7 w-7 rounded-lg bg-cyan/20 border border-cyan/40 text-cyan text-xs grid place-items-center flex-none mt-1">
                          AI
                        </div>
                      )}
                      {m.sender === 'system' && (
                        <div className="h-7 w-7 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 text-xs grid place-items-center flex-none mt-1">
                          SYS
                        </div>
                      )}

                      <div
                        className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-md ${
                          m.sender === 'patient'
                            ? 'bg-gradient-to-br from-cyan-600 to-cyan-500 text-slate-950 font-medium rounded-tr-none'
                            : m.sender === 'system'
                            ? 'border border-amber-500/30 bg-amber-500/10 text-amber-200'
                            : 'border border-hair bg-[rgba(12,22,33,0.85)] text-ice rounded-tl-none'
                        }`}
                      >
                        {m.text}

                        {/* Read out loud button for AI message */}
                        {m.sender === 'ai' && (
                          <div className="mt-2 pt-2 border-t border-hair/50 flex items-center justify-between text-xs text-dim">
                            <button
                              type="button"
                              onClick={() => speakText(m.text)}
                              className="inline-flex items-center gap-1 text-cyan hover:underline"
                            >
                              <Volume2 size={12} />
                              <span>Listen</span>
                            </button>
                            <span className="text-[10px] text-dim">
                              {new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Quick Reply Chips */}
                    {m.options && m.options.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap gap-1.5 pl-9 max-w-full">
                        {m.options.map((opt, i) => (
                          <button
                            key={i}
                            onClick={() => handleSendMessage(opt)}
                            className="text-xs px-3 py-1.5 rounded-full border border-hairStrong bg-[rgba(143,182,196,0.08)] hover:bg-cyan/20 hover:border-cyan hover:text-ice text-mute transition-all text-left"
                          >
                            {opt}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {isAiTyping && (
                  <div className="flex items-center gap-2 text-dim text-xs pl-2">
                    <span className="h-2 w-2 rounded-full bg-cyan animate-pulse" />
                    <span>MediKiosk is analyzing your response...</span>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>

              {/* Chat Input Bar */}
              <div className="p-3 border-t border-hair bg-[rgba(7,12,19,0.85)]">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendMessage();
                  }}
                  className="flex items-center gap-2"
                >
                  {/* Mic Voice Button */}
                  <button
                    type="button"
                    onClick={toggleRecording}
                    className={`h-11 w-11 flex-none rounded-xl border transition-all grid place-items-center ${
                      isRecording
                        ? 'border-red-500 bg-red-500/20 text-red-400 animate-pulse'
                        : 'border-hair bg-white/5 text-mute hover:text-ice hover:border-cyan'
                    }`}
                    title={isRecording ? 'Listening...' : 'Tap to speak your answer'}
                  >
                    {isRecording ? <MicOff size={18} /> : <Mic size={18} />}
                  </button>

                  <input
                    type="text"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    placeholder={
                      isRecording
                        ? 'Listening to your voice...'
                        : 'Type your symptoms or select options above...'
                    }
                    className="flex-1 rounded-xl border border-hair bg-[rgba(6,10,16,0.7)] px-4 py-2.5 text-sm text-ice placeholder-dim focus:border-cyan focus:outline-none"
                  />

                  <button
                    type="submit"
                    disabled={!inputText.trim()}
                    className="h-11 px-4 rounded-xl bg-cyan font-medium text-slate-950 flex items-center justify-center gap-1.5 hover:bg-cyan-soft disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >
                    <span>Send</span>
                    <Send size={15} />
                  </button>
                </form>

                {isRecording && (
                  <div className="mt-2 flex items-center justify-center gap-2 text-xs text-red-400">
                    <span className="h-2 w-2 rounded-full bg-red-500 animate-ping" />
                    <span>Transcribing speech in real-time...</span>
                  </div>
                )}
              </div>
            </div>

            {/* Sidebar Context Card */}
            <div className="space-y-4">
              {/* Triage Preview */}
              <div className="cell p-5 border-hair">
                <div className="flex items-center justify-between text-xs font-semibold text-dim uppercase tracking-wider">
                  <span>Live Triage Status</span>
                  <Activity size={14} className="text-cyan" />
                </div>

                <div className="mt-3 p-3 rounded-xl border border-amber-500/30 bg-amber-500/10">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-amber-400 animate-ping" />
                    <span className="text-xs font-bold text-amber-300">
                      {priorityData ? priorityData.priority : 'EVALUATING INTAKE'}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-amber-200/80">
                    {priorityData?.label || priorityData?.primary_reason || 'Screening for cardiovascular and respiratory red flags.'}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-hair space-y-2 text-xs text-mute">
                  <div className="flex justify-between">
                    <span>Patient:</span>
                    <span className="text-ice font-medium">{patientName}, {patientAge}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Language:</span>
                    <span className="text-ice font-medium uppercase">{selectedLang}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Attending:</span>
                    <span className="text-ice font-medium">Dr. A. Menon</span>
                  </div>
                </div>
              </div>

              {/* Next Stage Button */}
              <button
                onClick={() => setStep(3)}
                className="w-full btn btn-primary justify-center py-3 text-sm font-semibold shadow-lg group"
              >
                Upload Medical Reports
                <ChevronRight size={16} className="transition-transform group-hover:translate-x-1" />
              </button>
            </div>
          </div>
        )}

        {/* ================= STAGE 3: Document Upload & Live OCR ================= */}
        {step === 3 && (
          <div className="cell p-8 max-w-3xl mx-auto border-hairStrong shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3 text-cyan">
                <Upload size={28} />
                <h2 className="text-2xl font-display font-semibold text-ice">
                  Upload Previous Reports & Prescriptions
                </h2>
              </div>
              <button
                onClick={() => setStep(2)}
                className="text-xs text-mute hover:text-ice"
              >
                ← Back to Interview
              </button>
            </div>
            <p className="mt-2 text-sm text-mute leading-relaxed">
              MediKiosk reads the prescriptions, blood test results, and discharge summaries you brought with you, automatically extracting medications and flagged abnormal lab values.
            </p>

            {/* Drag & drop upload area */}
            <div
              onClick={() => fileInputRef.current?.click()}
              className="mt-6 border-2 border-dashed border-hairStrong hover:border-cyan rounded-2xl p-8 text-center cursor-pointer bg-[rgba(6,10,16,0.5)] hover:bg-cyan/5 transition-all group"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.txt"
                onChange={handleFileUpload}
                className="hidden"
              />
              <div className="h-12 w-12 rounded-2xl bg-cyan/15 text-cyan mx-auto grid place-items-center group-hover:scale-110 transition-transform">
                <FileText size={24} />
              </div>
              <div className="mt-3 text-base font-medium text-ice">
                Click to browse or drop files here
              </div>
              <p className="mt-1 text-xs text-dim">
                Supports PDF, JPG, PNG reports (Lab results, Prescriptions, ECG, Discharge slips)
              </p>
              {uploadingDoc && (
                <div className="mt-3 text-xs text-cyan flex items-center justify-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-cyan animate-ping" />
                  <span>Extracting lab markers and medications with OCR...</span>
                </div>
              )}
            </div>

            {/* Quick Demo Upload Buttons */}
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="text-xs text-dim self-center mr-1">Quick Sample Data:</span>
              <button
                type="button"
                onClick={() => handleUploadSampleDoc('lab')}
                disabled={uploadingDoc}
                className="px-3 py-1.5 rounded-lg border border-hair bg-white/5 hover:bg-white/10 text-xs text-ice transition-colors flex items-center gap-1.5"
              >
                <span>🧪 Attach Lab Report (HbA1c 8.2%, FBS 168)</span>
              </button>
              <button
                type="button"
                onClick={() => handleUploadSampleDoc('rx')}
                disabled={uploadingDoc}
                className="px-3 py-1.5 rounded-lg border border-hair bg-white/5 hover:bg-white/10 text-xs text-ice transition-colors flex items-center gap-1.5"
              >
                <span>💊 Attach 2025 Prescription (Metformin + Amlodipine)</span>
              </button>
            </div>

            {/* Extracted Documents List */}
            {documents.length > 0 && (
              <div className="mt-6 space-y-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-mute">
                  Analyzed Documents ({documents.length})
                </div>
                {documents.map((doc, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl border border-hair bg-[rgba(12,22,33,0.7)] space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 size={16} className="text-emerald-400" />
                        <span className="text-sm font-medium text-ice">{doc.filename}</span>
                        <span className="chip text-[11px] border-cyan/30 text-cyan">
                          {doc.structured_data?.doc_type || 'Medical Record'}
                        </span>
                      </div>
                      <span className="text-xs text-dim font-mono">confidence 0.94</span>
                    </div>

                    {/* Labs extracted */}
                    {doc.structured_data?.extracted_labs?.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {doc.structured_data.extracted_labs.map((lab: any, lIdx: number) => (
                          <span
                            key={lIdx}
                            className={`chip text-xs ${
                              lab.status.includes('Critical')
                                ? 'border-red-500/40 bg-red-500/10 text-red-300'
                                : lab.status.includes('High') || lab.status.includes('Elevated')
                                ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
                                : 'border-hair text-mute'
                            }`}
                          >
                            <strong>{lab.test}:</strong> {lab.value} ({lab.status})
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Meds extracted */}
                    {doc.structured_data?.extracted_medications?.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {doc.structured_data.extracted_medications.map((med: string, mIdx: number) => (
                          <span key={mIdx} className="chip text-xs border-blue-500/30 text-blue-300">
                            💊 {med}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            <button
              type="button"
              onClick={handleProceedToSummary}
              className="mt-8 w-full btn btn-primary btn-lg justify-center shadow-xl group"
            >
              Synthesize AI Clinical Summary & Triage
              <ArrowRight size={18} className="transition-transform group-hover:translate-x-1" />
            </button>
          </div>
        )}

        {/* ================= STAGE 4: AI Summary & Submit to Doctor Queue ================= */}
        {step === 4 && (
          <div className="cell p-8 max-w-3xl mx-auto border-hairStrong shadow-2xl">
            {/* Urgency Badge Banner */}
            <div className="flex items-center justify-between p-4 rounded-xl border border-amber-500/40 bg-gradient-to-r from-amber-500/15 to-transparent">
              <div className="flex items-center gap-3">
                <span className="h-3 w-3 rounded-full bg-amber-400 animate-ping" />
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-amber-300">
                    Clinical Priority Assigned: {priorityData?.priority || 'CRITICAL'} (Score {priorityData?.score || 85}/100)
                  </div>
                  <div className="text-sm font-medium text-ice mt-0.5">
                    {priorityData?.reasons?.[0] || 'Suspected Acute Coronary Syndrome · Priority queue routing'}
                  </div>
                </div>
              </div>
              <span className="chip border-amber-500/40 text-amber-300">Priority Review</span>
            </div>

            {/* Clinical Summary Preview */}
            <div className="mt-6 rounded-xl border border-hair p-5 bg-[rgba(6,10,16,0.6)] space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-hair">
                <div className="flex items-center gap-2">
                  <FileText size={18} className="text-cyan" />
                  <h3 className="text-lg font-display font-medium text-ice">
                    Structured Clinical Summary (Draft)
                  </h3>
                </div>
                <span className="chip border-dashed border-amber-500/50 text-[#F5CE93]">
                  Draft — Subject to Doctor Verification
                </span>
              </div>

              <div className="grid gap-3 text-sm">
                <div>
                  <span className="text-xs font-semibold uppercase text-dim block">Chief Complaint</span>
                  <p className="text-ice mt-0.5">
                    {summaryData?.chief_complaint_summary || 'Central chest pain, 6 hours, radiating to the left arm, with breathlessness on exertion.'}
                  </p>
                </div>

                <div>
                  <span className="text-xs font-semibold uppercase text-dim block">History of Present Illness</span>
                  <p className="text-mute mt-0.5">
                    {summaryData?.hpi || '54-year-old male with Type 2 Diabetes and Hypertension presenting with sudden-onset heavy retrosternal chest pain radiating to left shoulder and arm. Severity 8/10.'}
                  </p>
                </div>

                <div>
                  <span className="text-xs font-semibold uppercase text-dim block">Past Medical History</span>
                  <p className="text-mute mt-0.5">
                    {summaryData?.past_medical_history || 'Type 2 diabetes noted in a 2025 prescription. Hypertension on the same script.'}
                  </p>
                </div>

                <div>
                  <span className="text-xs font-semibold uppercase text-dim block">Current Medications</span>
                  <p className="text-ice mt-0.5">
                    {summaryData?.current_medications || 'Metformin 500 mg twice daily, Amlodipine 5 mg once daily.'}
                  </p>
                </div>

                <div>
                  <span className="text-xs font-semibold uppercase text-dim block">Lab & Diagnostic Findings</span>
                  <p className="text-ice mt-0.5">
                    {summaryData?.lab_findings || 'HbA1c 8.2% on 12 Mar 2026 (confidence 0.94); Fasting Blood Sugar 168 mg/dL; BP 148/92 mmHg.'}
                  </p>
                </div>

                <div>
                  <span className="text-xs font-semibold uppercase text-dim block">Red Flag Signs Flagged</span>
                  <p className="text-amber-300 mt-0.5">
                    {summaryData?.red_flags || 'Breathlessness reported with chest pain — routed to the doctor\'s priority queue.'}
                  </p>
                </div>
              </div>

              <div className="pt-3 border-t border-hair flex flex-wrap gap-2">
                <span className="chip border-cyan/30 text-cyan">Complaint — patient direct</span>
                <span className="chip border-blue-500/30 text-blue-300">Meds — uploaded prescription</span>
                <span className="chip border-blue-500/30 text-blue-300">HbA1c — pathology lab report</span>
                <span className="chip border-amber-500/30 text-amber-300">Triage — automated priority</span>
              </div>
            </div>

            {/* Submission Actions */}
            <div className="mt-6 flex flex-col sm:flex-row gap-3">
              <button
                type="button"
                onClick={() => onComplete(caseId || 'case-rk-001')}
                className="flex-1 btn btn-primary btn-lg justify-center shadow-xl group"
              >
                Submit File to Doctor's Queue
                <ArrowRight size={18} className="transition-transform group-hover:translate-x-1" />
              </button>
              <button
                type="button"
                onClick={() => onComplete(caseId || 'case-rk-001')}
                className="btn btn-lg justify-center border-hairStrong hover:bg-white/5"
              >
                View in Doctor Queue
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
