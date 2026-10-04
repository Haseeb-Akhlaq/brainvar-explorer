/** Documentation system types. */

/** Frontmatter parsed from the top of a markdown file. */
export interface DocsFrontmatter {
  title: string;
  description: string;
  order?: number;
  lastUpdated?: string;
}

/** Section metadata, from the section's _meta.json. */
export interface DocsSectionMeta {
  title: string;
  order: number;
  /** A lucide-react icon name, e.g. "BookOpen". */
  icon?: string;
  description?: string;
}

/** One documentation page. */
export interface DocsPage {
  /** "section/page" */
  id: string;
  title: string;
  description: string;
  sectionSlug: string;
  pageSlug: string;
  /** "/docs/section/page" */
  path: string;
  /** Markdown body, frontmatter stripped. */
  content: string;
  order: number;
  lastUpdated?: string;
}

/** A section and the pages inside it. */
export interface DocsSection {
  slug: string;
  title: string;
  order: number;
  icon?: string;
  description?: string;
  pages: DocsPage[];
}

/** A heading in the table of contents. */
export interface TocHeading {
  /** Anchor id, matching what rehype-slug generates. */
  id: string;
  text: string;
  level: 2 | 3;
}

/** Previous/next link at the foot of a page. */
export interface DocsNavItem {
  title: string;
  path: string;
  sectionTitle: string;
}

/** A search hit. */
export interface DocsSearchResult {
  page: DocsPage;
  sectionTitle: string;
  /** Higher is a better match. */
  score: number;
  /** Surrounding text with the query in context. */
  excerpt: string;
}
