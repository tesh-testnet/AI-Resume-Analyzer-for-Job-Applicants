'use strict';

/* THEME */
(function(){
  const r=document.documentElement;
  let d=r.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
  r.setAttribute('data-theme',d);
  function icon(){
    const t=document.querySelector('[data-theme-toggle]');
    if(!t)return;
    t.innerHTML=d==='dark'
      ?'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
      :'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  }
  icon();
  document.querySelector('[data-theme-toggle]')?.addEventListener('click',()=>{
    d=d==='dark'?'light':'dark';r.setAttribute('data-theme',d);icon();
  });
})();

/* TABS */
const tabs=[...document.querySelectorAll('.tab-btn')];
const panels={
  signin:document.getElementById('panel-signin'),
  signup:document.getElementById('panel-signup'),
  forgot:document.getElementById('panel-forgot')
};
function switchTab(name){
  tabs.forEach(t=>{
    const active=t.dataset.tab===name;
    t.classList.toggle('active',active);
    t.setAttribute('aria-selected',active?'true':'false');
  });
  Object.entries(panels).forEach(([key,el])=>el.classList.toggle('active',key===name));
  statusMsg('');
}

/* STATUS */
const statusEl=document.getElementById('auth-status');
function statusMsg(msg,type){
  if(!statusEl)return;
  statusEl.textContent=msg||'';
  statusEl.className='auth-status'+(type?' '+type:'');
}

/* FIREBASE */
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js';
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  updateProfile
} from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js';

const firebaseConfig = {
  apiKey: "AIzaSyCYY4vSBHvHRk6J_hN_ETWFhy9go1DFNEE",
  authDomain: "resume-analyzer-a55b5.firebaseapp.com",
  projectId: "resume-analyzer-a55b5",
  storageBucket: "resume-analyzer-a55b5.firebasestorage.app",
  messagingSenderId: "751160437599",
  appId: "1:751160437599:web:b0a643f644c48d22a664ea"
};

const app=initializeApp(firebaseConfig);
const auth=getAuth(app);

/* ACTIONS */
async function doSignIn(){
  const email=document.getElementById('signin-email').value.trim();
  const pass=document.getElementById('signin-password').value.trim();
  if(!email||!pass){statusMsg('Enter email and password.','err');return;}
  statusMsg('Signing in...');
  try{
    await signInWithEmailAndPassword(auth,email,pass);
    statusMsg('Signed in. Redirecting...','ok');
    const params=new URLSearchParams(window.location.search);
    const nextParam=params.get('next');
    const destPath = nextParam ? decodeURIComponent(nextParam) : '/analyzer';
    const destUrl = new URL(destPath, window.location.origin);
    setTimeout(()=>{window.location.href=destUrl.href;},800);
  }catch(e){
    statusMsg(e.message||'Sign in failed.','err');
  }
}

async function doSignUp(){
  const name=document.getElementById('signup-name').value.trim();
  const email=document.getElementById('signup-email').value.trim();
  const pass=document.getElementById('signup-password').value.trim();
  if(!name||!email||!pass){statusMsg('Fill in all fields.','err');return;}
  if(pass.length<8){statusMsg('Password must be at least 8 characters.','err');return;}
  statusMsg('Creating account...');
  try{
    const cred=await createUserWithEmailAndPassword(auth,email,pass);
    if(name) await updateProfile(cred.user,{displayName:name});
    statusMsg('Account created. Redirecting...','ok');
    const params=new URLSearchParams(window.location.search);
    const nextParam=params.get('next');
    const destPath = nextParam ? decodeURIComponent(nextParam) : '/analyzer';
    const destUrl = new URL(destPath, window.location.origin);
    setTimeout(()=>{window.location.href=destUrl.href;},800);
  }catch(e){
    statusMsg(e.message||'Sign up failed.','err');
  }
}

async function doForgot(){
  const email=document.getElementById('forgot-email').value.trim();
  if(!email){statusMsg('Enter your email address.','err');return;}
  statusMsg('Sending reset email...');
  try{
    await sendPasswordResetEmail(auth,email);
    statusMsg('Reset email sent. Check your inbox.','ok');
  }catch(e){
    statusMsg(e.message||'Reset failed.','err');
  }
}

/* EVENTS */
tabs.forEach(t=>t.addEventListener('click',()=>switchTab(t.dataset.tab)));
document.getElementById('signin-btn').addEventListener('click',doSignIn);
document.getElementById('signup-btn').addEventListener('click',doSignUp);
document.getElementById('forgot-btn').addEventListener('click',doForgot);
document.getElementById('forgot-link').addEventListener('click',(e)=>{
  e.preventDefault();
  switchTab('forgot');
});

lucide.createIcons();
