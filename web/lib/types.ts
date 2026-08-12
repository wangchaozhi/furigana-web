export type Segment = {
  text: string;
  ruby?: string | null;
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

export type OverrideItem = {
  id: number;
  surface: string;
  reading: string;
  context: string;
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
  lines: AnnotatedLine[];
};
