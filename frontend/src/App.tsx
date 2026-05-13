import "./amplify-config";
import { useState } from "react";
import {
  signUp,
  confirmSignUp,
  signIn,
  signOut,
  getCurrentUser,
  fetchAuthSession,
} from "aws-amplify/auth";
import type { AuthUser } from "aws-amplify/auth";

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  return String(error);
}

function App() {
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");

  const [confirmEmail, setConfirmEmail] = useState<string>("");
  const [code, setCode] = useState<string>("");

  const [message, setMessage] = useState<string>("");
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [idTokenPreview, setIdTokenPreview] = useState<string>("");

  async function handleSignUp(): Promise<void> {
    try {
      setMessage("Creating user...");

      await signUp({
        username: email,
        password,
        options: {
          userAttributes: {
            email,
          },
        },
      });

      setConfirmEmail(email);
      setMessage("User created. Check your email for the verification code.");
    } catch (error: unknown) {
      console.error(error);
      setMessage(getErrorMessage(error) || "Sign up failed.");
    }
  }

  async function handleConfirmSignUp(): Promise<void> {
    try {
      setMessage("Confirming user...");

      await confirmSignUp({
        username: confirmEmail,
        confirmationCode: code,
      });

      setMessage("User confirmed. You can now sign in.");
    } catch (error: unknown) {
      console.error(error);
      setMessage(getErrorMessage(error) || "Confirmation failed.");
    }
  }

  async function handleSignIn(): Promise<void> {
    try {
      setMessage("Signing in...");

      await signIn({
        username: email,
        password,
      });

      await loadCurrentUser();

      setMessage("Signed in successfully.");
    } catch (error: unknown) {
      console.error(error);
      setMessage(getErrorMessage(error) || "Sign in failed.");
    }
  }

  async function loadCurrentUser(): Promise<void> {
    try {
      const user = await getCurrentUser();
      const session = await fetchAuthSession();

      setCurrentUser(user);

      const idToken = session.tokens?.idToken?.toString() ?? "";
      setIdTokenPreview(idToken ? `${idToken.slice(0, 40)}...` : "");
    } catch (error: unknown) {
      console.error(error);
      setCurrentUser(null);
      setIdTokenPreview("");
      setMessage("No signed-in user.");
    }
  }

  async function handleSignOut(): Promise<void> {
    try {
      await signOut();

      setCurrentUser(null);
      setIdTokenPreview("");
      setMessage("Signed out.");
    } catch (error: unknown) {
      console.error(error);
      setMessage(getErrorMessage(error) || "Sign out failed.");
    }
  }

  return (
    <main style={{ maxWidth: "700px", margin: "40px auto", fontFamily: "Arial" }}>
      <h1>Aussie Eco Lens Auth Demo</h1>

      <section style={{ border: "1px solid #ddd", padding: "20px", marginBottom: "20px" }}>
        <h2>1. Sign up</h2>

        <input
          style={{ display: "block", marginBottom: "10px", width: "100%", padding: "8px" }}
          type="email"
          placeholder="Email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />

        <input
          style={{ display: "block", marginBottom: "10px", width: "100%", padding: "8px" }}
          type="password"
          placeholder="Password, e.g. Test1234"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />

        <button type="button" onClick={handleSignUp}>
          Create user
        </button>
      </section>

      <section style={{ border: "1px solid #ddd", padding: "20px", marginBottom: "20px" }}>
        <h2>2. Confirm sign up</h2>

        <input
          style={{ display: "block", marginBottom: "10px", width: "100%", padding: "8px" }}
          type="email"
          placeholder="Email to confirm"
          value={confirmEmail}
          onChange={(event) => setConfirmEmail(event.target.value)}
        />

        <input
          style={{ display: "block", marginBottom: "10px", width: "100%", padding: "8px" }}
          type="text"
          placeholder="Verification code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />

        <button type="button" onClick={handleConfirmSignUp}>
          Confirm user
        </button>
      </section>

      <section style={{ border: "1px solid #ddd", padding: "20px", marginBottom: "20px" }}>
        <h2>3. Sign in / sign out</h2>

        <button type="button" onClick={handleSignIn}>
          Sign in
        </button>

        <button type="button" onClick={loadCurrentUser} style={{ marginLeft: "10px" }}>
          Check current user
        </button>

        <button type="button" onClick={handleSignOut} style={{ marginLeft: "10px" }}>
          Sign out
        </button>
      </section>

      <section style={{ border: "1px solid #ddd", padding: "20px" }}>
        <h2>Status</h2>

        <p>{message}</p>

        {currentUser && (
          <>
            <p>
              <strong>Username:</strong> {currentUser.username}
            </p>

            <p>
              <strong>User ID:</strong> {currentUser.userId}
            </p>

            <p>
              <strong>ID token preview:</strong> {idTokenPreview}
            </p>
          </>
        )}
      </section>
    </main>
  );
}

export default App;