export type ListResponse<T> = {
  items: T[];
  page?: number;
  page_size?: number;
  total?: number;
};

export type ServiceState = "checking" | "online" | "offline";

export type ViewKey =
  | "inbox"
  | "stories"
  | "documents"
  | "reports"
  | "saved"
  | "history"
  | "workbench"
  | "ask"
  | "topics"
  | "subjects"
  | "sources"
  | "monitors"
  | "questions"
  | "runs"
  | "alerts"
  | "settings";

export type ClaimEvidence = {
  id: string;
  evidence_span_id: string;
  relationship: "supports" | "contradicts" | "contextualizes";
  excerpt: string;
  locator_type: string | null;
  locator_value: string | null;
  document_version: { id: string; retrieved_at: string; content_hash: string };
  document: { id: string; canonical_url: string; title: string; source_id: string };
  source: { id: string; name: string; slug: string };
};

export type Claim = {
  id: string;
  proposition: string;
  importance: "major" | "relevant" | "peripheral";
  state: string;
  accepted: boolean;
  accepted_at?: string | null;
  story_id: string | null;
  article_analysis_id: string | null;
  candidate_claim_index: number | null;
  created_at: string;
  provenance: {
    origin: "manual" | "automatic";
    promotion_id: string | null;
    promotion_identity: string | null;
    article_analysis_id: string | null;
    candidate_claim_index: number | null;
  };
  evidence: ClaimEvidence[];
};

export type StoryRevision = {
  id: string;
  story_id: string;
  revision_number: number;
  created_at: string;
  claim_ids: string[];
  document_ids: string[];
  origin: "manual" | "automatic";
  story_evolution_event_id: string | null;
};

export type OrchestrationJob = {
  id: string;
  job_type: "automatic_story_stage" | "automatic_report_stage" | "automatic_alert_stage";
  status: string;
  attempts: number;
  max_attempts: number;
  next_attempt_at: string | null;
  lease_owner: string | null;
  lease_expires_at: string | null;
  failure_cause: string | null;
  orchestration: {
    outcome: string;
    promotion_id?: string;
    claim_id?: string;
    story_id?: string;
    report_id?: string;
    revision_id?: string;
    report_revision_id?: string;
    alert_ids?: string[];
    delivery_ids?: string[];
    reason_code?: string;
  };
};

export type Story = {
  id: string;
  headline?: string;
  summary?: string;
  why_it_matters?: string;
  lifecycle: string;
  current_revision_id?: string | null;
  current_revision?: { headline?: string; summary?: string; why_it_matters?: string } | null;
  updated_at?: string;
};

export type Report = {
  id: string;
  name: string;
  target_type: string;
  target_id: string;
  status: string;
  timezone_name: string;
  current_revision_id?: string | null;
  current_revision?: ReportRevision | null;
  revisions?: ReportRevision[];
};

export type ReportRevision = {
  id: string;
  revision_number: number;
  claim_set_hash: string;
  material_change: number;
  current_status: string;
  generated_at: string;
  claim_ids: string[];
  propositions: Array<{ text: string; claim_ids: string[] }>;
  sections: {
    current_status?: string;
    what_changed?: Array<{ text: string; cause_type?: string; evidence_span_ids?: string[] }>;
    active_stories?: Array<{ story_id: string; headline: string; lifecycle: string; claim_ids: string[] }>;
    evidence_strength?: Array<Record<string, unknown>>;
    contradictions?: Array<{ claim_id: string; proposition: string; evidence_span_ids: string[] }>;
    unresolved_questions?: Array<{ id: string; question: string; priority: string }>;
    recommended_investigations?: Array<{ id: string; suggestion: string; rationale: string; expected_information_value: number }>;
  };
  audit: { passed: boolean; unsupported_propositions?: string[]; unsupported_changes?: string[] };
  change_causes: Array<{
    id: string;
    cause_type: string;
    rationale: string;
    evidence_span_id: string | null;
    claim_id: string | null;
    document_id: string | null;
  }>;
};

export type Alert = {
  id: string;
  rule_id: string;
  report_id: string | null;
  report_revision_id: string | null;
  story_id: string | null;
  title: string;
  body: string;
  event_type: string;
  importance_score: number;
  status: "unread" | "acknowledged";
  created_at: string;
  cause: Array<{
    id: string;
    revision_id: string;
    cause_type: string;
    cause_id: string;
    story_id: string | null;
    claim_id: string | null;
    evidence_span_id: string | null;
    document_id: string | null;
    rationale: string;
  }>;
  deliveries: Array<{ id: string; channel: string; status: string; error_detail?: string | null }>;
};

export type AlertRule = {
  id: string;
  name: string;
  target_type: string;
  target_id: string | null;
  event_types: string[];
  min_importance: number;
  browser_enabled: boolean;
  enabled: boolean;
};

export type NotificationPreferences = {
  browser_enabled: boolean;
  permission_state: "default" | "granted" | "denied";
  online: boolean;
};

export type Briefing = {
  id: string;
  period: "daily" | "weekly";
  timezone_name: string;
  period_start: string;
  period_end: string;
  items: Array<{
    id: string;
    report_id: string;
    report_revision_id: string;
    story_id: string | null;
    rank: number;
    importance_score: number;
    reason: string;
    claim_ids: string[];
    evidence_span_ids: string[];
  }>;
};

export type DocumentRecord = {
  id: string;
  title: string;
  canonical_url: string;
  published_at?: string | null;
  source_id: string;
  first_seen_at?: string;
};

export type DocumentVersion = { id: string; retrieved_at: string; content_hash: string; content_kind: string };

export type Timeline = { events?: Array<Record<string, unknown>>; revisions?: Array<Record<string, unknown>> };

export type CollectionRecord = Record<string, unknown> & { id: string; name?: string; title?: string; status?: string; enabled?: boolean };

export type ResearchQuestionClaim = {
  claim_id: string;
  relationship: "supports" | "contradicts" | "contextualizes" | "resolves";
  origin?: "manual" | "automatic" | "task";
  confidence?: number;
  rationale?: string;
};

export type ResearchQuestionGap = {
  id: string;
  gap_type: string;
  description: string;
  status: "open" | "pursuing" | "satisfied" | "dismissed" | "blocked";
  rationale?: string;
};

export type ResearchTask = {
  id: string;
  status: "planned" | "running" | "completed_with_evidence" | "completed_with_candidates" | "completed_no_findings" | "deferred" | "failed" | "cancelled";
  mode: "manual" | "automatic";
  outcome?: Record<string, unknown>;
  limits?: Record<string, number>;
};

export type ResearchQuestion = CollectionRecord & {
  question: string;
  assessment_state?: "open" | "partially_answered" | "supported" | "contradicted" | "resolved" | "stale";
  assessment_explanation?: string;
  assessment_at?: string | null;
  pursuit_policy?: "disabled" | "manual" | "automatic";
};

export type ResearchQuestionDetail = ResearchQuestion & {
  claims?: ResearchQuestionClaim[];
  gaps?: ResearchQuestionGap[];
  tasks?: ResearchTask[];
  assessment_history?: Array<Record<string, unknown>>;
};

export type AskCitation = {
  id: string;
  object_type: string;
  object_id: string;
  label: string;
  kind: string;
  resolvable: boolean;
  document_id?: string;
  document_version_id?: string;
  retrieved_at?: string;
  locator_type?: string | null;
  locator_value?: string | null;
};

export type AskStatement = {
  id: string;
  text: string;
  classification: "fact" | "inference" | "uncertainty" | "contradiction" | "user_hypothesis" | "context";
  citation_ids: string[];
};

export type AskRun = {
  run_id: string;
  conversation_id: string;
  turn_number: number;
  prompt_hash?: string;
  prompt_length?: number;
  status: "running" | "answered" | "qualified" | "refused" | "cancelled" | "failed";
  answer: string;
  statements: AskStatement[];
  citations: AskCitation[];
  retrieval: {
    candidate_count?: number;
    entity_types?: string[];
    context_units?: number;
    context_budget?: number;
    stale_evidence_count?: number;
    ambiguous?: boolean;
  };
  refusal_code?: string | null;
  provider_route?: string;
  estimated_cost_usd?: number;
  created_at?: string;
  completed_at?: string | null;
};

export type AskConversation = {
  id: string;
  scope_type: string;
  scope_id: string | null;
  created_at: string;
  updated_at: string;
  turns: AskRun[];
};
