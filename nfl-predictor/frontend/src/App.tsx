import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Predict from './pages/Predict';
import Teams from './pages/Teams';
import TeamDetail from './pages/TeamDetail';
import Compare from './pages/Compare';
import Season from './pages/Season';
import History from './pages/History';
import Playoffs from './pages/Playoffs';
import PlayerPage from './pages/PlayerPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/predict" element={<Predict />} />
          <Route path="/teams" element={<Teams />} />
          <Route path="/teams/:abbr" element={<TeamDetail />} />
          <Route path="/compare/:team1?/:team2?" element={<Compare />} />
          <Route path="/seasons/:year?" element={<Season />} />
          <Route path="/history" element={<History />} />
          <Route path="/playoffs" element={<Playoffs />} />
          <Route path="/players/:id" element={<PlayerPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
