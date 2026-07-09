import type { Phase } from "../lib/types";
import { PHASE_LABEL } from "../lib/types";

// A restrained stage gradient built from the existing design tokens: neutral for
// early phases, accent through mid/late clinical, amber at filing, green at
// approval, red for withdrawn. Color always pairs with the phase label.
const STAGE_STYLE: Record<Phase, string> = {
  preclinical: "bg-surface-container-high text-ink-muted-light",
  phase_1: "bg-surface-container-high text-ink-muted-light",
  phase_1_2: "bg-accent-container text-on-accent-container",
  phase_2: "bg-accent-container text-on-accent-container",
  phase_2_3: "bg-accent-container text-accent",
  phase_3: "bg-accent text-white",
  phase_4: "bg-accent text-white",
  filed: "bg-risk-some-container text-risk-some",
  approved: "bg-risk-low-container text-risk-low",
  withdrawn: "bg-risk-high-container text-risk-high",
  unknown: "bg-surface-container text-outline",
};

export function StagePill({ phase }: { phase: Phase }) {
  return (
    <span
      className={`inline-flex items-center rounded-sm px-2 py-0.5 text-[11px] font-semibold ${STAGE_STYLE[phase]}`}
    >
      {PHASE_LABEL[phase]}
    </span>
  );
}
