"""
ML-powered risk scoring and premium calculation engine for SurakshaShift AI.

Uses GradientBoostingRegressor trained on synthetic disruption data
modeled after real Indian city patterns. Auto-trains on first use.
"""
from __future__ import annotations

import logging
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

log = logging.getLogger(__name__)

# ── Synthetic data generation ────────────────────────────────────────

_CITY_RISK: dict[str, float] = {
    "Mumbai": 0.82, "Chennai": 0.75, "Kolkata": 0.70, "Bengaluru": 0.55,
    "Delhi": 0.65, "Hyderabad": 0.50, "Pune": 0.48, "Ahmedabad": 0.45,
    "Jaipur": 0.40, "Lucknow": 0.42,
}

_SHIFT_MULTIPLIER: dict[str, float] = {
    "morning": 0.6, "afternoon": 0.8, "evening": 0.9,
    "night": 1.0, "full_day": 0.85, "split": 0.75,
}

_rng = np.random.RandomState(42)


def _generate_training_data(n: int = 5000) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic training data for risk & premium models."""
    cities = list(_CITY_RISK.keys())
    shifts = list(_SHIFT_MULTIPLIER.keys())

    rows = []
    risk_labels = []
    premium_labels = []

    for _ in range(n):
        city = cities[_rng.randint(len(cities))]
        shift = shifts[_rng.randint(len(shifts))]
        city_factor = _CITY_RISK[city]
        shift_factor = _SHIFT_MULTIPLIER[shift]

        rain = np.clip(_rng.beta(2, 5) * city_factor * 1.3, 0, 1)
        flood = np.clip(_rng.beta(1.5, 6) * city_factor, 0, 1)
        aqi = np.clip(_rng.beta(2, 4) * (0.8 if city in ("Delhi", "Kolkata", "Lucknow") else 0.4), 0, 1)
        closure = np.clip(_rng.beta(1, 8) * 0.6, 0, 1)
        shift_exp = np.clip(shift_factor + _rng.normal(0, 0.1), 0, 1)
        income = _rng.uniform(1500, 8000)

        # Risk score formula (ground truth with noise)
        base_risk = (
            0.28 * rain + 0.22 * flood + 0.18 * aqi
            + 0.12 * closure + 0.10 * shift_exp + 0.10 * city_factor
        )
        noise = _rng.normal(0, 0.03)
        risk = float(np.clip(base_risk + noise, 0.02, 0.98))

        # Premium formula (ground truth): base + risk-driven + income-adjusted
        base_premium = 22.0
        risk_premium = risk * 55.0
        income_adj = (income / 8000) * 12.0
        premium_noise = _rng.normal(0, 1.5)
        premium = float(np.clip(base_premium + risk_premium + income_adj + premium_noise, 19, 99))

        rows.append([rain, flood, aqi, closure, shift_exp, income, city_factor])
        risk_labels.append(risk)
        premium_labels.append(premium)

    return np.array(rows), np.array(risk_labels), np.array(premium_labels)


# ── Model class ──────────────────────────────────────────────────────

class PremiumModel:
    """Singleton ML model for risk scoring and premium pricing."""

    def __init__(self) -> None:
        self._risk_model: GradientBoostingRegressor | None = None
        self._premium_model: GradientBoostingRegressor | None = None
        self._scaler: StandardScaler | None = None
        self._trained = False

    def train(self) -> None:
        if self._trained:
            return
        log.info("Training SurakshaShift ML models on synthetic data...")
        X, y_risk, y_premium = _generate_training_data(5000)

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        self._risk_model = GradientBoostingRegressor(
            n_estimators=120, max_depth=4, learning_rate=0.1, random_state=42
        )
        self._risk_model.fit(X_scaled, y_risk)

        self._premium_model = GradientBoostingRegressor(
            n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42
        )
        self._premium_model.fit(X_scaled, y_premium)

        self._trained = True
        log.info("ML models trained successfully. Feature importances (risk): %s",
                 dict(zip(
                     ["rain", "flood", "aqi", "closure", "shift", "income", "city"],
                     [round(float(x), 3) for x in self._risk_model.feature_importances_]
                 )))

    def predict_risk_score(
        self,
        rain_risk: float, flood_risk: float, aqi_risk: float,
        closure_risk: float, shift_exposure: float,
        avg_weekly_income: float, city: str,
    ) -> float:
        self.train()
        city_factor = _CITY_RISK.get(city, 0.45)
        features = np.array([[rain_risk, flood_risk, aqi_risk, closure_risk,
                              shift_exposure, avg_weekly_income, city_factor]])
        scaled = self._scaler.transform(features)  # type: ignore[union-attr]
        pred = self._risk_model.predict(scaled)[0]  # type: ignore[union-attr]
        return round(float(np.clip(pred, 0.02, 0.98)), 4)

    def predict_premium(
        self,
        rain_risk: float, flood_risk: float, aqi_risk: float,
        closure_risk: float, shift_exposure: float,
        avg_weekly_income: float, city: str,
    ) -> float:
        self.train()
        city_factor = _CITY_RISK.get(city, 0.45)
        features = np.array([[rain_risk, flood_risk, aqi_risk, closure_risk,
                              shift_exposure, avg_weekly_income, city_factor]])
        scaled = self._scaler.transform(features)  # type: ignore[union-attr]
        pred = self._premium_model.predict(scaled)[0]  # type: ignore[union-attr]
        return round(float(np.clip(pred, 19.0, 99.0)), 2)

    def get_feature_importances(self) -> dict[str, float]:
        self.train()
        names = ["rain_risk", "flood_risk", "aqi_risk", "closure_risk",
                 "shift_exposure", "avg_weekly_income", "city_risk"]
        return {n: round(float(v), 3) for n, v in
                zip(names, self._risk_model.feature_importances_)}  # type: ignore[union-attr]


# Singleton instance — trained lazily on first call
model = PremiumModel()
