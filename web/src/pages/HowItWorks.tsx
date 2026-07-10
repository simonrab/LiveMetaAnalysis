import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";

// How Strata works — the trust story made visible. Every visual on this page
// restates the same rule from a different angle: Claude reads, deterministic
// code computes, a human confirms, and nothing enters the pool without a
// source and a passing validation check. Static content only: no backend
// calls, safe to open mid-demo.

// ── Division of labour ─────────────────────────────────────────────────────

type Role = "claude" | "code" | "human";

const ROLE = {
  claude: {
    label: "Claude",
    icon: "psychology",
    chip: "border-accent-border bg-accent-container text-on-accent-container",
  },
  code: {
    label: "Code",
    icon: "function",
    chip: "border-outline-variant bg-surface-container-low text-ink-light",
  },
  human: {
    label: "You",
    icon: "person",
    chip: "border-outline-variant bg-card-light text-ink-muted-light",
  },
} as const;

function RoleChip({ role }: { role: Role }) {
  const c = ROLE[role];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${c.chip}`}
    >
      <Icon name={c.icon} size={12} />
      {c.label}
    </span>
  );
}

const ACTORS = [
  {
    role: "claude" as Role,
    title: "Claude",
    body: "Reads and structures the evidence — trial records, arm-level effect data, bias signals. Strong at reading. Never trusted with arithmetic.",
  },
  {
    role: "code" as Role,
    title: "Deterministic code",
    body: "Runs every calculation: the validation checks and the pooling itself, in a validated statistics library following Cochrane Handbook Ch. 10. Reproducible to the digit.",
  },
  {
    role: "human" as Role,
    title: "You",
    body: "Confirms the load-bearing judgments — uncertain extractions and risk-of-bias calls — before they count. The audit trail records every decision.",
  },
];

// ── Pipeline ───────────────────────────────────────────────────────────────

const STAGES: { title: string; desc: string; roles: Role[] }[] = [
  {
    title: "Ask",
    desc: "One clinical question in PICO form, one outcome.",
    roles: ["claude"],
  },
  {
    title: "Retrieve",
    desc: "Structured trial results from ClinicalTrials.gov, publications from Europe PMC.",
    roles: ["code"],
  },
  {
    title: "Extract",
    desc: "Events and totals per arm, read into a fixed schema. Every value carries the exact sentence it came from — or comes back null and flags the trial.",
    roles: ["claude"],
  },
  {
    title: "Validate",
    desc: "Deterministic checks on every extraction before anything is allowed to pool.",
    roles: ["code"],
  },
  {
    title: "Appraise",
    desc: "Risk of bias (RoB 2) per trial and certainty (GRADE) per outcome — each judgment with a source quote, confirmed by a human.",
    roles: ["claude", "human"],
  },
  {
    title: "Pool",
    desc: "Random-effects meta-analysis: REML between-study variance, HKSJ intervals, heterogeneity reported, leave-one-out sensitivity. Library code only.",
    roles: ["code"],
  },
  {
    title: "Watch",
    desc: "When a new trial reads out, the review re-pools itself and flags whether the estimate or the conclusion moved.",
    roles: ["code"],
  },
];

function Pipeline() {
  return (
    <ol className="flex flex-col">
      {STAGES.map((s, i) => (
        <li key={s.title} data-testid="pipeline-stage" className="relative flex gap-4 pb-5">
          {/* Spine: node + connector down to the next stage */}
          <div className="flex flex-col items-center">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-mono text-[12px] ${
                s.title === "Pool"
                  ? "bg-primary text-on-primary"
                  : "hairline bg-surface-container-low text-ink-light"
              }`}
            >
              {i + 1}
            </span>
            {i < STAGES.length - 1 && <span className="w-px flex-1 bg-hairline-light" aria-hidden />}
          </div>
          <div className="flex-1 pt-0.5">
            <div className="flex flex-wrap items-center gap-2">
              <span data-testid="stage-title" className="text-[14px] font-semibold text-ink-light">
                {s.title}
              </span>
              {s.roles.map((r) => (
                <RoleChip key={r} role={r} />
              ))}
            </div>
            <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-muted-light">
              {s.desc}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

// ── Provenance ─────────────────────────────────────────────────────────────

function ProvenanceDemo() {
  return (
    <div className="grid items-stretch gap-3 sm:grid-cols-[1fr_auto_1.2fr]">
      <div
        data-testid="provenance-value"
        className="rounded-md hairline bg-surface-container-low p-4"
      >
        <p className="text-label-caps uppercase text-ink-muted-light">In the forest plot</p>
        <p className="mt-2 font-mono text-[20px] text-ink-light">
          412 <span className="text-ink-muted-light">/</span> 4668
        </p>
        <p className="mt-1 font-mono text-[11px] text-ink-muted-light">
          events / total · treatment arm
        </p>
      </div>

      <div className="flex items-center justify-center text-ink-muted-light" aria-hidden>
        <Icon name="link" size={20} />
      </div>

      <div data-testid="provenance-snippet" className="rounded-md hairline bg-card-light p-4">
        <p className="text-label-caps uppercase text-ink-muted-light">Its source</p>
        <blockquote className="mt-2 border-l-2 border-accent pl-3 text-[13px] italic leading-relaxed text-ink-light">
          “The primary outcome occurred in 412 of 4668 participants (8.8%) in the treatment
          group…”
        </blockquote>
        <p className="mt-2 font-mono text-[11px] text-ink-muted-light">
          NCT01720446 · results section
        </p>
      </div>
    </div>
  );
}

// ── Validation gate ────────────────────────────────────────────────────────

const CHECKS = [
  "Events cannot exceed arm totals",
  "Arm sizes must sum correctly",
  "Percentages must match counts",
];

function ValidationGateDemo() {
  return (
    <div className="grid items-center gap-3 sm:grid-cols-[1.2fr_auto_1fr]">
      <div className="rounded-md hairline bg-surface-container-low p-4">
        <p className="text-label-caps uppercase text-ink-muted-light">Every extraction</p>
        <ul className="mt-2 flex flex-col gap-1.5">
          {CHECKS.map((c) => (
            <li key={c} className="flex items-center gap-2 font-mono text-[12px] text-ink-light">
              <Icon name="rule" size={14} className="text-ink-muted-light" />
              {c}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex items-center justify-center text-ink-muted-light" aria-hidden>
        <Icon name="arrow_forward" size={20} className="hidden sm:block" />
        <Icon name="arrow_downward" size={20} className="sm:hidden" />
      </div>

      <div className="flex flex-col gap-2.5">
        <div className="flex items-center gap-2.5 rounded-md border border-risk-low bg-risk-low-container px-4 py-3">
          <Icon name="check_circle" size={18} className="text-risk-low" />
          <div>
            <p className="text-[13px] font-medium text-ink-light">Passes — enters the pool</p>
          </div>
        </div>
        <div className="flex items-center gap-2.5 rounded-md border border-risk-some bg-risk-some-container px-4 py-3">
          <Icon name="flag" size={18} className="text-risk-some" />
          <div>
            <p className="text-[13px] font-medium text-ink-light">
              Fails — flagged for your review, never pooled
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Living layer ───────────────────────────────────────────────────────────

// Mini confidence-interval bar: linear scale, dashed null line at RR 1.0.
function CiBar({
  low,
  high,
  effect,
  accent,
}: {
  low: number;
  high: number;
  effect: number;
  accent?: boolean;
}) {
  const min = 0.7;
  const max = 1.15;
  const w = 220;
  const x = (v: number) => ((v - min) / (max - min)) * w;
  const cls = accent ? "text-accent" : "text-ink-light";
  return (
    <svg viewBox={`0 0 ${w} 24`} className={`h-6 w-[220px] ${cls}`} aria-hidden>
      <line
        x1={x(1)}
        y1={0}
        x2={x(1)}
        y2={24}
        stroke="var(--outline-variant)"
        strokeWidth="1"
        strokeDasharray="3 3"
      />
      <line x1={x(low)} y1={12} x2={x(high)} y2={12} stroke="currentColor" strokeWidth="1.5" />
      <line x1={x(low)} y1={8} x2={x(low)} y2={16} stroke="currentColor" strokeWidth="1.5" />
      <line x1={x(high)} y1={8} x2={x(high)} y2={16} stroke="currentColor" strokeWidth="1.5" />
      <rect x={x(effect) - 4} y={8} width={8} height={8} fill="currentColor" />
    </svg>
  );
}

function LivingDemo() {
  return (
    <div className="flex flex-col gap-3">
      <div
        data-testid="living-before"
        className="grid items-center gap-x-4 gap-y-1 rounded-md hairline bg-surface-container-low px-4 py-3 sm:grid-cols-[7rem_auto_1fr]"
      >
        <span className="font-mono text-[11px] text-ink-muted-light">v1 · 6 trials</span>
        <CiBar low={0.8} high={0.99} effect={0.89} />
        <span className="font-mono text-[13px] text-ink-light">RR 0.89 [0.80, 0.99]</span>
      </div>

      <div className="flex items-center gap-2 pl-4 text-ink-muted-light">
        <Icon name="sync" size={16} className="text-accent" />
        <span className="text-[12px]">
          A new trial reads out — the review re-pools itself and diffs the answer
        </span>
      </div>

      <div
        data-testid="living-after"
        className="grid items-center gap-x-4 gap-y-1 rounded-md border border-accent-border bg-accent-container/40 px-4 py-3 sm:grid-cols-[7rem_auto_1fr]"
      >
        <span className="font-mono text-[11px] text-ink-muted-light">v2 · 7 trials</span>
        <CiBar low={0.79} high={0.94} effect={0.86} accent />
        <span className="flex flex-wrap items-center gap-3 font-mono text-[13px] text-ink-light">
          RR 0.86 [0.79, 0.94]
          <span className="inline-flex items-center gap-1.5 rounded-full border border-accent bg-card-light px-2.5 py-1 font-sans text-[10px] font-semibold uppercase tracking-wider text-accent">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Estimate updated
          </span>
        </span>
      </div>

      <p className="pl-4 text-[11px] text-ink-muted-light">
        Dashed line marks no effect (RR 1.0). Version history and the full diff live in each
        review’s Updates and Audit Trail screens.
      </p>
    </div>
  );
}

// ── Refusals ───────────────────────────────────────────────────────────────

const REFUSALS = [
  "Claude never computes a pooled estimate. All statistics run in a validated library, never in the model.",
  "No silent inference. A value that is not clearly present comes back null and flags the trial — never back-calculated.",
  "Unlike trials are not pooled. Clinical homogeneity is confirmed, not assumed.",
  "When data is thin or heterogeneity is high, the tool abstains rather than invent precision.",
  "Rare events change the method (Peto or Mantel–Haenszel) or stop the pool. No silent zero-cell corrections.",
];

// ── Page ───────────────────────────────────────────────────────────────────

function Section({
  label,
  title,
  lead,
  children,
}: {
  label: string;
  title: string;
  lead: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-label={label} className="rounded-md hairline bg-card-light p-6">
      <h2 className="text-section-sm text-ink-light">{title}</h2>
      <p className="mb-5 mt-1 max-w-2xl text-[13px] text-ink-muted-light">{lead}</p>
      {children}
    </section>
  );
}

export function HowItWorks() {
  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <div className="mb-8">
        <h1 className="font-sans text-display-lg text-ink-light">How Strata works</h1>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-ink-muted-light">
          A living meta-analysis you can audit line by line. One rule holds it together:{" "}
          <span className="font-medium text-ink-light">
            pool only numbers that can be traced to a source and pass validation
          </span>{" "}
          — and say what was excluded, and why.
        </p>
      </div>

      {/* Division of labour: each part does only what it is reliable at. */}
      <section aria-label="Division of labour" className="mb-4">
        <div className="grid gap-3 sm:grid-cols-3">
          {ACTORS.map((a) => (
            <div key={a.title} className="rounded-md hairline bg-card-light p-5">
              <RoleChip role={a.role} />
              <h2 className="mt-3 text-[14px] font-semibold text-ink-light">{a.title}</h2>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted-light">{a.body}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="flex flex-col gap-4">
        <Section
          label="The pipeline"
          title="The pipeline"
          lead="Seven stages from question to living answer. The chips show who is trusted with each one — the model never touches a stage that involves arithmetic."
        >
          <Pipeline />
        </Section>

        <Section
          label="Provenance"
          title="Every number carries its source"
          lead="Each extracted value keeps the trial it came from and the exact sentence or table cell behind it. In the Evidence screen, clicking any number opens exactly this."
        >
          <ProvenanceDemo />
        </Section>

        <Section
          label="The validation gate"
          title="The validation gate"
          lead="Plain code — not the model — checks every extraction before pooling. There is no third exit: a number either passes or waits for a human."
        >
          <ValidationGateDemo />
        </Section>

        <Section
          label="The living layer"
          title="The answer never goes stale"
          lead="A published meta-analysis is out of date the moment it prints. Here, a new readout triggers a re-pool, and the diff tells you whether the estimate — or the conclusion — moved."
        >
          <LivingDemo />
        </Section>

        <Section
          label="What Strata refuses to do"
          title="What Strata refuses to do"
          lead="In a regulated setting, the refusals are the feature. A confident wrong answer is worse than an honest abstention."
        >
          <ul className="flex flex-col gap-2.5">
            {REFUSALS.map((r) => (
              <li key={r} className="flex items-start gap-2.5 text-[13px] leading-relaxed">
                <Icon name="block" size={16} className="mt-0.5 shrink-0 text-risk-high" />
                <span className="text-ink-light">{r}</span>
              </li>
            ))}
          </ul>
        </Section>
      </div>

      <div className="mt-8 flex items-center gap-4">
        <Link
          to="/ask"
          className="inline-flex items-center gap-1.5 rounded-md bg-ink-light px-4 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
        >
          <Icon name="edit_note" size={18} />
          Run a review
        </Link>
        <Link to="/" className="text-[13px] text-accent underline">
          or browse existing reviews
        </Link>
      </div>
    </div>
  );
}
