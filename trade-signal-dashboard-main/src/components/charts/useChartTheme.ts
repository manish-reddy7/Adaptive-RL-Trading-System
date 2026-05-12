import { useEffect, useState } from "react";

/**
 * Reads CSS variable values (HSL triples like "190 95% 55%") so Chart.js
 * can be styled from the same design tokens as the rest of the app.
 * Re-reads on theme change.
 */
export function useChartTheme() {
  const [tokens, setTokens] = useState(() => readTokens());

  useEffect(() => {
    const obs = new MutationObserver(() => setTokens(readTokens()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);

  return tokens;
}

function hsl(varName: string, alpha = 1) {
  if (typeof window === "undefined") return "";
  const v = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  return alpha === 1 ? `hsl(${v})` : `hsl(${v} / ${alpha})`;
}

function readTokens() {
  return {
    grid: hsl("--chart-grid", 0.6),
    axis: hsl("--chart-axis"),
    bull: hsl("--chart-bull"),
    bear: hsl("--chart-bear"),
    sideways: hsl("--chart-sideways"),
    primary: hsl("--primary"),
    primaryGlow: hsl("--primary-glow"),
    primaryFill: hsl("--primary", 0.18),
    surface: hsl("--surface-1"),
    foreground: hsl("--foreground"),
    muted: hsl("--muted-foreground"),
    border: hsl("--border"),
  };
}
