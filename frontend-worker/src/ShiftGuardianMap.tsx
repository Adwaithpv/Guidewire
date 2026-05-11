import { useEffect } from "react";
import { MapContainer, TileLayer, Circle, CircleMarker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export type ShiftZone = {
  zone_name: string;
  city: string;
  risk_level: string;
  disruption_probability: number;
  income_protection_score: number;
  estimated_safe_hours: number;
  composite_risk: number;
  lat: number;
  lon: number;
};

type Props = {
  currentZone: ShiftZone;
  recommendedZone: ShiftZone;
  alternatives: ShiftZone[];
};

const RISK_COLORS: Record<string, string> = {
  low: "#22c55e",
  moderate: "#f59e0b",
  high: "#ef4444",
  critical: "#b91c1c",
};

function colorForRisk(level: string): string {
  return RISK_COLORS[(level || "").toLowerCase()] ?? "#94a3b8";
}

function FitBounds({ zones }: { zones: ShiftZone[] }) {
  const map = useMap();
  const key = zones.map((z) => z.zone_name).join("|");
  useEffect(() => {
    if (!zones.length) return;
    const bounds = L.latLngBounds(zones.map((z) => [z.lat, z.lon] as [number, number]));
    // Defensive: containers that mount inside flex/grid sometimes report 0 size on first paint.
    map.invalidateSize();
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return null;
}

export default function ShiftGuardianMap({ currentZone, recommendedZone, alternatives }: Props) {
  const seen = new Set<string>();
  const allZones: ShiftZone[] = [currentZone, recommendedZone, ...alternatives].filter((z) => {
    if (!z || typeof z.lat !== "number" || typeof z.lon !== "number") return false;
    if (seen.has(z.zone_name)) return false;
    seen.add(z.zone_name);
    return true;
  });

  if (!allZones.length) return null;

  const center: [number, number] = [currentZone.lat, currentZone.lon];

  return (
    <div className="shift-guardian-map-wrap">
      <MapContainer
        center={center}
        zoom={12}
        scrollWheelZoom={false}
        className="shift-guardian-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds zones={allZones} />
        {allZones.map((z) => {
          const color = colorForRisk(z.risk_level);
          const isRecommended = z.zone_name === recommendedZone.zone_name;
          const isCurrent = z.zone_name === currentZone.zone_name;
          return (
            <Circle
              key={z.zone_name}
              center={[z.lat, z.lon]}
              radius={900}
              pathOptions={{
                color,
                fillColor: color,
                fillOpacity: isRecommended ? 0.45 : 0.22,
                weight: isRecommended ? 4 : 2,
                dashArray: isRecommended ? undefined : "4 6",
              }}
            >
              <Popup>
                <div style={{ fontSize: "0.85rem", lineHeight: 1.55, minWidth: 180 }}>
                  <div style={{ fontWeight: 700, marginBottom: 6, color: "#0F172A" }}>
                    {isRecommended ? "✅ " : isCurrent ? "📍 " : ""}
                    {z.zone_name}
                    {isCurrent && !isRecommended && (
                      <span style={{ marginLeft: 6, fontSize: "0.7rem", color: "#64748b" }}>(your zone)</span>
                    )}
                  </div>
                  <div>
                    Risk: <strong style={{ color, textTransform: "capitalize" }}>{z.risk_level}</strong>
                  </div>
                  <div>
                    Disruption: <strong>{z.disruption_probability}%</strong>
                  </div>
                  <div>
                    Safety: <strong>{z.income_protection_score}/100</strong>
                  </div>
                  <div>
                    Safe hours this shift: <strong>{z.estimated_safe_hours}</strong>
                  </div>
                </div>
              </Popup>
            </Circle>
          );
        })}
        <CircleMarker
          center={[currentZone.lat, currentZone.lon]}
          radius={6}
          pathOptions={{
            color: "#0F172A",
            fillColor: "#ffffff",
            fillOpacity: 1,
            weight: 3,
          }}
        >
          <Popup>You are here · {currentZone.zone_name}</Popup>
        </CircleMarker>
      </MapContainer>
      <div className="shift-guardian-map-legend">
        <span>
          <span className="legend-dot" style={{ background: RISK_COLORS.low }} /> Low risk
        </span>
        <span>
          <span className="legend-dot" style={{ background: RISK_COLORS.moderate }} /> Moderate
        </span>
        <span>
          <span className="legend-dot" style={{ background: RISK_COLORS.high }} /> High / critical
        </span>
        <span>
          <span className="legend-dot legend-dot-recommended" /> Recommended (solid)
        </span>
      </div>
    </div>
  );
}
