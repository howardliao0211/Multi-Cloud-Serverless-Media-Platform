import { useRef, useState } from "react";
import { authFetch } from "../services/api";
import {
    getErrorMessage,
    isValidMediaFile,
    type QueryTagsResponse,
    type QuerySpeciesResponse,
    type QueryThumbnailUrlResponse,
    type QueryFileResponse,
    type QueryMediaResult,
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

    const [results, setResults] = useState<QueryMediaResult[]>([]);
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

            setResults(data.results ?? []);
            setResultCount(data.count ?? data.results?.length ?? 0);
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

            setResults(data.results ?? []);
            setResultCount(data.count ?? data.results?.length ?? 0);
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

            const result: QueryMediaResult = {
                checksum: data.checksum,
                file_name: data.file_name,
                visibility: data.visibility,
                media_type: null,
                url: data.url,
                thumbnail_url: data.thumbnail_url,
                tags: {},
            };

            setResults([result]);
            setResultCount(1);
        } catch (error) {
            setError(getErrorMessage(error));
        } finally {
            setIsLoading(false);
        }
    }

    function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
        if (event.target.files && event.target.files[0]) {
            setFile(event.target.files[0]);
        }
    }

    function handleDrop(event: React.DragEvent<HTMLLabelElement>) {
        event.preventDefault();

        if (event.dataTransfer.files && event.dataTransfer.files[0]) {
            setFile(event.dataTransfer.files[0]);
        }
    }

    type UploadResponse = {
        uploadUrl: string;
        fileUrl: string;
    };

    async function handleUpload() {
        if (!file) return;

        // call upload API for each file
        console.log("Uploading", file.name);

        const data = await authFetch<UploadResponse>("/upload-url", {
            method: "POST",
            body: JSON.stringify({
                fileName: file.name,
                fileType: file.type,
            }),
        });

        await fetch(data.uploadUrl, {
            method: "PUT",
            headers: {
                "Content-Type": file.type,
            },
            body: file,
        });
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
                        <label className="content-dropzone" onDrop={handleDrop} onDragOver={(event) => event.preventDefault()}>
                            <input ref={fileInputRef} className="file-input-hidden" type="file"
                                accept="image/*,video/*" onChange={handleFileChange} />
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
                            <button type="button" onClick={handleUpload} disabled={!file}>
                                Upload
                            </button>
                        </div>
                    </>
                )}
            </section>
        </main>
    );
}
export default QueryScreen;