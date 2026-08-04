from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"


class TechnicalStatus(StrEnum):
    NO_SETUP = "NO_SETUP"
    CONSOLIDATING = "CONSOLIDATING"
    BREAKOUT = "BREAKOUT"
    EARLY_RECOVERY_BREAKOUT = "EARLY_RECOVERY_BREAKOUT"
    WEAK_BREAKOUT = "WEAK_BREAKOUT"
    BREAKOUT_HOLDING = "BREAKOUT_HOLDING"
    RETEST = "RETEST"
    # Retained so historical technical-v1 through technical-v4 rows remain readable.
    FORMING = "FORMING"
    READY = "READY"
    FAILED_BREAKOUT = "FAILED_BREAKOUT"
    SETUP_FOUND = "SETUP_FOUND"


class FundamentalCoverageStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"


class TrackingOperationalState(StrEnum):
    PREPARING = "PREPARING"
    READY = "READY"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"


class FundamentalPeriodKind(StrEnum):
    YEARLY = "YEARLY"
    QUARTERLY = "QUARTERLY"


class StatementBasis(StrEnum):
    CONSOLIDATED = "CONSOLIDATED"
    STANDALONE = "STANDALONE"


class AnalysisJobType(StrEnum):
    ONBOARD_INSTRUMENT = "ONBOARD_INSTRUMENT"
    ANALYZE_INSTRUMENT = "ANALYZE_INSTRUMENT"
    REFRESH_FUNDAMENTALS = "REFRESH_FUNDAMENTALS"


class AnalysisJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TelegramNotificationStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
