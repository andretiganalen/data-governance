import { describe, expect, it } from "vitest";
import { can } from "./permissions";
import { CreateProjectSchema } from "./projects/schemas";

describe("RBAC", () => {
  it("viewer is read-only", () => {
    expect(can("VIEWER", "project:read")).toBe(true);
    expect(can("VIEWER", "task:create")).toBe(false);
  });
  it("member can work tasks but not create projects", () => {
    expect(can("MEMBER", "task:update")).toBe(true);
    expect(can("MEMBER", "project:create")).toBe(false);
  });
  it("admin manages members", () => {
    expect(can("ADMIN", "member:manage")).toBe(true);
  });
});

describe("CreateProjectSchema", () => {
  it("normalizes key to upper case", () => {
    expect(CreateProjectSchema.parse({ key: "dg", name: "Data Gov" }).key).toBe("DG");
  });
  it("rejects due date before start date", () => {
    const r = CreateProjectSchema.safeParse({
      key: "DG",
      name: "Data Gov",
      startDate: "2026-12-01",
      dueDate: "2026-11-01",
    });
    expect(r.success).toBe(false);
  });
});
