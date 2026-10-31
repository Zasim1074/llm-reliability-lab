import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Home from "./page";

describe("Reliability Lab dashboard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders the dashboard and empty state when no experiments exist", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => ({
      ok: true,
      status: 200,
      json: async () => String(url).includes("summary")
        ? { total_experiments: 0, cache_hit_rate: null, estimated_avoided_calls: 0, average_cache_latency_ms: null, latest_evaluation_score: null, rag_attack_success_rate: null, recent: [] }
        : [],
    }));
    vi.stubGlobal("fetch", fetchMock);
    render(<Home />);
    expect(await screen.findByRole("heading", { name: "Workspace pulse" })).toBeInTheDocument();
    expect(await screen.findByText("No experiments yet")).toBeInTheDocument();
    expect(screen.getByText("Experiments").parentElement?.querySelector("strong")).toHaveTextContent("0");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain("/experiments/summary");
    expect(fetchMock.mock.calls[0][1]?.headers).not.toHaveProperty("Content-Type");
  });
});
