import { useRef, useState } from "react";
import { calculateFileHash, getMediaType } from "../utils";
import { authFetch } from "../services/api";

function UploadScreen(){
    const [files, setFiles] = useState<File[]>([]);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const [uploadMessage, setUploadMessage] = useState<string>("");

    function handleFileChange(event: React.ChangeEvent<HTMLInputElement>){
        if (event.target.files){
            setFiles(Array.from(event.target.files));
        }
    }

    type UploadResponse = {
        duplicate: boolean;
        upload_url?: string;
        expires?: number;
    };

    async function handleUpload() {
        if (files.length === 0) return;

        setUploadMessage("Uploading...");
        
        try{
            let uploadedCount = 0;
            let duplicatedFiles: string[] = [];

            for (const file of files){
                // call upload API for each file
                const hash = await calculateFileHash(file);
                const mediaType = getMediaType(file);
                
                const data = await authFetch<UploadResponse>("/get_signed_url", {
                    method: "POST",
                    body: JSON.stringify({
                        hash,
                        media_type: mediaType,
                    }),
                });

                console.log(file.name, data);

                if (data.duplicate) {
                    duplicatedFiles.push(file.name);
                    continue;
                }
            
                if (!data.upload_url){
                    throw new Error("Upload URL was not returned.");
                }

                const uploadResponse = await fetch(data.upload_url, {
                    method: "PUT",
                    body: file,
                });
            
                if (!uploadResponse.ok) {
                    throw new Error(`S3 upload failed: ${uploadResponse.status}`);
                }

                uploadedCount++;
            }

            if (duplicatedFiles.length > 0){
                setUploadMessage(`Upload complete. ${uploadedCount} uploaded. Duplicate skipped: ${duplicatedFiles.join(", ")}`);
            } else {
                setUploadMessage(`Upload complete. ${uploadedCount} uploaded.`);
            }
        } catch (error) {
            setUploadMessage("Upload failed.")
            console.error(error);
            }
        }
    
    return(
        <main className="dashboard-content"> 
            <h1>Upload Media</h1>
            <p>Upload images or videos for wildlife species detection.</p>
            
            <label className="upload-dropzone">
                <input ref={fileInputRef} className="file-input-hidden" type="file" 
                    accept="image/*,video/*" multiple onChange={handleFileChange} />
                <div className="upload-icon">📁</div>

                <h2>Click to browse or drag files here</h2>

                <p>Images (.jpg, .png, .webp) or Videos (.mp4, .mov)</p>

                {files.length > 0 && (
                    <div className="selected-file">
                        <p className="selected-file-title">Selected files:</p> {files.map((file) => (
                            <p key={file.name}>{file.name}</p>
                        ))}
                    </div>
                )}
            </label>
            
            <div className="button-row">
                <button type="button" onClick={handleUpload} disabled={files.length === 0}>
                    Upload
                </button>
                {uploadMessage && <p className="success-message">{uploadMessage}</p>}
            </div>
        </main>
    );
}

export default UploadScreen;