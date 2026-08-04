import { apiClient } from "../../../api/client";

interface ConnectionResponse { available: boolean; connected: boolean; pending: boolean; username: string | null }
interface LinkResponse extends ConnectionResponse { bot_url: string | null; expires_at: string | null }

export interface TelegramConnection { available: boolean; connected: boolean; pending: boolean; username: string | null }
export interface TelegramLink extends TelegramConnection { botUrl: string | null; expiresAt: string | null }

const mapConnection = (value: ConnectionResponse): TelegramConnection => ({
  available: value.available,
  connected: value.connected,
  pending: value.pending,
  username: value.username,
});

export async function getTelegramConnection(): Promise<TelegramConnection> {
  const response = await apiClient.get<ConnectionResponse>("/telegram/connection");
  return mapConnection(response.data);
}

export async function connectTelegram(): Promise<TelegramLink> {
  const response = await apiClient.post<LinkResponse>("/telegram/connection");
  return {
    ...mapConnection(response.data),
    botUrl: response.data.bot_url,
    expiresAt: response.data.expires_at,
  };
}
