import { useState } from 'react';
import { X, Stethoscope, User, Lock, Mail, ArrowRight, Sparkles } from 'lucide-react';
import { api } from '@/lib/api';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (role: string) => void;
}

export function LoginModal({ isOpen, onClose, onSuccess }: LoginModalProps) {
  const [isRegister, setIsRegister] = useState(false);
  const [role, setRole] = useState<'doctor' | 'patient'>('doctor');
  const [email, setEmail] = useState('doctor@medikiosk.in');
  const [password, setPassword] = useState('doctor123');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleQuickFill = (targetRole: 'doctor' | 'patient') => {
    setRole(targetRole);
    setIsRegister(false);
    setError(null);
    if (targetRole === 'doctor') {
      setEmail('doctor@medikiosk.in');
      setPassword('doctor123');
    } else {
      setEmail('ravi.kumar@example.com');
      setPassword('patient123');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (isRegister) {
        const res = await api.register({
          email,
          password,
          full_name: fullName || (role === 'doctor' ? 'Dr. Physician' : 'Patient User'),
          role,
        });
        onSuccess(res.user?.role || role);
      } else {
        const res = await api.login(email, password);
        onSuccess(res.user?.role || role);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/75 backdrop-blur-md transition-all">
      <div
        className="relative w-full max-w-md rounded-2xl border border-hairStrong bg-gradient-to-b from-[rgba(14,24,38,0.95)] to-[rgba(7,12,19,0.95)] p-6 shadow-[0_40px_100px_-20px_rgba(0,0,0,0.95)] backdrop-blur-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 p-1.5 text-mute hover:text-ice hover:bg-white/5 rounded-lg transition-colors"
          title="Close modal"
        >
          <X size={18} />
        </button>

        {/* Title & badge */}
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan">
          <Sparkles size={14} />
          <span>MediKiosk Portal</span>
        </div>
        <h2 className="mt-1 text-2xl font-display font-semibold text-ice">
          {isRegister ? 'Create Account' : 'Welcome Back'}
        </h2>
        <p className="mt-1 text-sm text-mute">
          Access the clinical triage queue or pre-consultation intake.
        </p>

        {/* Role toggle */}
        <div className="mt-5 grid grid-cols-2 gap-2 p-1 rounded-xl bg-[rgba(6,10,16,0.6)] border border-hair">
          <button
            type="button"
            onClick={() => handleQuickFill('doctor')}
            className={`flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all ${
              role === 'doctor'
                ? 'bg-cyan/15 text-cyan border border-cyan/30 shadow-sm'
                : 'text-mute hover:text-ice'
            }`}
          >
            <Stethoscope size={16} />
            <span>Doctor</span>
          </button>
          <button
            type="button"
            onClick={() => handleQuickFill('patient')}
            className={`flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all ${
              role === 'patient'
                ? 'bg-cyan/15 text-cyan border border-cyan/30 shadow-sm'
                : 'text-mute hover:text-ice'
            }`}
          >
            <User size={16} />
            <span>Patient</span>
          </button>
        </div>

        {/* Quick 1-click test pills */}
        <div className="mt-3 flex items-center justify-between text-xs text-dim">
          <span>Quick Demo Access:</span>
          <div className="flex gap-1.5">
            <button
              type="button"
              onClick={() => handleQuickFill('doctor')}
              className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 text-ice border border-hair transition-colors"
            >
              Dr. Menon
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill('patient')}
              className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 text-ice border border-hair transition-colors"
            >
              Ravi Kumar
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-3 p-2.5 rounded-lg border border-red-500/30 bg-red-500/10 text-xs text-red-200">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          {isRegister && (
            <div>
              <label className="block text-xs font-medium text-mute mb-1">Full Name</label>
              <div className="relative">
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder={role === 'doctor' ? 'Dr. Sarah Jenkins' : 'Rajesh Verma'}
                  className="w-full rounded-xl border border-hair bg-[rgba(6,10,16,0.7)] px-3.5 py-2.5 text-sm text-ice placeholder-dim focus:border-cyan focus:outline-none"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-mute mb-1">Email Address</label>
            <div className="relative flex items-center">
              <Mail size={16} className="absolute left-3.5 text-dim pointer-events-none" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@hospital.org"
                className="w-full rounded-xl border border-hair bg-[rgba(6,10,16,0.7)] pl-10 pr-3.5 py-2.5 text-sm text-ice placeholder-dim focus:border-cyan focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-mute mb-1">Password</label>
            <div className="relative flex items-center">
              <Lock size={16} className="absolute left-3.5 text-dim pointer-events-none" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl border border-hair bg-[rgba(6,10,16,0.7)] pl-10 pr-3.5 py-2.5 text-sm text-ice placeholder-dim focus:border-cyan focus:outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 btn btn-primary justify-center py-2.5 text-sm font-semibold shadow-lg group"
          >
            {loading ? 'Authenticating...' : isRegister ? 'Register & Continue' : `Sign In as ${role === 'doctor' ? 'Doctor' : 'Patient'}`}
            <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
          </button>
        </form>

        <div className="mt-4 pt-3 border-t border-hair flex items-center justify-between text-xs text-mute">
          <button
            type="button"
            onClick={() => setIsRegister(!isRegister)}
            className="text-cyan hover:underline"
          >
            {isRegister ? 'Already have an account? Sign In' : "Don't have an account? Register"}
          </button>
          {role === 'patient' && (
            <button
              type="button"
              onClick={() => {
                onSuccess('patient');
                onClose();
              }}
              className="text-dim hover:text-ice transition-colors"
            >
              Skip to Kiosk →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
