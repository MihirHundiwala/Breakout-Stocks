import { apiClient } from "../../../api/client";


export interface ReadinessResponse {
  status: "ready" | "not_ready";
  database: "ok" | "unavailable";
}

export async function getReadiness(): Promise<ReadinessResponse> {
  const response = await apiClient.get<ReadinessResponse>("/ready", {
    validateStatus: (status: number) => status === 200 || status === 503,
  });

  return response.data;
}
