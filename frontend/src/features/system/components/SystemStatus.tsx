import { useReadiness } from "../hooks/useReadiness";


export function SystemStatus() {
  const readinessQuery = useReadiness();

  if (readinessQuery.isPending) {
    return (
      <section
        className="system-status system-status--checking"
        aria-live="polite"
      >
        <span
          className="system-status__indicator"
          aria-hidden="true"
        />
        <div>
          <h2>Checking market research</h2>
          <p>Confirming that the latest research is available…</p>
        </div>
      </section>
    );
  }

  if (readinessQuery.isError) {
    return (
      <section
        className="system-status system-status--unavailable"
        role="alert"
      >
        <span
          className="system-status__indicator"
          aria-hidden="true"
        />
        <div>
          <h2>Market research is temporarily unavailable</h2>
          <p>The latest research could not be reached. Please try again shortly.</p>
        </div>
      </section>
    );
  }

  const isReady =
    readinessQuery.data.status === "ready" &&
    readinessQuery.data.database === "ok";

  if (!isReady) {
    return (
      <section
        className="system-status system-status--unavailable"
        role="alert"
      >
        <span
          className="system-status__indicator"
          aria-hidden="true"
        />
        <div>
          <h2>Market research is temporarily unavailable</h2>
          <p>The latest saved market information cannot be reached yet.</p>
        </div>
      </section>
    );
  }

  return (
    <section
      className="system-status system-status--ready"
      aria-live="polite"
    >
      <span
        className="system-status__indicator"
        aria-hidden="true"
      />
      <div>
        <h2>Market research is available</h2>
        <p>The latest saved results are ready to view.</p>
      </div>

      {readinessQuery.isFetching && (
        <span className="system-status__refresh">
          Checking for updates…
        </span>
      )}
    </section>
  );
}
