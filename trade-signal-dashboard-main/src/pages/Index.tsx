import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/dashboard/Header";
import { SignalHero } from "@/components/dashboard/SignalHero";
import { ScoreCard } from "@/components/dashboard/ScoreCard";
import { IndicatorsPanel } from "@/components/dashboard/IndicatorsPanel";
import { SentimentPanel } from "@/components/dashboard/SentimentPanel";
import { RegimePanel } from "@/components/dashboard/RegimePanel";
import { BacktestPanel } from "@/components/dashboard/BacktestPanel";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { useAnalysis } from "@/hooks/useAnalysis";
import { isUsingMock } from "@/lib/api";
import { NIFTY_TICKERS } from "@/lib/constants";

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] as const },
  }),
};

export default function Index() {
  const [ticker, setTicker] = useState<string>(NIFTY_TICKERS[5].ticker); // Kotak default
  const queryClient = useQueryClient();
  const { data, isLoading, isFetching, error, dataUpdatedAt, refetch } = useAnalysis(ticker);
  const lastErrorRef = useRef<string | null>(null);
  const mockToastShown = useRef(false);

  useEffect(() => {
    if (error) {
      const msg = (error as Error).message;
      if (lastErrorRef.current !== msg) {
        lastErrorRef.current = msg;
        toast.error("Could not load analysis", { description: msg });
      }
    } else {
      lastErrorRef.current = null;
    }
  }, [error]);

  useEffect(() => {
    if (isUsingMock && !mockToastShown.current) {
      mockToastShown.current = true;
      toast("Demo mode", {
        description: "Set VITE_API_BASE_URL to connect your Python API.",
      });
    }
  }, []);

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["analysis", ticker] });
    refetch();
  };

  const lastUpdated = useMemo(
    () => (dataUpdatedAt ? new Date(dataUpdatedAt) : undefined),
    [dataUpdatedAt]
  );

  return (
    <div className="min-h-screen">
      <Header
        ticker={ticker}
        onTickerChange={setTicker}
        onRefresh={handleRefresh}
        isFetching={isFetching}
        lastUpdated={lastUpdated}
        hasError={!!error && !data}
      />

      <main className="container py-6 md:py-8">
        {isLoading || !data ? (
          <DashboardSkeleton />
        ) : (
          <motion.div
            key={ticker}
            initial="hidden"
            animate="show"
            variants={{ show: { transition: { staggerChildren: 0.04 } } }}
            className="space-y-5"
          >
            <motion.div custom={0} variants={fadeUp}>
              <SignalHero
                signal={data.signal}
                actionValue={data.action_value}
                ticker={data.ticker}
                name={data.name}
              />
            </motion.div>

            <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
              <motion.div custom={1} variants={fadeUp}>
                <ScoreCard label="Technical Score" score={data.technical_score} description="Price-action and indicator confluence" />
              </motion.div>
              <motion.div custom={2} variants={fadeUp}>
                <ScoreCard label="Sentiment Score" score={data.sentiment_score} description="News + headline polarity" />
              </motion.div>
              <motion.div custom={3} variants={fadeUp}>
                <ScoreCard label="Regime Score" score={data.regime_score} description="Macro market context" />
              </motion.div>
            </div>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <motion.div custom={4} variants={fadeUp}>
                <IndicatorsPanel indicators={data.indicators} />
              </motion.div>
              <motion.div custom={5} variants={fadeUp}>
                <SentimentPanel
                  dates={data.sentiment_chart.dates}
                  scores={data.sentiment_chart.scores}
                  headlines={data.headlines}
                />
              </motion.div>
              <motion.div custom={6} variants={fadeUp}>
                <RegimePanel regime={data.market_regime} />
              </motion.div>
            </div>

            <motion.div custom={7} variants={fadeUp}>
              <BacktestPanel backtest={data.backtest} />
            </motion.div>
          </motion.div>
        )}
      </main>

      <footer className="container py-8 text-center text-xs text-muted-foreground">
        Recommendations are model outputs, not financial advice. Auto-refreshes every 5 minutes.
      </footer>
    </div>
  );
}
