# GigShield

### Hyperlocal Income Protection for Delivery Partners in Q-Commerce

*AI-Powered Parametric Insurance for India's Q-Commerce Delivery Workers*

> **Team SharkBYTE · Phase 1 Submission · Guidewire DEVTrails 2026**

---

## 1. The Problem We Are Solving

Traditional city-level parametric insurance suffers from **basis risk**: a trigger may fire even when a worker's delivery zone is unaffected, or fail when that worker actually loses income. GigShield solves this for India's Q-Commerce delivery workers (Zepto, Blinkit, Swiggy Instamart), who typically operate within a **1–3 km radius of a single dark store**.

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
In April, the Heat Index in Ravi's zone exceeds 54°C — NDMA's "Danger" category for outdoor workers. Ravi cannot work safely. GigShield's environmental trigger fires, compensating two hours of lost income.

**Scenario 3 — The Zone Closure**  
A local government drive shuts down an illegal market next to the dark store. A police cordon blocks access for four hours. GigShield's social disruption trigger automatically initiates a payout.

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

GigShield uses a **weekly subscription model** aligned with Zepto and Blinkit's payout cycles (Monday–Sunday earnings paid the following Tuesday/Wednesday). Every Sunday night, the ML Premium Engine recalculates the worker's premium for the coming week.

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

## 5. System Architecture

GigShield System Architecture  
*Figure 1 — GigShield Full System Architecture*

The platform is organised into five layers:

1. **External Data Sources** — OpenWeatherMap, OpenAQ, Heat Index calculation, News API/Govt scraper, Zepto/Blinkit mock API
2. **Real-Time Trigger Engine** — Polls every 15 minutes, zone-specific thresholds, 5 automated triggers
3. **Core Processing Layer** — ML Engine (XGBoost/Prophet/Isolation Forest/LSTM), SHIELD Fraud Score, Claims Processor, Payout Engine
4. **Infrastructure Layer** — Node.js + FastAPI backend, PostgreSQL + Redis, JWT + OTP auth, Vercel + Railway + Supabase
5. **Frontend Layer** — Worker PWA, Insurer Dashboard, Zone Maps (Leaflet.js)

---

## 6. Application Workflow

### Step 1 — Onboarding

- Worker signs up via mobile PWA
- Aadhaar-lite KYC (DigiLocker mock)
- Links delivery platform worker ID (Zepto/Blinkit mock API)
- AI Risk Profiler: zone assignment, income baseline, historical disruption score
- Weekly premium quoted in real time

### Step 2 — Policy Subscription

- Worker selects coverage tier for the coming week
- Pays weekly premium via UPI (₹25–₹65 depending on tier and zone risk)
- Policy record stored with zone polygon, coverage window, and payout caps

### Step 3 — Real-Time Trigger Monitoring

Background engine polls 5 data sources every 15 minutes:

- Weather API (per dark store lat/long)
- AQI feed (zone-level via OpenAQ)
- Heat Index calculation (temp + humidity)
- Government notification scraper / News API (curfews, bandhs)
- Dark store operational status (mock platform API)

### Step 4 — Automated Claim Initiation

- On threshold breach: Fraud Pre-Check (GPS cross-validation, deduplication, anomaly score)
- If clean: auto-approve and initiate payout within 10 minutes
- If flagged: routed to insurer dashboard for manual review

### Step 5 — Payout

- UPI transfer (Razorpay test mode) or wallet credit
- Worker receives a push notification with disruption type, duration, and payout amount

### Step 6 — Analytics Dashboards

- **Worker view:** weekly pay protected, coverage status, disruption history
- **Insurer view:** loss ratio, zone risk heatmap, ML-predicted disruption probability

---

## 7. AI / ML Integration Plan

### 7.1 Dynamic Premium Calculation Engine *(XGBoost)*

Training data is synthesised from IMD rainfall history by pin code, OpenAQ AQI readings, and documented earnings distributions. Output: a personalised weekly premium (₹25–₹65) with a clear worker-facing explanation.

### 7.2 Income Baseline Fingerprinting *(Facebook Prophet)*

Instead of assuming flat earnings, GigShield builds a worker-specific income curve from the first two weeks of order data. That allows payouts to better reflect **when** the disruption occurred. This improves fairness, not just model accuracy.

### 7.3 Fraud Detection — Trajectory Anomaly Engine *(Isolation Forest)*

Features include average speed during the disruption window, distance from the dark store centroid, movement entropy, and deviation from the worker's 90-day GPS baseline. A worker appearing 8 km away during a zone trigger is an automatic escalation case.

### 7.4 Predictive Disruption Dashboard *(LSTM)*

Historical weather, AQI trends, and city event calendars are used to forecast zone-level disruption probability for the next week. This helps insurers estimate liability and plan reserves.

---

## 8. Technology Stack


| Layer              | Technology                                       | Rationale                                                             |
| ------------------ | ------------------------------------------------ | --------------------------------------------------------------------- |
| **Frontend**       | React (PWA) + Tailwind CSS                       | Offline-capable, mobile-first, push notifications, no App Store delay |
| **Backend API**    | Node.js (Express) + FastAPI (Python)             | Node for business logic; FastAPI for high-performance ML inference    |
| **Database**       | PostgreSQL + Redis                               | Relational for policies/claims; Redis for real-time trigger state     |
| **ML / AI**        | XGBoost, Prophet, scikit-learn, Isolation Forest | Mature libraries for all four ML use-cases in one Python ecosystem    |
| **Weather API**    | OpenWeatherMap (free tier)                       | Real lat/long queries, `rain.1h` field, 60 calls/min free             |
| **AQI API**        | OpenAQ (open source)                             | Zone-level AQI data for Indian cities                                 |
| **Payments**       | Razorpay Test Mode                               | UPI simulation for full payout flow in Phase 1–2                      |
| **Maps / Zone**    | Leaflet.js + GeoJSON                             | Zone polygon visualisation at zero cost                               |
| **Infrastructure** | Vercel + Railway + Supabase                      | All free tiers; zero cloud cost in Phase 1–2                          |
| **Auth**           | JWT + OTP (mock Twilio)                          | Phone-number-based auth fits the delivery partner persona             |


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

### GigShield — Market Crash Response

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

That is why GigShield uses a continuous **0–100 SHIELD Score** instead of a binary fraud flag.

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

If any zone receives **>2.5× its 90-day average claim volume within 4 hours**, GigShield auto-halts new claims from that zone and alerts the insurer's risk team. Claims already queued continue processing normally.

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