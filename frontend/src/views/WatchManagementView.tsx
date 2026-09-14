import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";
import { ApiError, apiFetch, apiList, formatDate, getAIStatus, isApiUnavailable, jsonBody, shortId } from "../lib/api";
import type { AIStatus, CollectionRecord, ResearchQuestion, VocabularyKind, WatchResearchContext, WatchSetupResponse, WatchVocabularyTerm } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, Stat } from "../components/ViewPrimitives";
import { queueDocumentNavigation } from "./DocumentView";

type Watch = CollectionRecord & {
  target_type?: string;
  target_id?: string;
  policy?: CollectionRecord;
  vocabulary?: WatchVocabularyTerm[];
  primary_terms?: CollectionRecord[];
  source_candidates?: CollectionRecord[];
  sources?: WatchSource[];
  research_context?: WatchResearchContext;
  research_question?: ResearchQuestion;
};

type WatchSource = { source?: CollectionRecord; monitor?: CollectionRecord };

type SourceActivity = CollectionRecord & {
  outcome?: string;
  error_code?: string | null;
  observed_at?: string | null;
};

type SourceHealth = {
  latest: SourceActivity | null;
  error?: string;
};

type SourceHealthMap = Record<string, SourceHealth>;

type VocabularyInput = {
  term: string;
  kind: VocabularyKind;
  expansion_of?: string;
  rationale: string;
};

type Health = {
  status: string;
  discovery_enabled: boolean;
  active_source_count: number;
  pending_source_candidate_count: number;
  pending_vocabulary_suggestion_count: number;
  last_attempt?: string | null;
  last_success?: string | null;
  next_scheduled_run?: string | null;
  last_discovery_run?: string | null;
  last_discovery_status?: string | null;
  last_error?: string | null;
  review?: WatchReview;
  progress?: WatchProgress;
};

type WatchReview = {
  interest: string;
  approved_terms: string[];
  excluded_terms: string[];
  sources: Array<{ name: string; domain?: string | null; usable: boolean; enabled: boolean }>;
  cadence: { base_cadence_seconds: number; min_cadence_seconds: number; max_cadence_seconds: number; next_check_at?: string | null };
  supported_channels: string[];
  paid_budget_usd: number;
  paid_mode: string;
  ready_to_start: boolean;
  blockers: string[];
};

type WatchProgress = {
  state: string;
  label: string;
  detail: string;
  last_attempt?: string | null;
  last_result?: string | null;
  last_error?: string | null;
  retryable: boolean;
  results: Array<{ kind: "document" | "story"; id: string; title: string; canonical_url?: string; ready_at?: string | null }>;
};

type SetupDraft = {
  request_id: string;
  target_type: "topic" | "research_question";
  interest: string;
  question: string;
  question_source: "new" | "existing";
  name: string;
  primary_terms: string[];
  term_draft: string;
  name_touched: boolean;
  term_touched: boolean;
  create_report: boolean;
  enable_briefing: boolean;
};

type SetupSubmission = {
  request_id: string;
  target_type: "topic" | "research_question";
  interest: string;
  question: string;
  name: string;
  primary_terms: string[];
  create_report: boolean;
  enable_briefing: boolean;
};

type BriefingSchedule = {
  cadence: "daily" | "weekly";
  timezone_name: string;
  enabled: boolean;
  paused: boolean;
};

type SourceCandidateInput = {
  source_id?: string;
  name: string;
  homepage_url?: string;
  feed_url?: string;
  discovery_method: "manual" | "existing_source";
  rationale: string;
};

type VocabularyRouteSummary = {
  title: string;
  detail: string;
  tone: "neutral" | "mint" | "amber" | "coral";
};

const VOCABULARY_KIND_OPTIONS: Array<{ value: VocabularyKind; label: string }> = [
  { value: "alias", label: "Alias" },
  { value: "synonym", label: "Synonym" },
  { value: "acronym", label: "Acronym" },
  { value: "acronym_expansion", label: "Acronym expansion" },
  { value: "related", label: "Related term or entity" },
  { value: "include", label: "Include" },
  { value: "exclude", label: "Exclude / meaning to leave out" },
  { value: "primary", label: "Primary term" },
];

function vocabularyKindLabel(kind: string): string {
  return VOCABULARY_KIND_OPTIONS.find((option) => option.value === kind)?.label ?? kind;
}

function vocabularyEnabled(item: WatchVocabularyTerm): boolean {
  return item.enabled === true || item.enabled === 1;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "The terminology request could not be completed.";
}

function vocabularyRouteSummary(status: AIStatus | null, statusError: unknown, policy?: CollectionRecord): VocabularyRouteSummary {
  if (statusError) {
    return {
      title: "Manual fallback",
      detail: "Provider status is unavailable. Manual terms always available; retry suggestions after the local service is reachable.",
      tone: "amber",
    };
  }
  if (!status) {
    return {
      title: "Checking route",
      detail: "Newsroom is checking the configured terminology route. Manual terms always available while this status loads.",
      tone: "neutral",
    };
  }
  const route = status.routes.find((item) => item.capability === "vocabulary");
  const effective = route?.effective;
  if (!effective || effective.provider_route === "local") {
    const unavailable = effective?.reason === "connection_unavailable" || effective?.reason === "connection_missing";
    return {
      title: unavailable ? "Local fallback" : "Local / offline",
      detail: `${unavailable ? "The managed provider is unavailable, so Newsroom uses its deterministic local fallback." : "This Watch uses the deterministic local route."} Manual terms always available and cost nothing. Suggestions remain review-only.`,
      tone: "mint",
    };
  }
  const paidBudget = Number(policy?.paid_budget_usd ?? 0);
  if (!status?.paid_enabled || !Number.isFinite(paidBudget) || paidBudget <= 0) {
    return {
      title: "Managed route, paid off",
      detail: "A managed terminology provider is configured, but background paid routing is disabled for this request or this Watch has a zero paid budget. Manual terms always available; deterministic fallback remains safe.",
      tone: "amber",
    };
  }
  return {
    title: `Managed · ${effective.provider}`,
    detail: `Explicit suggestion requests may use ${effective.model ?? "the configured model"} within this Watch's saved paid budget. Manual terms always available; no suggestion is active until you approve it.`,
    tone: "amber",
  };
}

const SETUP_DRAFT_KEY = "newsroom.watch-setup.v2";
const SETUP_PENDING_KEY = "newsroom.watch-setup.pending.v1";
const SELECTED_WATCH_KEY = "newsroom.selected-watch.v1";
const MAX_PRIMARY_TERMS = 100;
const MAX_PRIMARY_TERM_LENGTH = 300;
const text = (value: unknown, fallback = "—") => String(value ?? fallback);

function freshSetupDraft(): SetupDraft {
  return {
    request_id: window.crypto.randomUUID(),
    target_type: "topic",
    interest: "",
    question: "",
    question_source: "new",
    name: "",
    primary_terms: [],
    term_draft: "",
    name_touched: false,
    term_touched: false,
    create_report: false,
    enable_briefing: false,
  };
}

function validPrimaryTerms(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  const terms = value.filter((item): item is string => typeof item === "string").slice(0, MAX_PRIMARY_TERMS);
  if (terms.some((item) => item.length > MAX_PRIMARY_TERM_LENGTH)) return null;
  return terms;
}

function loadStoredSetupDraft(): SetupDraft {
  try {
    const raw = window.sessionStorage.getItem(SETUP_DRAFT_KEY);
    if (!raw) return freshSetupDraft();
    const saved = JSON.parse(raw) as Partial<SetupDraft>;
    if (typeof saved.request_id !== "string" || typeof saved.interest !== "string" || typeof saved.name !== "string") return freshSetupDraft();
    const primaryTerms = validPrimaryTerms(saved.primary_terms);
    if (primaryTerms === null) return freshSetupDraft();
    const targetType = saved.target_type === "research_question" ? "research_question" : "topic";
    const savedQuestion = typeof saved.question === "string" ? saved.question : "";
    const savedName = saved.name_touched === true || saved.name !== saved.interest.slice(0, 200) ? saved.name : "";
    const savedTermDraft = typeof saved.term_draft === "string" && saved.term_draft.length <= MAX_PRIMARY_TERM_LENGTH ? saved.term_draft : "";
    const termDraft = saved.term_touched === true || savedTermDraft !== saved.interest.slice(0, MAX_PRIMARY_TERM_LENGTH) ? savedTermDraft : "";
    return {
      request_id: saved.request_id,
      target_type: targetType,
      interest: saved.interest,
      question: targetType === "research_question" ? savedQuestion || saved.interest : savedQuestion,
      question_source: saved.question_source === "existing" ? "existing" : "new",
      name: savedName,
      primary_terms: primaryTerms,
      term_draft: termDraft,
      name_touched: saved.name_touched === true,
      term_touched: saved.term_touched === true,
      create_report: saved.create_report === true,
      enable_briefing: saved.enable_briefing === true,
    };
  } catch {
    return freshSetupDraft();
  }
}

function loadStoredPendingSubmission(): SetupSubmission | null {
  try {
    const raw = window.sessionStorage.getItem(SETUP_PENDING_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as Partial<SetupSubmission>;
    const primaryTerms = validPrimaryTerms(saved.primary_terms);
    if (
      typeof saved.request_id !== "string" || !saved.request_id ||
      typeof saved.interest !== "string" || !saved.interest.trim() ||
      typeof saved.name !== "string" || !saved.name.trim() ||
      primaryTerms === null || primaryTerms.length === 0
    ) return null;
    const targetType = saved.target_type === "research_question" ? "research_question" : "topic";
    return {
      request_id: saved.request_id,
      target_type: targetType,
      interest: saved.interest,
      question: targetType === "research_question" && typeof saved.question === "string" ? saved.question : targetType === "research_question" ? saved.interest : "",
      name: saved.name,
      primary_terms: primaryTerms,
      create_report: saved.create_report === true,
      enable_briefing: saved.enable_briefing === true,
    };
  } catch {
    return null;
  }
}

function persistPendingSubmission(submission: SetupSubmission | null) {
  try {
    if (submission) window.sessionStorage.setItem(SETUP_PENDING_KEY, JSON.stringify(submission));
    else window.sessionStorage.removeItem(SETUP_PENDING_KEY);
  } catch { /* Keep in-memory recovery when browser storage is unavailable. */ }
}

function normalizedTerm(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

function submissionFromDraft(draft: SetupDraft): SetupSubmission {
  return {
    request_id: draft.request_id,
    target_type: draft.target_type,
    interest: draft.interest.trim(),
    question: draft.target_type === "research_question" ? draft.question.trim() : "",
    name: draft.name.trim(),
    primary_terms: draft.primary_terms.map((item) => item.trim()),
    create_report: draft.create_report,
    enable_briefing: draft.enable_briefing,
  };
}

function setupDraftHasContent(draft: SetupDraft): boolean {
  return Boolean(
    draft.interest.trim() ||
    draft.question.trim() ||
    draft.name.trim() ||
    draft.primary_terms.length > 0 ||
    draft.term_draft.trim() ||
    draft.create_report ||
    draft.enable_briefing
  );
}

export function WatchManagementView() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [policies, setPolicies] = useState<CollectionRecord[]>([]);
  const [researchQuestions, setResearchQuestions] = useState<ResearchQuestion[]>([]);
  const [researchQuestionsLoading, setResearchQuestionsLoading] = useState(false);
  const [researchQuestionsError, setResearchQuestionsError] = useState<unknown>(null);
  const [selectedId, setSelectedId] = useState("");
  const [selected, setSelected] = useState<Watch | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [sourceHealth, setSourceHealth] = useState<SourceHealthMap>({});
  const [setupDraft, setSetupDraft] = useState<SetupDraft>(loadStoredSetupDraft);
  const [pendingSubmission, setPendingSubmission] = useState<SetupSubmission | null>(loadStoredPendingSubmission);
  const [setupError, setSetupError] = useState<unknown>(null);
  const [setupValidation, setSetupValidation] = useState("");
  const [setupSaved, setSetupSaved] = useState("");
  const [policyId, setPolicyId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [targetType, setTargetType] = useState("topic");
  const [legacyWatchName, setLegacyWatchName] = useState("");
  const [legacyPolicyName, setLegacyPolicyName] = useState("");
  const [editName, setEditName] = useState("");
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);
  const [aiStatusError, setAiStatusError] = useState<unknown>(null);
  const [suggestionError, setSuggestionError] = useState<unknown>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      if (setupDraftHasContent(setupDraft)) window.sessionStorage.setItem(SETUP_DRAFT_KEY, JSON.stringify(setupDraft));
      else window.sessionStorage.removeItem(SETUP_DRAFT_KEY);
    } catch { /* Browser storage may be unavailable. */ }
  }, [setupDraft]);

  useEffect(() => { persistPendingSubmission(pendingSubmission); }, [pendingSubmission]);

  const loadResearchQuestions = useCallback(async () => {
    setResearchQuestionsLoading(true);
    setResearchQuestionsError(null);
    try {
      setResearchQuestions((await apiList<ResearchQuestion>("/research-questions?page_size=100")).items);
    } catch (caught) {
      setResearchQuestionsError(caught);
    } finally {
      setResearchQuestionsLoading(false);
    }
  }, []);

  useEffect(() => { void loadResearchQuestions(); }, [loadResearchQuestions]);

  const loadDetail = useCallback(async (id: string) => {
    const watch = await apiFetch<Watch>(`/watches/${id}`);
    const policyRequest = watch.policy_id
      ? apiFetch<CollectionRecord>(`/monitoring-policies/${watch.policy_id}`)
      : Promise.resolve(null);
    const primaryTermsRequest = watch.target_type === "topic" && watch.target_id
      ? apiList<CollectionRecord>(`/topics/${watch.target_id}/vocabulary?page_size=100`)
      : Promise.resolve({ items: [] as CollectionRecord[] });
    const aiStatusRequest = getAIStatus().catch((caught) => {
      setAiStatusError(caught);
      return null;
    });
    const [watchHealth, vocabulary, candidates, sources, primaryTerms, policy, nextAiStatus] = await Promise.all([
      apiFetch<Health>(`/watches/${id}/health`),
      apiList<WatchVocabularyTerm>(`/watches/${id}/vocabulary?page_size=100`),
      apiList<CollectionRecord>(`/watches/${id}/source-candidates?page_size=100`),
      apiList<WatchSource>(`/watches/${id}/sources?page_size=100`),
      primaryTermsRequest,
      policyRequest,
      aiStatusRequest,
    ]);
    const nextSourceHealth: SourceHealthMap = {};
    await Promise.all(sources.items.map(async (item) => {
      const monitorId = text(item.monitor?.id, "");
      if (!monitorId) return;
      try {
        const activity = await apiList<SourceActivity>(`/monitors/${encodeURIComponent(monitorId)}/activity?page_size=1`);
        nextSourceHealth[monitorId] = { latest: activity.items[0] ?? null };
      } catch (caught) {
        nextSourceHealth[monitorId] = { latest: null, error: errorMessage(caught) };
      }
    }));
    setAiStatus(nextAiStatus);
    if (nextAiStatus) setAiStatusError(null);
    setSelected({ ...watch, policy: policy ?? undefined, vocabulary: vocabulary.items, primary_terms: primaryTerms.items, source_candidates: candidates.items, sources: sources.items });
    setHealth(watchHealth);
    setSourceHealth(nextSourceHealth);
    setEditName(text(watch.name, ""));
  }, []);

  const load = useCallback(async (preferredId = "") => {
    setLoading(true);
    setError(null);
    try {
      const [watchResult, policyResult] = await Promise.all([
        apiList<Watch>("/watches?page_size=100"),
        apiList<CollectionRecord>("/monitoring-policies?page_size=100"),
      ]);
      setWatches(watchResult.items);
      setPolicies(policyResult.items);
      setPolicyId((current) => current && policyResult.items.some((item) => item.id === current) ? current : policyResult.items[0]?.id ?? "");
      let storedId = preferredId;
      if (!storedId) {
        try { storedId = window.localStorage.getItem(SELECTED_WATCH_KEY) ?? ""; } catch { storedId = ""; }
      }
      const nextId = storedId && watchResult.items.some((item) => item.id === storedId) ? storedId : watchResult.items[0]?.id ?? "";
      setSelectedId(nextId);
      if (nextId) {
        try { window.localStorage.setItem(SELECTED_WATCH_KEY, nextId); } catch { /* Keep in-memory selection. */ }
        await loadDetail(nextId);
      } else {
        setSelected(null);
        setHealth(null);
        setSourceHealth({});
        try { window.localStorage.removeItem(SELECTED_WATCH_KEY); } catch { /* No durable selection available. */ }
      }
    } catch (caught) { setError(caught); } finally { setLoading(false); }
  }, [loadDetail]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    const progressState = health?.progress?.state;
    if (!selectedId || !progressState || !["collecting", "processing", "deferred", "error"].includes(progressState)) return;
    let cancelled = false;
    let timer: number | undefined;
    let failures = 0;
    const poll = async () => {
      if (cancelled) return;
      try {
        setHealth(await apiFetch<Health>(`/watches/${selectedId}/health`));
        failures = 0;
      } catch (caught) {
        failures += 1;
        setError(caught);
      }
      if (cancelled) return;
      const base = progressState === "error" ? 10_000 : progressState === "deferred" ? 5_000 : 2_500;
      const delay = Math.min(30_000, base * (2 ** Math.min(failures, 3)));
      timer = window.setTimeout(() => void poll(), delay);
    };
    timer = window.setTimeout(() => void poll(), progressState === "error" ? 5_000 : 1_500);
    return () => { cancelled = true; if (timer !== undefined) window.clearTimeout(timer); };
  }, [selectedId, health?.progress?.state]);

  async function selectWatch(id: string) {
    setSelectedId(id);
    setWorking(true);
    setError(null);
    try {
      try { window.localStorage.setItem(SELECTED_WATCH_KEY, id); } catch { /* Keep in-memory selection. */ }
      await loadDetail(id);
    } catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function refresh(id = selectedId) {
    if (!id) return;
    setWorking(true);
    try {
      await loadDetail(id);
      const result = await apiList<Watch>("/watches?page_size=100");
      setWatches(result.items);
    } catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  function updateInterest(value: string) {
    const materialChange = normalizedTerm(setupDraft.interest) !== normalizedTerm(value);
    const invalidatedApproval = materialChange && setupDraft.primary_terms.length > 0;
    setSetupError(null);
    setSetupSaved("");
    setSetupValidation(invalidatedApproval ? "Interest changed. Reconfirm at least one primary term before saving." : "");
    setSetupDraft((current) => ({
      ...current,
      interest: value,
      name: current.name,
      primary_terms: materialChange ? [] : current.primary_terms,
      term_draft: current.term_draft,
    }));
  }

  function updateQuestion(value: string) {
    const previous = setupDraft.question || setupDraft.interest;
    const materialChange = normalizedTerm(previous) !== normalizedTerm(value);
    const invalidatedApproval = materialChange && setupDraft.primary_terms.length > 0;
    setSetupError(null);
    setSetupSaved("");
    setSetupValidation(invalidatedApproval ? "Question changed. Reconfirm at least one primary term before saving." : "");
    setSetupDraft((current) => ({
      ...current,
      interest: value,
      question: value,
      question_source: "new",
      name: current.name,
      primary_terms: materialChange ? [] : current.primary_terms,
      term_draft: current.term_draft,
    }));
  }

  function changeSetupTarget(value: "topic" | "research_question") {
    setSetupError(null);
    setSetupSaved("");
    setSetupValidation("");
    setSetupDraft((current) => {
      const textValue = current.target_type === "research_question" ? current.question : current.interest;
      return {
        ...current,
        target_type: value,
        interest: textValue,
        question: value === "research_question" ? textValue : current.question,
        question_source: "new",
        name: current.name,
      };
    });
    if (value === "research_question" && researchQuestions.length === 0 && !researchQuestionsLoading) void loadResearchQuestions();
  }

  function chooseExistingQuestion(value: string) {
    const question = value.trim();
    if (!question) return;
    updateQuestion(question);
    setSetupDraft((current) => ({ ...current, question_source: "existing" }));
  }

  function addPrimaryTerm() {
    const candidate = setupDraft.term_draft.trim();
    setSetupValidation("");
    if (!candidate) { setSetupValidation("Enter a primary term before confirming it."); return; }
    if (candidate.length > MAX_PRIMARY_TERM_LENGTH) { setSetupValidation(`Primary terms are limited to ${MAX_PRIMARY_TERM_LENGTH} characters.`); return; }
    if (setupDraft.primary_terms.length >= MAX_PRIMARY_TERMS) { setSetupValidation(`A Watch can have at most ${MAX_PRIMARY_TERMS} primary terms during setup.`); return; }
    const identity = normalizedTerm(candidate);
    if (setupDraft.primary_terms.some((item) => normalizedTerm(item) === identity)) {
      setSetupDraft((current) => ({ ...current, term_draft: "", term_touched: true }));
      return;
    }
    setSetupDraft((current) => ({ ...current, primary_terms: [...current.primary_terms, candidate], term_draft: "", term_touched: true }));
  }

  function removePrimaryTerm(index: number) {
    setSetupDraft((current) => ({ ...current, primary_terms: current.primary_terms.filter((_item, itemIndex) => itemIndex !== index), term_touched: true }));
  }

  async function attemptSetup(submission: SetupSubmission) {
    setWorking(true); setSetupError(null); setSetupValidation(""); setSetupSaved("");
    try {
      const result = await apiFetch<WatchSetupResponse>("/watches/setup", {
        method: "POST",
        body: jsonBody({
          request_id: submission.request_id,
          target_type: submission.target_type,
          interest: submission.interest,
          ...(submission.target_type === "research_question" ? { question: submission.question } : {}),
          name: submission.name,
          primary_terms: submission.primary_terms,
        }),
      });
      const optionalWarnings: string[] = [];
      if (submission.create_report) {
        try {
          const savedWatch = await apiFetch<Watch>(`/watches/${encodeURIComponent(result.watch_id)}`);
          await apiFetch("/reports", {
            method: "POST",
            body: jsonBody({ name: `${text(savedWatch.name, "Watch")} report`, target_type: savedWatch.target_type, target_id: savedWatch.target_id, timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC" }),
          });
        } catch (caught) {
          if (!(caught instanceof ApiError && caught.status === 409)) optionalWarnings.push("The Living Report choice could not be saved; open Reports to retry it.");
        }
      }
      if (submission.enable_briefing) {
        try {
          const currentSchedule = await apiFetch<BriefingSchedule | null>("/briefing-schedule");
          await apiFetch("/briefing-schedule", {
            method: "PUT",
            body: jsonBody(currentSchedule ? { enabled: true } : { cadence: "daily", timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC", enabled: true }),
          });
        } catch {
          optionalWarnings.push("The briefing choice could not be saved; open Reports to enable it.");
        }
      }
      try {
        window.localStorage.setItem(SELECTED_WATCH_KEY, result.watch_id);
        window.sessionStorage.removeItem(SETUP_DRAFT_KEY);
        window.sessionStorage.removeItem(SETUP_PENDING_KEY);
      } catch { /* The server draft remains canonical even without browser storage. */ }
      setPendingSubmission(null);
      setSelectedId(result.watch_id);
      const savedMessage = result.resumed ? "Recovered the same saved paused Watch. Next: Add Sources." : "Setup saved as a paused Watch. Nothing is collecting yet. Next: Add Sources.";
      setSetupSaved([savedMessage, submission.create_report ? "Living Report preference saved." : "", submission.enable_briefing ? "Daily briefing preference saved." : "", ...optionalWarnings].filter(Boolean).join(" "));
      setSetupDraft(freshSetupDraft());
      await load(result.watch_id);
    } catch (caught) {
      setSetupError(caught);
    } finally {
      setWorking(false);
    }
  }

  async function saveSetup() {
    if (pendingSubmission) {
      setSetupValidation("A previous save may already have reached Newsroom. Retry that exact submitted save before starting another.");
      return;
    }
    const setupText = setupDraft.target_type === "research_question" ? setupDraft.question : setupDraft.interest;
    if (!setupText.trim() || !setupDraft.name.trim() || setupDraft.primary_terms.length === 0) {
      setSetupValidation(`${setupDraft.target_type === "research_question" ? "Enter a research question" : "Enter an interest"} and name, then explicitly confirm at least one primary term.`);
      return;
    }
    const submission = submissionFromDraft(setupDraft);
    persistPendingSubmission(submission);
    setPendingSubmission(submission);
    await attemptSetup(submission);
  }

  function discardSetupDraft() {
    if (pendingSubmission || !setupDraftHasContent(setupDraft)) return;
    if (!window.confirm("Discard this Watch draft? The question, name, and confirmed terms will be cleared, and nothing will be created.")) return;
    try {
      window.sessionStorage.removeItem(SETUP_DRAFT_KEY);
      window.sessionStorage.removeItem(SETUP_PENDING_KEY);
    } catch { /* The in-memory reset still clears the visible draft. */ }
    setSetupDraft(freshSetupDraft());
    setSetupError(null);
    setSetupValidation("");
    setSetupSaved("Watch draft discarded. Nothing was created.");
  }

  async function retryPendingSetup() {
    if (!pendingSubmission) return;
    await attemptSetup(pendingSubmission);
  }

  async function submitSetup(event: FormEvent) {
    event.preventDefault();
    await saveSetup();
  }

  async function createPolicy(event: FormEvent) {
    event.preventDefault(); if (!legacyPolicyName.trim()) return;
    setWorking(true); setError(null);
    try {
      const policy = await apiFetch<CollectionRecord>("/monitoring-policies", { method: "POST", body: jsonBody({ name: legacyPolicyName.trim(), allowed_channels: ["direct_http"], base_cadence_seconds: 3600, min_cadence_seconds: 900, max_cadence_seconds: 86400, priority: "normal", query_budget: 10, local_model_budget: 10, paid_budget_usd: 0 }) });
      setPolicies((items) => [...items, policy]);
      setPolicyId(policy.id);
      setLegacyPolicyName("");
    } catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function createWatch(event: FormEvent) {
    event.preventDefault(); if (!targetId.trim() || !policyId || !legacyWatchName.trim()) return;
    setWorking(true); setError(null);
    try {
      const watch = await apiFetch<Watch>("/watches", { method: "POST", body: jsonBody({ name: legacyWatchName.trim(), target_type: targetType, target_id: targetId.trim(), policy_id: policyId }) });
      setTargetId(""); setLegacyWatchName("");
      try { window.localStorage.setItem(SELECTED_WATCH_KEY, watch.id); } catch { /* Keep in-memory selection. */ }
      await load(watch.id);
    } catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function action(path: string, body?: unknown) {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try { await apiFetch(`/watches/${selectedId}/${path}`, { method: "POST", body: body ? jsonBody(body) : undefined }); await refresh(); }
    catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function pursueQuestionGap() {
    const context = selected?.research_context;
    const gap = context?.active_gap;
    if (!context || !gap || gap.status !== "open" || !selected) return;
    setWorking(true);
    setError(null);
    try {
      await apiFetch(`/research-questions/${encodeURIComponent(context.question_id)}/gaps/${encodeURIComponent(gap.id)}/pursue`, {
        method: "POST",
        body: jsonBody({ mode: "manual", query_units: 1, limits: { max_queries: 12, max_candidates: 25, max_documents: 5 } }),
      });
      await loadDetail(selected.id);
    } catch (caught) {
      setError(caught);
    } finally {
      setWorking(false);
    }
  }

  async function saveName(event: FormEvent) {
    event.preventDefault(); if (!selected || !editName.trim()) return;
    setWorking(true); setError(null);
    try { await apiFetch(`/watches/${selected.id}`, { method: "PATCH", body: jsonBody({ name: editName.trim() }) }); await refresh(selected.id); }
    catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function addTerm(input: VocabularyInput) {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try {
      await apiFetch(`/watches/${selectedId}/vocabulary`, { method: "POST", body: jsonBody(input) });
      await loadDetail(selectedId);
    } catch (caught) {
      setError(caught);
      throw caught;
    } finally { setWorking(false); }
  }

  async function reviewVocabulary(vocabularyId: string, status: "approved" | "rejected") {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try {
      await apiFetch(`/watches/${selectedId}/vocabulary/${encodeURIComponent(vocabularyId)}/review`, { method: "POST", body: jsonBody({ status }) });
      await loadDetail(selectedId);
    } catch (caught) {
      setError(caught);
      throw caught;
    } finally { setWorking(false); }
  }

  async function suggestVocabulary() {
    if (!selectedId) return;
    setWorking(true); setError(null); setSuggestionError(null);
    try {
      await apiFetch<{ items: WatchVocabularyTerm[] }>(`/watches/${selectedId}/vocabulary/suggest`, { method: "POST", body: jsonBody({ limit: 20 }) });
      await loadDetail(selectedId);
    } catch (caught) {
      setSuggestionError(caught);
      setError(caught);
    } finally { setWorking(false); }
  }

  async function addSourceCandidate(input: SourceCandidateInput) {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try {
      await apiFetch(`/watches/${selectedId}/source-candidates`, { method: "POST", body: jsonBody(input) });
      await refresh();
    } catch (caught) { setError(caught); throw caught; } finally { setWorking(false); }
  }

  async function detachSource(sourceId: string) {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try { await apiFetch(`/watches/${selectedId}/sources/${encodeURIComponent(sourceId)}`, { method: "DELETE" }); await refresh(); }
    catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function updateCadence(baseCadenceSeconds: number) {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try {
      await apiFetch(`/watches/${selectedId}/cadence`, { method: "PATCH", body: jsonBody({ base_cadence_seconds: baseCadenceSeconds }) });
      await refresh();
    } catch (caught) { setError(caught); throw caught; } finally { setWorking(false); }
  }

  async function retrySource(monitorId: string) {
    if (!monitorId) return;
    setWorking(true); setError(null);
    try {
      await apiFetch(`/monitors/${encodeURIComponent(monitorId)}`, {
        method: "PATCH",
        body: jsonBody({ enabled: true, next_check_at: new Date().toISOString() }),
      });
      await refresh();
    } catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function review(path: string, status: "approved" | "rejected") { await action(`${path}/review`, { status }); }

  function openSelectedReport() {
    if (!selected) return;
    try { window.localStorage.setItem(SELECTED_WATCH_KEY, selected.id); } catch { /* Reports can still use the current route selection. */ }
    window.location.hash = "reports";
  }

  if (loading) return <><PageHeader eyebrow="Configure" title="Watches" description="Persistent monitoring intent, approved vocabulary, Sources, and schedules." /><LoadingState label="Loading Watches" />{error && <ErrorState error={error} />}</>;

  const setupTitle = watches.length ? "Create another Watch" : "What do you want Newsroom to watch?";
  const canDiscover = Boolean(selectedId && selected?.status === "active");
  const setupText = setupDraft.target_type === "research_question" ? setupDraft.question : setupDraft.interest;
  const canSubmitSetup = !working && !pendingSubmission && Boolean(setupText.trim() && setupDraft.name.trim() && setupDraft.primary_terms.length > 0);
  const canDiscardSetup = !working && !pendingSubmission && setupDraftHasContent(setupDraft);
  return <>
    <PageHeader eyebrow="Configure / intelligent monitoring" title="Watches" description="Start with an interest in ordinary language. Newsroom saves the setup paused so you can review scope and Sources before collection begins." action={canDiscover ? <button className="secondary-button" type="button" onClick={() => void action("discover-sources", { limit: 25 })} disabled={working}>Discover Sources</button> : undefined} />
    {error && <ErrorState error={error} retry={() => void load(selectedId)} />}

    <SectionCard title={setupTitle} description="No internal IDs are required. Choose a Topic or a Research Question, confirm exact primary scope, and save a private zero-paid paused Watch. The saved Watch then opens terminology and Source review before collection.">
      <form className="stack-form" onSubmit={(event) => void submitSetup(event)} aria-busy={working}>
        <fieldset className="stack-form" aria-describedby="watch-target-help">
          <legend>Watch focus</legend>
          <label><input style={{ width: "auto", minHeight: "auto", marginRight: "8px" }} type="radio" name="watch-target-type" value="topic" checked={setupDraft.target_type === "topic"} onChange={() => changeSetupTarget("topic")} disabled={working} />Topic interest</label>
          <label><input style={{ width: "auto", minHeight: "auto", marginRight: "8px" }} type="radio" name="watch-target-type" value="research_question" checked={setupDraft.target_type === "research_question"} onChange={() => changeSetupTarget("research_question")} disabled={working} />Research question</label>
          <p id="watch-target-help" className="status-note">A Research Question Watch keeps its canonical evidence Gap, assessment, bounded Tasks, and evidence boundary visible beside Sources.</p>
        </fieldset>
        {setupDraft.target_type === "research_question" ? <>
          <label htmlFor="watch-question-source">Research Question entry</label>
          <select id="watch-question-source" value={setupDraft.question_source} onChange={(event) => {
            const source = event.target.value as "new" | "existing";
            setSetupError(null);
            setSetupSaved("");
            setSetupValidation("");
            if (source === "existing") {
              const first = researchQuestions[0]?.question ?? "";
              setSetupDraft((current) => ({ ...current, question_source: source, question: first, interest: first, name: current.name, primary_terms: first && normalizedTerm(first) !== normalizedTerm(current.question) ? [] : current.primary_terms, term_draft: current.term_draft }));
            } else {
              setSetupDraft((current) => ({ ...current, question_source: source }));
            }
          }} disabled={working}>
            <option value="new">Create a new Research Question</option>
            <option value="existing">Select an existing Research Question</option>
          </select>
          {setupDraft.question_source === "existing" ? <>
            {researchQuestionsLoading && <p className="status-note" role="status">Loading saved Research Questions…</p>}
            {researchQuestionsError && <div className="state-panel error-panel" role="alert"><strong>Existing Research Questions could not be loaded.</strong><p>{errorMessage(researchQuestionsError)}</p><button className="secondary-button" type="button" onClick={() => void loadResearchQuestions()} disabled={working}>Retry questions</button></div>}
            {!researchQuestionsLoading && !researchQuestionsError && (researchQuestions.length ? <>
              <label htmlFor="watch-existing-question">Select by question wording</label>
              <select id="watch-existing-question" value={setupDraft.question} onChange={(event) => chooseExistingQuestion(event.target.value)} disabled={working}>
                <option value="">Choose a saved Research Question…</option>
                {researchQuestions.map((item) => <option key={item.id} value={item.question}>{item.question}</option>)}
              </select>
              <p className="status-note">Only the displayed wording is submitted. Newsroom resolves it to the canonical Research Question; duplicate wording is rejected instead of guessed.</p>
            </> : <EmptyState title="No saved Research Questions" description="Create a new question with the entry choice above, or refresh after another question is saved." action={<button className="secondary-button" type="button" onClick={() => void loadResearchQuestions()} disabled={working}>Refresh questions</button>} />)}
          </> : <>
            <label htmlFor="watch-question">Research Question</label>
            <textarea id="watch-question" rows={4} maxLength={2000} value={setupDraft.question} onChange={(event) => updateQuestion(event.target.value)} placeholder="What evidence would answer this question?" aria-describedby="question-help" />
            <p id="question-help" className="status-note">Newsroom creates one canonical Research Question and one open evidence Gap. A failed or empty pursuit leaves that Gap open for another bounded attempt.</p>
          </>}
        </> : <>
          <label htmlFor="watch-interest">Interest</label>
          <textarea id="watch-interest" rows={4} maxLength={2000} value={setupDraft.interest} onChange={(event) => updateInterest(event.target.value)} placeholder="What do you want to stay on top of?" />
        </>}
        <label htmlFor="watch-setup-name">Watch name</label>
        <input id="watch-setup-name" maxLength={200} value={setupDraft.name} onChange={(event) => { setSetupSaved(""); setSetupDraft((current) => ({ ...current, name: event.target.value, name_touched: true })); }} placeholder="A short name you will recognize" />
        <label htmlFor="watch-primary-term">Primary term to confirm</label>
        <input id="watch-primary-term" maxLength={MAX_PRIMARY_TERM_LENGTH} value={setupDraft.term_draft} onChange={(event) => { setSetupValidation(""); setSetupDraft((current) => ({ ...current, term_draft: event.target.value, term_touched: true })); }} placeholder="An exact word or phrase Newsroom should match" aria-describedby="primary-term-help" />
        <p id="primary-term-help" className="status-note">This is approved monitoring scope: it drives exact relevance matching and the initial Watch query variants. It does not rename the Watch or summarize the question. Add at least one exact term; AI and synonym proposals remain separate review-only suggestions after setup.</p>
        <div className="button-row"><button className="secondary-button" type="button" onClick={addPrimaryTerm} disabled={working || !setupDraft.term_draft.trim() || setupDraft.primary_terms.length >= MAX_PRIMARY_TERMS}>Confirm primary term</button></div>
        {setupDraft.primary_terms.length > 0 && <div className="resource-list" aria-label="Confirmed primary terms">{setupDraft.primary_terms.map((primaryTerm, index) => <div className="resource-row" key={`${normalizedTerm(primaryTerm)}-${index}`}><span><strong>{primaryTerm}</strong><small>Confirmed primary monitoring term</small></span><button className="quiet-button" type="button" onClick={() => removePrimaryTerm(index)} disabled={working} aria-label={`Remove primary term ${primaryTerm}`}>Remove</button></div>)}</div>}
        <fieldset className="stack-form">
          <legend>First intelligence choices <span className="muted">(optional)</span></legend>
          <label><input style={{ width: "auto", minHeight: "auto", marginRight: "8px" }} type="checkbox" checked={setupDraft.create_report} onChange={(event) => setSetupDraft((current) => ({ ...current, create_report: event.target.checked }))} disabled={working} />Create a Living Report for this Watch</label>
          <p className="status-note">Creates a durable report now; its first revision appears only after accepted evidence-backed Claims exist.</p>
          <label><input style={{ width: "auto", minHeight: "auto", marginRight: "8px" }} type="checkbox" checked={setupDraft.enable_briefing} onChange={(event) => setSetupDraft((current) => ({ ...current, enable_briefing: event.target.checked }))} disabled={working} />Enable a daily workspace briefing</label>
          <p className="status-note">Enables the zero-paid briefing schedule in your browser’s local timezone. Configure weekly cadence or another timezone in Reports.</p>
        </fieldset>
        {setupValidation && <p className="status-note" role="alert">{setupValidation}</p>}
        {pendingSubmission && <div className="state-panel error-panel" role={setupError !== null ? "alert" : "status"}><strong>{setupError !== null ? "Could not confirm this save." : "A previous save still needs confirmation."}</strong>{setupError !== null && <p>{setupError instanceof Error ? setupError.message : "The request failed."}</p>}{isApiUnavailable(setupError) && <p>Use your installed Start Newsroom launcher to start the local service, reload this page, and retry. The exact submitted request is retained in this tab.</p>}<p>Retry will resend the original submitted {pendingSubmission.target_type === "research_question" ? "question Watch" : "Watch"} named <strong>{pendingSubmission.name}</strong> with the same approved scope. Later edits in this form are kept separate until that save is resolved.</p><button className="secondary-button" type="button" onClick={() => void retryPendingSetup()} disabled={working}>Retry the same save</button></div>}
        {setupError !== null && !pendingSubmission && <div className="state-panel error-panel" role="alert"><strong>Could not save this Watch.</strong><p>{setupError instanceof Error ? setupError.message : "The request failed."}</p>{isApiUnavailable(setupError) && <p>Use your installed Start Newsroom launcher to start the local service, reload this page, and retry.</p>}</div>}
        {setupSaved && <p className="status-note" role="status"><strong>{setupSaved}</strong></p>}
        <div className="button-row"><button className="primary-button" type="submit" disabled={!canSubmitSetup}>{working ? "Saving paused Watch…" : pendingSubmission ? "Resolve previous save first" : "Save paused Watch"}</button>{canDiscardSetup && <button className="quiet-button" type="button" onClick={discardSetupDraft}>Discard Watch draft</button>}</div>
      </form>
    </SectionCard>

    <details className="section-card">
      <summary><strong>Advanced: create from an existing canonical object</strong></summary>
      <p className="muted">These controls preserve the existing ID-based workflow for advanced use. Ordinary Watch setup above does not require IDs or a separately created policy.</p>
      <div className="content-grid">
        <SectionCard title="Existing target" description="Create a Watch against an existing Topic, Subject, Story, Source, or Research Question.">
          <form className="stack-form" onSubmit={createWatch}><label htmlFor="watch-target-type">Target type</label><select id="watch-target-type" value={targetType} onChange={(event) => setTargetType(event.target.value)}><option value="topic">Topic</option><option value="subject">Subject</option><option value="story">Story</option><option value="source">Source</option><option value="research_question">Research Question</option></select><label htmlFor="watch-target-id">Target ID</label><input id="watch-target-id" value={targetId} onChange={(event) => setTargetId(event.target.value)} placeholder="canonical target ID" /><label htmlFor="legacy-watch-name">Watch name</label><input id="legacy-watch-name" value={legacyWatchName} onChange={(event) => setLegacyWatchName(event.target.value)} /><button className="primary-button" type="submit" disabled={working || !policyId || !targetId.trim() || !legacyWatchName.trim()}>Create Watch</button></form>
        </SectionCard>
        <SectionCard title="Monitoring policy" description="Advanced cadence and budget policy controls."><form className="stack-form" onSubmit={createPolicy}><label htmlFor="policy-name">Policy name</label><input id="policy-name" value={legacyPolicyName} onChange={(event) => setLegacyPolicyName(event.target.value)} /><button className="secondary-button" type="submit" disabled={working || !legacyPolicyName.trim()}>Create policy</button></form>{policies.length ? <div className="resource-list">{policies.map((policy) => <button type="button" className={`resource-row ${policy.id === policyId ? "selected" : ""}`} key={policy.id} onClick={() => setPolicyId(policy.id)}><span><strong>{text(policy.name, "Policy")}</strong><small>{shortId(policy.id)} · {text(policy.priority, "normal")}</small></span><Badge tone={policy.id === policyId ? "mint" : "neutral"}>{policy.id === policyId ? "selected" : "select"}</Badge></button>)}</div> : <EmptyState title="No policy" description="Create an advanced policy before using the canonical-ID workflow." />}</SectionCard>
      </div>
    </details>

    <SectionCard title="Configured Watches" description={`${watches.length} Watch${watches.length === 1 ? "" : "es"}; select one to inspect its durable state.`}>{watches.length ? <div className="resource-list">{watches.map((watch) => <button type="button" className={`resource-row ${selectedId === watch.id ? "selected" : ""}`} key={watch.id} onClick={() => void selectWatch(watch.id)}><span><strong>{text(watch.name, text(watch.target_type))}</strong><small>{text(watch.target_type, "Watch")} · {text(watch.status, "active")}</small></span><Badge tone={watch.status === "active" ? "mint" : "neutral"}>{text(watch.status, "active")}</Badge></button>)}</div> : <EmptyState title="No Watches yet" description="Use the interest form above to save your first paused Watch." />}</SectionCard>
    {selected && health && <WatchDetail watch={selected} health={health} sourceHealth={sourceHealth} aiStatus={aiStatus} aiStatusError={aiStatusError} suggestionError={suggestionError} name={editName} setName={setEditName} working={working} onSave={saveName} onSuggest={suggestVocabulary} onAddTerm={addTerm} onReviewVocabulary={reviewVocabulary} onAddSource={addSourceCandidate} onDetachSource={detachSource} onUpdateCadence={updateCadence} onRetrySource={retrySource} onAction={action} onReview={review} onOpenReport={openSelectedReport} onPursueQuestion={pursueQuestionGap} />}
  </>;
}

type CadenceChoice = "hourly" | "several_times_daily" | "daily" | "custom";

const PRESET_SECONDS: Record<Exclude<CadenceChoice, "custom">, number> = {
  hourly: 3_600,
  several_times_daily: 21_600,
  daily: 86_400,
};

function numericValue(value: unknown, fallback: number): number {
  const result = typeof value === "number" ? value : Number(value);
  return Number.isFinite(result) ? result : fallback;
}

function cadenceChoice(seconds: number): CadenceChoice {
  if (seconds === PRESET_SECONDS.hourly) return "hourly";
  if (seconds === PRESET_SECONDS.several_times_daily) return "several_times_daily";
  if (seconds === PRESET_SECONDS.daily) return "daily";
  return "custom";
}

function cadenceLabel(seconds: number): string {
  if (seconds % 86_400 === 0) return `every ${seconds / 86_400} day${seconds === 86_400 ? "" : "s"}`;
  if (seconds % 3_600 === 0) return `every ${seconds / 3_600} hour${seconds === 3_600 ? "" : "s"}`;
  if (seconds % 60 === 0) return `every ${seconds / 60} minute${seconds === 60 ? "" : "s"}`;
  return `every ${seconds} seconds`;
}

function formatNextCheck(value: string | null | undefined): string {
  if (!value) return "Not scheduled while this Watch is paused";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" }).format(date);
}

function CadenceSetup({ watch, health, policy, working, onSave }: { watch: Watch; health: Health; policy?: CollectionRecord; working: boolean; onSave: (seconds: number) => Promise<void> }) {
  const base = numericValue(policy?.base_cadence_seconds, 3_600);
  const minimum = numericValue(policy?.min_cadence_seconds, 1);
  const maximum = numericValue(policy?.max_cadence_seconds, 31_536_000);
  const [choice, setChoice] = useState<CadenceChoice>(cadenceChoice(base));
  const [seconds, setSeconds] = useState(String(base));
  const [validation, setValidation] = useState("");

  useEffect(() => {
    setChoice(cadenceChoice(base));
    setSeconds(String(base));
    setValidation("");
  }, [policy?.id, base]);

  function choose(value: CadenceChoice) {
    setChoice(value);
    if (value !== "custom") setSeconds(String(PRESET_SECONDS[value]));
    setValidation("");
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    const value = Number(seconds);
    if (!Number.isInteger(value) || value < minimum || value > maximum) {
      setValidation(`Choose a cadence between ${cadenceLabel(minimum)} and ${cadenceLabel(maximum)}.`);
      return;
    }
    try { await onSave(value); setValidation(""); } catch { /* The parent keeps the last good policy and renders recovery. */ }
  }

  const channels = Array.isArray(policy?.allowed_channels) ? policy.allowed_channels.map(String) : [];
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "local time";
  return <SectionCard title="Cadence" description="Choose how often this Watch should be checked. These choices update only this Watch's policy and do not start collection.">
    <form className="stack-form" onSubmit={(event) => void save(event)}>
      <label htmlFor="watch-cadence-choice">Check frequency</label>
      <select id="watch-cadence-choice" value={choice} onChange={(event) => choose(event.target.value as CadenceChoice)} disabled={working}>
        <option value="hourly">Hourly</option>
        <option value="several_times_daily">Several times daily (every 6 hours)</option>
        <option value="daily">Daily</option>
        <option value="custom">Custom interval</option>
      </select>
      {choice === "custom" && <><label htmlFor="watch-cadence-seconds">Custom interval in seconds</label><input id="watch-cadence-seconds" type="number" min={minimum} max={maximum} step={1} value={seconds} onChange={(event) => { setSeconds(event.target.value); setValidation(""); }} onInvalid={(event) => { event.preventDefault(); setValidation(`Choose a cadence between ${cadenceLabel(minimum)} and ${cadenceLabel(maximum)}.`); }} aria-describedby="watch-cadence-help" /><p id="watch-cadence-help" className="status-note">Supported range: {cadenceLabel(minimum)} to {cadenceLabel(maximum)}.</p></>}
      {validation && <p className="status-note" role="alert">{validation}</p>}
      <div className="stats-grid"><Stat label="Saved cadence" value={cadenceLabel(base)} /><Stat label="Next check" value={formatNextCheck(health.next_scheduled_run)} /><Stat label="Timezone" value={timezone} /></div>
      <p className="muted">Supported channels: {channels.length ? channels.join(", ") : "none configured"}. Paid mode: {numericValue(policy?.paid_budget_usd, 0) === 0 ? "zero paid calls" : "configured server policy"}. {watch.status === "paused" ? "This Watch remains paused until you explicitly start it." : "This change preserves the Watch's current state."}</p>
      <button className="secondary-button" type="submit" disabled={working}>{working ? "Saving cadence…" : "Save cadence"}</button>
    </form>
  </SectionCard>;
}

function SourceSetup({ working, onCreate }: { working: boolean; onCreate: (input: SourceCandidateInput) => Promise<void> }) {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<CollectionRecord[]>([]);
  const [searched, setSearched] = useState(false);
  const [searchError, setSearchError] = useState<unknown>(null);
  const [manualName, setManualName] = useState("");
  const [homepageUrl, setHomepageUrl] = useState("");
  const [feedUrl, setFeedUrl] = useState("");
  const [rationale, setRationale] = useState("Added manually by the owner.");
  const [formError, setFormError] = useState("");

  async function search(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (!value) { setSearchError(new Error("Enter a Source name or URL to search.")); return; }
    setSearchError(null); setSearched(true);
    try { setMatches((await apiList<CollectionRecord>(`/sources?q=${encodeURIComponent(value)}&page_size=25`)).items); }
    catch (caught) { setSearchError(caught); setMatches([]); }
  }

  async function previewExisting(source: CollectionRecord) {
    setFormError("");
    try {
      await onCreate({
        source_id: source.id,
        name: text(source.name, "Existing Source"),
        discovery_method: "existing_source",
        rationale: "Existing Source selected by name or URL; review before attaching.",
      });
      setQuery(""); setMatches([]); setSearched(false);
    } catch (caught) { setFormError(caught instanceof Error ? caught.message : "Could not create the Source preview."); }
  }

  async function previewManual(event: FormEvent) {
    event.preventDefault();
    setFormError("");
    if (!manualName.trim() || !homepageUrl.trim() || !rationale.trim()) {
      setFormError("Enter a Source name, homepage or feed URL, and a reason before previewing.");
      return;
    }
    try {
      await onCreate({
        name: manualName.trim(),
        homepage_url: homepageUrl.trim(),
        feed_url: feedUrl.trim() || undefined,
        discovery_method: "manual",
        rationale: rationale.trim(),
      });
      setManualName(""); setHomepageUrl(""); setFeedUrl(""); setRationale("Added manually by the owner.");
    } catch (caught) { setFormError(caught instanceof Error ? caught.message : "Could not create the Source preview."); }
  }

  return <SectionCard title="Add Sources" description="Search by name or URL to reuse an existing Source, or preview a manual page/feed. A preview is never attached until you explicitly approve it.">
    <form className="inline-form" onSubmit={(event) => void search(event)}>
      <label htmlFor="existing-source-search">Find an existing Source</label>
      <input id="existing-source-search" value={query} onChange={(event) => { setQuery(event.target.value); setSearchError(null); }} placeholder="Source name or URL" />
      <button className="secondary-button" type="submit" disabled={working}>Search Sources</button>
    </form>
    {searchError !== null && <p className="status-note" role="alert">{searchError instanceof Error ? searchError.message : "Source search failed."}</p>}
    {searched && (matches.length ? <div className="resource-list" aria-label="Existing Source search results">{matches.map((source) => <div className="resource-row" key={source.id}><span><strong>{text(source.name, "Unnamed Source")}</strong><small>{text(source.domain, text(source.homepage_url, "No domain recorded"))}</small></span><button className="secondary-button" type="button" onClick={() => void previewExisting(source)} disabled={working || !text(source.homepage_url, text(source.feed_url, ""))}>Preview Source</button></div>)}</div> : <EmptyState title="No matching Sources" description="Try another name or URL, or use the manual preview below." />)}
    <form className="stack-form" onSubmit={(event) => void previewManual(event)}>
      <h3>Preview a manual Source</h3>
      <p className="muted">Unsafe, local, and private URLs are rejected by the server before anything is saved.</p>
      <label htmlFor="manual-source-name">Source name</label>
      <input id="manual-source-name" value={manualName} onChange={(event) => setManualName(event.target.value)} placeholder="Example: NASA News" />
      <label htmlFor="manual-source-homepage">Homepage or page URL</label>
      <input id="manual-source-homepage" type="url" value={homepageUrl} onChange={(event) => setHomepageUrl(event.target.value)} placeholder="https://example.org/news" />
      <label htmlFor="manual-source-feed">Feed URL (optional)</label>
      <input id="manual-source-feed" type="url" value={feedUrl} onChange={(event) => setFeedUrl(event.target.value)} placeholder="https://example.org/feed.xml" />
      <label htmlFor="manual-source-rationale">Why this Source?</label>
      <textarea id="manual-source-rationale" rows={2} value={rationale} onChange={(event) => setRationale(event.target.value)} />
      {formError && <p className="status-note" role="alert">{formError}</p>}
      <button className="secondary-button" type="submit" disabled={working}>Preview Source for approval</button>
    </form>
  </SectionCard>;
}

function vocabularyStatusLabel(item: WatchVocabularyTerm): string {
  if (item.status === "suggested") return "suggested · inactive";
  if (item.status === "approved") return vocabularyEnabled(item) ? "approved · active" : "approved · inactive";
  if (item.status === "rejected") return "rejected · excluded";
  return item.status;
}

function vocabularyBadgeTone(item: WatchVocabularyTerm): "neutral" | "mint" | "amber" | "coral" {
  if (item.kind === "exclude") return item.status === "approved" ? "coral" : "amber";
  if (item.status === "approved" && vocabularyEnabled(item)) return "mint";
  if (item.status === "suggested") return "amber";
  return "neutral";
}

function VocabularyRow({ item, children }: { item: WatchVocabularyTerm; children?: ReactNode }) {
  const origin = item.origin === "ai" ? "Provider suggestion" : item.origin === "deterministic" ? "Deterministic suggestion" : text(item.origin, "Manual");
  return <div className="resource-row">
    <span>
      <strong>{text(item.term)}</strong>
      <small>{vocabularyKindLabel(item.kind)} · {origin}{item.expansion_of ? ` · Expansion of ${item.expansion_of}` : ""}</small>
      {item.rationale && <small>Why: {item.rationale}</small>}
    </span>
    <div className="button-row ai-provider-actions"><Badge tone={vocabularyBadgeTone(item)}>{vocabularyStatusLabel(item)}</Badge>{children}</div>
  </div>;
}

type TerminologyReviewProps = {
  watch: Watch;
  vocabulary: WatchVocabularyTerm[];
  aiStatus: AIStatus | null;
  aiStatusError: unknown;
  suggestionError: unknown;
  working: boolean;
  onSuggest: () => Promise<void>;
  onAdd: (input: VocabularyInput) => Promise<void>;
  onReview: (id: string, status: "approved" | "rejected") => Promise<void>;
};

function TerminologyReview({ watch, vocabulary, aiStatus, aiStatusError, suggestionError, working, onSuggest, onAdd, onReview }: TerminologyReviewProps) {
  const [term, setTerm] = useState("");
  const [kind, setKind] = useState<VocabularyKind>("alias");
  const [expansionOf, setExpansionOf] = useState("");
  const [rationale, setRationale] = useState("Added manually by the owner.");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTerm, setEditTerm] = useState("");
  const [editKind, setEditKind] = useState<VocabularyKind>("alias");
  const [editExpansionOf, setEditExpansionOf] = useState("");
  const [editRationale, setEditRationale] = useState("");
  const [formError, setFormError] = useState("");
  const route = vocabularyRouteSummary(aiStatus, aiStatusError, watch.policy);
  const suggested = vocabulary.filter((item) => item.status === "suggested");
  const approved = vocabulary.filter((item) => item.status === "approved");
  const rejected = vocabulary.filter((item) => item.status === "rejected");

  async function addManualTerm(event: FormEvent) {
    event.preventDefault();
    setFormError("");
    if (!term.trim()) { setFormError("Enter a term before adding it to approved scope."); return; }
    try {
      await onAdd({ term: term.trim(), kind, expansion_of: expansionOf.trim() || undefined, rationale: rationale.trim() || "Added manually by the owner." });
      setTerm(""); setExpansionOf(""); setRationale("Added manually by the owner.");
    } catch (caught) { setFormError(errorMessage(caught)); }
  }

  function beginEdit(item: WatchVocabularyTerm) {
    setFormError(""); setEditingId(item.id); setEditTerm(item.term); setEditKind(item.kind); setEditExpansionOf(item.expansion_of ?? ""); setEditRationale(item.rationale ?? "");
  }

  function cancelEdit() {
    setEditingId(null); setEditTerm(""); setEditExpansionOf(""); setEditRationale("");
  }

  async function saveEdit(event: FormEvent, item: WatchVocabularyTerm) {
    event.preventDefault();
    setFormError("");
    if (!editTerm.trim()) { setFormError("Enter a term before saving the edited suggestion."); return; }
    const input: VocabularyInput = { term: editTerm.trim(), kind: editKind, expansion_of: editExpansionOf.trim() || undefined, rationale: editRationale.trim() || "Edited by the owner during terminology review." };
    try { await onAdd(input); }
    catch (caught) { setFormError(errorMessage(caught)); return; }
    try { await onReview(item.id, "rejected"); }
    catch (caught) { setFormError(`The edited term was saved, but the original suggestion could not be rejected: ${errorMessage(caught)}`); return; }
    cancelEdit();
  }

  async function reviewItem(item: WatchVocabularyTerm, status: "approved" | "rejected") {
    setFormError("");
    try { await onReview(item.id, status); }
    catch (caught) { setFormError(errorMessage(caught)); }
  }

  return <SectionCard title="Review terminology" description="Confirm what Newsroom should mean before you add Sources or start collection. Suggested terms are proposals only; approval is the server-side action that makes a term active." action={<button className="secondary-button" type="button" onClick={() => void onSuggest()} disabled={working}>{working ? "Working…" : "Suggest terms"}</button>}>
    <div className="state-panel" role="status">
      <strong>Provider route and cost</strong>
      <p><Badge tone={route.tone}>{route.title}</Badge> {route.detail}</p>
      <p>Every suggestion request is explicit and bounded. No provider call happens while typing, and rejected or suggested terms never enter monitoring scope.</p>
    </div>
    {suggestionError !== null && suggestionError !== undefined && <div className="state-panel error-panel" role="alert"><strong>Suggestions could not be loaded.</strong><p>{errorMessage(suggestionError)}</p>{isApiUnavailable(suggestionError) && <p>Use the installed Start Newsroom launcher, reload this page, and retry. Manual terms remain available.</p>}<button className="secondary-button" type="button" onClick={() => void onSuggest()} disabled={working}>Retry suggestions</button></div>}
    <form className="stack-form" onSubmit={(event) => void addManualTerm(event)}>
      <h3>Manual terms always available</h3>
      <p className="muted">Add an approved term directly when the provider is disabled, unavailable, or not useful. Exclusions are explicit and remain visible in review history.</p>
      <label htmlFor="watch-vocabulary-term">Term or meaning</label>
      <input id="watch-vocabulary-term" value={term} onChange={(event) => setTerm(event.target.value)} maxLength={300} placeholder="Alternate name, acronym, or excluded meaning" />
      <label htmlFor="watch-vocabulary-kind">Kind</label>
      <select id="watch-vocabulary-kind" value={kind} onChange={(event) => setKind(event.target.value as VocabularyKind)}>
        {VOCABULARY_KIND_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <label htmlFor="watch-vocabulary-expansion">Expansion of (optional)</label>
      <input id="watch-vocabulary-expansion" value={expansionOf} onChange={(event) => setExpansionOf(event.target.value)} maxLength={300} placeholder="Link an acronym to its full phrase" />
      <label htmlFor="watch-vocabulary-rationale">Why this term?</label>
      <textarea id="watch-vocabulary-rationale" rows={2} value={rationale} onChange={(event) => setRationale(event.target.value)} maxLength={2000} />
      {formError && <p className="status-note" role="alert">{formError}</p>}
      <button className="secondary-button" type="submit" disabled={working || !term.trim()}>{working ? "Saving term…" : "Add approved term"}</button>
    </form>
    <div className="content-grid">
      <div>
        <h3>Suggested terminology</h3>
        <p className="muted">Provider and deterministic proposals are inert until you approve them on the server.</p>
        {suggested.length ? <div className="resource-list">{suggested.map((item) => editingId === item.id ? <form className="stack-form" key={item.id} onSubmit={(event) => void saveEdit(event, item)} aria-label={`Edit suggested term ${item.term}`}>
          <label htmlFor={`edit-vocabulary-term-${item.id}`}>Term</label><input id={`edit-vocabulary-term-${item.id}`} value={editTerm} onChange={(event) => setEditTerm(event.target.value)} maxLength={300} />
          <label htmlFor={`edit-vocabulary-kind-${item.id}`}>Kind</label><select id={`edit-vocabulary-kind-${item.id}`} value={editKind} onChange={(event) => setEditKind(event.target.value as VocabularyKind)}>{VOCABULARY_KIND_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
          <label htmlFor={`edit-vocabulary-expansion-${item.id}`}>Expansion of (optional)</label><input id={`edit-vocabulary-expansion-${item.id}`} value={editExpansionOf} onChange={(event) => setEditExpansionOf(event.target.value)} maxLength={300} />
          <label htmlFor={`edit-vocabulary-rationale-${item.id}`}>Why this term?</label><textarea id={`edit-vocabulary-rationale-${item.id}`} rows={2} value={editRationale} onChange={(event) => setEditRationale(event.target.value)} maxLength={2000} />
          <div className="button-row"><button className="secondary-button" type="submit" disabled={working}>Save edited term</button><button className="quiet-button" type="button" onClick={cancelEdit} disabled={working}>Cancel</button></div>
        </form> : <VocabularyRow key={item.id} item={item}><button className="secondary-button" type="button" onClick={() => beginEdit(item)} disabled={working}>Edit</button><button className="secondary-button" type="button" onClick={() => void reviewItem(item, "approved")} disabled={working}>Approve</button><button className="quiet-button" type="button" onClick={() => void reviewItem(item, "rejected")} disabled={working}>Reject</button></VocabularyRow>)}</div> : <EmptyState title="No suggestions waiting for review" description="Newsroom has no new terminology proposals. You can add an approved term manually at any time." />}
      </div>
      <div>
        <h3>Approved monitoring scope</h3>
        <p className="muted">Only terms shown as approved and active affect future Watch queries. Already acquired material keeps its original pinned scope.</p>
        {approved.length ? <div className="resource-list">{approved.map((item) => <VocabularyRow key={item.id} item={item} />)}</div> : <EmptyState title="No additional approved terms" description="The confirmed primary Topic terms remain above. Add or approve supporting terminology only when it matches your intended meaning." />}
      </div>
    </div>
    <div>
      <h3>Rejected terminology</h3>
      {rejected.length ? <div className="resource-list">{rejected.map((item) => <VocabularyRow key={item.id} item={item} />)}</div> : <p className="muted">No rejected terms yet. Rejections are retained so the same proposal does not silently return.</p>}
    </div>
  </SectionCard>;
}

function sourceCandidateMethod(item: CollectionRecord): { label: string; tone: "neutral" | "mint" | "amber" } {
  const method = text(item.discovery_method, "manual");
  if (method === "ai_suggestion") return { label: "Unverified recommendation", tone: "amber" };
  if (method === "existing_source") return { label: "Existing Source", tone: "mint" };
  if (method === "document_link" || method === "feed_discovery") return { label: "Observed corpus signal", tone: "neutral" };
  return { label: "Manual preview", tone: "neutral" };
}

function SourceRecommendations({ candidates, health, isUnstartedDraft, working, onDiscover, onReview }: { candidates: CollectionRecord[]; health: Health; isUnstartedDraft: boolean; working: boolean; onDiscover: () => Promise<void>; onReview: (path: string, status: "approved" | "rejected") => Promise<void> }) {
  const canDiscover = health.status === "active";
  const lastRun = health.last_discovery_run ? formatDate(health.last_discovery_run) : "Not run yet";
  const discoveryStatus = text(health.last_discovery_status, "not run").replace(/_/g, " ");
  return <SectionCard title="Recommended Sources" description="Recommendations and corpus signals are previews only. One canonical URL appears once per Watch; rejected rows remain in history and are not silently re-added." action={<button className="secondary-button" type="button" onClick={() => void onDiscover()} disabled={working || !canDiscover}>{health.last_error && canDiscover ? "Retry recommendations" : "Recommend Sources"}</button>}>
    <div className="state-panel" role="status">
      <strong>Recommendation provenance</strong>
      <p>Model recommendations are labeled <Badge tone="amber">unverified</Badge> and remain inactive until you approve them. The server records the source-discovery route and review state; approval does not fetch the URL or create evidence.</p>
      <p className="status-note">Last recommendation run: {lastRun} · status: {discoveryStatus} · {health.discovery_enabled ? "bounded assistance available when the Watch is active and its information-need corpus is empty" : "recommendation route is disabled"}.</p>
    </div>
    {health.last_error && <div className="state-panel error-panel" role="alert"><strong>Recommendations or collection need attention.</strong><p>{health.last_error}</p>{canDiscover && <button className="secondary-button" type="button" onClick={() => void onDiscover()} disabled={working}>Retry recommendations</button>}<p className="status-note">Manual fallback remains available above, and existing successful Sources stay attached below.</p></div>}
    {candidates.length ? <div className="resource-list" aria-label="Recommended Source previews">{candidates.map((item) => { const method = sourceCandidateMethod(item); const status = text(item.status, "suggested"); const provenance = item.provenance && typeof item.provenance === "object" ? item.provenance as Record<string, unknown> : {}; const url = text(item.homepage_url, text(item.feed_url, "No URL recorded")); return <div className="resource-row" key={item.id}><span><strong>{text(item.name, "Unnamed Source")}</strong><small>{url}</small><small><Badge tone={method.tone}>{method.label}</Badge> · {text(item.discovery_method, "manual").replace(/_/g, " ")}</small><small>{text(item.rationale, "No rationale recorded")}</small>{method.label === "Unverified recommendation" && <small>Recommendation provenance: {text(provenance.capability, "source_discovery")} · {text(provenance.trigger, "empty_corpus")} · unverified</small>}{text(item.authority_context, "") && <small>Authority context: {text(item.authority_context, "")}</small>}{text(item.limitations, "") && <small>Limitations: {text(item.limitations, "")}</small>}</span><div className="button-row"><Badge tone={status === "approved" ? "mint" : status === "rejected" ? "neutral" : method.tone === "amber" ? "amber" : "neutral"}>{status === "suggested" ? "Review needed" : status}</Badge>{status === "suggested" && <><button className="secondary-button" type="button" onClick={() => void onReview(`source-candidates/${item.id}`, "approved")} disabled={working}>Approve and attach</button><button className="quiet-button" type="button" onClick={() => void onReview(`source-candidates/${item.id}`, "rejected")} disabled={working}>Reject</button></>}</div></div>; })}</div> : <EmptyState title="No recommendations yet" description={isUnstartedDraft ? "Manual fallback: search an existing Source or preview a page/feed above. Nothing is attached until you approve it." : "Manual fallback: add or search a Source above. A bounded recommendation run may return previews only when the information-need corpus is empty."} />}
  </SectionCard>;
}

function sourceHealthSummary(source: WatchSource, detail?: SourceHealth): { label: string; tone: "neutral" | "mint" | "amber" | "coral"; outcome: string; failure: string | null; checkedAt: string | null } {
  const monitor = source.monitor;
  const latest = detail?.latest ?? null;
  const outcome = text(latest?.outcome, text(monitor?.last_result, "not_run"));
  const failure = outcome === "error" || outcome === "retired" || Boolean(latest?.error_code) ? text(latest?.error_code, outcome.replace(/_/g, " ")) : null;
  if (failure) return { label: "Failed", tone: "coral", outcome, failure, checkedAt: latest?.observed_at ?? (typeof monitor?.last_run_at === "string" ? monitor.last_run_at : null) };
  if (outcome === "partial") return { label: "Partial result", tone: "amber", outcome, failure: null, checkedAt: latest?.observed_at ?? (typeof monitor?.last_run_at === "string" ? monitor.last_run_at : null) };
  if (outcome === "not_run") return { label: "Not checked", tone: "neutral", outcome, failure: null, checkedAt: null };
  return { label: outcome === "no_change" ? "Healthy · no change" : "Healthy · change found", tone: "mint", outcome, failure: null, checkedAt: latest?.observed_at ?? (typeof monitor?.last_run_at === "string" ? monitor.last_run_at : null) };
}

function AttachedSources({ sources, sourceHealth, working, onDetach, onRetry }: { sources: WatchSource[]; sourceHealth: SourceHealthMap; working: boolean; onDetach: (sourceId: string) => Promise<void>; onRetry: (monitorId: string) => Promise<void> }) {
  return <SectionCard title="Attached Sources · Source health" description="Each Source is shown separately so one failed page or feed never hides a successful sibling. Detach changes only this Watch relationship; editing a shared Source in Sources affects every Watch that uses it.">{sources.length ? <div className="resource-list">{sources.map((item) => { const source = item.source; const monitor = item.monitor; const monitorId = text(monitor?.id, ""); const summary = sourceHealthSummary(item, monitorId ? sourceHealth[monitorId] : undefined); const page = text(source?.homepage_url, ""); const feed = text(source?.feed_url, ""); const detailError = monitorId ? sourceHealth[monitorId]?.error : undefined; return <div className="resource-row" key={text(source?.id, monitorId)}><span><strong>{text(source?.name, "Unnamed Source")}</strong><small>Page: {page || "not configured"}</small><small>Feed: {feed || "not configured"}</small><small>Last check: {summary.checkedAt ? formatDate(summary.checkedAt) : "Not checked yet"} · outcome: {summary.outcome.replace(/_/g, " ")}</small><small>Last failure: {summary.failure ? `${summary.failure}${summary.checkedAt ? ` · ${formatDate(summary.checkedAt)}` : ""}` : "None recorded"}</small>{detailError && <small>Health detail unavailable: {detailError}. Showing the last known monitor state.</small>}</span><div className="button-row"><Badge tone={summary.tone}>{summary.label}</Badge>{summary.failure && monitorId && <button className="secondary-button" type="button" onClick={() => void onRetry(monitorId)} disabled={working}>Retry source</button>}<button className="quiet-button" type="button" onClick={() => void onDetach(text(source?.id, ""))} disabled={working}>Detach</button></div></div>; })}</div> : <EmptyState title="No attached Sources" description="Approve a Source preview to attach it. Manual fallback remains available above; nothing is collecting until you explicitly start the Watch." />}</SectionCard>;
}

function researchAssessmentTone(state: string): "neutral" | "mint" | "amber" | "coral" {
  if (state === "supported" || state === "resolved") return "mint";
  if (state === "contradicted") return "coral";
  if (state === "partially_answered") return "amber";
  return "neutral";
}

function researchTaskLabel(status: string): string {
  if (status === "completed_no_findings") return "No findings";
  if (status === "completed_with_evidence") return "Evidence ready";
  if (status === "completed_with_candidates") return "Candidates need review";
  if (status === "failed") return "Pursuit failed";
  if (status === "cancelled") return "Pursuit cancelled";
  return "Pursuit in progress";
}

function QuestionResearchContext({ context, working, onPursue }: { context: WatchResearchContext; working: boolean; onPursue: () => Promise<void> }) {
  const state = String(context.assessment_state || "open");
  const gaps = context.gaps ?? [];
  const activeGap = context.active_gap ?? gaps.find((gap) => gap.status === "open" || gap.status === "pursuing" || gap.status === "blocked") ?? null;
  const tasks = context.tasks ?? [];
  const latestTask = tasks[tasks.length - 1];
  const taskStatus = String(latestTask?.status ?? "");
  const outcome = latestTask?.outcome && typeof latestTask.outcome === "object" ? latestTask.outcome : {};
  const outcomeNote = typeof outcome.outcome_note === "string" ? outcome.outcome_note : "";
  const recovery = taskStatus === "completed_no_findings" || taskStatus === "failed" || taskStatus === "cancelled";
  return <SectionCard title="Research Question context" description="This Watch is bound to a canonical question. Assessment, evidence Gaps, and bounded Task outcomes stay visible beside Source setup." action={<Badge tone={researchAssessmentTone(state)}>{state}</Badge>}>
    <div className="stats-grid"><Stat label="Open evidence Gaps" value={context.open_gap_count} tone={context.open_gap_count ? "amber" : "mint"} /><Stat label="Bounded Tasks" value={tasks.length} /><Stat label="Evidence gate" value={context.evidence_gated ? "Required" : "Review"} tone={context.evidence_gated ? "amber" : "neutral"} /></div>
    <div className="content-grid">
      <div><h3>Question</h3><p>{context.question}</p><p className="status-note">Assessment: {state}. {context.assessment_explanation || "No assessment explanation has been recorded yet."}</p></div>
      <div><h3>Active evidence Gap</h3>{activeGap ? <div className="state-panel" role="status"><strong>{activeGap.description}</strong><p>Status: {activeGap.status}</p>{activeGap.status === "open" && <button className="secondary-button" type="button" onClick={() => void onPursue()} disabled={working}>{working ? "Starting bounded pursuit…" : "Pursue open Gap"}</button>}{activeGap.status === "pursuing" && <p className="status-note">A bounded Task is already pursuing this Gap.</p>}{activeGap.status === "blocked" && <p className="status-note">This Gap is blocked; review the question workspace before retrying it.</p>}</div> : <p className="muted">No open evidence Gap is waiting for pursuit.</p>}</div>
    </div>
    {latestTask && <div className={`state-panel ${taskStatus === "failed" ? "error-panel" : ""}`} role={taskStatus === "failed" ? "alert" : "status"}><strong>Latest bounded Task: {researchTaskLabel(taskStatus)}</strong><p>{outcomeNote || (taskStatus === "completed_no_findings" ? "The bounded search completed without qualifying findings." : taskStatus === "failed" ? "The bounded pursuit failed before producing qualifying evidence." : "The latest bounded Task is recorded separately from trusted evidence.")}</p>{recovery && activeGap?.status === "open" && <p className="status-note">Gap remains open. Review the outcome and use Pursue open Gap to try another bounded attempt.</p>}</div>}
    <p className="status-note"><strong>Evidence boundary:</strong> {context.candidate_note || "Hypotheses remain review-only until canonical evidence is verified; candidate material is not an accepted Claim."}</p>
    {gaps.length > 1 && <div><h3>Other question Gaps</h3><ul className="compact-list">{gaps.slice(1, 10).map((gap) => <li key={gap.id}><Badge tone={gap.status === "satisfied" ? "mint" : gap.status === "dismissed" ? "neutral" : "amber"}>{gap.status}</Badge> {gap.description}</li>)}</ul></div>}
  </SectionCard>;
}

function WatchDetail({ watch, health, sourceHealth, aiStatus, aiStatusError, suggestionError, name, setName, working, onSave, onSuggest, onAddTerm, onReviewVocabulary, onAddSource, onDetachSource, onUpdateCadence, onRetrySource, onAction, onReview, onOpenReport, onPursueQuestion }: { watch: Watch; health: Health; sourceHealth: SourceHealthMap; aiStatus: AIStatus | null; aiStatusError: unknown; suggestionError: unknown; name: string; setName: (value: string) => void; working: boolean; onSave: (event: FormEvent) => void; onSuggest: () => Promise<void>; onAddTerm: (input: VocabularyInput) => Promise<void>; onReviewVocabulary: (id: string, status: "approved" | "rejected") => Promise<void>; onAddSource: (input: SourceCandidateInput) => Promise<void>; onDetachSource: (sourceId: string) => Promise<void>; onUpdateCadence: (seconds: number) => Promise<void>; onRetrySource: (monitorId: string) => Promise<void>; onAction: (path: string, body?: unknown) => Promise<void>; onReview: (path: string, status: "approved" | "rejected") => Promise<void>; onOpenReport: () => void; onPursueQuestion: () => Promise<void> }) {
  const vocabulary = watch.vocabulary ?? [];
  const primaryTerms = watch.primary_terms ?? [];
  const candidates = watch.source_candidates ?? [];
  const sources = watch.sources ?? [];
  const review = health.review;
  const progress = health.progress;
  const canResume = health.status !== "active" && Boolean(review?.ready_to_start);
  const isUnstartedDraft = health.status === "paused" && sources.length === 0;
  const progressTone = progress?.state === "ready" || progress?.state === "no-change" ? "mint" : progress?.state === "error" ? "coral" : progress?.state === "deferred" || progress?.state === "irrelevant" ? "amber" : "neutral";
  return <>
    {isUnstartedDraft && <SectionCard title="Setup saved" description="This Watch is paused and is not collecting yet."><div className="button-row"><Badge tone="neutral">Paused</Badge><Badge tone="amber">Next: Add Sources</Badge></div><p className="muted">Your approved primary terms are stored. Source selection is the next setup step; starting collection comes later after Sources and cadence are reviewed.</p></SectionCard>}
    <SectionCard title={text(watch.name)} description={`${text(watch.target_type, "Watch")} monitoring intent`} action={<div className="button-row" style={{ flexWrap: "wrap", justifyContent: "flex-end", minWidth: 0 }}><Badge tone={health.status === "active" ? "mint" : "neutral"}>{health.status}</Badge><button className="secondary-button" type="button" onClick={onOpenReport} disabled={working}>Open Living Report</button>{health.status === "active" && <button className="quiet-button" type="button" onClick={() => void onAction("pause")} disabled={working}>Pause</button>}{canResume && <button className="primary-button" type="button" onClick={() => void onAction("resume")} disabled={working}>{health.status === "paused" ? "Start Watch" : "Resume Watch"}</button>}{sources.length > 0 && <button className="secondary-button" type="button" onClick={() => void onAction("vocabulary/suggest", { limit: 20 })} disabled={working}>Suggest vocabulary</button>}</div>}>
      <div className="stats-grid"><Stat label="Active Sources" value={health.active_source_count} tone="mint" /><Stat label="Pending terms" value={health.pending_vocabulary_suggestion_count} tone="amber" /><Stat label="Pending Sources" value={health.pending_source_candidate_count} tone="amber" /><Stat label="Last successful collection" value={health.last_success ? formatDate(health.last_success) : watch.status === "paused" ? "Not started" : "None yet"} /><Stat label="Next run" value={formatDate(text(health.next_scheduled_run, "Not scheduled"))} /></div>
      <form className="inline-form" onSubmit={onSave}><label htmlFor="selected-watch-name">Edit name</label><input id="selected-watch-name" value={name} onChange={(event) => setName(event.target.value)} /><button className="secondary-button" type="submit" disabled={working}>Save</button></form>
      {health.last_error && <p className="status-note">Recent error: {health.last_error}</p>}
    </SectionCard>
    {watch.research_context && <QuestionResearchContext context={watch.research_context} working={working} onPursue={onPursueQuestion} />}
    {review && <SectionCard title="Review before Start" description="Newsroom will start only from this saved interest, approved scope, Sources, cadence, and budget mode. Starting activates existing Monitors; it does not claim that a result is ready.">
      <div className="stats-grid"><Stat label="Saved interest" value={review.interest || "Not recorded"} /><Stat label="Approved terms" value={review.approved_terms.length} tone={review.approved_terms.length ? "mint" : "amber"} /><Stat label="Cadence" value={cadenceLabel(review.cadence.base_cadence_seconds)} /><Stat label="Budget mode" value={review.paid_mode === "zero-paid" ? "Zero-paid" : "Configured paid budget"} tone={review.paid_mode === "zero-paid" ? "mint" : "amber"} /></div>
      <div className="content-grid">
        <div><h3>Approved scope</h3>{review.approved_terms.length ? <ul className="compact-list">{review.approved_terms.map((item) => <li key={item}><Badge tone="mint">approved</Badge> {item}</li>)}</ul> : <p className="muted">No approved terms are saved.</p>}</div>
        <div><h3>Approved Sources</h3>{review.sources.length ? <ul className="compact-list">{review.sources.map((item) => <li key={`${item.name}-${item.domain}`}><Badge tone={item.usable ? "mint" : "coral"}>{item.usable ? "usable" : "not usable"}</Badge> {item.name}{item.domain ? ` · ${item.domain}` : ""}</li>)}</ul> : <p className="muted">No approved Sources yet.</p>}</div>
      </div>
      <p className="muted">Allowed channels: {review.supported_channels.length ? review.supported_channels.join(", ") : "none configured"}. {review.cadence.next_check_at ? `Next check: ${formatNextCheck(review.cadence.next_check_at)}.` : "Next check will be scheduled when this Watch starts."}</p>
      {!review.ready_to_start && <div className="state-panel empty-panel" role="status"><strong>Complete this review before Start.</strong><ul className="compact-list">{review.blockers.map((item) => <li key={item}>{item}</li>)}</ul></div>}
    </SectionCard>}
    {progress && <SectionCard title="First-value progress" description="This status is read from persisted backend state. It distinguishes an attempt from a verified result." action={<Badge tone={progressTone}>{progress.label}</Badge>}>
      <div aria-live="polite"><p>{progress.detail}</p><div className="stats-grid"><Stat label="State" value={progress.label} tone={progressTone} /><Stat label="Last attempt" value={progress.last_attempt ? formatDate(progress.last_attempt) : "Not attempted"} /><Stat label="Last result" value={progress.last_result ?? "Not attempted"} /></div></div>
      {progress.results.length ? <div className="resource-list" aria-label="Ready results">{progress.results.map((item) => <div className="resource-row" key={`${item.kind}-${item.id}`}><span><strong>{item.kind === "document" ? "Document" : "Story"}: {item.title}</strong><small>{item.ready_at ? formatDate(item.ready_at) : "Persisted result"}</small></span><div className="button-row">{item.kind === "document" && item.canonical_url && <a className="quiet-button" href={item.canonical_url} target="_blank" rel="noreferrer">Open source</a>}<a className="secondary-button" href={`#${item.kind === "document" ? "documents" : "stories"}`} onClick={() => { if (item.kind === "document") queueDocumentNavigation(item.id); }}>{item.kind === "document" ? "Open Document review" : "Open Stories"}</a></div></div>)}</div> : progress.state === "ready" ? <p className="status-note">A ready state needs a persisted Document or Story link; none is available yet.</p> : <p className="muted">No ready result has been persisted.</p>}
      {(progress.state === "error" || progress.state === "deferred") && <p className="status-note">Your setup is preserved. Review the Source configuration and use the existing Watch controls to recover; Newsroom will not label this attempt successful until backend state confirms it.</p>}
    </SectionCard>}
    {watch.target_type === "topic" && <SectionCard title="Confirmed primary scope" description="These exact Topic terms are active monitoring scope. AST-24 does not generate or preapprove additional semantics.">{primaryTerms.length ? <div className="resource-list">{primaryTerms.map((item) => <div className="resource-row" key={item.id}><span><strong>{text(item.term)}</strong><small>{text(item.term_type, "include")} · {text(item.concept_kind, "term")}</small></span><Badge tone="mint">confirmed</Badge></div>)}</div> : <EmptyState title="No primary terms" description="This Topic has no confirmed primary scope. Edit the Topic vocabulary before relying on it for monitoring." />}</SectionCard>}
    <TerminologyReview watch={watch} vocabulary={vocabulary} aiStatus={aiStatus} aiStatusError={aiStatusError} suggestionError={suggestionError} working={working} onSuggest={onSuggest} onAdd={onAddTerm} onReview={onReviewVocabulary} />
    <SourceSetup working={working} onCreate={onAddSource} />
    <SourceRecommendations candidates={candidates} health={health} isUnstartedDraft={isUnstartedDraft} working={working} onDiscover={() => onAction("discover-sources", { limit: 25 })} onReview={onReview} />
    <CadenceSetup watch={watch} health={health} policy={watch.policy} working={working} onSave={onUpdateCadence} />
    <AttachedSources sources={sources} sourceHealth={sourceHealth} working={working} onDetach={onDetachSource} onRetry={onRetrySource} />
  </>;
}
