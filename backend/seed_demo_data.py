"""
Seed script: populates the SQLite DB with 20 realistic gig-worker profiles,
12 weeks of policy history, disruption events, claims, fraud checks, and
payouts calibrated to demonstrate healthy unit economics.

Run:  python seed_demo_data.py          (from backend/)
      python -m seed_demo_data          (from backend/)

Safe to re-run: it deletes all prior demo rows first.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models import Base
from app.models.entities import (
    Claim,
    DataConsent,
    DisruptionEvent,
    FraudCheck,
    Payout,
    Policy,
    PolicyTrigger,
    RiskProfile,
    TriggerMatch,
    User,
    WorkerProfile,
    Zone,
)

random.seed(42)

NOW = datetime.now(timezone.utc).replace(tzinfo=None)
WEEK = timedelta(weeks=1)

# ── Zone definitions ─────────────────────────────────────────────────────
CITY_ZONES: dict[str, list[tuple[str, float]]] = {
    "Bengaluru": [("HSR Layout", 0.32), ("Koramangala", 0.30), ("Whitefield", 0.28)],
    "Mumbai": [("Andheri", 0.38), ("Bandra", 0.35), ("Powai", 0.30)],
    "Chennai": [("Anna Nagar", 0.34), ("T Nagar", 0.33)],
    "Delhi": [("Connaught Place", 0.40), ("Dwarka", 0.36)],
    "Hyderabad": [("Madhapur", 0.29), ("Gachibowli", 0.27)],
}

# ── Worker templates ─────────────────────────────────────────────────────
WORKERS = [
    # (name, city, zone_name, platform, persona, income, shift, gender, plan)
    ("Ravi Kumar",       "Bengaluru", "HSR Layout",       "Swiggy",   "food",    4200, "day",      "male",              "standard"),
    ("Arun Reddy",       "Bengaluru", "Koramangala",      "Zepto",    "grocery", 3800, "full_day", "male",              "basic"),
    ("Priya Sharma",     "Bengaluru", "Whitefield",       "Blinkit",  "grocery", 3500, "day",      "female",            "her-standard"),
    ("Vikram Gowda",     "Bengaluru", "HSR Layout",       "Dunzo",    "courier", 5200, "split",    "male",              "full"),
    ("Deepa Nair",       "Bengaluru", "Koramangala",      "Swiggy",   "food",    4000, "night",    "female",            "her-standard"),
    ("Suresh Babu",      "Bengaluru", "Whitefield",       "Zomato",   "food",    3600, "day",      "male",              "standard"),
    ("Amit Patil",       "Mumbai",    "Andheri",          "Swiggy",   "food",    5500, "full_day", "male",              "standard"),
    ("Rohit Deshmukh",   "Mumbai",    "Bandra",           "Zepto",    "grocery", 6200, "day",      "male",              "full"),
    ("Sneha Kulkarni",   "Mumbai",    "Powai",            "Blinkit",  "grocery", 4800, "day",      "female",            "standard"),
    ("Manoj Joshi",      "Mumbai",    "Andheri",          "Zomato",   "food",    4500, "night",    "male",              "basic"),
    ("Kiran Sawant",     "Mumbai",    "Bandra",           "Dunzo",    "courier", 7500, "split",    "male",              "full"),
    ("Rajesh Iyer",      "Chennai",   "Anna Nagar",       "Swiggy",   "food",    3900, "day",      "male",              "standard"),
    ("Lakshmi Devi",     "Chennai",   "T Nagar",          "Zepto",    "grocery", 3200, "day",      "female",            "standard"),
    ("Ganesh Subbu",     "Chennai",   "Anna Nagar",       "Blinkit",  "grocery", 4100, "full_day", "male",              "basic"),
    ("Meena Rajan",      "Chennai",   "T Nagar",          "Swiggy",   "food",    2800, "night",    "male",              "basic"),
    ("Sanjay Verma",     "Delhi",     "Connaught Place",  "Zomato",   "food",    5800, "day",      "male",              "full"),
    ("Rahul Singh",      "Delhi",     "Dwarka",           "Swiggy",   "food",    4600, "full_day", "male",              "standard"),
    ("Pooja Gupta",      "Delhi",     "Connaught Place",  "Blinkit",  "grocery", 4000, "day",      "prefer_not_to_say", "standard"),
    ("Naveen Rao",       "Hyderabad", "Madhapur",         "Swiggy",   "food",    4300, "day",      "male",              "standard"),
    ("Venkat Reddy",     "Hyderabad", "Gachibowli",       "Zepto",    "grocery", 3700, "split",    "male",              "basic"),
]

PLAN_PREMIUM_RANGE: dict[str, tuple[float, float]] = {
    "basic":        (18, 35),
    "standard":     (30, 55),
    "full":         (45, 85),
    "her-basic":    (14, 40),
    "her-standard": (25, 50),
    "her-full":     (30, 75),
}

PLAN_COVERAGE_PCT: dict[str, float] = {
    "basic": 0.20, "standard": 0.35, "full": 0.50,
    "her-basic": 0.25, "her-standard": 0.40, "her-full": 0.55,
}

DEFAULT_TRIGGERS = ["heavy_rain", "flood", "aqi_severe", "curfew", "platform_outage"]
HER_EXTRA_TRIGGERS = ["safety_incident", "night_shift_disruption", "health_leave"]

# ── Disruption event templates ───────────────────────────────────────────
EVENT_TEMPLATES: list[dict] = [
    {"type": "heavy_rain", "cities": ["Bengaluru", "Mumbai", "Chennai"], "severity_weights": [0.5, 0.35, 0.15]},
    {"type": "heavy_rain", "cities": ["Bengaluru", "Mumbai", "Chennai"], "severity_weights": [0.5, 0.35, 0.15]},
    {"type": "heavy_rain", "cities": ["Mumbai", "Chennai"],             "severity_weights": [0.4, 0.4, 0.2]},
    {"type": "heavy_rain", "cities": ["Bengaluru"],                     "severity_weights": [0.6, 0.3, 0.1]},
    {"type": "heavy_rain", "cities": ["Chennai", "Bengaluru"],          "severity_weights": [0.5, 0.35, 0.15]},
    {"type": "heavy_rain", "cities": ["Mumbai"],                        "severity_weights": [0.3, 0.4, 0.3]},
    {"type": "heavy_rain", "cities": ["Bengaluru", "Chennai"],          "severity_weights": [0.6, 0.3, 0.1]},
    {"type": "heavy_rain", "cities": ["Mumbai", "Bengaluru"],           "severity_weights": [0.5, 0.35, 0.15]},
    {"type": "heavy_rain", "cities": ["Chennai"],                       "severity_weights": [0.5, 0.35, 0.15]},
    {"type": "heavy_rain", "cities": ["Bengaluru", "Mumbai"],           "severity_weights": [0.55, 0.3, 0.15]},
    {"type": "heavy_rain", "cities": ["Mumbai"],                        "severity_weights": [0.5, 0.3, 0.2]},
    {"type": "heavy_rain", "cities": ["Bengaluru"],                     "severity_weights": [0.6, 0.3, 0.1]},
    {"type": "heavy_rain", "cities": ["Chennai", "Mumbai"],             "severity_weights": [0.5, 0.35, 0.15]},
    {"type": "heavy_rain", "cities": ["Bengaluru"],                     "severity_weights": [0.5, 0.35, 0.15]},
    {"type": "heavy_rain", "cities": ["Mumbai", "Chennai"],             "severity_weights": [0.4, 0.4, 0.2]},
    {"type": "aqi_severe", "cities": ["Delhi"],                         "severity_weights": [0.3, 0.5, 0.2]},
    {"type": "aqi_severe", "cities": ["Delhi"],                         "severity_weights": [0.4, 0.4, 0.2]},
    {"type": "aqi_severe", "cities": ["Delhi"],                         "severity_weights": [0.3, 0.5, 0.2]},
    {"type": "aqi_severe", "cities": ["Delhi"],                         "severity_weights": [0.5, 0.35, 0.15]},
    {"type": "aqi_severe", "cities": ["Delhi"],                         "severity_weights": [0.4, 0.4, 0.2]},
    {"type": "aqi_severe", "cities": ["Delhi", "Mumbai"],               "severity_weights": [0.5, 0.35, 0.15]},
    {"type": "aqi_severe", "cities": ["Delhi"],                         "severity_weights": [0.3, 0.5, 0.2]},
    {"type": "aqi_severe", "cities": ["Delhi"],                         "severity_weights": [0.5, 0.3, 0.2]},
    {"type": "flood",      "cities": ["Mumbai", "Chennai"],             "severity_weights": [0.3, 0.4, 0.3]},
    {"type": "flood",      "cities": ["Mumbai"],                        "severity_weights": [0.3, 0.4, 0.3]},
    {"type": "flood",      "cities": ["Chennai"],                       "severity_weights": [0.4, 0.4, 0.2]},
    {"type": "flood",      "cities": ["Mumbai", "Chennai"],             "severity_weights": [0.3, 0.4, 0.3]},
    {"type": "curfew",     "cities": ["Delhi", "Bengaluru"],            "severity_weights": [0.5, 0.4, 0.1]},
    {"type": "curfew",     "cities": ["Mumbai"],                        "severity_weights": [0.6, 0.3, 0.1]},
    {"type": "platform_outage", "cities": ["Bengaluru", "Mumbai", "Chennai", "Delhi", "Hyderabad"], "severity_weights": [0.7, 0.25, 0.05]},
    {"type": "platform_outage", "cities": ["Bengaluru", "Mumbai"],      "severity_weights": [0.6, 0.3, 0.1]},
    {"type": "platform_outage", "cities": ["Chennai", "Hyderabad"],     "severity_weights": [0.7, 0.25, 0.05]},
]


def _severity(weights: list[float]) -> str:
    return random.choices(["moderate", "high", "severe"], weights=weights, k=1)[0]


def _rand_premium(plan: str) -> float:
    lo, hi = PLAN_PREMIUM_RANGE.get(plan, (25, 55))
    return round(random.uniform(lo, hi), 2)


def _upi(name: str) -> str:
    slug = name.lower().split()[0]
    bank = random.choice(["okaxis", "ybl", "paytm", "ibl"])
    return f"{slug}{random.randint(10, 99)}@{bank}"


def _ref() -> str:
    return f"UPI{uuid.uuid4().hex[:12].upper()}"


def run_seed():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # Wipe existing data in correct FK order
        for tbl in [
            "payouts", "fraud_checks", "trigger_matches", "claims",
            "policy_triggers", "policies", "disruption_events",
            "risk_profiles", "shift_guardian_alerts", "data_consents",
            "worker_profiles", "users", "zones",
        ]:
            try:
                db.execute(text(f"DELETE FROM {tbl}"))
            except Exception:
                pass
        db.commit()

        # ── 1. Zones ─────────────────────────────────────────────
        zone_map: dict[str, Zone] = {}
        for city, zones in CITY_ZONES.items():
            for zname, risk in zones:
                z = Zone(city=city, zone_name=zname, default_risk_level=risk)
                db.add(z)
                db.flush()
                zone_map[zname] = z

        # ── 2. Workers ───────────────────────────────────────────
        worker_rows: list[dict] = []
        for name, city, zname, platform, persona, income, shift, gender, plan in WORKERS:
            user = User(name=name, phone=f"9{random.randint(100000000, 999999999)}", city=city,
                        created_at=NOW - timedelta(weeks=14) + timedelta(days=random.randint(0, 7)))
            db.add(user)
            db.flush()

            wp = WorkerProfile(
                user_id=user.id, persona_type=persona, platform_name=platform,
                avg_weekly_income=income, primary_zone_id=zone_map[zname].id,
                shift_type=shift, gps_enabled=True, payout_upi=_upi(name),
                gender=gender, risk_score=zone_map[zname].default_risk_level,
            )
            db.add(wp)
            db.flush()

            db.add(DataConsent(
                worker_id=wp.id, gps_consent=True, upi_consent=True,
                platform_data_consent=True, consent_version="v1",
                captured_at=user.created_at, updated_at=user.created_at,
            ))

            rp = RiskProfile(
                worker_id=wp.id,
                rain_risk=round(random.uniform(0.15, 0.55), 3),
                flood_risk=round(random.uniform(0.05, 0.35), 3),
                aqi_risk=round(random.uniform(0.05, 0.40), 3),
                closure_risk=round(random.uniform(0.02, 0.15), 3),
                shift_exposure=round(random.uniform(0.1, 0.4), 3),
                final_risk_score=wp.risk_score,
                quoted_premium=_rand_premium(plan),
            )
            db.add(rp)

            worker_rows.append({
                "wp": wp, "user": user, "zone": zone_map[zname],
                "plan": plan, "income": income, "city": city,
            })

        db.flush()

        # ── 3. Policies (12 weeks per worker) ────────────────────
        policy_map: dict[int, list[Policy]] = {}
        for w in worker_rows:
            wp = w["wp"]
            plan = w["plan"]
            policies: list[Policy] = []
            for week_offset in range(12, 0, -1):
                start = NOW - timedelta(weeks=week_offset)
                end = start + WEEK
                premium = _rand_premium(plan)
                cov_pct = PLAN_COVERAGE_PCT.get(plan, 0.35)
                max_payout = round(w["income"] * cov_pct, 2)
                status = "active" if week_offset == 1 else "expired"

                pol = Policy(
                    worker_id=wp.id, plan_name=plan,
                    premium_weekly=premium, max_weekly_payout=max_payout,
                    coverage_start=start, coverage_end=end,
                    status=status, auto_renew=True,
                )
                db.add(pol)
                db.flush()

                triggers = DEFAULT_TRIGGERS[:]
                if plan.startswith("her-"):
                    triggers += HER_EXTRA_TRIGGERS
                for trig in triggers:
                    db.add(PolicyTrigger(
                        policy_id=pol.id, trigger_type=trig,
                        threshold_value=round(random.uniform(0.3, 0.7), 2),
                        payout_formula_type="hour_based",
                    ))
                policies.append(pol)
            policy_map[wp.id] = policies

        db.flush()

        # ── 4. Disruption events ─────────────────────────────────
        events: list[DisruptionEvent] = []
        for i, tmpl in enumerate(EVENT_TEMPLATES):
            city = random.choice(tmpl["cities"])
            city_zones = [z for zn, z in zone_map.items() if z.city == city]
            zone = random.choice(city_zones)
            week_offset = random.randint(1, 12)
            day_offset = random.randint(0, 6)
            hour = random.randint(6, 22)
            started = NOW - timedelta(weeks=week_offset) + timedelta(days=day_offset, hours=hour)
            duration_hours = random.uniform(2, 8)
            ended = started + timedelta(hours=duration_hours)

            ev = DisruptionEvent(
                event_type=tmpl["type"], zone_id=zone.id,
                started_at=started, ended_at=ended,
                severity=_severity(tmpl["severity_weights"]),
                source_name=random.choice(["openweathermap", "waqi", "newsdata", "platform_api"]),
                is_verified=True,
            )
            db.add(ev)
            db.flush()
            events.append(ev)

        # ── 5. Claims, fraud checks, payouts ─────────────────────
        total_premium_sum = 0.0
        for w in worker_rows:
            for pol in policy_map[w["wp"].id]:
                total_premium_sum += float(pol.premium_weekly)

        target_payout_sum = total_premium_sum * random.uniform(0.55, 0.62)
        payout_budget = target_payout_sum
        claim_count = 0

        for ev in events:
            ev_zone = db.get(Zone, ev.zone_id)
            affected = [
                w for w in worker_rows
                if w["zone"].id == ev.zone_id or (w["zone"].city == ev_zone.city and random.random() < 0.25)
            ]
            if not affected:
                continue

            random.shuffle(affected)
            pick = affected[:random.randint(1, min(3, len(affected)))]

            for w in pick:
                if payout_budget <= 0:
                    break

                wp = w["wp"]
                active_policies = [p for p in policy_map[wp.id] if p.coverage_start <= ev.started_at <= p.coverage_end]
                if not active_policies:
                    continue

                pol = active_policies[0]
                claim_count += 1

                roll = random.random()
                if roll < 0.75:
                    status = random.choice(["approved", "paid"])
                elif roll < 0.90:
                    status = "validation_pending"
                elif roll < 0.95:
                    status = "fraud_check"
                else:
                    status = "rejected"

                base_payout = round(random.uniform(80, 320), 2)
                payout_amt = min(base_payout, float(pol.max_weekly_payout))

                claim = Claim(
                    worker_id=wp.id, policy_id=pol.id, event_id=ev.id,
                    claim_type=ev.event_type, status=status,
                    estimated_loss=round(payout_amt * random.uniform(1.1, 1.4), 2),
                    approved_payout=payout_amt if status in ("approved", "paid") else 0,
                    created_at=ev.started_at + timedelta(minutes=random.randint(5, 60)),
                    auto_created=random.random() < 0.92,
                )
                db.add(claim)
                db.flush()

                db.add(TriggerMatch(
                    event_id=ev.id, worker_id=wp.id, policy_id=pol.id,
                    matched_at=claim.created_at, expected_payout=payout_amt,
                    status="matched",
                ))

                fraud_roll = random.random()
                if fraud_roll < 0.85:
                    review = "auto_approve"
                    fraud_score = round(random.uniform(0.03, 0.22), 4)
                elif fraud_roll < 0.95:
                    review = "soft_review"
                    fraud_score = round(random.uniform(0.22, 0.42), 4)
                else:
                    review = "manual_review"
                    fraud_score = round(random.uniform(0.42, 0.68), 4)

                db.add(FraudCheck(
                    claim_id=claim.id,
                    gps_score=round(random.uniform(0.01, 0.3), 4),
                    activity_score=round(random.uniform(0.01, 0.25), 4),
                    duplicate_score=round(random.uniform(0.0, 0.15), 4),
                    anomaly_score=round(random.uniform(0.0, 0.2), 4),
                    source_score=round(random.uniform(0.0, 0.1), 4),
                    final_fraud_score=fraud_score,
                    review_status=review,
                ))

                if status in ("approved", "paid"):
                    payout_budget -= payout_amt
                    db.add(Payout(
                        claim_id=claim.id, worker_id=wp.id,
                        amount=payout_amt, method="upi", status="success",
                        gateway_ref=_ref(),
                        initiated_at=claim.created_at + timedelta(minutes=random.randint(1, 5)),
                        completed_at=claim.created_at + timedelta(minutes=random.randint(6, 15)),
                    ))

        db.commit()

        # ── Summary ──────────────────────────────────────────────
        from sqlalchemy import func
        prem = float(db.scalar(func.coalesce(func.sum(Policy.premium_weekly), 0)) or 0)
        pays = float(db.scalar(func.coalesce(func.sum(Payout.amount), 0)) or 0)
        n_claims = db.scalar(func.count(Claim.id)) or 0
        n_workers = db.scalar(func.count(WorkerProfile.id)) or 0
        lr = round(pays / prem, 4) if prem else 0

        print("=" * 60)
        print("  SEED COMPLETE")
        print("=" * 60)
        print(f"  Workers:          {n_workers}")
        print(f"  Zones:            {len(zone_map)}")
        print(f"  Policies:         {n_workers * 12}")
        print(f"  Events:           {len(events)}")
        print(f"  Claims:           {n_claims}")
        print(f"  Total premiums:   Rs {prem:,.2f}")
        print(f"  Total payouts:    Rs {pays:,.2f}")
        print(f"  Loss ratio:       {lr:.1%}")
        print(f"  BCR:              {round(prem/pays, 3) if pays else 'N/A'}")
        print("=" * 60)


if __name__ == "__main__":
    run_seed()
