import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

// MSW intercepte fetch() en environnement Node (Vitest).
// Les URLs matchent window.location.origin = "http://localhost" en jsdom.
const DASH = "http://localhost/api/dashboard";

export const handlers = [
  http.get(`${DASH}/overview/`, () =>
    HttpResponse.json({
      jobs: { total: 5, today: 2, running: 1, failed: 0 },
      cost_30d_eur: "0.0240",
      incidents: { open: 0, critical_or_high: 0 },
    }),
  ),

  http.get(`${DASH}/jobs/`, () =>
    HttpResponse.json([
      {
        id: "job-chunk-test-01",
        deliverable_type: "market_study",
        status: "done",
        total_cost_eur: "0.0180",
        budget_eur: "2.0000",
        chapters_done: 22,
        chapters_total: 22,
        started_at: "2026-06-13T10:00:00Z",
        completed_at: "2026-06-13T10:15:00Z",
        order_id: "order-abc",
        error_message: null,
      },
      {
        id: "job-chunk-test-02",
        deliverable_type: "market_study",
        status: "running",
        total_cost_eur: "0.0060",
        budget_eur: "2.0000",
        chapters_done: 5,
        chapters_total: 22,
        started_at: "2026-06-13T10:20:00Z",
        completed_at: null,
        order_id: "order-def",
        error_message: null,
      },
    ]),
  ),

  http.get(`${DASH}/system/`, () =>
    HttpResponse.json({
      api: "ok",
      email_stub: true,
      ai_stub: true,
    }),
  ),

  http.get(`${DASH}/incidents/`, () => HttpResponse.json([])),

  http.get(`${DASH}/jobs/:id/`, ({ params }) =>
    HttpResponse.json({
      id: params.id,
      deliverable_type: "market_study",
      status: "done",
      total_cost_eur: "0.0180",
      budget_eur: "2.0000",
      chapters_done: 22,
      chapters_total: 22,
      started_at: "2026-06-13T10:00:00Z",
      completed_at: "2026-06-13T10:15:00Z",
      order_id: "order-abc",
      error_message: null,
      customer_email: "client@test.com",
      offer_name: "Etude de marche — Test",
      chapters: [
        {
          number: 1,
          title: "Analyse chiffree du marche mondial et europeen",
          prompt_key: "em.01.marche_mondial_europeen",
          status: "done",
          cost_eur: "0.0030",
          input_tokens: 1200,
          output_tokens: 8000,
          retry_count: 0,
          error_message: null,
        },
      ],
    }),
  ),
];

export const server = setupServer(...handlers);
