import { describe, it, expect, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Sidebar } from "./Sidebar";

// jsdom has no matchMedia; the theme hook needs it.
beforeAll(() => {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
});

describe("Sidebar", () => {
  it("links to the How it works page", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );
    const link = screen.getByRole("link", { name: /how it works/i });
    expect(link).toHaveAttribute("href", "/how-it-works");
  });
});
