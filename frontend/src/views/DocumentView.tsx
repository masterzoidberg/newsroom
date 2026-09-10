import { FormEvent, useEffect, useState } from "react";
import { apiFetch, formatDate, shortId } from "../lib/api";
import type { DocumentRecord, DocumentVersion } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard } from "../components/ViewPrimitives";

type Span = { id: string; excerpt: string; locator_type?: string | null; locator_value?: string | null };
type Lineage = { items?: Array<Record<string, unknown>> };

export const DOCUMENT_NAVIGATION_KEY = "newsroom.document.inspect.v1";

export function queueDocumentNavigation(documentId: string) {
  const identifier = documentId.trim();
  if (!identifier) return;
  try { window.sessionStorage.setItem(DOCUMENT_NAVIGATION_KEY, identifier); } catch { /* The document ID remains available from the Watch result. */ }
}

function takeQueuedDocumentNavigation(): string {
  try {
    const identifier = window.sessionStorage.getItem(DOCUMENT_NAVIGATION_KEY) ?? "";
    window.sessionStorage.removeItem(DOCUMENT_NAVIGATION_KEY);
    return identifier.trim();
  } catch { return ""; }
}

export function DocumentView() {
  const [documentId, setDocumentId] = useState(takeQueuedDocumentNavigation);
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [spans, setSpans] = useState<Span[]>([]);
  const [lineage, setLineage] = useState<Lineage | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  async function load(identifier: string) {
    setLoading(true);
    setError(null);
    try {
      const encoded = encodeURIComponent(identifier);
      const [doc, versionResponse, lineageResponse] = await Promise.all([
        apiFetch<DocumentRecord>(`/documents/${encoded}`),
        apiFetch<{ items: DocumentVersion[] }>(`/documents/${encoded}/versions`),
        apiFetch<Lineage>(`/documents/${encoded}/lineage`),
      ]);
      setDocument(doc);
      setVersions(versionResponse.items);
      setLineage(lineageResponse);
      const latest = versionResponse.items[0];
      setSpans(latest ? (await apiFetch<{ items: Span[] }>(`/document-versions/${latest.id}/evidence-spans`)).items : []);
    } catch (caught) {
      setDocument(null);
      setVersions([]);
      setSpans([]);
      setLineage(null);
      setError(caught);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (documentId) void load(documentId);
  }, []);

  async function inspect(event: FormEvent) {
    event.preventDefault();
    const identifier = documentId.trim();
    if (!identifier) { setError(new Error("Enter a Document ID to inspect.")); return; }
    await load(identifier);
  }

  return <>
    <PageHeader eyebrow="Review / analysis" title="Documents" description="Analyze version history, exact Evidence Spans, and publication lineage without storing article bodies in the UI." />
    <SectionCard title="Open a Document" description="Use the canonical Document ID from an evidence or Watch result. Deferred analysis opens here without inventing a Story.">
      <form className="inline-form" onSubmit={(event) => void inspect(event)}>
        <label htmlFor="document-id">Document ID</label>
        <input id="document-id" name="document_id" autoComplete="off" value={documentId} onChange={(event) => setDocumentId(event.target.value)} placeholder="doc_…" />
        <button className="primary-button" type="submit" disabled={loading}>{loading ? "Analyzing…" : "Analyze Document"}</button>
      </form>
    </SectionCard>
    {loading && <LoadingState label="Loading versions and spans" />}
    {error && <ErrorState error={error} />}
    {document && <>
      <section className="story-summary">
        <div><p className="eyebrow">Document analysis</p><h2>{document.title}</h2><p><a href={document.canonical_url} target="_blank" rel="noreferrer">{document.canonical_url}</a></p></div>
        <div className="story-summary-meta"><Badge tone="mint">{document.source_id}</Badge><span>First seen {formatDate(document.first_seen_at)}</span><span>Published {formatDate(document.published_at)}</span></div>
      </section>
      <div className="content-grid document-grid">
        <SectionCard title="Version history" description="Each retrieved version is immutable.">{versions.length ? <div className="resource-list">{versions.map((version, index) => <div className={`resource-row ${index === 0 ? "selected" : ""}`} key={version.id}><span><strong>{index === 0 ? "Latest version" : `Version ${versions.length - index}`}</strong><small>{formatDate(version.retrieved_at)} · {version.content_kind}</small></span><code>{shortId(version.content_hash)}</code></div>)}</div> : <EmptyState title="No versions" description="This Document has no retrieved versions." />}</SectionCard>
        <SectionCard title="Exact spans" description="The latest version’s locators are the source of truth.">{spans.length ? <ul className="evidence-list">{spans.map((span) => <li className="evidence-item" key={span.id}><div className="evidence-item-header"><strong>{shortId(span.id)}</strong><span>{span.locator_type ?? "document"}: {span.locator_value ?? "exact span"}</span></div><blockquote>{span.excerpt}</blockquote></li>)}</ul> : <EmptyState title="No spans" description="No exact Evidence Spans are linked to the latest version." />}</SectionCard>
      </div>
      <SectionCard title="Lineage" description="Citations, syndication, wire propagation, and rewritten reporting remain visible as provenance.">{lineage?.items?.length ? <div className="resource-list">{lineage.items.map((item, index) => <div className="resource-row" key={index}><span><strong>{String(item.relationship ?? "lineage edge")}</strong><small>{String(item.target_document_id ?? item.source_document_id ?? "Provenance edge")}</small></span><Badge tone="neutral">recorded</Badge></div>)}</div> : <EmptyState title="No lineage edges" description="No document lineage has been recorded." />}</SectionCard>
    </>}
  </>;
}
