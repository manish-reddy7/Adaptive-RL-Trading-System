import type { Analysis } from "@/lib/schema";
import { PanelHeader } from "./IndicatorsPanel";
import { cn } from "@/lib/utils";

interface Props {
  backtest: Analysis["backtest"];
}

export function BacktestPanel({ backtest: b }: Props) {
  const items = [
    { label: "Sharpe Ratio", value: b.sharpe.toFixed(2), good: b.sharpe >= 1 },
    { label: "Sortino Ratio", value: b.sortino.toFixed(2), good: b.sortino >= 1 },
    { label: "Win Rate", value: `${b.win_rate.toFixed(1)}%`, good: b.win_rate >= 50 },
    { label: "Cumulative Return", value: `${b.cum_ret >= 0 ? "+" : ""}${b.cum_ret.toFixed(2)}%`, good: b.cum_ret >= 0 },
    { label: "Annual Return", value: `${b.ann_ret >= 0 ? "+" : ""}${b.ann_ret.toFixed(2)}%`, good: b.ann_ret >= 0 },
    { label: "Max Drawdown", value: `${b.max_dd.toFixed(2)}%`, good: b.max_dd > -5 },
    { label: "BUY Precision", value: `${b.buy_precision.toFixed(1)}%`, good: b.buy_precision >= 50 },
    { label: "SELL Precision", value: `${b.sell_precision.toFixed(1)}%`, good: b.sell_precision >= 50 },
  ];

  return (
    <section className="surface-card p-6">
      <PanelHeader
        title="Backtest Performance"
        subtitle={b.period}
      />
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {items.map((m) => (
          <div key={m.label} className="rounded-xl border border-border/60 bg-surface-2 p-3">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
              {m.label}
            </div>
            <div className={cn(
              "mt-1 font-mono text-xl font-bold tabular-nums",
              m.good ? "text-status-strong" : "text-status-weak"
            )}>
              {m.value}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
