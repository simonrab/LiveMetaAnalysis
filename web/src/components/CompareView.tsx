import type { AssetComparison, AssetEvidenceContext } from "../lib/types";
import { EvidenceBadgeView } from "./EvidenceBadgeView";
import { Icon } from "./Icon";

// Side-by-side profile. Operational facts compare in the table; efficacy does NOT
// — each asset's pooled evidence is shown in its own context, and a comparability
// banner makes explicit that two estimates from separate meta-analyses are not
// directly comparable. No shared axis, no "winner".

function EvidenceCard({ ctx }: { ctx: AssetEvidenceContext }) {
  return (
    <div className="rounded-md hairline bg-surface-container-low p-3">
      <div className="text-[13px] font-medium text-ink-light">{ctx.asset_name}</div>
      <div className="text-[11px] text-ink-muted-light">
        {ctx.population || ctx.indication}
        {ctx.comparator ? ` · vs ${ctx.comparator}` : " · comparator not established"}
      </div>
      <div className="mt-1 text-[12px] text-ink-light">{ctx.plain_summary}</div>
      {ctx.badge && <EvidenceBadgeView badge={ctx.badge} />}
    </div>
  );
}

export function CompareView({ comparison }: { comparison: AssetComparison }) {
  const { assets, rows, evidence, comparability } = comparison;

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-md hairline bg-card-light">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="hairline-b text-label-caps uppercase text-ink-muted-light">
              <th className="px-4 py-2.5 text-left font-semibold" />
              {assets.map((a) => (
                <th key={a} className="px-4 py-2.5 text-left font-semibold text-ink-light">
                  {a}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="hairline-b">
                <td className="px-4 py-2.5 text-ink-muted-light">{row.label}</td>
                {row.values.map((v, i) => (
                  <td key={i} className="px-4 py-2.5 font-mono text-ink-light">
                    {v}
                    {row.more[i] && (
                      <span className="ml-1 text-[11px] font-sans text-ink-muted-light">(more)</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-md hairline bg-card-light p-4">
        <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-ink-light">
          <Icon name="analytics" size={16} className="text-ink-muted-light" />
          Pooled evidence
        </div>

        {!comparability.directly_comparable && (
          <div className="mb-3 rounded-sm border border-risk-some bg-risk-some-container/40 p-3 text-[12px] text-risk-some">
            <div className="flex items-center gap-1.5 font-semibold">
              <Icon name="warning" size={14} /> Indirect — not directly comparable
            </div>
            <p className="mt-1 text-ink-muted-light">
              These estimates come from separate meta-analyses, so they are shown in their own
              context and not ranked. No cross-trial “winner.”
            </p>
            {comparability.reasons.length > 0 && (
              <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-ink-muted-light">
                {comparability.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          {evidence.map((ctx) => (
            <EvidenceCard key={ctx.asset_name} ctx={ctx} />
          ))}
        </div>
      </div>
    </div>
  );
}
