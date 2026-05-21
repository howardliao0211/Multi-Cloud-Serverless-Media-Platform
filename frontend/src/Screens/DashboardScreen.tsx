import { useState } from "react";
import UploadScreen from "./UploadScreen";
import QueryScreen from "./QueryScreen";
import TagsScreen from "./TagsScreen";
import NotificationScreen from "./NotificationScreen";
import AccountScreen from "./AccountScreen";
import koala from "../assets/koala.png";
import animals from "../assets/animals.jpg";

function DashboardScreen({ onSignOut }: { onSignOut: () => void }){
    const [view, setView] = useState<string>("Welcome");

    return(
        
        <div className="dashboard">
            <header className="dashboard-header">
                <div className="brand" role="button" tabIndex={0} onClick={() => setView("Welcome")}
                    onKeyDown={(event) => {if (event.key === "Enter") {setView("Welcome");}
                    }}
                >
                    <img src={koala} alt="Aussie EcoLens logo" className="brand-logo" />
                    <h1>Aussie EcoLens</h1>
                </div>
            <nav>
                <button onClick={() => setView("upload")}>Upload</button>
                <button onClick={() => setView("query")}>Search</button>
                <button onClick={() => setView("tags")}>Tags</button>
                <button onClick={() => setView("notification")}>Notifications</button>
                <button onClick={() => setView("account")}>Account</button>
            </nav>
            </header>
            <main className="dashboard-content"> 
                { view === "upload" && <UploadScreen/>}
                { view === "query" && <QueryScreen/>}
                { view === "tags" && <TagsScreen/>}
                { view === "notification" && <NotificationScreen/>}
                { view === "account" && <AccountScreen onSignOut={onSignOut}/>}
            </main>
            <footer className="dashboard-footer">
                <img src={animals} alt="Aussie Ecolens footer illustration" />
            </footer>
        </div>
    );
}

export default DashboardScreen;