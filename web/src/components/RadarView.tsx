import { Link } from "react-router-dom";
import type { Milestone, MilestoneRadar } from "../lib/types";
import { Icon } from "./Icon";
import { StagePill } from "./StagePill";

// Forward milestone radar: upcoming expected readouts bucketed by quarter.

function byQuarter(milestones: Milestone[]): [string, Milestone[]][] {
  const groups = new Map<string, Milestone[]>();
  for (const m of milestones) {
    const key = m.quarter || "Undated";
    (groups.get(key) ?? groups.set(key, []).get(key)!).push(m);
  }
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

export function RadarView({ radar }: { radar: MilestoneRadar }) {
  if (radar.milestones.length === 0) {
    return (
      <div className="rounded-md hairline bg-card-light p-8 text-center text-[14px] text-ink-muted-light">
        No expected readouts for <span className="font-medium">{radar.scope}</span> in the next{" "}
        {radar.horizon_months} months.
      </div>
    );
  }
  const quarters = byQuarter(radar.milestones);

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {quarters.map(([quarter, items]) => (
        <div key={quarter} className="rounded-md hairline bg-card-light p-3">
          <div className="mb-3 border-b border-hairline-light pb-1.5 font-mono text-[12px] text-ink-muted-light">
            {quarter}
          </div>
          <div className="space-y-2">
            {items.map((m) => (
              <Link
                key={m.nct_id}
                to={`/asset/${encodeURIComponent(m.asset_name)}`}
                className="block rounded-sm hairline bg-surface-container-low p-2.5 hover:bg-surface-container"
              >
                <div className="flex items-center justify-between">
                  <StagePill phase={m.phase} />
                  <span className="font-mono text-[11px] text-ink-muted-light">
                    {m.expected_date?.slice(0, 7)}
                  </span>
                </div>
                <div className="mt-1.5 text-[13px] font-medium text-ink-light">{m.asset_name}</div>
                <div className="text-[11px] text-ink-muted-light">{m.indication}</div>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function RadarFootnote() {
  return (
    <p className="mt-4 flex items-center gap-2 text-[12px] text-ink-muted-light">
      <Icon name="info" size={16} />
      Expected readouts are trials whose primary completion is still ahead and not yet reported,
      read from ClinicalTrials.gov.
    </p>
  );
}
