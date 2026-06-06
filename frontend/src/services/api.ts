import { fetchAuthSession } from "aws-amplify/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL;

export async function authFetch<TResponse>( path: string, 
        options: RequestInit = {},
        getFullError = false ): Promise<TResponse> {
    const session = await fetchAuthSession();
    const token = session.tokens?.idToken?.toString();

    if (!token){
        throw new Error("No JWT token found.");
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {...options,
        headers: {
            Authorization: `Bearer ${token}`, "Content-Type": "application/json",
            ...options.headers,
        },
    });

    if (!response.ok) {
        let errorMessage = `API request failed: ${response.status}`;

        if (getFullError) {
            try {
                const errorBody = await response.json();

                if (
                    errorBody &&
                    typeof errorBody === "object" &&
                    "message" in errorBody &&
                    typeof errorBody.message === "string"
                ) {
                    errorMessage = errorBody.message;
                }
            } catch {
                // Keep the default error message if the response body is not valid JSON.
            }
        }

        throw new Error(errorMessage);
    }

    return response.json() as Promise<TResponse>;
}