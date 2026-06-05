import { NavLink, Outlet, useLocation } from "react-router-dom";
import koala from "../assets/koala.png";
import animals from "../assets/animals.jpg";
import { useEffect, useState } from "react";
import {
    createStatus, getErrorMessage, getMyPrivateMedia, getMyPublicMedia,
    type StatusMessage, type MediaRecordResponse,
    getCurrentUserId
} from "../utils";
import { authFetch } from "../services/api";


function DashboardScreen() {
    const location = useLocation();
    const isDashboardHome = location.pathname === "/dashboard";
    const [myMediaRecords, setMyMediaRecords] = useState<MediaRecordResponse[]>([]);
    const [otherPublicMediaRecords, setOtherPublicMediaRecords] = useState<MediaRecordResponse[]>([]);
    const [status, setStatus] = useState<StatusMessage>(createStatus("idle", ""));

    const isSplitPage = location.pathname === "/dashboard/delete" || location.pathname === "/dashboard/tags";
    const [selectedUrls, setSelectedUrls] = useState<string[]>([]);
    const [selectedUrl, setSelectedUrl] = useState<string>("");

    const outletContext = {
        selectedUrls,
        setSelectedUrls,
        selectedUrl,
        setSelectedUrl,
    };

    function handleToggleSelectedUrl(url: string) {
        setSelectedUrls((prev) =>
            prev.includes(url)
                ? prev.filter((selectedUrls) => selectedUrls !== url)
                : [...prev, url]
        );
    }

    function mergeUniqueMediaRecords(records: MediaRecordResponse[]) {
        const map = new Map<string, MediaRecordResponse>();

        records.forEach((record) => {
            map.set(`${record.checksum}-${record.file_name}`, record);
        });
        return Array.from(map.values());
    }

    async function loadMyMedia() {
        const currentUserId = await getCurrentUserId();

        setStatus(createStatus("loading", "Loading your uploads..."));

        try {
            const privateData = await getMyPrivateMedia();

            const publicData = await getMyPublicMedia();

            const myPublicRecords = publicData.media_records.filter(
                (record) => record.owner_id === currentUserId
            );

            const otherPublicRecords = publicData.media_records.filter(
                (record) => record.owner_id !== currentUserId
            );

            setMyMediaRecords(
                mergeUniqueMediaRecords([
                    ...privateData.media_records,
                    ...myPublicRecords,
                ])
            );

            setOtherPublicMediaRecords(otherPublicRecords);

            setStatus(createStatus("success", ""));
        } catch (error) {
            setStatus(createStatus("error", getErrorMessage(error)));
        }
    }

    useEffect(() => {
        if (location.pathname === "/dashboard" || isSplitPage) {
            void loadMyMedia();
        }
    }, [location.pathname]);

    async function handleChangeVisibility(url: string, visibility: "private" | "public") {
        try {
            await authFetch("/change_visibility", {
                method: "PATCH",
                body: JSON.stringify({
                    url,
                    visibility,
                }),
            });
            await loadMyMedia();
        } catch (error) {
            setStatus(createStatus("error", getErrorMessage(error)));
        }
    }

    async function handleCopyThumbnailUrl(thumbnailUrl: string) {
        await navigator.clipboard.writeText(thumbnailUrl);
        setSelectedUrl(thumbnailUrl);
    }

    function readerMyUpload(showOthersPublic: boolean) {
        return (
            <main className="dashboard-content">
                <h1>My Uploads</h1>
                <p>Welcome to your media dashboard!</p>

                {status.text && (
                    <div className={`status-message ${status.type}`}>
                        <p>{status.text}</p>
                    </div>
                )}

                {myMediaRecords.length === 0 && status.type !== "loading" && (
                    <p>No uploaded files found.</p>
                )}

                <section className="media-cards-grid">
                    {myMediaRecords.map((record) => (
                        <article className="media-card" key={`${record.owner_id}-${record.checksum}-${record.file_name}`}>
                            <div className="media-thumbnail">
                                {record.thumbnail_presigned_url ? (
                                    <img
                                        src={record.thumbnail_presigned_url}
                                        alt={`${record.file_name} thumbnail`}
                                        onClick={() => {
                                            if (record.full_presigned_url) {
                                                window.open(record.full_presigned_url, "_blank");
                                            }
                                        }}
                                    />
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
                                                {tag} ({count})
                                            </p>
                                        ))
                                    ) : (
                                        <p>No tags yet</p>
                                    )}
                            </div>

                            <div className="media-url-actions">
                                <button type="button"
                                    disabled={!record.full_url}
                                    className={record.full_url && selectedUrls.includes(record.full_url)
                                        ? "selected"
                                        : ""
                                    }
                                    onClick={() => {
                                        if (record.full_url) {
                                            handleToggleSelectedUrl(record.full_url);
                                        }
                                    }}
                                >
                                    {record.full_url && selectedUrls.includes(record.full_url)
                                        ? "Selected"
                                        : "Select"}
                                </button>

                                <button
                                    type="button"
                                    disabled={!record.thumbnail_url}
                                    onClick={() => {
                                        if (record.thumbnail_url) {
                                            void handleCopyThumbnailUrl(record.thumbnail_url);
                                        }
                                    }}
                                >
                                    Copy Thumbnail URL
                                </button>

                                <button
                                    type="button"
                                    disabled={!record.full_url}
                                    onClick={() => {
                                        if (record.full_url) {
                                            handleChangeVisibility(
                                                record.full_url,
                                                record.visibility === "private" ? "public" : "private"
                                            );
                                        }
                                    }}
                                >
                                    Make {record.visibility === "private" ? "Public" : "Private"}
                                </button>
                            </div>

                        </article>
                    ))}
                </section>

                {showOthersPublic && (
                    <>
                        <h1 className="section-title">Other's Public</h1>

                        {otherPublicMediaRecords.length === 0 ? (
                            <p>No public files from other users found.</p>
                        ) : (
                            <section className="media-cards-grid">
                                {
                                    otherPublicMediaRecords.map((record) => (
                                        <article
                                            className="media-card"
                                            key={`${record.owner_id}-${record.file_name}-${record.full_url ?? ""}`}
                                        >
                                            <div className="media-thumbnail">
                                                {record.thumbnail_presigned_url ? (
                                                    <img
                                                        src={record.thumbnail_presigned_url}
                                                        alt={`${record.file_name} thumbnail`}
                                                        onClick={() => {
                                                            if (record.full_presigned_url) {
                                                                window.open(record.full_presigned_url, "_blank");
                                                            }
                                                        }}
                                                    />
                                                ) : (
                                                    <span>No thumbnail available</span>
                                                )}
                                            </div>

                                            <p>
                                                Visibility: <strong>{record.visibility}</strong>
                                            </p>

                                            <div className="media-tags-text">
                                                {Object.entries(record.tags).length > 0 ? (
                                                    Object.entries(record.tags).map(([tag, count]) => (
                                                        <p key={tag}>
                                                            {tag} ({count})
                                                        </p>
                                                    ))
                                                ) : (
                                                    <p>No tags yet</p>
                                                )}
                                            </div>

                                            <div className="media-url-actions">
                                                {/* <button
                                                    type="button"
                                                    disabled={!record.full_url}
                                                    onClick={() => {
                                                        if (record.full_url) {
                                                            navigator.clipboard.writeText(record.full_url);
                                                        }
                                                    }}
                                                >
                                                    Select
                                                </button> */}

                                                <button
                                                    type="button"
                                                    disabled={!record.thumbnail_url}
                                                    onClick={() => {
                                                        if (record.thumbnail_url) {
                                                            navigator.clipboard.writeText(record.thumbnail_url);
                                                        }
                                                    }}
                                                >
                                                    Copy Thumbnail URL
                                                </button>
                                            </div>
                                        </article>
                                    ))}
                            </section>
                        )}
                    </>
                )}
            </main>
        );
    }

    return (
        <div className="dashboard">
            <header className="dashboard-header">
                <NavLink to="/dashboard" className="brand">
                    <img src={koala} alt="Aussie EcoLens logo" className="brand-logo" />
                    <h1>Aussie EcoLens</h1>
                </NavLink>
                <nav className="dashboard-nav">
                    <NavLink to="/dashboard/delete">Delete</NavLink>
                    <NavLink to="/dashboard/tags">Tags</NavLink>
                    <NavLink to="/dashboard/upload">Upload</NavLink>
                    <NavLink to="/dashboard/search">Search</NavLink>
                    <NavLink to="/dashboard/notifications">Notifications</NavLink>
                    <NavLink to="/dashboard/account">Account</NavLink>
                </nav>
            </header>

            {isDashboardHome ? (
                readerMyUpload(true)
            ) : isSplitPage ? (
                <main className="dashboard-split-content">
                    <section className="dashboard-split-pane dashboard-split-left">
                        {readerMyUpload(false)}
                    </section>

                    <section className="dashboard-split-pane dashboard-split-right">
                        <Outlet
                            context={outletContext} />
                    </section>
                </main>
            ) : (
                <Outlet
                    context={outletContext} />
            )}

            <footer className="dashboard-footer">
                <img src={animals} alt="Aussie Ecolens footer illustration" />
            </footer>
        </div>
    );
}
export default DashboardScreen;