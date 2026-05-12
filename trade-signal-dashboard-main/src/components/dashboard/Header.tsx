import { useTheme } from "next-themes";
import { Moon, Sun, RefreshCw, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StockPicker } from "./StockPicker";
import { LiveStatus } from "./LiveStatus";
import { cn } from "@/lib/utils";

interface Props {
  ticker: string;
  onTickerChange: (t: string) => void;
  onRefresh: () => void;
  isFetching: boolean;
  lastUpdated?: Date;
  hasError?: boolean;
}

export function Header({ ticker, onTickerChange, onRefresh, isFetching, lastUpdated, hasError }: Props) {
  const { theme, setTheme } = useTheme();
  return (
    <header className="border-b border-border/60 bg-background/60 backdrop-blur-xl sticky top-0 z-40">
      <div className="container flex flex-col gap-4 py-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-primary shadow-elevated">
            <Activity className="h-5 w-5 text-primary-foreground" strokeWidth={2.5} />
          </div>
          <div>
            <h1 className="font-display text-xl font-bold leading-tight md:text-2xl">
              Nifty 50 PPO Dashboard
            </h1>
            <p className="text-xs text-muted-foreground md:text-sm">
              PPO Reinforcement Learning · Live Market Analysis
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 md:gap-3">
          <LiveStatus isFetching={isFetching} lastUpdated={lastUpdated} hasError={hasError} />
          <StockPicker value={ticker} onChange={onTickerChange} />
          <Button
            variant="outline"
            size="icon"
            onClick={onRefresh}
            disabled={isFetching}
            aria-label="Refresh analysis"
            className="shrink-0"
          >
            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label="Toggle theme"
            className="shrink-0"
          >
            <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          </Button>
        </div>
      </div>
    </header>
  );
}
