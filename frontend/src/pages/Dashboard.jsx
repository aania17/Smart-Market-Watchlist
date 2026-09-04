import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  listWatchlists,
  createWatchlist,
  deleteWatchlist,
  addItem,
  removeItem,
  viewWatchlist,
  hourlyWatchlist,
  updateSensitivity,
  updateQuantity,
} from "../api/watchlists";
import AddSymbolForm from "../components/AddSymbolForm";
import SignalCard from "../components/SignalCard";
import HourlyDashboard from "../components/HourlyDashboard";

function timeAgo(iso) {
  if (!iso) return null;

  // Force JavaScript to treat the string as UTC if it lacks a timezone marker.
  const utcIso = iso.endsWith("Z") ? iso : `${iso}Z`;
  const diffMs = Date.now() - new Date(utcIso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function Dashboard() {
  const { user, logout } = useAuth();

  const [watchlists, setWatchlists] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [view, setView] = useState(null); // { watchlist, signals }
  const [hourlySeries, setHourlySeries] = useState([]);
  const [hourlyLoading, setHourlyLoading] = useState(false);
  const [expandedSymbol, setExpandedSymbol] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [newListName, setNewListName] = useState("");
  const [error, setError] = useState("");
  const viewRequestId = useRef(0);
  const bootstrapStarted = useRef(false);
  const watchlistCache = useRef(new Map());
  const activeIdRef = useRef(null);
  const hourlyRequestRef = useRef(null);

  // Bootstrap: load watchlists, auto-create a default one if the account has none.
  useEffect(() => {
    if (bootstrapStarted.current) return;
    bootstrapStarted.current = true;
    (async () => {
      try {
        let lists = await listWatchlists();
        if (lists.length === 0) {
          const created = await createWatchlist("My Watchlist");
          lists = [created];
        }
        setWatchlists(lists);
        setActiveId(lists[0].id);
      } catch {
        setError("Couldn't load your watchlists.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function loadView(id, updateBaseline = false) {
    const requestId = ++viewRequestId.current;
    const cached = watchlistCache.current.get(id);
    if (cached) {
      setView(cached.view);
    }
    setRefreshing(!cached);
    setError("");
    try {
      const viewResult = await viewWatchlist(id, updateBaseline);
      if (requestId !== viewRequestId.current) return;
      setView(viewResult);
      watchlistCache.current.set(id, { view: viewResult });
    } catch {
      if (requestId === viewRequestId.current) setError("Couldn't load prices right now.");
    } finally {
      if (requestId === viewRequestId.current) setRefreshing(false);
    }
  }

  async function handleViewGraph(symbol) {
    const watchlistId = activeId;
    setExpandedSymbol(symbol);
    if (hourlySeries.some((item) => item.symbol === symbol)) return;
    if (hourlyRequestRef.current?.watchlistId === watchlistId) return;
    setHourlyLoading(true);
    const request = hourlyWatchlist(watchlistId);
    hourlyRequestRef.current = { watchlistId, request };
    try {
      const series = await request;
      if (watchlistId === activeIdRef.current) setHourlySeries(series);
    } catch {
      if (watchlistId === activeIdRef.current) setHourlySeries([]);
    } finally {
      if (hourlyRequestRef.current?.request === request) {
        hourlyRequestRef.current = null;
        setHourlyLoading(false);
      }
    }
  }

  // Passive reads preserve the baseline. Only the explicit acknowledgement
  // button below advances the "since last visit" interval.
  useEffect(() => {
    activeIdRef.current = activeId;
    setExpandedSymbol(null);
    setHourlySeries([]);
    if (activeId != null) loadView(activeId, false);
  }, [activeId]);

  async function handleAddSymbol(symbol, assetClass) {
    await addItem(activeId, symbol, assetClass);
    await loadView(activeId, false);
  }

  async function handleRemoveSymbol(symbol) {
    try {
      await removeItem(activeId, symbol);
      await loadView(activeId, false);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't remove that symbol");
    }
  }

  async function handleUpdateQuantity(symbol, quantity) {
    await updateQuantity(activeId, symbol, quantity);
    setView((current) => {
      if (!current) return current;
      const signals = current.signals.map((signal) => {
        if (signal.symbol !== symbol) return signal;
        const impact = quantity !== null && signal.last_visit_price !== null
          ? Number((quantity * (signal.current_price - signal.last_visit_price)).toFixed(2))
          : null;
        return { ...signal, quantity, impact };
      });
      const next = { ...current, items: current.items.map((item) => item.symbol === symbol ? { ...item, quantity } : item), signals };
      watchlistCache.current.set(activeId, { view: next });
      return next;
    });
  }

  async function handleSensitivityChange(event) {
    const threshold = Number(event.target.value);
    const updated = await updateSensitivity(activeId, threshold);
    setWatchlists((current) => current.map((watchlist) => watchlist.id === activeId ? updated : watchlist));
    setView((current) => {
      if (!current) return current;
      const signals = current.signals.map((signal) => ({
        ...signal,
        is_meaningful: Math.max(Math.abs(signal.change_since_last_visit_pct ?? 0), Math.abs(signal.relative_move_vs_index_pct ?? 0)) >= threshold,
      }));
      const next = { ...current, watchlist: updated, signals };
      watchlistCache.current.set(activeId, { view: next });
      return next;
    });
  }

  async function handleCreateWatchlist(e) {
    e.preventDefault();
    const name = newListName.trim();
    if (!name) return;
    try {
      const created = await createWatchlist(name);
      setWatchlists((prev) => [...prev, created]);
      setNewListName("");
      setActiveId(created.id);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't create that watchlist");
    }
  }

  async function handleDeleteWatchlist(id) {
    if (watchlists.length === 1) {
      setError("Keep at least one watchlist.");
      return;
    }
    try {
      await deleteWatchlist(id);
      const remaining = watchlists.filter((watchlist) => watchlist.id !== id);
      setWatchlists(remaining);
      if (id === activeId) setActiveId(remaining[0].id);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't delete that watchlist");
    }
  }

  if (loading) {
    return <div className="flex h-screen items-center justify-center text-slate-500">Loading…</div>;
  }

  const meaningfulCount = view?.signals.filter((s) => s.is_meaningful).length ?? 0;
  const lastVisitAt = view?.signals.find((s) => s.last_visit_at)?.last_visit_at ?? null;
  const stockCount = view?.items?.filter((item) => item.asset_class === "stock").length ?? 0;
  const cryptoCount = view?.items?.filter((item) => item.asset_class === "crypto").length ?? 0;
  const activeWatchlist = watchlists.find((watchlist) => watchlist.id === activeId);
  const signalsBySymbol = new Map((view?.signals ?? []).map((signal) => [signal.symbol, signal]));
  const hourlyBySymbol = new Map((hourlySeries ?? []).map((item) => [item.symbol, item]));
  const displayItems = [...(view?.items ?? [])].sort((first, second) => {
    const firstSignal = signalsBySymbol.get(first.symbol);
    const secondSignal = signalsBySymbol.get(second.symbol);
    if (Boolean(firstSignal?.is_meaningful) !== Boolean(secondSignal?.is_meaningful)) {
      return firstSignal?.is_meaningful ? -1 : 1;
    }
    const firstMove = Math.max(
      Math.abs(firstSignal?.change_since_last_visit_pct ?? 0),
      Math.abs(firstSignal?.relative_move_vs_index_pct ?? 0)
    );
    const secondMove = Math.max(
      Math.abs(secondSignal?.change_since_last_visit_pct ?? 0),
      Math.abs(secondSignal?.relative_move_vs_index_pct ?? 0)
    );
    return secondMove - firstMove;
  });

  return (
    <div data-theme="dark" className="market-grid min-h-screen">
      <header className="bg-primary px-5 py-4 text-white shadow-sm sm:px-8">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <p className="display-font text-lg font-semibold tracking-tight">market / watch</p>
            <p className="mt-0.5 text-xs text-[#aebbd0]">Signed in as {user?.email}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={logout}
              className="rounded-lg border border-[#536781] px-3 py-2 text-xs font-semibold text-[#e2e9f3] transition hover:border-[#8ea5c4] hover:bg-[#263754]"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-7 sm:px-8 sm:py-10">
        <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-sky-600">Your market pulse</p>
            <h1 className="text-3xl font-semibold tracking-tight text-primary sm:text-4xl">
              {activeWatchlist?.name || "Your watchlist"}
            </h1>
            <p className="mt-2 max-w-xl text-sm text-slate-500">The moves that deserve your attention since your last visit.</p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-borders bg-surface px-3 py-2 text-xs font-semibold text-slate-600">
            <span className="h-2 w-2 rounded-full bg-[#2878d4] shadow-[0_0_0_4px_rgba(40,120,212,0.14)]" />
            Markets monitored
          </div>
        </div>

        {/* Watchlist switcher */}
        <div className="mb-6 flex flex-wrap items-center gap-2">
          {watchlists.map((wl) => (
            <div
              key={wl.id}
                className={`flex items-center rounded-lg text-sm font-medium transition ${
                wl.id === activeId ? "bg-[#2878d4] text-white shadow-[0_5px_12px_rgba(40,120,212,0.2)]" : "border border-borders bg-surface text-slate-600"
              }`}
            >
              <button onClick={() => setActiveId(wl.id)} className="px-3 py-2 hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-inset">
                {wl.name}
              </button>
                <button
                onClick={() => handleDeleteWatchlist(wl.id)}
                  className="px-2 py-2 opacity-60 hover:text-market-down hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-inset"
                aria-label={`Delete ${wl.name}`}
                title="Delete watchlist"
              >
                ×
              </button>
            </div>
          ))}
          <form onSubmit={handleCreateWatchlist} className="flex items-center gap-1">
            <input
              value={newListName}
              onChange={(e) => setNewListName(e.target.value)}
              placeholder="New watchlist…"
              className="w-36 rounded-lg border border-borders bg-surface px-3 py-2 text-sm text-primary outline-none placeholder:text-muted focus:border-slate-400 focus:ring-2 focus:ring-slate-400"
            />
            <button
              type="submit"
              className="rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400"
            >
              Add
            </button>
          </form>
        </div>

        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-borders bg-surface px-4 py-3 shadow-sm">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Attention sensitivity</p>
            <p className="mt-1 text-xs text-muted">Flag moves at or above this percentage.</p>
          </div>
          <label className="flex items-center gap-3 text-sm font-semibold text-primary">
            <input
              type="range"
              min="0.5"
              max="10"
              step="0.5"
              value={view?.watchlist?.meaningful_threshold_pct ?? activeWatchlist?.meaningful_threshold_pct ?? 2}
              onChange={handleSensitivityChange}
              aria-label="Attention sensitivity percentage"
            />
            <span className="w-12 text-right">{view?.watchlist?.meaningful_threshold_pct ?? activeWatchlist?.meaningful_threshold_pct ?? 2}%</span>
          </label>
        </div>

        <div className="mb-6 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-[#dce5df] bg-[#dce5df] shadow-[0_8px_24px_rgba(31,52,45,0.04)] sm:grid-cols-4">
          <div className="bg-white p-4 sm:p-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Instruments</p>
            <p className="mt-2 text-2xl font-semibold text-primary">{view?.items?.length ?? 0}</p>
          </div>
          <div className="bg-white p-4 sm:p-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Stocks</p>
            <p className="mt-2 text-2xl font-semibold text-primary">{stockCount}</p>
          </div>
          <div className="bg-white p-4 sm:p-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Crypto</p>
            <p className="mt-2 text-2xl font-semibold text-primary">{cryptoCount}</p>
          </div>
          <div className="bg-[#edf3fc] p-4 sm:p-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Worth a look</p>
            <p className="display-font mt-2 text-2xl font-semibold text-[#2878d4]">{meaningfulCount}</p>
          </div>
        </div>

        {/* Summary banner, the core "what changed" hook */}
        <div className="mb-6 flex flex-col gap-4 rounded-xl border border-borders bg-surface p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              {lastVisitAt ? `Last visit: ${timeAgo(lastVisitAt)} (UTC)` : "This is your first visit to this watchlist"}
            </p>
            <p className="mt-2 max-w-3xl text-base font-semibold text-primary">{view?.briefing || (view?.signals.length ? "Nothing meaningfully different since last time" : "Add a symbol to get started")}</p>
            {view?.move_groups?.map((group) => (
              <p key={`${group.direction}-${group.symbols.join("-")}`} className="mt-2 text-xs text-muted">
                {group.symbols.join(", ")} moved together {group.direction} around {Math.abs(group.average_move_pct).toFixed(1)}%.
              </p>
            ))}
          </div>
          <button
            onClick={() => loadView(activeId, true)}
            disabled={refreshing}
            className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50"
          >
            {refreshing ? "Checking…" : "Mark as read & update"}
          </button>
        </div>

        {error && <p className="mb-4 rounded-lg border border-[#f1c5bd] bg-[#fff4f1] px-3 py-2 text-sm font-medium text-[#c85151]">{error}</p>}

        <div className="mb-6">
          <AddSymbolForm onAdd={handleAddSymbol} />
        </div>

        {view?.items?.length === 0 ? (
          <p className="rounded-xl bg-surface p-6 text-center text-sm text-slate-500 shadow-sm">
            No symbols yet — add a stock ticker (e.g. AAPL) or crypto pair (e.g. BTC/USD) above.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {displayItems.map((item) => {
              const signal = signalsBySymbol.get(item.symbol);
              if (signal) {
                return (
                  <SignalCard
                    key={item.symbol}
                    signal={signal}
                    hourlyItem={hourlyBySymbol.get(item.symbol)}
                    onViewGraph={() => handleViewGraph(item.symbol)}
                    onRemove={() => handleRemoveSymbol(item.symbol)}
                    onUpdateQuantity={(quantity) => handleUpdateQuantity(item.symbol, quantity)}
                  />
                );
              }
              return (
                <div
                  key={item.symbol}
                  onClick={() => setExpandedSymbol((current) => (current === item.symbol ? null : item.symbol))}
                  className="cursor-pointer rounded-xl border border-borders bg-surface p-5 shadow-sm transition hover:border-slate-500"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-primary">{item.symbol}</span>
                        <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted">
                          {item.asset_class === "crypto" ? "Crypto" : "Stock"}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-muted">Registered. Price data is unavailable right now.</p>
                    </div>
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        handleRemoveSymbol(item.symbol);
                      }}
                      className="rounded-md px-1 text-lg leading-none text-slate-300 transition hover:bg-red-50 hover:text-market-down focus:outline-none focus:ring-2 focus:ring-slate-400"
                      aria-label={`Remove ${item.symbol}`}
                      title="Remove from watchlist"
                    >
                      ×
                    </button>
                  </div>
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      handleViewGraph(item.symbol);
                    }}
                    className="mt-4 w-full rounded-lg border border-slate-600 px-3 py-2 text-xs font-semibold text-slate-300 transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400"
                  >
                    View graph
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </main>
      {expandedSymbol && (
        <HourlyDashboard
          item={hourlyBySymbol.get(expandedSymbol)}
          loading={hourlyLoading}
          onClose={() => setExpandedSymbol(null)}
        />
      )}
    </div>
  );
}
