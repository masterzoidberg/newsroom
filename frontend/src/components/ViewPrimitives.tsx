import { ReactNode } from "react";
import { ApiError } from "../lib/api";

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>{action && <div className="page-action">{action}</div>}</div>;
}

export function LoadingState({ label = "Loading workspace" }: { label?: string }) {
  return <div className="state-panel" role="status" aria-busy="true"><span className="loading-bar" aria-hidden="true" /><p>{label}…</p></div>;
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Something went wrong.";
  return <div className="state-panel error-panel" role="alert"><strong>Could not load this view.</strong><p>{message}</p>{retry && <button className="secondary-button" type="button" onClick={retry}>Try again</button>}</div>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="state-panel empty-panel"><span className="empty-mark" aria-hidden="true">○</span><strong>{title}</strong><p>{description}</p>{action}</div>;
}

export function Stat({ label, value, tone = "neutral" }: { label: string; value: string | number; tone?: "neutral" | "mint" | "amber" | "coral" }) {
  return <div className={`stat-card stat-${tone}`}><span>{label}</span><strong>{value}</strong></div>;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "mint" | "amber" | "coral" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function SectionCard({ title, description, children, action }: { title: string; description?: string; children: ReactNode; action?: ReactNode }) {
  return <section className="section-card"><div className="section-card-heading"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}</div>{children}</section>;
}
