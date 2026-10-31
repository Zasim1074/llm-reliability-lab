"use client";

import { useCallback, useEffect, useState } from "react";

const API =
  (typeof window === "undefined" ? process.env.INTERNAL_API_BASE_URL : process.env.NEXT_PUBLIC_API_BASE_URL) ||
  (typeof window === "undefined" ? "http://api:8000/api/v1" : "http://localhost:8000/api/v1");
const inFlightGets = new Map<string, Promise<unknown>>();
const nav = [
  "Overview",
  "Semantic Cache",
  "Cache Benchmarks",
  "Evaluation Lab",
  "Bias Testing",
  "RAG Security",
  "Experiment History",
  "Settings",
];
type RecordItem = {
  id: string;
  type: string;
  name: string;
  status: string;
  started_at: string;
  metrics: Record<string, number | string>;
};
type Summary = {
  total_experiments: number;
  cache_hit_rate: number | null;
  estimated_avoided_calls: number;
  average_cache_latency_ms: number | null;
  latest_evaluation_score: number | null;
  rag_attack_success_rate: number | null;
  recent: RecordItem[];
};

async function api(path: string, init?: RequestInit) {
  const method = (init?.method || "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  const accessToken = typeof window === "undefined"
    ? null
    : window.sessionStorage.getItem("llm_reliability_access_token");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const existing = method === "GET" ? inFlightGets.get(path) : undefined;
  if (existing) return existing;

  const request = (async () => {
    const response = await fetch(`${API}${path}`, { ...init, method, headers });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || body?.detail || `Request failed (${response.status})`);
    }
    return response.status === 204 ? null : response.json();
  })();
  if (method === "GET") inFlightGets.set(path, request);
  try {
    return await request;
  } finally {
    if (method === "GET" && inFlightGets.get(path) === request) {
      inFlightGets.delete(path);
    }
  }
}

function Icon({ children }: { children: React.ReactNode }) {
  return (
    <span className="icon" aria-hidden="true">
      {children}
    </span>
  );
}

export default function Home() {
  const [active, setActive] = useState("Overview");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [experiments, setExperiments] = useState<RecordItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [namespace, setNamespace] = useState("default");
  const [response, setResponse] = useState("");
  const [lookup, setLookup] = useState<{
    hit: boolean;
    match_type: string | null;
    score: number;
    response: string | null;
    latency_ms: number;
  } | null>(null);
  const [prompt, setPrompt] = useState("");
  const [candidate, setCandidate] = useState("");
  const [alternativeCandidate, setAlternativeCandidate] = useState("");
  const [reference, setReference] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [securityResult, setSecurityResult] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [runtimeSettings, setRuntimeSettings] = useState<Record<string, unknown> | null>(null);
  const [accessTokenInput, setAccessTokenInput] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const s = (await api("/experiments/summary")) as Summary;
      setSummary(s);
      setExperiments(s.recent || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to reach the API");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    let active = true;
    const load = async () => {
      setError("");
      try {
        const s = (await api("/experiments/summary")) as Summary;
        if (active) {
          setSummary(s);
          setExperiments(s.recent || []);
        }
      } catch (e) {
        if (active)
          setError(e instanceof Error ? e.message : "Unable to reach the API");
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (active !== "Experiment History") return;
    let current = true;
    api("/experiments?limit=50")
      .then((items) => {
        if (current) setExperiments(items as RecordItem[]);
      })
      .catch((e: unknown) => {
        if (current)
          setError(e instanceof Error ? e.message : "Unable to load experiments");
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [active]);

  useEffect(() => {
    if (active !== "Settings") return;
    let current = true;
    api("/settings")
      .then((value) => {
        if (current) setRuntimeSettings(value as Record<string, unknown>);
      })
      .catch((e: unknown) => {
        if (current) setError(e instanceof Error ? e.message : "Unable to load settings");
      });
    return () => {
      current = false;
    };
  }, [active]);

  const act = async (
    action: () => Promise<unknown>,
    message: string,
    refreshSummary = true,
  ) => {
    setError("");
    setNotice("");
    try {
      const value = await action();
      if (value && typeof value === "object")
        setResult(value as Record<string, unknown>);
      setNotice(message);
      if (refreshSummary) await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "The operation failed");
    }
  };

  const runCache = async () => {
    const v = await api("/cache/lookup", {
      method: "POST",
      body: JSON.stringify({ query, namespace }),
    });
    setLookup(v);
    return v;
  };
  const runBenchmark = () =>
    act(
      () =>
        api("/benchmarks", {
          method: "POST",
          body: JSON.stringify({
            query:
              query || "How does semantic caching improve LLM performance?",
            namespace,
          }),
        }),
      "Benchmark complete. Measured lookup values and estimated cost savings are shown below.",
    );
  const storeAnswer = () =>
    act(
      () =>
        api("/cache", {
          method: "POST",
          body: JSON.stringify({ query, response, namespace }),
        }),
      "Response stored in the cache.",
      false,
    );
  const evaluate = () =>
    act(
      () =>
        api(active === "Bias Testing" ? "/bias-tests" : "/evaluations", {
          method: "POST",
          body: JSON.stringify({
            prompt,
            candidate,
            alternative_candidate:
              active === "Bias Testing" ? alternativeCandidate : undefined,
            reference: reference || null,
          }),
        }),
      active === "Bias Testing"
        ? "Bias diagnostics completed."
        : "Evaluation saved.",
    );
  const runSecurity = async () => {
    const cases = await api("/security/sample-cases");
    const r = await api("/security/runs", {
      method: "POST",
      body: JSON.stringify({
        name: "Sample injection evaluation",
        cases,
        mitigation: true,
      }),
    });
    setSecurityResult(r);
    setNotice("Security harness run completed.");
    await refresh();
  };

  const renderContent = () => {
    if (active === "Overview")
      return (
        <>
          <section className="welcome">
            <div>
              <div className="eyebrow">RELIABILITY WORKSPACE</div>
              <h1>
                Make every LLM call
                <br />
                more dependable.
              </h1>
              <p>
                Measure performance, evaluate quality, and test security with
                reproducible experiments.
              </p>
              <div className="welcome-actions">
                <button
                  className="button light"
                  onClick={() => setActive("Semantic Cache")}
                >
                  Explore cache <span>→</span>
                </button>
                <span className="provider">
                  <i /> Demo providers active
                </span>
              </div>
            </div>
            <div className="welcome-art">
              <div className="orb orb-one" />
              <div className="orb orb-two" />
              <div className="signal-card">
                <span className="signal-label">SYSTEM STATUS</span>
                <strong>
                  <i />
                  Operational
                </strong>
                <div className="signal-line">
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                </div>
                <small>Demo mode · local database</small>
              </div>
            </div>
            <div className="grid-glow" />
          </section>
          <div className="section-heading">
            <div>
              <h2>Workspace pulse</h2>
              <p>Signals from your saved experiments</p>
            </div>
            <button
              className="text-button"
              onClick={() => setActive("Experiment History")}
            >
              View history <span>↗</span>
            </button>
          </div>
          <section className="metrics-grid">
            <Metric
              title="Experiments"
              value={summary?.total_experiments ?? 0}
              icon="⌘"
              sub="Persisted runs"
              tone="violet"
            />
            <Metric
              title="Cache hit rate"
              value={
                summary?.cache_hit_rate == null
                  ? "—"
                  : `${summary.cache_hit_rate}%`
              }
              icon="◉"
              sub="Latest benchmark"
              tone="blue"
            />
            <Metric
              title="Avoided calls"
              value={summary?.estimated_avoided_calls ?? 0}
              icon="↗"
              sub="Estimated"
              tone="mint"
            />
            <Metric
              title="Avg. lookup"
              value={
                summary?.average_cache_latency_ms == null
                  ? "—"
                  : `${summary.average_cache_latency_ms} ms`
              }
              icon="◷"
              sub="Measured locally"
              tone="amber"
            />
          </section>
          <section className="lower-grid">
            <div className="panel activity">
              <div className="panel-head">
                <div>
                  <h3>Recent activity</h3>
                  <p>Your latest engineering runs</p>
                </div>
                <span className="live-pill">
                  <i /> LIVE
                </span>
              </div>
              {summary?.recent?.length ? (
                <div className="activity-list">
                  {summary.recent.map((item) => (
                    <Activity key={item.id} item={item} />
                  ))}
                </div>
              ) : (
                <Empty
                  title="No experiments yet"
                  text="Run a cache benchmark, evaluation, or security test to see activity here."
                  action="Start with cache"
                  onClick={() => setActive("Semantic Cache")}
                />
              )}
            </div>
            <div className="panel readiness">
              <div className="panel-head">
                <div>
                  <h3>Reliability signals</h3>
                  <p>Latest results across modules</p>
                </div>
                <span className="dots">•••</span>
              </div>
              <Signal
                label="Evaluation score"
                value={
                  summary?.latest_evaluation_score == null
                    ? "No runs"
                    : `${summary.latest_evaluation_score}/100`
                }
                color="purple"
              />
              <Signal
                label="RAG attack success"
                value={
                  summary?.rag_attack_success_rate == null
                    ? "No runs"
                    : `${summary.rag_attack_success_rate}%`
                }
                color="red"
              />
              <div className="disclosure">
                <span>ⓘ</span>
                <p>
                  Demo metrics are calculated from your local runs. Cost avoided
                  is an estimate based on a configurable assumption.
                </p>
              </div>
            </div>
          </section>
        </>
      );
    if (active === "Semantic Cache" || active === "Cache Benchmarks")
      return (
        <Module
          title={active}
          eyebrow={
            active === "Semantic Cache"
              ? "PERFORMANCE ENGINEERING"
              : "REPRODUCIBLE MEASUREMENTS"
          }
          description={
                active === "Semantic Cache"
              ? "Inspect namespace-safe cached responses and test exact or provider-embedding similarity matches. Demo mode uses exact matches only."
              : "Compare cache behavior against a disabled baseline using your saved cache entries."
          }
        >
          <div className="two-col">
            <div className="panel form-panel">
              <h3>
                {active === "Semantic Cache"
                  ? "Cache playground"
                  : "Run benchmark"}
              </h3>
              <p>Inputs are processed by the local demo API.</p>
              <label>
                Query
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask a question to look up or cache…"
                />
              </label>
              <label>
                Namespace
                <input
                  value={namespace}
                  onChange={(e) => setNamespace(e.target.value)}
                  placeholder="default"
                />
              </label>
              {active === "Semantic Cache" ? (
                <>
                  <div className="button-row">
                    <button
                      className="button primary"
                      disabled={!query.trim()}
                      onClick={() =>
                        void act(runCache, "Cache lookup complete.", false)
                      }
                    >
                      Look up query <span>→</span>
                    </button>
                  </div>
                  <label>
                    Response to cache
                    <textarea
                      value={response}
                      onChange={(e) => setResponse(e.target.value)}
                      placeholder="Add the response for this query…"
                    />
                  </label>
                  <button
                    className="button secondary"
                    disabled={!query.trim() || !response.trim()}
                    onClick={() => void storeAnswer()}
                  >
                    Store response
                  </button>
                </>
              ) : (
                <button
                  className="button primary"
                  onClick={() => void runBenchmark()}
                >
                  Run benchmark <span>→</span>
                </button>
              )}
            </div>
            <div className="panel result-panel">
              <div className="panel-head">
                <div>
                  <h3>
                    {active === "Semantic Cache"
                      ? "Lookup result"
                      : "Latest result"}
                  </h3>
                  <p>Results appear here after an operation</p>
                </div>
                <span className="result-mark">✳</span>
              </div>
              {lookup && active === "Semantic Cache" ? (
                <>
                  <div
                    className={`result-banner ${lookup.hit ? "success" : "neutral"}`}
                  >
                    <strong>{lookup.hit ? "Cache hit" : "Cache miss"}</strong>
                    <span>{lookup.match_type || "No qualifying match"}</span>
                  </div>
                  <div className="result-stats">
                    <span>
                      Similarity score <b>{lookup.score}</b>
                    </span>
                    <span>
                      Lookup latency <b>{lookup.latency_ms} ms</b>
                    </span>
                  </div>
                  {lookup.response && <pre>{lookup.response}</pre>}
                </>
              ) : (
                <Result value={result} />
              )}
              <div className="disclosure">
                <span>ⓘ</span>
                <p>
                  Demo mode matches exact normalized queries only. Configure a
                  real embedding provider to enable semantic similarity.
                </p>
              </div>
            </div>
          </div>
        </Module>
      );
    if (active === "Evaluation Lab" || active === "Bias Testing")
      return (
        <Module
          title={active}
          eyebrow="QUALITY ENGINEERING"
          description={
            active === "Bias Testing"
              ? "Probe position, verbosity, and repeatability behavior with the deterministic demo judge."
              : "Score candidate responses against a transparent rule-based rubric and save results."
          }
        >
          <div className="two-col">
            <div className="panel form-panel">
              <h3>
                {active === "Bias Testing"
                  ? "Bias diagnostic"
                  : "Evaluate response"}
              </h3>
              <label>
                Prompt
                <input
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="What did the user ask?"
                />
              </label>
              <label>
                Candidate response
                <textarea
                  value={candidate}
                  onChange={(e) => setCandidate(e.target.value)}
                  placeholder="Paste a model response…"
                />
              </label>
              {active === "Bias Testing" && (
                <label>
                  Alternative response
                  <textarea
                    value={alternativeCandidate}
                    onChange={(e) => setAlternativeCandidate(e.target.value)}
                    placeholder="A second answer for the swapped-order comparison…"
                  />
                </label>
              )}
              <label>
                Reference answer <span className="optional">OPTIONAL</span>
                <textarea
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="Provide a reference for groundedness and correctness"
                />
              </label>
              <button
                className="button primary"
                disabled={
                  !prompt.trim() ||
                  !candidate.trim() ||
                  (active === "Bias Testing" && !alternativeCandidate.trim())
                }
                onClick={() => void evaluate()}
              >
                {active === "Bias Testing"
                  ? "Run bias diagnostics"
                  : "Score response"}{" "}
                <span>→</span>
              </button>
              <a
                className="export-link"
                href={`${API}/evaluations/export?format=csv`}
              >
                Export saved evaluations as CSV ↗
              </a>
            </div>
            <div className="panel result-panel">
              <div className="panel-head">
                <div>
                  <h3>Analysis</h3>
                  <p>Criterion and bias indicators</p>
                </div>
                <span className="result-mark">✳</span>
              </div>
              <Result value={result} />
              <div className="disclosure">
                <span>ⓘ</span>
                <p>
                  Heuristic scores are not factuality guarantees or actual LLM
                  judgments. Tiny samples do not support statistical
                  conclusions.
                </p>
              </div>
            </div>
          </div>
        </Module>
      );
    if (active === "RAG Security")
      return (
        <Module
          title={active}
          eyebrow="SECURITY ENGINEERING"
          description="Test prompt-injection handling in a controlled harness. Retrieved text stays untrusted and is never executed."
        >
          <div className="two-col">
            <div className="panel form-panel security-card">
              <div className="security-icon">⌑</div>
              <h3>Run safe sample suite</h3>
              <p>
                Includes benign, direct injection, retrieved-document injection,
                and unauthorized-action examples.
              </p>
              <button
                className="button primary"
                onClick={() =>
                  void act(runSecurity, "Security harness run completed.")
                }
              >
                Run security tests <span>→</span>
              </button>
              <div className="tag-row">
                <span>4 curated cases</span>
                <span>Mitigation enabled</span>
                <span>Local only</span>
              </div>
            </div>
            <div className="panel result-panel">
              <div className="panel-head">
                <div>
                  <h3>Attack outcomes</h3>
                  <p>Harness results; not a security guarantee</p>
                </div>
                <span className="result-mark">⌁</span>
              </div>
              <Result value={securityResult} />
              {Array.isArray(securityResult?.results) && (
                <div className="case-list">
                  {(
                    securityResult.results as {
                      case: number;
                      kind: string;
                      outcome: string;
                    }[]
                  ).map((r) => (
                    <div key={r.case}>
                      <span>{r.case.toString().padStart(2, "0")}</span>
                      <b>{r.kind.replaceAll("_", " ")}</b>
                      <i className={r.outcome}>{r.outcome}</i>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Module>
      );
    if (active === "Experiment History")
      return (
        <Module
          title="Experiment History"
          eyebrow="REPRODUCIBILITY"
          description="Browse persisted runs from cache, evaluation, bias, and security workflows."
        >
          <div className="panel history-panel">
            <div className="panel-head">
              <div>
                <h3>All experiments</h3>
                <p>{experiments.length} saved runs</p>
              </div>
              <button
                className="icon-button"
                onClick={() => void refresh()}
                aria-label="Refresh"
              >
                ↻
              </button>
            </div>
            {experiments.length ? (
              <div className="history-table">
                <div className="table-header">
                  <span>EXPERIMENT</span>
                  <span>TYPE</span>
                  <span>STATUS</span>
                  <span>DATE</span>
                </div>
                {experiments.map((e) => (
                  <Activity key={e.id} item={e} />
                ))}
              </div>
            ) : (
              <Empty
                title="History is empty"
                text="Your completed experiments will be persisted here."
                action="Run an experiment"
                onClick={() => setActive("Semantic Cache")}
              />
            )}
          </div>
        </Module>
      );
    return (
      <Module
        title="Settings"
        eyebrow="WORKSPACE CONFIGURATION"
        description="The demo uses local deterministic providers. Configure environment values on the API host for deployment."
      >
        <div className="two-col">
          <div className="panel readiness">
            <h3>Runtime configuration</h3>
            <Signal label="API" value={API} color="purple" />
            <Signal label="Mode" value={runtimeSettings?.demo_mode === false ? "Production" : "Demo"} color="green" />
            <Signal label="LLM provider" value={String(runtimeSettings?.llm_provider || "Loading…")} color="blue" />
            <Signal label="Embedding provider" value={String(runtimeSettings?.embedding_provider || "Loading…")} color="amber" />
            <p className="form-hint">Provider credentials remain on the API server. Demo mode makes no external provider calls.</p>
          </div>
          <div className="panel form-panel">
            <h3>API access</h3>
            <p>For protected deployments, enter the application access token supplied by the operator. It is stored only in this browser tab.</p>
            <label>
              Bearer token
              <input type="password" autoComplete="off" value={accessTokenInput} onChange={(event) => setAccessTokenInput(event.target.value)} placeholder="APP_ACCESS_TOKEN" />
            </label>
            <div className="button-row">
              <button className="button primary" disabled={!accessTokenInput.trim()} onClick={() => {
                window.sessionStorage.setItem("llm_reliability_access_token", accessTokenInput.trim());
                setAccessTokenInput("");
                void refresh();
              }}>Connect</button>
              <button className="button secondary" onClick={() => {
                window.sessionStorage.removeItem("llm_reliability_access_token");
                setRuntimeSettings(null);
                setNotice("API token removed from this tab.");
              }}>Disconnect</button>
            </div>
          </div>
          <div className="panel form-panel">
            <h3>Reset demo data</h3>
            <p>
              Invalidates all stored cache entries and removes experiment
              history. This cannot be undone.
            </p>
            <button
              className="button danger"
              onClick={async () => {
                if (
                  !window.confirm(
                    "Delete all experiment history and clear the cache?",
                  )
                )
                  return;
                await act(async () => {
                  return api("/settings/demo-data", { method: "DELETE" });
                }, "Demo data cleared.");
              }}
            >
              Reset data
            </button>
          </div>
        </div>
      </Module>
    );
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <span>R</span>
            <i />
          </div>
          <div>
            <b>
              reliability<span>lab</span>
            </b>
            <small>LLM ENGINEERING</small>
          </div>
        </div>
        <div className="workspace-label">
          WORKSPACE <span>⌄</span>
        </div>
        <nav>
          {nav.map((item, i) => (
            <button
              key={item}
              className={`nav-item ${active === item ? "active" : ""} ${i === 3 || i === 5 || i === 6 || i === 7 ? "nav-gap" : ""}`}
              onClick={() => {
                if (item === "Experiment History") setLoading(true);
                setActive(item);
                setResult(null);
                setLookup(null);
                setSecurityResult(null);
              }}
            >
              <Icon>{["⌂", "◉", "▥", "✳", "⟲", "⌑", "◷", "⚙"][i]}</Icon>
              <span>{item}</span>
              {item === "Experiment History" && summary?.total_experiments ? (
                <small>{summary.total_experiments}</small>
              ) : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="demo-box">
            <div>
              <i /> DEMO MODE
            </div>
            <p>Local providers are active. No API key needed.</p>
            <button onClick={() => setActive("Settings")}>
              Configure providers <span>→</span>
            </button>
          </div>
          <div className="user-row">
            <div className="avatar">LL</div>
            <div>
              <b>Lab workspace</b>
              <small>Local environment</small>
            </div>
            <button aria-label="Workspace menu">···</button>
          </div>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            Workspace <span>/</span> <b>{active}</b>
          </div>
          <div className="top-actions">
            <span className="connected">
              <i /> API connected
            </span>
            <button
              className="icon-button"
              onClick={() => void refresh()}
              aria-label="Refresh dashboard"
            >
              ↻
            </button>
            <button className="help-button">
              ? <span>Help</span>
            </button>
          </div>
        </header>
        <div className="content">
          {error && (
            <div className="alert error">
              <b>Could not complete request</b>
              <span>{error}</span>
            </div>
          )}
          {notice && (
            <div className="alert success">
              <b>Done</b>
              <span>{notice}</span>
              <button onClick={() => setNotice("")}>×</button>
            </div>
          )}
          {loading && active === "Overview" ? (
            <div className="loading-state">
              <div className="loader" />
              Loading workspace data…
            </div>
          ) : (
            renderContent()
          )}
          <footer>
            <span>
              RELIABILITY LAB <i /> DEMO BUILD
            </span>
            <span>
              Metrics from local experiments ·{" "}
              <a
                href={`${API.replace("/api/v1", "")}/docs`}
                target="_blank"
                rel="noreferrer"
              >
                API documentation ↗
              </a>
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}

function Metric({
  title,
  value,
  icon,
  sub,
  tone,
}: {
  title: string;
  value: string | number;
  icon: string;
  sub: string;
  tone: string;
}) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${tone}`}>{icon}</div>
      <div className="metric-title">
        {title}
        <span>ⓘ</span>
      </div>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}
function Activity({ item }: { item: RecordItem }) {
  const colors: Record<string, string> = {
    benchmark: "blue",
    evaluation: "violet",
    bias: "amber",
    security: "red",
  };
  return (
    <div className="activity-row">
      <div className={`activity-icon ${colors[item.type] || "blue"}`}>
        {item.type === "security"
          ? "⌑"
          : item.type === "evaluation"
            ? "✳"
            : item.type === "bias"
              ? "⟲"
              : "◉"}
      </div>
      <div className="activity-name">
        <b>{item.name}</b>
        <small>
          {item.type} · {new Date(item.started_at).toLocaleString()}
        </small>
      </div>
      <span className={`status ${item.status}`}>{item.status}</span>
      <span className="row-arrow">↗</span>
    </div>
  );
}
function Signal({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="signal-row">
      <span>
        <i className={color} />
        {label}
      </span>
      <b>{value}</b>
    </div>
  );
}
function Empty({
  title,
  text,
  action,
  onClick,
}: {
  title: string;
  text: string;
  action: string;
  onClick: () => void;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">⌁</div>
      <h4>{title}</h4>
      <p>{text}</p>
      <button className="text-button" onClick={onClick}>
        {action} →
      </button>
    </div>
  );
}
function Module({
  title,
  eyebrow,
  description,
  children,
}: {
  title: string;
  eyebrow: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <div className="module-intro">
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </>
  );
}
function Result({ value }: { value: Record<string, unknown> | null }) {
  if (!value)
    return (
      <div className="result-empty">
        <div>✳</div>
        <b>Ready when you are</b>
        <span>Run this module to see calculated results.</span>
      </div>
    );
  const metrics = (
    value.metrics && typeof value.metrics === "object" ? value.metrics : value
  ) as Record<string, unknown>;
  const scores = (
    value.scores && typeof value.scores === "object" ? value.scores : null
  ) as Record<string, unknown> | null;
  const overall =
    typeof value.overall === "number"
      ? value.overall
      : typeof metrics.overall_score === "number"
        ? metrics.overall_score
        : null;
  const keyLabels: Record<string, string> = {
    total_requests: "Total requests",
    cache_hits: "Cache hits",
    cache_misses: "Cache misses",
    hit_rate: "Hit rate",
    average_lookup_latency_ms: "Average lookup latency",
    median_lookup_latency_ms: "Median lookup latency",
    estimated_avoided_calls: "Estimated avoided calls",
    estimated_cost_avoided_usd: "Estimated cost avoided",
    blocked_attacks: "Blocked attacks",
    successful_attacks: "Successful attacks",
    attack_success_rate: "Attack success rate",
    false_positives: "False positives",
    false_negatives: "False negatives",
    exact_hits: "Exact hits",
    similarity_hits: "Similarity hits",
  };
  const simple = Object.entries(metrics).filter(
    ([k, v]) =>
      keyLabels[k] && (typeof v === "string" || typeof v === "number"),
  );
  return (
    <div className="structured-result">
      {overall !== null && (
        <div className="score-highlight">
          <span>OVERALL SCORE</span>
          <b>
            {overall}
            <small>/100</small>
          </b>
          <i>
            <em style={{ width: `${Math.min(100, Math.max(0, overall))}%` }} />
          </i>
        </div>
      )}
      {scores && (
        <div className="score-list">
          {Object.entries(scores).map(([k, v]) => (
            <div key={k}>
              <span>{k.replaceAll("_", " ")}</span>
              <b>
                {String(v)}
                <small>/100</small>
              </b>
              <i>
                <em
                  style={{
                    width: `${Math.min(100, Math.max(0, Number(v) || 0))}%`,
                  }}
                />
              </i>
            </div>
          ))}
        </div>
      )}
      {simple.length > 0 && (
        <div className="metric-results">
          {simple.map(([k, v]) => (
            <div key={k}>
              <span>{keyLabels[k]}</span>
              <b>
                {typeof v === "number" && k.includes("latency")
                  ? `${v} ms`
                  : typeof v === "number" && k.includes("rate")
                    ? `${v}%`
                    : typeof v === "number" && k.includes("usd")
                      ? `$${v}`
                      : String(v)}
              </b>
            </div>
          ))}
        </div>
      )}
      {!scores && !simple.length && (
        <pre className="json-result">{JSON.stringify(value, null, 2)}</pre>
      )}
      {typeof value.limitation === "string" && (
        <p className="result-note">{value.limitation}</p>
      )}
    </div>
  );
}
