import { confirmSignIn } from "aws-amplify/auth";
import { getErrorMessage } from "../utils";
import { useState } from "react";

function NewPasswordScreen({ onNewPassSuccess }: {onNewPassSuccess: () => void }){
    
    const [password, setPassword] = useState<string>("");
    const [confirmPassword, setConfirmPassword] = useState<string>("");
    const [errorMessage, setErrorMessage] = useState<string>("");
    
    async function handleNewPassword(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setErrorMessage("");

        if (password !== confirmPassword) {
            setErrorMessage("Passwords do not match.");
            return;
        }

        try {
            await confirmSignIn({
                challengeResponse: password,
            });
            onNewPassSuccess();
        } catch (error) {
            setErrorMessage(getErrorMessage(error));
        }
    }

    return (
        <main className="app-container"> 
            <form onSubmit={handleNewPassword}>
                <h1>New Password Setting</h1><br/>
                <p>Please set a new password, the requirenents:</p>
                <p>Contains at least 1 number</p>
                <p>Contains at least 1 special character</p>
                <p>Contains at least 1 uppercase letter</p>
                <p>Contains at least 1 lowercase letter</p>

                <label className="form-label">
                    New Password: <input type="password" value={password} onChange={(event) => setPassword(event.target.value)}/>
                </label>

                <label className="form-label">
                    Comfirm Password: <input type="comfirm" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)}/>
                </label><br/>

                {errorMessage && <p>{errorMessage}</p>}
                <div className="button-row">
                    <button type="submit">Set Password</button>
                </div>
            </form>
        </main>
    );
}

export default NewPasswordScreen