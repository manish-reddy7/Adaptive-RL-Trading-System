import { motion } from "framer-motion";
import { scoreStatus, statusBgClass, statusColorClass } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  score: number;
  description?: string;
}

export function ScoreCard({ label, score, description }: Props) {
  const status = scoreStatus(score);
  return (
    <div className="surface-card p-5">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">{label}</h3>
        <span className={cn("text-xs font-semibold uppercase tracking-wider", statusColorClass(status))}>
          {status}
        </span>
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="font-mono text-4xl font-bold text-foreground">{score}</span>
        <span className="text-sm text-muted-foreground">/ 100</span>
      </div>
      <div
        className="mt-4 h-2 w-full overflow-hidden rounded-full bg-secondary"
        role="progressbar"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label} ${score} of 100`}
      >
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score}%` }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          className={cn("h-full rounded-full", statusBgClass(status))}
        />
      </div>
      {description && (
        <p className="mt-3 text-xs text-muted-foreground">{description}</p>
      )}
    </div>
  );
}
