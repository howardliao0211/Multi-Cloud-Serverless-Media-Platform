import { useRef, useState } from "react";
import { calculateFileHash, createStatus, getMediaType, type StatusMessage} from "../utils";
import { authFetch } from "../services/api";

function UploadScreen(){
    const [files, setFiles] = useState<File[]>([]);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const [status, setStatus] = useState<StatusMessage>(createStatus("idle", ""));
    const [visibility, setVisibility] = useState<"private" | "public">("private");
    const [fileStatuses, setFileStatuses] = useState<FileUploadItem[]>([]);
    const [overallProgress, setOverallProgress] = useState<number>(0);

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

    type FileUploadStatus = "waiting"
        | "uploading"
        | "pending"
        | "uploaded"
        | "processing"
        | "ready"
        | "failed"
        | "duplicate";

    type FileUploadItem = {
        name: string;
        status: FileUploadStatus;
    };

    type MediaUploadStatus = "pending" | "uploaded" | "processing" | "ready" | "failed";

    type MediaUploadStatusResponse = {
        upload_status: MediaUploadStatus;
        error_message?: string | null;
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
        setFileStatuses((current) => {
            const updated = current.map((item) =>
            item.name === fileName ? { ...item, status } : item
            );

            const finishedCount = updated.filter(
            (item) => item.status === "ready" || 
                      item.status === "failed" || 
                      item.status === "duplicate"
            ).length;

            updateOverallProgress(finishedCount, updated.length);

            if (finishedCount === updated.length) {
            const readyCount = updated.filter((item) => item.status === "ready").length;
            const failedCount = updated.filter((item) => item.status === "failed").length;
            const duplicateCount = updated.filter((item) => item.status === "duplicate").length;

            if (failedCount > 0) {
                setStatus(createStatus("error", `Finished with ${failedCount} failed file(s).`));
            } else {
                setStatus(
                createStatus(
                    "success",
                    `Complete. ${readyCount} ready, ${duplicateCount} duplicate skipped.`
                )
                );
            }
            }

            return updated;
        });
    }

    function updateOverallProgress(doneCount: number, totalCount: number) {
        setOverallProgress(Math.round((doneCount / totalCount) * 100));
    }

    function getProgress(status: string): number {
        switch (status) {
            case "waiting":
            return 0;
            case "pending":
            return 10;
            case "uploading":
            return 20;
            case "uploaded":
            return 40;
            case "processing":
            return 70;
            case "ready":
            return 100;
            case "duplicate":
            return 100;
            case "failed":
            return 70;
            default:
            return 0;
        }
    }

    async function fetchUploadStatus(fileName: string, checksum: string) {
        const query = new URLSearchParams({
             file_name: fileName, 
             checksum ,
        });
        
        return authFetch<MediaUploadStatusResponse>(`/get_upload_status?${query.toString()}`, {
            method: "GET",
        });
    }

    async function pollUploadStatus(fileName: string, checksum: string) {
        let pollCount = 0;
        const maxPolls = 20; // Stop polling after 20 attempts (1 minute)

        const intervalId = window.setInterval(async () => {
            pollCount++;
            if (pollCount > maxPolls) {
                updateFileStatus(fileName, "failed");
                window.clearInterval(intervalId);
                return;
            }
            
            try {
                const data = await fetchUploadStatus(fileName, checksum);

                updateFileStatus(fileName, data.upload_status);

                if (data.upload_status === "ready" || data.upload_status === "failed") {
                    window.clearInterval(intervalId);
                }
                } catch (error) {
                    console.error(error);
                    updateFileStatus(fileName, "failed");
                    window.clearInterval(intervalId);
                }
            }, 3000);
        }

    async function handleUpload() {
        if (files.length === 0) return;

        setStatus(createStatus("loading", ""));

        try{
            let uploadedCount = 0;
            let duplicatedFiles: string[] = [];
            let finishedCount = 0;

            for (const file of files){
                updateFileStatus(file.name, "uploading");

                // call upload API for each file
                const hash = await calculateFileHash(file);
                const mediaType = getMediaType(file);
                const data = await authFetch<UploadResponse>("/get_signed_url", {
                    method: "POST",
                    body: JSON.stringify({
                        file_name: file.name,
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
                pollUploadStatus(file.name, hash);
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
                        <div className="media-status-track">
                            <div
                                className={`upload-progress-bar ${item.status}`}
                                style={{
                                    width: `${getProgress(item.status)}%`,
                                }}
                            />
                        </div>
                    </div>
                    ))}
                </div>
            )}
        </main>
    );
}

export default UploadScreen;