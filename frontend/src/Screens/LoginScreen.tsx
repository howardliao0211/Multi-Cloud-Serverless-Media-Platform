import { createStatus, getErrorMessage, type StatusMessage } from "../utils";
import { useState } from "react";
import { signIn, signOut } from "aws-amplify/auth";
import { useNavigate } from "react-router-dom";
import NewPasswordScreen from "./NewPasswordScreen";

/**
 * Displays the user login form and authenticates users through AWS Amplify.
 *
 * If Cognito requires the user to set a new password, this component switches
 * to NewPasswordScreen. After successful authentication, the user is redirected
 * to the dashboard.
 *
 * @returns the login form or the new-password confirmation screen.
 */
function LoginScreen() {
    const navigate = useNavigate();
    const [email, setEmail] = useState<string>("");
    const [password, setPassword] = useState<string>("");
    // Determines whether Cognito requires the user to create a new password.
    const [needNewPassword, setNeedNewPassword] = useState<boolean>(false);
    const [status, setStatus] = useState<StatusMessage>(createStatus("idle", ""));

    /**
     * Authenticates the user with Cognito.
     *
     * Any existing Amplify session is cleared before a new sign-in attempt.
     * Users required to create a new password are redirected to the appropriate
     * confirmation screen. Successfully authenticated users are sent to the
     * dashboard.
     *
     * @param event the login form submission event.
     */
    async function handleLogin(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setStatus(createStatus("idle", ""));
        try {

            try {
                // Clear any stale authenticated session before signing in again.
                await signOut();
            } catch {
                // Ignore the absence of an existing authenticated session.
            }

            const result = await signIn({
                username: email,
                password,
            });

            // Switch to the mandatory password-change flow when required by Cognito.
            if (result.nextStep.signInStep === "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED") {
                setNeedNewPassword(true);
                return;
            }
            navigate("/dashboard");
        } catch (error) {
            setStatus(createStatus("error", getErrorMessage(error)));
        }
    }

    if (needNewPassword) {
        return <NewPasswordScreen onNewPassSuccess={() => navigate("/dashboard")} />;
    }

    return (
        <main className="app-container">
            <form onSubmit={handleLogin}>
                <h1>Login</h1><br /><br />

                <label className="form-label">
                    Email: <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
                </label>

                <label className="form-label">
                    Password: <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
                </label><br /><br />

                {status.text && (
                    <div className={`status-message ${status.type}`}>
                        <p>{status.text}</p>
                    </div>
                )}

                <div className="button-row">
                    <button type="button" onClick={() => navigate("/")}>
                        Return
                    </button>
                    <button type="submit">Log in</button>
                </div>
            </form>
        </main>
    );
}

export default LoginScreen