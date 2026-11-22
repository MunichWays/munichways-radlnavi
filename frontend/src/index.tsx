import React, {lazy, Suspense} from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
const App = lazy(() => import('./App'));
const PublicJunctionReview = lazy(() => import('./PublicJunctionReview'));
const junctionReview = /^\/kreuzungspruefung\/?$/.test(window.location.pathname);

const root = createRoot(document.getElementById('root') as Element);

root.render(
  <React.StrictMode>
    <Suspense fallback={<p>Wird geladen …</p>}>
      {junctionReview ? <PublicJunctionReview /> : <App />}
    </Suspense>
  </React.StrictMode>
);
