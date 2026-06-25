import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  Link,
  redirect,
} from "@tanstack/react-router";
import { Text, Heading } from "@radix-ui/themes";
import { Dashboard } from "./pages/Dashboard";
import { GenerateManual } from "./pages/GenerateManual";
import { Jobs } from "./pages/Jobs";
import { JobDetail } from "./pages/JobDetail";
import { Incidents } from "./pages/Incidents";
import { Clients } from "./pages/Clients";
import { ClientDetail } from "./pages/ClientDetail";
import { Orders } from "./pages/Orders";
import { Login } from "./pages/Login";
import { isAuthenticated } from "./auth";

// --- Root layout -------------------------------------------------------------

const rootRoute = createRootRoute({
  component: () => (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-logo">⬡</span>
          <div>
            <Heading size="2">EVKHA</Heading>
            <Text size="1" color="gray">Dashboard</Text>
          </div>
        </div>
        <ul className="sidebar-nav">
          <li>
            <Link to="/" className="sidebar-link" activeProps={{ className: "active" }} activeOptions={{ exact: true }}>
              Vue d'ensemble
            </Link>
          </li>
          <li>
            <Link to="/clients" className="sidebar-link" activeProps={{ className: "active" }}>
              Clients
            </Link>
          </li>
          <li>
            <Link to="/orders" className="sidebar-link" activeProps={{ className: "active" }}>
              Commandes
            </Link>
          </li>
          <li>
            <Link to="/jobs" className="sidebar-link" activeProps={{ className: "active" }}>
              Livrables
            </Link>
          </li>
          <li>
            <Link to="/generate" className="sidebar-link" activeProps={{ className: "active" }}>
              Générer
            </Link>
          </li>
          <li>
            <Link to="/incidents" className="sidebar-link" activeProps={{ className: "active" }}>
              Incidents
            </Link>
          </li>
        </ul>
      </nav>
      <main className="app-main">
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

const clientsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/clients",
  beforeLoad: requireAuth,
  component: Clients,
});

const clientDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/clients/$clientId",
  beforeLoad: requireAuth,
  component: ClientDetail,
});

const ordersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/orders",
  beforeLoad: requireAuth,
  component: Orders,
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

const generateRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/generate",
  beforeLoad: requireAuth,
  component: GenerateManual,
});

const routeTree = rootRoute.addChildren([
  loginRoute,
  indexRoute,
  clientsRoute,
  clientDetailRoute,
  ordersRoute,
  jobsRoute,
  jobDetailRoute,
  incidentsRoute,
  generateRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
