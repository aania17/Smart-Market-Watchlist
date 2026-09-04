import { useState } from "react";

function formatPrice(price, assetClass) {
  const decimals = assetClass === "crypto" ? 2 : 2;
  return price.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatPct(pct) {
  if (pct === null || pct === undefined) return null;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

function ChangePill({ pct, label }) {
  if (pct === null || pct === undefined) return null;
  const positive = pct > 0;
  const flat = pct === 0;
  const colorClasses = flat
    ? "bg-slate-100 text-slate-600"
    : positive
    ? "bg-market-up/10 text-[#008f70]"
    : "bg-market-down/10 text-market-down";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${colorClasses}`}>
      {!flat && (positive ? "▲" : "▼")} {formatPct(pct)}
      <span className="text-[10px] font-normal opacity-70">{label}</span>
    </span>
  );
}

export default function SignalCard({ signal, onRemove, onViewGraph, onUpdateQuantity }) {
  const isCrypto = signal.asset_class === "crypto";
  const hasBaseline = signal.change_since_last_visit_pct !== null;
  const [quantity, setQuantity] = useState(signal.quantity ?? "");
  const [editingQuantity, setEditingQuantity] = useState(false);
  const [savingQuantity, setSavingQuantity] = useState(false);

  async function saveQuantity() {
    const nextQuantity = quantity === "" ? null : Number(quantity);
    if (nextQuantity !== null && (!Number.isFinite(nextQuantity) || nextQuantity <= 0)) return;
    setSavingQuantity(true);
    try {
      await onUpdateQuantity(nextQuantity);
      setEditingQuantity(false);
    } finally {
      setSavingQuantity(false);
    }
  }

  return (
    <div
      className={`relative rounded-xl border border-borders bg-surface p-5 shadow-sm transition hover:border-slate-500 ${
        signal.is_meaningful ? "border-amber-300 ring-1 ring-amber-200" : ""
      }`}
    >
      {signal.is_meaningful && (
        <span className="absolute -top-2 left-4 rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-amber-800 shadow-sm">
          Worth a look
        </span>
      )}

      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-primary">{signal.symbol}</span>
            <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted">
              {isCrypto ? "Crypto" : "Stock"}
            </span>
            {signal.is_stale && (
              <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                Stale data
              </span>
            )}
          </div>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-primary">
            {isCrypto ? "$" : "$"}
            {formatPrice(signal.current_price, signal.asset_class)}
          </p>
          <p className="mt-1 text-xs text-muted">as of {formatTime(signal.as_of)} UTC</p>
        </div>

        <button
          onClick={(event) => {
            event.stopPropagation();
            onRemove();
          }}
          className="rounded-md px-1 text-lg leading-none text-slate-300 transition hover:bg-red-50 hover:text-market-down focus:outline-none focus:ring-2 focus:ring-slate-400"
          aria-label={`Remove ${signal.symbol}`}
          title="Remove from watchlist"
        >
          ✕
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {hasBaseline ? (
          <ChangePill pct={signal.change_since_last_visit_pct} label="since last visit" />
        ) : (
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-muted">
            First time viewing — building your baseline
          </span>
        )}
        {!isCrypto && <ChangePill pct={signal.relative_move_vs_index_pct} label="vs. SPY" />}
      </div>

      <div className="mt-4 border-t border-slate-100 pt-3 dark:border-slate-700">
        {editingQuantity ? (
          <div className="flex items-center gap-2">
            <input
              type="number"
              min="0"
              step="any"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              placeholder="Shares"
              className="min-w-0 flex-1 rounded-md border border-slate-300 bg-transparent px-2 py-1.5 text-xs text-primary outline-none focus:ring-2 focus:ring-slate-400"
              aria-label={`Quantity for ${signal.symbol}`}
            />
            <button onClick={saveQuantity} disabled={savingQuantity} className="text-xs font-semibold text-[#2878d4] disabled:opacity-50">
              {savingQuantity ? "Saving" : "Save"}
            </button>
            <button onClick={() => setEditingQuantity(false)} className="text-xs text-muted">Cancel</button>
          </div>
        ) : (
          <button
            onClick={() => setEditingQuantity(true)}
            className="text-xs text-muted transition hover:text-primary"
          >
            {signal.quantity ? `${signal.quantity} units` : "Add units for money impact"}
          </button>
        )}
        {signal.impact !== null && signal.impact !== undefined && (
          <p className={`mt-2 text-sm font-semibold ${signal.impact >= 0 ? "text-[#008f70]" : "text-market-down"}`}>
            {signal.impact >= 0 ? "+" : "-"}${Math.abs(signal.impact).toLocaleString(undefined, { maximumFractionDigits: 2 })} since last visit
          </p>
        )}
      </div>

      <button
        onClick={(event) => {
          event.stopPropagation();
          onViewGraph();
        }}
        className="mt-5 w-full rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-slate-500 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
      >
        View graph
      </button>
    </div>
  );
}
