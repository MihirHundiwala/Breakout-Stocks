const priceFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const signedPercentFormatter = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "always",
});

const analysisDateFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});


export function formatPrice(value: string | null): string {
  if (value === null) {
    return "—";
  }

  return priceFormatter.format(Number(value));
}

export function formatSignedPercentage(value: string | null): string {
  if (value === null) return "—";
  return `${signedPercentFormatter.format(Number(value))}%`;
}

export function formatAnalysisDate(value: string | null): string {
  if (value === null) return "—";
  const [year, month, day] = value.split("-").map(Number);

  return analysisDateFormatter.format(
    new Date(Date.UTC(year, month - 1, day)),
  );
}

export function movementClassName(value: string | null): string {
  if (value === null) return "text-slate-600";
  const numericValue = Number(value);

  if (numericValue > 0) {
    return "text-emerald-700";
  }

  if (numericValue < 0) {
    return "text-red-700";
  }

  return "text-slate-600";
}
