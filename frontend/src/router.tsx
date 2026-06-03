import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  Link,
} from "@tanstack/react-router";
import { Dashboard } from "./pages/Dashboard";
import { Jobs } from "./pages/Jobs";
import { JobDetail } from "./pages/JobDetail";
import { Incidents } from "./pages/Incidents";

// --- Root layout -------------------------------------------------------------

const rootRoute = createRootRoute({
  component: () => (
    <div className="layout">
      <nav className="sidebar">
        <div className="brand">
          <span className="logo">⬡</span>
          <div>
            <strong>EVKHA</strong>
            <small>Dashboard</small>
          </div>
        </div>
        <ul>
          <li>
            <Link to="/" activeProps={{ className: "active" }}>
              Vue d'ensemble
            </Link>
          </li>
          <li>
            <Link to="/jobs" activeProps={{ className: "active" }}>
              Livrables
            </Link>
          </li>
          <li>
            <Link to="/incidents" activeProps={{ className: "active" }}>
              Incidents
            </Link>
          </li>
        </ul>
      </nav>
      <main>
        <Outlet />
      </main>
    </div>
  ),
});

// --- Routes ------------------------------------------------------------------

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Dashboard,
});

const jobsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/jobs",
  component: Jobs,
});

const jobDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/jobs/$jobId",
  component: JobDetail,
});

const incidentsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/incidents",
  component: Incidents,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  jobsRoute,
  jobDetailRoute,
  incidentsRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
