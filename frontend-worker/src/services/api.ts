const API_BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000").replace(/\/+$/, "");

export type WorkerPayload = {
  name: string;
  phone: string;
  email?: string;
  city: string;
  persona_type: string;
  platform_name: string;
  platform_names: string[];
  avg_weekly_income: number;
  primary_zone: string;
  shift_type: string;
  gps_enabled: boolean;
  payout_upi: string;
  gender?: string;
};

export type WorkerLocationPayload = {
  city: string;
  zone_name: string;
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

export type EventIngestPayload = {
  event_type: string;
  zone_name: string;
  started_at: string;
  ended_at: string;
  severity?: string;
  source_name?: string;
  source_payload?: Record<string, unknown>;
  worker_id?: number;
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
  updateWorkerLocation: (workerId: number, data: WorkerLocationPayload) =>
    request(`${API_BASE}/workers/profile/${workerId}/location`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  // Risk
  getRiskQuote: (data: RiskQuotePayload) =>
    request(`${API_BASE}/risk/quote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
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
  getQuotePlans: (workerId: number) =>
    request(`${API_BASE}/policies/quote-plans?worker_id=${workerId}`, {
      method: "POST",
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
  raiseClaimDispute: (claimId: number, reason: string) =>
    request(`${API_BASE}/claims/dispute/${claimId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    }),

  // Shift Guardian
  getShiftRecommendation: (workerId: number) =>
    request(`${API_BASE}/shift-guardian/recommendation/${workerId}`),

  // Events
  ingestWeather: (data: EventIngestPayload) =>
    request(`${API_BASE}/events/ingest/weather`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  ingestAqi: (data: EventIngestPayload) =>
    request(`${API_BASE}/events/ingest/aqi`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  ingestClosure: (data: EventIngestPayload) =>
    request(`${API_BASE}/events/ingest/closure`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  ingestPlatformOutage: (data: EventIngestPayload) =>
    request(`${API_BASE}/events/ingest/platform-outage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  ingestFlood: (data: EventIngestPayload) =>
    request(`${API_BASE}/events/ingest/flood`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  checkLiveEvents: (city: string) =>
    request(`${API_BASE}/events/check-live/${encodeURIComponent(city)}`),

  // Phase 3: Payouts
  getPayouts: (workerId: number) =>
    request(`${API_BASE}/payouts/${workerId}`),
  initiatePayout: (claimId: number) =>
    request(`${API_BASE}/payouts/initiate/${claimId}`, { method: "POST" }),

  // Phase 3: Fraud
  evaluateFraud: (claimId: number) =>
    request(`${API_BASE}/fraud/evaluate/${claimId}`, { method: "POST" }),
  getFraudFlags: () =>
    request(`${API_BASE}/fraud/flags`),

  // Phase 3: Analytics / Admin
  getAnalyticsKpis: (filters?: { city?: string; plan?: string }) => {
    const p = new URLSearchParams();
    if (filters?.city) p.set("city", filters.city);
    if (filters?.plan) p.set("plan", filters.plan);
    const qs = p.toString();
    return request(`${API_BASE}/analytics/kpis${qs ? `?${qs}` : ""}`);
  },
  getZoneHeatmap: () =>
    request(`${API_BASE}/analytics/zone-heatmap`),
  getClaimsByTrigger: (filters?: { city?: string; plan?: string }) => {
    const p = new URLSearchParams();
    if (filters?.city) p.set("city", filters.city);
    if (filters?.plan) p.set("plan", filters.plan);
    const qs = p.toString();
    return request(`${API_BASE}/analytics/claims-by-trigger${qs ? `?${qs}` : ""}`);
  },
  getFraudOverview: (filters?: { city?: string; plan?: string }) => {
    const p = new URLSearchParams();
    if (filters?.city) p.set("city", filters.city);
    if (filters?.plan) p.set("plan", filters.plan);
    const qs = p.toString();
    return request(`${API_BASE}/analytics/fraud-overview${qs ? `?${qs}` : ""}`);
  },
  getPredictions: (city: string) =>
    request(`${API_BASE}/analytics/predictions?city=${encodeURIComponent(city)}`),
  getWorkerProtection: (workerId: number) =>
    request(`${API_BASE}/analytics/worker-protection/${workerId}`),
  getPayoutsLedger: (filters?: { city?: string; plan?: string }) => {
    const p = new URLSearchParams();
    if (filters?.city) p.set("city", filters.city);
    if (filters?.plan) p.set("plan", filters.plan);
    const qs = p.toString();
    return request(`${API_BASE}/analytics/payouts-ledger${qs ? `?${qs}` : ""}`);
  },
  getFinancialProof: (city: string) =>
    request(`${API_BASE}/analytics/financial-proof?city=${encodeURIComponent(city)}`),
  getComplianceChecklist: () =>
    request(`${API_BASE}/analytics/compliance-checklist`),
  getWorkersTable: (filters?: { city?: string; plan?: string }) => {
    const p = new URLSearchParams();
    if (filters?.city) p.set("city", filters.city);
    if (filters?.plan) p.set("plan", filters.plan);
    const qs = p.toString();
    return request(`${API_BASE}/analytics/workers-table${qs ? `?${qs}` : ""}`);
  },
  getWeeklyTrends: (filters?: { city?: string; plan?: string }) => {
    const p = new URLSearchParams();
    if (filters?.city) p.set("city", filters.city);
    if (filters?.plan) p.set("plan", filters.plan);
    const qs = p.toString();
    return request(`${API_BASE}/analytics/weekly-trends${qs ? `?${qs}` : ""}`);
  },
  getPlanDistribution: (city?: string) => {
    const qs = city ? `?city=${encodeURIComponent(city)}` : "";
    return request(`${API_BASE}/analytics/plan-distribution${qs}`);
  },

  // Phase 3: WhatsApp notifications
  getWhatsappStatus: () =>
    request(`${API_BASE}/notifications/whatsapp/status`),
  testWhatsapp: (phone: string, message?: string) =>
    request(`${API_BASE}/notifications/whatsapp/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, message }),
    }),
  sendPolicyWhatsapp: (workerId: number) =>
    request(`${API_BASE}/notifications/whatsapp/policy-activated/${workerId}`, { method: "POST" }),
  sendShiftGuardianWhatsapp: (workerId: number) =>
    request(`${API_BASE}/notifications/whatsapp/shift-guardian/${workerId}`, { method: "POST" }),
};
