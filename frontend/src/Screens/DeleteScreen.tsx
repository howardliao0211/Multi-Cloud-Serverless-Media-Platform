import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { authFetch } from "../services/api";
import { getErrorMessage, type EditTagsResponse } from "../utils";

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

    async function handleDelete(){

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

                <button className="button-row" type="button" onClick={handleDelete}>Delete Files</button>

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