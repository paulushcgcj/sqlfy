import { RootRoute, Route, Router } from '@tanstack/react-router';

import RootLayout from '@/layouts/RootLayout';
import AskPage from '@/pages/AskPage';
import ChunksPage from '@/pages/ChunksPage';
import DiffPage from '@/pages/DiffPage';
import GraphExportPage from '@/pages/GraphExportPage';
import GraphPage from '@/pages/GraphPage';
import HealthPage from '@/pages/HealthPage';
import InsightsPage from '@/pages/InsightsPage';
import LandingPage from '@/pages/LandingPage';
import MigrationsPage from '@/pages/MigrationsPage';
import SchemaStatePage from '@/pages/SchemaStatePage';
import SimulatePage from '@/pages/SimulatePage';

// Root route with layout
const rootRoute = new RootRoute({
  component: RootLayout,
});

// Index route (landing page)
const indexRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/',
  component: LandingPage,
});

// Migration analysis pages
const migrationsRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/migrations',
  component: MigrationsPage,
});

const graphRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/graph',
  component: GraphPage,
});

const chunksRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/chunks',
  component: ChunksPage,
});

const askRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/ask',
  component: AskPage,
});

const schemaStateRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/schema-state',
  component: SchemaStatePage,
});

const insightsRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/insights',
  component: InsightsPage,
});

const graphExportRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/graph-export',
  component: GraphExportPage,
});

const healthRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/health',
  component: HealthPage,
});

const simulateRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/simulate',
  component: SimulatePage,
});

const diffRoute = new Route({
  getParentRoute: () => rootRoute,
  path: '/diff',
  component: DiffPage,
});

// Build route tree
const routeTree = rootRoute.addChildren([
  indexRoute,
  migrationsRoute,
  graphRoute,
  chunksRoute,
  askRoute,
  schemaStateRoute,
  insightsRoute,
  graphExportRoute,
  healthRoute,
  simulateRoute,
  diffRoute,
]);

// Create router
export const router = new Router({ routeTree });

// Register router for type safety
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
