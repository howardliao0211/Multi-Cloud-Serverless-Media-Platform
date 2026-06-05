import { useState } from "react";
import { authFetch } from "../services/api";
import { getErrorMessage, type EditTagsResponse } from "../utils";

function TagsScreen() {
    const [tagUrlText, setTagUrlText] = useState<string>("");
    const [tagName, setTagName] = useState<string>("");
    const [tagCount, setTagCount] = useState<number>(1);
    const [tagQueries, setTagQueries] = useState<{ name: string; count: number }[]>([]);
    const [operation, setOperation] = useState<1 | 0>(1);
    
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);


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

    function handleApplyChanges() {
        const urls = tagUrlText.split("\n").map((url) => url.trim()).filter(Boolean);

        if (tagQueries.length === 0) {
            setError("Please add at least one tag.");
            return;
        }

        const tags = Object.fromEntries(
            tagQueries.map((tag) => [tag.name, tag.count])
        );

        try {
            const data = await authFetch<>("/query_species", {
                method: "POST",
                body: JSON.stringify({

                }),
            });


        } catch (error) {
            setError(getErrorMessage(error));
        } finally {

        }


    }

    return (
        <main className="dashboard-content">
            <h1>Manage Tags</h1>

            <section className="search-card">
                <h2>Bulk Tag Modification</h2>
                <p>File URLs (one per line):</p>
                <textarea value={tagUrlText} onChange={(event) => setTagUrlText(event.target.value)} placeholder="https://s3.amazonaws.com/bucket/file1.jpg" />
                <p>Tag :</p>
                <div className="search-row">
                    <input value={ } onChange={ } placeholder="koala, wombat, magpie" />
                </div>
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
                    <button type="button" onClick={() => setOperation(1)}>+ Add Tags</button>
                    <button type="button" onClick={() => setOperation(0)}>- Remove Tags</button>
                </div>
                <button className="button-row" type="button" onClick={handleApplyChanges}>Apply Changes</button>
            </section>

        </main>
    );
}

export default TagsScreen;