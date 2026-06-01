
import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { getCurrentUser } from "aws-amplify/auth";
import LoginScreen from "./Screens/LoginScreen.tsx"
import RegisterScreen from "./Screens/RegisterScreen.tsx";
import DashboardScreen from "./Screens/DashboardScreen.tsx";
import koala from "./assets/koala.png";
import AccountScreen from "./Screens/AccountScreen.tsx";
import UploadScreen from "./Screens/UploadScreen.tsx";
import QueryScreen from "./Screens/QueryScreen.tsx";
import TagsScreen from "./Screens/TagsScreen.tsx";
import NotificationScreen from "./Screens/NotificationScreen.tsx";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
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

    checkAuth();
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

function WelcomeScreen() {
  const navigate = useNavigate();
  const [showRegisterSuccess, setShowRegisterSuccess] = useState<boolean>(
    sessionStorage.getItem("showRegisterSuccess") === "true"
  );

  useEffect(() => {
    if (showRegisterSuccess) {
      sessionStorage.removeItem("registerSuccess");
    }
  }, [showRegisterSuccess]);

  return (
    <main className="app-container">
      <h1>Welcome to Aussie EcoLens</h1>
      <br />
      <img src={koala} alt="Aussie EcoLens logo" className="koala" />
      <p>A wildlife observation platform</p>
      <br />
      {showRegisterSuccess && (
        <div className="status-message success">
          <p>Registration successful.</p>
          <p>Please check your email for the temporary password.</p>
          <p>Then log in using that temporary password.</p>
        </div>
      )}


      <div className="button-row">
        <button onClick={() => navigate("/login")}>Login</button>
        <button onClick={() => navigate("/register")}>Register</button>
      </div>
    </main>
  );
}

function LoginRoute() {
  const navigate = useNavigate();
  return (<LoginScreen
    onLoginSuccess={() => navigate("/dashboard")}
    onReturn={() => navigate("/")}
  />
  );
}

function RegisterRoute() {
  const navigate = useNavigate();
  return (<RegisterScreen
    onRegisterSuccess={() => {
      sessionStorage.setItem("showRegisterSuccess", "true");
      navigate("/");
    }}
    onReturn={() => navigate("/")}
  />
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<WelcomeScreen />} />
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/register" element={<RegisterRoute />} />

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardScreen />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="upload" replace />} />
        <Route path="upload" element={<UploadScreen />} />
        <Route path="search" element={<QueryScreen />} />
        <Route path="tags" element={<TagsScreen />} />
        <Route path="notifications" element={<NotificationScreen />} />
        <Route path="account" element={<AccountScreen />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
export default App