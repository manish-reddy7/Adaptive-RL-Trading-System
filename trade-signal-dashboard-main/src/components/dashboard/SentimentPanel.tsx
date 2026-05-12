import type { Headline } from "@/lib/schema";
import { SentimentBarChart } from "@/components/charts/SentimentBarChart";
import { PanelHeader } from "./IndicatorsPanel";
import { cn } from "@/lib/utils";

interface Props {
  dates: string[];
  scores: number[];
  headlines: Headline[];
}

const sentimentLabel = { pos: "Positive", neu: "Neutral", neg: "Negative" } as const;
const sentimentClass = {
  pos: "bg-status-strong/15 text-status-strong border-status-strong/30",
  neu: "bg-muted text-muted-foreground border-border",
  neg: "bg-status-weak/15 text-status-weak border-status-weak/30",
} as const;

export function SentimentPanel({ dates, scores, headlines }: Props) {
  return (
    <section className="surface-card p-6">
      <PanelHeader title="News Sentiment" subtitle="Last 14 days · headline polarity" />
      <div className="mt-4">
        <SentimentBarChart dates={dates} scores={scores} />
      </div>
      <div className="mt-5 border-t border-border/60 pt-4">
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Recent Headlines
        </h4>
        <ul className="space-y-2">
          {headlines.slice(0, 5).map((h, i) => (
            <li
              key={i}
              className="flex items-start gap-3 rounded-lg border border-border/60 bg-surface-2 px-3 py-2"
            >
              <span
                className={cn(
                  "mt-0.5 shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                  sentimentClass[h.sentiment]
                )}
              >
                {sentimentLabel[h.sentiment]}
              </span>
              <div className="min-w-0">
                <p className="text-sm leading-snug text-foreground">{h.text}</p>
                {h.source && (
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{h.source}</p>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
