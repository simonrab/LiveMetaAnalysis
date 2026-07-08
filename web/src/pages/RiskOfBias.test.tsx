import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { RiskOfBias } from "./RiskOfBias";
import { reviewFixture } from "../test/fixtures";

vi.mock("../lib/api", () => ({ getReview: vi.fn(), postRobDecision: vi.fn() }));
import { getReview, postRobDecision } from "../lib/api";

function renderAt(id: string) {
  return render(
    <MemoryRouter initialEntries={[`/reviews/${id}/rob`]}>
      <Routes>
        <Route path="/reviews/:id/rob" element={<RiskOfBias />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("RiskOfBias", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the five RoB 2 domains with judgments and source quotes", async () => {
    vi.mocked(getReview).mockResolvedValue(reviewFixture);
    renderAt("glp1-mace");

    expect(await screen.findByText(/D1: Randomization/)).toBeInTheDocument();
    expect(screen.getByText(/D5: Selection/)).toBeInTheDocument();
    // The source quote a judgment rests on is shown.
    expect(
      screen.getByText(/centralized, computer-generated schedule/)
    ).toBeInTheDocument();
    // Overall judgment chip (LEADER is "some concerns").
    expect(screen.getAllByText(/Some concerns/).length).toBeGreaterThan(0);
  });

  it("confirms a domain via the Verify button", async () => {
    vi.mocked(getReview).mockResolvedValue(reviewFixture);
    vi.mocked(postRobDecision).mockResolvedValue(reviewFixture);
    renderAt("glp1-mace");

    const verifyButtons = await screen.findAllByRole("button", { name: /Verify/ });
    fireEvent.click(verifyButtons[0]);

    await waitFor(() =>
      expect(postRobDecision).toHaveBeenCalledWith("glp1-mace", {
        study_id: "NCT01179048",
        domain_key: "D1",
      })
    );
  });
});
