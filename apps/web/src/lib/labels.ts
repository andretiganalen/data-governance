export const TASK_STATUSES = ["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE", "CANCELLED"] as const;
export const TASK_STATUS_LABEL: Record<string, string> = {
  TODO: "To do",
  IN_PROGRESS: "In progress",
  IN_REVIEW: "In review",
  DONE: "Done",
  CANCELLED: "Cancelled",
};
export const PROJECT_STATUS_LABEL: Record<string, string> = {
  PLANNED: "Planned",
  ACTIVE: "Active",
  ON_HOLD: "On hold",
  COMPLETED: "Completed",
  ARCHIVED: "Archived",
};
export const PRIORITY_STYLE: Record<string, string> = {
  LOW: "bg-muted text-muted-fg",
  MEDIUM: "bg-info/15 text-info",
  HIGH: "bg-warn/15 text-warn",
  URGENT: "bg-danger/15 text-danger",
};
export const fmtDate = (d: Date | null) =>
  d
    ? new Intl.DateTimeFormat("id-ID", { day: "2-digit", month: "short", year: "numeric" }).format(
        d,
      )
    : "—";
