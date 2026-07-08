import { ForestPlot } from "./ForestPlot";
import { ProvenancePopover } from "./ProvenancePopover";
import type { ReviewResult } from "../lib/types";

function i2Band(i2: number): string {
  if (i2 <= 40) return "might not be important";
  if (i2 <= 60) return "moderate";
  if (i2 <= 90) return "substantial";
  return "considerable";
}

// The pooled-answer report. Presentational: given a ReviewResult, renders the
// headline estimate, clinical conclusion, heterogeneity, forest plot, and the
// evidence ledger with per-row provenance.
export function ReportView({ result }: { result: ReviewResult }) {
  if (!result.pool) {
    return (
      <p className="font-mono text-[13px] text-ink-muted-light">
        Too few valid trials to pool — abstaining. {result.summary}
      </p>
    );
  }
  const { pool, summary, extractions, grade, sensitivity } = result;
  const significant = pool.ci_high < 1 || pool.ci_low > 1;

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
          Pooled answer
        </p>
        {grade && (
          <span className="inline-flex items-center gap-2 rounded-full border border-hairline-light px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-ink-light">
            <span className="flex gap-0.5">
              {Array.from({ length: 4 }).map((_, i) => (
                <span
                  key={i}
                  className={`h-2 w-2 rounded-full ${
                    i < { high: 4, moderate: 3, low: 2, very_low: 1 }[grade.certainty]
                      ? "bg-secondary"
                      : "bg-surface-container-highest"
                  }`}
                />
              ))}
            </span>
            {grade.certainty.replace("_", " ")} certainty
          </span>
        )}
      </div>

      <div className="mt-3 flex items-baseline gap-4">
        <span className="font-mono text-[40px] font-medium tracking-tight text-ink-light">
          {pool.measure} {pool.estimate.toFixed(2)}
        </span>
        <span className="font-mono text-[16px] text-ink-muted-light">
          95% CI {pool.ci_low.toFixed(2)}–{pool.ci_high.toFixed(2)}
        </span>
        <span className="ml-auto rounded-full border border-hairline-light px-3 py-1 font-mono text-[11px] text-ink-muted-light">
          {pool.ci_method.toUpperCase()} · {pool.method} · {pool.engine}
        </span>
      </div>

      <p className="mt-6 border-l-2 border-accent pl-4 font-serif text-[18px] leading-7 text-ink-light">
        {summary}
      </p>

      <div className="mt-8 grid grid-cols-4 gap-px overflow-hidden rounded-md border border-hairline-light bg-hairline-light">
        {[
          ["Studies", String(pool.k)],
          ["I²", `${pool.i2.toFixed(0)}% · ${i2Band(pool.i2)}`],
          ["τ²", pool.tau2.toFixed(3)],
          [
            "Prediction",
            pool.prediction_low != null
              ? `${pool.prediction_low.toFixed(2)}–${pool.prediction_high!.toFixed(2)}`
              : "n/a",
          ],
        ].map(([k, v]) => (
          <div key={k} className="bg-card-light p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
              {k}
            </p>
            <p className="mt-1 font-mono text-[14px] text-ink-light">{v}</p>
          </div>
        ))}
      </div>

      <section className="mt-8 rounded-md border border-hairline-light bg-card-light p-6">
        <h2 className="mb-4 text-[13px] font-medium text-ink-light">Forest plot</h2>
        <ForestPlot pool={pool} />
      </section>

      {pool.notes.length > 0 && (
        <ul className="mt-4 flex flex-col gap-1">
          {pool.notes.map((n, i) => (
            <li key={i} className="font-mono text-[12px] text-risk-some">
              ⚠ {n}
            </li>
          ))}
        </ul>
      )}

      {sensitivity.length > 0 && (
        <section className="mt-8 rounded-md border border-hairline-light bg-card-light p-6">
          <h2 className="mb-1 text-[13px] font-medium text-ink-light">
            Leave-one-out sensitivity
          </h2>
          <p className="mb-4 text-[12px] text-ink-muted-light">
            Re-pooling with each trial removed — does the answer rest on any single
            trial?
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] border-collapse text-left">
              <thead>
                <tr className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
                  <th className="pb-2 pr-4">Omitted trial</th>
                  <th className="pb-2 pr-4 text-right">{pool.measure} (95% CI)</th>
                  <th className="pb-2 pr-4 text-right">I²</th>
                  <th className="pb-2 text-right">Effect</th>
                </tr>
              </thead>
              <tbody>
                {sensitivity.map((r) => {
                  // Highlight rows whose omission flips the significance verdict.
                  const rowSig = r.ci_high < 1 || r.ci_low > 1;
                  const flips = rowSig !== significant;
                  return (
                    <tr
                      key={r.omitted_study_id}
                      className="border-t border-hairline-light"
                    >
                      <td className="py-2 pr-4 text-[13px] text-ink-light">
                        − {r.omitted_label}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono text-[13px] text-ink-light">
                        {r.estimate.toFixed(2)} [{r.ci_low.toFixed(2)}, {r.ci_high.toFixed(2)}]
                      </td>
                      <td className="py-2 pr-4 text-right font-mono text-[12px] text-ink-muted-light">
                        {r.i2.toFixed(0)}%
                      </td>
                      <td className="py-2 text-right">
                        {flips ? (
                          <span className="rounded-full border border-[#fde68a] bg-[#fef3c7] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[#b45309]">
                            Conclusion flips
                          </span>
                        ) : (
                          <span className="text-[11px] text-ink-muted-light">stable</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="mt-10">
        <h2 className="mb-3 text-[13px] font-medium text-ink-light">
          Evidence ledger — every number traced to its source
        </h2>
        <div className="overflow-hidden rounded-md border border-hairline-light">
          {extractions.map((e) => (
            <div
              key={e.study_id}
              className="flex items-start gap-4 border-b border-hairline-light bg-card-light p-4 last:border-0"
            >
              <span className="w-28 shrink-0 font-mono text-[12px] text-ink-muted-light">
                {e.study_id}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] text-ink-light">{e.label}</p>
                <p className="mt-1 font-mono text-[12px] text-ink-muted-light">
                  {e.provenance[0]?.snippet}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="font-mono text-[13px] text-ink-light">
                  {e.flagged ? "flagged" : `HR ${e.hr}`}
                </span>
                {!e.flagged && <ProvenancePopover provenance={e.provenance} />}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
