import { createStatus, getErrorMessage, type StatusMessage } from "../utils";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

/**
 * Displays the user registration form.
 *
 * The form collects the user's first name, last name, and email address,
 * then sends the registration request to the backend registration endpoint.
 * After a successful registration, the user is redirected to the login page.
 *
 * @returns the user registration form.
 */
function RegisterScreen() {
    const navigate = useNavigate();
    const [email, setEmail] = useState<string>("");
    const [firstName, setFirstName] = useState<string>("");
    const [lastName, setLastName] = useState<string>("");
    const [status, setStatus] = useState<StatusMessage>(createStatus("idle", ""));

    /**
     * Submits the registration details to the backend API.
     *
     * The backend creates the user account and returns an error response when
     * the registration cannot be completed. Successful registrations redirect
     * the user to the login page.
     *
     * @param event the registration form submission event.
     * @returns a promise that resolves after the registration request is handled.
     */
    async function handleRegister(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setStatus(createStatus("idle", ""));
        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL}/register_user`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    email,
                    firstName,
                    lastName,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || "Registration failed.");
            }

            sessionStorage.setItem("showRegisterSuccess", "true");
            navigate("/");
        } catch (error) {
            setStatus(createStatus("error", getErrorMessage(error)));
        }
    }

    return (
        <main className="app-container">
            <form onSubmit={handleRegister}>
                <h1>Registration</h1><br /><br />


                <label className="form-label">
                    First Name: <input type="text" value={firstName} onChange={(event) => setFirstName(event.target.value)} />
                </label>

                <label className="form-label">
                    Last Name: <input type="text" value={lastName} onChange={(event) => setLastName(event.target.value)} />
                </label>

                <label className="form-label">
                    Email: <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
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
                    <button type="submit">Create Account</button>
                </div>
            </form>
        </main>
    );
}

export default RegisterScreen