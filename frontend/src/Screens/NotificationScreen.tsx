import { useState } from "react";

function NotificationScreen(){
    const [tagName, setTagName] = useState<string>("");
    const [email, setEmail] = useState<string>("");
    const [subscribe, setSubscribe] = useState<{name: string; email: string}[]>([]);

    function handleSubscribe(){
        if (!tagName.trim()) return;
        if (!email.trim()) return;

        setSubscribe([
            ...subscribe, {
                name: tagName.trim(),
                email: email.trim(),
            }
        ]);

        setTagName("");
        setEmail("");
    }

    function handleRemove(name: string, email: string) {
        setSubscribe(
            subscribe.filter(
                (item) => !(item.name === name && item.email === email)
            )
        );
    }

    return(
        <main className="dashboard-content">
            <h1>Tag-based Notifications</h1>
            <p>Subscribe to receive email alerts when new files with specific species are uploaded.</p>

            <section className="search-card">
                <h2>Add Notification</h2>
                <div className="search-row">
                    <input value={tagName} onChange={(event) => setTagName(event.target.value)} placeholder="Species tag (e.g. koala)" />
                    <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="your@email.com"/>
                </div>
                <br/><button type="button" onClick={handleSubscribe}>Subscribe</button>
            </section>
            <section className="search-card">
                <div className="table-row table-header">
                    <span>Species Tag</span>
                    <span>Email</span>
                    <span></span>
                </div>

                {subscribe.length === 0 ? (
                    <p>No subscriptions yet.</p>
                ) : (
                    subscribe.map((item) => (
                        <div className="table-row" key={`${item.name}-${item.email}`}>
                            <span>{item.name}</span>
                            <span>{item.email}</span>
                            <button type="button" onClick={() => handleRemove(item.name, item.email)}>
                                Remove
                            </button>
                        </div>                        
                    ))       
                )}
            </section>
        </main>
    );    
}

export default NotificationScreen;