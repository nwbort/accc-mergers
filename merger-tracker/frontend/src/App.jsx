import { useState, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';
import KeyboardShortcutsHelp from './components/KeyboardShortcutsHelp';
import CommandPalette from './components/CommandPalette';
import FeedbackPopup from './components/FeedbackPopup';
import { TrackingProvider } from './context/TrackingContext';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import ScrollToTop from './components/ScrollToTop';
import Dashboard from './pages/Dashboard';
import Mergers from './pages/Mergers';
import MergerDetail from './pages/MergerDetail';
import Timeline from './pages/Timeline';
import Industries from './pages/Industries';
import IndustryDetail from './pages/IndustryDetail';
import Parties from './pages/Parties';
import PartyDetail from './pages/PartyDetail';
import Commentary from './pages/Commentary';
import Digest from './pages/Digest';
import NickTwort from './pages/NickTwort';
import Analysis from './pages/Analysis';
import Phase2 from './pages/Phase2';
import RefiledNotifications from './pages/RefiledNotifications';
import Extensions from './pages/Extensions';
import PrivacyPolicy from './pages/PrivacyPolicy';
import Feedback from './pages/Feedback';
import NotFound from './pages/NotFound';

function AppContent() {
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const toggleShortcuts = useCallback(() => setShowShortcuts(prev => !prev), []);
  const togglePalette = useCallback(() => setShowCommandPalette(prev => !prev), []);
  const openPalette = useCallback(() => setShowCommandPalette(true), []);

  useKeyboardShortcuts({ onToggleHelp: toggleShortcuts, onTogglePalette: togglePalette });

  return (
    <>
      <ScrollToTop />
      <div className="min-h-screen gradient-mesh flex flex-col">
        <Navbar onOpenSearch={openPalette} />
        <main id="main-content" className="flex-grow pt-16">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/mergers" element={<Mergers />} />
            <Route path="/mergers/:id" element={<MergerDetail />} />
            <Route path="/mergers/:id/:slug" element={<MergerDetail />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/industries" element={<Industries />} />
            <Route path="/industries/:code" element={<IndustryDetail />} />
            <Route path="/industries/:code/:slug" element={<IndustryDetail />} />
            <Route path="/parties" element={<Parties />} />
            <Route path="/parties/:id" element={<PartyDetail />} />
            <Route path="/parties/:id/:slug" element={<PartyDetail />} />
            <Route path="/commentary" element={<Commentary />} />
            <Route path="/digest" element={<Digest />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/phase-2" element={<Phase2 />} />
            <Route path="/refiled-notifications" element={<RefiledNotifications />} />
            <Route path="/extensions" element={<Extensions />} />
            <Route path="/nick-twort" element={<NickTwort />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/feedback" element={<Feedback />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <Footer />
      </div>
      <KeyboardShortcutsHelp
        isOpen={showShortcuts}
        onClose={() => setShowShortcuts(false)}
      />
      <CommandPalette
        isOpen={showCommandPalette}
        onClose={() => setShowCommandPalette(false)}
      />
      <FeedbackPopup />
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
