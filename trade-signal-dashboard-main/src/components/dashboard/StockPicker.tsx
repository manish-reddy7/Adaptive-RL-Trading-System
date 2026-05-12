import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { NIFTY_TICKERS } from "@/lib/constants";

interface Props {
  value: string;
  onChange: (v: string) => void;
}

export function StockPicker({ value, onChange }: Props) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-[230px]" aria-label="Select Nifty 50 stock">
        <SelectValue placeholder="Select stock" />
      </SelectTrigger>
      <SelectContent>
        {NIFTY_TICKERS.map((s) => (
          <SelectItem key={s.ticker} value={s.ticker}>
            <span className="flex items-center justify-between gap-3 w-full">
              <span className="font-medium">{s.name}</span>
              <span className="font-mono text-xs text-muted-foreground">
                {s.ticker.replace(".NS", "")}
              </span>
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
