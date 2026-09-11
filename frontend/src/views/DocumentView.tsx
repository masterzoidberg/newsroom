import { FormEvent, useEffect, useState } from "react";
import { ApiError, apiFetch, formatDate, shortId } from "../lib/api";
import type { DocumentNavigationContext, DocumentRecord, DocumentVersion, EvidenceSpan } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard } from "../components/ViewPrimitives";

type Lineage = { items?: Array<Record<string, unknown>> };

export const DOCUMENT_NAVIGATION_KEY = "newsroom.document.inspect.v1";

export function queueDocumentNavigation(documentId: string, options: Omit<DocumentNavigationContext, "documentId"> = {}) {
  const identifier = documentId.trim();
  if (!identifier) return;
  try { window.sessionStorage.setItem(DOCUMENT_NAVIGATION_KEY, JSON.stringify({ documentId: identifier, ...options })); } catch { /* The document ID remains available from the Watch result. */ }
}

function readQueuedDocumentNavigation(): DocumentNavigationContext | null {
  try {
    const raw = window.sessionStorage.getItem(DOCUMENT_NAVIGATION_KEY);
    if (!raw) return null;
    if (!raw.trim().startsWith("{")) return { documentId: raw.trim() };
    const saved = JSON.parse(raw) as Partial<DocumentNavigationContext>;
    if (typeof saved.documentId !== "string" || !saved.documentId.trim()) return null;
    return {
      documentId: saved.documentId.trim(),
      ...(typeof saved.documentVersionId === "string" && saved.documentVersionId.trim() ? { documentVersionId: saved.documentVersionId.trim() } : {}),
      ...(typeof saved.evidenceSpanId === "string" && saved.evidenceSpanId.trim() ? { evidenceSpanId: saved.evidenceSpanId.trim() } : {}),
      ...(typeof saved.returnStoryId === "string" && saved.returnStoryId.trim() ? { returnStoryId: saved.returnStoryId.trim() } : {}),
      ...(typeof saved.returnClaimId === "string" && saved.returnClaimId.trim() ? { returnClaimId: saved.returnClaimId.trim() } : {}),
    };
  } catch { return null; }
}

export function DocumentView() {
  const [initialNavigation] = useState(readQueuedDocumentNavigation);
  const [documentId, setDocumentId] = useState(initialNavigation?.documentId ?? "");
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [spans, setSpans] = useState<EvidenceSpan[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState(initialNavigation?.documentVersionId ?? "");
  const [selectedSpanId, setSelectedSpanId] = useState(initialNavigation?.evidenceSpanId ?? "");
  const [returnContext, setReturnContext] = useState({ storyId: initialNavigation?.returnStoryId ?? "", claimId: initialNavigation?.returnClaimId ?? "" });
  const [targetError, setTargetError] = useState<string | null>(null);
  const [lineage, setLineage] = useState<Lineage | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  async function load(identifier: string, requestedVersionId = "", requestedSpanId = "", preserveReturnContext = true) {
    setLoading(true);
    setError(null);
    setTargetError(null);
    try {
      const encoded = encodeURIComponent(identifier);
      const [doc, versionResponse, lineageResponse, requestedVersion] = await Promise.all([
        apiFetch<DocumentRecord>(`/documents/${encoded}`),
        apiFetch<{ items: DocumentVersion[] }>(`/documents/${encoded}/versions`),
        apiFetch<Lineage>(`/documents/${encoded}/lineage`),
        requestedVersionId ? apiFetch<DocumentVersion>(`/document-versions/${encodeURIComponent(requestedVersionId)}`) : Promise.resolve(null),
      ]);
      if (requestedVersion && requestedVersion.document_id && requestedVersion.document_id !== doc.id) {
        throw new Error(`DocumentVersion ${shortId(requestedVersion.id)} does not belong to Document ${shortId(doc.id)}.`);
      }
      const selectedVersion = requestedVersion ?? versionResponse.items[0] ?? null;
      const nextVersions = selectedVersion && !versionResponse.items.some((version) => version.id === selectedVersion.id)
        ? [selectedVersion, ...versionResponse.items]
        : versionResponse.items;
      let nextSpans: EvidenceSpan[] = [];
      let nextSelectedSpanId = requestedSpanId;
      if (selectedVersion) {
        nextSpans = (await apiFetch<{ items: EvidenceSpan[] }>(`/document-versions/${encodeURIComponent(selectedVersion.id)}/evidence-spans`)).items;
        if (requestedSpanId && !nextSpans.some((span) => span.id === requestedSpanId)) {
          try {
            const requestedSpan = await apiFetch<EvidenceSpan>(`/evidence-spans/${encodeURIComponent(requestedSpanId)}`);
            const spanVersionId = requestedSpan.document_version_id ?? requestedSpan.document_version?.id;
            if (spanVersionId && spanVersionId !== selectedVersion.id) {
              setTargetError(`EvidenceSpan ${shortId(requestedSpanId)} belongs to DocumentVersion ${shortId(spanVersionId)}, not the requested version. The displayed version remains unverified for that stale span.`);
              nextSelectedSpanId = "";
            } else {
              nextSpans = [requestedSpan, ...nextSpans];
            }
          } catch (caught) {
            if (caught instanceof ApiError && caught.status === 404) {
              setTargetError(`EvidenceSpan ${shortId(requestedSpanId)} is unavailable. The exact source span may be stale or deleted; no replacement span is shown as verified.`);
              nextSelectedSpanId = "";
            } else throw caught;
          }
        }
      } else if (requestedSpanId) {
        setTargetError(`EvidenceSpan ${shortId(requestedSpanId)} cannot be inspected because this Document has no available versions.`);
        nextSelectedSpanId = "";
      }
      setDocument(doc);
      setVersions(nextVersions);
      setSelectedVersionId(selectedVersion?.id ?? "");
      setSelectedSpanId(nextSelectedSpanId);
      setDocumentId(identifier);
      const nextReturnContext = preserveReturnContext ? returnContext : { storyId: "", claimId: "" };
      setReturnContext(nextReturnContext);
      queueDocumentNavigation(identifier, {
        documentVersionId: selectedVersion?.id,
        evidenceSpanId: requestedSpanId || undefined,
        returnStoryId: nextReturnContext.storyId || undefined,
        returnClaimId: nextReturnContext.claimId || undefined,
      });
      setLineage(lineageResponse);
      setSpans(nextSpans);
    } catch (caught) {
      setDocument(null);
      setVersions([]);
      setSpans([]);
      setLineage(null);
      setError(caught instanceof ApiError && caught.status === 404
        ? new Error(`Document or DocumentVersion ${shortId(requestedVersionId || identifier)} is unavailable. The link may be stale or the record may have been deleted; no evidence is shown as verified.`)
        : caught);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (initialNavigation?.documentId) void load(initialNavigation.documentId, initialNavigation.documentVersionId ?? "", initialNavigation.evidenceSpanId ?? "");
  }, []);

  async function inspect(event: FormEvent) {
    event.preventDefault();
    const identifier = documentId.trim();
    if (!identifier) { setError(new Error("Enter a Document ID to inspect.")); return; }
    await load(identifier, "", "", false);
  }

  return <>
    <PageHeader eyebrow="Review / analysis" title="Documents" description="Analyze version history, exact Evidence Spans, and publication lineage without storing article bodies in the UI." action={returnContext.storyId ? <a className="secondary-button" href="#stories">Back to Claim {shortId(returnContext.claimId)}</a> : undefined} />
    <SectionCard title="Open a Document" description="Use the canonical Document ID from an evidence or Watch result. Deferred analysis opens here without inventing a Story.">
      <form className="inline-form" onSubmit={(event) => void inspect(event)}>
        <label htmlFor="document-id">Document ID</label>
        <input id="document-id" name="document_id" autoComplete="off" value={documentId} onChange={(event) => setDocumentId(event.target.value)} placeholder="doc_…" />
        <button className="primary-button" type="submit" disabled={loading}>{loading ? "Analyzing…" : "Analyze Document"}</button>
      </form>
    </SectionCard>
    {loading && <LoadingState label="Loading versions and spans" />}
    {error && <ErrorState error={error} />}
    {targetError && <p className="status-note" role="status">{targetError}</p>}
    {document && <>
      <section className="story-summary">
        <div><p className="eyebrow">Document analysis</p><h2>{document.title}</h2><p><a href={document.canonical_url} target="_blank" rel="noreferrer">{document.canonical_url}</a></p></div>
        <div className="story-summary-meta"><Badge tone="mint">{document.source_id}</Badge>{selectedVersionId && <Badge tone="amber">DocumentVersion target</Badge>}<span>First seen {formatDate(document.first_seen_at)}</span><span>Published {formatDate(document.published_at)}</span></div>
      </section>
      <div className="content-grid document-grid">
        <SectionCard title="Version history" description="Each retrieved version is immutable. The selected target is loaded directly when a Claim points to an older version.">{versions.length ? <div className="resource-list">{versions.map((version, index) => <button className={`resource-row ${version.id === selectedVersionId ? "selected" : ""}`} type="button" key={version.id} onClick={() => void load(document.id, version.id)} disabled={loading}><span><strong>{version.id === selectedVersionId ? "Selected source version" : index === 0 ? "Latest version" : `Version ${versions.length - index}`}</strong><small>DocumentVersion {version.id} · {formatDate(version.retrieved_at)} · {version.content_kind}</small></span><code>{shortId(version.content_hash)}</code></button>)}</div> : <EmptyState title="No versions" description="This Document has no retrieved versions." />}</SectionCard>
        <SectionCard title="Exact spans" description={selectedVersionId ? `Locators for DocumentVersion ${selectedVersionId}.` : "Select a DocumentVersion before treating a span as source context."}>{spans.length ? <ul className="evidence-list">{spans.map((span) => <li className={`evidence-item ${span.id === selectedSpanId ? "selected" : ""}`} key={span.id}><div className="evidence-item-header"><strong>EvidenceSpan {span.id}</strong><span>{span.locator_type ?? "document"}: {span.locator_value ?? "exact span"}</span></div><blockquote>{span.excerpt}</blockquote></li>)}</ul> : <EmptyState title="No spans" description="No exact Evidence Spans are linked to the selected DocumentVersion." />}</SectionCard>
      </div>
      <SectionCard title="Lineage" description="Citations, syndication, wire propagation, and rewritten reporting remain visible as provenance.">{lineage?.items?.length ? <div className="resource-list">{lineage.items.map((item, index) => <div className="resource-row" key={index}><span><strong>{String(item.relationship ?? "lineage edge")}</strong><small>{String(item.target_document_id ?? item.source_document_id ?? "Provenance edge")}</small></span><Badge tone="neutral">recorded</Badge></div>)}</div> : <EmptyState title="No lineage edges" description="No document lineage has been recorded." />}</SectionCard>
    </>}
  </>;
}
