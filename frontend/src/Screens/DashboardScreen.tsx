import { NavLink, Outlet, useLocation } from "react-router-dom";
import koala from "../assets/koala.png";
import animals from "../assets/animals.jpg";
import { useEffect, useState } from "react";
import {
    createStatus, getErrorMessage,
    type StatusMessage, type GetMediaResponse, type MediaRecordResponse,
    getCurrentUserId
} from "../utils";
import { authFetch } from "../services/api";


function DashboardScreen() {
    const location = useLocation();
    const isDashboardHome = location.pathname === "/dashboard";
    const [mediaRecords, setMediaRecords] = useState<MediaRecordResponse[]>([]);
    const [status, setStatus] = useState<StatusMessage>(createStatus("idle", ""));

    useEffect(() => {
        async function loadMyMedia() {
            const currentUserId = await getCurrentUserId();

            setStatus(createStatus("loading", "Loading your uploads..."));

            try {
                const privateData = await authFetch<GetMediaResponse>("/get_private_media", {
                    method: "GET",
                });

                const publicData = await authFetch<GetMediaResponse>("/get_public_media", {
                    method: "GET",
                });

                const myPublicRecords = publicData.media_records.filter(
                    (record) => record.owner_id === currentUserId
                );

                setMediaRecords([
                    ...privateData.media_records,
                    ...myPublicRecords,
                ]);
                setStatus(createStatus("success", ""));
            } catch (error) {
                setStatus(createStatus("error", getErrorMessage(error)));
            }
        }

        loadMyMedia();
    }, [location.state]);

    return (
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

            {isDashboardHome ? (
                <main className="dashboard-content">
                    <h1>My Uploads</h1>
                    <p>Welcome to your media dashboard!</p>

                    {status.text && (
                        <div className={`status-message ${status.type}`}>
                            <p>{status.text}</p>
                        </div>
                    )}

                    {mediaRecords.length === 0 && status.type !== "loading" && (
                        <p>No uploaded files found.</p>
                    )}

                    <section className="media-cards-grid">
                        {mediaRecords.map((record) => (
                            <article className="media-card" key={`${record.owner_id}-${record.file_name}`}>
                                <div className="media-thumbnail">
                                    {record.thumbnail_presigned_url ? (
                                        <img src={record.thumbnail_presigned_url} alt={`${record.file_name} thumbnail`} />
                                    ) : (
                                        <span>No thumbnail available</span>
                                    )}
                                </div>
                                <p>
                                    Visibility: <strong>{record.visibility}</strong>
                                </p>

                                <div className="media-tags-text">
                                    {Object.entries(record.tags).length > 0
                                        ? (Object.entries(record.tags)
                                            .map(([tag, count]) => (
                                                <p key={tag}>
                                                    Tag: {tag}; Count: {count}
                                                </p>
                                            ))
                                        ) : (
                                            <p>No tags yet</p>
                                        )}
                                </div>

                                <div className="media-url-actions">
                                    <button type="button" onClick={() => navigator.clipboard.writeText(record.full_presigned_url)}>
                                        Copy Full URL
                                    </button>
                                    <button type="button" onClick={() => navigator.clipboard.writeText(record.thumbnail_presigned_url)}>
                                        Copy Thumbnail URL
                                    </button>
                                </div>

                            </article>
                        ))}
                    </section>
                </main>
            ) : (
                <Outlet />
            )}

            <footer className="dashboard-footer">
                <img src={animals} alt="Aussie Ecolens footer illustration" />
            </footer>
        </div>
    );
}

export default DashboardScreen;