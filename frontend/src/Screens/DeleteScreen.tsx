import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { authFetch } from "../services/api";
import { getErrorMessage, type DeleteFileResponse, type EditTagsResponse } from "../utils";

type DashboardOutletContext = {
    selectedUrls: string[];
    setSelectedUrls: React.Dispatch<React.SetStateAction<string[]>>;
}

function DeleteScreen() {
    const [deleteUrlText, setDeleteUrlText] = useState<string>("");

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const { selectedUrls, setSelectedUrls, } = useOutletContext<DashboardOutletContext>();

    useEffect(() => {
        setDeleteUrlText(selectedUrls.join("\n"));
    }, [selectedUrls]);

    async function handleDelete() {
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

            if (data.deleted_count > 0){
                setSelectedUrls([]);
                setDeleteUrlText("");
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