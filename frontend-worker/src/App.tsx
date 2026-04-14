import { useState, useEffect, useCallback } from "react";
import { api, WorkerPayload } from "./services/api";

type View = "landing" | "otp" | "register" | "quote" | "dashboard" | "admin";

type DashboardSection = "home" | "policy" | "claims" | "live";
type AdminSection = "overview" | "claims" | "fraud" | "predictions" | "payouts";

function App() {
  const [view, setView] = useState<View>("landing");
  const [dashboardSection, setDashboardSection] = useState<DashboardSection>("home");
  const [workerId, setWorkerId] = useState<number | null>(null);
  const [profile, setProfile] = useState<any>(null);
  const [riskQuote, setRiskQuote] = useState<any>(null);
  const [plansQuote, setPlansQuote] = useState<any>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("standard");
  /** Snapshot from /risk/quote-live (live weather + AQI used for ML inputs). */
  const [quoteLiveFactors, setQuoteLiveFactors] = useState<any>(null);
  const [policies, setPolicies] = useState<any[]>([]);
  const [claims, setClaims] = useState<any[]>([]);
  const [claimsSummary, setClaimsSummary] = useState<any>(null);
  const [liveRisk, setLiveRisk] = useState<any>(null);

  // OTP state
  const [phone, setPhone] = useState("9876543210");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);

  // Form state
  const [formData, setFormData] = useState<WorkerPayload>({
    name: "",
    phone: "",
    city: "Bengaluru",
    persona_type: "grocery",
    platform_name: "Zepto",
    avg_weekly_income: 3500,
    primary_zone: "HSR Layout",
    shift_type: "full_day",
    gps_enabled: true,
    payout_upi: "",
  });

  const [loading, setLoading] = useState(false);
  const [triggerLoading, setTriggerLoading] = useState<string | null>(null);
  const [simulatorLastResult, setSimulatorLastResult] = useState<any>(null);
  /** 0–4 = step in progress / highlighting; 5 = all steps complete (mock claim pipeline animation). */
  const [simPipelineStep, setSimPipelineStep] = useState<number | null>(null);
  const [shiftRec, setShiftRec] = useState<any>(null);
  const [shiftRecLoading, setShiftRecLoading] = useState(false);
  const [waConfigured, setWaConfigured] = useState<boolean | null>(null);

  // Phase 3 state
  const [workerProtection, setWorkerProtection] = useState<any>(null);
  const [adminSection, setAdminSection] = useState<AdminSection>("overview");
  const [adminKpis, setAdminKpis] = useState<any>(null);
  const [adminFraud, setAdminFraud] = useState<any>(null);
  const [adminPredictions, setAdminPredictions] = useState<any>(null);
  const [adminClaimsByTrigger, setAdminClaimsByTrigger] = useState<any[]>([]);
  const [adminPayoutsLedger, setAdminPayoutsLedger] = useState<any[]>([]);
  const [adminLoading, setAdminLoading] = useState(false);

  // Dashboard data refresh
  const fetchDashboardData = useCallback(async () => {
    if (!workerId) return;
    try {
      const [p, c, s, wp] = await Promise.all([
        api.getPolicies(workerId),
        api.getClaims(workerId),
        api.getClaimsSummary(workerId),
        api.getWorkerProtection(workerId),
      ]);
      setPolicies(p);
      setClaims(c);
      setClaimsSummary(s);
      setWorkerProtection(wp);
    } catch (e) {
      console.error(e);
    }
  }, [workerId]);

  // Refresh live risk factors
  const fetchLiveRisk = useCallback(async () => {
    if (!profile?.city) return;
    try {
      const r = await api.getLiveRiskFactors(profile.city);
      setLiveRisk(r);
    } catch (e) {
      console.error(e);
    }
  }, [profile?.city]);

  const fetchShiftRecommendation = useCallback(async () => {
    if (!workerId) return;
    setShiftRecLoading(true);
    try {
      const rec = await api.getShiftRecommendation(workerId);
      setShiftRec(rec);
    } catch (e) {
      console.error(e);
    } finally {
      setShiftRecLoading(false);
    }
  }, [workerId]);

  useEffect(() => {
    let interval: number;
    if (view === "dashboard" && workerId) {
      fetchDashboardData();
      fetchLiveRisk();
      interval = window.setInterval(() => {
        fetchDashboardData();
        fetchLiveRisk();
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [view, workerId, fetchDashboardData, fetchLiveRisk]);

  useEffect(() => {
    api.getWhatsappStatus().then(r => setWaConfigured(r.configured)).catch(() => setWaConfigured(false));
  }, []);

  useEffect(() => {
    if (simPipelineStep === null) return;
    if (simPipelineStep >= 5) return;
    const t = window.setTimeout(() => setSimPipelineStep(s => (s === null ? null : s + 1)), 780);
    return () => window.clearTimeout(t);
  }, [simPipelineStep]);

  // ── OTP Handlers ──
  const handleSendOtp = async () => {
    setLoading(true);
    try {
      await api.sendOtp(phone);
      setOtpSent(true);
    } catch { /* mock always succeeds */ }
    finally { setLoading(false); }
  };

  const handleVerifyOtp = async () => {
    setLoading(true);
    try {
      const res = await api.verifyOtp(phone, otp);
      if (res.status === "verified") {
        setFormData(f => ({ ...f, phone }));
        setView("register");
      } else {
        alert("Invalid OTP. Use 123456.");
      }
    } catch { alert("Verification failed"); }
    finally { setLoading(false); }
  };

  // ── Register Handler ──
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.createProfile({
        ...formData,
        avg_weekly_income: Number(formData.avg_weekly_income),
      });
      setWorkerId(res.worker_id);
      const p = await api.getProfile(res.worker_id);
      setProfile(p);

      // Load quote and all plan tiers together for selection UX.
      const [quote, allPlans] = await Promise.all([
        api.getRiskQuoteLive(res.worker_id),
        api.getQuotePlans(res.worker_id),
      ]);
      setRiskQuote(quote);
      setPlansQuote(allPlans);
      setSelectedPlanId("standard");
      setQuoteLiveFactors(quote.live_factors ?? null);
      setView("quote");
    } catch (err) {
      alert("Registration failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshQuote = async () => {
    if (!workerId) return;
    setLoading(true);
    try {
      const [quote, allPlans] = await Promise.all([
        api.getRiskQuoteLive(workerId),
        api.getQuotePlans(workerId),
      ]);
      setRiskQuote(quote);
      setPlansQuote(allPlans);
      setQuoteLiveFactors(quote.live_factors ?? null);
    } catch {
      alert("Could not refresh quote — check API connection.");
    } finally {
      setLoading(false);
    }
  };

  // ── Subscribe ──
  const handleSubscribe = async () => {
    if (!workerId || !plansQuote?.plans?.length) return;
    const selectedPlan =
      plansQuote.plans.find((p: any) => p.plan_id === selectedPlanId) ||
      plansQuote.plans.find((p: any) => p.plan_id === "standard") ||
      plansQuote.plans[0];
    if (!selectedPlan) return;
    setLoading(true);
    try {
      await api.createPolicy({
        worker_id: workerId,
        plan_id: selectedPlan.plan_id,
        premium_weekly: selectedPlan.premium_weekly,
        max_weekly_payout: selectedPlan.max_weekly_payout,
        covered_events: ["heavy_rain", "flood", "aqi_severe", "curfew", "platform_outage"],
        auto_renew: true,
      });
      setView("dashboard");
    } catch {
      alert("Policy activation failed");
    } finally {
      setLoading(false);
    }
  };

  // ── Trigger Handler ──
  const handleTrigger = async (type: string) => {
    if (!profile?.zone_name) {
      alert("Zone not loaded — refresh the dashboard or re-register.");
      return;
    }
    setTriggerLoading(type);
    setSimulatorLastResult(null);
    setSimPipelineStep(null);
    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 3600000);
    const twoHoursAgo = new Date(now.getTime() - 7200000);
    try {
      let res: any;
      switch (type) {
        case "rain":
          res = await api.ingestWeather({
            event_type: "heavy_rain",
            zone_name: profile.zone_name,
            started_at: oneHourAgo.toISOString(),
            ended_at: now.toISOString(),
            severity: "severe",
            source_name: "Mock Weather Sensor",
            source_payload: { rainfall_mm: 62.5, wind_kmh: 45 },
            worker_id: workerId ?? undefined,
          });
          break;
        case "flood":
          res = await api.ingestFlood({
            event_type: "flood",
            zone_name: profile.zone_name,
            started_at: twoHoursAgo.toISOString(),
            ended_at: now.toISOString(),
            severity: "severe",
            source_name: "Mock Flood Sensor",
            source_payload: { water_level_cm: 35 },
            worker_id: workerId ?? undefined,
          });
          break;
        case "aqi":
          res = await api.ingestAqi({
            event_type: "aqi_severe",
            zone_name: profile.zone_name,
            started_at: oneHourAgo.toISOString(),
            ended_at: now.toISOString(),
            severity: "severe",
            source_name: "Mock AQI Monitor",
            source_payload: { aqi: 380, dominant_pollutant: "pm25" },
            worker_id: workerId ?? undefined,
          });
          break;
        case "closure":
          res = await api.ingestClosure({
            event_type: "curfew",
            zone_name: profile.zone_name,
            started_at: twoHoursAgo.toISOString(),
            ended_at: now.toISOString(),
            severity: "high",
            source_name: "Mock Authority Alert",
            worker_id: workerId ?? undefined,
          });
          break;
        case "outage":
          res = await api.ingestPlatformOutage({
            event_type: "platform_outage",
            zone_name: profile.zone_name,
            started_at: oneHourAgo.toISOString(),
            ended_at: now.toISOString(),
            severity: "moderate",
            source_name: "Mock Platform Monitor",
            source_payload: { platform: profile.platform_name, downtime_min: 45 },
            worker_id: workerId ?? undefined,
          });
          break;
        default:
          return;
      }
      setSimulatorLastResult(res);
      if (!res.deduplicated) {
        window.setTimeout(() => {
          setSimPipelineStep(workerId != null ? 0 : null);
        }, 100);
      }
      await fetchDashboardData();
    } catch (err) {
      console.error(err);
      setSimPipelineStep(null);
      setSimulatorLastResult({
        error: true,
        message: err instanceof Error ? err.message : "Simulator request failed",
      });
    } finally {
      setTimeout(() => setTriggerLoading(null), 600);
    }
  };

  // ── Helpers ──
  const eventIcon: Record<string, string> = {
    heavy_rain: "🌧️", flood: "🌊", aqi_severe: "😷",
    curfew: "🚧", platform_outage: "📡", parametric_income_loss: "📋",
  };
  const statusColor = (s: string) =>
    s === "paid" ? "success" : s === "approved" ? "success" : s === "fraud_check" ? "pending" : "";

  const fetchAdminData = useCallback(async () => {
    setAdminLoading(true);
    try {
      const city = profile?.city || "Bengaluru";
      const [kpi, fraud, pred, triggers, ledger] = await Promise.all([
        api.getAnalyticsKpis(),
        api.getFraudOverview(),
        api.getPredictions(city),
        api.getClaimsByTrigger(),
        api.getPayoutsLedger(),
      ]);
      setAdminKpis(kpi);
      setAdminFraud(fraud);
      setAdminPredictions(pred);
      setAdminClaimsByTrigger(triggers);
      setAdminPayoutsLedger(ledger);
    } catch (e) {
      console.error(e);
    } finally {
      setAdminLoading(false);
    }
  }, [profile?.city]);

  useEffect(() => {
    if (view === "admin") {
      fetchAdminData();
    }
  }, [view, fetchAdminData]);

  const formatTime = (iso: string) =>
    new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  const formatPolicyDate = (iso: string) =>
    new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

  const scrollToDashboardSection = (section: DashboardSection) => {
    setDashboardSection(section);
    const id =
      section === "home"
        ? "dash-home"
        : section === "policy"
          ? "dash-policy"
          : section === "claims"
            ? "dash-claims"
            : "dash-live";
    requestAnimationFrame(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  // ═══════════════════════════════════════════════════════════════
  //  VIEW: LANDING
  // ═══════════════════════════════════════════════════════════════
  if (view === "landing") {
    return (
      <div className="landing">
        <header className="landing-nav">
          <div className="landing-brand">
            <svg className="landing-brand-mark" width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
              <path
                d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3z"
                fill="hsl(22, 95%, 55%)"
                stroke="hsl(22, 95%, 48%)"
                strokeWidth="1.2"
              />
            </svg>
            <span className="landing-brand-text">SurakshaShift</span>
          </div>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <button type="button" className="landing-signin" style={{ opacity: 0.7, fontSize: "0.82rem" }} onClick={() => { setView("admin"); fetchAdminData(); }}>
              Admin Portal
            </button>
            <button type="button" className="landing-signin" onClick={() => setView("otp")}>
              Sign in
            </button>
          </div>
        </header>

        <main className="landing-main">
          <section className="landing-hero">
            <p className="landing-eyebrow">Parametric income protection</p>
            <h1 className="landing-headline">
              Cover for every shift.
              <span className="landing-headline-accent"> Peace for every ride.</span>
            </h1>
            <p className="landing-lede">
              Weekly plans built for India&apos;s delivery workforce — rain, flood, air quality, closures, and platform outages
              matched to <strong>your zone</strong>, not just your city.
            </p>
            <div className="landing-hero-ctas">
              <button type="button" className="landing-btn-primary" onClick={() => setView("otp")}>
                Get started
              </button>
              <p className="landing-hero-note">Takes under a minute · Demo OTP 123456</p>
            </div>
          </section>

          <section className="landing-features" aria-label="Why SurakshaShift">
            <div className="landing-feature">
              <div className="landing-feature-icon" aria-hidden>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3z"
                    stroke="hsl(22, 95%, 48%)"
                    strokeWidth="1.5"
                    fill="hsla(22, 95%, 55%, 0.12)"
                  />
                </svg>
              </div>
              <h2 className="landing-feature-title">Zone-sharp triggers</h2>
              <p className="landing-feature-copy">Disruptions are verified against your delivery catchment — lower basis risk than city-wide products.</p>
            </div>
            <div className="landing-feature">
              <div className="landing-feature-icon" aria-hidden>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M4 14h4l2-8 4 14 2-6h6"
                    stroke="hsl(200, 65%, 40%)"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fill="none"
                  />
                </svg>
              </div>
              <h2 className="landing-feature-title">Live risk pricing</h2>
              <p className="landing-feature-copy">Weather, AQI, and news signals feed a transparent actuarial blend with an ML residual — every rupee is traceable.</p>
            </div>
            <div className="landing-feature">
              <div className="landing-feature-icon" aria-hidden>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <rect x="4" y="6" width="16" height="12" rx="2" stroke="hsl(152, 55%, 38%)" strokeWidth="1.5" fill="hsla(152, 60%, 40%, 0.08)" />
                  <path d="M8 10h8M8 14h5" stroke="hsl(152, 55%, 38%)" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </div>
              <h2 className="landing-feature-title">Automated claims path</h2>
              <p className="landing-feature-copy">Eligible events can flow from sensor to review to payout with fraud checks in between — see the pipeline in the dashboard demo.</p>
            </div>
          </section>

          <p className="landing-footnote">
            Data partners: OpenWeatherMap · WAQI · NewsData.io / GNews when configured
          </p>
        </main>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  VIEW: OTP VERIFICATION
  // ═══════════════════════════════════════════════════════════════
  if (view === "otp") {
    return (
      <>
        <div className="app-container auth-split">
          <aside className="auth-panel-left">
            <div className="auth-brand-row">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                <path
                  d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3z"
                  fill="hsl(22, 95%, 55%)"
                  stroke="hsl(22, 95%, 48%)"
                  strokeWidth="1.2"
                />
              </svg>
              <span className="auth-brand-wordmark">SurakshaShift</span>
            </div>
            <p className="auth-tagline">Income protection for India&apos;s delivery workforce</p>
            <ul className="auth-trust-list">
              <li>
                <span className="auth-trust-icon">✓</span>
                <span>Parametric coverage aligned with real-world disruptions — rain, flood, air quality, and more.</span>
              </li>
              <li>
                <span className="auth-trust-icon">✓</span>
                <span>Weekly plans designed for gig schedules — simple pricing, no jargon.</span>
              </li>
              <li>
                <span className="auth-trust-icon">✓</span>
                <span>Claims guided by live zone data — built for trust and transparency.</span>
              </li>
            </ul>
          </aside>
          <div className="auth-panel-right center-view">
            <div className="card wizard-card">
              <div className="wizard-progress">
                <div className="progress-step active">1</div>
                <div className="progress-line" />
                <div className="progress-step">2</div>
                <div className="progress-line" />
                <div className="progress-step">3</div>
                <div className="progress-line" />
                <div className="progress-step">4</div>
              </div>
              <div className="wizard-header">
                <div className="hero-shield" aria-hidden>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path
                      d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3z"
                      fill="hsl(22, 95%, 55%)"
                      stroke="hsl(22, 95%, 48%)"
                      strokeWidth="1.2"
                    />
                  </svg>
                </div>
                <h2>Sign in with mobile</h2>
                <p className="subtitle">Verify your number to continue to your SurakshaShift profile</p>
              </div>
              <div className="wizard-body">
                <div className="form-group">
                  <label>Mobile Number</label>
                  <div className="phone-input-group">
                    <span className="phone-prefix">+91</span>
                    <input
                      type="tel"
                      value={phone}
                      onChange={e => setPhone(e.target.value)}
                      placeholder="Enter your 10-digit number"
                      maxLength={10}
                    />
                  </div>
                </div>
                {!otpSent ? (
                  <button onClick={handleSendOtp} disabled={loading || phone.length < 10} style={{ width: "100%" }}>
                    {loading ? "Sending..." : "Send OTP →"}
                  </button>
                ) : (
                  <>
                    <div className="otp-sent-label">
                      <span className="pulse-dot" />
                      OTP sent to +91 {phone}{" "}
                      <span style={{ color: "var(--text-dim)", fontSize: "0.8rem" }}>(use 123456)</span>
                    </div>
                    <div className="form-group">
                      <label>Enter OTP</label>
                      <input
                        type="text"
                        value={otp}
                        onChange={e => setOtp(e.target.value)}
                        placeholder="6-digit OTP"
                        maxLength={6}
                        className="otp-input"
                      />
                    </div>
                    <button onClick={handleVerifyOtp} disabled={loading || otp.length < 6} style={{ width: "100%" }}>
                      {loading ? "Verifying..." : "Verify & Continue →"}
                    </button>
                  </>
                )}
              </div>
              <div className="wizard-footer">Covering 10L+ workers across India · Weekly plans from ₹15</div>
            </div>
          </div>
        </div>
        <footer className="auth-footer">
          Live risk inputs: OpenWeatherMap · WAQI · NewsData.io / GNews (when configured) · IMD-aligned city weights in pricing engine
        </footer>
      </>
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  VIEW: REGISTRATION FORM
  // ═══════════════════════════════════════════════════════════════
  if (view === "register") {
    return (
      <div className="app-container center-view">
        <div className="card wizard-card" style={{ maxWidth: "580px" }}>
          <div className="reg-progress" role="navigation" aria-label="Onboarding steps">
            <div className="reg-step done">Verify</div>
            <div className="reg-step active">Profile</div>
            <div className="reg-step">Coverage</div>
            <div className="reg-step">Done</div>
          </div>
          <div className="wizard-header">
            <h2>Tell us about your work</h2>
            <p className="subtitle">This helps our AI calculate your personalized premium</p>
          </div>
          <form className="wizard-body" onSubmit={handleRegister}>
            <div className="grid two" style={{ gap: "16px" }}>
              <div className="form-group">
                <label>Full Name</label>
                <input value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} placeholder="Ravi Kumar" required />
              </div>
              <div className="form-group">
                <label>City</label>
                <select value={formData.city} onChange={e => setFormData({ ...formData, city: e.target.value })}>
                  {["Bengaluru", "Mumbai", "Delhi", "Chennai", "Kolkata", "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Lucknow"].map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid two" style={{ gap: "16px" }}>
              <div className="form-group">
                <label>Delivery Platform</label>
                <select value={formData.platform_name} onChange={e => setFormData({ ...formData, platform_name: e.target.value })}>
                  <option value="Zepto">Zepto</option>
                  <option value="Blinkit">Blinkit</option>
                  <option value="Instamart">Swiggy Instamart</option>
                  <option value="BigBasket">BigBasket</option>
                  <option value="Amazon">Amazon Fresh</option>
                  <option value="Dunzo">Dunzo</option>
                </select>
              </div>
              <div className="form-group">
                <label>Persona Type</label>
                <select value={formData.persona_type} onChange={e => setFormData({ ...formData, persona_type: e.target.value })}>
                  <option value="grocery">Grocery / Q-Commerce</option>
                  <option value="food">Food Delivery</option>
                  <option value="ecommerce">E-Commerce / Parcels</option>
                </select>
              </div>
            </div>
            <div className="grid two" style={{ gap: "16px" }}>
              <div className="form-group">
                <label>Avg Weekly Income (₹)</label>
                <input type="number" value={formData.avg_weekly_income} onChange={e => setFormData({ ...formData, avg_weekly_income: Number(e.target.value) })} min={500} required />
              </div>
              <div className="form-group">
                <label>Primary Delivery Zone</label>
                <input value={formData.primary_zone} onChange={e => setFormData({ ...formData, primary_zone: e.target.value })} placeholder="HSR Layout" required />
              </div>
            </div>
            <div className="grid two" style={{ gap: "16px" }}>
              <div className="form-group">
                <label>Shift Type</label>
                <select value={formData.shift_type} onChange={e => setFormData({ ...formData, shift_type: e.target.value })}>
                  <option value="morning">Morning (6am–12pm)</option>
                  <option value="afternoon">Afternoon (12pm–6pm)</option>
                  <option value="evening">Evening (6pm–12am)</option>
                  <option value="night">Night (12am–6am)</option>
                  <option value="full_day">Full Day</option>
                  <option value="split">Split Shift</option>
                </select>
              </div>
              <div className="form-group">
                <label>UPI ID (for payouts)</label>
                <input value={formData.payout_upi} onChange={e => setFormData({ ...formData, payout_upi: e.target.value })} placeholder="name@upi" required />
              </div>
            </div>
            <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "12px" }}>
              <input type="checkbox" checked={formData.gps_enabled} onChange={e => setFormData({ ...formData, gps_enabled: e.target.checked })} style={{ width: "auto" }} id="gps-check" />
              <label htmlFor="gps-check" style={{ textTransform: "none", fontSize: "0.9rem" }}>Enable GPS validation for faster claim approvals</label>
            </div>
            <button type="submit" disabled={loading} style={{ width: "100%", marginTop: "8px" }}>
              {loading ? (
                "Analyzing risk…"
              ) : (
                <>
                  Get my risk quote
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                    <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  VIEW: AI RISK QUOTE
  // ═══════════════════════════════════════════════════════════════
  if (view === "quote" && riskQuote) {
    const importances = riskQuote.feature_importances || {};
    const maxImp = Math.max(...Object.values(importances).map(Number), 0.01);
    const importanceFriendly: Record<string, string> = {
      rain_risk: "Heavy rain",
      flood_risk: "Flooding",
      aqi_risk: "Air quality",
      closure_risk: "Local shutdowns & news",
      shift_exposure: "When you work",
      avg_weekly_income: "Your weekly income",
      city_risk: "City you work in",
    };

    const shiftTypeToExposure = (st: string) =>
      (
        {
          morning: 0.6,
          afternoon: 0.8,
          evening: 0.9,
          night: 1.0,
          full_day: 0.85,
          split: 0.75,
        } as Record<string, number>
      )[st] ?? 0.75;

    const exposureInputs =
      riskQuote.quote_exposure_inputs ??
      (quoteLiveFactors
        ? {
            rain_risk: quoteLiveFactors.rain_risk,
            flood_risk: quoteLiveFactors.flood_risk,
            aqi_risk: quoteLiveFactors.aqi_risk,
            closure_risk: quoteLiveFactors.closure_risk,
            shift_exposure: shiftTypeToExposure(profile?.shift_type ?? "full_day"),
            city: profile?.city ?? "",
          }
        : null);

    const exposureRows = exposureInputs
      ? [
          { key: "rain_risk", label: "Heavy rain risk" },
          { key: "flood_risk", label: "Flood risk" },
          { key: "aqi_risk", label: "Air quality (pollution)" },
          { key: "closure_risk", label: "Bandhs, curfews & local shutdowns" },
          { key: "shift_exposure", label: "Your work hours / shift type" },
        ]
      : [];
    const maxExp = exposureInputs
      ? Math.max(
          0.01,
          ...exposureRows.map(r => Number((exposureInputs as Record<string, number>)[r.key] ?? 0)),
        )
      : 1;
    const planList = plansQuote?.plans ?? [];
    const selectedPlan =
      planList.find((p: any) => p.plan_id === selectedPlanId) ||
      planList.find((p: any) => p.plan_id === "standard") ||
      planList[0];
    const riskTone = (plansQuote?.risk_level || "moderate").toLowerCase();
    const riskPillClass = ["low", "moderate", "high", "critical"].includes(riskTone) ? riskTone : "moderate";
    const riskColor =
      riskTone === "low"
        ? "var(--success)"
        : riskTone === "moderate"
          ? "var(--primary-hover)"
          : riskTone === "high"
            ? "var(--warning)"
            : "var(--error)";
    return (
      <div className="app-container quote-page">
        <div className="reg-progress" style={{ maxWidth: "640px", width: "100%", margin: "0 auto 28px" }} role="navigation" aria-label="Onboarding steps">
          <div className="reg-step done">Verify</div>
          <div className="reg-step done">Profile</div>
          <div className="reg-step active">Coverage</div>
          <div className="reg-step">Done</div>
        </div>

        <h2 style={{ fontSize: "2rem", marginBottom: "8px", textAlign: "center" }}>Your personalised quote</h2>
        <p className="subtitle" style={{ marginBottom: "10px", textAlign: "center", maxWidth: "36rem", marginLeft: "auto", marginRight: "auto" }}>
          Actuarial + ML blend · Live factors for {profile?.zone_name}, {profile?.city}
        </p>
        <p style={{ textAlign: "center", fontSize: "0.85rem", color: "var(--text-dim)", marginBottom: "10px", maxWidth: "40rem", marginLeft: "auto", marginRight: "auto", lineHeight: 1.55 }}>
          Premium uses <strong style={{ color: "var(--primary-hover)" }}>live</strong> weather, AQI, and{" "}
          <strong style={{ color: "var(--primary-hover)" }}>news</strong> (bandh / curfew signals) for {profile?.city}
          {quoteLiveFactors?.fetched_at && (
            <> · Updated {new Date(quoteLiveFactors.fetched_at).toLocaleString("en-IN")}</>
          )}
        </p>
        <p className="quote-model-version">Pricing model · {riskQuote?.model_version || "actuarial-gbm-blend-v1"}</p>

        <div className="quote-top-bar" style={{ maxWidth: "1000px", margin: "0 auto 20px", width: "100%" }}>
          <span className={`risk-pill ${riskPillClass}`}>{(plansQuote?.risk_level || "moderate").toUpperCase()}</span>
          <span className="quote-city">{profile?.city}</span>
          {quoteLiveFactors ? (
            <div className="quote-live-strip">
              <span className="live-badge">
                <span className="pulse-dot" /> LIVE INPUTS
              </span>
              <div className="quote-live-strip__metrics">
                <div className="quote-metric">
                  <span className="quote-metric__icon" aria-hidden>
                    🌡️
                  </span>
                  <div className="quote-metric__body">
                    <span className="quote-metric__main">
                      {quoteLiveFactors.weather?.temperature_c ?? "—"}°C · {quoteLiveFactors.weather?.condition ?? "—"}
                    </span>
                    <span className="quote-metric__sub">
                      {quoteLiveFactors.weather?.source === "openweathermap" ? "OpenWeatherMap" : quoteLiveFactors.weather?.source || "—"}
                    </span>
                  </div>
                </div>
                <div className="quote-metric">
                  <span className="quote-metric__icon" aria-hidden>
                    🌧️
                  </span>
                  <div className="quote-metric__body">
                    <span className="quote-metric__main">
                      {quoteLiveFactors.weather?.rain_mm_1h ?? 0} mm/h rain · {quoteLiveFactors.weather?.wind_speed_kmh ?? 0} km/h wind
                    </span>
                    <span className="quote-metric__sub">Live weather strip</span>
                  </div>
                </div>
                <div className="quote-metric">
                  <span className="quote-metric__icon" aria-hidden>
                    😷
                  </span>
                  <div className="quote-metric__body">
                    <span className="quote-metric__main">AQI {quoteLiveFactors.aqi?.aqi ?? "—"}</span>
                    <span className="quote-metric__sub">
                      {quoteLiveFactors.aqi?.source === "waqi" ? "WAQI" : quoteLiveFactors.aqi?.source || "mock"}
                    </span>
                  </div>
                </div>
                <div
                  className="quote-metric"
                  title={
                    quoteLiveFactors.closure_source === "newsdata" || quoteLiveFactors.closure_source === "gnews"
                      ? "Live news (NewsData.io or GNews): India stories mentioning bandh, curfew, hartal, etc., matched to your city/region"
                      : "Set NEWSDATA_API_KEY and/or GNEWS_API_KEY for real headlines; otherwise a low demo baseline"
                  }
                >
                  <span className="quote-metric__icon" aria-hidden>
                    🚧
                  </span>
                  <div className="quote-metric__body">
                    <span className="quote-metric__main">
                      Closure signal{" "}
                      {typeof quoteLiveFactors.closure_risk === "number" ? `${(quoteLiveFactors.closure_risk * 100).toFixed(0)}%` : "—"}
                    </span>
                    <span className="quote-metric__sub">
                      {quoteLiveFactors.closure_source === "newsdata" || quoteLiveFactors.closure_source === "gnews"
                        ? "News-driven"
                        : "Mock baseline"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
          <button type="button" className="btn-ghost" onClick={handleRefreshQuote} disabled={loading} style={{ padding: "10px 16px", fontSize: "0.88rem" }}>
            {loading ? "Refreshing…" : "↻ Refresh live quote"}
          </button>
        </div>

        {quoteLiveFactors &&
          Array.isArray(quoteLiveFactors.closure_headlines) &&
          quoteLiveFactors.closure_headlines.length > 0 && (
            <div
              className="card"
              style={{
                maxWidth: "1000px",
                margin: "0 auto 24px",
                width: "100%",
                padding: "14px 18px",
                fontSize: "0.78rem",
                color: "var(--text-dim)",
                lineHeight: 1.45,
              }}
            >
              <strong style={{ color: "var(--text-secondary)" }}>News matched:</strong>
              <ul style={{ margin: "6px 0 0 18px", padding: 0 }}>
                {quoteLiveFactors.closure_headlines.slice(0, 3).map((h: { title?: string }, i: number) => (
                  <li key={i}>{h.title || "(no title)"}</li>
                ))}
              </ul>
            </div>
          )}

        <div className="quote-main-grid" style={{ maxWidth: "1000px", margin: "0 auto", width: "100%" }}>
          <div className="quote-plans-col">
            <div className="card premium-card">
              <div
                style={{
                  marginBottom: "16px",
                  borderRadius: "10px",
                  border: `1px solid ${riskColor}`,
                  background: "var(--accent-light)",
                  padding: "10px 14px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  Risk level
                </span>
                <strong style={{ color: riskColor, letterSpacing: "0.05em", fontSize: "0.85rem" }}>
                  {(plansQuote?.risk_level || "moderate").toUpperCase()}
                </strong>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {planList.map((plan: any, planIdx: number) => {
                  const isSelected = selectedPlan?.plan_id === plan.plan_id;
                  const isRecommended = plan.plan_id === "standard";
                  const tierClass = planIdx % 3 === 0 ? "plan-tier-a" : planIdx % 3 === 1 ? "plan-tier-b" : "plan-tier-c";
                  return (
                    <button
                      key={plan.plan_id}
                      type="button"
                      onClick={() => setSelectedPlanId(plan.plan_id)}
                      className={`plan-select-btn ${isSelected ? "selected" : ""} ${tierClass}`}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
                        <div>
                          <div style={{ fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif', fontWeight: 800, fontSize: "1.02rem", color: "var(--navy)" }}>
                            {plan.label}
                          </div>
                          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "4px", lineHeight: 1.45 }}>{plan.description}</div>
                        </div>
                        {isRecommended && (
                          <span
                            style={{
                              borderRadius: "999px",
                              border: "1px solid var(--success-border)",
                              color: "var(--success)",
                              background: "var(--success-bg)",
                              fontSize: "0.65rem",
                              fontWeight: 800,
                              padding: "4px 8px",
                              letterSpacing: "0.06em",
                            }}
                          >
                            TOP PICK
                          </span>
                        )}
                      </div>
                      <div style={{ marginTop: "12px", display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "8px" }}>
                        <div style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--accent)", fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif' }}>
                          ₹{Number(plan.premium_weekly).toFixed(0)}
                          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 600, marginLeft: "4px" }}>/week</span>
                        </div>
                        <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", fontWeight: 600 }}>{Number(plan.risk_rate_pct).toFixed(2)}% risk rate</div>
                      </div>
                      <div style={{ marginTop: "10px", display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                        <span style={{ fontWeight: 700, color: "var(--success)" }}>Max ₹{Number(plan.max_weekly_payout).toFixed(0)}</span>
                        <span
                          style={{
                            borderRadius: "999px",
                            padding: "2px 10px",
                            fontSize: "0.72rem",
                            fontWeight: 700,
                            background: "var(--surface-raised)",
                            border: "1px solid var(--border)",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {(Number(plan.coverage_pct) * 100).toFixed(0)}% coverage
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>

              <button onClick={handleSubscribe} disabled={loading || !selectedPlan} style={{ width: "100%", marginTop: "20px", padding: "18px" }}>
                {loading || !selectedPlan ? "Activating…" : `Pay ₹${Number(selectedPlan.premium_weekly).toFixed(0)} via UPI & activate`}
              </button>

              <div className="exclusion-note">Excludes: health, life, accident, and vehicle repair coverage.</div>
            </div>
          </div>

          <div className="quote-chart-col">
            <div className="card">
              {exposureInputs && (
                <>
                  <h3 style={{ marginBottom: "8px", fontSize: "1.05rem" }}>What we&apos;re seeing right now</h3>
                  <p style={{ color: "var(--text-dim)", fontSize: "0.82rem", lineHeight: 1.55, marginBottom: "18px" }}>
                    These bars show how risky things look <strong>today</strong> for <strong>{exposureInputs.city}</strong> — weather, air, local news about shutdowns, and how you work. Higher bars mean more of that risk is in play for this quote (each bar is out of 100%).
                  </p>
                  <div className="feature-importance-list" style={{ marginBottom: "28px" }}>
                    {exposureRows.map(({ key, label }) => {
                      const v = Number((exposureInputs as Record<string, number>)[key] ?? 0);
                      return (
                        <div className="fi-row" key={key}>
                          <div className="fi-label">{label}</div>
                          <div className="fi-bar-container">
                            <div className="fi-bar" style={{ width: `${(v / maxExp) * 100}%` }} />
                          </div>
                          <div className="fi-value">{(v * 100).toFixed(0)}%</div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}

              <h3 style={{ marginBottom: "8px", fontSize: "1.05rem" }}>How the system was trained to think</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.88rem", lineHeight: 1.6, marginBottom: "12px" }}>
                Your weekly price is mostly a <strong>straightforward formula</strong> (coverage × risk level, with city built in). A smaller slice uses <strong>pattern learning</strong> from sample scenarios—not a black box, but not the same as &quot;today&apos;s sky.&quot;
              </p>
              <p style={{ color: "var(--text-muted)", fontSize: "0.76rem", lineHeight: 1.5, marginBottom: "16px" }}>
                The bars below show which factors the model relied on most when it learned. Compare them to <strong>today&apos;s bars above</strong> to see the difference.
              </p>

              <div className="feature-importance-list">
                {Object.entries(importances).map(([name, value]) => (
                  <div className="fi-row" key={name}>
                    <div className="fi-label">{importanceFriendly[name] ?? name.replace(/_/g, " ")}</div>
                    <div className="fi-bar-container">
                      <div className="fi-bar" style={{ width: `${(Number(value) / maxImp) * 100}%` }} />
                    </div>
                    <div className="fi-value">{(Number(value) * 100).toFixed(1)}%</div>
                  </div>
                ))}
              </div>

              <div className="alert" style={{ background: "var(--accent-light)", borderColor: "hsl(22, 80%, 82%)", marginTop: "24px" }}>
                <div className="alert-icon">⚡</div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.55 }}>
                  <strong style={{ color: "var(--accent-hover)" }}>Fast claims:</strong> If something covered happens in <strong>{profile?.zone_name}</strong>, we can start a claim for you and send the payout to your UPI—without long paperwork when things check out.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  VIEW: DASHBOARD
  // ═══════════════════════════════════════════════════════════════
  const activePolicy = policies.find((p: any) => p.status === "active") || policies[0];

  if (view === "dashboard") return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
            <path
              d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3z"
              fill="hsl(22, 95%, 55%)"
              stroke="hsl(22, 95%, 48%)"
              strokeWidth="1.2"
            />
          </svg>
          <span>SurakshaShift</span>
        </div>
        <nav className="nav">
          <button
            type="button"
            className={`nav-link ${dashboardSection === "home" ? "active" : ""}`}
            onClick={() => scrollToDashboardSection("home")}
          >
            📊 Dashboard
          </button>
          <button
            type="button"
            className={`nav-link ${dashboardSection === "policy" ? "active" : ""}`}
            onClick={() => scrollToDashboardSection("policy")}
          >
            🛡️ My Policy
          </button>
          <button
            type="button"
            className={`nav-link ${dashboardSection === "claims" ? "active" : ""}`}
            onClick={() => scrollToDashboardSection("claims")}
          >
            📋 My claims
          </button>
          <button
            type="button"
            className={`nav-link ${dashboardSection === "live" ? "active" : ""}`}
            onClick={() => scrollToDashboardSection("live")}
          >
            🌦️ Live Conditions
          </button>
        </nav>
        <button
          type="button"
          className="nav-link"
          style={{ marginTop: "8px", fontSize: "0.82rem", opacity: 0.7 }}
          onClick={() => { setView("admin"); fetchAdminData(); }}
        >
          🏢 Admin Portal
        </button>
        <div className={`worker-status ${activePolicy ? 'active' : ''}`}>
          <div style={{ fontWeight: 600, marginBottom: "4px" }}>{profile?.name}</div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-dim)", marginBottom: "6px" }}>{profile?.platform_name} • {profile?.zone_name}</div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span className={`status-dot ${activePolicy ? 'active' : ''}`} />
            {activePolicy ? "Protected • Weekly Shield" : "Unprotected"}
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        <section id="dash-home" className="dashboard-section" aria-labelledby="dash-home-title">
          <header className="dashboard-header">
            <div>
              <h1 id="dash-home-title" style={{ fontSize: "2.2rem" }}>
                Hello, {profile?.name?.split(" ")[0]} 👋
              </h1>
              <p className="subtitle" style={{ fontSize: "1rem", marginTop: "6px" }}>
                {liveRisk?.is_disruptive
                  ? `⚠️ Disruption detected in ${profile?.city}! Your coverage is active.`
                  : `Your ${profile?.zone_name} zone is currently clear of disruptions.`}
              </p>
            </div>
            <div className="badge success" style={{ padding: "8px 16px", fontSize: "0.85rem" }}>
              <span className="status-dot active" style={{ marginRight: "6px" }} />
              {profile?.platform_name} Shift Active
            </div>
          </header>

          <div className="grid four" style={{ marginTop: "28px" }}>
            <div className="stat-card">
              <span className="stat-decorator" aria-hidden>
                ₹
              </span>
              <span className="stat-label">Weekly Premium</span>
              <span className="stat-value">₹{activePolicy?.premium_weekly || "0"}</span>
              <span className="stat-sub">Auto-renews weekly</span>
            </div>
            <div className="stat-card">
              <span className="stat-decorator" aria-hidden>
                🛡️
              </span>
              <span className="stat-label">Max Payout</span>
              <span className="stat-value" style={{ color: "var(--success)" }}>
                ₹{activePolicy?.max_weekly_payout || "0"}
              </span>
              <span className="stat-sub">Up to {activePolicy?.plan_name === "weekly-full" ? "50" : activePolicy?.plan_name === "weekly-basic" ? "20" : "35"}% of avg income</span>
            </div>
            <div className="stat-card">
              <span className="stat-decorator" aria-hidden>
                💰
              </span>
              <span className="stat-label">Earnings Protected</span>
              <span className="stat-value" style={{ color: "var(--success)" }}>
                ₹{workerProtection?.earnings_protected?.toFixed(0) || "0"}
              </span>
              <span className="stat-sub">
                {(workerProtection?.net_benefit ?? 0) >= 0
                  ? `+₹${(workerProtection?.net_benefit ?? 0).toFixed(0)} net benefit`
                  : `₹${Math.abs(workerProtection?.net_benefit ?? 0).toFixed(0)} paid in premiums`}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-decorator" aria-hidden>
                📋
              </span>
              <span className="stat-label">Claims</span>
              <span className="stat-value" style={{ color: "var(--secondary)" }}>
                {claimsSummary?.approved_claims || 0}
              </span>
              <span className="stat-sub">{claimsSummary?.total_claims || 0} filed · ₹{claimsSummary?.total_payout?.toFixed(0) || "0"} paid out</span>
            </div>
          </div>

          {workerProtection?.active_coverage?.has_active && (
            <div className="card" style={{ marginTop: "20px", padding: "20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <h3 style={{ margin: 0, fontSize: "1rem" }}>Active Weekly Coverage</h3>
                <span className="badge success" style={{ fontSize: "0.75rem" }}>
                  {workerProtection.active_coverage.days_remaining} days left
                </span>
              </div>
              <div style={{ background: "var(--surface-raised)", borderRadius: "8px", height: "10px", overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    borderRadius: "8px",
                    background: "linear-gradient(90deg, var(--success), var(--primary))",
                    width: `${(workerProtection.active_coverage.coverage_progress_pct || 0) * 100}%`,
                    transition: "width 0.5s ease",
                  }}
                />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "8px", fontSize: "0.78rem", color: "var(--text-dim)" }}>
                <span>Premium: ₹{workerProtection.active_coverage.premium_weekly}/wk</span>
                <span>Max payout: ₹{workerProtection.active_coverage.max_weekly_payout}/wk</span>
              </div>
            </div>
          )}

          {workerProtection?.payout_history?.length > 0 && (
            <div className="card" style={{ marginTop: "20px", padding: "20px" }}>
              <h3 style={{ margin: "0 0 14px", fontSize: "1rem" }}>Recent Payouts (UPI)</h3>
              <div className="data-list" style={{ marginTop: 0, maxHeight: "240px", overflowY: "auto" }}>
                {workerProtection.payout_history.slice(0, 8).map((p: any) => (
                  <div className="data-item" key={p.id}>
                    <div className="item-main">
                      <span className="item-title" style={{ fontFamily: "monospace", fontSize: "0.82rem" }}>
                        {p.status === "success" ? "✅" : "❌"} {p.gateway_ref}
                      </span>
                      <span className="item-meta">
                        {p.completed_at ? formatTime(p.completed_at) : "Processing..."}
                        <span className={`badge ${p.status === "success" ? "success" : "pending"}`} style={{ marginLeft: "8px", zoom: 0.8 }}>
                          {p.status === "success" ? "PAID" : p.status.toUpperCase()}
                        </span>
                      </span>
                    </div>
                    <div className="item-amount" style={{ color: p.status === "success" ? "var(--success)" : "var(--text-muted)" }}>
                      ₹{p.amount}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="card shift-guardian-card" style={{ marginTop: "28px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
              <h3 style={{ display: "flex", alignItems: "center", gap: "8px", margin: 0, flexWrap: "wrap" }}>
                <span>🧭</span> Shift Guardian
                <span className="shift-ai-badge">AI-POWERED</span>
              </h3>
              <button
                type="button"
                className="btn-ghost"
                onClick={fetchShiftRecommendation}
                disabled={shiftRecLoading}
                style={{
                  padding: "10px 16px",
                  fontSize: "0.85rem",
                  cursor: shiftRecLoading ? "wait" : "pointer",
                }}
              >
                {shiftRecLoading ? "Analysing zones…" : "Check before I start shift →"}
              </button>
            </div>

            {!shiftRec && !shiftRecLoading && (
              <div style={{ textAlign: "center", padding: "28px 0", color: "var(--text-dim)", fontSize: "0.9rem" }}>
                Tap the button before starting your shift to see which nearby zone is safest for earnings today.
              </div>
            )}

            {shiftRecLoading && <div className="shimmer-block" style={{ height: "160px" }} />}

            {shiftRec && !shiftRecLoading && (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div
                  style={{
                    padding: "16px",
                    borderRadius: "12px",
                    background:
                      shiftRec.alert_type === "all_clear"
                        ? "var(--success-bg)"
                        : shiftRec.alert_type === "zone_switch_recommended"
                          ? "var(--surface-raised)"
                          : "var(--warning-bg)",
                    border: `1px solid ${
                      shiftRec.alert_type === "all_clear"
                        ? "var(--success-border)"
                        : shiftRec.alert_type === "zone_switch_recommended"
                          ? "var(--border-strong)"
                          : "hsl(38, 70%, 72%)"
                    }`,
                    fontSize: "0.9rem",
                    lineHeight: 1.6,
                    color:
                      shiftRec.alert_type === "all_clear"
                        ? "hsl(152, 55%, 28%)"
                        : shiftRec.alert_type === "zone_switch_recommended"
                          ? "var(--text-primary)"
                          : "hsl(38, 85%, 28%)",
                  }}
                >
                  {shiftRec.recommendation_text}
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div
                    style={{
                      padding: "14px",
                      borderRadius: "12px",
                      background: "var(--surface)",
                      border: "1px solid var(--border-strong)",
                      boxShadow: "var(--shadow-sm)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "0.72rem",
                        color: "var(--text-muted)",
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        marginBottom: "6px",
                        fontWeight: 700,
                      }}
                    >
                      Your zone
                    </div>
                    <div style={{ fontWeight: 800, fontSize: "1rem", marginBottom: "8px", color: "var(--navy)" }}>
                      📍 {shiftRec.current_zone?.zone_name}
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                      Disruption:{" "}
                      <strong style={{ color: "var(--warning)" }}>{shiftRec.current_zone?.disruption_probability}%</strong>
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                      Safety score: <strong>{shiftRec.current_zone?.income_protection_score}</strong>/100
                    </div>
                  </div>

                  <div
                    style={{
                      padding: "14px",
                      borderRadius: "12px",
                      background: "var(--success-bg)",
                      border: "1px solid var(--success-border)",
                      boxShadow: "var(--shadow-sm)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "0.72rem",
                        color: "var(--success)",
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        marginBottom: "6px",
                        fontWeight: 700,
                      }}
                    >
                      Recommended
                    </div>
                    <div style={{ fontWeight: 800, fontSize: "1rem", marginBottom: "8px", color: "var(--navy)" }}>
                      ✅ {shiftRec.recommended_zone?.zone_name}
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                      Disruption:{" "}
                      <strong style={{ color: "var(--success)" }}>
                        {shiftRec.recommended_zone?.disruption_probability}%
                      </strong>
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                      Safety score: <strong>{shiftRec.recommended_zone?.income_protection_score}</strong>/100
                    </div>
                  </div>
                </div>

                {shiftRec.estimated_income_difference > 0 && (
                  <div
                    style={{
                      padding: "14px 18px",
                      borderRadius: "12px",
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      boxShadow: "var(--shadow-sm)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: "8px",
                    }}
                  >
                    <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                      Estimated income protected by switching zones
                    </span>
                    <span style={{ fontSize: "1.45rem", fontWeight: 800, color: "var(--accent)", fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif' }}>
                      +₹{Number(shiftRec.estimated_income_difference).toFixed(0)}
                    </span>
                  </div>
                )}

                {shiftRec.alternatives?.length > 0 && (
                  <div>
                    <div
                      style={{
                        fontSize: "0.75rem",
                        color: "var(--text-dim)",
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        marginBottom: "8px",
                      }}
                    >
                      All nearby zones
                    </div>
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      {[shiftRec.current_zone, ...shiftRec.alternatives].map((z: any) => {
                        const rl = String(z.risk_level || "").toLowerCase();
                        const dotColor =
                          rl === "low" ? "var(--success)" : rl === "high" || rl === "critical" ? "var(--error)" : "var(--accent)";
                        return (
                          <div key={z.zone_name} className="zone-pill">
                            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <span style={{ width: 8, height: 8, borderRadius: "50%", background: dotColor, flexShrink: 0 }} />
                              <span style={{ fontWeight: 700, color: "var(--navy)" }}>{z.zone_name}</span>
                            </div>
                            <div style={{ color: "var(--text-muted)", marginTop: "4px", fontSize: "0.76rem" }}>
                              {z.disruption_probability}% · {z.risk_level}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                    Window: {shiftRec.forecast_window} · {shiftRec.generated_at && new Date(shiftRec.generated_at).toLocaleString("en-IN")}
                  </div>
                  {waConfigured && workerId && (
                    <button
                      type="button"
                      className="btn-ghost"
                      style={{ fontSize: "0.78rem", padding: "6px 12px", display: "flex", alignItems: "center", gap: "4px" }}
                      onClick={async () => {
                        try {
                          await api.sendShiftGuardianWhatsapp(workerId);
                          alert("Shift Guardian summary sent to your WhatsApp!");
                        } catch { alert("Could not send WhatsApp notification"); }
                      }}
                    >
                      📱 Send to WhatsApp
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="card simulator-card" style={{ marginTop: "28px" }}>
            <h3 style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
              <span style={{ color: "var(--primary)" }}>⚡</span> Disruption Simulator
            </h3>
            <p className="subtitle" style={{ fontSize: "0.85rem", marginBottom: "24px" }}>
              Simulate real-world events that trigger automated income-loss claims in {profile?.zone_name}
            </p>

            <div className="trigger-grid">
              {[
                {
                  id: "rain",
                  icon: "🌧️",
                  label: "Heavy Rain",
                  desc: "62mm/hr rainfall",
                  color: "hsl(210, 80%, 40%)",
                  iconBg: "hsla(210, 85%, 92%, 1)",
                },
                {
                  id: "flood",
                  icon: "🌊",
                  label: "Flash Flood",
                  desc: "Water level 35cm+",
                  color: "hsl(185, 65%, 36%)",
                  iconBg: "hsla(185, 70%, 92%, 1)",
                },
                {
                  id: "aqi",
                  icon: "😷",
                  label: "AQI Severe",
                  desc: "AQI > 300 (hazardous)",
                  color: "hsl(38, 88%, 42%)",
                  iconBg: "hsla(38, 92%, 94%, 1)",
                },
                {
                  id: "closure",
                  icon: "🚧",
                  label: "Zone Closure",
                  desc: "Curfew / strike alert",
                  color: "hsl(4, 72%, 48%)",
                  iconBg: "hsla(4, 75%, 95%, 1)",
                },
                {
                  id: "outage",
                  icon: "📡",
                  label: "Platform Outage",
                  desc: `${profile?.platform_name} down 45min`,
                  color: "hsl(270, 55%, 48%)",
                  iconBg: "hsla(270, 60%, 95%, 1)",
                },
              ].map(t => (
                <button
                  key={t.id}
                  className="trigger-btn"
                  onClick={() => handleTrigger(t.id)}
                  disabled={triggerLoading !== null || !activePolicy}
                  style={{ "--trigger-color": t.color } as React.CSSProperties}
                >
                  <span className="trigger-icon-wrap" style={{ background: t.iconBg }}>
                    <span className="trigger-icon">{t.icon}</span>
                  </span>
                  <span className="trigger-label">{t.label}</span>
                  <span className="trigger-desc">{t.desc}</span>
                  {triggerLoading === t.id && <span className="trigger-loading" />}
                </button>
              ))}
            </div>

            <div className="alert" style={{ background: "var(--surface-raised)", borderColor: "var(--border)", marginTop: "20px" }}>
              <div className="alert-icon">ℹ️</div>
              <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                Each trigger ingests a disruption event → the backend matches it against your active policy → runs ML fraud scoring → auto-creates & approves a claim → payout is calculated based on disrupted hours and your weekly income.
              </div>
            </div>

            {simulatorLastResult?.error && (
              <div
                className="alert"
                style={{
                  marginTop: "14px",
                  background: "var(--error-bg)",
                  borderColor: "hsl(4, 55%, 78%)",
                }}
              >
                <div className="alert-icon">⚠️</div>
                <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.5 }}>{simulatorLastResult.message}</div>
              </div>
            )}

            {simulatorLastResult && !simulatorLastResult.error && simulatorLastResult.deduplicated && (
              <div
                className="alert"
                style={{
                  marginTop: "14px",
                  background: "var(--warning-bg)",
                  borderColor: "hsl(38, 70%, 72%)",
                }}
              >
                <div className="alert-icon">⏳</div>
                <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
                  {simulatorLastResult.reason || "Duplicate event skipped (cooldown still applies to non-mock ingests)."}
                </div>
              </div>
            )}

            {simulatorLastResult &&
              !simulatorLastResult.error &&
              !simulatorLastResult.deduplicated &&
              simPipelineStep !== null &&
              (() => {
                const res = simulatorLastResult;
                const claimRows = Array.isArray(res.claims) ? res.claims : [];
                const n = typeof res.claim_candidates === "number" ? res.claim_candidates : claimRows.length;
                const total = claimRows.reduce((a: number, c: { approved_payout?: number }) => a + Number(c.approved_payout ?? 0), 0);
                const steps: { title: string; detail: string; warn?: boolean }[] = [
                  {
                    title: "Disruption detected",
                    detail: `Verified signal ingested for your zone (${profile?.zone_name}).`,
                  },
                  {
                    title: "Policy match",
                    detail: "Checked active weekly policy, coverage dates, and parametric triggers for this event type.",
                  },
                  {
                    title: "Fraud & risk review",
                    detail: "Automated scoring: GPS consistency, activity pattern, duplicates, and source quality.",
                  },
                  n > 0
                    ? {
                        title: "Claim approved",
                        detail: `${n} claim${n === 1 ? "" : "s"} on your policy · ₹${total.toFixed(0)} estimated payout.`,
                      }
                    : {
                        title: "No claim created",
                        detail: "Policy window, weekly payout cap, or trigger thresholds may not be satisfied for this run.",
                        warn: true,
                      },
                  n > 0
                    ? {
                        title: "Payout via UPI + WhatsApp alert",
                        detail: `₹${total.toFixed(0)} credited to ${profile?.payout_upi || "your UPI"} via Razorpay. WhatsApp confirmation sent to your number.`,
                      }
                    : {
                        title: "No payout",
                        detail: "Nothing sent until a claim is approved.",
                        warn: true,
                      },
                ];
                return (
                  <div className="sim-pipeline" aria-live="polite">
                    <div className="sim-pipeline-header">Automatic claim flow</div>
                    <p className="sim-pipeline-sub">
                      Event #{res.event_id} · {profile?.zone_name}
                    </p>
                    <ol className="sim-pipeline-steps">
                      {steps.map((step, i) => {
                        const done = simPipelineStep !== null && i < simPipelineStep;
                        const active = simPipelineStep !== null && i === simPipelineStep && simPipelineStep < 5;
                        const pending = simPipelineStep !== null && i > simPipelineStep;
                        const warn = Boolean(step.warn);
                        return (
                          <li
                            key={step.title}
                            className={`sim-step ${done ? "done" : ""} ${active ? "active" : ""} ${pending ? "pending" : ""} ${warn && done ? "warn" : ""}`}
                          >
                            <span className="sim-step-marker" aria-hidden>
                              {done ? "✓" : active ? <span className="sim-step-pulse" /> : "○"}
                            </span>
                            <div className="sim-step-body">
                              <div className="sim-step-title">{step.title}</div>
                              <div className="sim-step-detail">{step.detail}</div>
                            </div>
                          </li>
                        );
                      })}
                    </ol>
                    {simPipelineStep >= 5 && (
                      <div className={`sim-pipeline-done ${n === 0 ? "muted" : ""}`}>
                        {n > 0
                          ? "Pipeline complete — see My claims for the new entry."
                          : "Run complete — adjust coverage or try another trigger."}
                      </div>
                    )}
                  </div>
                );
              })()}

            {simulatorLastResult &&
              !simulatorLastResult.error &&
              !simulatorLastResult.deduplicated &&
              simPipelineStep === null && (
                <div
                  className="alert"
                  style={{
                    marginTop: "14px",
                    background: "var(--success-bg)",
                    borderColor: "var(--success-border)",
                  }}
                >
                  <div className="alert-icon">✓</div>
                  <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
                    Event #{simulatorLastResult.event_id}: <strong>{simulatorLastResult.claim_candidates}</strong> claim(s) created.
                    {(simulatorLastResult.claim_candidates ?? 0) === 0 && (
                      <> Check policy coverage window, zone match, or weekly payout cap.</>
                    )}
                  </div>
                </div>
              )}
          </div>
        </section>

        <section id="dash-policy" className="dashboard-section" aria-labelledby="dash-policy-title" style={{ marginTop: "40px" }}>
          <h2 id="dash-policy-title" style={{ fontSize: "1.35rem", marginBottom: "16px" }}>
            🛡️ My Policy
          </h2>
          <div className="card">
            {activePolicy ? (
              <>
                <div className="grid two" style={{ gap: "20px", gridTemplateColumns: "1fr 1fr" }}>
                  <div>
                    <span className="stat-label">Status</span>
                    <div style={{ fontWeight: 600, marginTop: "4px", textTransform: "capitalize" }}>{activePolicy.status}</div>
                  </div>
                  <div>
                    <span className="stat-label">Auto-renew</span>
                    <div style={{ fontWeight: 600, marginTop: "4px" }}>{activePolicy.auto_renew ? "Yes" : "No"}</div>
                  </div>
                  <div>
                    <span className="stat-label">Weekly premium</span>
                    <div style={{ fontWeight: 600, marginTop: "4px" }}>₹{activePolicy.premium_weekly}</div>
                  </div>
                  <div>
                    <span className="stat-label">Max weekly payout</span>
                    <div style={{ fontWeight: 600, marginTop: "4px", color: "var(--success)" }}>₹{activePolicy.max_weekly_payout}</div>
                  </div>
                  <div style={{ gridColumn: "1 / -1" }}>
                    <span className="stat-label">Coverage window</span>
                    <div style={{ fontWeight: 600, marginTop: "4px" }}>
                      {activePolicy.coverage_start && formatPolicyDate(activePolicy.coverage_start)} —{" "}
                      {activePolicy.coverage_end && formatPolicyDate(activePolicy.coverage_end)}
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: "24px" }}>
                  <span className="stat-label">Covered parametric events</span>
                  <div className="event-pills" style={{ marginTop: "10px" }}>
                    {["Heavy rain", "Flood", "Severe AQI", "Curfew / closure", "Platform outage"].map(e => (
                      <span className="event-pill" key={e}>
                        {e}
                      </span>
                    ))}
                  </div>
                </div>
                <p style={{ fontSize: "0.82rem", color: "var(--text-dim)", marginTop: "20px", marginBottom: 0 }}>
                Payouts: income loss only — excludes health, accident, and vehicle repair. UPI on file: {profile?.payout_upi || "—"}
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "12px" }}>
                <span style={{ fontSize: "0.82rem", color: waConfigured ? "var(--success)" : "var(--text-dim)" }}>
                  📱 WhatsApp alerts: <strong>{waConfigured ? "Active" : "Not configured"}</strong>
                </span>
                {waConfigured && (
                  <span style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>
                    Claim payouts & disruption alerts sent to your number
                  </span>
                )}
              </div>
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-icon">🛡️</div>
                <div>No active weekly policy</div>
                <p style={{ fontSize: "0.85rem", color: "var(--text-dim)", marginTop: "8px" }}>Complete onboarding to activate coverage.</p>
              </div>
            )}
          </div>
        </section>

        <section id="dash-live" className="dashboard-section" aria-labelledby="dash-live-title" style={{ marginTop: "40px" }}>
          <h2 id="dash-live-title" style={{ fontSize: "1.35rem", marginBottom: "16px" }}>
            🌦️ Live Conditions — {profile?.city}
          </h2>
          <div className="card">
            <h3 style={{ marginBottom: "20px", display: "flex", alignItems: "center", gap: "8px" }}>
              <span>🌦️</span> Weather &amp; air quality
              <span className={`live-badge ${liveRisk?.is_disruptive ? "critical" : ""}`}>
                <span className="pulse-dot" /> LIVE
              </span>
            </h3>
            {liveRisk ? (
              <div className="live-conditions-grid">
                <div className="condition-card">
                  <div className="condition-icon">🌡️</div>
                  <div className="condition-value">{liveRisk.weather?.temperature_c || "--"}°C</div>
                  <div className="condition-label">{liveRisk.weather?.condition || "Loading"}</div>
                </div>
                <div className="condition-card">
                  <div className="condition-icon">🌧️</div>
                  <div className="condition-value">{liveRisk.weather?.rain_mm_1h || "0"} mm</div>
                  <div className="condition-label">Rain (1hr)</div>
                </div>
                <div className="condition-card">
                  <div className="condition-icon">💨</div>
                  <div className="condition-value">{liveRisk.weather?.wind_speed_kmh || "0"} km/h</div>
                  <div className="condition-label">Wind Speed</div>
                </div>
                <div className="condition-card">
                  <div className="condition-icon">😷</div>
                  <div className="condition-value">{liveRisk.aqi?.aqi || "--"}</div>
                  <div className="condition-label">AQI</div>
                </div>
                <div className="risk-meters">
                  <div className="risk-meter">
                    <span>Rain Risk</span>
                    <div className="meter-bar">
                      <div className="meter-fill rain" style={{ width: `${(liveRisk.rain_risk || 0) * 100}%` }} />
                    </div>
                    <span className="meter-val">{((liveRisk.rain_risk || 0) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="risk-meter">
                    <span>Flood Risk</span>
                    <div className="meter-bar">
                      <div className="meter-fill flood" style={{ width: `${(liveRisk.flood_risk || 0) * 100}%` }} />
                    </div>
                    <span className="meter-val">{((liveRisk.flood_risk || 0) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="risk-meter">
                    <span>AQI Risk</span>
                    <div className="meter-bar">
                      <div className="meter-fill aqi" style={{ width: `${(liveRisk.aqi_risk || 0) * 100}%` }} />
                    </div>
                    <span className="meter-val">{((liveRisk.aqi_risk || 0) * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div className={`overall-risk ${liveRisk.overall_risk}`}>
                  Overall: <strong>{liveRisk.overall_risk?.toUpperCase()}</strong>
                  {liveRisk.weather?.source && <span className="data-source">Source: {liveRisk.weather.source}</span>}
                </div>
              </div>
            ) : (
              <div className="shimmer-block" style={{ height: "200px" }} />
            )}
          </div>
        </section>

        <section id="dash-claims" className="dashboard-section" aria-labelledby="dash-claims-title" style={{ marginTop: "40px", marginBottom: "48px" }}>
          <h2 id="dash-claims-title" style={{ fontSize: "1.35rem", marginBottom: "6px" }}>
            📋 My claim history
          </h2>
          <p className="subtitle" style={{ fontSize: "0.88rem", marginBottom: "16px" }}>
            Only claims linked to your profile and policies are shown here.
          </p>
          <div className="card claims-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
              <h3 style={{ margin: 0 }}>Your claims</h3>
              {claimsSummary && (
                <span className="badge success" style={{ fontSize: "0.75rem" }}>
                  {claimsSummary.approved_claims} approved · {claimsSummary.pending_claims || 0} pending
                </span>
              )}
            </div>

            {claims.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">🌤️</div>
                <div>No claims yet this period</div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-dim)", marginTop: "4px" }}>
                  Use the simulator on Dashboard to test parametric triggers
                </div>
              </div>
            ) : (
              <div className="data-list" style={{ marginTop: 0, maxHeight: "480px", overflowY: "auto" }}>
                {claims.map((claim: any) => (
                  <div className="data-item" key={claim.id}>
                    <div className="item-main">
                      <span className="item-title">
                        {eventIcon[claim.claim_type] || "📋"}{" "}
                        {claim.auto_created ? "Auto claim" : "Manual claim"} · {String(claim.claim_type || "").replace(/_/g, " ")}
                      </span>
                      <span className="item-meta">
                        {formatTime(claim.created_at)}
                        <span className={`badge ${statusColor(claim.status)}`} style={{ marginLeft: "8px", zoom: 0.8 }}>
                          {claim.status === "paid" ? "PAID" : claim.status.replace("_", " ").toUpperCase()}
                        </span>
                        {claim.fraud_score != null && (
                          <span className={`badge ${claim.fraud_score > 0.5 ? "pending" : ""}`} style={{ marginLeft: "4px", zoom: 0.75, opacity: 0.8 }}>
                            Fraud: {(claim.fraud_score * 100).toFixed(0)}%
                          </span>
                        )}
                      </span>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div
                        className="item-amount"
                        style={{ color: claim.status === "paid" || claim.status === "approved" ? "var(--success)" : "var(--text-muted)" }}
                      >
                        ₹{claim.approved_payout}
                      </div>
                      {claim.payout_ref && (
                        <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", fontFamily: "monospace", marginTop: "2px" }}>
                          {claim.payout_ref}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );

  // ═══════════════════════════════════════════════════════════════
  //  VIEW: ADMIN / INSURER DASHBOARD
  // ═══════════════════════════════════════════════════════════════
  if (view === "admin") {
    const kpi = adminKpis;
    const lossRatioColor = (kpi?.loss_ratio ?? 0) > 1 ? "var(--error)" : (kpi?.loss_ratio ?? 0) > 0.7 ? "var(--warning)" : "var(--success)";
    const trendIcon = (t: string) => t === "rising" ? "📈" : t === "stable" ? "➡️" : "📉";

    return (
      <div className="app-container">
        <aside className="sidebar">
          <div className="sidebar-logo">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
              <path d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3z" fill="hsl(22, 95%, 55%)" stroke="hsl(22, 95%, 48%)" strokeWidth="1.2" />
            </svg>
            <span>SurakshaShift</span>
          </div>
          <div style={{ fontSize: "0.72rem", color: "var(--accent)", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 700, padding: "0 16px", marginBottom: "8px" }}>
            Insurer Admin
          </div>
          <nav className="nav">
            {([
              { id: "overview" as AdminSection, label: "📊 Overview" },
              { id: "claims" as AdminSection, label: "📋 Claims" },
              { id: "fraud" as AdminSection, label: "🛡️ Fraud Detection" },
              { id: "predictions" as AdminSection, label: "🔮 Predictions" },
              { id: "payouts" as AdminSection, label: "💸 Payouts" },
            ]).map(item => (
              <button key={item.id} type="button" className={`nav-link ${adminSection === item.id ? "active" : ""}`} onClick={() => setAdminSection(item.id)}>
                {item.label}
              </button>
            ))}
          </nav>
          <button
            type="button"
            className="nav-link"
            style={{ marginTop: "16px", fontSize: "0.82rem", opacity: 0.7 }}
            onClick={() => setView(workerId ? "dashboard" : "landing")}
          >
            ← Back to {workerId ? "Dashboard" : "Home"}
          </button>
        </aside>

        <main className="main-content" style={{ padding: "40px" }}>
          {adminLoading && !kpi && !adminFraud ? (
            <div style={{ textAlign: "center", padding: "80px 0", color: "var(--text-dim)" }}>Loading admin data...</div>
          ) : (
            <>
              {adminSection === "overview" && kpi && (
                <section>
                  <h1 style={{ fontSize: "2rem", marginBottom: "6px" }}>Insurer Dashboard</h1>
                  <p className="subtitle" style={{ marginBottom: "28px" }}>Real-time KPIs, loss ratios, and platform health</p>

                  <div className="grid four" style={{ marginBottom: "28px" }}>
                    <div className="stat-card">
                      <span className="stat-decorator" aria-hidden>👥</span>
                      <span className="stat-label">Active Workers</span>
                      <span className="stat-value">{kpi.active_workers}</span>
                      <span className="stat-sub">{kpi.active_policies} active policies</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-decorator" aria-hidden>₹</span>
                      <span className="stat-label">Premiums Collected</span>
                      <span className="stat-value">₹{kpi.premium_collected}</span>
                      <span className="stat-sub">Weekly premiums</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-decorator" aria-hidden>💸</span>
                      <span className="stat-label">Total Payouts</span>
                      <span className="stat-value" style={{ color: "var(--accent)" }}>₹{kpi.total_payouts}</span>
                      <span className="stat-sub">{kpi.approved_claims} claims paid</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-decorator" aria-hidden>📊</span>
                      <span className="stat-label">Loss Ratio</span>
                      <span className="stat-value" style={{ color: lossRatioColor }}>
                        {(kpi.loss_ratio * 100).toFixed(1)}%
                      </span>
                      <span className="stat-sub">{kpi.loss_ratio < 0.7 ? "Healthy" : kpi.loss_ratio < 1 ? "Watch" : "Unsustainable"}</span>
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
                    <div className="card" style={{ padding: "24px" }}>
                      <h3 style={{ marginBottom: "16px" }}>Claims Breakdown</h3>
                      <div className="grid two" style={{ gap: "12px" }}>
                        <div>
                          <span className="stat-label">Total Claims</span>
                          <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{kpi.total_claims}</div>
                        </div>
                        <div>
                          <span className="stat-label">Avg Claim Value</span>
                          <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>₹{kpi.avg_claim_value}</div>
                        </div>
                        <div>
                          <span className="stat-label">Approved</span>
                          <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--success)" }}>{kpi.approved_claims}</div>
                        </div>
                        <div>
                          <span className="stat-label">Pending</span>
                          <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--warning)" }}>{kpi.pending_claims}</div>
                        </div>
                      </div>
                    </div>
                    <div className="card" style={{ padding: "24px" }}>
                      <h3 style={{ marginBottom: "16px" }}>Fraud Detection</h3>
                      <div className="grid two" style={{ gap: "12px" }}>
                        <div>
                          <span className="stat-label">Auto-approved</span>
                          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--success)" }}>{kpi.auto_approved}</div>
                        </div>
                        <div>
                          <span className="stat-label">Flagged for Review</span>
                          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--error)" }}>{kpi.fraud_flagged}</div>
                        </div>
                        <div>
                          <span className="stat-label">Soft Review</span>
                          <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--warning)" }}>{kpi.soft_review}</div>
                        </div>
                        <div>
                          <span className="stat-label">Avg Fraud Score</span>
                          <div style={{ fontSize: "1.2rem", fontWeight: 600 }}>{adminFraud ? (adminFraud.avg_fraud_score * 100).toFixed(1) + "%" : "—"}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {adminSection === "claims" && adminClaimsByTrigger && (
                <section>
                  <h2 style={{ fontSize: "1.5rem", marginBottom: "20px" }}>Claims by Trigger Type</h2>
                  <div className="card" style={{ padding: "24px" }}>
                    {adminClaimsByTrigger.length === 0 ? (
                      <div className="empty-state">
                        <div className="empty-icon">📋</div>
                        <div>No claims data yet</div>
                      </div>
                    ) : (
                      <div className="data-list">
                        {adminClaimsByTrigger.map((row: any) => {
                          const maxCount = Math.max(...adminClaimsByTrigger.map((r: any) => r.count), 1);
                          return (
                            <div className="data-item" key={row.event_type} style={{ alignItems: "center" }}>
                              <div className="item-main" style={{ flex: 1 }}>
                                <span className="item-title">
                                  {eventIcon[row.event_type] || "📋"} {String(row.event_type || "").replace(/_/g, " ")}
                                </span>
                                <div style={{ background: "var(--surface-raised)", borderRadius: "6px", height: "8px", marginTop: "6px", overflow: "hidden" }}>
                                  <div style={{ height: "100%", borderRadius: "6px", background: "var(--primary)", width: `${(row.count / maxCount) * 100}%` }} />
                                </div>
                              </div>
                              <div className="item-amount">{row.count}</div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </section>
              )}

              {adminSection === "fraud" && !adminFraud && (
                <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-dim)" }}>Loading fraud data...</div>
              )}

              {adminSection === "fraud" && adminFraud && (
                <section>
                  <h2 style={{ fontSize: "1.5rem", marginBottom: "6px" }}>Advanced Fraud Detection</h2>
                  <p className="subtitle" style={{ marginBottom: "20px" }}>GPS spoofing, weather cross-reference, velocity checks, and anomaly scoring</p>

                  <div className="grid four" style={{ marginBottom: "24px" }}>
                    <div className="stat-card">
                      <span className="stat-label">Total Checks</span>
                      <span className="stat-value">{adminFraud.total_checks}</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Avg Fraud Score</span>
                      <span className="stat-value">{(adminFraud.avg_fraud_score * 100).toFixed(1)}%</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Auto-approved</span>
                      <span className="stat-value" style={{ color: "var(--success)" }}>{adminFraud.by_status?.auto_approve || 0}</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Manual Review</span>
                      <span className="stat-value" style={{ color: "var(--error)" }}>{adminFraud.by_status?.manual_review || 0}</span>
                    </div>
                  </div>

                  {adminFraud.high_risk_claims?.length > 0 && (
                    <div className="card" style={{ padding: "24px" }}>
                      <h3 style={{ marginBottom: "16px" }}>High-Risk Claims (score &gt; 50%)</h3>
                      <div style={{ overflowX: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.84rem" }}>
                          <thead>
                            <tr style={{ borderBottom: "2px solid var(--border)" }}>
                              <th style={{ textAlign: "left", padding: "8px 12px", color: "var(--text-dim)", fontWeight: 600 }}>Claim</th>
                              <th style={{ textAlign: "center", padding: "8px 6px", color: "var(--text-dim)", fontWeight: 600 }}>Score</th>
                              <th style={{ textAlign: "center", padding: "8px 6px", color: "var(--text-dim)", fontWeight: 600 }}>GPS</th>
                              <th style={{ textAlign: "center", padding: "8px 6px", color: "var(--text-dim)", fontWeight: 600 }}>Dup/Vel</th>
                              <th style={{ textAlign: "center", padding: "8px 6px", color: "var(--text-dim)", fontWeight: 600 }}>Activity</th>
                              <th style={{ textAlign: "center", padding: "8px 6px", color: "var(--text-dim)", fontWeight: 600 }}>Anomaly</th>
                              <th style={{ textAlign: "center", padding: "8px 6px", color: "var(--text-dim)", fontWeight: 600 }}>Source</th>
                              <th style={{ textAlign: "center", padding: "8px 6px", color: "var(--text-dim)", fontWeight: 600 }}>Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {adminFraud.high_risk_claims.map((fc: any) => (
                              <tr key={fc.claim_id} style={{ borderBottom: "1px solid var(--border)" }}>
                                <td style={{ padding: "8px 12px", fontWeight: 600 }}>#{fc.claim_id}</td>
                                <td style={{ textAlign: "center", padding: "8px 6px", fontWeight: 700, color: fc.fraud_score > 0.7 ? "var(--error)" : "var(--warning)" }}>{(fc.fraud_score * 100).toFixed(0)}%</td>
                                <td style={{ textAlign: "center", padding: "8px 6px" }}>{(fc.gps_score * 100).toFixed(0)}%</td>
                                <td style={{ textAlign: "center", padding: "8px 6px" }}>{(fc.duplicate_score * 100).toFixed(0)}%</td>
                                <td style={{ textAlign: "center", padding: "8px 6px" }}>{(fc.activity_score * 100).toFixed(0)}%</td>
                                <td style={{ textAlign: "center", padding: "8px 6px" }}>{(fc.anomaly_score * 100).toFixed(0)}%</td>
                                <td style={{ textAlign: "center", padding: "8px 6px" }}>{(fc.source_score * 100).toFixed(0)}%</td>
                                <td style={{ textAlign: "center", padding: "8px 6px" }}>
                                  <span className={`badge ${fc.review_status === "manual_review" ? "pending" : "success"}`} style={{ zoom: 0.85 }}>
                                    {fc.review_status.replace("_", " ")}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  <div className="card" style={{ padding: "24px", marginTop: "20px" }}>
                    <h3 style={{ marginBottom: "12px" }}>Fraud Signals Explained</h3>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", fontSize: "0.85rem" }}>
                      {[
                        { name: "GPS Spoofing", desc: "Worker's registered zone vs event zone + GPS enabled status", weight: "20%" },
                        { name: "Weather Cross-ref", desc: "Claimed disruption verified against live/historical weather data", weight: "20%" },
                        { name: "Duplicate / Velocity", desc: "Too many claims in a short window from same worker", weight: "20%" },
                        { name: "Activity Absence", desc: "Claims during hours when the worker is unlikely to be on shift", weight: "15%" },
                        { name: "Anomaly Payout", desc: "Payout amount disproportionate to weekly income", weight: "15%" },
                        { name: "Source Conflict", desc: "Event from unverified or mock sources", weight: "10%" },
                      ].map(s => (
                        <div key={s.name} style={{ padding: "14px", background: "var(--surface-raised)", borderRadius: "10px" }}>
                          <div style={{ fontWeight: 700, marginBottom: "4px" }}>{s.name} <span style={{ color: "var(--text-dim)", fontWeight: 400 }}>({s.weight})</span></div>
                          <div style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>{s.desc}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              )}

              {adminSection === "claims" && !adminClaimsByTrigger && (
                <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-dim)" }}>Loading claims data...</div>
              )}

              {adminSection === "predictions" && !adminPredictions && (
                <div style={{ textAlign: "center", padding: "60px 0", color: "var(--text-dim)" }}>Loading predictions...</div>
              )}

              {adminSection === "predictions" && adminPredictions && (
                <section>
                  <h2 style={{ fontSize: "1.5rem", marginBottom: "6px" }}>Predictive Analytics — {adminPredictions.city}</h2>
                  <p className="subtitle" style={{ marginBottom: "20px" }}>{adminPredictions.forecast_window} · Based on last 4 weeks of event data</p>

                  <div className="grid four" style={{ marginBottom: "24px" }}>
                    <div className="stat-card">
                      <span className="stat-label">Events (4 weeks)</span>
                      <span className="stat-value">{adminPredictions.summary.total_events_4w}</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Claims (4 weeks)</span>
                      <span className="stat-value">{adminPredictions.summary.total_claims_4w}</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Payouts (4 weeks)</span>
                      <span className="stat-value">₹{adminPredictions.summary.total_payouts_4w}</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-label">Projected Weekly</span>
                      <span className="stat-value" style={{ color: "var(--accent)" }}>₹{adminPredictions.summary.projected_weekly_payout}</span>
                    </div>
                  </div>

                  <div className="card" style={{ padding: "24px" }}>
                    <h3 style={{ marginBottom: "16px" }}>Next Week Disruption Forecast</h3>
                    <div className="data-list">
                      {adminPredictions.disruption_forecasts.map((f: any) => (
                        <div className="data-item" key={f.event_type} style={{ alignItems: "center" }}>
                          <div className="item-main" style={{ flex: 1 }}>
                            <span className="item-title">
                              {eventIcon[f.event_type] || "📋"} {f.label}
                              <span style={{ marginLeft: "8px", fontSize: "0.75rem" }}>{trendIcon(f.risk_trend)} {f.risk_trend}</span>
                            </span>
                            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "6px" }}>
                              <div style={{ flex: 1, background: "var(--surface-raised)", borderRadius: "6px", height: "8px", overflow: "hidden" }}>
                                <div style={{
                                  height: "100%", borderRadius: "6px",
                                  background: f.next_week_probability > 0.6 ? "var(--error)" : f.next_week_probability > 0.3 ? "var(--warning)" : "var(--success)",
                                  width: `${f.next_week_probability * 100}%`,
                                }} />
                              </div>
                              <span style={{ fontSize: "0.82rem", fontWeight: 700, minWidth: "40px" }}>{(f.next_week_probability * 100).toFixed(0)}%</span>
                            </div>
                            <div style={{ fontSize: "0.78rem", color: "var(--text-dim)", marginTop: "4px" }}>
                              {f.last_4_weeks_count} events in 4 wks · ~{f.expected_claims} expected claims
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              )}

              {adminSection === "payouts" && (
                <section>
                  <h2 style={{ fontSize: "1.5rem", marginBottom: "6px" }}>Payout Ledger</h2>
                  <p className="subtitle" style={{ marginBottom: "20px" }}>Razorpay test-mode transactions — all UPI payouts to workers</p>

                  <div className="card" style={{ padding: "24px" }}>
                    {adminPayoutsLedger.length === 0 ? (
                      <div className="empty-state">
                        <div className="empty-icon">💸</div>
                        <div>No payouts yet</div>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-dim)", marginTop: "8px" }}>Payouts are auto-initiated when claims are approved</p>
                      </div>
                    ) : (
                      <div style={{ overflowX: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.84rem" }}>
                          <thead>
                            <tr style={{ borderBottom: "2px solid var(--border)" }}>
                              <th style={{ textAlign: "left", padding: "8px 12px", color: "var(--text-dim)", fontWeight: 600 }}>ID</th>
                              <th style={{ textAlign: "left", padding: "8px 12px", color: "var(--text-dim)", fontWeight: 600 }}>Worker</th>
                              <th style={{ textAlign: "right", padding: "8px 12px", color: "var(--text-dim)", fontWeight: 600 }}>Amount</th>
                              <th style={{ textAlign: "center", padding: "8px 12px", color: "var(--text-dim)", fontWeight: 600 }}>Method</th>
                              <th style={{ textAlign: "center", padding: "8px 12px", color: "var(--text-dim)", fontWeight: 600 }}>Status</th>
                              <th style={{ textAlign: "left", padding: "8px 12px", color: "var(--text-dim)", fontWeight: 600 }}>Gateway Ref</th>
                              <th style={{ textAlign: "left", padding: "8px 12px", color: "var(--text-dim)", fontWeight: 600 }}>Time</th>
                            </tr>
                          </thead>
                          <tbody>
                            {adminPayoutsLedger.map((p: any) => (
                              <tr key={p.id} style={{ borderBottom: "1px solid var(--border)" }}>
                                <td style={{ padding: "8px 12px", fontWeight: 600 }}>#{p.id}</td>
                                <td style={{ padding: "8px 12px" }}>{p.worker_name || `Worker #${p.worker_id}`}</td>
                                <td style={{ padding: "8px 12px", textAlign: "right", fontWeight: 700, color: "var(--success)" }}>₹{p.amount}</td>
                                <td style={{ padding: "8px 12px", textAlign: "center" }}>
                                  <span className="badge" style={{ zoom: 0.85 }}>UPI</span>
                                </td>
                                <td style={{ padding: "8px 12px", textAlign: "center" }}>
                                  <span className={`badge ${p.status === "success" ? "success" : "pending"}`} style={{ zoom: 0.85 }}>
                                    {p.status === "success" ? "PAID" : p.status.toUpperCase()}
                                  </span>
                                </td>
                                <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: "0.78rem" }}>{p.gateway_ref}</td>
                                <td style={{ padding: "8px 12px", fontSize: "0.78rem", color: "var(--text-dim)" }}>
                                  {p.completed_at ? formatTime(p.completed_at) : p.initiated_at ? formatTime(p.initiated_at) : "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </section>
              )}
            </>
          )}
        </main>
      </div>
    );
  }

  return null;
}

export default App;
