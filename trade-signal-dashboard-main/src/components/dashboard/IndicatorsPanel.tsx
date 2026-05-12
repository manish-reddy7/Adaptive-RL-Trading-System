import { motion } from "framer-motion";
import type { Indicator } from "@/lib/schema";
import { statusBgClass, statusColorClass } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Props {
  indicators: Indicator[];
}

export function IndicatorsPanel({ indicators }: Props) {
  return (
    <section className="surface-card p-6">
      <PanelHeader title="Technical Indicators" subtitle="Normalised 0–1 with status" />
      <ul className="mt-4 space-y-3">
        {indicators.map((ind, i) => (
          <li key={ind.name} className="grid grid-cols-[80px_1fr_auto] items-center gap-3">
            <span className="font-mono text-sm font-medium text-foreground">{ind.name}</span>
            <div className="h-2 overflow-hidden rounded-full bg-secondary">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.max(2, ind.value * 100)}%` }}
                transition={{ duration: 0.7, delay: i * 0.04, ease: [0.16, 1, 0.3, 1] }}
                className={cn("h-full rounded-full", statusBgClass(ind.status))}
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground tabular-nums">
                {ind.value.toFixed(2)}
              </span>
              <span className={cn("min-w-[52px] text-right text-[11px] font-semibold uppercase tracking-wider", statusColorClass(ind.status))}>
                {ind.status}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function PanelHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <h3 className="font-display text-lg font-semibold text-foreground">{title}</h3>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
