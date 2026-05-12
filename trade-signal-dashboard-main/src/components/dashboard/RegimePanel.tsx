import type { Analysis } from "@/lib/schema";
import { NiftyLineChart } from "@/components/charts/NiftyLineChart";
import { RegimeDonut } from "@/components/charts/RegimeDonut";
import { PanelHeader } from "./IndicatorsPanel";

interface Props {
  regime: Analysis["market_regime"];
}

export function RegimePanel({ regime }: Props) {
  return (
    <section className="surface-card p-6">
      <PanelHeader title="Market Regime" subtitle="Nifty 50 trajectory · regime distribution" />
      <div className="mt-4">
        <NiftyLineChart data={regime.nifty_data} />
      </div>
      <div className="mt-5 grid grid-cols-1 items-center gap-4 border-t border-border/60 pt-5 sm:grid-cols-[auto_1fr]">
        <div className="flex justify-center">
          <RegimeDonut bull={regime.bull_pct} sideways={regime.sideways_pct} bear={regime.bear_pct} />
        </div>
        <ul className="space-y-2">
          <RegimeRow label="Bullish" pct={regime.bull_pct} dotClass="bg-chart-bull" />
          <RegimeRow label="Sideways" pct={regime.sideways_pct} dotClass="bg-chart-sideways" />
          <RegimeRow label="Bearish" pct={regime.bear_pct} dotClass="bg-chart-bear" />
        </ul>
      </div>
    </section>
  );
}

function RegimeRow({ label, pct, dotClass }: { label: string; pct: number; dotClass: string }) {
  return (
    <li className="flex items-center justify-between rounded-lg border border-border/60 bg-surface-2 px-3 py-2">
      <span className="flex items-center gap-2 text-sm font-medium text-foreground">
        <span className={`h-2.5 w-2.5 rounded-full ${dotClass}`} />
        {label}
      </span>
      <span className="font-mono text-sm font-semibold tabular-nums text-foreground">
        {pct.toFixed(1)}%
      </span>
    </li>
  );
}
