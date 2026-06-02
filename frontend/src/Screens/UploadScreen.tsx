import { useRef, useState } from "react";
import { calculateFileHash, createStatus, getMediaType, type StatusMessage } from "../utils";
import { authFetch } from "../services/api";

function UploadScreen(){
    const [files, setFiles] = useState<File[]>([]);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const [status, setStatus] = useState<StatusMessage>(createStatus("idle", ""));
    const [visibility, setVisibility] = useState<"private" | "public">("private");
    const [fileStatuses, setFileStatuses] = useState<FileUploadItem[]>([]);
    const [overallProgress, setOverallProgress] = useState<number>(0);
    const [mediaRecords, setMediaRecords] = useState<MediaRecordResponse[]>([]);

    function handleDrop(event: React.DragEvent<HTMLLabelElement>){
        event.preventDefault();

        if (event.dataTransfer.files){
            setFiles(Array.from(event.dataTransfer.files));
        }
    }

    type UploadResponse = {
        duplicate: boolean;
        upload_url?: string;
        expires_in?: number;
    };

    type FileUploadStatus = "waiting" | "uploading" | "uploaded" | "processing" | "processed" | "ready" | "failed" | "duplicate";

    type FileUploadItem = {
        name: string;
        status: FileUploadStatus;
    };

    type MediaRecordResponse = {
        owner_id: string;
        file_name: string;
        visibility: "private" | "public";
        full_file_path: string;
        thumbnail_path: string;
        tags: Record<string, string>;
        upload_status: "pending" | "uploaded" | "processing" | "ready" | "failed";
        error_message?: string;
    };

    type GetMediaResponse = {
        media_records: MediaRecordResponse[];
    };
    
    function handleFileChange(event: React.ChangeEvent<HTMLInputElement>){
        if (event.target.files){
            const newFiles = Array.from(event.target.files);
            setFiles(newFiles);
            setFileStatuses(newFiles.map((file) => ({ name: file.name, status: "waiting" })));
            setOverallProgress(0);
        }
    }

    function updateFileStatus(fileName: string, status: FileUploadStatus) {
        setFileStatuses((current) =>
            current.map((item) =>
                item.name === fileName ? { ...item, status } : item
            )
        );
    }

    function updateOverallProgress(doneCount: number, totalCount: number) {
        setOverallProgress(Math.round((doneCount / totalCount) * 100));
    }

    function getProgress(status: string): number {
        switch (status) {
            case "pending": return 20;
            case "uploaded": return 40;
            case "processing": return 70;
            case "ready": return 100;
            case "failed": return 100;
            default: return 0;
        }
    }

    async function fetchMediaStatus() {
        try {
            const endpoint = visibility === "private" ? "/get-private-media" : "/get-public-media";
            const response = await authFetch<GetMediaResponse>(endpoint, {
                method: "GET",
            });

            setMediaRecords(response.media_records);
        } catch (error) {
            console.error(error);
        }
    }

    async function handleUpload() {
        if (files.length === 0) return;

        setStatus(createStatus("loading", "Uploading..."));

        try{
            let uploadedCount = 0;
            let duplicatedFiles: string[] = [];
            let finishedCount = 0;

            for (const file of files){
                updateFileStatus(file.name, "uploading");

                // call upload API for each file
                const hash = await calculateFileHash(file);
                const mediaType = getMediaType(file);
                
                const data = await authFetch<UploadResponse>("/get-signed-url", {
                    method: "POST",
                    body: JSON.stringify({
                        filename: file.name,
                        checksum: hash,
                        media_type: mediaType,
                        visibility
                    }),
                });

                console.log(file.name, data);

                if (data.duplicate) {
                    duplicatedFiles.push(file.name);
                    updateFileStatus(file.name, "duplicate");
                    finishedCount++;
                    updateOverallProgress(finishedCount, files.length);
                    continue;
                }
            
                if (!data.upload_url){
                    updateFileStatus(file.name, "failed");
                    throw new Error("Upload URL was not returned.");
                }

                const uploadResponse = await fetch(data.upload_url, {
                    method: "PUT",
                    headers: {
                        "x-amz-meta-file_name": file.name,
                        "x-amz-meta-checksum": hash,
                    },
                    body: file,
                });
            
                if (!uploadResponse.ok) {
                    throw new Error(`S3 upload failed: ${uploadResponse.status}`);
                }

                uploadedCount++;
                updateFileStatus(file.name, "uploaded");

                finishedCount++;
                updateOverallProgress(finishedCount, files.length);
            }

            if (duplicatedFiles.length > 0){
                setStatus(createStatus("success", `Upload complete. ${uploadedCount} uploaded. Duplicate skipped: ${duplicatedFiles.join(", ")}`));
            } else {
                setStatus(createStatus("success", `Upload complete. ${uploadedCount} uploaded.`));
                
                fetchMediaStatus();
                const intervalId = setInterval(fetchMediaStatus, 3000);
                
                setTimeout(() => {
                    clearInterval(intervalId);
                }, 60000);
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
            
            <label className="upload-dropzone" onDrop={handleDrop} onDragOver={(event) => event.preventDefault()}>
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
            <div className="visibility-options">
                <label>
                    <input type="radio" name="visibility" value="private" checked={visibility === "private"} onChange={() => setVisibility("private")} />
                    Private
                </label>
                <label>
                    <input type="radio" name="visibility" value="public" checked={visibility === "public"} onChange={() => setVisibility("public")} />
                    Public
                </label>
            </div>
            <div className="button-row">
                <button type="button" onClick={handleUpload} disabled={files.length === 0}>
                    Upload
                </button>
            </div>

            {status.text && (
                <div className={`status-message ${status.type}`}>
                    <p>{status.text}</p>
                </div>
            )}
            
            {fileStatuses.length > 0 && (
                <div className="media-status-list">
                    <div className="upload-progress-header">
                    <span>Overall Progress</span>
                    <span> {overallProgress}%</span>
                    </div>

                    <div className="upload-progress-track">
                    <div
                        className="upload-progress-bar"
                        style={{ width: `${overallProgress}%` }}
                    />
                </div>

                {fileStatuses.map((item) => (
                    <div key={item.name} className="media-status-card">
                        <div className="media-status-header">
                        <span>{item.name}</span>
                        <span>{item.status}</span>
                        </div>
                    </div>
                    ))}
                </div>
            )}
            
            {mediaRecords.length > 0 && (
                <div className="media-status-list" >
                    {mediaRecords.map((record) => (
                        <div key={record.file_name} className="media-status-card">
                            <div className="media-status-header">
                                <span>{ record.file_name }</span>
                                <span>{ record.upload_status }</span>
                            </div>

                            <div className="media-status-track">
                                <div className={`upload-status-bar ${record.upload_status}`} style={{width: `${getProgress(record.upload_status)}%`}} />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </main>
    );
}

export default UploadScreen;