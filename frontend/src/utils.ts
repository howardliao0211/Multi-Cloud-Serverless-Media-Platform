import { getCurrentUser, fetchUserAttributes } from "aws-amplify/auth";
import { authFetch } from "./services/api";
import type { Dispatch, SetStateAction } from "react";

/**
 * Authentication helpers
 * 
 * @returns the Cognito ID of the currently authenticated user.
 */
export async function getCurrentUserId(): Promise<string> {
  const user = await getCurrentUser();

  if (!user.userId){
    throw new Error("User ID not found.");
  }
  return user.userId;
}

/**
 * Authentication helpers
 * 
 * @returns the Cognito Email of the currently authenticated user.
 */
export async function getCurrentUserEmail(): Promise<string> {
  const attributes = await fetchUserAttributes();

  const email = attributes.email;

  if (!email) {
    throw new Error("User email not found.");
  }

  return email;
}

/**
 * Masks an owner ID before displaying it in the UI.
 *
 * @param ownerId - The original owner ID.
 * @returns The first five characters followed by four asterisks.
 */
export function maskOwnerId(ownerId: string): string {
  if (!ownerId) {
    return "Unknown";
  }

  return `${ownerId.slice(0, 5)}****`;
}

/**
 * Converts an unknown caught value into a user-friendly error message.
 * 
 * @param error the value caught from a try/catch block.
 * @returns the original error message when the value is an Error; otherwise, a generic fallback message.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

/**
 * Shared values and actions provided by DashboardScreen through
 * React Router's Outlet context.
 *
 * Nested dashboard pages use this context to share selected media URLs,
 * prepare a thumbnail URL for search, and refresh the dashboard media list
 * after a successful update or deletion.
 */
export type DashboardOutletContext = {
    selectedUrls: string[]; //Permanent full-media URLs currently selected for bulk operations
    setSelectedUrls: Dispatch<SetStateAction<string[]>>; //Updates the shared list of selected full-media URLs.

    selectedUrl: string; //Permanent thumbnail URL prepared for thumbnail-based search.
    setSelectedUrl: Dispatch<SetStateAction<string>>; //Updates the shared thumbnail URL used by the search page.

    refreshMyMedia: () => Promise<void>; //Reloads the current user's media records in DashboardScreen.
};

/**
 * Media retrieval helpers.
 * 
 * @returns private media belonging to the current user.
 */
export async function getMyPrivateMedia() {
  return authFetch<GetMediaResponse>("/get_private_media", {
    method: "GET",
  });
}

/**
 * Media retrieval helpers.
 * 
 * @returns all publicly accessible media.
 * the caller can filter the returned records by owener ID when required. 
 */
export async function getMyPublicMedia() {
  return authFetch<GetMediaResponse>("/get_public_media", {
    method: "GET",
  });
}

/**
 * File validation and normalisation
 */
export const ALLOWED_MEDIA_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "video/mp4",
  "video/quicktime",
];

/**
 * Checks whether a file has one of the supported MIME types.
 * 
 * @param file the file that uploaded by the current user.
 * @returns true if the file is supported, otherwise false.
 */
export function isValidMediaFile(file: File): boolean {
  return ALLOWED_MEDIA_TYPES.includes(file.type);
}

/**
 * Normalises the file extemsion to lowercase.
 * 
 * @param file the original browser File object.
 * @returns the file name withe a lowercase extension.
 */
export function getNormalizedFileName(file: File): string {
  const parts = file.name.split(".");
  if (parts.length < 2) return file.name;

  const extension = parts.pop()?.toLowerCase();
  return `${parts.join(".")}.${extension}`;
}

/**
 * Separates a collection of files into valid and invalid media files.
 * 
 * @param files the files to validate.
 * @returns an object containing valid files and invalid files.
 */
export function validateMediaFiles(files: File[]): {
  validFiles: File[];
  invalidFiles: File[];
} {
  const validFiles = files.filter(isValidMediaFile);
  const invalidFiles = files.filter((file) => !isValidMediaFile(file));

  return { validFiles, invalidFiles };
}

/**
 * Status types
 */
export type StatusType = "idle" | "loading" | "success" | "error";

export type StatusMessage = {
  type: StatusType;
  text: string;
};

/**
 * Creates a consistent status object for UI feedback.
 * 
 * @param type 
 * @param text 
 * @returns 
 */
export function createStatus(type: StatusType, text: string): StatusMessage {
  return {type, text};
}

/**
 * Media types.
 */
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

/**
 * Bull tag editing.
 */
export type TagCount = Record<string, number>;

export type EditTagsRequest = {
  urls: string[];
  tags: TagCount[];
  // 1 adds tags and 0 removes tags.
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

/**
 * Bulk file deletion
 */
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

/**
 * Search responses
 */
export type QueryTagsResponse = GetMediaResponse;

export type QuerySpeciesResponse = GetMediaResponse;

export type QueryFileUploadUrlResponse = {
  upload_url: string;
  query_key: string;
  expires_in: number;
  upload_headers: Record<string, string>;
};

export type QueryFileResult = {
  owner_id: string;
  checksum: string;
  file_name: string;
  visibility: MediaVisibility;
  media_type: "image" | "video" | null;
  url?: string | null;
  thumbnail_url?: string | null;
  full_presigned_url?: string | null;
  thumbnail_presigned_url?: string | null;
  tags: Record<string, number>;
};

export type QueryFileResponse = {
  detected_tags: Record<string, number>;
  count: number;
  results: QueryFileResult[];
};

export type QueryFileJobStatus = "pending" | "processing" | "completed" | "failed";

export type QueryFileJobResponse = {
  job_id: string;
  status: QueryFileJobStatus;
};

export type QueryFileJobStatusResponse = QueryFileJobResponse & QueryFileResponse & {
  error_message?: string | null;
};

export type QueryThumbnailUrlResponse = {
  media_records: MediaRecordResponse[];
};

/**
 * SNS notification types
 */
export type SNSSubscribeRequest = {
  email: string;
  tags: string[];
}

export type SNSSubscribeResponse = {
  email: string;
  tags: string[];
  subscription_arn?: string | null;
  message: string;
}

export type SNSUnsubscribeRequest = {
  email: string;
}


export type SNSGetSubscriptionRequest = {
  email: string;
}

export type SubscriptionStatus =
  | "none"
  | "pending"
  | "deleted"
  | "confirmed"
  | "invalid";

export type SNSGetSubscriptionResponse = {
  email: string;
  tags: string[];
  state: SubscriptionStatus;
}
