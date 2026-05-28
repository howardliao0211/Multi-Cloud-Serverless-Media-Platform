import { useRef, useState } from "react";
import { calculateFileHash, createStatus, getMediaType, type StatusMessage } from "../utils";
import { authFetch } from "../services/api";

function UploadScreen(){
    const [files, setFiles] = useState<File[]>([]);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const [status, setStatus] = useState<StatusMessage>(createStatus("idle", ""));

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

        setStatus(createStatus("idle", "Uploading..."));

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
                setStatus(createStatus("success", `Upload complete. ${uploadedCount} uploaded. Duplicate skipped: ${duplicatedFiles.join(", ")}`));
            } else {
                setStatus(createStatus("success", `Upload complete. ${uploadedCount} uploaded.`));
            }
        } catch (error) {
            setStatus(createStatus("error", "Upload failed."));
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
                {status.text && (
                    <div className={`status-message ${status.type}`}>
                        <p>{status.text}</p>
                    </div>
                )}
            </div>
        </main>
    );
}

export default UploadScreen;