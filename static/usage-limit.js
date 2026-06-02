// usage-limit.js
import {
  getAuth,
  onAuthStateChanged,
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const auth = getAuth();

onAuthStateChanged(auth, (user) => {
  const isLoggedIn = !!user;
  if (window.setAuthenticated) {
    window.setAuthenticated(isLoggedIn);
  }
  console.log("[AUTH] State changed, logged in:", isLoggedIn);
});
