export type RuntimeOverallState = "idle" | "queued" | "processing" | "degraded";
export type ServiceState = RuntimeOverallState | "checking" | "starting" | "stopping" | "stopped" | "unavailable";
export type RuntimeControlAction = "restart_api" | "restart_worker" | "restart_scheduler" | "stop_newsroom";

export type RuntimeComponentStatus = {
  status: "healthy" | "missing" | "stale" | "ambiguous" | "unmanaged" | string;
  detail: string;
  managed: boolean;
};

export type RuntimeStatus = {
  managed: boolean;
  overall: RuntimeOverallState;
  supervisor: RuntimeComponentStatus;
  components: Record<"api" | "worker" | "scheduler", RuntimeComponentStatus>;
  work: {
    state: "idle" | "queued" | "processing";
    queued_jobs: number;
    running_jobs: number;
  };
  controls: {
    available: boolean;
    actions: RuntimeControlAction[];
  };
  request_id: string;
};

export type RuntimeControlAck = {
  accepted: boolean;
  action: RuntimeControlAction;
  transition: "restarting" | "stopping";
  request_id: string;
};
