import { NavLink, Outlet, useLocation } from "react-router-dom";
import koala from "../assets/koala.png";
import animals from "../assets/animals.jpg";
import { useEffect, useRef, useState } from "react";
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

    const mediaPollingRef = useRef<number | null>(null);


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
     * Loads the current user's media and public media from other users.
     *
     * @param silent - When true, refreshes data without showing the loading state.
     * @returns The current user's combined private and public media records.
     */
    async function loadMyMedia(
        silent = false
    ): Promise<MediaRecordResponse[]> {
        if (!silent) {
            setStatus(
                createStatus(
                    "loading",
                    "Loading your uploads..."
                )
            );
        }

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
            const myRecords =
                mergeUniqueMediaRecords([
                    ...privateData.media_records,
                    ...myPublicRecords,
                ]);

            setMyMediaRecords(myRecords);
            setOtherPublicMediaRecords(
                otherPublicRecords
            );

            if (!silent) {
                setStatus(
                    createStatus("success", "")
                );
            }

            return myRecords;
        } catch (error) {
            setStatus(createStatus(
                "error",
                getErrorMessage(error)
            ));

            return [];
        }
    }

    /**
     * Checks whether a media record is still being processed.
     *
     * @param record - The media record to inspect.
     * @returns True when processing has not reached a final state.
     */
    function isMediaStillProcessing(
        record: MediaRecordResponse
    ): boolean {
        return (
            record.upload_status === "pending" ||
            record.upload_status === "uploaded" ||
            record.upload_status === "processing"
        );
    }

    /**
     * Stops the dashboard media polling interval.
     */
    function stopMediaPolling(): void {
        if (mediaPollingRef.current !== null) {
            window.clearInterval(
                mediaPollingRef.current
            );

            mediaPollingRef.current = null;
        }
    }

    /**
     * Refreshes dashboard media in the background while uploads are processing.
     */
    function startMediaPolling(): void {
        if (mediaPollingRef.current !== null) {
            return;
        }

        mediaPollingRef.current =
            window.setInterval(async () => {
                const records =
                    await loadMyMedia(true);

                const hasProcessingMedia =
                    records.some(
                        isMediaStillProcessing
                    );

                if (!hasProcessingMedia) {
                    stopMediaPolling();
                }
            }, 3000);
    }

    /**
     * Reloads media whenever the user enters the dashboard home, Delete page,
     * or Tags page.
     */
    useEffect(() => {
        async function initialiseMedia(): Promise<void> {
            const shouldLoadMedia =
                location.pathname === "/dashboard" ||
                isSplitPage;

            if (!shouldLoadMedia) {
                stopMediaPolling();
                return;
            }

            // Initial load shows the normal loading message.
            const records = await loadMyMedia();

            if (records.some(isMediaStillProcessing)) {
                startMediaPolling();
            } else {
                stopMediaPolling();
            }
        }

        void initialiseMedia();

        return () => {
            stopMediaPolling();
        };
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
     * Toggles a thumbnail URL for thumbnail-based search.
     *
     * Clicking an unselected thumbnail URL copies it to the clipboard and stores
     * it in the shared search state. Clicking the same URL again clears the
     * selected state.
     *
     * @param thumbnailUrl the permanent thumbnail URL to select or clear.
     * @returns a promise that resolves after the clipboard operation is handled.
     */
    async function handleCopyThumbnailUrl(
        thumbnailUrl: string
    ): Promise<void> {
        try {
            if (selectedUrl === thumbnailUrl) {
                setSelectedUrl("");
                return;
            }

            await navigator.clipboard.writeText(thumbnailUrl);
            setSelectedUrl(thumbnailUrl);
        } catch (error) {
            setStatus(
                createStatus("error", getErrorMessage(error))
            );
        }
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
                                    className={
                                        record.thumbnail_url === selectedUrl
                                            ? "selected"
                                            : ""
                                    }
                                    onClick={() => {
                                        if (record.thumbnail_url) {
                                            void handleCopyThumbnailUrl(
                                                record.thumbnail_url
                                            );
                                        }
                                    }}
                                >
                                    {record.thumbnail_url === selectedUrl
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
                                                {record.upload_status === "failed" ? (
                                                    <span>
                                                        {record.error_message ??
                                                            "Processing failed"}
                                                    </span>
                                                ) : record.upload_status !== "ready" ? (
                                                    <span>Processing...</span>
                                                ) : record.thumbnail_presigned_url ? (
                                                    <img
                                                        src={record.thumbnail_presigned_url}
                                                        alt={`${record.file_name} thumbnail`}
                                                        onClick={() => {
                                                            if (record.full_presigned_url) {
                                                                window.open(
                                                                    record.full_presigned_url,
                                                                    "_blank",
                                                                    "noopener,noreferrer"
                                                                );
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
                                                    className={
                                                        record.thumbnail_url === selectedUrl
                                                            ? "selected"
                                                            : ""
                                                    }
                                                    onClick={() => {
                                                        if (record.thumbnail_url) {
                                                            void handleCopyThumbnailUrl(
                                                                record.thumbnail_url
                                                            );
                                                        }
                                                    }}
                                                >
                                                    {record.thumbnail_url === selectedUrl
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