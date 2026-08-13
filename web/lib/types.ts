export type Segment = {
  text: string;
  ruby?: string | null;
  candidates?: string[];
  confidence?: "high" | "medium" | "low" | null;
};

export type AnnotatedLine = {
  source: string;
  segments: Segment[];
  translation?: string;
};

export type TranslationLanguage = "none" | "zh" | "en";
export type TranslationProvider = "azure" | "libretranslate" | "baidu" | "youdao" | "google" | "deepl" | "openai";
export type TranslationProviderStatus = { id: TranslationProvider; label: string; configured: boolean };

export type LyricsSearchResult = {
  id: number;
  track_name: string;
  artist_name: string;
  album_name: string;
  duration: number;
  plain_lyrics: string;
  has_synced_lyrics: boolean;
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
  columns: 1 | 2;
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
  translation_language: TranslationLanguage;
  lines: AnnotatedLine[];
};
