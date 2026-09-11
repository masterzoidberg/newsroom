import { formatDate, shortId } from "../lib/api";
import type { Claim, ClaimEvidence, StoryEvidenceResponse } from "../lib/types";
import { Badge, EmptyState } from "./ViewPrimitives";

type EvidenceViewProps = {
  ledger: StoryEvidenceResponse;
  selectedClaimId?: string;
  dependencyGroupCount?: number;
  onSelectClaim?: (claimId: string) => void;
  onOpenEvidence?: (claim: Claim, evidence: ClaimEvidence) => void;
};

function relationshipLabel(relationship: ClaimEvidence["relationship"]): string {
  return relationship === "supports"
    ? "Supports"
    : relationship === "contradicts"
      ? "Contradicts"
      : "Contextualizes";
}

function claimLabel(claim: Claim): { label: string; tone: "mint" | "amber" | "coral" | "neutral" } {
  if (claim.accepted) return { label: "Accepted for synthesis", tone: "mint" };
  if (claim.state === "pending") return { label: "Pending review · not verified", tone: "amber" };
  if (claim.state === "superseded") return { label: "Superseded · historical only", tone: "neutral" };
  if (claim.state === "disputed") return { label: "Disputed · not verified", tone: "coral" };
  if (claim.state === "unsubstantiated") return { label: "Unsubstantiated · not verified", tone: "coral" };
  return { label: `${claim.state} · not verified`, tone: "coral" };
}

export function EvidenceView({ ledger, selectedClaimId, dependencyGroupCount, onSelectClaim, onOpenEvidence }: EvidenceViewProps) {
  if (ledger.claims.length === 0) return <EmptyState title="No current Claims" description="This Story has no current Claims. No factual statement is treated as verified." />;

  return <>
    {dependencyGroupCount !== undefined && <p className="status-note" role="status">Corroboration records {dependencyGroupCount} known source-dependency group{dependencyGroupCount === 1 ? "" : "s"}; multiple sources do not automatically mean independent confirmation.</p>}
    <div className="claim-list" role="list" aria-label="Story claims">
      {ledger.claims.map((claim) => {
        const status = claimLabel(claim);
        return <article className={`claim-card ${selectedClaimId === claim.id ? "claim-card-selected" : ""}`} id={`claim-${claim.id}`} key={claim.id} role="listitem" aria-label={`Claim ${claim.proposition}`}>
          <div className="claim-header">
            <span><Badge tone={status.tone}>{status.label}</Badge><small>{claim.importance} importance</small></span>
            <code>{shortId(claim.id)}</code>
          </div>
          <div className="claim-title-row"><h3>{claim.proposition}</h3>{onSelectClaim && <button className="quiet-button" type="button" onClick={() => onSelectClaim(claim.id)} aria-pressed={selectedClaimId === claim.id}>{selectedClaimId === claim.id ? "Selected Claim" : "Select Claim"}</button>}</div>
          <p className="claim-provenance">{status.label}{claim.accepted_at ? ` · accepted ${formatDate(claim.accepted_at)}` : ""}{claim.provenance.origin === "manual" ? " · manual provenance; automated verification identity unavailable" : ""}</p>
          {(claim.provenance.article_analysis_id || claim.provenance.promotion_identity) && <p className="claim-provenance">Analysis {shortId(claim.provenance.article_analysis_id)} · promotion {shortId(claim.provenance.promotion_identity)}{claim.provenance.candidate_claim_index !== null ? ` · candidate ${claim.provenance.candidate_claim_index}` : ""}</p>}
          {claim.evidence.length ? <ul className="evidence-list">{claim.evidence.map((item) => <li key={item.id} className={`evidence-item relationship-${item.relationship}`}>
            <div className="evidence-item-header"><strong>{relationshipLabel(item.relationship)}</strong><span>{item.source.name} · DocumentVersion {shortId(item.document_version.id)}</span></div>
            <blockquote>{item.excerpt}</blockquote>
            <p className="evidence-provenance">{item.document.title} · {item.locator_type ?? "document"}: {item.locator_value ?? "exact span"} · retrieved {item.document_version.retrieved_at ? new Date(item.document_version.retrieved_at).toLocaleString() : "—"}</p>
            <div className="button-row"><a className="quiet-button" href={item.document.canonical_url} target="_blank" rel="noreferrer">Open source</a>{onOpenEvidence && <button className="secondary-button" type="button" onClick={() => onOpenEvidence(claim, item)}>Inspect exact DocumentVersion</button>}</div>
          </li>)}</ul> : <p className="muted">No EvidenceSpan is linked; this Claim cannot be source-verified.</p>}
        </article>;
      })}
    </div>
  </>;
}
