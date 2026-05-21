import { useState } from "react";

function TagsScreen(){
    const [urls, setUrls] = useState<string[]>([]);
    const [tagList, setTagList] = useState<string[]>([]);

    function handleUrlChange(){
    }

    function handleTagChange(){

    }

    return(
        <main className="dashboard-content">
            <h1>Manage Tags and Files</h1>

            <section className="search-card">
                <h2>Bulk Tag Modification</h2>
                <p>File URLs (one per line):</p>
                <div className="search-row">
                    <input value={urls} onChange={handleUrlChange} placeholder="https://s3.amazonaws.com/bucket/file1.jpg" />
                </div>
                <p>Tags (comma-seperated):</p>
                <div className="search-row">
                    <input value={tagList} onChange={handleTagChange} placeholder="koala, wambat, magpie"/>
                </div>
                <p>Operation</p>
                <div className="button-operator">
                    <button type="button">+ Add Tags</button>
                    <button type="button">- Remove Tags</button>
                </div>
                <button className="button-row">Apply Changes</button>
            </section>

            <section className="search-card">
                <h2>⚠️ Delete Files</h2>
                <p>Files, thumbnails, and all datavase entries will be permanently removed.</p>
                <p>File URLs to delete (one per line)</p>
                <div className="search-row">
                    <input value={urls} onChange={handleUrlChange} placeholder="https://s3.amazonaws.com/bucket/file.jpg" />
                </div>
                <button className="button-row">Delete Files</button>
            </section>
        </main>
    );
}

export default TagsScreen;