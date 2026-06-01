
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { getCurrentUser } from "aws-amplify/auth";
import LoginScreen from "./Screens/LoginScreen.tsx"
import RegisterScreen from "./Screens/RegisterScreen.tsx";
import DashboardScreen from "./Screens/DashboardScreen.tsx";
import koala from "./assets/koala.png";

function ProtectedRoute({ children }: { children: React.ReactNode}) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [checkingAuth, setCheckingAuth] = useState<boolean>(true);

  useEffect(() => {
    async function checkAuth() {
      try {
        await getCurrentUser();
        setIsAuthenticated(true);
      } catch (error) {
        setIsAuthenticated(false);
      } finally {
        setCheckingAuth(false);
      }
    }
  }, []);

  if (checkingAuth) {
    return <main className="app-container">
      <p>Loading...</p>
    </main>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}


function App(){
  const [view, setView] = useState<string>("Welcome");
  const [showRegisterSuccess, setShowRegisterSuccess] = useState<boolean>(false);


  function handleSuccess(){
    console.log("login successfull");
    setView("dashboard");
  } 

  if (view === "login"){
    return <LoginScreen onLoginSuccess={handleSuccess} 
    onReturn={() => setView("Welcome")}/>;
  }
  if (view === "register") {
    return (
      <RegisterScreen
        onRegisterSuccess={() => {
          setShowRegisterSuccess(true);
          setView("Welcome");
        }}
        onReturn={() => setView("Welcome")}
      />
    );
  }
  if (view === "dashboard"){
    return <DashboardScreen onSignOut={() => setView("Welcome")}/>;
  }

  return(
    <main className="app-container">
      <h1>Welcome to Aussie EcoLens</h1><br/>
      <img src={koala} alt="Aussie EcoLens logo" className="koala" />
      <p>A wildlife observation platform</p><br/>

      {showRegisterSuccess && (
        <div className="status-message success">
          <p>Registration successful.</p>
          <p>Please check your email for the temporary password.</p>
          <p>Then log in using that temporary password.</p>
        </div>
      )}

      <div className="button-row">
        <button onClick={ ()=> setView("login")}>Login</button>
        <button onClick={ ()=> setView("register")}>Register</button>
      </div>
    </main>
  );
}
export default App