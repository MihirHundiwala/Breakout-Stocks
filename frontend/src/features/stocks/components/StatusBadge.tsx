import type {
  FundamentalCoverageStatus,
  TechnicalStatus,
  TrackingOperationalState,
} from "../types";


interface BadgeAppearance {
  label: string;
  className: string;
}

const technicalStatusAppearance: Record<
  TechnicalStatus,
  BadgeAppearance
> = {
  NO_SETUP: {
    label: "No setup",
    className:
      "bg-slate-100 text-slate-700 ring-slate-600/20",
  },
  CONSOLIDATING: {
    label: "Consolidating",
    className:
      "bg-sky-50 text-sky-700 ring-sky-600/20",
  },
  RETEST: {
    label: "Retest",
    className:
      "bg-violet-50 text-violet-700 ring-violet-600/20",
  },
  FORMING: {
    label: "Forming",
    className:
      "bg-sky-50 text-sky-700 ring-sky-600/20",
  },
  READY: {
    label: "Breakout ready",
    className:
      "bg-amber-50 text-amber-800 ring-amber-600/20",
  },
  BREAKOUT: {
    label: "Breakout",
    className:
      "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  },
  EARLY_RECOVERY_BREAKOUT: {
    label: "Early recovery",
    className:
      "bg-teal-50 text-teal-800 ring-teal-600/20",
  },
  WEAK_BREAKOUT: {
    label: "Weak breakout",
    className:
      "bg-orange-50 text-orange-800 ring-orange-600/20",
  },
  BREAKOUT_HOLDING: {
    label: "Breakout holding",
    className:
      "bg-cyan-50 text-cyan-800 ring-cyan-600/20",
  },
  FAILED_BREAKOUT: {
    label: "Failed breakout",
    className:
      "bg-rose-50 text-rose-700 ring-rose-600/20",
  },
  SETUP_FOUND: {
    label: "Setup found",
    className:
      "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  },
};

const coverageAppearance: Record<
  FundamentalCoverageStatus,
  BadgeAppearance
> = {
  UNKNOWN: {
    label: "Coverage unknown",
    className:
      "bg-slate-100 text-slate-700 ring-slate-600/20",
  },
  PARTIAL: {
    label: "Partial coverage",
    className:
      "bg-blue-50 text-blue-700 ring-blue-600/20",
  },
  COMPLETE: {
    label: "Complete coverage",
    className:
      "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  },
};

function Badge({ appearance }: { appearance: BadgeAppearance }) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-full px-2.5 py-1",
        "text-xs font-semibold whitespace-nowrap ring-1 ring-inset",
        appearance.className,
      ].join(" ")}
    >
      {appearance.label}
    </span>
  );
}

export function TechnicalStatusBadge({
  status,
}: {
  status: TechnicalStatus;
}) {
  return <Badge appearance={technicalStatusAppearance[status]} />;
}

function operationalAppearance(
  state: TrackingOperationalState,
  errorCode: string | null,
): BadgeAppearance {
  if (state === "ANALYSIS_FAILED") {
    if (errorCode === "INSUFFICIENT_LISTING_HISTORY") {
      return {
        label: "Insufficient history",
        className: "bg-amber-50 text-amber-800 ring-amber-600/20",
      };
    }
    if (errorCode === "PERSISTENT_CANDLE_GAPS") {
      return {
        label: "Candle gaps",
        className: "bg-rose-50 text-rose-700 ring-rose-600/20",
      };
    }
    return {
      label: "Analysis failed",
      className: "bg-rose-50 text-rose-700 ring-rose-600/20",
    };
  }

  return {
    label: state === "PREPARING" ? "Analysis pending" : "Analysis unavailable",
    className: "bg-slate-100 text-slate-700 ring-slate-600/20",
  };
}

export function StockAnalysisStatusBadge({
  status,
  operationalState,
  errorCode,
}: {
  status: TechnicalStatus | null;
  operationalState: TrackingOperationalState;
  errorCode: string | null;
}) {
  if (operationalState === "ANALYSIS_FAILED" || status === null) {
    return (
      <Badge appearance={operationalAppearance(operationalState, errorCode)} />
    );
  }
  return <TechnicalStatusBadge status={status} />;
}

export function FundamentalCoverageBadge({
  status,
}: {
  status: FundamentalCoverageStatus;
}) {
  return <Badge appearance={coverageAppearance[status]} />;
}
