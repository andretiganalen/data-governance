import path from "node:path";
import { config } from "dotenv";
config({ path: path.resolve(import.meta.dirname, "../../../.env") });

const { prisma } = await import("../src/index");

const org = await prisma.organization.upsert({
  where: { slug: "len" },
  update: {},
  create: { slug: "len", name: "PT Len Industri" },
});

const andre = await prisma.user.upsert({
  where: { email: "andre.tigana@len.co.id" },
  update: {},
  create: { email: "andre.tigana@len.co.id", name: "Andre Tigana" },
});

await prisma.membership.upsert({
  where: { organizationId_userId: { organizationId: org.id, userId: andre.id } },
  update: {},
  create: { organizationId: org.id, userId: andre.id, role: "OWNER" },
});

const existing = await prisma.project.findUnique({
  where: { organizationId_key: { organizationId: org.id, key: "DG" } },
});
if (!existing) {
  const tasks = [
    {
      title: "Deploy OpenMetadata 2.0.7 di server dev (Docker Compose)",
      status: "IN_PROGRESS",
      priority: "HIGH",
    },
    {
      title: "Impor Teams dari Master_Organization (45 unit kerja)",
      status: "TODO",
      priority: "MEDIUM",
    },
    {
      title: "Muat metadata valid dari Workbook Governance Rev.0.1",
      status: "TODO",
      priority: "HIGH",
    },
    { title: "Petakan hak DG-* menjadi policy OpenMetadata", status: "TODO", priority: "MEDIUM" },
    { title: "Integrasi login IDS (OIDC) — fase 2", status: "TODO", priority: "LOW" },
  ] as const;
  await prisma.project.create({
    data: {
      organizationId: org.id,
      key: "DG",
      name: "Data Governance ERM",
      description: "Tata kelola metadata ERM dengan OpenMetadata.",
      status: "ACTIVE",
      ownerId: andre.id,
      taskSeq: tasks.length,
      tasks: {
        create: tasks.map((t, i) => ({
          ...t,
          number: i + 1,
          sortOrder: i + 1,
          reporterId: andre.id,
          assigneeId: andre.id,
        })),
      },
    },
  });
}

console.log(`Seeded org=${org.slug} user=${andre.email}`);
await prisma.$disconnect();
