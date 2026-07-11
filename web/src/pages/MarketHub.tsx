import { useState } from "react";
import { marketAsk } from "../lib/api";
import type { MarketAnswer } from "../lib/types";
import { Icon } from "../components/Icon";
import { MarketResult } from "../components/MarketResult";

// The market-intelligence front door. Ask in plain language; the router picks the
// right tool and this renders that tool's real view inline, with a grounded
// narrative and follow-up chips. Deterministic figures — the model only routes.

interface Turn {
  question: string;
  answer?: MarketAnswer;
  error?: boolean;
}

const STARTERS = [
  "Map the obesity landscape",
  "What changed in obesity since 2023",
  "Compare tirzepatide and semaglutide",
  "Upcoming readouts in obesity",
  "Group obesity by mechanism",
];

export function MarketHub() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function ask(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    const idx = turns.length;
    setTurns((t) => [...t, { question: q }]);
    try {
      const answer = await marketAsk(q);
      setTurns((t) => t.map((turn, i) => (i === idx ? { ...turn, answer } : turn)));
    } catch {
      setTurns((t) => t.map((turn, i) => (i === idx ? { ...turn, error: true } : turn)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-4xl flex-col px-8 py-10">
      <div className="mb-6">
        <h1 className="font-sans text-display-lg text-ink-light">Market Intelligence</h1>
        <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
          Ask about assets, indications, timing, or what moved — in plain language.
        </p>
      </div>

      {turns.length === 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {STARTERS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => ask(s)}
              className="rounded-full hairline bg-card-light px-3.5 py-1.5 text-[13px] text-ink-muted-light hover:text-ink-light"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 space-y-6">
        {turns.map((turn, i) => (
          <div key={i}>
            <div className="mb-3 flex justify-end">
              <div className="max-w-[80%] rounded-xl rounded-br-sm bg-accent-container px-3.5 py-2 text-[13px] text-on-accent-container">
                {turn.question}
              </div>
            </div>

            {turn.error && (
              <p className="font-mono text-[13px] text-risk-high">
                Could not answer that. Is the backend running on :8000?
              </p>
            )}

            {turn.answer && (
              <div className="flex gap-3">
                <div className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-primary text-on-primary">
                  <Icon name="auto_awesome" size={14} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="mb-3 text-[13px] leading-relaxed text-ink-light">
                    {turn.answer.narrative}
                  </p>
                  <MarketResult answer={turn.answer} />
                  {turn.answer.suggestions.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {turn.answer.suggestions.map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => ask(s)}
                          className="inline-flex items-center gap-1 rounded-full hairline bg-surface-container-low px-3 py-1 text-[12px] text-ink-muted-light hover:text-ink-light"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {!turn.answer && !turn.error && (
              <div className="flex items-center gap-2 text-[13px] text-ink-muted-light">
                <Icon name="progress_activity" size={16} className="animate-spin" />
                Working…
              </div>
            )}
          </div>
        ))}
      </div>

      <form
        className="sticky bottom-6 mt-6 flex items-center gap-2 rounded-full hairline bg-card-light py-1.5 pl-4 pr-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <input
          aria-label="market question"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about assets, indications, timing, or what moved…"
          className="flex-1 bg-transparent text-[14px] text-ink-light outline-none placeholder:text-ink-muted-light"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          aria-label="send"
          className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-on-primary disabled:opacity-40"
        >
          <Icon name="arrow_upward" size={18} />
        </button>
      </form>
    </div>
  );
}
