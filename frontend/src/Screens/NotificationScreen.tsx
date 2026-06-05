import { useState } from "react";
import { authFetch } from "../services/api";
import {
    type SNSSubscribeResponse,
    type SNSUnsubscribeRequest,
    getErrorMessage,
} from "../utils";

function NotificationScreen() {
    const [tagName, setTagName] = useState<string>("");
    const [email, setEmail] = useState<string>("");
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState<string | null>(null);

    const [subscribe, setSubscribe] = useState<
        { name: string; email: string }[]
    >([]);

    async function handleSubscribe() {
        if (!tagName.trim()) return;
        if (!email.trim()) return;

        setError(null);
        setMessage(null);

        const tags = tagName
            .split(",")
            .map((tag) => tag.trim().toLowerCase())
            .filter((tag) => tag.length > 0);

        if (tags.length === 0) return;

        const normalizedEmail = email.trim().toLowerCase();

        try {
            const data = await authFetch<SNSSubscribeResponse>("/subscribe_tags", {
                method: "POST",
                body: JSON.stringify({
                    email: normalizedEmail,
                    tags: tags,
                }),
            });
            
            if (data.subscription_arn != null) {
                setSubscribe([
                    ...subscribe,
                    {
                        name: tags.join(", "),
                        email: normalizedEmail,
                    },
                ]);
            };

            setMessage(
                data.message
            );

        } catch (error) {
            setError(getErrorMessage(error));
        } finally {
            setTagName("");
            setEmail("");
        }
    }

    async function handleRemove(name: string, email: string) {
        setError(null);
        setMessage(null);

        try {
            const data = await authFetch<SNSUnsubscribeRequest>("/unsubscribe_tags", {
                method: "POST",
                body: JSON.stringify({
                    email: email.trim().toLowerCase(),
                }),
            });

            setMessage(data.message);

            setSubscribe((prevSubscribe) =>
                prevSubscribe.filter(
                    (item) => !(item.name === name && item.email === email)
                )
            );
        } catch (error) {
            setError(getErrorMessage(error));
        }
    }

    return(
        <main className="dashboard-content">
            <h1>Tag-based Notifications</h1>
            <p>Subscribe to receive email alerts when new files with specific species are uploaded.</p>

            <section className="search-card">
                <h2>Add Notification</h2>
                <div className="search-row">
                    <input value={tagName} onChange={(event) => setTagName(event.target.value)} placeholder="Species tags separated with comma, e.g. koala, wombat" />
                    <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="your@email.com"/>
                </div>
                <br/><button type="button" onClick={handleSubscribe}>Subscribe</button>
            </section>
            <section className="search-card">
                <div className="table-row table-header">
                    <span>Species Tags</span>
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
            {message && (
                <p className="success-message">
                    {message}
                </p>
            )}

            {error && (
                <p className="error-message">
                    {error}
                </p>
            )}
        </main>
    );
}

export default NotificationScreen;