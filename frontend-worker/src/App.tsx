import { useState } from "react";

// --- Phase 1: Minimal-Scope Concept Prototype ---
// This is a single-page product vision showcase for the SurakshaShift AI platform.
// No backend connectivity. Purely demonstrates the IDEA.

const DISRUPTIONS = [
  { icon: "🌧️", title: "Heavy Rain & Floods", desc: "Waterlogging blocks delivery routes, halting all orders for hours." },
  { icon: "🔥", title: "Extreme Heat", desc: "Temperatures above 45°C make outdoor delivery dangerous and impossible." },
  { icon: "🌫️", title: "Severe Pollution (AQI)", desc: "Air quality index above 300 forces platforms to suspend operations." },
  { icon: "🚫", title: "Curfews & Zone Closures", desc: "Unplanned government curfews or market shutdowns block access." },
  { icon: "📱", title: "Platform Outages", desc: "App crashes or server downtime prevent order allocation." },
  { icon: "🚧", title: "Road Blockages", desc: "Strikes, protests, or accidents block major delivery corridors." }
];

const HOW_IT_WORKS = [
  { step: "01", icon: "📝", title: "Quick Onboarding", desc: "Worker registers with phone, zone, platform, and shift preferences. Takes under 2 minutes." },
  { step: "02", icon: "🤖", title: "AI Risk Scoring", desc: "Our ML model analyzes zone weather history, flood frequency, AQI trends, and more to calculate a fair weekly premium." },
  { step: "03", icon: "⚡", title: "Auto-Trigger Detection", desc: "Real-time monitoring of weather APIs, traffic feeds, and platform status. When a disruption crosses the threshold → claim is auto-created." },
  { step: "04", icon: "💰", title: "Instant Payout", desc: "Verified claims are paid directly to the worker's UPI wallet. No paperwork, no delays." }
];

function App() {
  const [demoActive, setDemoActive] = useState(false);
  const [demoStep, setDemoStep] = useState(0);

  function runDemo() {
    setDemoActive(true);
    setDemoStep(0);
    let step = 0;
    const interval = setInterval(() => {
      step++;
      setDemoStep(step);
      if (step >= 4) clearInterval(interval);
    }, 1500);
  }

  function resetDemo() {
    setDemoActive(false);
    setDemoStep(0);
  }

  return (
    <div className="app-container" style={{ flexDirection: "column" }}>
      {/* ── Top Nav Bar ── */}
      <header className="topnav">
        <div className="topnav-brand">🛡️ SurakshaShift AI</div>
        <nav className="topnav-links">
          <a href="#how">How It Works</a>
          <a href="#disruptions">Disruptions</a>
          <a href="#pricing">Pricing</a>
          <a href="#demo">Live Demo</a>
        </nav>
      </header>

      <main className="main-content" style={{ marginLeft: 0, maxWidth: "100%", padding: "0" }}>

        {/* ── Hero Section ── */}
        <section className="hero-section">
          <div className="hero-inner">
            <div className="hero-badge">Phase 1 Prototype • DEVTrails 2026</div>
            <h1 className="hero-title">
              Weekly Income Protection<br />
              for <span className="gradient-text">Delivery Workers</span>
            </h1>
            <p className="hero-subtitle">
              AI-powered parametric insurance that automatically detects disruptions
              and pays gig workers for lost income. No paperwork. No delays.
              Structured on a <strong>weekly pricing model</strong>.
            </p>
            <div className="hero-stats">
              <div className="hero-stat">
                <span className="stat-value">₹25–99</span>
                <span className="stat-label">Weekly Premium</span>
              </div>
              <div className="hero-stat">
                <span className="stat-value">Up to ₹1,400</span>
                <span className="stat-label">Max Weekly Payout</span>
              </div>
              <div className="hero-stat">
                <span className="stat-value">&lt; 5 min</span>
                <span className="stat-label">Claim to Payout</span>
              </div>
            </div>
            <a href="#demo"><button style={{ padding: "18px 40px", fontSize: "1.2rem" }}>Try the Demo ⚡</button></a>
          </div>
        </section>

        {/* ── How It Works ── */}
        <section id="how" className="content-section">
          <h2 className="section-title">How It Works</h2>
          <p className="section-subtitle">A seamless 4-step journey from onboarding to payout</p>
          <div className="grid four" style={{ marginTop: "40px" }}>
            {HOW_IT_WORKS.map((item) => (
              <div className="step-card" key={item.step}>
                <div className="step-number">{item.step}</div>
                <div style={{ fontSize: "2.5rem", marginBottom: "12px" }}>{item.icon}</div>
                <h3>{item.title}</h3>
                <p>{item.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Disruptions Covered ── */}
        <section id="disruptions" className="content-section" style={{ background: "hsla(230, 35%, 10%, 0.5)" }}>
          <h2 className="section-title">Disruptions We Cover</h2>
          <p className="section-subtitle">External events causing loss of working income — NOT health, life, accidents, or vehicle repair</p>
          <div className="grid three" style={{ marginTop: "40px" }}>
            {DISRUPTIONS.map((d) => (
              <div className="card disruption-card" key={d.title}>
                <div style={{ fontSize: "2.5rem", marginBottom: "12px" }}>{d.icon}</div>
                <h3>{d.title}</h3>
                <p style={{ color: "var(--text-muted)", marginTop: "8px" }}>{d.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Weekly Pricing Model ── */}
        <section id="pricing" className="content-section">
          <h2 className="section-title">Weekly Pricing Model</h2>
          <p className="section-subtitle">Aligned with gig worker payout cycles — pay weekly, protected weekly</p>
          <div className="grid two" style={{ marginTop: "40px", maxWidth: "900px", margin: "40px auto 0" }}>
            <div className="card" style={{ textAlign: "center", padding: "40px" }}>
              <h3 style={{ color: "var(--text-muted)", marginBottom: "16px" }}>How Premium is Calculated</h3>
              <div style={{ textAlign: "left", lineHeight: "2", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.9rem", background: "hsla(210, 20%, 8%, 0.7)", padding: "20px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
                <div><span style={{ color: "var(--secondary)" }}>base_premium</span> = ₹25</div>
                <div>+ <span style={{ color: "hsl(350, 70%, 65%)" }}>rain_risk_factor</span></div>
                <div>+ <span style={{ color: "hsl(350, 70%, 65%)" }}>flood_factor</span></div>
                <div>+ <span style={{ color: "hsl(350, 70%, 65%)" }}>aqi_factor</span></div>
                <div>+ <span style={{ color: "hsl(350, 70%, 65%)" }}>closure_factor</span></div>
                <div>− <span style={{ color: "var(--success)" }}>loyalty_discount</span></div>
                <div style={{ borderTop: "1px solid var(--border)", marginTop: "8px", paddingTop: "8px" }}>= <span style={{ color: "var(--primary-hover)", fontWeight: 700 }}>weekly_premium</span> (₹19 – ₹99)</div>
              </div>
            </div>
            <div className="card" style={{ padding: "40px" }}>
              <h3 style={{ color: "var(--text-muted)", marginBottom: "16px" }}>AI Risk Inputs</h3>
              <ul style={{ listStyle: "none", padding: 0, lineHeight: "2.2" }}>
                <li>📍 Zone weather history & flood frequency</li>
                <li>🌡️ Temperature & AQI trend data</li>
                <li>🚗 Traffic disruption history</li>
                <li>🕐 Worker shift hours & exposure</li>
                <li>🏍️ Platform type & delivery density</li>
                <li>📊 Historical claim frequency in zone</li>
              </ul>
            </div>
          </div>
        </section>

        {/* ── Interactive Demo ── */}
        <section id="demo" className="content-section" style={{ background: "hsla(230, 35%, 10%, 0.5)" }}>
          <h2 className="section-title">Interactive Concept Demo</h2>
          <p className="section-subtitle">See how a parametric trigger automatically protects a worker's income</p>
          
          <div className="card" style={{ maxWidth: "800px", margin: "40px auto 0", padding: "40px", textAlign: "center" }}>
            {!demoActive ? (
              <div>
                <p style={{ fontSize: "1.1rem", color: "var(--text-muted)", marginBottom: "24px" }}>
                  Simulate a <strong>heavy rainstorm</strong> in the Velachery delivery zone and watch the parametric engine respond in real-time.
                </p>
                <button onClick={runDemo} style={{ padding: "18px 40px", fontSize: "1.1rem" }}>
                  🌩️ Trigger Heavy Rain Event
                </button>
              </div>
            ) : (
              <div className="demo-timeline">
                <DemoStep active={demoStep >= 1} complete={demoStep > 1}
                  icon="🌧️" title="Disruption Detected"
                  detail="Heavy rain alert: 72mm in 3 hours in Velachery zone. Threshold exceeded (50mm)." />
                <DemoStep active={demoStep >= 2} complete={demoStep > 2}
                  icon="🤖" title="AI Claim Auto-Created"
                  detail="Parametric engine matched 3 active workers in zone. Claims generated automatically." />
                <DemoStep active={demoStep >= 3} complete={demoStep > 3}
                  icon="✅" title="Fraud Validation Passed"
                  detail="GPS consistency ✓ | Activity check ✓ | No duplicates ✓ | Fraud score: 0.12 (low risk)" />
                <DemoStep active={demoStep >= 4} complete={demoStep >= 4}
                  icon="💸" title="Instant Payout Released"
                  detail="₹320 credited to worker's UPI wallet. Total time: 4 minutes 12 seconds." />

                {demoStep >= 4 && (
                  <div style={{ marginTop: "32px" }}>
                    <div className="alert success" style={{ justifyContent: "center", fontSize: "1.1rem" }}>
                      <span className="alert-icon">🎉</span>
                      <span>Worker protected! ₹320 paid for 4 hours of lost income.</span>
                    </div>
                    <button className="secondary" onClick={resetDemo} style={{ marginTop: "16px" }}>
                      Reset Demo
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {/* ── Persona ── */}
        <section className="content-section">
          <h2 className="section-title">Target Persona</h2>
          <p className="section-subtitle">Grocery & Quick-Commerce Delivery Partners (Zepto, Blinkit, Instamart)</p>
          <div className="card" style={{ maxWidth: "700px", margin: "40px auto 0", padding: "32px" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className="data-item">
                <div className="item-main"><span className="item-title">Why this persona?</span></div>
              </div>
              <ul style={{ paddingLeft: "20px", lineHeight: "2", color: "var(--text-muted)" }}>
                <li>Highly sensitive to <strong>short-term local disruptions</strong></li>
                <li>Hyperlocal delivery model enables strong <strong>parametric trigger matching</strong></li>
                <li>Work zones are well-defined and map to weather/AQI data sources</li>
                <li>Weekly earnings cycle aligns perfectly with our pricing model</li>
                <li>Clear demo path: "Rain event in Zone A → shift disruption → auto payout"</li>
              </ul>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer style={{ textAlign: "center", padding: "40px", color: "var(--text-dim)", fontSize: "0.85rem", borderTop: "1px solid var(--border)" }}>
          SurakshaShift AI — DEVTrails 2026 • Phase 1 Prototype • Guidewire
        </footer>
      </main>
    </div>
  );
}

// --- Demo Step Component ---
function DemoStep({ active, complete, icon, title, detail }: { active: boolean; complete: boolean; icon: string; title: string; detail: string }) {
  return (
    <div style={{
      display: "flex",
      alignItems: "flex-start",
      gap: "16px",
      padding: "20px",
      borderRadius: "var(--radius-sm)",
      background: active ? (complete ? "var(--success-bg)" : "hsla(250, 85%, 65%, 0.1)") : "transparent",
      border: active ? `1px solid ${complete ? "var(--success)" : "var(--primary)"}` : "1px solid var(--border)",
      opacity: active ? 1 : 0.3,
      transition: "all 0.6s cubic-bezier(0.16, 1, 0.3, 1)",
      marginBottom: "12px",
      textAlign: "left"
    }}>
      <div style={{ fontSize: "2rem" }}>{complete ? "✅" : icon}</div>
      <div>
        <div style={{ fontWeight: 700, fontSize: "1.1rem", fontFamily: "'Outfit', sans-serif" }}>{title}</div>
        <div style={{ color: "var(--text-muted)", marginTop: "4px" }}>{detail}</div>
      </div>
    </div>
  );
}

export default App;
