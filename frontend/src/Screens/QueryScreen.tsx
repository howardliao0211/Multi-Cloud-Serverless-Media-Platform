import { useRef, useState } from "react";
import { authFetch } from "../services/api";

import {
    getErrorMessage,
    isValidMediaFile,
    type MediaRecordResponse,
    type QueryTagsResponse,
    type QuerySpeciesResponse,
    type QueryThumbnailUrlResponse,
    type QueryFileResponse,
} from "../utils";

type SearchMode = "tags" | "species" | "thumbnail" | "content";

function QueryScreen() {
    const [mode, setMode] = useState<SearchMode>("tags");
    const [tagName, setTagName] = useState<string>("");
    const [tagCount, setTagCount] = useState<number>(1);
    const [species, setSpecies] = useState<string>("");
    const [tagQueries, setTagQueries] = useState<{ name: string; count: number }[]>([]);
    const [thumbUrl, setThumbUrl] = useState<string>("");
    const [file, setFile] = useState<File | null>(null);
    const fileInputRef = useRef<HTMLInputElement | null>(null);

    const [results, setResults] = useState<MediaRecordResponse[]>([]);
    const [detectedTags, setDetectedTags] = useState<Record<string, number>>({});
    const [resultCount, setResultCount] = useState<number>(0);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    function resetSearchState() {
        setResults([]);
        setDetectedTags({});
        setResultCount(0);
        setError(null);
    }

    function handleModeChange(nextMode: SearchMode) {
        setMode(nextMode);
        resetSearchState();
    }

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

    function handleRemoveTag(name: string) {
        setTagQueries(tagQueries.filter(tag => tag.name !== name));
    }

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

    async function handleSpeciesSearch() {
        const normalizedSpecies = species.trim().toLowerCase();

        if (!normalizedSpecies) {
            setError("Please enter a species name.");
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

    async function handleThumbnailSearch() {
        const normalizedThumbUrl = thumbUrl.trim();

        if (!normalizedThumbUrl) {
            setError("Please enter a thumbnail URL.");
            return;
        }

        setIsLoading(true);
        setError(null);
        setDetectedTags({});

        try {
            const data = await authFetch<QueryThumbnailUrlResponse>("/query_thumbnail_url", {
                method: "POST",
                body: JSON.stringify({
                    thumbnail_url: normalizedThumbUrl,
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

    async function handleContentSearch() {
        if (!file) {
            setError("Please select a file.");
            return;
        }

        if (!isValidMediaFile(file)) {
            setError("Unsupported file type. Please upload JPG, PNG, WEBP, MP4, or MOV.");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);

        setIsLoading(true);
        setError(null);

        try {
            const data = await authFetch<QueryFileResponse>("/query_file", {
                method: "POST",
                body: formData,
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
                                placeholder="Enter species name (eg. koala)"
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
                            <input value={thumbUrl}
                                onChange={(event) => setThumbUrl(event.target.value)}
                                placeholder="https://.../thumbnail.jpg" />
                        </div>
                        <br />
                        <button type="button" onClick={handleThumbnailSearch} disabled={isLoading}>
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

                            <p>
                                File Name: <strong>{record.file_name}</strong>
                            </p>

                            <p>
                                Visibility: <strong>{record.visibility}</strong>
                            </p>

                            <div className="media-tags-text">
                                {Object.entries(record.tags ?? {}).length > 0 ? (
                                    Object.entries(record.tags).map(([tag, count]) => (
                                        <p key={tag}>
                                            Tag: {tag}; Count: {count}
                                        </p>
                                    ))
                                ) : (
                                    <p>No tags yet</p>
                                )}
                            </div>
                        </article>
                    ))}
                </section>
            </section>
        </main >
    );
}
export default QueryScreen;