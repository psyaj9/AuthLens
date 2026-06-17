export type DocumentStatus = "queued" | "uploaded" | "error";

export type DocumentItem = {
  id: string;
  name: string;
  size: number;
  status: DocumentStatus;
};

export type AsyncStatus = "idle" | "loading" | "success" | "error";

export type HealthStatus = {
  ok: boolean;
  backendConfigured: boolean;
  backendReachable: boolean;
  error?: string;
};
