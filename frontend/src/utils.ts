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

export async function getMyPrivateMedia() {
  return authFetch<GetMediaResponse>("/get_private_media", {
    method: "GET",
  });
}

export async function getMyPublicMedia() {
  return authFetch<GetMediaResponse>("/get_private_media", {
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

export type QueryResult = {
  checksum: string;
  file_name: string;
  media_type?: string | null;
  url?: string | null;
  thumbnail_url?: string | null;
  tags?: Record<string, number>;
};

export type QueryResponse = {
  count: number;
  results: QueryResult[];
};

export type QueryThumbnailResponse = {
  checksum: string;
  file_name: string;
  url: string;
  thumbnail_url: string;
};