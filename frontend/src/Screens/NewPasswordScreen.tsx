import { confirmSignIn } from "aws-amplify/auth";
import { createStatus, getErrorMessage, type StatusMessage } from "../utils";
import { useState } from "react";

/**
 * 
 * @param props - component properties.
 * @param props.onNewPassSuccess - called after the new password is accepted.
 * @returns the new-password form.
 */
function NewPasswordScreen({ onNewPassSuccess }: {onNewPassSuccess: () => void }){
    
    const [password, setPassword] = useState<string>("");
    const [confirmPassword, setConfirmPassword] = useState<string>("");
    const [status, setStatus] = useState<StatusMessage>(createStatus("idle", ""));
    
    /**
     * Validates the two password fields and completes the Cognito challenge.
     * 
     * @param event the new-password form submission event.
     * @returns a promise that resolves when the password challenge is completed.
     */
    async function handleNewPassword(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setStatus(createStatus("idle", ""));

        if (password !== confirmPassword) {
            setStatus(createStatus("error", "Passwords do not match."));
            return;
        }

        try {
            // Complete Cognito's mandatory new-password challenge.
            await confirmSignIn({
                challengeResponse: password,
            });
            onNewPassSuccess();
        } catch (error) {
            setStatus(createStatus("error", getErrorMessage(error)));
        }
    }

    return (
        <main className="app-container"> 
            <form onSubmit={handleNewPassword}>
                <h1>New Password Setting</h1><br/>
                <p>Please set a new password, the requirements:</p>
                <p>Contains at least 1 number</p>
                <p>Contains at least 1 special character</p>
                <p>Contains at least 1 uppercase letter</p>
                <p>Contains at least 1 lowercase letter</p>

                <label className="form-label">
                    New Password: <input type="password" value={password} onChange={(event) => setPassword(event.target.value)}/>
                </label>

                <label className="form-label">
                    Confirm Password: <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)}/>
                </label><br/>

                {status.text && (
                    <div className={`status-message ${status.type}`}>
                        <p>{status.text}</p>
                    </div>
                )}
                <div className="button-row">
                    <button type="submit">Set Password</button>
                </div>
            </form>
        </main>
    );
}

export default NewPasswordScreen