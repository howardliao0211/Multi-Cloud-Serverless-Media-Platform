import { getErrorMessage } from "../utils";
import { useState } from "react";
import { signIn, signOut } from "aws-amplify/auth";
import NewPasswordScreen from "./NewPasswordScreen";

function LoginScreen({ onLoginSuccess, onReturn, }: 
    {onLoginSuccess: () => void; onReturn: () => void;}){
    
    const [email, setEmail] = useState<string>("");
    const [password, setPassword] = useState<string>("");
    const [needNewPassword, setNeedNewPassword] = useState<boolean>(false);
    const [errorMessage, setErrorMessage] = useState<string>("");
    
    async function handleLogin(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setErrorMessage("");
        try {
            await signOut();
            const result = await signIn({
                username: email,
                password,
            }); 

            if (result.nextStep.signInStep === "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED"){
                setNeedNewPassword(true);
                return;
            }
            onLoginSuccess();
        } catch (error) {
       setErrorMessage(getErrorMessage(error));
        }
    }

    if (needNewPassword){
        return <NewPasswordScreen onNewPassSuccess={onLoginSuccess}/>;
    }

    return (
        <main className="app-container"> 
            <form onSubmit={handleLogin}>
                <h1>Login</h1><br/><br/>

                <label className="form-label">
                    Email: <input type="email" value={email} onChange={(event) => setEmail(event.target.value)}/>
                </label>

                <label className="form-label">
                    Password: <input type="password" value={password} onChange={(event) => setPassword(event.target.value)}/>
                </label><br/><br/>

                {errorMessage && <p>{errorMessage}</p>}

                <div className="button-row">
                    <button type="button" onClick={ onReturn }>Return</button>
                    <button type="submit">Log in</button>
                </div>
            </form>
        </main>   
    );
}

export default LoginScreen