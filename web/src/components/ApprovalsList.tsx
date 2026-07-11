import type { RegulatoryApproval } from "../lib/types";
import { Icon } from "./Icon";

// The human-facing FDA source for an approval is its Drugs@FDA overview page,
// keyed by the numeric part of the application number (e.g. NDA209637 -> 209637).
// Returns null when no digits are present, so we render plain text rather than a
// dead link.
export function drugsAtFdaUrl(applicationNumber: string): string | null {
  const applNo = applicationNumber.replace(/\D/g, "");
  if (!applNo) return null;
  return `https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo=${applNo}`;
}

// The shared list of FDA approvals, each linking to its Drugs@FDA overview page.
// Used by both the per-asset dossier and the per-company pipeline.
export function ApprovalsList({ approvals }: { approvals: RegulatoryApproval[] }) {
  return (
    <ul className="space-y-1" data-testid="approvals-list">
      {approvals.map((a) => {
        const fdaUrl = drugsAtFdaUrl(a.application_number);
        return (
          <li key={a.application_number} className="flex items-center gap-2 text-[13px]">
            <Icon name="verified" size={15} className="text-accent" />
            <span className="font-medium text-ink-light">
              {a.brand_names.join(", ") || a.drug}
            </span>
            {fdaUrl ? (
              <a
                href={fdaUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 font-mono text-accent hover:underline"
                title={`View ${a.application_number} on Drugs@FDA`}
              >
                {a.application_number}
                <Icon name="open_in_new" size={13} label="opens on FDA.gov" />
              </a>
            ) : (
              <span className="font-mono text-ink-muted-light">{a.application_number}</span>
            )}
            {a.approval_date && <span className="text-ink-muted-light">· {a.approval_date}</span>}
            {a.marketing_status && (
              <span className="text-ink-muted-light">· {a.marketing_status}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
