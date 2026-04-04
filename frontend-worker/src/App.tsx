import { useState, useEffect, useCallback } from "react";
import { api, WorkerPayload } from "./services/api";

type View = "otp" | "register" | "quote" | "dashboard";

type DashboardSection = "home" | "policy" | "claims" | "live";

function App() {
  const [view, setView] = useState<View>("otp");
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
  const [shiftRec, setShiftRec] = useState<any>(null);
  const [shiftRecLoading, setShiftRecLoading] = useState(false);

  // Dashboard data refresh
  const fetchDashboardData = useCallback(async () => {
    if (!workerId) return;
    try {
      const [p, c, s] = await Promise.all([
        api.getPolicies(workerId),
        api.getClaims(workerId),
        api.getClaimsSummary(workerId),
      ]);
      setPolicies(p);
      setClaims(c);
      setClaimsSummary(s);
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
          });
          break;
        default:
          return;
      }
      setSimulatorLastResult(res);
      await fetchDashboardData();
    } catch (err) {
      console.error(err);
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
    s === "approved" ? "success" : s === "fraud_check" ? "pending" : "";

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
  //  VIEW: OTP VERIFICATION
  // ═══════════════════════════════════════════════════════════════
  if (view === "otp") {
    return (
      <div className="app-container center-view">
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
            <div className="hero-shield">🛡️</div>
            <h2>SurakshaShift AI</h2>
            <p className="subtitle">AI-Powered Income Protection for Gig Workers</p>
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
                  OTP sent to +91 {phone} <span style={{ color: "var(--text-dim)", fontSize: "0.8rem" }}>(use 123456)</span>
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
          <div className="wizard-footer">
            Covering 10L+ workers across India · Weekly Plans from ₹15
          </div>
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════
  //  VIEW: REGISTRATION FORM
  // ═══════════════════════════════════════════════════════════════
  if (view === "register") {
    return (
      <div className="app-container center-view">
        <div className="card wizard-card" style={{ maxWidth: "580px" }}>
          <div className="wizard-progress">
            <div className="progress-step done">✓</div>
            <div className="progress-line filled" />
            <div className="progress-step active">2</div>
            <div className="progress-line" />
            <div className="progress-step">3</div>
            <div className="progress-line" />
            <div className="progress-step">4</div>
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
              {loading ? "Analyzing Risk..." : "Get My AI Risk Premium ⚡"}
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
          { key: "rain_risk", label: "Rain exposure (this quote)" },
          { key: "flood_risk", label: "Flood exposure (this quote)" },
          { key: "aqi_risk", label: "AQI exposure (this quote)" },
          { key: "closure_risk", label: "Closure signal (news / pricing)" },
          { key: "shift_exposure", label: "Shift exposure (your schedule)" },
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
    const riskColor =
      riskTone === "low"
        ? "var(--success)"
        : riskTone === "moderate"
          ? "var(--primary-hover)"
          : riskTone === "high"
            ? "var(--warning)"
            : "hsl(350, 80%, 62%)";
    return (
      <div className="app-container center-view" style={{ padding: "40px" }}>
        <div className="wizard-progress" style={{ marginBottom: "40px" }}>
          <div className="progress-step done">✓</div>
          <div className="progress-line filled" />
          <div className="progress-step done">✓</div>
          <div className="progress-line filled" />
          <div className="progress-step active">3</div>
          <div className="progress-line" />
          <div className="progress-step">4</div>
        </div>

        <h2 style={{ fontSize: "2.2rem", marginBottom: "8px", textAlign: "center" }}>Your AI-Calculated Shield 🛡️</h2>
        <p className="subtitle" style={{ marginBottom: "12px", textAlign: "center" }}>
          Actuarial + ML blend • Live factors for your zone • {profile?.zone_name}, {profile?.city}
        </p>
        <p style={{ textAlign: "center", fontSize: "0.85rem", color: "var(--text-dim)", marginBottom: "24px" }}>
          Premium uses <strong style={{ color: "var(--primary-hover)" }}>live</strong> weather, AQI, and{" "}
          <strong style={{ color: "var(--primary-hover)" }}>news</strong> (bandh / curfew signals) for {profile?.city}
          {quoteLiveFactors?.fetched_at && (
            <> · Updated {new Date(quoteLiveFactors.fetched_at).toLocaleString("en-IN")}</>
          )}
        </p>

        {quoteLiveFactors && (
          <div
            className="card"
            style={{
              maxWidth: "900px",
              margin: "0 auto 28px",
              padding: "16px 20px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              background: "hsla(210, 25%, 12%, 0.85)",
              borderColor: "var(--border)",
            }}
          >
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "16px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "20px", alignItems: "center" }}>
                <span className="live-badge" style={{ marginRight: "4px" }}>
                  <span className="pulse-dot" /> LIVE INPUTS
                </span>
                <span style={{ fontSize: "0.88rem" }}>
                  🌡️ {quoteLiveFactors.weather?.temperature_c ?? "—"}°C · {quoteLiveFactors.weather?.condition ?? "—"}
                  <span style={{ color: "var(--text-dim)", marginLeft: "8px" }}>
                    ({quoteLiveFactors.weather?.source === "openweathermap" ? "OpenWeatherMap" : quoteLiveFactors.weather?.source || "—"})
                  </span>
                </span>
                <span style={{ fontSize: "0.88rem" }}>
                  🌧️ {quoteLiveFactors.weather?.rain_mm_1h ?? 0} mm/h · 💨 {quoteLiveFactors.weather?.wind_speed_kmh ?? 0} km/h
                </span>
                <span style={{ fontSize: "0.88rem" }}>
                  😷 AQI {quoteLiveFactors.aqi?.aqi ?? "—"}
                  <span style={{ color: "var(--text-dim)", marginLeft: "6px" }}>
                    ({quoteLiveFactors.aqi?.source === "waqi" ? "WAQI" : quoteLiveFactors.aqi?.source || "mock"})
                  </span>
                </span>
                <span
                  style={{ fontSize: "0.88rem", color: "var(--text-muted)" }}
                  title={
                    quoteLiveFactors.closure_source === "newsdata" ||
                    quoteLiveFactors.closure_source === "gnews"
                      ? "Live news (NewsData.io or GNews): India stories mentioning bandh, curfew, hartal, etc., matched to your city/region"
                      : "Set NEWSDATA_API_KEY and/or GNEWS_API_KEY for real headlines; otherwise a low demo baseline"
                  }
                >
                  🚧 Closure {(typeof quoteLiveFactors.closure_risk === "number" ? (quoteLiveFactors.closure_risk * 100).toFixed(0) : "—")}%
                  <span style={{ color: "var(--text-dim)", marginLeft: "6px", fontSize: "0.8rem" }}>
                    (
                      {quoteLiveFactors.closure_source === "newsdata" ||
                      quoteLiveFactors.closure_source === "gnews"
                        ? "news"
                        : "mock"}
                    )
                  </span>
                </span>
              </div>
              <button
                type="button"
                onClick={handleRefreshQuote}
                disabled={loading}
                style={{
                  whiteSpace: "nowrap",
                  padding: "8px 14px",
                  borderRadius: "8px",
                  border: "1px solid var(--border)",
                  background: "hsla(210, 20%, 18%, 0.9)",
                  color: "var(--text-main)",
                  cursor: loading ? "wait" : "pointer",
                }}
              >
                {loading ? "Refreshing…" : "↻ Refresh live quote"}
              </button>
            </div>
            {Array.isArray(quoteLiveFactors.closure_headlines) && quoteLiveFactors.closure_headlines.length > 0 && (
              <div style={{ fontSize: "0.78rem", color: "var(--text-dim)", lineHeight: 1.45 }}>
                <strong style={{ color: "var(--text-muted)" }}>News matched:</strong>
                <ul style={{ margin: "6px 0 0 18px", padding: 0 }}>
                  {quoteLiveFactors.closure_headlines.slice(0, 3).map((h: { title?: string }, i: number) => (
                    <li key={i}>{h.title || "(no title)"}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <div className="grid" style={{ maxWidth: "900px", margin: "0 auto", gridTemplateColumns: "1fr 1fr" }}>
          {/* Left: Plan selector */}
          <div className="card premium-card">
            <div
              style={{
                marginBottom: "14px",
                borderRadius: "10px",
                border: `1px solid ${riskColor}`,
                background: "hsla(210,20%,12%,0.75)",
                padding: "10px 12px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <span style={{ fontSize: "0.82rem", color: "var(--text-dim)" }}>Risk profile</span>
              <strong style={{ color: riskColor, letterSpacing: "0.04em" }}>
                {(plansQuote?.risk_level || "moderate").toUpperCase()}
              </strong>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {planList.map((plan: any) => {
                const isSelected = selectedPlan?.plan_id === plan.plan_id;
                const isRecommended = plan.plan_id === "standard";
                return (
                  <button
                    key={plan.plan_id}
                    type="button"
                    onClick={() => setSelectedPlanId(plan.plan_id)}
                    style={{
                      textAlign: "left",
                      borderRadius: "12px",
                      border: isSelected ? "1px solid var(--primary)" : "1px solid var(--border)",
                      background: isSelected ? "hsla(250,85%,65%,0.10)" : "hsla(210,20%,12%,0.70)",
                      padding: "14px",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
                      <div>
                        <div style={{ fontWeight: 700 }}>{plan.label}</div>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-dim)", marginTop: "4px" }}>
                          {plan.description}
                        </div>
                      </div>
                      {isRecommended && (
                        <span
                          style={{
                            borderRadius: "999px",
                            border: "1px solid var(--success)",
                            color: "var(--success)",
                            background: "hsla(140,60%,55%,0.12)",
                            fontSize: "0.68rem",
                            fontWeight: 700,
                            padding: "3px 7px",
                            letterSpacing: "0.05em",
                          }}
                        >
                          RECOMMENDED
                        </span>
                      )}
                    </div>
                    <div style={{ marginTop: "10px", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                      <div style={{ fontSize: "1.45rem", fontWeight: 800, color: "var(--primary-hover)" }}>
                        ₹{Number(plan.premium_weekly).toFixed(0)}
                        <span style={{ fontSize: "0.8rem", color: "var(--text-dim)", marginLeft: "4px" }}>/week</span>
                      </div>
                      <div style={{ fontSize: "0.78rem", color: "var(--text-dim)" }}>
                        {Number(plan.risk_rate_pct).toFixed(2)}% risk rate
                      </div>
                    </div>
                    <div style={{ marginTop: "8px", fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      Max payout ₹{Number(plan.max_weekly_payout).toFixed(0)} · Coverage {(Number(plan.coverage_pct) * 100).toFixed(0)}%
                    </div>
                  </button>
                );
              })}
            </div>

            <button onClick={handleSubscribe} disabled={loading || !selectedPlan} style={{ width: "100%", marginTop: "18px", padding: "18px" }}>
              {loading || !selectedPlan
                ? "Activating Shield..."
                : `Pay ₹${Number(selectedPlan.premium_weekly).toFixed(0)} via UPI & Activate`}
            </button>

            <div className="exclusion-note">
              ⚠️ Excludes: health, life, accident, vehicle repair coverage
            </div>
          </div>

          {/* Right: live inputs vs training-time GBM sensitivity */}
          <div className="card" style={{ background: "hsla(210, 20%, 10%, 0.5)" }}>
            {exposureInputs && (
              <>
                <h3 style={{ marginBottom: "8px" }}>📍 This quote: exposure inputs</h3>
                <p style={{ color: "var(--text-dim)", fontSize: "0.82rem", lineHeight: 1.5, marginBottom: "16px" }}>
                  Values fed into your actuarial + ML premium for <strong>{exposureInputs.city}</strong> (0–100% scale).
                  These come from live/mocked weather, WAQI, news closure signal, and your shift pattern—not from the
                  training chart below.
                </p>
                <div className="feature-importance-list" style={{ marginBottom: "28px" }}>
                  {exposureRows.map(({ key, label }) => {
                    const v = Number((exposureInputs as Record<string, number>)[key] ?? 0);
                    return (
                      <div className="fi-row" key={key}>
                        <div className="fi-label">{label}</div>
                        <div className="fi-bar-container">
                          <div
                            className="fi-bar"
                            style={{
                              width: `${(v / maxExp) * 100}%`,
                              background: "linear-gradient(90deg, hsl(190, 75%, 45%), hsl(210, 80%, 55%))",
                            }}
                          />
                        </div>
                        <div className="fi-value">{(v * 100).toFixed(0)}%</div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            <h3 style={{ marginBottom: "8px" }}>🧠 GBM sensitivity (training data)</h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", lineHeight: 1.6, marginBottom: "16px" }}>
              {riskQuote.explanation}
            </p>
            <p style={{ color: "var(--text-dim)", fontSize: "0.78rem", lineHeight: 1.5, marginBottom: "16px" }}>
              The bars below are <strong>global feature importances</strong> from the GBM fit on actuarial-anchored
              training scenarios. If rain stays high here while live rain is low, that reflects how often the model
              splits on rain in training—not current rainfall.
            </p>

            <div className="feature-importance-list">
              {Object.entries(importances).map(([name, value]) => (
                <div className="fi-row" key={name}>
                  <div className="fi-label">{name.replace(/_/g, " ")}</div>
                  <div className="fi-bar-container">
                    <div className="fi-bar" style={{ width: `${(Number(value) / maxImp) * 100}%` }} />
                  </div>
                  <div className="fi-value">{(Number(value) * 100).toFixed(1)}%</div>
                </div>
              ))}
            </div>

            <div className="alert" style={{ background: "hsla(250, 85%, 65%, 0.1)", borderColor: "var(--primary)", marginTop: "24px" }}>
              <div className="alert-icon">⚡</div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                <strong style={{ color: "var(--primary-hover)" }}>Zero-Touch Payouts:</strong> When sensors detect a disruption in {profile?.zone_name}, claims are auto-generated and paid to your UPI instantly.
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

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">SurakshaShift</div>
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
            📋 Claims History
          </button>
          <button
            type="button"
            className={`nav-link ${dashboardSection === "live" ? "active" : ""}`}
            onClick={() => scrollToDashboardSection("live")}
          >
            🌦️ Live Conditions
          </button>
        </nav>
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
              <span className="stat-label">Weekly Premium</span>
              <span className="stat-value">₹{activePolicy?.premium_weekly || "0"}</span>
              <span className="stat-sub">Auto-renews weekly</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Max Payout</span>
              <span className="stat-value" style={{ color: "var(--success)" }}>
                ₹{activePolicy?.max_weekly_payout || "0"}
              </span>
              <span className="stat-sub">Up to 40% of avg income</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Total Claimed</span>
              <span className="stat-value" style={{ color: "var(--secondary)" }}>
                ₹{claimsSummary?.total_payout?.toFixed(0) || "0"}
              </span>
              <span className="stat-sub">{claimsSummary?.total_claims || 0} claims filed</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Risk Score</span>
              <span className="stat-value" style={{ color: "var(--primary)" }}>
                {((profile?.risk_score || 0) * 100).toFixed(0)}
              </span>
              <span className="stat-sub">Risk engine v1</span>
            </div>
          </div>

          <div className="card shift-guardian-card" style={{ marginTop: "28px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
              <h3 style={{ display: "flex", alignItems: "center", gap: "8px", margin: 0, flexWrap: "wrap" }}>
                <span>🧭</span> Shift Guardian
                <span
                  style={{
                    fontSize: "0.72rem",
                    padding: "3px 8px",
                    borderRadius: "999px",
                    background: "hsla(140,60%,55%,0.15)",
                    border: "1px solid var(--success)",
                    color: "var(--success)",
                    fontWeight: 700,
                    letterSpacing: "0.06em",
                  }}
                >
                  AI-POWERED
                </span>
              </h3>
              <button
                type="button"
                onClick={fetchShiftRecommendation}
                disabled={shiftRecLoading}
                style={{
                  padding: "8px 16px",
                  fontSize: "0.85rem",
                  borderRadius: "8px",
                  background: "hsla(250,85%,65%,0.15)",
                  border: "1px solid var(--primary)",
                  color: "var(--primary-hover)",
                  cursor: shiftRecLoading ? "wait" : "pointer",
                }}
              >
                {shiftRecLoading ? "Analysing zones..." : "Check Before I Start Shift →"}
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
                          ? "hsla(220,85%,62%,0.12)"
                          : "var(--warning-bg)",
                    border: `1px solid ${
                      shiftRec.alert_type === "all_clear"
                        ? "var(--success)"
                        : shiftRec.alert_type === "zone_switch_recommended"
                          ? "hsl(220,85%,62%)"
                          : "var(--warning)"
                    }`,
                    fontSize: "0.9rem",
                    lineHeight: 1.6,
                    color:
                      shiftRec.alert_type === "all_clear"
                        ? "var(--success)"
                        : shiftRec.alert_type === "zone_switch_recommended"
                          ? "hsl(220,90%,74%)"
                          : "var(--warning)",
                  }}
                >
                  {shiftRec.recommendation_text}
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div
                    style={{
                      padding: "14px",
                      borderRadius: "10px",
                      background: "hsla(210,20%,10%,0.5)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "0.72rem",
                        color: "var(--text-dim)",
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        marginBottom: "6px",
                      }}
                    >
                      Your zone
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "1rem", marginBottom: "8px" }}>
                      📍 {shiftRec.current_zone?.zone_name}
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      Disruption:{" "}
                      <strong style={{ color: "var(--warning)" }}>{shiftRec.current_zone?.disruption_probability}%</strong>
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      Safety score: <strong>{shiftRec.current_zone?.income_protection_score}</strong>/100
                    </div>
                  </div>

                  <div
                    style={{
                      padding: "14px",
                      borderRadius: "10px",
                      background: "hsla(140,60%,55%,0.08)",
                      border: "1px solid var(--success)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "0.72rem",
                        color: "var(--success)",
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        marginBottom: "6px",
                      }}
                    >
                      Recommended
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "1rem", marginBottom: "8px" }}>
                      ✅ {shiftRec.recommended_zone?.zone_name}
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      Disruption:{" "}
                      <strong style={{ color: "var(--success)" }}>
                        {shiftRec.recommended_zone?.disruption_probability}%
                      </strong>
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      Safety score: <strong>{shiftRec.recommended_zone?.income_protection_score}</strong>/100
                    </div>
                  </div>
                </div>

                {shiftRec.estimated_income_difference > 0 && (
                  <div
                    style={{
                      padding: "12px 16px",
                      borderRadius: "10px",
                      background: "hsla(250,85%,65%,0.1)",
                      border: "1px solid var(--primary)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: "8px",
                    }}
                  >
                    <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                      Estimated income protected by switching zones
                    </span>
                    <span style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--primary-hover)" }}>
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
                      {[shiftRec.current_zone, ...shiftRec.alternatives].map((z: any) => (
                        <div
                          key={z.zone_name}
                          style={{
                            padding: "8px 12px",
                            borderRadius: "8px",
                            fontSize: "0.78rem",
                            background: "hsla(210,20%,12%,0.6)",
                            border: "1px solid var(--border)",
                          }}
                        >
                          <div style={{ fontWeight: 600 }}>{z.zone_name}</div>
                          <div style={{ color: "var(--text-dim)", marginTop: "2px" }}>
                            {z.disruption_probability}% · {z.risk_level}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                  Window: {shiftRec.forecast_window} · {shiftRec.generated_at && new Date(shiftRec.generated_at).toLocaleString("en-IN")}
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
                { id: "rain", icon: "🌧️", label: "Heavy Rain", desc: "62mm/hr rainfall", color: "hsl(210, 80%, 40%)" },
                { id: "flood", icon: "🌊", label: "Flash Flood", desc: "Water level 35cm+", color: "hsl(200, 70%, 35%)" },
                { id: "aqi", icon: "😷", label: "AQI Severe", desc: "AQI > 300 (hazardous)", color: "hsl(30, 70%, 40%)" },
                { id: "closure", icon: "🚧", label: "Zone Closure", desc: "Curfew / strike alert", color: "hsl(350, 70%, 40%)" },
                { id: "outage", icon: "📡", label: "Platform Outage", desc: `${profile?.platform_name} down 45min`, color: "hsl(270, 60%, 40%)" },
              ].map(t => (
                <button
                  key={t.id}
                  className="trigger-btn"
                  onClick={() => handleTrigger(t.id)}
                  disabled={triggerLoading !== null || !activePolicy}
                  style={{ "--trigger-color": t.color } as React.CSSProperties}
                >
                  <span className="trigger-icon">{t.icon}</span>
                  <span className="trigger-label">{t.label}</span>
                  <span className="trigger-desc">{t.desc}</span>
                  {triggerLoading === t.id && <span className="trigger-loading" />}
                </button>
              ))}
            </div>

            <div className="alert" style={{ background: "hsla(210, 20%, 15%, 0.8)", borderColor: "var(--border)", marginTop: "20px" }}>
              <div className="alert-icon">ℹ️</div>
              <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                Each trigger ingests a disruption event → the backend matches it against your active policy → runs ML fraud scoring → auto-creates & approves a claim → payout is calculated based on disrupted hours and your weekly income.
              </div>
            </div>

            {simulatorLastResult && (
              <div
                className="alert"
                style={{
                  marginTop: "14px",
                  background: simulatorLastResult.error
                    ? "hsla(350, 50%, 20%, 0.5)"
                    : simulatorLastResult.deduplicated
                      ? "hsla(40, 60%, 20%, 0.45)"
                      : "hsla(140, 45%, 18%, 0.45)",
                  borderColor: simulatorLastResult.error
                    ? "hsl(350, 60%, 45%)"
                    : simulatorLastResult.deduplicated
                      ? "var(--warning)"
                      : "var(--success)",
                }}
              >
                <div className="alert-icon">{simulatorLastResult.error ? "⚠️" : simulatorLastResult.deduplicated ? "⏳" : "✓"}</div>
                <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
                  {simulatorLastResult.error ? (
                    <span>{simulatorLastResult.message}</span>
                  ) : simulatorLastResult.deduplicated ? (
                    <span>{simulatorLastResult.reason || "Duplicate event skipped (cooldown still applies to non-mock ingests)."}</span>
                  ) : (
                    <span>
                      Event #{simulatorLastResult.event_id}: <strong>{simulatorLastResult.claim_candidates}</strong> claim(s) created.
                      {simulatorLastResult.claim_candidates === 0 && (
                        <> Check policy coverage window, zone match, or weekly payout cap.</>
                      )}
                    </span>
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
          <h2 id="dash-claims-title" style={{ fontSize: "1.35rem", marginBottom: "16px" }}>
            📋 Claims History
          </h2>
          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
              <h3 style={{ margin: 0 }}>All claims</h3>
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
                          {claim.status.replace("_", " ").toUpperCase()}
                        </span>
                      </span>
                    </div>
                    <div
                      className="item-amount"
                      style={{ color: claim.status === "approved" ? "var(--success)" : "var(--text-main)" }}
                    >
                      ₹ {claim.approved_payout}
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
}

export default App;
