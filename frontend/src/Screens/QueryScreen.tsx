import { useRef, useState } from "react";
import { authFetch } from "../services/api";
import { type QueryResult, type QueryResponse, type QueryThumbnailResponse} from "../utils";

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
    const [results, setResults] = useState<QueryResult[]>([]);

    function handleAddTag() {
        if (!tagName.trim()) return;

        setTagQueries([
            ...tagQueries, {
                name: tagName.trim(),
                count: tagCount,
            },
        ]);

        setTagName("");
        setTagCount(1);
    }

    function handleRemoveTag(name: string) {
        setTagQueries(tagQueries.filter(tag => tag.name !== name));
    }

    async function handleTagSearch() {
        const tags = Object.fromEntries(
            tagQueries.map((tag) => [tag.name, tag.count]));

        const data = await authFetch<QueryResponse>("/query_tags", {
            method: "POST",
            body: JSON.stringify({ tags }),
        });
        setResults(data.results);
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
                <button className={mode === "tags" ? "active" : ""} onClick={() => setMode("tags")}>
                    By Tags + Count
                </button>
                <button className={mode === "species" ? "active" : ""} onClick={() => setMode("species")}>
                    By Species
                </button>
                <button className={mode === "thumbnail" ? "active" : ""} onClick={() => setMode("thumbnail")}>
                    By Thumbnail URL
                </button>
                <button className={mode === "content" ? "active" : ""} onClick={() => setMode("content")}>
                    By File Content
                </button>
            </div>

            <section className="search-card">
                {mode === "tags" && (
                    <>
                        <h2>Add species tags with minimum count:</h2>
                        <div className="search-row">
                            <input value={tagName} onChange={(event) => setTagName(event.target.value)} placeholder="Species (e.g. koala)" />
                            <input type="number" min={1} value={tagCount} onChange={(event) => setTagCount(Number(event.target.value))} />
                            <button type="button" onClick={handleAddTag}>+ Add</button>
                        </div>
                        {tagQueries.length > 0 && (
                            <div className="selected-tags">
                                {tagQueries.map((tag) => (<span key={tag.name} className="tag-pill" onClick={() => handleRemoveTag(tag.name)}>
                                    {tag.name}: {tag.count} x
                                </span>))}
                            </div>
                        )}
                        <br /><button type="button" onClick={handleTagSearch}>Search</button>
                    </>
                )}

                {mode === "species" && (
                    <>
                        <div className="search-row">
                            <input value={species} onChange={(event) => setSpecies(event.target.value)} placeholder="Enter species name (eg. koala)" />
                        </div>
                        <br /><button type="button" onClick={handleAddTag}>Search</button>
                    </>
                )}

                {mode === "thumbnail" && (
                    <>
                        <h2>Enter thumbnail URL to get full-size image:</h2>
                        <div className="search-row">
                            <input value={thumbUrl} onChange={(event) => setThumbUrl(event.target.value)} placeholder="https://.../thumbnail.jpg" />
                        </div>
                        <br /><button type="button">Search</button>
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