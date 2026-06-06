import { NavLink, Outlet, useLocation } from "react-router-dom";
import koala from "../assets/koala.png";
import animals from "../assets/animals.jpg";
import { useEffect, useState } from "react";
import {
    createStatus, getErrorMessage, getMyPrivateMedia, getMyPublicMedia,
    type StatusMessage, type MediaRecordResponse,
    getCurrentUserId,
    maskOwnerId
} from "../utils";
import { authFetch } from "../services/api";

/**
 * Main authenticated dashboard layout.
 * 
 * This component:
 * -Displays the current user's uploads.
 * -Displays public media uploaded by other users on the dashboard home page.
 * -Provides shared media selection state to nested Delete and Tags pages.
 * -Supports changing media visibility.
 * -Passes shared state and refresh functions through React Router Outlet context.
 * 
 * @returns The dashboard layout and the currently selected nested page. 
 */
function DashboardScreen() {
    const location = useLocation();

    // Determines whether the user is currently viewing the dashboard home page.
    const isDashboardHome = location.pathname === "/dashboard";

    // Media owned by the currently authentiacated user.
    const [myMediaRecords, setMyMediaRecords] = useState<MediaRecordResponse[]>([]);
    
    // Public media owned by other users.
    const [otherPublicMediaRecords, setOtherPublicMediaRecords] = useState<MediaRecordResponse[]>([]);

    // Delete and Tags pages use the split-screen layout.
    const isSplitPage = location.pathname === "/dashboard/delete" || location.pathname === "/dashboard/tags";
    
    // Full media URLs selected for bulk tag editing or deletion.
    const [selectedUrls, setSelectedUrls] = useState<string[]>([]);
    
    // Thumbnail URL prepared for the Search by Thumbnail URL filed.
    const [selectedUrl, setSelectedUrl] = useState<string>("");

    const [status, setStatus] = useState<StatusMessage>(createStatus("idle", ""));

    /**
     * Shared data made available to nested dashboard pages through Outlet.
     * 
     * DeleteScreen and TagScreen use selectedUrls.
     * QureyScrren uses selectedUrl.
     * Nested pages can call refreshMyMedia after modifying backend data.
     */
    const outletContext = {
        selectedUrls,
        setSelectedUrls,
        selectedUrl,
        setSelectedUrl,
        refreshMyMedia: loadMyMedia,
    };

    /**
     * Adds or removes a full media URL from the bulk selection.
     * 
     * @param url the permanent full media URL to toggle. 
     */
    function handleToggleSelectedUrl(url: string) {
        setSelectedUrls((prev) =>
            prev.includes(url)
                ? prev.filter((selectedUrls) => selectedUrls !== url)
                : [...prev, url]
        );
    }

    /**
     * Removes duplicate media records.
     * A record is identified by the combination of checksum and file name.
     * 
     * @param records media records that may contain duplicates.
     * @returns a new array containing only unique media records.
     */
    function mergeUniqueMediaRecords(records: MediaRecordResponse[]) {
        const map = new Map<string, MediaRecordResponse>();

        records.forEach((record) => {
            map.set(`${record.checksum}-${record.file_name}`, record);
        });
        return Array.from(map.values());
    }

    /**
     * Loads media required by the dashboard.
     * 
     * Private media is already restricted to the current user by the backend.
     * Public media is separated into:
     * -the current user's public media.
     * -public media owned by other users.
     */
    async function loadMyMedia() {
        setStatus(createStatus("loading", "Loading your uploads..."));

        try {
            const currentUserId = await getCurrentUserId();
            const privateData = await getMyPrivateMedia();
            const publicData = await getMyPublicMedia();

            const myPublicRecords = publicData.media_records.filter(
                (record) => record.owner_id === currentUserId
            );

            const otherPublicRecords = publicData.media_records.filter(
                (record) => record.owner_id !== currentUserId
            );

            // Combine the current user's private and public media.
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

    /**
     * Reloads media whenever the user enters the dashboard home, Delete page,
     * or Tags page.
     */
    useEffect(() => {
        if (location.pathname === "/dashboard" || isSplitPage) {
            void loadMyMedia();
        }
    }, [location.pathname]);

    /**
     * Changes the visibility of a media record and refreshes the dashboard.
     * 
     * @param url the permanent full URL identifying the media record. 
     * @param visibility the target visibility value.
     */
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

    /**
     * Copies a permanent thumbnail URL and prepares it for thumbnail search.
     * When the user opens the Search page, QueryScreen reads selectedUrl from the Outlet context.
     * 
     * @param thumbnailUrl the permanent thumbnail URL to copy.
     */
    async function handleCopyThumbnailUrl(thumbnailUrl: string) {
        await navigator.clipboard.writeText(thumbnailUrl);
        setSelectedUrl(thumbnailUrl);
    }

    /**
     * Renders media owned by the current user.
     * On the dashboard home page, public media belonging to other users
     * can also be displayed beneath the user's uploads.
     * 
     * @param showOthersPublic whether to render public media from other users.
     * @returns the My Uploads dashboard section.
     */
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
                                    {record.thumbnail_url && selectedUrl.includes(record.thumbnail_url)
                                        ? "Copied to Search"
                                        : "Copy Thumbnail URL"}
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
                                                Owner: <strong>{maskOwnerId(record.owner_id)}</strong>
                                            </p>
                                            
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
                                                <button
                                                    type="button"
                                                    disabled={!record.thumbnail_url}
                                                    onClick={() => {
                                                        if (record.thumbnail_url) {
                                                            void handleCopyThumbnailUrl(record.thumbnail_url);
                                                        }
                                                    }}
                                                >
                                                    {record.thumbnail_url && selectedUrl.includes(record.thumbnail_url)
                                                        ? "Copied to Search"
                                                        : "Copy Thumbnail URL"}
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