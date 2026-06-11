import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  Link,
  redirect,
} from "@tanstack/react-router";
import { Dashboard } from "./pages/Dashboard";
import { Jobs } from "./pages/Jobs";
import { JobDetail } from "./pages/JobDetail";
import { Incidents } from "./pages/Incidents";
import { Login } from "./pages/Login";
import { isAuthenticated } from "./auth";

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

// --- Auth guard (skip for /login) -------------------------------------------

function requireAuth() {
  if (!isAuthenticated()) {
    throw redirect({ to: "/login" });
  }
}

// --- Routes ------------------------------------------------------------------

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: Login,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: requireAuth,
  component: Dashboard,
});

const jobsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/jobs",
  beforeLoad: requireAuth,
  component: Jobs,
});

const jobDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/jobs/$jobId",
  beforeLoad: requireAuth,
  component: JobDetail,
});

const incidentsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/incidents",
  beforeLoad: requireAuth,
  component: Incidents,
});

const routeTree = rootRoute.addChildren([
  loginRoute,
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
