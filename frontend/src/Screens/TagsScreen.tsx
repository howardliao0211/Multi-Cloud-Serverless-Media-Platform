import { useState } from "react";

function TagsScreen(){
    const [tagUrlText, setTagUrlText] = useState<string>("");
    const [tagText, setTagText] = useState<string>("");
    const [operation, setOperation] = useState<1 | 0>(1);
    
    function handleTagChange(event: React.ChangeEvent<HTMLInputElement>){
        setTagText(event.target.value);
    }

    function handleApplyChanges(){
        const urls = tagUrlText.split("\n").map((url) => url.trim()).filter(Boolean);
        const tags = tagText.split(",").map((tag) => tag.trim()).filter(Boolean);
        
        console.log({
            urls,
            tags,
            operation,
        });

        
    }

    return(
        <main className="dashboard-content">
            <h1>Manage Tags</h1>

            <section className="search-card">
                <h2>Bulk Tag Modification</h2>
                <p>File URLs (one per line):</p>
                <textarea value={tagUrlText} onChange={(event) => setTagUrlText(event.target.value)} placeholder="https://s3.amazonaws.com/bucket/file1.jpg" />
                <p>Tags (comma-separated):</p>
                <div className="search-row">
                    <input value={tagText} onChange={handleTagChange} placeholder="koala, wombat, magpie"/>
                </div>
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