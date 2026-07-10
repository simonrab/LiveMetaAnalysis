import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { HowItWorks } from "./HowItWorks";

function renderPage() {
  return render(
    <MemoryRouter>
      <HowItWorks />
    </MemoryRouter>
  );
}

// BDD: a first-time visitor opens "How it works" and can understand, from the
// visuals alone, who does what, why every number is traceable, and why the
// answer stays current.

describe("HowItWorks", () => {
  it("Given a visitor, When the page loads, Then it states the division of labour", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: /how strata works/i })).toBeInTheDocument();
    // The three actors, each with what they are trusted to do.
    expect(screen.getByText(/reads and structures the evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/deterministic code/i)).toBeInTheDocument();
    expect(screen.getByText(/confirms the load-bearing judgments/i)).toBeInTheDocument();
  });

  it("shows the pipeline stages in order, each tagged with who performs it", () => {
    renderPage();
    const pipeline = screen.getByRole("region", { name: /pipeline/i });
    const stages = within(pipeline).getAllByTestId("pipeline-stage");
    const titles = stages.map((s) => within(s).getByTestId("stage-title").textContent);
    expect(titles).toEqual([
      "Ask",
      "Retrieve",
      "Extract",
      "Validate",
      "Appraise",
      "Pool",
      "Watch",
    ]);
    // The pooling stage is code-only: Claude never does the math.
    const pool = stages[5];
    expect(within(pool).getByText("Code")).toBeInTheDocument();
    expect(within(pool).queryByText("Claude")).not.toBeInTheDocument();
    // Extraction is Claude's reading job.
    expect(within(stages[2]).getByText("Claude")).toBeInTheDocument();
  });

  it("illustrates provenance: an extracted number linked to its source snippet", () => {
    renderPage();
    const prov = screen.getByRole("region", { name: /provenance/i });
    // A concrete extracted value, its trial id, and the quoted snippet it came from.
    expect(within(prov).getByTestId("provenance-value")).toBeInTheDocument();
    expect(within(prov).getByTestId("provenance-snippet")).toBeInTheDocument();
    expect(within(prov).getByText(/NCT\d+/)).toBeInTheDocument();
  });

  it("illustrates the validation gate with its checks and both outcomes", () => {
    renderPage();
    const gate = screen.getByRole("region", { name: /validation gate/i });
    expect(within(gate).getByText(/events cannot exceed arm totals/i)).toBeInTheDocument();
    expect(within(gate).getByText(/arm sizes must sum correctly/i)).toBeInTheDocument();
    expect(within(gate).getByText(/percentages must match counts/i)).toBeInTheDocument();
    // Both exits of the gate are visible: into the pool, or flagged — never pooled.
    expect(within(gate).getByText(/enters the pool/i)).toBeInTheDocument();
    expect(within(gate).getByText(/never pooled/i)).toBeInTheDocument();
  });

  it("illustrates the living layer: a new trial re-pools the answer and flags the change", () => {
    renderPage();
    const living = screen.getByRole("region", { name: /living/i });
    expect(within(living).getByTestId("living-before")).toBeInTheDocument();
    expect(within(living).getByTestId("living-after")).toBeInTheDocument();
    expect(within(living).getByText(/new trial/i)).toBeInTheDocument();
    expect(within(living).getByText(/estimate updated/i)).toBeInTheDocument();
  });

  it("explains the competitive landscape and that every cell is backed by pooled evidence", () => {
    renderPage();
    const landscape = screen.getByRole("region", { name: /landscape/i });
    // The board maps assets by development stage.
    expect(within(landscape).getByText("Assets by development phase")).toBeInTheDocument();
    // Every cell carries an honest evidence badge in one of three states.
    expect(within(landscape).getByText("Pooled estimate")).toBeInTheDocument();
    expect(within(landscape).getByText("Gate pending")).toBeInTheDocument();
    expect(within(landscape).getByText("Abstained")).toBeInTheDocument();
    // The two halves are one system: a new trial moves the standing, not just a number.
    expect(within(landscape).getByText(/competitive standing/i)).toBeInTheDocument();
  });

  it("states what the tool refuses to do", () => {
    renderPage();
    const refusals = screen.getByRole("region", { name: /refuses/i });
    expect(within(refusals).getByText(/never computes a pooled estimate/i)).toBeInTheDocument();
    expect(within(refusals).getByText(/abstains/i)).toBeInTheDocument();
  });

  it("ends with a way to start a review", () => {
    renderPage();
    const cta = screen.getByRole("link", { name: /run a review/i });
    expect(cta).toHaveAttribute("href", "/ask");
  });
});
