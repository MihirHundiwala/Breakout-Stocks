export function tradingViewUrl(exchange: string, tradingSymbol: string): string {
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(`${exchange}:${tradingSymbol}`)}`;
}
