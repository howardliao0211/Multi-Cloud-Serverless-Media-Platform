
import { useEffect, useState } from "react";
import { Navigate, Route, useNavigate } from "react-router-dom";
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

function WelcomeScreen(){
  const navigate = useNavigate();
  const [showRegisterSuccess, setShowRegisterSuccess] = useState<boolean>(
    sessionStorage.getItem("showRegisterSuccess") === "true"
  );

  useEffect(() => {
    if (showRegisterSuccess) {
      sessionStorage.removeItem("registerSuccess");
    } 
  }, [showRegisterSuccess]);

  return(
    <main className="app-container">
      <h1>Welcome to Aussie EcoLens</h1>
      <br/>
      <img src={koala} alt="Aussie EcoLens logo" className="koala" />
      <p>A wildlife observation platform</p>
      <br/>
      {showRegisterSuccess && (
        <div className="status-message success">
          <p>Registration successful.</p>
          <p>Please check your email for the temporary password.</p>
          <p>Then log in using that temporary password.</p>
        </div>
      )}
    

    <div className="button-row">
      <button onClick={ ()=> navigate("/login")}>Login</button>
      <button onClick={ ()=> navigate("/register")}>Register</button>
    </div>
  </main>
  );
}

function App(){
  return (
    <Route>
      <Route path="/" element={<WelcomeScreen />} />
      <Route path="/login" element={<LoginScreen onLoginSuccess={() => window.location.href = "/dashboard"} 
        onReturn={() => window.location.href = "/"} />} />
      <Route path="/register" element={<RegisterScreen onRegisterSuccess={() => sessionStorage.setItem("registerSuccess", "true");
         window.location.href = "/"; }} onReturn={() => window.location.href = "/"} }/>} />
      <Route path="/dashboard" element={<ProtectedRoute><DashboardScreen /> onSignOut={() => {
        window.location.href = "/";
      }} /> </ProtectedRoute>} />
      
      <Route path="*" element={<Navigate to="/" replace />} />
    </Route>
  );
}
export default App