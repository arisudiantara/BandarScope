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
  // NEW
  verdict?: string;
  retail_non_flow_min?: number;
  retail_non_flow_label?: string;
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

// ---------- Verdict ----------
export interface VerdictDetail {
  symbol: string;
  as_of: string;
  verdict: "GREEN_CHECK" | "ORANGE_X" | "RED_MINUS";
  icon: string;
  color: string;
  confidence: number;
  explanation: string;
  slope_5d: number;
  slope_15d: number;
  slope_30d: number;
  r_squared_15d: number;
  consistency_pct: number;
  buy_days_15d: number;
  bandar_lot_growth_15d: number;
  retail_non_flow_score: number;
  retail_non_flow_label: "POSITIVE_NONFLOW" | "NEUTRAL" | "NEGATIVE_NONFLOW";
  retail_non_flow_explanation: string;
  retail_net_value_15d: number;
}

export const verdictApi = {
  get: (symbol: string) => request<VerdictDetail>(`/verdict/${symbol}`),
};

// ---------- Daily Brief ----------
export interface DailyBrief {
  as_of: string;
  generated_at: string;
  market_summary: {
    advance: number;
    decline: number;
    unchanged: number;
    advance_ratio: number;
    total_value: number;
    foreign_net: number;
    avg_change: number;
  };
  top_accumulation: any[];
  distribution_warnings: any[];
  sector_rotation: Record<string, any[]>;
  sector_capital_flow: any[];
  pattern_alerts: any[];
  stocks_to_watch: any[];
}

export const dailyBriefApi = {
  get: () => request<DailyBrief>(`/daily-brief`),
  markdown: () =>
    fetch(
      `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/daily-brief/markdown`
    ).then((r) => r.text()),
};

// ---------- Patterns ----------
export interface PatternInfo {
  code: string;
  name: string;
  name_id: string;
  category: string;
  description: string;
  playbook: string;
  win_rate_label: string;
}

export interface PatternResult {
  pattern: string;
  name: string;
  name_id: string;
  category: string;
  detected: boolean;
  confidence: number;
  evidence: Record<string, any>;
  interpretation: string;
  playbook: string;
}

export const patternsApi = {
  catalog: () => request<PatternInfo[]>(`/patterns/catalog`),
  detect: (symbol: string, lookback = 60) =>
    request<{
      symbol: string;
      as_of: string;
      lookback_days: number;
      patterns: PatternResult[];
    }>(`/patterns/detect/${symbol}?lookback_days=${lookback}`),
  scan: (pattern_code: string, min_confidence = 60, limit = 50) =>
    request<{
      pattern_code: string;
      total_hits: number;
      results: Array<{
        symbol: string;
        name: string;
        sector: string;
        confidence: number;
        evidence: any;
      }>;
    }>(
      `/patterns/scan/${pattern_code}?min_confidence=${min_confidence}&limit=${limit}`
    ),
};

// ---------- Backtest ----------
export interface BacktestStrategy {
  min_foreign_score?: number;
  min_momentum_score?: number;
  min_volume_anomaly?: number;
  min_inventory_score?: number;
  min_composite_score?: number;
  sector?: string | null;
  hold_days?: number;
  max_positions?: number;
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
  rebalance_every_days?: number;
  initial_capital?: number;
  commission_pct?: number;
}

export interface BacktestResult {
  strategy: BacktestStrategy;
  period: { start: string; end: string };
  metrics: {
    total_trades: number;
    winners: number;
    losers: number;
    win_rate_pct: number;
    avg_return_pct: number;
    median_return_pct: number;
    best_trade_pct: number;
    worst_trade_pct: number;
    avg_win_pct: number;
    avg_loss_pct: number;
    profit_factor: number;
    sharpe_ratio: number;
    max_drawdown_pct: number;
    total_return_pct: number;
    exit_breakdown: Record<string, number>;
  };
  trades: Array<{
    symbol: string;
    entry_date: string;
    entry_price: number;
    exit_date: string;
    exit_price: number;
    return_pct: number;
    exit_reason: string;
    score_at_entry: number;
  }>;
  equity_curve: Array<{
    date: string;
    equity: number;
    trade_return_pct: number;
    symbol: string;
  }>;
  monthly_returns: Array<{ month: string; return_pct: number }>;
}

export const backtestApi = {
  presets: () =>
    request<
      Array<{
        id: string;
        name: string;
        description: string;
        spec: BacktestStrategy;
      }>
    >(`/backtest/presets`),
  run: (data: {
    strategy: BacktestStrategy;
    start_date?: string;
    end_date?: string;
  }) =>
    request<BacktestResult>(`/backtest/run`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  runPreset: (id: string, days = 365) =>
    request<BacktestResult>(`/backtest/run-preset/${id}?days=${days}`, {
      method: "POST",
    }),
};

// ---------- Yearly Heatmap ----------
export interface YearlyHeatmapSymbolData {
  symbol: string;
  months: Array<{
    month: string;
    trading_days: number;
    open: number;
    close: number;
    high: number;
    low: number;
    price_return_pct: number;
    avg_volume: number;
    total_value: number;
    foreign_net: number;
    bandar_net_lot: number;
    retail_net_lot: number;
    behavior_score: number;
    behavior_label: string;
  }>;
  summary: {
    avg_behavior_score: number;
    accumulation_months: number;
    distribution_months: number;
    best_month: { month: string; score: number; label: string };
    worst_month: { month: string; score: number; label: string };
    current_streak: { type: string; length: number };
    cumulative_foreign_net: number;
    cumulative_bandar_lot: number;
  };
}

export interface YearlyHeatmapUniverse {
  months: string[];
  month_count: number;
  symbol_count: number;
  matrix: Array<{
    symbol: string;
    name: string;
    sector: string;
    avg_score: number;
    cells: Array<{ month: string; score: number; label: string }>;
  }>;
}

export const yearlyHeatmapApi = {
  perSymbol: (symbol: string, months = 12) =>
    request<YearlyHeatmapSymbolData>(
      `/yearly-heatmap/symbol/${symbol}?months=${months}`
    ),
  universe: (months = 12, top_n = 30) =>
    request<YearlyHeatmapUniverse>(
      `/yearly-heatmap/universe?months=${months}&top_n=${top_n}`
    ),
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
  // NEW: verdict + retail non-flow
  verdict: "GREEN_CHECK" | "ORANGE_X" | "RED_MINUS";
  verdict_explanation: string;
  slope_15d: number;
  r_squared_15d: number;
  consistency_pct: number;
  retail_non_flow_score: number;
  retail_non_flow_label: "POSITIVE_NONFLOW" | "NEUTRAL" | "NEGATIVE_NONFLOW";
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
