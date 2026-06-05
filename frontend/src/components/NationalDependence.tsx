// National-dependence chip (Phase B) — a port's share of its COUNTRY's maritime
// trade, an IMF systemic-importance signal. A sole-gateway port (Mombasa ≈ 99.8% of
// Kenya's imports) means a disruption there is nationally systemic, not just a local
// dip. Straight from the snapshot (0-100%), no estimate. Ports only.
interface NationalDependenceProps {
  shareImport?: number;
  shareExport?: number;
  country?: string | null;
}

export default function NationalDependence({
  shareImport,
  shareExport,
  country,
}: NationalDependenceProps) {
  const hi = Math.max(shareImport || 0, shareExport || 0);
  if (hi < 10) return null; // below this it isn't a meaningful dependency story
  const sole = hi >= 80;
  return (
    <div className={`fr-natdep ${sole ? 'is-sole' : ''}`}>
      <div className="fr-natdep-head">
        National dependence <span>· {country || 'country'} · IMF systemic-importance</span>
      </div>
      <div className="fr-natdep-row">
        {shareImport != null && (
          <div className="fr-natdep-stat">
            <b>{Math.round(shareImport)}%</b>
            <span>of imports</span>
          </div>
        )}
        {shareExport != null && (
          <div className="fr-natdep-stat">
            <b>{Math.round(shareExport)}%</b>
            <span>of exports</span>
          </div>
        )}
      </div>
      {sole && (
        <div className="fr-natdep-note">
          Single-port dependency — a disruption here is systemic for {country || 'the country'}.
        </div>
      )}
    </div>
  );
}
