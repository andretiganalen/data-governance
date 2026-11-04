export class DomainError extends Error {
  constructor(
    message: string,
    public readonly code: "FORBIDDEN" | "NOT_FOUND" | "CONFLICT" | "VALIDATION",
  ) {
    super(message);
    this.name = "DomainError";
  }
}
export const forbidden = (msg = "You do not have permission to perform this action") =>
  new DomainError(msg, "FORBIDDEN");
export const notFound = (what: string) => new DomainError(`${what} not found`, "NOT_FOUND");
export const conflict = (msg: string) => new DomainError(msg, "CONFLICT");
