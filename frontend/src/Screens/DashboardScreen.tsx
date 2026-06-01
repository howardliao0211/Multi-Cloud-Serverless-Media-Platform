import { NavLink, Outlet } from "react-router-dom";
import koala from "../assets/koala.png";
import animals from "../assets/animals.jpg";

function DashboardScreen(){
    return(
        
        <div className="dashboard">
            <header className="dashboard-header">
                <NavLink to="/dashboard" className="brand">
                    <img src={koala} alt="Aussie EcoLens logo" className="brand-logo" />
                    <h1>Aussie EcoLens</h1>
                </NavLink>
                <nav className="dashboard-nav">
                    <NavLink to="/dashboard/upload">Upload</NavLink>
                    <NavLink to="/dashboard/search">Search</NavLink>
                    <NavLink to="/dashboard/tags">Tags</NavLink>
                    <NavLink to="/dashboard/notifications">Notifications</NavLink>
                    <NavLink to="/dashboard/account">Account</NavLink>
                </nav>
            </header>
            <Outlet />
            <footer className="dashboard-footer">
                <img src={animals} alt="Aussie Ecolens footer illustration" />
            </footer>
        </div>
    );
}

export default DashboardScreen;