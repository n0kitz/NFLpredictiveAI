import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import Spinner from './components/Spinner';
import NotFound from './pages/NotFound';

// Route-level code splitting — heavy pages loaded on demand
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Predict = lazy(() => import('./pages/Predict'));
const Teams = lazy(() => import('./pages/Teams'));
const TeamDetail = lazy(() => import('./pages/TeamDetail'));
const Compare = lazy(() => import('./pages/Compare'));
const Season = lazy(() => import('./pages/Season'));
const History = lazy(() => import('./pages/History'));
const Playoffs = lazy(() => import('./pages/Playoffs'));
const PlayerPage = lazy(() => import('./pages/PlayerPage'));
const FantasyPage = lazy(() => import('./pages/FantasyPage'));
const TeamSchedule = lazy(() => import('./pages/TeamSchedule'));

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Suspense fallback={<Spinner />}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/predict" element={<Predict />} />
              <Route path="/teams" element={<Teams />} />
              <Route path="/teams/:abbr" element={<TeamDetail />} />
              <Route path="/teams/:abbr/schedule" element={<TeamSchedule />} />
              <Route path="/compare/:team1?/:team2?" element={<Compare />} />
              <Route path="/seasons/:year?" element={<Season />} />
              <Route path="/history" element={<History />} />
              <Route path="/playoffs" element={<Playoffs />} />
              <Route path="/players/:id" element={<PlayerPage />} />
              <Route path="/fantasy" element={<FantasyPage />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </BrowserRouter>
  );
}
