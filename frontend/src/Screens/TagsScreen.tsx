import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { authFetch } from "../services/api";
import { getErrorMessage, type DashboardOutletContext, type EditTagsResponse } from "../utils";

/**
 * Provides a bulk interface for adding or removing tags from media files.
 *
 * Users can select media URLs from My Uploads or enter URLs manually. Multiple
 * tags and counts can be applied to all selected media records in one request.
 * After a successful update, the My Uploads section is refreshed.
 *
 * @returns The bulk tag-management interface.
 */
function TagsScreen() {
    const [tagUrlText, setTagUrlText] = useState<string>("");
    const [tagName, setTagName] = useState<string>("");
    const [tagCount, setTagCount] = useState<number>(1);
    const [tagQueries, setTagQueries] = useState<{ name: string; count: number }[]>([]);
    const [operation, setOperation] = useState<0 | 1>(1);

    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const { selectedUrls, setSelectedUrls, refreshMyMedia,} = useOutletContext<DashboardOutletContext>();

    /**
     * Keeps the URL textarea synchronised with media selected in My Uploads.
     */
    useEffect(() => {
        setTagUrlText(selectedUrls.join("\n"));
    }, [selectedUrls]);

    /**
     * Adds a normalised tag and count to the pending tag query.
     *
     * If the tag already exists, its count is replaced instead of creating
     * a duplicate entry.
     */
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

    /**
     * Removes a tag from the pending bulk-update request.
     *
     * @param name the normalised tag name to remove.
     */
    function handleRemoveTag(name: string) {
        setTagQueries((prev) =>
            prev.filter((tag) => tag.name !== name)
        );
    }

    /**
     * Applies the selected tag operation to all unique media URLs.
     *
     * The backend uses operation_key 1 to add tags and operation_key 0 to
     * remove tags. Successfully modified media is reloaded in DashboardScreen.
     *
     * @returns a promise that resolves after the update request is handled.
     */
    async function handleApplyChanges() {
        // Trim blank lines and remove duplicate media URLs.
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
                    operation_key: operation,
                }),
            });

            const failedResults = data.results.filter(
                (result) => !result.updated
            );

            if (data.updated_count > 0) {
                setSuccessMessage(
                    `${data.updated_count} file${data.updated_count === 1 ? "" : "s"
                    } updated successfully.`
                );
            } else {
                setSuccessMessage(null);
            }

            if (failedResults.length > 0) {
                setError(
                    failedResults
                        .map((result) => {
                            const fileLabel =
                                result.file_name ??
                                "Selected file";

                            return `${fileLabel}: ${result.message ?? "Update failed."
                                }`;
                        })
                        .join("\n")
                );
            }

            if (data.updated_count > 0) {
                setSelectedUrls([]);
                setTagUrlText("");
                setTagQueries([]);
                setTagName("");
                setTagCount(1);

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
            <h1>Manage Tags</h1>

            <section className="search-card">
                <h2>Bulk Tag Modification</h2>
                <p>File URLs (one per line):</p>
                <textarea value={tagUrlText} onChange={(event) => {
                    const value = event.target.value;

                    setTagUrlText(value);

                    setSelectedUrls(
                        Array.from(
                            new Set(value.split("\n").map((url) => url.trim()).filter(Boolean))
                        )
                    );
                }} placeholder="https://s3.amazonaws.com/bucket/file1.jpg" />
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
                            <button
                                key={tag.name}
                                className="tag-pill"
                                onClick={() => handleRemoveTag(tag.name)}
                            >
                                {tag.name}: {tag.count}x
                            </button>
                        ))}
                    </div>
                )}

                <p>Operation</p>
                <div className="button-operator">
                    <button type="button"
                        className={`add-operation ${operation === 1 ? "active" : ""}`}
                        onClick={() => setOperation(1)}
                        disabled={isLoading}>
                        + Add Tags
                    </button>

                    <button type="button"
                        className={`remove-operation ${operation === 0 ? "active" : ""}`}
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