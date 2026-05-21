import { fetchAuthSession } from "aws-amplify/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL;

export async function authFetch<TResponse>( path: string, 
        options: RequestInit = {}, ): Promise<TResponse> {
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

    if (!response.ok){
        throw new Error(`API request failed: ${response.status}`);
    }

    return response.json() as Promise<TResponse>;
}