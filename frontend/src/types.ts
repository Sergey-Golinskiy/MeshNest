export type UserRole = "admin" | "contributor" | "viewer";

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface ModelCard {
  id: string;
  slug: string;
  title: string;
  category_path: string | null;
  tags: string[];
  preview_url: string | null;
  has_stl: boolean;
  has_step: boolean;
  has_3mf: boolean;
  has_images: boolean;
  has_video: boolean;
  is_flexi: boolean;
  is_print_in_place: boolean;
  is_multipart: boolean;
  is_reviewed: boolean;
  status: string;
  file_count: number;
}

export interface ModelDetail extends ModelCard {
  original_title: string | null;
  description: string | null;
  category_id: string | null;
  category_confidence: number | null;
  is_assembly: boolean;
  preview_status: string;
  viewer_status: string;
  source_type: string | null;
  source_name: string | null;
  source_hash: string | null;
  stl_count: number;
  step_count: number;
  three_mf_count: number;
  image_count: number;
  video_count: number;
  document_count: number;
  created_at: string;
  updated_at: string;
  imported_at: string | null;
}

export interface FileItem {
  id: string;
  file_name: string;
  extension: string | null;
  file_type: string;
  role: string;
  size_bytes: number;
  sha256: string | null;
  is_primary: boolean;
  download_url: string;
}

export interface CategoryNode {
  id: string;
  slug: string;
  name: string;
  path: string;
  sort_order: number;
  model_count: number;
  children: CategoryNode[];
}

export interface TagOut {
  id: string;
  slug: string;
  name: string;
  type: string;
  model_count: number;
}

export interface ImportJob {
  id: string;
  status: string;
  progress_pct: number;
  source_type: string | null;
  source_name: string | null;
  models_created: number;
  files_processed: number;
  warnings_count: number;
  errors_count: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModelListResponse {
  items: ModelCard[];
  total: number;
  page: number;
  page_size: number;
}

export interface InviteOut {
  id: string;
  token: string;
  role: UserRole;
  email_hint: string | null;
  expires_at: string;
  used_at: string | null;
  created_at: string;
  invite_url: string;
}
