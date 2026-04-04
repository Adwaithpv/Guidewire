"""
GBM risk + premium models trained on labels anchored to the actuarial engine.

Training no longer uses a self-referential synthetic premium formula: premium targets are
actuarial_weekly_premium(...) + noise, so the trees learn non-linear residuals around the
defensible baseline. City factors come from pricing_service.CITY_RISK_WEIGHTS (IMD-style).
"""
from __future__ import annotations

import logging

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

from app.services.pricing_service import (
    CITY_RISK_WEIGHTS,
    actuarial_weekly_premium,
    city_risk_factor,
    composite_exposure,
)

log = logging.getLogger(__name__)

_SHIFT_MULTIPLIER: dict[str, float] = {
    "morning": 0.6,
    "afternoon": 0.8,
    "evening": 0.9,
    "night": 1.0,
    "full_day": 0.85,
    "split": 0.75,
}

_rng = np.random.RandomState(42)


def _generate_training_data(n: int = 5000) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cities = list(CITY_RISK_WEIGHTS.keys())
    shifts = list(_SHIFT_MULTIPLIER.keys())

    rows = []
    risk_labels = []
    premium_labels = []

    for _ in range(n):
        city = cities[_rng.randint(len(cities))]
        shift = shifts[_rng.randint(len(shifts))]
        city_factor = city_risk_factor(city)
        shift_factor = _SHIFT_MULTIPLIER[shift]

        rain = np.clip(_rng.beta(2, 5) * (0.5 + 0.5 * city_factor), 0, 1)
        flood = np.clip(_rng.beta(1.5, 6) * city_factor, 0, 1)
        aqi = np.clip(
            _rng.beta(2, 4) * (0.85 if city in ("Delhi", "Kolkata", "Lucknow") else 0.45),
            0,
            1,
        )
        closure = np.clip(_rng.beta(1, 8) * 0.6, 0, 1)
        shift_exp = np.clip(shift_factor + _rng.normal(0, 0.08), 0, 1)
        income = float(_rng.uniform(1500, 8000))

        comp = composite_exposure(rain, flood, aqi, closure, shift_exp, city)
        noise_r = _rng.normal(0, 0.025)
        risk = float(np.clip(comp + noise_r, 0.02, 0.98))

        act = actuarial_weekly_premium(rain, flood, aqi, closure, shift_exp, income, city)
        noise_p = _rng.normal(0, 3.5)
        premium = float(np.clip(act + noise_p, 19.0, 99.0))

        rows.append([rain, flood, aqi, closure, shift_exp, income, city_factor])
        risk_labels.append(risk)
        premium_labels.append(premium)

    return np.array(rows), np.array(risk_labels), np.array(premium_labels)


class PremiumModel:
    def __init__(self) -> None:
        self._risk_model: GradientBoostingRegressor | None = None
        self._premium_model: GradientBoostingRegressor | None = None
        self._scaler: StandardScaler | None = None
        self._trained = False

    def train(self) -> None:
        if self._trained:
            return
        log.info("Training GBM models (labels anchored to actuarial engine)...")
        X, y_risk, y_premium = _generate_training_data(5000)

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        self._risk_model = GradientBoostingRegressor(
            n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42
        )
        self._risk_model.fit(X_scaled, y_risk)

        self._premium_model = GradientBoostingRegressor(
            n_estimators=80, max_depth=3, learning_rate=0.1, random_state=42
        )
        self._premium_model.fit(X_scaled, y_premium)

        self._trained = True
        log.info(
            "GBM trained. Risk feature importances: %s",
            dict(
                zip(
                    ["rain", "flood", "aqi", "closure", "shift", "income", "city"],
                    [round(float(x), 3) for x in self._risk_model.feature_importances_],
                )
            ),
        )

    def predict_risk_score(
        self,
        rain_risk: float,
        flood_risk: float,
        aqi_risk: float,
        closure_risk: float,
        shift_exposure: float,
        avg_weekly_income: float,
        city: str,
    ) -> float:
        self.train()
        city_factor = city_risk_factor(city)
        features = np.array(
            [[rain_risk, flood_risk, aqi_risk, closure_risk, shift_exposure, avg_weekly_income, city_factor]]
        )
        scaled = self._scaler.transform(features)  # type: ignore[union-attr]
        pred = self._risk_model.predict(scaled)[0]  # type: ignore[union-attr]
        return round(float(np.clip(pred, 0.02, 0.98)), 4)

    def predict_premium(
        self,
        rain_risk: float,
        flood_risk: float,
        aqi_risk: float,
        closure_risk: float,
        shift_exposure: float,
        avg_weekly_income: float,
        city: str,
    ) -> float:
        self.train()
        city_factor = city_risk_factor(city)
        features = np.array(
            [[rain_risk, flood_risk, aqi_risk, closure_risk, shift_exposure, avg_weekly_income, city_factor]]
        )
        scaled = self._scaler.transform(features)  # type: ignore[union-attr]
        pred = self._premium_model.predict(scaled)[0]  # type: ignore[union-attr]
        return round(float(np.clip(pred, 19.0, 99.0)), 2)

    def get_feature_importances(self) -> dict[str, float]:
        self.train()
        names = [
            "rain_risk",
            "flood_risk",
            "aqi_risk",
            "closure_risk",
            "shift_exposure",
            "avg_weekly_income",
            "city_risk",
        ]
        return {
            n: round(float(v), 3)
            for n, v in zip(names, self._risk_model.feature_importances_)  # type: ignore[union-attr]
        }


model = PremiumModel()
