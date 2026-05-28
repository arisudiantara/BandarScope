/**
 * API client for BandarScope backend.
 */
const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE_URL}/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

// ---------- Symbols ----------
export const symbolsApi = {
  list: (params: { sector?: string; search?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.sector) qs.set("sector", params.sector);
    if (params.search) qs.set("search", params.search);
    return request<SymbolListItem[]>(`/symbols?${qs.toString()}`);
  },
  get: (code: string) => request<SymbolDetail>(`/symbols/${code}`),
  candles: (code: string, days = 120) =>
    request<Candle[]>(`/symbols/${code}/candles?days=${days}`),
  sectors: () => request<SectorMeta[]>(`/symbols/sectors/list`),
};

// ---------- Screener ----------
export interface ScreenerParams {
  bandar_score_min?: number;
  bandar_score_max?: number;
  foreign_net_min?: number;
  foreign_net_days?: number;
  inventory_score_min?: number;
  momentum_score_min?: number;
  volume_anomaly_min?: number;
  smart_money_signal?: string;
  sector?: string;
  price_min?: number;
  price_max?: number;
  sort_by?: string;
  sort_desc?: boolean;
  limit?: number;
}

export const screenerApi = {
  scan: (params: ScreenerParams = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        qs.set(k, String(v));
      }
    });
    return request<ScreenerResponse>(`/screener?${qs.toString()}`);
  },
  presets: () => request<ScreenerPreset[]>(`/screener/presets`),
};

// ---------- Broker / Inventory ----------
export const brokerApi = {
  inventory: (symbol: string, days = 60, top_n = 5) =>
    request<InventoryResponse>(
      `/broker/inventory/${symbol}?days=${days}&top_n=${top_n}`
    ),
  topAccumulators: (symbol: string, days = 30, limit = 20) =>
    request<TopAccumulator[]>(
      `/broker/top-accumulators/${symbol}?days=${days}&limit=${limit}`
    ),
  doneDetail: (symbol: string, days = 5) =>
    request<DoneDetailResponse>(`/broker/done-detail/${symbol}?days=${days}`),
};

// ---------- Foreign / Transaction / Balance ----------
export const flowApi = {
  foreign: (symbol: string, days = 90) =>
    request<ForeignFlowResponse>(`/foreign/${symbol}?days=${days}`),
  transaction: (symbol: string, days = 120) =>
    request<TransactionResponse>(`/transaction/${symbol}?days=${days}`),
  balance: (symbol: string, days = 90) =>
    request<BalanceResponse>(`/balance/${symbol}?days=${days}`),
};

// ---------- Sectors ----------
export const sectorApi = {
  activity: (days = 5) => request<SectorActivity[]>(`/sectors/activity?days=${days}`),
  rotation: (period_days = 30) =>
    request<RotationResponse>(`/sectors/rotation?period_days=${period_days}`),
  heatmap: () => request<HeatmapItem[]>(`/sectors/heatmap`),
};

// ---------- Watchlist ----------
export const watchlistApi = {
  list: () => request<Watchlist[]>(`/watchlists`),
  create: (data: { name: string; symbols: string[]; color?: string }) =>
    request<Watchlist>(`/watchlists`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: string, data: Partial<Watchlist>) =>
    request<Watchlist>(`/watchlists/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/watchlists/${id}`, { method: "DELETE" }),
};

// ============================================================
// Types
// ============================================================
export interface SymbolListItem {
  code: string;
  name: string;
  sector: string;
  board: string;
  market_cap: number;
  free_float_pct: number;
}

export interface SymbolDetail {
  code: string;
  name: string;
  sector: string;
  board: string;
  market_cap: number;
  shares_listed: number;
  free_float_pct: number;
  listing_date: string | null;
  latest: {
    date: string | null;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    volume: number | null;
    value: number | null;
    pct_change: number;
  };
  score: {
    bandar_score: number;
    foreign_score: number;
    inventory_score: number;
    volume_score: number;
    momentum_score: number;
    consistency_score: number;
    smart_money_signal: string;
    behavior_label: string;
    multi_tf_strength: number;
  } | null;
}

export interface Candle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  value: number;
  frequency: number;
}

export interface SectorMeta {
  code: string;
  name: string;
  name_id: string;
  color: string;
}

export interface ScreenerRow {
  symbol: string;
  name: string;
  sector: string;
  close: number;
  volume: number;
  value: number;
  volume_anomaly: number;
  foreign_net: number;
  bandar_score: number;
  foreign_score: number;
  inventory_score: number;
  volume_score: number;
  momentum_score: number;
  consistency_score: number;
  smart_money_signal: string;
  behavior_label: string;
  multi_tf_strength: number;
}

export interface ScreenerResponse {
  count: number;
  as_of: string;
  filter: ScreenerParams;
  results: ScreenerRow[];
}

export interface ScreenerPreset {
  id: string;
  name: string;
  description: string;
  filters: ScreenerParams;
}

export interface InventoryLine {
  broker_code: string;
  broker_name: string;
  broker_type: string;
  cluster_label: string;
  total_net_lot: number;
  total_net_value: number;
  data: Array<{
    date: string;
    inventory_lot: number;
    inventory_value: number;
    daily_net_lot: number;
  }>;
}

export interface InventoryResponse {
  symbol: string;
  period_days: number;
  lines: InventoryLine[];
  price_series: Array<{ date: string; close: number; volume: number }>;
  stealth_accumulation: {
    detected: boolean;
    price_change_pct?: number;
    accumulator_count?: number;
    total_lots_accumulated?: number;
    interpretation: string;
  };
}

export interface TopAccumulator {
  broker_code: string;
  broker_name: string;
  broker_type: string;
  cluster_label: string;
  is_foreign: boolean;
  buy_lot: number;
  sell_lot: number;
  net_lot: number;
  buy_value: number;
  sell_value: number;
  net_value: number;
  avg_buy_price: number;
  active_days: number;
  consistency_score: number;
  behavior_label: string;
}

export interface DoneDetailResponse {
  symbol: string;
  period_days: number;
  brokers: Array<{
    broker_code: string;
    broker_name: string;
    cluster: string;
    is_foreign: boolean;
    buy_value: number;
    sell_value: number;
    net_value: number;
  }>;
}

export interface ForeignFlowResponse {
  symbol: string;
  period_days: number;
  data: Array<{
    date: string;
    buy: number;
    sell: number;
    net: number;
    cumulative: number;
    price: number;
  }>;
  summary: {
    net_total: number;
    buy_total: number;
    sell_total: number;
    net_5d: number;
    net_20d: number;
    buy_days: number;
    sell_days: number;
    divergence: {
      type: string | null;
      strength: number;
      price_change_pct: number;
      flow_normalized: number;
      interpretation: string;
    };
  };
}

export interface TransactionResponse {
  symbol: string;
  period_days: number;
  data: Array<{
    date: string;
    price: number;
    buy: number;
    sell: number;
    net: number;
    cum_foreign: number;
    mfi: number;
  }>;
  divergence_markers: Array<{
    date: string;
    type: string;
    price: number;
  }>;
  hidden_accumulation: {
    detected: boolean;
    price_range_pct?: number;
    cum_foreign_growth?: number;
    interpretation: string;
  };
}

export interface BalanceResponse {
  symbol: string;
  period_days: number;
  data: Array<Record<string, any>>;
  summary: Record<
    string,
    {
      buy_value: number;
      sell_value: number;
      net_value: number;
      buy_pct: number;
      sell_pct: number;
    }
  >;
}

export interface SectorActivity {
  code: string;
  name: string;
  name_id: string;
  color: string;
  symbol_count: number;
  total_value: number;
  foreign_net: number;
  foreign_net_5d: number;
  momentum_pct: number;
  avg_bandar_score: number;
  avg_momentum_score: number;
  flow_label: string;
  rank: number;
}

export interface RotationResponse {
  as_of: string;
  period_days: number;
  benchmark: string;
  data: Array<{
    code: string;
    name: string;
    color: string;
    rs_ratio: number;
    rs_momentum: number;
    quadrant: "leading" | "improving" | "weakening" | "lagging";
    tail: number[][];
  }>;
}

export interface HeatmapItem {
  symbol: string;
  name: string;
  sector: string;
  close: number;
  pct_change: number;
  value: number;
  volume: number;
  bandar_score: number;
  smart_money_signal: string;
}

export interface Watchlist {
  id: string;
  name: string;
  description?: string;
  symbols: string[];
  color: string;
}
