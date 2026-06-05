import { useState } from "react";
import { authFetch } from "../services/api";
import { getErrorMessage, type EditTagsResponse } from "../utils";

function TagsScreen() {
    const [tagUrlText, setTagUrlText] = useState<string>("");
    const [tagName, setTagName] = useState<string>("");
    const [tagCount, setTagCount] = useState<number>(1);
    const [tagQueries, setTagQueries] = useState<{ name: string; count: number }[]>([]);
    const [operation, setOperation] = useState<0 | 1>(1);

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);


    function handleAddTag() {
        const normalizedName = tagName.trim().toLowerCase();
        const normalizedCount = Math.max(1, Number(tagCount) || 1);

        if (!normalizedName) {
            setError("Please enter a tag name.");
            return;
        }

        setTagQueries((prev) => {
            const existingTag = prev.find((tag) => tag.name === normalizedName);

            if (existingTag) {
                return prev.map((tag) =>
                    tag.name === normalizedName
                        ? { ...tag, count: normalizedCount }
                        : tag
                );
            }

            return [
                ...prev,
                {
                    name: normalizedName,
                    count: normalizedCount,
                },
            ];
        });

        setTagName("");
        setTagCount(1);
        setError(null);
    }

    function handleRemoveTag(name: string) {
        setTagQueries((prev) =>
            prev.filter((tag) => tag.name !== name)
        );
    }

    async function handleApplyChanges() {
        const urls = Array.from(
            new Set(
                tagUrlText
                    .split("\n")
                    .map((url) => url.trim())
                    .filter(Boolean)
            )
        );

        if (urls.length === 0) {
            setError("Please enter at least one file URL.");
            return;
        }

        if (tagQueries.length === 0) {
            setError("Please add at least one tag.");
            return;
        }

        const tags = tagQueries.map((tag) => ({
            [tag.name]: tag.count,
        }));

        setIsLoading(true);
        setError(null);
        setSuccessMessage(null);

        try {
            const data = await authFetch<EditTagsResponse>("/edit_tags", {
                method: "POST",
                body: JSON.stringify({
                    urls,
                    tags,
                    operation,
                }),
            });

            setSuccessMessage(
                `${data.updated_count} file${data.updated_count === 1 ? "" : "s"
                } updated successfully.`
            );

            const failedResults = data.results.filter(
                (result) => !result.updated
            );

            if (failedResults.length > 0) {
                setError(
                    failedResults.map(
                        (result) =>
                            `${result.url}: ${result.message ?? "Update failed."
                            }`
                    )
                        .join("\n")
                );
            }

            if (data.updated_count > 0) {
                setTagQueries([]);
                setTagName("");
                setTagCount(1);
            }

        } catch (error) {
            setError(getErrorMessage(error));
        } finally {
            setIsLoading(false);
        }
    }

    return (
        <main className="dashboard-content">
            <h1>Manage Tags</h1>

            <section className="search-card">
                <h2>Bulk Tag Modification</h2>
                <p>File URLs (one per line):</p>
                <textarea value={tagUrlText} onChange={(event) => setTagUrlText(event.target.value)} placeholder="https://s3.amazonaws.com/bucket/file1.jpg" />
                <p>Tag and Count:</p>

                <div className="search-row">
                    <input
                        value={tagName}
                        onChange={(event) => setTagName(event.target.value)}
                        placeholder="Species (e.g. koala)"
                    />

                    <input
                        type="number"
                        min={1}
                        value={tagCount}
                        onChange={(event) => setTagCount(Number(event.target.value))}
                    />

                    <button type="button" onClick={handleAddTag}>
                        + Add
                    </button>
                </div>

                {tagQueries.length > 0 && (
                    <div className="selected-tags">
                        {tagQueries.map((tag) => (
                            <span
                                key={tag.name}
                                className="tag-pill"
                                onClick={() => handleRemoveTag(tag.name)}
                            >
                                {tag.name}: {tag.count}x
                            </span>
                        ))}
                    </div>
                )}

                <p>Operation</p>
                <div className="button-operator">
                    <button type="button"
                        className={operation === 1 ? "active" : ""}
                        onClick={() => setOperation(1)}
                        disabled={isLoading}>
                        + Add Tags
                    </button>

                    <button type="button"
                        className={operation === 0 ? "active" : ""}
                        onClick={() => setOperation(0)}
                        disabled={isLoading}>
                        - Remove Tags
                    </button>
                </div>
                <div className="apply-changes-row">
                    <button
                        type="button"
                        onClick={handleApplyChanges}
                        disabled={isLoading}
                    >
                        {isLoading ? "Applying..." : "Apply Changes"}
                    </button>
                </div>

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

export default TagsScreen;