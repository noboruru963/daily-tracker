import { initializeApp } from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js';
import {
    createUserWithEmailAndPassword,
    getAuth,
    sendEmailVerification,
    signInWithEmailAndPassword,
    signOut,
    updateProfile
} from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js';

const firebaseConfig = window.DAILY_FIREBASE_CONFIG || {};
const message = document.getElementById('authMessage');
let auth = null;

if (firebaseConfig.apiKey && firebaseConfig.projectId && firebaseConfig.authDomain) {
    auth = getAuth(initializeApp(firebaseConfig));
}

function showMessage(text, type = 'danger') {
    if (!message) return;
    message.textContent = text;
    message.className = `alert alert-${type}`;
}

function firebaseErrorMessage(error) {
    const code = error.code || '';
    const messages = {
        'auth/api-key-not-valid': 'Firebase rejected the API key. Copy the exact apiKey from Firebase Project settings → Your apps.',
        'auth/invalid-api-key': 'Firebase rejected the API key. Copy the exact apiKey from Firebase Project settings → Your apps.',
        'auth/unauthorized-domain': 'Add localhost to Firebase Authentication → Settings → Authorized domains.',
        'auth/network-request-failed': 'Could not connect to Firebase. Check your internet connection.',
        'auth/too-many-requests': 'Firebase temporarily blocked requests. Wait a little and try again.',
        'auth/user-disabled': 'This Firebase account is disabled. Contact the app administrator.',
        'auth/invalid-email': 'Enter a valid email address.',
        'auth/email-already-in-use': 'An account already uses this email. Try signing in instead.',
        'auth/weak-password': 'Choose a password with at least 6 characters.',
        'auth/invalid-credential': 'Email or password is incorrect.',
        'auth/user-not-found': 'Email or password is incorrect.',
        'auth/wrong-password': 'Email or password is incorrect.',
        'auth/operation-not-allowed': 'Enable Email/Password under Firebase Authentication → Sign-in method.'
    };
    if (messages[code]) return messages[code];
    console.error('Firebase authentication request failed:', error);
    return `Firebase authentication failed${code ? ` (${code})` : ''}. Check the browser console.`;
}

function requireFirebase() {
    if (!firebaseConfig.apiKey) {
        showMessage('Firebase API key is missing. Set FIREBASE_API_KEY to the exact apiKey from your Firebase web app config.');
        return false;
    }
    if (!auth) {
        showMessage('Firebase web configuration is incomplete. Check the Firebase web app settings.');
        return false;
    }
    return true;
}

async function createFlaskSession(firebaseUser, remember) {
    const idToken = await firebaseUser.getIdToken();
    const response = await fetch('/auth/session-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken, remember })
    });
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
        throw new Error(`Flask returned HTTP ${response.status} without a JSON response.`);
    }
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.error || `Flask rejected sign-in (HTTP ${response.status}).`);
    }
    window.location.assign(result.redirect);
}

const loginForm = document.getElementById('loginForm');
if (loginForm) {
    loginForm.addEventListener('submit', async event => {
        event.preventDefault();
        if (!requireFirebase()) return;

        const button = loginForm.querySelector('button[type="submit"]');
        button.disabled = true;
        try {
            const credential = await signInWithEmailAndPassword(
                auth,
                document.getElementById('email').value.trim(),
                document.getElementById('password').value
            );
            if (!credential.user.emailVerified) {
                try {
                    await sendEmailVerification(credential.user);
                } finally {
                    await signOut(auth);
                }
                showMessage('Verify your email using the link we just sent, then sign in again.', 'warning');
                return;
            }
            await createFlaskSession(
                credential.user,
                document.getElementById('remember').checked
            );
        } catch (error) {
            if (error instanceof TypeError) {
                showMessage('Could not reach the Flask server. Make sure run.py is running.');
            } else {
                showMessage(error.code ? firebaseErrorMessage(error) : error.message);
            }
        } finally {
            button.disabled = false;
        }
    });
}

const registerForm = document.getElementById('registerForm');
if (registerForm) {
    registerForm.addEventListener('submit', async event => {
        event.preventDefault();
        if (!requireFirebase()) return;

        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;
        const confirmation = document.getElementById('confirm_password').value;
        if (password !== confirmation) {
            showMessage('Passwords do not match.');
            return;
        }

        const button = registerForm.querySelector('button[type="submit"]');
        button.disabled = true;
        let createdUser = null;
        try {
            const credential = await createUserWithEmailAndPassword(
                auth,
                document.getElementById('email').value.trim(),
                password
            );
            createdUser = credential.user;
            await updateProfile(createdUser, { displayName: username });
            await sendEmailVerification(createdUser);
            await signOut(auth);
            showMessage('Account created. Verify your email, then sign in to start using Daily Tracker.', 'success');
        } catch (error) {
            if (createdUser) {
                try {
                    await signOut(auth);
                } catch (signOutError) {
                    console.error('Could not sign out after registration:', signOutError);
                }
            }
            showMessage(error.code ? firebaseErrorMessage(error) : error.message);
        } finally {
            button.disabled = false;
        }
    });
}

document.querySelectorAll('a[href$="/auth/logout"]').forEach(link => {
    link.addEventListener('click', async event => {
        event.preventDefault();
        try {
            if (auth) await signOut(auth);
        } catch (error) {
            console.error('Firebase sign-out failed:', error);
        } finally {
            window.location.assign(link.href);
        }
    });
});
