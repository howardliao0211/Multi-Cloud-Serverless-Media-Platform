import { useEffect, useState } from "react";
import { authFetch } from "../services/api";
import {
    type SNSSubscribeResponse,
    type SNSGetSubscriptionResponse,
    getErrorMessage,
    getCurrentUserEmail
} from "../utils";

function NotificationScreen() {
    const [tagName, setTagName] = useState<string>("");
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(false);

    const [subscribe, setSubscribe] = useState<SNSGetSubscriptionResponse>({
        email: "",
        tags: [],
        state: "none"
    });

    function clearNotification() {
        setError(null);
        setMessage(null);
    }

    async function handleGetSub(showError = true) {
        setIsLoading(true);

        try {
            const email: string = await getCurrentUserEmail();
            const emailToQuery = email.trim().toLowerCase();

            if (!emailToQuery) {
                if (showError) {
                    setError("User email not found.");
                }
                return;
            }

            const query = new URLSearchParams({
                email: emailToQuery
            });

            const data = await authFetch<SNSGetSubscriptionResponse>(
                `/get_subscription?${query.toString()}`,
                {
                    method: "GET"
                }
            );

            setSubscribe({
                email: data.email,
                tags: data.tags ?? [],
                state: data.state ?? "none"
            });
        } catch (error) {
            if (showError) {
                setError(getErrorMessage(error));
            }

            setSubscribe({
                email: "",
                tags: [],
                state: "none"
            });
        } finally {
            setIsLoading(false);
        }
    }

    useEffect(() => {
        handleGetSub(false);
    }, []);

    async function handleSubscribe() {
        const email: string = await getCurrentUserEmail();

        if (!tagName.trim()) {
            setError("Please enter at least one tag.");
            return;
        }

        if (!email.trim()) {
            setError("User email not found.");
            return;
        }

        clearNotification();

        const tags = tagName
            .split(",")
            .map((tag) => tag.trim().toLowerCase())
            .filter((tag) => tag.length > 0);

        if (tags.length === 0) {
            setError("Please enter at least one valid tag.");
            return;
        }

        const normalizedEmail = email.trim().toLowerCase();

        try {
            const data = await authFetch<SNSSubscribeResponse>(
                "/subscribe_tags",
                {
                    method: "POST",
                    body: JSON.stringify({
                        email: normalizedEmail,
                        tags
                    })
                },
                true
            );

            setMessage(data.message);

            await handleGetSub();
        } catch (error) {
            setError(getErrorMessage(error));
        } finally {
            setTagName("");
        }
    }

    async function handleRemove() {
        const email: string = await getCurrentUserEmail();

        if (!email.trim()) {
            setError("No subscription email found.");
            return;
        }

        clearNotification();

        try {
            const data = await authFetch<{ message: string }>(
                "/unsubscribe_tags",
                {
                    method: "POST",
                    body: JSON.stringify({
                        email: email.trim().toLowerCase()
                    })
                },
                true
            );

            setMessage(data.message);

            await handleGetSub();
        } catch (error) {
            setError(getErrorMessage(error));
        }
    }

    return (
        <main className="dashboard-content">
            {(message || error) && (
                <div className="notification-overlay">
                    <div
                        className={
                            error
                                ? "notification-box notification-error"
                                : "notification-box notification-success"
                        }
                    >
                        <button
                            type="button"
                            className="notification-close"
                            onClick={clearNotification}
                        >
                            ×
                        </button>

                        <h3>{error ? "Error" : "Success"}</h3>

                        <p>{error ?? message}</p>
                    </div>
                </div>
            )}

            <h1>Tag-based Notifications</h1>
            <p>
                Subscribe to receive email alerts when new files with specific
                species are uploaded.
            </p>

            <section className="search-card">
                <h2>Add Notification</h2>

                <div className="search-row">
                    <input
                        value={tagName}
                        onChange={(event) => setTagName(event.target.value)}
                        placeholder="Species tags separated with comma, e.g. koala, wombat"
                    />
                </div>

                <br />

                <button type="button" onClick={handleSubscribe}>
                    Subscribe
                </button>
            </section>

            <section className="search-card">
                <h2>Current Subscription</h2>

                <div className="table-row table-header">
                    <span>Species Tags</span>
                    <span>Email</span>
                    <span>Status</span>
                    <span></span>
                </div>

                {isLoading ? (
                    <p>Loading subscription...</p>
                ) : subscribe.state === "none" ? (
                    <p>No subscriptions yet.</p>
                ) : (
                    <div className="table-row" key={subscribe.email}>
                        <span>
                            {subscribe.tags.length > 0
                                ? subscribe.tags.join(", ")
                                : "No tags"}
                        </span>

                        <span>{subscribe.email}</span>

                        <span>{subscribe.state}</span>

                        <button type="button" onClick={handleRemove}>
                            Remove
                        </button>
                    </div>
                )}
            </section>
        </main>
    );
}

export default NotificationScreen;
