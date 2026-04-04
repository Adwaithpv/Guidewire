# SurakshaShift AI

### Hyperlocal Income Protection for Delivery Partners in Q-Commerce

*AI-Powered Parametric Insurance for India's Q-Commerce Delivery Workers*

> **Team SharkBYTE · Guidewire DEVTrails 2026** · Phase 2 worker prototype + API

**Live worker app:** [https://sharkbytedevtrail.vercel.app/](https://sharkbytedevtrail.vercel.app/) — try the full flow in the browser (ensure the deployed API is reachable from `VITE_API_BASE` if you self-host the backend).

---

## Repository overview

| Path | What it is |
|------|------------|
| **`backend/`** | **FastAPI** app — SQLite by default, parametric event ingest, tiered pricing (actuarial + GBM), fraud scoring, claims, **Shift Guardian**, live risk factors (weather / AQI / news closure). |
| **`frontend-worker/`** | **React 18 + Vite + TypeScript** — light fintech UI: OTP → profile → live quote → dashboard (policy, **My claims**, live conditions, disruption **simulator** with step-by-step claim pipeline animation). |

### Quick start

```bash
# API (from repo root)
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate  ·  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Copy .env.example → .env (optional keys; mocks work when empty)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# Worker UI
cd frontend-worker
npm install
# Copy .env.example → .env (set VITE_API_BASE if API is not localhost:8000)
npm run dev
```

**Local:** open the Vite URL (e.g. `http://localhost:5173`). **Hosted:** use the [live app](https://sharkbytedevtrail.vercel.app/). **Demo OTP:** `123456`. Recommended evaluator flow: register → quote → activate policy → **Shift Guardian** → run a **simulator** trigger → watch **Automatic claim flow** → open **My claims**.

```bash
# Production build (CI-friendly)
cd frontend-worker && npm run build
```

### Environment variables

**`backend/.env`** (see `backend/.env.example`)

| Variable | Role |
|----------|------|
| `OPENWEATHERMAP_API_KEY` | OpenWeatherMap for live weather / rainfall in quotes |
| `WAQI_API_TOKEN` | WAQI for AQI |
| `NEWSDATA_API_KEY` | Preferred source for India closure/bandh headlines |
| `GNEWS_API_KEY` | Fallback news API if NewsData is unset or fails |
| `DATABASE_URL` | Default `sqlite:///./surakshashift.db` |
| `CORS_ORIGINS` | `*` in dev; comma-separated origins in production |

**`frontend-worker/.env`** — `VITE_API_BASE` (API origin, default `http://localhost:8000`).

### Implementation notes (honest scope)

- **Pricing:** ~**80%** transparent actuarial / tiered formula + **~20%** GBM residual (`actuarial-gbm-blend-v1`). Traceable in `backend/app/services/risk_service.py`, `pricing_service.py`, `app/ml/premium_model.py`. The quote screen surfaces **`model_version`**.
- **Simulator:** Ingests use `source_name` prefixed with `Mock …`; optional **`worker_id`** scopes claim creation to the logged-in worker (avoids one click → claims for all workers in the zone).
- **Policies:** New purchase **supersedes** prior active policies for that worker; trigger engine enforces **one claim per worker per disruption event** to prevent duplicate rows from legacy data.
- **External data:** Works with **mocks** when keys are empty; configure keys for live demos (OpenWeatherMap, WAQI, NewsData/GNews).

---

## 1. The Problem We Are Solving

Traditional city-level parametric insurance suffers from **basis risk**: a trigger may fire even when a worker's delivery zone is unaffected, or fail when that worker actually loses income. SurakshaShift AI solves this for India's Q-Commerce delivery workers (Zepto, Blinkit, Swiggy Instamart), who typically operate within a **1–3 km radius of a single dark store**.

- During peak periods, Q-Commerce workers complete **3–4 deliveries per hour**, so even a short disruption can sharply reduce income.
- Workers are **zone-locked** — earnings depend on one dark store catchment, so disruption means a *full stop*, not a slowdown.
- Dark stores are often located in **basements or narrow market lanes**, making them more vulnerable to flooding and access restrictions.
- Only **10% of gig workers** in India currently receive any social security benefits (ILO), and this segment remains largely uncovered.

> 📌 **Key Insight:** The true unit of risk is not the city or neighbourhood — it is the worker's specific dark store polygon.

---

## 2. Our Persona — Ravi, who is a Q-Commerce Delivery Partner


| Attribute                   | Detail                                                              |
| --------------------------- | ------------------------------------------------------------------- |
| **Platform**                | Zepto / Blinkit                                                     |
| **City**                    | Bengaluru · Dark store in HSR Layout                                |
| **Working Hours**           | 10 AM – 10 PM (with breaks)                                         |
| **Average Weekly Pay**      | ₹2,800 – ₹4,800 (net ₹70–₹120/hr × ~8 hrs/day × 5 days)             |
| **Most Vulnerable Periods** | Monsoon (June–Sept) · Summer heat waves (Apr–Jun) · Election bandhs |


### Persona Scenarios

**Scenario 1 — The Monsoon Stop**  
Rainfall at Ravi's dark store zone exceeds 7.6 mm/hour on a Tuesday night. Orders stop, Zepto limits available slots, and Ravi loses three hours of peak earnings (₹360–₹540). A weather sensor reading from his zone automatically initiates a claim. Within 15 minutes, ₹350–₹500 reaches his UPI wallet.

**Scenario 2 — The Heat Stress Lock**  
In April, the Heat Index in Ravi's zone exceeds 54°C — NDMA's "Danger" category for outdoor workers. Ravi cannot work safely. SurakshaShift AI's environmental trigger fires, compensating two hours of lost income.

**Scenario 3 — The Zone Closure**  
A local government drive shuts down an illegal market next to the dark store. A police cordon blocks access for four hours. SurakshaShift AI's social disruption trigger automatically initiates a payout.

**Scenario 4 — The Attempted Fraud**  
A partner claims rain caused a disruption, but their GPS log shows continuous movement in a nearby unaffected area. The claim is flagged and sent for human review instead of auto-payment.

---

## 3. Parametric Triggers

All triggers are zone-specific and only fire for workers whose registered dark store zone falls within the disruption area.


| #   | Trigger                   | Threshold & Source                                                              | Payout/Hour |
| --- | ------------------------- | ------------------------------------------------------------------------------- | ----------- |
| 1   | 🌧 **Rainfall Intensity** | >7.6 mm/hour for 30+ min · IMD "Moderate" threshold · OpenWeatherMap `rain.1h`  | ₹70–₹110    |
| 2   | 🌡 **Heat Stress Index**  | Heat Index >54°C · NDMA "Danger" zone for outdoor workers · OWM temp + humidity | ₹60–₹90     |
| 3   | 🌫 **Severe AQI**         | AQI >300 for 2+ consecutive hours · CPCB "Very Poor/Severe" · OpenAQ API        | ₹50–₹80     |
| 4   | 📢 **Social Disruption**  | Curfew / Section 144 / Bandh in delivery pin code · News API + Govt scraper     | ₹100–₹150   |
| 5   | 🏪 **Dark Store Closure** | Zero orders for 90+ min during business hours · Zepto/Blinkit Platform API      | ₹90–₹130    |


> 📐 **Calibration Note:** Payout-per-hour values are benchmarked against documented net hourly earnings of ₹70–₹120. Basic Shield offers partial income replacement; Full Shield targets 90–100% replacement for the disruption window.

---

## 4. Weekly Premium Model — SmartWeek Pricing

SurakshaShift AI uses a **weekly subscription model** aligned with Zepto and Blinkit's payout cycles (Monday–Sunday earnings paid the following Tuesday/Wednesday). Every Sunday night, the ML Premium Engine recalculates the worker's premium for the coming week.

### 4.1 Feature Weights


| Feature                                       | Weight  | Reasoning                                                 |
| --------------------------------------------- | ------- | --------------------------------------------------------- |
| Zone Disruption History Score (last 90 days)  | **30%** | Historical risk for that dark store zone                  |
| 7-Day Forward Weather Forecast                | **25%** | IMD + OpenWeatherMap probabilistic rainfall/heat forecast |
| Worker Income Tier (baseline weekly earnings) | **20%** | Higher earners get higher coverage cap and premium        |
| AQI Trend (zone-level, 7-day rolling)         | **15%** | Worsening trend triggers a small upward adjustment        |
| City-Level Social Risk Score                  | **10%** | Elections, festivals, and curfews in the past calendar    |


### 4.2 Coverage Tiers


| Tier                   | Premium/Week | Triggers Covered                               | Max Weekly Payout |
| ---------------------- | ------------ | ---------------------------------------------- | ----------------- |
| 🟢 **Basic Shield**    | ₹25          | Environmental (rain, heat)                     | ₹600              |
| 🔵 **Standard Shield** | ₹42          | Environmental + AQI                            | ₹1,000            |
| 🟣 **Full Shield**     | ₹65          | Env + AQI + Social/Curfew + Dark Store Closure | ₹1,600            |


> 💡 **Pricing Rationale:** The weekly payout cap (₹600–₹1,600) covers roughly 20–40% of disruption-linked income loss. The Standard Shield premium-to-coverage ratio of 4.2% is viable for a high-frequency product in a monsoon-prone market.

---

## 5. System Architecture *(this repository)*

End-to-end data path for the Phase 2 prototype:

1. **External signals** — OpenWeatherMap, WAQI, NewsData.io / GNews (closure proxy); all optional with **mock fallbacks** when API keys are unset.
2. **API layer** — **FastAPI** (`backend/app/main.py`): workers, auth (OTP), risk / quote-live, policies + triggers, claims, events ingest, Shift Guardian.
3. **Persistence** — **SQLAlchemy** + **SQLite** (default) or any URL in `DATABASE_URL`; Alembic migrations under `backend/alembic/`.
4. **Pricing & ML** — Actuarial/tiered premium + **scikit-learn GBM** residual in `app/ml/premium_model.py`; explanations and feature importances for the quote UI.
5. **Parametric engine** — `app/services/trigger_engine.py`: zone + coverage window match, trigger thresholds, fraud score stub, claim creation; **dedupe** and **single active policy** rules documented above.
6. **Worker UI** — **Vite + React**: onboarding, multi-plan quote, dashboard with live conditions, simulator, animated claim pipeline.

*Roadmap items from the original vision (insurer console, Leaflet zones, Redis job runner, Prophet/LSTM pipelines, Razorpay) are not in this repo — they remain design targets.*

---

## 6. Application Workflow *(implemented app)*

| Step | In the product |
|------|----------------|
| **1. OTP** | Phone + mock OTP verification → session moves to registration. |
| **2. Profile** | City, zone, platform, income, shift, UPI — creates **worker** + **zone** as needed. |
| **3. Quote** | **`/risk/quote-live`** returns live factors, **multi-plan** premiums, GBM explanation; **`model_version`** shown on screen. |
| **4. Activate** | **`/policies/create`** — one active policy; triggers seeded from covered events. |
| **5. Dashboard** | Stats, **Shift Guardian** (zone comparison), **Disruption Simulator** (mock ingest + animated steps), live weather/AQI strip, **My claims** (scoped to `worker_id`). |
| **6. Claims** | Auto-created on matching ingest; fraud review path exists in schema; UPI payout is **represented** in copy, not a live payment rail in this build. |

Optional: **`GET /events/check-live/{city}`** can auto-ingest severe rain/AQI for zones in that city (uses **non-mock** dedupe rules).

---

## 7. AI / ML in this build

| Capability | Status | Where |
|------------|--------|--------|
| **Weekly premium** | **Shipped** — actuarial blend + GBM risk/premium predictors | `premium_model.py`, `risk_service.py`, `pricing_service.py` |
| **Quote explanation** | **Shipped** — narrative + global feature importances | `get_risk_explanation()` |
| **Fraud scoring (claims)** | **Simplified** — weighted score → approve vs manual review | `fraud_service.py`, `trigger_engine.py` |
| **Prophet income curve / Isolation Forest GPS / LSTM forecast** | **Not implemented** — documented as **Phase 3+** research directions | — |

**Evaluator sound bite:** *“About four-fifths of the weekly price is a transparent actuarial curve tied to exposure and city; the GBM adds a bounded residual so live APIs move the quote without a black box.”*

---

## 8. Technology Stack *(as shipped)*


| Layer | Technology | Notes |
| ----- | ---------- | ----- |
| **Worker frontend** | React 18, Vite 5, TypeScript | Custom CSS (Plus Jakarta Sans / DM Sans); responsive dashboard |
| **Backend** | Python 3.11+, FastAPI, Uvicorn | REST JSON API |
| **ORM / DB** | SQLAlchemy 2, SQLite default | PostgreSQL-compatible via `DATABASE_URL` |
| **ML** | scikit-learn (GBM), NumPy | Premium and risk score |
| **HTTP client** | httpx | Live weather / AQI / news |
| **Tests** | pytest | Run: `cd backend && pytest` |

**External APIs (optional keys)** — OpenWeatherMap, WAQI, NewsData.io, GNews (see `.env.example`).


---

## 9. Financial Viability

### 9.1 Market Sizing

- ~7.7 million gig workers in India today (NITI Aayog 2022), growing to **23.5 million by 2029–30**
- **3+ million** combined gig workers for Zepto, Blinkit, Zomato, and Swiggy
- Q-Commerce workers (Blinkit + Zepto + Instamart ≈ 95% market share): conservative estimate of **700,000–1,000,000 workers**
- Year-1 target: **5% adoption across three metro areas** ≈ 35,000–50,000 workers

### 9.2 Unit Economics *(Standard Shield, 50,000 Workers)*


| Metric                                 | Value                  | Basis                                          |
| -------------------------------------- | ---------------------- | ---------------------------------------------- |
| Standard Shield price / worker / week  | ₹42                    | SmartWeek ML pricing model                     |
| Weekly premium income (50,000 workers) | ₹21,00,000             | 50,000 × ₹42                                   |
| Expected claim frequency               | 15–20% of policy-weeks | Standard parametric micro-insurance loss ratio |
| Average payout per claim               | ₹300–₹500              | 3–5 hours at ₹70–₹110/hour                     |
| Weekly claims cost                     | ~₹15,12,000            | At midpoint estimates                          |
| **Net weekly margin (before ops)**     | **~₹5–6 lakhs**        | Revenue minus claims                           |


> 📊 A net weekly margin of ₹5–6 lakhs at 50,000 workers suggests a commercially sound base for a high-frequency disruption product.

---

## 10. References

1. Order frequency and weekly payout cycle — AlphaReach.tech, *Zepto Delivery Partner Guide*, 2026
2. Social security coverage rate — The Week, *"The evolving dynamics of India's gig economy"*, November 2024
3. Net hourly earnings ₹70–₹120 — Whalesbook, *"India's Quick Commerce Meltdown?"*, January 2026
4. IMD Rainfall Classification thresholds — Thakur et al., *Meteorological Applications*, 2020
5. Heat stress threshold — NDMA *Heat Action Plan*; WHO *Guidelines on Heat Stress in the Workplace*
6. Micro-insurance loss ratio 15–20% — ILO Microinsurance Innovation Facility Research Series
7. 20–30% income loss from disruptions — Guidewire DEVTrails 2026 Problem Statement, Page 1
8. CPCB AQI categories — CPCB *National Air Quality Index*, 2014
9. Gig worker growth projections — NITI Aayog 2022; ILO, April 2024
10. 3 million gig workers across major platforms — Wikipedia, *Zepto (company)*, accessed March 2026
11. Q-Commerce market concentration — Mukund Mohan Blog, May 2025; Demand Sage *Quick Commerce Statistics 2026*

---

# 🚨 Adversarial Defense & Anti-Spoofing Strategy

### SurakshaShift AI — Market Crash Response

**Team SharkBYTE · Guidewire DEVTrails 2026 · Filed: March 20, 2026**

---

> *"500 delivery partners. Fake GPS. Real payouts. Simple GPS verification is dead."*

---

## The Core Asymmetry

GPS coordinates are easy to fake. What is much harder to fake is a **consistent behavioural signature across multiple independent signals**.

A genuine stranded worker creates several matching signals at once: local weather conditions, nearby network markers, motion patterns, and zero platform orders. A fraudster may spoof location, but matching every other layer at the same time is far harder.

---

## The Six Signal Layers


| #   | Layer                         | What It Checks                                                                                                                                                                                                                                                    | Why It Can't Be Faked From Software                                                                           |
| --- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 1   | **Hardware Sensor Fusion**    | Barometric pressure vs. weather API (±5 hPa tolerance); altitude plausibility for Bengaluru (~900m ASL); accelerometer pattern vs. worker's own 90-day baseline; Android `isFromMockProvider()` flag                                                              | Hardware sensors read directly from the chip — no userspace spoofing app intercepts them                      |
| 2   | **Network Triangulation**     | Cell tower IDs + Wi-Fi BSSIDs triangulated independently of GPS; mismatch >1.5 km is a fraud flag                                                                                                                                                                 | Defeating this requires physical radio transmitters, not software                                             |
| 3   | **Pre-Trigger Trajectory**    | Worker must show 2 hours of in-zone GPS history before the trigger fired — the dark store ↔ delivery address loop at scooter speed                                                                                                                                | A ring member who was never in the zone has no history to produce                                             |
| 4   | **Ring Detection Graph**      | Spatial clustering (30 claims within 10m radius); temporal burst (2–4 min filing window); referral graph density (>40% of claimants within 2 hops); tier uniformity (>80% Basic Shield in one burst); new account concentration (>50% accounts under 21 days old) | Coordination itself is the evidence — the ring cannot avoid producing these patterns                          |
| 5   | **Platform Cross-Validation** | Queries Zepto/Blinkit API for order completions during the claimed window — any completion is a binary disqualifier for that hour                                                                                                                                 | A ring member isn't actually delivering; the platform log is the proof                                        |
| 6   | **Honeypot Pings**            | Silent sensor bundle pings on a randomised 8–40 min schedule — no UI indication, hardware-sourced readings only                                                                                                                                                   | Unpredictable timing makes evasion impossible; hardware data can't be intercepted by a foreground spoofer app |


---

## Genuine Worker vs. Faker — The Decisive Difference

**A genuine worker may fail one layer** because of real-world conditions — poor GPS, an older phone, or temporary movement to shelter. That should result in a **Soft Hold**, not a rejection.

**A fraud ring member is more likely to fail multiple layers together**: mismatched signals, no pre-trigger history, suspicious filing patterns, and referral-network clustering.

That is why SurakshaShift AI uses a continuous **0–100 SHIELD Score** instead of a binary fraud flag.

---

## SHIELD Score & Response Tiers


| Sub-Score Layer           | Weight | Key Signal                                               |
| ------------------------- | ------ | -------------------------------------------------------- |
| Hardware Sensor Fusion    | 25%    | Barometer, altitude, accelerometer, mock flag            |
| Network Triangulation     | 20%    | Cell tower + Wi-Fi position mismatch                     |
| Pre-Trigger Trajectory    | 20%    | Zone presence in 2 hrs before disruption                 |
| Ring Detection Graph      | 20%    | Clustering, referral graph, tier uniformity, account age |
| Platform Cross-Validation | 10%    | Zero order completions during claimed window             |
| Honeypot Ping Consistency | 5%     | Sensor bundle plausibility at random silent pings        |


> **Why Ring Detection carries 20%:** A coordinated ring is categorically different from an individual fraudster. Ring membership must be a near-certain disqualifier even when an individual member's sensor checks look clean.


| Score  | Action                                                    |
| ------ | --------------------------------------------------------- |
| 0–30   | ✅ **Auto-approve** — payout in ≤10 min                    |
| 31–55  | ⏳ **Soft hold** — 2-hr recheck; likely a sensor edge case |
| 56–75  | 👤 **Human review** — up to 24 hrs; worker notified       |
| 76–89  | ❌ **Denied** — reason given; appeal via photo evidence    |
| 90–100 | 🔒 **Account frozen** — investigation opened              |


---

## Liquidity Circuit Breaker

If any zone receives **>2.5× its 90-day average claim volume within 4 hours**, SurakshaShift AI auto-halts new claims from that zone and alerts the insurer's risk team. Claims already queued continue processing normally.

This turns a potential liquidity wipeout into a bounded and recoverable loss event.

---

## Possible Limitations


| Attack Vector                                                             | Why It Still Fails                                                                                                |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Rooted device + Xposed GPS injection (bypasses mock flag, spoofs sensors) | Cell tower triangulation requires physical radio hardware to defeat; ring graph flags the coordination regardless |
| Legitimate account lent to a ring member                                  | No pre-trigger trajectory + zero platform orders = caught on two independent layers                               |
| Slow-burn ring with accounts aged 3–6 months                              | Defeats new-account check only; spatial and temporal clustering fire regardless of account age                    |


**We are not claiming this is unbreakable. We are claiming it is uneconomical to break at scale.** Defeating all six layers consistently would cost more effort than the payout from a ₹600 Basic Shield claim.

---

*Team SharkBYTE · Guidewire DEVTrails 2026* 