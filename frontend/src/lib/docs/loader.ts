/**
 * Loads the markdown under src/docs/ using Vite's glob imports.
 *
 * Everything is pulled into the bundle at build time (`eager: true`), so the
 * docs need no server and no runtime fetching — they ship with the app.
 */

import GithubSlugger from "github-slugger";

import type {
  DocsFrontmatter,
  DocsNavItem,
  DocsPage,
  DocsSection,
  DocsSectionMeta,
  DocsSearchResult,
  TocHeading,
} from "./types";

/**
 * Minimal YAML frontmatter parser.
 *
 * gray-matter would do this, but it depends on Buffer and does not run in the
 * browser. Only `key: value` pairs are needed here.
 */
function parseFrontmatter(raw: string): { data: Record<string, unknown>; content: string } {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) return { data: {}, content: raw };

  const data: Record<string, unknown> = {};
  for (const line of match[1].split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const colon = trimmed.indexOf(":");
    if (colon === -1) continue;

    const key = trimmed.slice(0, colon).trim();
    let value: string | number = trimmed.slice(colon + 1).trim();

    const quoted =
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"));
    if (quoted) value = value.slice(1, -1);
    else if (value !== "" && !Number.isNaN(Number(value))) value = Number(value);

    data[key] = value;
  }
  return { data, content: match[2] };
}

const markdownModules = import.meta.glob<string>("/src/docs/**/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
});

const metaModules = import.meta.glob<DocsSectionMeta>("/src/docs/**/_meta.json", {
  import: "default",
  eager: true,
});

/** "/src/docs/getting-started/overview.md" -> section and page slugs. */
function parseFilePath(filePath: string): { sectionSlug: string; pageSlug: string } | null {
  const match = filePath.match(/\/src\/docs\/([^/]+)\/([^/]+)\.md$/);
  if (!match) return null;
  return { sectionSlug: match[1], pageSlug: match[2] };
}

function getSectionMeta(sectionSlug: string): DocsSectionMeta {
  const meta = metaModules[`/src/docs/${sectionSlug}/_meta.json`];
  if (meta) return meta;

  // No _meta.json: title-case the slug and sort last.
  return {
    title: sectionSlug
      .split("-")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" "),
    order: 999,
  };
}

/**
 * Pull h2 and h3 headings out of markdown, skipping fenced code blocks.
 *
 * Ids come from github-slugger — the same library rehype-slug uses — rather
 * than a hand-written approximation. Reimplementing it drifts: "Sample — 176
 * rows" slugs to `sample--176-rows` (the em dash leaves two spaces, and
 * hyphens are not collapsed), and `column_index` keeps its underscore. Getting
 * either wrong produces table-of-contents links that scroll nowhere.
 *
 * A fresh slugger per call keeps its duplicate-suffix counter aligned with the
 * one rehype-slug uses while rendering the same page.
 */
export function extractHeadings(content: string): TocHeading[] {
  const headings: TocHeading[] = [];
  const slugger = new GithubSlugger();
  let inFence = false;

  for (const line of content.split("\n")) {
    if (line.trimStart().startsWith("```")) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;

    const match = line.match(/^(#{2,3}) (.+)$/);
    if (!match) continue;

    // Strip backticks and emphasis asterisks, but NOT underscores: rehype-slug
    // keeps them, so removing them here would produce anchors that do not
    // match the rendered heading ids (e.g. `column_index`).
    // Strip the markdown markers rehype-slug never sees, because it works on
    // rendered text.
    const text = match[2].replace(/[`*]/g, "").trim();
    headings.push({
      id: slugger.slug(text),
      text,
      level: match[1].length === 2 ? 2 : 3,
    });
  }
  return headings;
}

/** Parsed once at module load — the glob is static, so the result cannot change. */
const allPages: DocsPage[] = Object.entries(markdownModules)
  .flatMap(([filePath, rawContent]) => {
    const parsed = parseFilePath(filePath);
    if (!parsed) return [];

    const { sectionSlug, pageSlug } = parsed;
    const { data, content } = parseFrontmatter(rawContent);
    const frontmatter = data as Partial<DocsFrontmatter>;

    return [
      {
        id: `${sectionSlug}/${pageSlug}`,
        title: frontmatter.title || pageSlug.replace(/-/g, " "),
        description: frontmatter.description || "",
        sectionSlug,
        pageSlug,
        path: `/docs/${sectionSlug}/${pageSlug}`,
        content,
        order: frontmatter.order ?? 999,
        lastUpdated: frontmatter.lastUpdated,
      },
    ];
  });

const allSections: DocsSection[] = (() => {
  const bySlug = new Map<string, DocsSection>();

  for (const page of allPages) {
    if (!bySlug.has(page.sectionSlug)) {
      const meta = getSectionMeta(page.sectionSlug);
      bySlug.set(page.sectionSlug, { slug: page.sectionSlug, ...meta, pages: [] });
    }
    bySlug.get(page.sectionSlug)!.pages.push(page);
  }

  const sections = [...bySlug.values()];
  for (const section of sections) section.pages.sort((a, b) => a.order - b.order);
  sections.sort((a, b) => a.order - b.order);
  return sections;
})();

export function getAllSections(): DocsSection[] {
  return allSections;
}

export function getPage(sectionSlug: string, pageSlug: string): DocsPage | null {
  return allPages.find((p) => p.sectionSlug === sectionSlug && p.pageSlug === pageSlug) ?? null;
}

/** Every page in sidebar order. */
export function getAllPagesFlat(): DocsPage[] {
  return allSections.flatMap((s) => s.pages);
}

export function getFirstPage(): DocsPage | null {
  return getAllPagesFlat()[0] ?? null;
}

/** The previous/next links shown at the foot of a page. */
export function getNavigation(current: DocsPage): { prev: DocsNavItem | null; next: DocsNavItem | null } {
  const pages = getAllPagesFlat();
  const index = pages.findIndex((p) => p.id === current.id);

  const toNavItem = (page: DocsPage): DocsNavItem => ({
    title: page.title,
    path: page.path,
    sectionTitle: allSections.find((s) => s.slug === page.sectionSlug)?.title ?? page.sectionSlug,
  });

  return {
    prev: index > 0 ? toNavItem(pages[index - 1]) : null,
    next: index >= 0 && index < pages.length - 1 ? toNavItem(pages[index + 1]) : null,
  };
}

/** Strip markdown syntax so search matches words rather than punctuation. */
function toPlainText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`[^`]*`/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[#>*_|-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const searchIndex = allPages.map((page) => ({
  page,
  sectionTitle: allSections.find((s) => s.slug === page.sectionSlug)?.title ?? page.sectionSlug,
  headings: extractHeadings(page.content).map((h) => h.text.toLowerCase()),
  plain: toPlainText(page.content),
  plainLower: toPlainText(page.content).toLowerCase(),
}));

/**
 * Substring search over titles, headings and body text.
 *
 * Titles are weighted above headings, and headings above body text, so an
 * exact page name always sorts first.
 */
export function searchDocs(query: string, limit = 8): DocsSearchResult[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];

  const results: DocsSearchResult[] = [];

  for (const entry of searchIndex) {
    const title = entry.page.title.toLowerCase();
    let score = 0;

    if (title === q) score += 100;
    else if (title.startsWith(q)) score += 60;
    else if (title.includes(q)) score += 40;

    if (entry.page.description.toLowerCase().includes(q)) score += 15;
    score += entry.headings.filter((h) => h.includes(q)).length * 10;

    const bodyAt = entry.plainLower.indexOf(q);
    if (bodyAt !== -1) score += 5;

    if (score === 0) continue;

    // A window of surrounding text, so the hit has context in the dialog.
    const excerpt =
      bodyAt === -1
        ? entry.page.description
        : `${bodyAt > 0 ? "…" : ""}${entry.plain.slice(Math.max(0, bodyAt - 40), bodyAt + 90).trim()}…`;

    results.push({ page: entry.page, sectionTitle: entry.sectionTitle, score, excerpt });
  }

  return results.sort((a, b) => b.score - a.score).slice(0, limit);
}
