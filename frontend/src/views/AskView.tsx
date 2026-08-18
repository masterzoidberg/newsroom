import { FormEvent, useState } from "react";
import { apiFetch, jsonBody, formatDate, shortId } from "../lib/api";
import type { AskConversation, AskRun, AskStatement } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard } from "../components/ViewPrimitives";

const SCOPES = [
  { value: "global", label: "Global workspace" },
  { value: "story", label: "Story" },
  { value: "claim", label: "Claim" },
  { value: "document", label: "Document" },
  { value: "report", label: "Report" },
  { value: "question", label: "Research question" },
  { value: "subject", label: "Subject" },
  { value: "monitor", label: "Monitor" },
] as const;

function toneFor(statement: AskStatement): "mint" | "amber" | "coral" | "neutral" {
  if (statement.classification === "fact") return "mint";
  if (statement.classification === "contradiction") return "coral";
  if (statement.classification === "uncertainty" || statement.classification === "user_hypothesis") return "amber";
  return "neutral";
}

function statusTone(status: AskRun["status"]): "mint" | "amber" | "coral" | "neutral" {
  if (status === "answered") return "mint";
  if (status === "qualified" || status === "running") return "amber";
  if (status === "refused" || status === "failed") return "coral";
  return "neutral";
}

export function AskView() {
  const [scopeType, setScopeType] = useState<(typeof SCOPES)[number]["value"]>("global");
  const [scopeId, setScopeId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [conversation, setConversation] = useState<AskConversation | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const question = prompt.trim();
    if (!question) {
      setError(new Error("Enter a question for Newsroom."));
      return;
    }
    if (scopeType !== "global" && !scopeId.trim()) {
      setError(new Error("Enter the ID for the selected object scope."));
      return;
    }
    setWorking(true);
    setError(null);
    try {
      const active = conversation ?? await apiFetch<AskConversation>("/ask/conversations", {
        method: "POST",
        body: jsonBody({ scope_type: scopeType, scope_id: scopeType === "global" ? undefined : scopeId.trim() }),
      });
      const turn = await apiFetch<AskRun>(`/ask/conversations/${encodeURIComponent(active.id)}/turns`, {
        method: "POST",
        body: jsonBody({ prompt: question, provider_mode: "local", context_budget: 4000 }),
      });
      setConversation({ ...active, turns: [...active.turns, turn], updated_at: turn.completed_at ?? active.updated_at });
      setPrompt("");
    } catch (caught) {
      setError(caught);
    } finally {
      setWorking(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Review / evidence"
        title="Ask Newsroom"
        description="Ask a bounded research question over the local evidence ledger. Every answer statement is classified and linked to a resolvable Newsroom object."
      />
      <div className="ask-layout">
        <SectionCard title="Ask a question" description="Local-only mode is the default. No web browsing or arbitrary tools are available to this conversation.">
          <form className="stack-form ask-composer" onSubmit={submit}>
            <label htmlFor="ask-scope">Conversation scope</label>
            <select id="ask-scope" value={scopeType} onChange={(event) => { setScopeType(event.target.value as typeof scopeType); setConversation(null); }}>
              {SCOPES.map((scope) => <option key={scope.value} value={scope.value}>{scope.label}</option>)}
            </select>
            {scopeType !== "global" && <>
              <label htmlFor="ask-scope-id">{SCOPES.find((scope) => scope.value === scopeType)?.label} ID</label>
              <input id="ask-scope-id" value={scopeId} onChange={(event) => { setScopeId(event.target.value); setConversation(null); }} placeholder="Paste an internal ID" autoComplete="off" />
            </>}
            <label htmlFor="ask-prompt">Question</label>
            <textarea id="ask-prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={4000} rows={6} placeholder="What does the evidence establish, and what remains uncertain?" />
            <div className="ask-form-footer">
              <span className="muted">{prompt.length}/4000 · prompt text is not retained in the audit record</span>
              <button className="primary-button" type="submit" disabled={working}>{working ? "Following evidence…" : "Ask Newsroom"}</button>
            </div>
          </form>
        </SectionCard>
        <SectionCard title="Evidence posture" description="The answer composer refuses unsupported factual answers and qualifies stale or conflicting records.">
          <ul className="ask-rules">
            <li><Badge tone="mint">Fact</Badge><span>Stored Claim with supporting Evidence.</span></li>
            <li><Badge tone="neutral">Inference</Badge><span>Interpretation derived from cited records, not a new Claim.</span></li>
            <li><Badge tone="amber">Uncertainty</Badge><span>Missing, stale, unresolved, or ambiguous context.</span></li>
            <li><Badge tone="coral">Contradiction</Badge><span>Stored Claims or Evidence disagree.</span></li>
            <li><Badge tone="amber">User hypothesis</Badge><span>Notes remain hypotheses and never become facts.</span></li>
          </ul>
        </SectionCard>
      </div>
      {working && <LoadingState label="Retrieving and resolving citations" />}
      {error && <ErrorState error={error} />}
      {conversation && <ConversationHistory conversation={conversation} />}
      {!conversation && !working && <EmptyState title="No conversation yet" description="Start with a global question or narrow the conversation to a Story, Document, Subject, Report, or Question." />}
    </>
  );
}

function ConversationHistory({ conversation }: { conversation: AskConversation }) {
  return (
    <SectionCard title="Conversation" description={`Scope: ${conversation.scope_type}${conversation.scope_id ? ` · ${shortId(conversation.scope_id)}` : ""}. Audit retains hashes, retrieval metadata, and citations—not raw prompts.`}>
      <div className="ask-history">
        {conversation.turns.map((turn) => <article className="ask-turn" key={turn.run_id}>
          <div className="ask-turn-header">
            <span><Badge tone={statusTone(turn.status)}>{turn.status}</Badge><small>Run {shortId(turn.run_id)} · {formatDate(turn.completed_at ?? turn.created_at)}</small></span>
            {turn.refusal_code && <code>{turn.refusal_code}</code>}
          </div>
          {turn.answer && <p className="ask-answer">{turn.answer}</p>}
          {turn.statements.length > 0 && <div className="ask-statements">
            {turn.statements.map((statement) => <div className="ask-statement" key={statement.id}>
              <div className="ask-statement-label"><Badge tone={toneFor(statement)}>{statement.classification.replace("_", " ")}</Badge><span>{statement.citation_ids.length} citation{statement.citation_ids.length === 1 ? "" : "s"}</span></div>
              <p>{statement.text}</p>
            </div>)}
          </div>}
          {turn.citations.length > 0 && <div className="ask-citations">
            <h3>Resolvable citations</h3>
            <ul>{turn.citations.map((citation) => <li key={citation.id}><Badge tone={citation.resolvable ? "mint" : "coral"}>{citation.object_type}</Badge><span>{citation.label}</span><code>{shortId(citation.object_id)}</code></li>)}</ul>
          </div>}
          <p className="ask-audit">Retrieved {turn.retrieval.candidate_count ?? 0} candidates · context {turn.retrieval.context_units ?? 0}/{turn.retrieval.context_budget ?? "—"} units · provider {turn.provider_route ?? "local"}</p>
        </article>)}
      </div>
    </SectionCard>
  );
}
