import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Home from "./page";

describe("Reliability Lab dashboard", () => {
  afterEach(() => {
    cleanup();
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
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).has("Content-Type")).toBe(false);
  });

  it("clears experiments through the supported endpoint", async () => {
    const fetchMock = vi.fn().mockImplementation(async (_url: string, init?: RequestInit) => ({
      ok: true,
      status: 200,
      json: async () => init?.method === "DELETE"
        ? { invalidated: 0, deleted: 0 }
        : { total_experiments: 0, cache_hit_rate: null, estimated_avoided_calls: 0, average_cache_latency_ms: null, latest_evaluation_score: null, rag_attack_success_rate: null, recent: [] },
    }));
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<Home />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Settings" }))[0]);
    fireEvent.click(screen.getByRole("button", { name: "Reset data" }));
    expect(await screen.findByText("Demo data cleared.")).toBeInTheDocument();
    await waitFor(() => {
    expect(fetchMock.mock.calls.some(([url, init]) =>
        String(url).endsWith("/settings/demo-data") && init?.method === "DELETE",
      )).toBe(true);
    });
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "DELETE")).toHaveLength(1);
  });
});
