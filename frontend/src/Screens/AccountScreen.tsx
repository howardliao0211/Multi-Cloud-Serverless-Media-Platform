import { useEffect, useState } from "react";
import { fetchUserAttributes, signOut } from "aws-amplify/auth";
import { useNavigate } from "react-router-dom";

function AccountScreen(){
    const navigate = useNavigate();

    // Store the signed-in user's Cognito profile attributes.
    const [email, setEmail] = useState<string>(""); 
    const [firstName, setFirstName] = useState<string>(""); 
    const [lastName, setLastName] = useState<string>("");

    useEffect(() => {
        // Load the current user's attributes once when the page is mounted.
        async function loadUserInfo() {
            const attributes = await fetchUserAttributes();

            setEmail(attributes.email ?? "");
            setFirstName(attributes.given_name ?? "");
            setLastName(attributes.family_name ?? "");
        }
        loadUserInfo();
    }, []);

    // Sign the user out of Cagnito and return them to the loading page.
    async function handleSignOut() {
        await signOut();
        navigate("/");
    }

    return(
        <main className="dashboard-content">
            <h1>Account</h1>

            <section className="account-card">
                <div className="account-profile">
                    <div className="account-avatar">
                        {/* Display the user's first initial as a simple profile avatar. */}
                        {firstName ? firstName[0].toUpperCase() : "?"}
                    </div>

                    <div>
                        <h2>User Information</h2>
                        <p className="account-email">{email}</p>
                    </div>
                </div>
                <div className="account-row">
                    <span>First Name</span>
                    <strong>{firstName}</strong>
                </div>      
                <div className="account-row">
                    <span>Last Name</span>
                    <strong>{lastName}</strong>
                </div>             
            </section>


            <div className="button-row">
                <button type="button" onClick={ handleSignOut }>Log out</button>
            </div>
        </main>
    );
}

export default AccountScreen;