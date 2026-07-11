import { useEffect, useState } from "react";
import { getMilestoneRadar } from "../lib/api";
import type { MilestoneRadar } from "../lib/types";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/Loading";
import { RadarView, RadarFootnote } from "../components/RadarView";

// Forward milestone radar — upcoming expected readouts for a condition.
export function MilestoneRadarPage() {
  const [input, setInput] = useState("Obesity");
  const [condition, setCondition] = useState("Obesity");
  const [horizon, setHorizon] = useState(18);
  const [radar, setRadar] = useState<MilestoneRadar | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getMilestoneRadar(condition, horizon)
      .then((r) => {
        setRadar(r);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [condition, horizon]);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-6">
        <h1 className="font-sans text-display-lg text-ink-light">Readout radar</h1>
        <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
          What's expected to read out next, across the competitive field.
        </p>
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
            placeholder="Condition, e.g. Obesity"
          />
        </div>
        <button
          type="submit"
          className="rounded-sm bg-ink-light px-4 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
        >
          Show radar
        </button>
        <label className="ml-1 flex items-center gap-2 text-[13px] text-ink-muted-light">
          Horizon
          <select
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="rounded-sm hairline bg-card-light px-2 py-1.5 text-ink-light"
          >
            <option value={12}>12 months</option>
            <option value={18}>18 months</option>
            <option value={24}>24 months</option>
            <option value={36}>36 months</option>
          </select>
        </label>
      </form>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Could not load the radar. Is the backend running on :8000?
        </p>
      )}
      {loading && !radar && <LoadingState label="Scanning for upcoming readouts…" />}
      {radar && <RadarView radar={radar} />}
      <RadarFootnote />
    </div>
  );
}
