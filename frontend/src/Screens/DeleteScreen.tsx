import { useState } from "react";

function DeleteScreen(){
    const [deleteUrlText, setDeleteUrlText] = useState<string>("");
    return(
        <main className="dashboard-content">
            <h1>Manage Files</h1>

            <section className="search-card">
                <h2>⚠️ Delete Files</h2>
                <p>Files, thumbnails, and all database entries will be permanently removed.</p>
                <p>File URLs to delete (one per line)</p>
                <textarea value={deleteUrlText} onChange={(event) => setDeleteUrlText(event.target.value)} placeholder="https://s3.amazonaws.com/bucket/file.jpg" />
                <button className="button-row" type="button">Delete Files</button>
            </section>
        </main>
    );
}

export default DeleteScreen;