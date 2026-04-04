const API_BASE = "http://localhost:8000";

export type WorkerPayload = {
  name: string;
  phone: string;
  email?: string;
  city: string;
  persona_type: string;
  platform_name: string;
  avg_weekly_income: number;
  primary_zone: string;
  shift_type: string;
  gps_enabled: boolean;
  payout_upi: string;
};

export type RiskQuotePayload = {
  worker_id: number;
  city: string;
  rain_risk: number;
  flood_risk: number;
  aqi_risk: number;
  closure_risk: number;
  shift_exposure: number;
};

async function request(url: string, options?: RequestInit) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  // Auth
  sendOtp: (phone: string) =>
    request(`${API_BASE}/auth/send-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone }),
    }),
  verifyOtp: (phone: string, otp: string) =>
    request(`${API_BASE}/auth/verify-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, otp }),
    }),

  // Workers
  createProfile: (data: WorkerPayload) =>
    request(`${API_BASE}/workers/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  getProfile: (workerId: number) =>
    request(`${API_BASE}/workers/profile/${workerId}`),

  // Risk
  getRiskQuote: (data: RiskQuotePayload) =>
    request(`${API_BASE}/risk/quote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  /** Live weather + AQI → ML weekly premium in one call (preferred for onboarding). */
  getRiskQuoteLive: (workerId: number) =>
    request(`${API_BASE}/risk/quote-live`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ worker_id: workerId }),
    }),
  getLiveRiskFactors: (city: string) =>
    request(`${API_BASE}/risk/live-factors/${encodeURIComponent(city)}`),

  // Policies
  getPolicyQuote: (workerId: number) =>
    request(`${API_BASE}/policies/quote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ worker_id: workerId }),
    }),
  createPolicy: (data: any) =>
    request(`${API_BASE}/policies/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  getPolicies: (workerId: number) =>
    request(`${API_BASE}/policies/${workerId}`),

  // Claims
  getClaims: (workerId: number) =>
    request(`${API_BASE}/claims/${workerId}`),
  getClaimsSummary: (workerId: number) =>
    request(`${API_BASE}/claims/summary/${workerId}`),
  processClaim: (claimId: number) =>
    request(`${API_BASE}/claims/process/${claimId}`, { method: "POST" }),

  getShiftRecommendation: (workerId: number) =>
    request(`${API_BASE}/shift-guardian/recommendation/${workerId}`),

  // Events
  ingestWeather: (data: any) =>
    request(`${API_BASE}/events/ingest/weather`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  ingestAqi: (data: any) =>
    request(`${API_BASE}/events/ingest/aqi`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  ingestClosure: (data: any) =>
    request(`${API_BASE}/events/ingest/closure`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  ingestPlatformOutage: (data: any) =>
    request(`${API_BASE}/events/ingest/platform-outage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  ingestFlood: (data: any) =>
    request(`${API_BASE}/events/ingest/flood`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  checkLiveEvents: (city: string) =>
    request(`${API_BASE}/events/check-live/${encodeURIComponent(city)}`),
};
