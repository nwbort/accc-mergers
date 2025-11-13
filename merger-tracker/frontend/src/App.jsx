import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Mergers from './pages/Mergers';
import MergerDetail from './pages/MergerDetail';
import Timeline from './pages/Timeline';
import Industries from './pages/Industries';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/mergers" element={<Mergers />} />
          <Route path="/mergers/:id" element={<MergerDetail />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/industries" element={<Industries />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
