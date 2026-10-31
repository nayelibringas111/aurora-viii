export type Family = "feedforward" | "rnn" | "cnn" | "gan";
export type JobStatus = "QUEUED" | "PREPARING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
export type Role = "lead" | "engineer" | "reviewer" | "reader";
export type Permission =
  | "view" | "edit_project" | "manage_members" | "design" | "train"
  | "review_model" | "retire_model" | "download_model" | "export" | "view_audit";

export interface Me { id: string; email: string; display_name: string; is_admin: boolean; status: string }

export interface Project {
  id: string; name: string; description: string; problem: string; tags: string[]; status: "active" | "archived";
  owner: { id: string; display_name: string }; created_at: string; updated_at: string;
  my_role: Role | null; my_role_label: string; my_permissions: Permission[];
  counts: { architectures: number; jobs: number; models: number; members: number };
}

export interface Member { user_id: string; email: string; display_name: string; role: Role; role_label: string; added_at: string; is_owner: boolean }

export interface LayerSpec {
  type: string; units?: number; activation?: string; rate?: number; filters?: number; kernel?: number;
  padding?: "same" | "valid"; pool?: number; return_sequences?: boolean;
}
export interface ClassifierConfig { input_shape: number[]; layers: LayerSpec[]; output: { units: number; activation: string } }
export interface GanConfig { data_dim: number; latent_dim: number; generator: LayerSpec[]; discriminator: LayerSpec[] }
export type ArchConfig = ClassifierConfig | GanConfig;

export interface LayerSummary { name: string; type: string; output_shape: number[]; params: number; units?: number; filters?: number; activation?: string }
export interface ArchSummary { total_params: number; input_shape: number[]; layers: LayerSummary[]; loss: string; generator?: LayerSummary[]; discriminator?: LayerSummary[] }
export interface Architecture {
  id: string; project_id: string; name: string; family: Family; justification: string; config: ArchConfig;
  summary: ArchSummary; version: number; config_hash: string; created_at: string;
}
export interface Issue { path: string; message: string }

export interface Dataset {
  id: string; project_id: string | null; name: string; version: number; kind: "builtin" | "upload"; family_hint: Family;
  status: string; task: "classification" | "generation"; input_shape: number[]; num_classes: number; samples: number;
  class_names?: string[]; feature_names?: string[]; description?: string; split: Record<string, number>;
  size_bytes?: number; sha256?: string; created_at: string;
}

export interface TrainingParams { epochs: number; batch_size: number; optimizer: "adam" | "sgd" | "rmsprop"; learning_rate: number; seed: number | null; observe: boolean }

export interface Job {
  id: string; project_id: string; architecture_id: string; dataset_id: string; status: JobStatus; status_label: string;
  progress: number; current_epoch: number; total_epochs: number; params: TrainingParams; attempt: number;
  cancel_requested: boolean; cancel_reason: string | null; error_message: string | null;
  result: {
    evaluation?: Record<string, number>; confusion_matrix?: number[][]; per_class_accuracy?: (number | null)[];
    class_names?: string[]; observations?: string[]; model_version?: number; checksum?: string;
    notes?: { author: string; text: string; at: string }[];
  };
  trace: Record<string, unknown>; created_at: string; started_at: string | null; ended_at: string | null; duration_seconds: number | null;
  architecture_name?: string; family?: Family; dataset_name?: string; project_name?: string; architecture_version?: number;
}

export interface VisLayer { name: string; kind: "input" | "dense" | "conv" | "recurrent" | "output"; size: number; shown: number[]; activation?: string | null; ops_before?: string[]; params?: number }
export interface Topology {
  family: Family; groups: { name: string; layers: VisLayer[] }[]; class_names?: string[]; total_params: number;
  has_boundary: boolean; points?: number[][] | null; real_points?: number[][]; input_shape?: number[];
}
export interface Snapshot {
  phase: "batch" | "epoch"; epoch: number;
  groups: { acts: number[][]; weights: number[][][] }[];
  sample: {
    kind: "image" | "series" | "vector" | "gan"; pixels?: number[][]; values?: number[]; true?: number; probs?: number[]; pred?: number;
    generated?: number[]; d_fake?: number;
  };
  boundary?: { n: number; x: [number, number]; y: [number, number]; cls: number[]; conf: number[] };
  generated_points?: number[][];
}
export interface JobDetail extends Job {
  architecture: { id: string; name: string; family: Family; version: number; summary: ArchSummary; config: ArchConfig };
  dataset: { id: string; name: string; version: number; class_names?: string[] };
  topology: Topology | null; snapshot: Snapshot | null; last_event_id: number;
}
export interface EpochMetrics { epoch: number; [k: string]: number }

export interface ModelVersion {
  id: string; project_id: string; job_id: string; version: number; status: "draft" | "reviewed" | "approved" | "retired";
  status_label: string; checksum: string; size_bytes: number; metrics: Record<string, number>; notes: string; created_at: string;
  architecture: { name: string; family: Family; version: number } | null; params: TrainingParams | null; trace: Record<string, unknown> | null;
}

export interface AuditEvent { id: number; action: string; actor: string | null; project?: string | null; metadata: Record<string, unknown>; created_at: string }

export interface FamilyInfo { id: Family; name: string; status: string; summary: string; use_cases: string[]; restrictions: string[]; template: ArchConfig; suggested_dataset: string }
