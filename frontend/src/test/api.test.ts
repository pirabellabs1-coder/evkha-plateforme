import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock auth avant d'importer api (getToken est appele dans chaque requete)
vi.mock("../auth", () => ({
  getToken: () => "test-token",
  clearToken: vi.fn(),
}));

const { api } = await import("../api");

describe("api — MSW integration", () => {
  beforeEach(() => {
    // JSDOM ne supporte pas window.location.href = ... sans erreur ;
    // on le mocke pour eviter les crashs sur les 401 redirects.
    Object.defineProperty(window, "location", {
      value: { origin: "http://localhost", href: "/" },
      writable: true,
    });
  });

  it("system() retourne le statut API avec les stubs actifs", async () => {
    const status = await api.system();
    expect(status.api).toBe("ok");
    expect(status.email_stub).toBe(true);
    expect(status.ai_stub).toBe(true);
  });

  it("overview() retourne les compteurs de jobs", async () => {
    const data = await api.overview();
    expect(data.jobs.total).toBe(5);
    expect(data.jobs.running).toBe(1);
    expect(data.jobs.failed).toBe(0);
    expect(typeof data.cost_30d_eur).toBe("string");
  });

  it("jobs() retourne la liste avec un job running et un done", async () => {
    const jobs = await api.jobs();
    expect(jobs).toHaveLength(2);
    const done = jobs.find((j) => j.status === "done");
    const running = jobs.find((j) => j.status === "running");
    expect(done).toBeDefined();
    expect(running).toBeDefined();
    // Verifie que les chapitres chunkes ont leur token count (8000 output sur ch.01)
    expect(done!.chapters_total).toBe(22);
    expect(running!.chapters_done).toBe(5);
  });

  it("job(id) retourne le detail avec le chapitre 1 chunke (8000 output tokens)", async () => {
    const job = await api.job("job-chunk-test-01");
    expect(job.offer_name).toContain("Test");
    const ch1 = job.chapters.find((c) => c.number === 1);
    expect(ch1).toBeDefined();
    // 8000 output tokens reflete la generation en 2 chunks fusionnes
    expect(ch1!.output_tokens).toBe(8000);
    expect(ch1!.status).toBe("done");
  });
});
