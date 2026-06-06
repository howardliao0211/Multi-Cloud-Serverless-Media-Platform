import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { authFetch } from "../services/api";

import {
    getErrorMessage,
    isValidMediaFile,
    type DashboardOutletContext,
    type MediaRecordResponse,
    type QueryTagsResponse,
    type QuerySpeciesResponse,
    type QueryThumbnailUrlResponse,
    type QueryFileResponse,
    calculateFileHash,
    getMediaType,
    maskOwnerId,
} from "../utils";

/**
 * Supported media search methods.
 *
 * -tags: Finds media containing the requested tags and minimum counts.
 * -species: Finds media containing a specific species.
 * -thumbnail: Finds the full media record from a thumbnail URL.
 * -content: Detects species from an uploaded file and finds matching media.
 */
type SearchMode = "tags" | "species" | "thumbnail" | "content";

/**
 * Provides multiple search methods for wildlife media.
 *
 * The screen supports tag-count, species, thumbnail URL, and file-content
 * searches. Search results display thumbnails, metadata, tags, and permanent
 * URLs. Thumbnail URLs can also be copied into the shared thumbnail search
 * field through DashboardScreen's Outlet context.
 *
 * @returns the wildlife media search interface.
 */
function QueryScreen() {
    // Controls the currently displayed search form.
    const [mode, setMode] = useState<SearchMode>("tags");

    // Tag-count search input and selected query tags.
    const [tagName, setTagName] = useState<string>("");
    const [tagCount, setTagCount] = useState<number>(1);
    const [tagQueries, setTagQueries] = useState<{ name: string; count: number }[]>([]);

    // Species search input.
    const [species, setSpecies] = useState<string>("");

    // Shared thumbnail URL stored by DashboardScreen.
    const { selectedUrl, setSelectedUrl } = useOutletContext<DashboardOutletContext>();

    const [copiedFullUrl, setCopiedFullUrl] = useState<string>("");

    // File-content search state.
    const [file, setFile] = useState<File | null>(null);
    const fileInputRef = useRef<HTMLInputElement | null>(null);

    // Search response and UI feedback state.
    const [results, setResults] = useState<MediaRecordResponse[]>([]);
    const [detectedTags, setDetectedTags] = useState<Record<string, number>>({});
    const [resultCount, setResultCount] = useState<number>(0);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    /**
     * Clears the current search results and feedback.
     *
     * Input values are preserved so users can switch search modes without
     * losing everything they previously entered.
     */
    function resetSearchState() {
        setResults([]);
        setDetectedTags({});
        setResultCount(0);
        setError(null);
    }

    /**
     * Switches to another search mode and clears the previous result state.
     *
     * @param nextMode the search mode to display.
     */
    function handleModeChange(nextMode: SearchMode) {
        setMode(nextMode);
        resetSearchState();
    }


    /**
    * Adds a normalised tag and minimum count to the tag query.
    *
    * Adding an existing tag replaces its previous count instead of creating
    * a duplicate entry.
    */
    function handleAddTag() {
        const normalizedName = tagName.trim().toLowerCase();
        const normalizedCount = Math.max(1, Number(tagCount) || 1);

        if (!normalizedName) return;

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
    }

    /**
     * Removes a tag from the current tag-count query.
     *
     * @param name the normalised tag name to remove.
     */
    function handleRemoveTag(name: string) {
        setTagQueries(tagQueries.filter(tag => tag.name !== name));
    }

    /**
     * Finds media that satisfies all selected tag-count requirements.
     *
     * @returns a promise that resolves after the search request is handled.
     */
    async function handleTagSearch() {
        if (tagQueries.length === 0) {
            setError("Please add at least one tag.");
            return;
        }

        const tags = Object.fromEntries(
            tagQueries.map((tag) => [tag.name, tag.count])
        );

        setIsLoading(true);
        setError(null);
        setDetectedTags({});

        try {
            const data = await authFetch<QueryTagsResponse>("/query_tags", {
                method: "POST",
                body: JSON.stringify({ tags }),
            });

            setResults(data.media_records ?? []);
            setResultCount(data.media_records?.length ?? 0);
        } catch (error) {
            setError(getErrorMessage(error));
        } finally {
            setIsLoading(false);
        }
    }

    /**
     * Finds media matching a normalised species name.
     *
     * @returns a promise that resolves after the search request is handled.
     */
    async function handleSpeciesSearch() {
        const normalizedSpecies = species.trim().toLowerCase();

        if (!normalizedSpecies) {
            setError("Please enter a species name.");
            return;
        }

        const containsMultipleSpecies =
            normalizedSpecies.includes(",") ||
            normalizedSpecies.includes(";") ||
            normalizedSpecies.includes("\n");

        if (containsMultipleSpecies) {
            setError("Please enter only one species.");
            return;
        }

        setIsLoading(true);
        setError(null);
        setDetectedTags({});

        try {
            const data = await authFetch<QuerySpeciesResponse>("/query_species", {
                method: "POST",
                body: JSON.stringify({
                    species: normalizedSpecies,
                }),
            });

            setResults(data.media_records ?? []);
            setResultCount(data.media_records?.length ?? 0);
        } catch (error) {
            setError(getErrorMessage(error));
        } finally {
            setIsLoading(false);
        }
    }

    /**
     * Automatically switches to thumbnail mode when DashboardScreen provides
     * a thumbnail URL through Outlet context.
     */
    useEffect(() => {
        if (!selectedUrl.trim()) return;

        setMode("thumbnail");
        setResults([]);
        setDetectedTags({});
        setResultCount(0);
        setError(null);
    }, [selectedUrl]);

    /**
     * Finds the media record associated with the entered thumbnail URL.
     *
     * @returns a promise that resolves after the thumbnail lookup is handled.
     */
    async function handleThumbnailSearch() {
        const normalizedThumbnailUrl = selectedUrl.trim();

        if (!normalizedThumbnailUrl) {
            setError("Please enter a thumbnail URL.");
            return;
        }

        setIsLoading(true);
        setError(null);
        setDetectedTags({});

        try {
            const data = await authFetch<QueryThumbnailUrlResponse>(
                "/query_thumbnail_url",
                {
                    method: "POST",
                    body: JSON.stringify({
                        thumbnail_url: normalizedThumbnailUrl,
                    }),
                }
            );

            const records = data.media_records ?? [];

            setResults(records);
            setResultCount(records.length);

            if (records.length === 0) {
                setError("No media found for this thumbnail URL.");
            }
        } catch (error) {
            setError(getErrorMessage(error));
        } finally {
            setIsLoading(false);
        }
    }

    /**
     * Copies a thumbnail URL and prepares it for thumbnail URL search.
     *
     * @param thumbnailUrl the permanent thumbnail URL to copy and reuse.
     * @returns a promise that resolves after the clipboard operation completes.
     */
    async function handleUseThumbnailUrl(thumbnailUrl: string) {
        try {
            await navigator.clipboard.writeText(thumbnailUrl);

            setSelectedUrl(thumbnailUrl);
            setMode("thumbnail");
            setError(null);

            window.scrollTo({
                top: 0,
                behavior: "smooth",
            });
        } catch (error) {
            setError(getErrorMessage(error));
        }
    }

    /**
     * Searches for media that matches species detected from an uploaded file.
     *
     * The file checksum and media type are sent to the backend query endpoint.
     *
     * @returns a promise that resolves after the content search is handled.
     */
    async function handleContentSearch() {
        if (!file) {
            setError("Please select a file.");
            return;
        }

        if (!isValidMediaFile(file)) {
            setError("Unsupported file type. Please upload JPG, PNG, WEBP, MP4, or MOV.");
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const hash = await calculateFileHash(file);
            const mediaType = getMediaType(file);

            const data = await authFetch<QueryFileResponse>("/query_file", {
                method: "POST",
                body: JSON.stringify({
                    file_name: file.name,
                    checksum: hash,
                    media_type: mediaType,
                }),
            });

            setDetectedTags(data.detected_tags ?? {});
            setResults(data.media_records ?? []);
            setResultCount(data.media_records?.length ?? 0);
        } catch (error) {
            setError(getErrorMessage(error));
        } finally {
            setIsLoading(false);
        }
    }

    /**
     * Validates and stores a file selected through the file input.
     *
     * @param event the file input change event.
     */
    function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
        const selectedFile = event.target.files?.[0];

        if (!selectedFile) return;

        if (!isValidMediaFile(selectedFile)) {
            setError("Unsupported file type. Please upload JPG, PNG, WEBP, MP4, or MOV.");
            setFile(null);
            return;
        }

        setFile(selectedFile);
        setError(null);
    }

    /**
     * Validates and stores a file dropped onto the content-search area.
     *
     * @param event the drag-and-drop event containing the selected file.
     */
    function handleDrop(event: React.DragEvent<HTMLLabelElement>) {
        event.preventDefault();

        const droppedFile = event.dataTransfer.files?.[0];

        if (!droppedFile) return;

        if (!isValidMediaFile(droppedFile)) {
            setError("Unsupported file type. Please upload JPG, PNG, WEBP, MP4, or MOV.");
            setFile(null);
            return;
        }

        setFile(droppedFile);
        setError(null);
    }

    return (
        <main className="dashboard-content">
            <h1>Search Files</h1>
            <p>Find wildlife media using different search methods.</p>

            <div className="button-row">
                <button className={mode === "tags" ? "active" : ""} onClick={() => handleModeChange("tags")}>
                    By Tags + Count
                </button>
                <button className={mode === "species" ? "active" : ""} onClick={() => handleModeChange("species")}>
                    By Species
                </button>
                <button className={mode === "thumbnail" ? "active" : ""} onClick={() => handleModeChange("thumbnail")}>
                    By Thumbnail URL
                </button>
                <button className={mode === "content" ? "active" : ""} onClick={() => handleModeChange("content")}>
                    By File Content
                </button>
            </div>

            <section className="search-card">
                {mode === "tags" && (
                    <>
                        <h2>Add species tags with minimum count:</h2>

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

                        <br />

                        <button type="button" onClick={handleTagSearch} disabled={isLoading}>
                            {isLoading ? "Searching..." : "Search"}
                        </button>
                    </>
                )}

                {mode === "species" && (
                    <>
                        <h2>Search by species:</h2>

                        <div className="search-row">
                            <input
                                value={species}
                                onChange={(event) => setSpecies(event.target.value)}
                                placeholder="Enter one species name (eg. koala)"
                            />
                        </div>

                        <br />

                        <button type="button" onClick={handleSpeciesSearch} disabled={isLoading}>
                            {isLoading ? "Searching..." : "Search"}
                        </button>
                    </>
                )}

                {mode === "thumbnail" && (
                    <>
                        <h2>Enter thumbnail URL to get full-size image:</h2>
                        <div className="search-row">
                            <textarea value={selectedUrl}
                                onChange={(event) => setSelectedUrl(event.target.value)}
                                placeholder="https://.../thumbnail.jpg" />
                        </div>
                        <br />
                        <button
                            type="button"
                            onClick={() => void handleThumbnailSearch()}
                            disabled={isLoading || !selectedUrl.trim()}
                        >
                            {isLoading ? "Searching..." : "Search"}
                        </button>
                    </>
                )}

                {mode === "content" && (
                    <>
                        <h2>Upload a file to find all database files with matching species:</h2>

                        <label
                            className="content-dropzone"
                            onDrop={handleDrop}
                            onDragOver={(event) => event.preventDefault()}
                        >
                            <input
                                ref={fileInputRef}
                                className="file-input-hidden"
                                type="file"
                                accept="image/*,video/*"
                                onChange={handleFileChange}
                            />

                            <div className="upload-icon">📁</div>

                            <h2>Drop file here or click to browse</h2>

                            <p>Images (.jpg, .png, .webp) or Videos (.mp4, .mov)</p>

                            {file && (
                                <div className="selected-file">
                                    <p className="selected-file-title">Selected file:</p>
                                    <p>{file.name}</p>
                                </div>
                            )}
                        </label>

                        <div className="button-row">
                            <button
                                type="button"
                                onClick={handleContentSearch}
                                disabled={!file || isLoading}
                            >
                                {isLoading ? "Searching..." : "Search by Content"}
                            </button>
                        </div>
                    </>
                )}

                {error && <p className="error-message">{error}</p>}
            </section>

            {Object.keys(detectedTags).length > 0 && (
                <section className="search-card">
                    <h2>Detected Tags</h2>

                    <div className="selected-tags">
                        {Object.entries(detectedTags).map(([tag, count]) => (
                            <span key={tag} className="tag-pill">
                                {tag} : {count} x
                            </span>
                        ))}
                    </div>
                </section>
            )}

            <section className="search-card">
                <h2>Results</h2>

                {isLoading && <p>Searching...</p>}

                {!isLoading && !error && resultCount === 0 && (
                    <p>No results yet.</p>
                )}

                {!isLoading && !error && resultCount > 0 && (
                    <p>
                        {resultCount} result{resultCount === 1 ? "" : "s"} found.
                    </p>
                )}

                <section className="media-cards-grid">
                    {results.map((record) => (
                        <article className="media-card" key={`${record.owner_id}-${record.file_name}-${record.full_url ?? ""}`} >
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
                            <div className="media-card-body">
                                <p className="media-file-name">
                                    File Name:
                                    <strong>{record.file_name}</strong>
                                </p>

                                <p>
                                    Owner: <strong>{maskOwnerId(record.owner_id)}</strong>
                                </p>

                                <p>
                                    Visibility: <strong>{record.visibility}</strong>
                                </p>

                                <div className="media-tags-text">
                                    {Object.entries(record.tags ?? {}).length > 0 ? (
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
                                    {mode !== "thumbnail" && (
                                        <button
                                            type="button"
                                            disabled={!record.thumbnail_url}
                                            onClick={() => {
                                                if (record.thumbnail_url) {
                                                    void handleUseThumbnailUrl(record.thumbnail_url);
                                                }
                                            }}
                                        >
                                            {record.thumbnail_url === selectedUrl
                                                ? "Copied to Search"
                                                : "Copy Thumbnail URL"}
                                        </button>
                                    )}

                                    <button
                                        type="button"
                                        disabled={!record.full_url}
                                        onClick={async () => {
                                            if (!record.full_url) return;

                                            try {
                                                await navigator.clipboard.writeText(record.full_url);
                                                setCopiedFullUrl(record.full_url);

                                                window.setTimeout(() => {
                                                    setCopiedFullUrl("");
                                                }, 2000);
                                            } catch (error) {
                                                setError(getErrorMessage(error));
                                            }
                                        }}
                                    >
                                        {record.full_url === copiedFullUrl
                                            ? "Copied Successfully"
                                            : "Copy Full URL"}
                                    </button>
                                </div>
                            </div>
                        </article>
                    ))}
                </section>
            </section>
        </main >
    );
}
export default QueryScreen;