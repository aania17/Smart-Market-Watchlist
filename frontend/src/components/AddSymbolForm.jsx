import { useState } from "react";

export default function AddSymbolForm({ onAdd }) {
  const [symbol, setSymbol] = useState("");
  const [assetClass, setAssetClass] = useState("stock");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmed = symbol.trim();
    if (!trimmed) return;
    setError("");
    if (assetClass === "stock" && !/^[A-Z0-9]+(?:[.-][A-Z0-9]+)*$/i.test(trimmed)) {
      setError("Use a stock ticker such as AAPL, not a crypto pair.");
      return;
    }
    if (assetClass === "crypto" && !/^[A-Z0-9]+\/[A-Z0-9]+$/i.test(trimmed)) {
      setError("Use a crypto pair in BASE/QUOTE format, such as BTC/USD.");
      return;
    }
    setBusy(true);
    try {
      await onAdd(trimmed, assetClass);
      setSymbol("");
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't add that symbol");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3 border-b border-[#dce5df] bg-white px-5 py-4">
      <div className="min-w-[180px] flex-1">
        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Add instrument</label>
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder={assetClass === "crypto" ? "e.g. BTC/USD" : "e.g. AAPL"}
          className="w-full rounded-lg border border-borders bg-surface px-3 py-2.5 text-sm text-primary outline-none transition placeholder:text-muted focus:border-slate-400 focus:ring-2 focus:ring-slate-400"
        />
      </div>
      <div>
        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Asset</label>
        <select
          value={assetClass}
          onChange={(e) => setAssetClass(e.target.value)}
          className="rounded-lg border border-borders bg-surface px-3 py-2.5 text-sm text-primary outline-none focus:border-slate-400 focus:ring-2 focus:ring-slate-400"
        >
          <option value="stock">Stock</option>
          <option value="crypto">Crypto</option>
        </select>
      </div>
      <button
        type="submit"
        disabled={busy}
        className="rounded-lg bg-[#2878d4] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#215ea8] focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50"
      >
        {busy ? "Adding..." : "Add to list"}
      </button>
      {error && <p className="w-full text-xs font-medium text-[#c85151]">{error}</p>}
    </form>
  );
}
