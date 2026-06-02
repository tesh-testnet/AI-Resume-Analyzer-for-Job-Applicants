/**
 * auth-guard.js
 * Drop this as <script type="module" src="auth-guard.js"> in any page
 * you want to protect. If the user is not signed in they are redirected
 * to auth.html?next=<current-page> so they land back here after login.
 */

import { initializeApp, getApps } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js';
import { getAuth, onAuthStateChanged } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js';

const firebaseConfig = {
  apiKey: "AIzaSyCYY4vSBHvHRk6J_hN_ETWFhy9go1DFNEE",
  authDomain: "resume-analyzer-a55b5.firebaseapp.com",
  projectId: "resume-analyzer-a55b5",
  storageBucket: "resume-analyzer-a55b5.firebasestorage.app",
  messagingSenderId: "751160437599",
  appId: "1:751160437599:web:b0a643f644c48d22a664ea"
};

// Avoid double-initialising if auth.js already ran on the same page
const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
const auth = getAuth(app);

// Hide page content instantly so unauthenticated users never see a flash
document.documentElement.style.visibility = 'hidden';

onAuthStateChanged(auth, (user) => {
  if (user) {
    // Signed in — reveal the page and patch the nav
    document.documentElement.style.visibility = '';
    patchNav(user);
  } else {
    // Not signed in — redirect to auth page, passing current URL as ?next=
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    // Resolve auth.html relative to this script's location
    const base = import.meta.url.replace(/auth-guard\.js$/, '');
    window.location.replace(`${base}auth.html?next=${next}`);
  }
});

/**
 * After sign-in, swap the Sign In / Sign Up nav buttons for a
 * greeting + Sign Out button so the UI reflects the auth state.
 */
function patchNav(user) {
  // Find both auth buttons by their href pattern
  const authLinks = [...document.querySelectorAll('a.btn')].filter(a =>
    a.href.includes('auth.html')
  );

  if (!authLinks.length) return;

  const displayName = user.displayName || user.email || 'User';

  // Build greeting chip
  const greeting = document.createElement('span');
  greeting.style.cssText = 'font-size:.8rem;color:var(--muted);font-weight:500;white-space:nowrap;';
  greeting.textContent = `Hi, ${displayName.split(' ')[0]}`;

  // Build sign-out button
  const signOutBtn = document.createElement('button');
  signOutBtn.textContent = 'Sign Out';
  signOutBtn.className = 'btn btn-ghost';
  signOutBtn.style.cursor = 'pointer';
  signOutBtn.addEventListener('click', async () => {
    const { signOut } = await import('https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js');
    await signOut(auth);
    window.location.href = 'auth.html';
  });

  // Replace all auth-related buttons with greeting + sign-out
  authLinks[0].replaceWith(greeting);
  authLinks.slice(1).forEach(el => el.remove());
  greeting.insertAdjacentElement('afterend', signOutBtn);
}