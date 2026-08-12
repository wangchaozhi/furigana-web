export type Segment = {
  text: string;
  ruby?: string | null;
  candidates?: string[];
  confidence?: "high" | "medium" | "low" | null;
};

export type AnnotatedLine = {
  source: string;
  segments: Segment[];
};

export type DocumentMeta = {
  title: string;
  artist: string;
  year: string;
};

export type LayoutSettings = {
  font_size: number;
  line_spacing: number;
  ruby_scale: number;
  page_margin: number;
  font_family: "gothic" | "mincho" | "system";
  vertical: boolean;
};

export type OverrideItem = {
  id: number;
  surface: string;
  reading: string;
  context: string;
  scope: "sentence" | "project" | "global";
  project_id?: number | null;
  created_at: string;
};

export type ProjectSummary = {
  id: number;
  title: string;
  artist: string;
  year: string;
  created_at: string;
  updated_at: string;
};

export type ProjectItem = ProjectSummary & {
  source_text: string;
  layout: LayoutSettings;
  lines: AnnotatedLine[];
};
