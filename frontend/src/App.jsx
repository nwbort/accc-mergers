import { useState, useCallback, useEffect, Suspense } from 'react';
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
import { PushProvider } from './context/PushContext';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useBackgroundRefresh } from './hooks/useBackgroundRefresh';
import ScrollToTop from './components/ScrollToTop';
import { ROUTES } from './routes';
import { markAppSettled } from './utils/appMount';


function AppContent() {
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const toggleShortcuts = useCallback(() => setShowShortcuts(prev => !prev), []);
  const togglePalette = useCallback(() => setShowCommandPalette(prev => !prev), []);
  const openPalette = useCallback(() => setShowCommandPalette(true), []);

  useKeyboardShortcuts({ onToggleHelp: toggleShortcuts, onTogglePalette: togglePalette });
  useEffect(markAppSettled, []);
  useBackgroundRefresh();

  return (
    <>
      <ScrollToTop />
      <div className="min-h-screen gradient-mesh flex flex-col">
        <Navbar onOpenSearch={openPalette} />
        <main id="main-content" className="flex-grow pt-16">
          <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            {/* Each page loads its own chunk on demand: see routes.js. */}
            {ROUTES.map(({ path, page: { Component } }) => (
              <Route key={path} path={path} element={<Component />} />
            ))}
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
        <PushProvider>
        <ErrorBoundary>
          <AppContent />
        </ErrorBoundary>
        </PushProvider>
        </TrackingProvider>
      </Router>
    </HelmetProvider>
  );
}

export default App;
