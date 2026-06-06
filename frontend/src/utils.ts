import { getCurrentUser } from "aws-amplify/auth";
import { authFetch } from "./services/api";

export async function getCurrentUserId(): Promise<string> {
  const user = await getCurrentUser();

  if (!user.userId){
    throw new Error("User ID not found.");
  }
  return user.userId;
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export type DashboardOutletContext = {
    selectedUrls: string[];
    setSelectedUrls: React.Dispatch<React.SetStateAction<string[]>>;

    selectedUrl: string;
    setSelectedUrl: React.Dispatch<React.SetStateAction<string>>;
};

export async function getMyPrivateMedia() {
  return authFetch<GetMediaResponse>("/get_private_media", {
    method: "GET",
  });
}

export async function getMyPublicMedia() {
  return authFetch<GetMediaResponse>("/get_public_media", {
    method: "GET",
  });
}

export const ALLOWED_MEDIA_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "video/mp4",
  "video/quicktime",
];

export function isValidMediaFile(file: File): boolean {
  return ALLOWED_MEDIA_TYPES.includes(file.type);
}

export function getNormalizedFileName(file: File): string {
  const parts = file.name.split(".");
  if (parts.length < 2) return file.name;

  const extension = parts.pop()?.toLowerCase();
  return `${parts.join(".")}.${extension}`;
}

export function validateMediaFiles(files: File[]): {
  validFiles: File[];
  invalidFiles: File[];
} {
  const validFiles = files.filter(isValidMediaFile);
  const invalidFiles = files.filter((file) => !isValidMediaFile(file));

  return { validFiles, invalidFiles };
}

export type StatusType = "idle" | "loading" | "success" | "error";

export type StatusMessage = {
  type: StatusType;
  text: string;
};

export function createStatus(type: StatusType, text: string): StatusMessage {
  return {type, text};
}

export type MediaVisibility = "private" | "public";

export type MediaRecordStatus =
  | "pending"
  | "uploaded"
  | "processing"
  | "ready"
  | "failed";

export type MediaRecordResponse = {
  owner_id: string;
  file_name: string;
  checksum: string;
  visibility: MediaVisibility;
  full_presigned_url?: string | null;
  thumbnail_presigned_url?: string | null;

  full_url?: string | null;
  thumbnail_url?: string | null;

  tags: Record<string, number>;
  upload_status: MediaRecordStatus;
  error_message?: string | null;
};

export type GetMediaResponse = {
  media_records: MediaRecordResponse[];
};

export async function calculateFileHash(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));

  return hashArray.map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function getMediaType(file: File): "image" | "video" {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";

  throw new Error("Unsupported file type.");
}

export type TagCount = Record<string, number>;

export type EditTagsRequest = {
  urls: string[];
  tags: TagCount[];
  operation_key: 0 | 1;
};

export type EditTagsResult = {
  url: string;
  updated: boolean;
  checksum?: string | null;
  file_name?: string | null;
  tags: Record<string, number>;
  message?: string | null;
};

export type EditTagsResponse = {
  updated_count: number;
  results: EditTagsResult[];
};

export async function editMediaTags(
  request: EditTagsRequest
): Promise<EditTagsResponse> {
  return authFetch<EditTagsResponse>("/edit_tags", {
    method: "PATCH",
    body: JSON.stringify(request),
  });
}

export type DeleteFileRequest = {
  urls: string[];
};

export type DeleteFileResult = {
  url: string;
  deleted: boolean;
  checksum?: string | null;
  file_name?: string | null;
  removed_db_entry: boolean;
  removed_full_object: boolean;
  removed_thumbnail_object: boolean;
  message?: string | null;
};

export type DeleteFileResponse = {
  deleted_count: number;
  results: DeleteFileResult[];
};

export type QueryTagsResponse = GetMediaResponse;

export type QuerySpeciesResponse = GetMediaResponse;

export type QueryFileResponse = {
  detected_tags: Record<string, number>;
  media_records: MediaRecordResponse[];
};

export type QueryThumbnailUrlResponse = {
  media_records: MediaRecordResponse[];
};

export type SNSSubscribeRequest = {
  email: string;
  tags: string[];
}

export type SNSSubscribeResponse = {
  email: string;
  tags: string[];
  subscription_arn?: string | null;
}

export type SNSUnsubscribeRequest = {
  email: string;
}
