import { getErrorMessage } from "../utils";
import { useState } from "react";

function RegisterScreen({ onRegisterSuccess, onReturn, }: 
    {onRegisterSuccess: () => void; onReturn: () => void;}){
    
    const [email, setEmail] = useState<string>("");
    const [firstName, setFirstName] = useState<string>("");
    const [lastName, setLastName] = useState<string>("");
    const [errorMessage, setErrorMessage] = useState<string>("");
    
    async function handleRegister(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setErrorMessage("");
        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL}/register-user`,{
                 method: "POST",
                 headers: {"Content-Type": "application/json"},
                 body: JSON.stringify({
                    email,
                    firstName,
                    lastName,
                 }),
            });
            if (!response.ok) throw new Error("Registration failed.");

            onRegisterSuccess();
        } catch (error) {
            console.log(error);
            setErrorMessage(getErrorMessage(error));
        }
    }

    return (
        <main className="app-container"> 
            <form onSubmit={handleRegister}>
                <h1>Registration</h1><br/><br/>


                <label className="form-label">
                    First Name: <input type="text" value={firstName} onChange={(event) => setFirstName(event.target.value)}/>
                </label>

                <label className="form-label">
                    Last Name: <input type="text" value={lastName} onChange={(event) => setLastName(event.target.value)}/>
                </label>

                <label className="form-label">
                    Email: <input type="email" value={email} onChange={(event) => setEmail(event.target.value)}/>
                </label><br/><br/>


                {errorMessage && <p>{errorMessage}</p>}

                <div className="button-row">
                    <button type="button" onClick={ onReturn }>Return</button>
                    <button type="submit">Create Account</button>
                </div>
            </form>
        </main>
    );
}

export default RegisterScreen