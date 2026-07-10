import { memo, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getLandscape } from "../lib/api";
import type { Landscape, LandscapeCell, Phase } from "../lib/types";
import { Icon } from "../components/Icon";
import { StagePill } from "../components/StagePill";
import { EvidenceBadgeView } from "../components/EvidenceBadgeView";

const MIN_YEAR = 2008;
const MAX_YEAR = new Date().getFullYear();

// Development phases in ascending order of advancement. This is the board's
// column axis: fixed, ordered, and dense — every asset sits in exactly one of
// these, so (unlike the old asset × indication matrix) there is no blank space.
const PHASE_ORDER: Phase[] = [
  "preclinical",
  "phase_1",
  "phase_1_2",
  "phase_2",
  "phase_2_3",
  "phase_3",
  "phase_4",
  "filed",
  "approved",
  "withdrawn",
  "unknown",
];

// How advanced each phase is, used to rank cards when capping so the late-stage
// competitors that matter are never dropped. Distinct from PHASE_ORDER (column
// layout): here withdrawn/unknown rank lowest so a flood of phase-untagged
// trials can't crowd out the real Phase 2/3/approved programs.
const ADVANCEMENT_RANK: Record<Phase, number> = {
  approved: 9,
  filed: 8,
  phase_4: 7,
  phase_3: 6,
  phase_2_3: 5,
  phase_2: 4,
  phase_1_2: 3,
  phase_1: 2,
  preclinical: 1,
  withdrawn: 0,
  unknown: -1,
};

// A broad condition (e.g. "Obesity") can return ~1000 assets. Cap the number of
// cards so the board stays responsive, keeping the most advanced first.
const MAX_CARDS = 120;

function AssetCard({ cell, condition }: { cell: LandscapeCell; condition: string }) {
  return (
    <div className="rounded-md hairline bg-card-light p-2.5" data-testid="asset-card">
      <div className="flex items-start justify-between gap-1">
        <Link
          to={`/asset/${encodeURIComponent(cell.asset_name)}`}
          className="text-[13px] font-medium leading-tight text-ink-light hover:text-accent hover:underline"
          title={`Full dossier — every trial for ${cell.asset_name} across indications`}
        >
          {cell.asset_name}
        </Link>
        {cell.conflict && (
          <span title={cell.conflict_note ?? "Sources disagree on the current stage"}>
            <Icon name="warning" size={14} className="text-risk-some" label="source conflict" />
          </span>
        )}
      </div>
      <p className="mt-1 truncate text-[11px] text-ink-muted-light" title={cell.indication}>
        {cell.indication}
      </p>
      {cell.sponsor && (
        <p className="truncate text-[10px] text-ink-muted-light" title={cell.sponsor}>
          {cell.sponsor}
        </p>
      )}
      {cell.evidence && <EvidenceBadgeView badge={cell.evidence} />}
      <Link
        to={`/landscape/asset/${encodeURIComponent(cell.asset_name)}?condition=${encodeURIComponent(condition)}`}
        className="mt-1 inline-flex items-center gap-0.5 text-[10px] text-accent hover:underline"
      >
        Timeline <Icon name="chevron_right" size={12} />
      </Link>
    </div>
  );
}

// The board is memoized on landscape/condition/indication so that typing in the
// search box (which changes only the parent's `input` state) does not re-render
// the whole board on every keystroke.
const PipelineBoard = memo(function PipelineBoard({
  landscape,
  condition,
  indication,
}: {
  landscape: Landscape;
  condition: string;
  indication: string | null;
}) {
  const { columns, truncated, total } = useMemo(() => {
    const cells = (landscape.cells ?? []).filter(
      (c) => indication === null || c.indication === indication
    );
    const total = cells.length;
    // Keep the most-advanced cells first when capping, so the cap never hides
    // the late-stage competitors that matter most.
    const shown = [...cells]
      .sort((a, b) => ADVANCEMENT_RANK[b.current_phase] - ADVANCEMENT_RANK[a.current_phase])
      .slice(0, MAX_CARDS);

    const byPhase = new Map<Phase, LandscapeCell[]>();
    for (const c of shown) {
      const list = byPhase.get(c.current_phase) ?? [];
      list.push(c);
      byPhase.set(c.current_phase, list);
    }
    // Only render columns that actually hold an asset, in phase order.
    const columns = PHASE_ORDER.filter((p) => byPhase.has(p)).map((phase) => ({
      phase,
      cells: byPhase.get(phase)!.sort((a, b) => a.asset_name.localeCompare(b.asset_name)),
    }));
    return { columns, truncated: total > MAX_CARDS, total };
  }, [landscape, indication]);

  if (columns.length === 0) {
    return (
      <div className="rounded-md hairline bg-card-light p-8 text-center text-[14px] text-ink-muted-light">
        No assets in {indication} for this condition{" "}
        {landscape.as_of ? `as of ${landscape.as_of}.` : "."}
      </div>
    );
  }

  return (
    <div className="rounded-md hairline bg-surface-container-low p-3">
      {truncated && (
        <p className="mb-2 px-1 text-[12px] text-ink-muted-light">
          Showing the {MAX_CARDS} most-advanced of {total} programs — narrow the condition or
          filter by indication to focus.
        </p>
      )}
      <div className="flex gap-3 overflow-x-auto pb-1" data-testid="pipeline-board">
        {columns.map(({ phase, cells }) => (
          <div
            key={phase}
            data-testid={`phase-col-${phase}`}
            className="flex w-56 shrink-0 flex-col"
          >
            <div className="mb-2 flex items-center justify-between px-1">
              <StagePill phase={phase} />
              <span className="text-[11px] font-medium text-ink-muted-light">{cells.length}</span>
            </div>
            <div className="flex flex-col gap-2">
              {cells.map((cell) => (
                <AssetCard
                  key={`${cell.asset_name}|${cell.indication}`}
                  cell={cell}
                  condition={condition}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});

// A condition can span hundreds of indications, so a chip row would bury the
// board. When there are only a few, chips are quickest; past that, fall back to
// a compact dropdown that keeps the board as the hero.
const CHIP_LIMIT = 8;

function IndicationFilter({
  indications,
  active,
  onSelect,
}: {
  indications: string[];
  active: string | null;
  onSelect: (ind: string | null) => void;
}) {
  if (indications.length <= 1) return null;

  if (indications.length > CHIP_LIMIT) {
    return (
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-[12px] text-ink-muted-light">Indication:</span>
        <select
          aria-label="Indication"
          value={active ?? ""}
          onChange={(e) => onSelect(e.target.value || null)}
          className="rounded-sm hairline bg-card-light px-3 py-1.5 text-[13px] text-ink-light outline-none"
        >
          <option value="">All indications ({indications.length})</option>
          {indications.map((ind) => (
            <option key={ind} value={ind}>
              {ind}
            </option>
          ))}
        </select>
        {active && (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="text-[12px] text-accent hover:underline"
          >
            Clear
          </button>
        )}
      </div>
    );
  }

  const chip = (label: string, selected: boolean, value: string | null) => (
    <button
      key={label}
      type="button"
      onClick={() => onSelect(value)}
      className={`rounded-full px-3 py-1 text-[12px] ${
        selected
          ? "bg-accent-container text-on-accent-container"
          : "hairline text-ink-muted-light hover:bg-card-light"
      }`}
    >
      {label}
    </button>
  );
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <span className="text-[12px] text-ink-muted-light">Indication:</span>
      {chip("All", active === null, null)}
      {indications.map((ind) => chip(ind, active === ind, ind))}
    </div>
  );
}

export function CompetitorLandscape() {
  const [input, setInput] = useState("Obesity");
  const [condition, setCondition] = useState("Obesity");
  const [year, setYear] = useState(MAX_YEAR);
  const [indication, setIndication] = useState<string | null>(null);
  const [landscape, setLandscape] = useState<Landscape | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const asOf = year >= MAX_YEAR ? null : `${year}-12-31`;

  useEffect(() => {
    setLoading(true);
    // A fresh condition may not carry the previously selected indication.
    setIndication(null);
    getLandscape(condition, asOf)
      .then((ls) => {
        setLandscape(ls);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [condition, year]);

  // Indications that actually have a cell, in the landscape's declared order.
  const indications = useMemo(() => {
    if (!landscape) return [];
    const used = new Set((landscape.cells ?? []).map((c) => c.indication));
    return landscape.indications.filter((ind) => used.has(ind));
  }, [landscape]);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-sans text-display-lg text-ink-light">Competitive Landscape</h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
            Every asset by its stage of development, joined to the living pooled evidence for each.
          </p>
        </div>
      </div>

      <form
        className="mb-5 flex flex-wrap items-center gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setCondition(input.trim() || condition);
        }}
      >
        <div className="flex items-center gap-2 rounded-sm hairline bg-card-light px-3 py-2">
          <Icon name="search" size={16} className="text-ink-muted-light" />
          <input
            aria-label="condition"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="w-64 bg-transparent text-[14px] text-ink-light outline-none"
            placeholder="Condition, e.g. Type 2 Diabetes"
          />
        </div>
        <button
          type="submit"
          className="rounded-sm bg-ink-light px-4 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
        >
          Map
        </button>
      </form>

      {/* As-of time slider — reconstruct the pipeline at a past point in time. */}
      <div className="mb-6 flex items-center gap-4 rounded-md hairline bg-card-light px-4 py-3">
        <Icon name="history" size={18} className="text-ink-muted-light" />
        <span className="text-label-caps uppercase text-ink-muted-light">As of</span>
        <input
          type="range"
          aria-label="as of year"
          min={MIN_YEAR}
          max={MAX_YEAR}
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="flex-1 accent-accent"
        />
        <span data-testid="as-of-label" className="w-24 text-right font-mono text-[13px] text-ink-light">
          {year >= MAX_YEAR ? "Now" : `Dec ${year}`}
        </span>
      </div>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Could not load the landscape. Is the backend running on :8000?
        </p>
      )}

      {loading && !landscape && (
        <p className="font-mono text-[13px] text-ink-muted-light">Mapping the landscape…</p>
      )}

      {landscape && landscape.assets.length === 0 && !loading && (
        <div className="rounded-md hairline bg-card-light p-8 text-center text-[14px] text-ink-muted-light">
          No development activity found for <span className="font-medium">{condition}</span>
          {asOf ? ` as of ${asOf}.` : "."}
        </div>
      )}

      {landscape && landscape.assets.length > 0 && (
        <>
          <IndicationFilter
            indications={indications}
            active={indication}
            onSelect={setIndication}
          />
          <PipelineBoard landscape={landscape} condition={condition} indication={indication} />
        </>
      )}

      <p className="mt-4 flex items-center gap-2 text-[12px] text-ink-muted-light">
        <Icon name="info" size={16} />
        Stages come from ClinicalTrials.gov with full provenance; a linked card carries its
        review's living pooled estimate, GRADE, and homogeneity-gate state.
      </p>
    </div>
  );
}
