import { useState, useCallback, lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';
import KeyboardShortcutsHelp from './components/KeyboardShortcutsHelp';
import CommandPalette from './components/CommandPalette';
import FeedbackPopup from './components/FeedbackPopup';
import LoadingSpinner from './components/LoadingSpinner';
import { TrackingProvider } from './context/TrackingContext';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import ScrollToTop from './components/ScrollToTop';

// Route components are code-split so the initial bundle only carries the app
// shell. Heavy, page-specific dependencies (charts, react-markdown) then load
// on demand with the route that needs them instead of on first paint.
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Mergers = lazy(() => import('./pages/Mergers'));
const MergerDetail = lazy(() => import('./pages/MergerDetail'));
const Timeline = lazy(() => import('./pages/Timeline'));
const Industries = lazy(() => import('./pages/Industries'));
const IndustryDetail = lazy(() => import('./pages/IndustryDetail'));
const Parties = lazy(() => import('./pages/Parties'));
const PartyDetail = lazy(() => import('./pages/PartyDetail'));
const Commentary = lazy(() => import('./pages/Commentary'));
const Digest = lazy(() => import('./pages/Digest'));
const NickTwort = lazy(() => import('./pages/NickTwort'));
const Analysis = lazy(() => import('./pages/Analysis'));
const Phase2 = lazy(() => import('./pages/Phase2'));
const RefiledNotifications = lazy(() => import('./pages/RefiledNotifications'));
const Extensions = lazy(() => import('./pages/Extensions'));
const StateOfPlay = lazy(() => import('./pages/StateOfPlay'));
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy'));
const Feedback = lazy(() => import('./pages/Feedback'));
const NotFound = lazy(() => import('./pages/NotFound'));

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
          <Suspense fallback={<LoadingSpinner />}>
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
            <Route path="/state-of-play" element={<StateOfPlay />} />
            <Route path="/nick-twort" element={<NickTwort />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/feedback" element={<Feedback />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
          </Suspense>
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
