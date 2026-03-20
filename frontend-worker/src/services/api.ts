// Phase 1: No backend API connectivity needed.
// This file is kept as a placeholder for Phase 2 integration.

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

// API functions will be implemented in Phase 2.
export const api = {};
