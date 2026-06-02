import { getCurrentUser } from "aws-amplify/auth";

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
  full_presigned_url: string;
  thumbnail_presigned_url: string;
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