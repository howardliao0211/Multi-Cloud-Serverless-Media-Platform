import { useRef, useState } from "react";
import { calculateFileHash, createStatus, getMediaType, getCurrentUserId, type StatusMessage, validateMediaFiles, getErrorMessage } from "../utils";
import { authFetch } from "../services/api";

/**
 * Response returned by the presigned upload URL endpoint.
 */
type UploadResponse = {
    duplicate: boolean;
    upload_url?: string;
    expires_in?: number;
};

/**
 * Status values used by the frontend to represent each upload.
 */
type FileUploadStatus = "waiting"
    | "uploading"
    | "pending"
    | "uploaded"
    | "processing"
    | "ready"
    | "failed"
    | "duplicate";

/**
 * Represents the current upload state of one selected file.
 */
type FileUploadItem = {
    name: string;
    status: FileUploadStatus;
};

/**
 * Processing status returned by the backend.
 */
type MediaUploadStatus = "pending" | "uploaded" | "processing" | "ready" | "failed";

/**
* Response returned by the upload-status endpoint.
*/
type MediaUploadStatusResponse = {
    upload_status: MediaUploadStatus;
    error_message?: string | null;
};

const STATUS_PROGRESS: Record<FileUploadStatus, number> = {
    waiting: 0,
    pending: 10,
    uploading: 20,
    uploaded: 40,
    processing: 70,
    ready: 100,
    failed: 100,
    duplicate: 100,
};

/**
 * Provides a multi-file media upload interface.
 *
 * The screen validates selected files, obtains presigned S3 upload URLs,
 * uploads files directly to S3, and polls the backend until processing is
 * completed. It also displays individual and overall upload progress.
 *
 * @returns the media upload interface.
 */
function UploadScreen() {
    const [files, setFiles] = useState<File[]>([]);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const [status, setStatus] = useState<StatusMessage>(createStatus("idle", ""));
    const [visibility, setVisibility] = useState<"private" | "public">("private");
    const [fileStatuses, setFileStatuses] = useState<FileUploadItem[]>([]);
    const [overallProgress, setOverallProgress] = useState<number>(0);

    /**
     * Validates selected files and prepares their initial upload states.
     *
     * If any unsupported file is included, the entire current selection is
     * cleared and an error message is displayed.
     *
     * @param selectedFiles files selected by the user.
     */
    function handleSelectedFiles(selectedFiles: File[]) {
        const { validFiles, invalidFiles } = validateMediaFiles(selectedFiles);

        if (invalidFiles.length > 0) {
            setFiles([]);
            setFileStatuses([]);
            setOverallProgress(0);
            setStatus(
                createStatus(
                    "error",
                    `Unsupported file type: ${invalidFiles.map((file) => file.name).join(", ")}. Please upload JPG, PNG, WEBP, MP4, or MOV files.`
                )
            );
            return;
        }

        setStatus(createStatus("idle", ""));
        setFiles(validFiles);
        setFileStatuses(validFiles.map((file) => ({ name: file.name, status: "waiting" })));
        setOverallProgress(0);
    }

    /**
     * Handles files dropped onto the upload area.
     *
     * @param event the drag-and-drop event containing the files.
     */
    function handleDrop(
        event: React.DragEvent<HTMLLabelElement>
    ): void {
        event.preventDefault();

        if (event.dataTransfer.files) {
            handleSelectedFiles(
                Array.from(event.dataTransfer.files)
            );
        }
    }

    /**
     * Handles files selected through the browser file picker.
     *
     * @param event the file input change event.
     */
    function handleFileChange(
        event: React.ChangeEvent<HTMLInputElement>
    ): void {
        if (event.target.files) {
            handleSelectedFiles(
                Array.from(event.target.files)
            );
        }
    }

    /**
 * Updates one file's status and recalculates overall progress.
 *
 * When every file reaches a final state, a completion summary is displayed.
 *
 * @param fileName - Name of the file being updated.
 * @param nextStatus - New upload or processing status.
 */
    function updateFileStatus(
        fileName: string,
        nextStatus: FileUploadStatus
    ): void {
        setFileStatuses((currentStatuses) => {
            const updatedStatuses = currentStatuses.map((item) => {
                if (item.name !== fileName) {
                    return item;
                }

                const currentProgress =
                    STATUS_PROGRESS[item.status];

                const nextProgress =
                    STATUS_PROGRESS[nextStatus];

                // Prevent an upload from moving back to an earlier stage.
                if (nextProgress < currentProgress) {
                    return item;
                }

                return {
                    ...item,
                    status: nextStatus,
                };
            });

            const totalProgress = updatedStatuses.reduce(
                (sum, item) =>
                    sum + STATUS_PROGRESS[item.status],
                0
            );

            const averageProgress =
                updatedStatuses.length > 0
                    ? Math.round(
                        totalProgress /
                        updatedStatuses.length
                    )
                    : 0;

            // Prevent the overall progress bar from moving backwards.
            setOverallProgress((previousProgress) =>
                Math.max(previousProgress, averageProgress)
            );

            const finishedCount = updatedStatuses.filter(
                (item) =>
                    item.status === "ready" ||
                    item.status === "failed" ||
                    item.status === "duplicate"
            ).length;

            if (
                updatedStatuses.length > 0 &&
                finishedCount === updatedStatuses.length
            ) {
                const readyCount = updatedStatuses.filter(
                    (item) => item.status === "ready"
                ).length;

                const failedCount = updatedStatuses.filter(
                    (item) => item.status === "failed"
                ).length;

                const duplicateCount = updatedStatuses.filter(
                    (item) => item.status === "duplicate"
                ).length;

                if (failedCount > 0) {
                    setStatus(
                        createStatus(
                            "error",
                            `Finished with ${failedCount} failed file(s).`
                        )
                    );
                } else {
                    setStatus(
                        createStatus(
                            "success",
                            `Complete. ${readyCount} ready, ${duplicateCount} duplicate skipped.`
                        )
                    );
                }
            }

            return updatedStatuses;
        });
    }

    /**
     * Converts an upload status into a visual progress percentage.
     *
     * @param currentStatus - Current frontend upload status.
     * @returns The progress percentage for the status.
     */
    function getProgress(
        currentStatus: FileUploadStatus
    ): number {
        return STATUS_PROGRESS[currentStatus];
    }

    /**
     * Retrieves the backend processing status for one uploaded file.
     *
     * @param fileName - Original file name.
     * @param checksum - SHA-256 checksum of the file.
     * @returns The current backend processing status.
     */
    async function fetchUploadStatus(
        fileName: string,
        checksum: string
    ): Promise<MediaUploadStatusResponse> {
        const query = new URLSearchParams({
            file_name: fileName,
            checksum,
        });

        return authFetch<MediaUploadStatusResponse>(
            `/get_upload_status?${query.toString()}`,
            {
                method: "GET",
            }
        );
    }

    /**
     * Polls the backend until processing succeeds, fails, or times out.
     *
     * Polling stops after 20 attempts to prevent an infinite request loop.
     * A timeout does not automatically mark the backend processing as failed.
     *
     * @param fileName - Original file name.
     * @param checksum - SHA-256 checksum of the file.
     */
    async function pollUploadStatus(
        fileName: string,
        checksum: string
    ): Promise<void> {
        let pollCount = 0;
        const maxPolls = 20;

        const intervalId = window.setInterval(
            async () => {
                pollCount++;

                if (pollCount > maxPolls) {
                    window.clearInterval(intervalId);

                    updateFileStatus(fileName, "failed");
                    
                    setStatus(
                        createStatus(
                            "error",
                            `${fileName} is still processing. Please refresh later.`
                        )
                    );

                    return;
                }

                try {
                    const data =
                        await fetchUploadStatus(
                            fileName,
                            checksum
                        );

                    updateFileStatus(
                        fileName,
                        data.upload_status
                    );

                    if (
                        data.upload_status === "ready" ||
                        data.upload_status === "failed"
                    ) {
                        window.clearInterval(
                            intervalId
                        );
                    }
                } catch (error) {
                    console.error(error);
                    window.clearInterval(intervalId);

                    setStatus(
                        createStatus(
                            "error",
                            getErrorMessage(error)
                        )
                    );
                }
            },
            3000
        );
    }

    /**
     * Uploads all selected files sequentially.
     *
     * For each file, the function:
     * 1. Calculates its SHA-256 checksum.
     * 2. Requests a presigned S3 upload URL.
     * 3. Skips duplicate files.
     * 4. Uploads the file directly to S3.
     * 5. Polls the backend processing status.
     */
    async function handleUpload(): Promise<void> {
        if (files.length === 0) {
            return;
        }

        setStatus(
            createStatus(
                "loading",
                "Uploading files..."
            )
        );

        try {
            for (const file of files) {
                updateFileStatus(file.name, "pending");

                const userId = await getCurrentUserId();
                const checksum = await calculateFileHash(file);
                const mediaType = getMediaType(file);

                const data = await authFetch<UploadResponse>(
                    "/get_signed_url",
                    {
                        method: "POST",
                        body: JSON.stringify({
                            file_name: file.name,
                            checksum,
                            media_type: mediaType,
                            visibility,
                        }),
                    }
                );
                if (data.duplicate) {
                    updateFileStatus(
                        file.name,
                        "duplicate"
                    );
                    continue;
                }

                if (!data.upload_url) {
                    updateFileStatus(
                        file.name,
                        "failed"
                    );

                    throw new Error(
                        "Upload URL was not returned."
                    );
                }

                updateFileStatus(file.name, "uploading");

                const uploadResponse =
                    await fetch(data.upload_url, {
                        method: "PUT",
                        headers: {
                            "x-amz-meta-file_name":
                                file.name,
                            "x-amz-meta-checksum":
                                checksum,
                            "x-amz-meta-owner_id":
                                userId,
                        },
                        body: file,
                    });

                if (!uploadResponse.ok) {
                    updateFileStatus(
                        file.name,
                        "failed"
                    );

                    throw new Error(
                        `S3 upload failed: ${uploadResponse.status}`
                    );
                }

                updateFileStatus(
                    file.name,
                    "uploaded"
                );

                void pollUploadStatus(
                    file.name,
                    checksum
                );
            }
        } catch (error) {
            setStatus(
                createStatus(
                    "error",
                    getErrorMessage(error)
                )
            );
        }
    }

    return (
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
                <button type="button"
                    onClick={handleUpload}
                    disabled={files.length === 0 || status.type === "loading"}
                >
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