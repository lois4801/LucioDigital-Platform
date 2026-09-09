import axios, { type AxiosInstance } from "axios";

const BACKEND_URL: string = process.env.REACT_APP_BACKEND_URL as string;
export const API = `${BACKEND_URL}/api`;

const api: AxiosInstance = axios.create({
  baseURL: API,
  withCredentials: true,
});

export type ApiErrorDetail =
  | string
  | null
  | undefined
  | { msg?: string }
  | Array<{ msg?: string } | string>;

export function formatApiError(detail: ApiErrorDetail): string {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e === "object" && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default api;
