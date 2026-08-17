import { FormEvent, useState } from "react";

type EvidenceItem = {
  id: string;
  relationship: "supports" | "contradicts" | "contextualizes";
  excerpt: string;
  locator_type: string | null;
  locator_value: string | null;
  document_version: {
    id: string;
    retrieved_at: string;
    content_hash: string;
  };
  document: {
    canonical_url: string;
    title: string;
  };
  source: {
    name: string;
    slug: string;
  };
};

type Claim = {
  id: string;
  proposition: string;
  importance: "major" | "relevant" | "peripheral";
  state: string;
  accepted: boolean;
  evidence: EvidenceItem[];
};

type EvidenceResponse = {
  claims: Claim[];
  revisions: Array<{
    id: string;
    revision_number: number;
    headline: string;
    claim_set_hash: string | null;
    claim_ids: string[];
  }>;
};

function relationshipLabel(relationship: EvidenceItem["relationship"]): string {
  return relationship === "supports"
    ? "Supports"
    : relationship === "contradicts"
      ? "Contradicts"
      : "Contextualizes";
}

export function EvidenceView() {
  const [storyId, setStoryId] = useState("");
  const [ledger, setLedger] = useState<EvidenceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const identifier = storyId.trim();
    if (!identifier) {
      setError("Enter a Story ID to inspect its evidence.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/v1/stories/${encodeURIComponent(identifier)}/evidence`);
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message ?? "Evidence could not be loaded.");
      setLedger(body as EvidenceResponse);
    } catch (caught) {
      setLedger(null);
      setError(caught instanceof Error ? caught.message : "Evidence could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="evidence-panel" aria-labelledby="evidence-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Evidence ledger</p>
          <h2 id="evidence-heading">Inspect why a Story says what it says.</h2>
        </div>
        <p className="section-note">Read-only view · exact spans · versioned provenance</p>
      </div>

      <form className="evidence-form" onSubmit={loadEvidence}>
        <label htmlFor="story-id">Story ID</label>
        <div className="evidence-form-row">
          <input
            id="story-id"
            name="story_id"
            value={storyId}
            onChange={(event) => setStoryId(event.target.value)}
            placeholder="st_…"
            autoComplete="off"
            spellCheck={false}
          />
          <button type="submit" disabled={loading}>
            {loading ? "Loading…" : "Inspect evidence"}
          </button>
        </div>
      </form>

      {error && <p className="evidence-message error" role="alert">{error}</p>}
      {!ledger && !error && (
        <p className="evidence-message" role="status">
          Load a Story to see accepted Claims, contradictions, and their exact source spans.
        </p>
      )}
      {ledger && ledger.claims.length === 0 && (
        <p className="evidence-message" role="status">This Story has no Claims yet.</p>
      )}
      {ledger && ledger.claims.length > 0 && (
        <div className="claim-list" role="list" aria-label="Story claims">
          {ledger.claims.map((claim) => (
            <article className="claim-card" key={claim.id} role="listitem">
              <div className="claim-header">
                <div>
                  <span className={`state-badge state-${claim.state}`}>{claim.state}</span>
                  <span className="importance-label">{claim.importance} importance</span>
                </div>
                <code>{claim.id}</code>
              </div>
              <h3>{claim.proposition}</h3>
              <p className="claim-meta">{claim.accepted ? "Accepted for synthesis" : "Not accepted for synthesis"}</p>
              {claim.evidence.length === 0 ? (
                <p className="claim-meta">No evidence linked.</p>
              ) : (
                <ul className="evidence-list">
                  {claim.evidence.map((item) => (
                    <li key={item.id} className={`evidence-item relationship-${item.relationship}`}>
                      <div className="evidence-item-header">
                        <strong>{relationshipLabel(item.relationship)}</strong>
                        <span>{item.source.name} · Version {item.document_version.id}</span>
                      </div>
                      <blockquote>{item.excerpt}</blockquote>
                      <p className="evidence-provenance">
                        {item.document.title} · {item.locator_type ?? "document"}: {item.locator_value ?? "exact span"}{" "}
                        <a href={item.document.canonical_url} target="_blank" rel="noreferrer">
                          Open source
                        </a>
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
