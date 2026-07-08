import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { GradeDetail } from "./GradeDetail";
import { reviewFixture } from "../test/fixtures";

vi.mock("../lib/api", () => ({ getReview: vi.fn() }));
import { getReview } from "../lib/api";

function renderAt(id: string) {
  return render(
    <MemoryRouter initialEntries={[`/reviews/${id}/grade`]}>
      <Routes>
        <Route path="/reviews/:id/grade" element={<GradeDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("GradeDetail", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the SoF line, certainty, and five certainty domains", async () => {
    vi.mocked(getReview).mockResolvedValue(reviewFixture);
    renderAt("glp1-mace");

    // Summary-of-Findings line.
    expect(
      await screen.findByText(/moderate-certainty evidence/)
    ).toBeInTheDocument();
    // Certainty rating shown (moderate).
    expect(screen.getAllByText(/moderate/i).length).toBeGreaterThan(0);
    // All five GRADE domains render.
    expect(screen.getByText("Risk of Bias")).toBeInTheDocument();
    expect(screen.getByText("Indirectness")).toBeInTheDocument();
    expect(screen.getByText("Publication Bias")).toBeInTheDocument();
    // The downgraded domain is flagged and its rationale surfaces.
    expect(screen.getByText("Downgraded")).toBeInTheDocument();
    // The rationale surfaces on the domain card and again in the footnote.
    expect(screen.getAllByText(/NYHA class differs/).length).toBeGreaterThan(0);
  });
});
