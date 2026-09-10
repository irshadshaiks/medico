const API_BASE = 'http://localhost:8000/api';

export function getAuthToken(): string | null {
  return localStorage.getItem('medikiosk_token');
}

export function setAuthToken(token: string) {
  localStorage.setItem('medikiosk_token', token);
}

export function clearAuthToken() {
  localStorage.removeItem('medikiosk_token');
  localStorage.removeItem('medikiosk_user');
}

export function getStoredUser(): any | null {
  const u = localStorage.getItem('medikiosk_user');
  return u ? JSON.parse(u) : null;
}

export function setStoredUser(user: any) {
  localStorage.setItem('medikiosk_user', JSON.stringify(user));
}

async function request(endpoint: string, options: RequestInit = {}) {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  const token = getAuthToken();
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API request failed');
  }

  return res.json();
}

export const api = {
  // Auth
  login: async (email: string, password: string) => {
    const res = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    if (res.token) {
      setAuthToken(res.token);
      setStoredUser(res.user);
    }
    return res;
  },

  register: async (data: { email: string; password: string; full_name: string; role?: string; phone?: string; age?: number; gender?: string }) => {
    const res = await request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (res.token) {
      setAuthToken(res.token);
      setStoredUser(res.user);
    }
    return res;
  },

  getMe: () => request('/auth/me'),

  // Intake & Languages
  getLanguages: () => request('/languages'),

  startIntake: (data: { patient_name: string; patient_age: number; patient_gender: string; language: string; consent_given: boolean }) =>
    request('/kiosk/start', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getKioskCase: (caseId: string) => request(`/kiosk/case/${caseId}`),

  respondInterview: (caseId: string, responseText: string) =>
    request('/kiosk/respond', {
      method: 'POST',
      body: JSON.stringify({ case_id: caseId, response_text: responseText }),
    }),

  uploadDocument: async (caseId: string, file: File) => {
    const formData = new FormData();
    formData.append('case_id', caseId);
    formData.append('file', file);
    return request('/documents/upload', {
      method: 'POST',
      body: formData,
    });
  },

  // Doctor Dashboard & Case File
  getDoctorQueue: (q?: string) => request(`/doctor/queue${q ? `?q=${encodeURIComponent(q)}` : ''}`),

  updatePriority: (caseId: string, priority: string, reason?: string) =>
    request('/doctor/priority', {
      method: 'POST',
      body: JSON.stringify({ case_id: caseId, priority, reason }),
    }),

  getDoctorCase: (caseId: string) => request(`/doctor/case/${caseId}`),

  verifySection: (caseId: string, section: string, status: string, newText?: string, notes?: string) =>
    request('/doctor/verify-section', {
      method: 'POST',
      body: JSON.stringify({ case_id: caseId, section, status, new_text: newText, notes }),
    }),

  finalizeCase: (caseId: string) =>
    request(`/doctor/finalize/${caseId}`, {
      method: 'POST',
    }),
};
