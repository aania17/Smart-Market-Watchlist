import client from "./client";

export async function listWatchlists() {
  const res = await client.get("/watchlists");
  return res.data;
}

export async function createWatchlist(name) {
  const res = await client.post("/watchlists", { name });
  return res.data;
}

export async function deleteWatchlist(id) {
  await client.delete(`/watchlists/${id}`);
}

export async function addItem(watchlistId, symbol, assetClass) {
  const res = await client.post(`/watchlists/${watchlistId}/items`, {
    symbol,
    asset_class: assetClass,
  });
  return res.data;
}

export async function updateSensitivity(watchlistId, meaningfulThresholdPct) {
  const res = await client.patch(`/watchlists/${watchlistId}/sensitivity`, {
    meaningful_threshold_pct: meaningfulThresholdPct,
  });
  return res.data;
}

export async function updateQuantity(watchlistId, symbol, quantity) {
  const res = await client.patch(
    `/watchlists/${watchlistId}/items/quantity`,
    { quantity },
    { params: { symbol } }
  );
  return res.data;
}

export async function removeItem(watchlistId, symbol) {
  // symbol goes as a query param (not a path segment) because crypto pairs
  // like "BTC/USD" contain a slash that would break path routing.
  await client.delete(`/watchlists/${watchlistId}/items`, { params: { symbol } });
}

export async function viewWatchlist(watchlistId, updateBaseline = false) {
  const res = await client.get(`/watchlists/${watchlistId}/view`, {
    params: { update_baseline: updateBaseline },
  });
  return res.data;
}

export async function hourlyWatchlist(watchlistId) {
  const res = await client.get(`/watchlists/${watchlistId}/hourly`);
  return res.data;
}
