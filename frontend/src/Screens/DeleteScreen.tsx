import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { authFetch } from "../services/api";
import { getErrorMessage, type DashboardOutletContext, type DeleteFileResponse } from "../utils";

/**
 * Provides a bulk file deletion interface.
 * 
 * Users can select media from My Uploads or manually enter permanent media
 * URLs. After a successful deletion, the shared URL selection is cleared and
 * DashboardScreen reloads the current user's media.
 * 
 * @returns the bulk media deletion page.
 */
function DeleteScreen() {
    const [deleteUrlText, setDeleteUrlText] = useState<string>("");

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const { selectedUrls, setSelectedUrls, refreshMyMedia, } = useOutletContext<DashboardOutletContext>();

    /**
     * Keeps the textarea synchronised with media selected from My Uploads.
     */
    useEffect(() => {
        setDeleteUrlText(selectedUrls.join("\n"));
    }, [selectedUrls]);

    /**
     * Deletes all unique media URLs entered or selected by the user.
     *
     * The backend verifies media ownership and removes the database record,
     * full media object, and thumbnail object when they are no longer
     * referenced by another media record.
     */
    async function handleDelete() {
        // Trim empty lines and remove duplicate URLs.
        const urls = Array.from(
            new Set(
                deleteUrlText
                    .split("\n")
                    .map((url) => url.trim())
                    .filter(Boolean)
            )
        );

        if (urls.length === 0) {
            setError("Please enter at least one file URL.");
            return;
        }

        setIsLoading(true);
        setError(null);
        setSuccessMessage(null);

        try {
            const data = await authFetch<DeleteFileResponse>("/delete_file", {
                method: "POST",
                body: JSON.stringify({
                    urls,
                }),
            });

            setSuccessMessage(
                `${data.deleted_count} file${data.deleted_count === 1 ? "" : "s"
                } deleted successfully.`
            );

            const failedResults = data.results.filter(
                (result) => !result.deleted
            );

            if (failedResults.length > 0) {
                setError(
                    failedResults.map(
                        (result) =>
                            `${result.url}: ${result.message ?? "Delete failed."
                            }`
                    )
                        .join("\n")
                );
            }

            if (data.deleted_count > 0) {
                setSelectedUrls([]);
                setDeleteUrlText("");
                // Refresh My Uploads without leaving the Delete page.
                await refreshMyMedia();
            }
        } catch (error) {
            setError(getErrorMessage(error));
        } finally {
            setIsLoading(false);
        }
    }

    return (
        <main className="dashboard-content">
            <h1>Manage Files</h1>

            <section className="search-card">
                <h2>⚠️ Delete Files</h2>
                <p>Files, thumbnails, and all database entries will be permanently removed.</p>
                <p>File URLs to delete (one per line)</p>
                <textarea value={deleteUrlText} onChange={(event) => {
                    const value = event.target.value;

                    setDeleteUrlText(value);
                    // Keep DashboardScreen's selected buttons in sync
                    // with URLs manually added or removed in the textarea.
                    setSelectedUrls(
                        Array.from(
                            new Set(value.split("\n").map((url) => url.trim()).filter(Boolean))
                        )
                    );
                }} placeholder="https://s3.amazonaws.com/bucket/file.jpg" />

                <button className="button-row" type="button" onClick={handleDelete}>
                    {isLoading ? "Deleting..." : "Delete Files"}
                </button>

                {successMessage && (
                    <p className="success-message">
                        {successMessage}
                    </p>
                )}

                {error && (
                    <p
                        className="error-message"
                        style={{ whiteSpace: "pre-wrap" }}
                    >
                        {error}
                    </p>
                )}
            </section>
        </main>
    );
}

export default DeleteScreen;