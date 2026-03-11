import { useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';
import KeyboardShortcutsHelp from './components/KeyboardShortcutsHelp';
import { TrackingProvider } from './context/TrackingContext';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import Dashboard from './pages/Dashboard';
import Mergers from './pages/Mergers';
import MergerDetail from './pages/MergerDetail';
import Timeline from './pages/Timeline';
import Industries from './pages/Industries';
import IndustryDetail from './pages/IndustryDetail';
import Commentary from './pages/Commentary';
import Digest from './pages/Digest';
import NickTwort from './pages/NickTwort';
import Analysis from './pages/Analysis';
import NotFound from './pages/NotFound';

function AppContent() {
  const [showShortcuts, setShowShortcuts] = useState(false);
  const toggleShortcuts = useCallback(() => setShowShortcuts(prev => !prev), []);

  useKeyboardShortcuts({ onToggleHelp: toggleShortcuts });

  return (
    <>
      <div className="min-h-screen gradient-mesh flex flex-col">
        <Navbar />
        <main id="main-content" className="flex-grow pt-16">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/mergers" element={<Mergers />} />
            <Route path="/mergers/:id" element={<MergerDetail />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/industries" element={<Industries />} />
            <Route path="/industries/:code" element={<IndustryDetail />} />
            <Route path="/commentary" element={<Commentary />} />
            <Route path="/digest" element={<Digest />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/nick-twort" element={<NickTwort />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <Footer />
      </div>
      <KeyboardShortcutsHelp
        isOpen={showShortcuts}
        onClose={() => setShowShortcuts(false)}
      />
    </>
  );
}

function App() {
  return (
    <HelmetProvider>
      <Router>
        <TrackingProvider>
        <ErrorBoundary>
          <AppContent />
        </ErrorBoundary>
        </TrackingProvider>
      </Router>
    </HelmetProvider>
  );
}

export default App;
