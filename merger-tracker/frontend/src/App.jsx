import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';
import { TrackingProvider } from './context/TrackingContext';
import Dashboard from './pages/Dashboard';
import Mergers from './pages/Mergers';
import MergerDetail from './pages/MergerDetail';
import Timeline from './pages/Timeline';
import Industries from './pages/Industries';
import Commentary from './pages/Commentary';
import Digest from './pages/Digest';
import NickTwort from './pages/NickTwort';

function App() {
  return (
    <HelmetProvider>
      <Router>
        <TrackingProvider>
        <ErrorBoundary>
          <div className="min-h-screen gradient-mesh flex flex-col">
            <Navbar />
            <main id="main-content" className="flex-grow pt-16">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/mergers" element={<Mergers />} />
                <Route path="/mergers/:id" element={<MergerDetail />} />
                <Route path="/timeline" element={<Timeline />} />
                <Route path="/industries" element={<Industries />} />
                <Route path="/commentary" element={<Commentary />} />
                <Route path="/digest" element={<Digest />} />
                <Route path="/nick-twort" element={<NickTwort />} />
              </Routes>
            </main>
            <Footer />
          </div>
        </ErrorBoundary>
        </TrackingProvider>
      </Router>
    </HelmetProvider>
  );
}

export default App;
