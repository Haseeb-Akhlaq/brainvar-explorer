import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";
import rehypeRaw from "rehype-raw";
import { Link } from "react-router-dom";

import type { DocsNavItem, DocsPage } from "../../lib/docs/types";
import { CodeBlock } from "./CodeBlock";
import { MermaidDiagram } from "./MermaidDiagram";

interface Props {
  page: DocsPage;
  prev: DocsNavItem | null;
  next: DocsNavItem | null;
}

export function DocsContent({ page, prev, next }: Props) {
  return (
    <article className="docs-content">
      <header className="docs-content-head">
        <h1>{page.title}</h1>
        {page.description && <p className="docs-description">{page.description}</p>}
        {page.lastUpdated && (
          <p className="docs-updated">Last updated {page.lastUpdated}</p>
        )}
      </header>

      <div className="docs-prose">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          // rehype-slug adds heading ids the table of contents links to.
          // rehype-raw allows the occasional inline HTML in a page.
          rehypePlugins={[rehypeSlug, rehypeRaw]}
          components={{
            code({ className, children, ...props }) {
              const language = /language-(\w+)/.exec(className ?? "")?.[1];
              const text = String(children).replace(/\n$/, "");

              // Inline code has no language class and no newlines.
              if (!language && !text.includes("\n")) {
                return (
                  <code className="inline-code" {...props}>
                    {children}
                  </code>
                );
              }
              if (language === "mermaid") return <MermaidDiagram chart={text} />;
              return <CodeBlock code={text} language={language ?? "text"} />;
            },
            // react-markdown wraps code in <pre>; CodeBlock brings its own.
            pre({ children }) {
              return <>{children}</>;
            },
            table({ children }) {
              // Wide tables scroll rather than pushing the page sideways.
              return (
                <div className="table-scroll">
                  <table>{children}</table>
                </div>
              );
            },
            a({ href, children, ...props }) {
              const internal = href?.startsWith("/");
              if (internal) {
                return (
                  <Link to={href!} {...props}>
                    {children}
                  </Link>
                );
              }
              return (
                <a href={href} target="_blank" rel="noreferrer noopener" {...props}>
                  {children}
                </a>
              );
            },
          }}
        >
          {page.content}
        </ReactMarkdown>
      </div>

      {(prev || next) && (
        <nav className="docs-pager" aria-label="Documentation pages">
          {prev ? (
            <Link className="docs-pager-link is-prev" to={prev.path}>
              <span className="docs-pager-dir">Previous</span>
              <span className="docs-pager-title">{prev.title}</span>
              <span className="docs-pager-section">{prev.sectionTitle}</span>
            </Link>
          ) : (
            <span />
          )}
          {next && (
            <Link className="docs-pager-link is-next" to={next.path}>
              <span className="docs-pager-dir">Next</span>
              <span className="docs-pager-title">{next.title}</span>
              <span className="docs-pager-section">{next.sectionTitle}</span>
            </Link>
          )}
        </nav>
      )}
    </article>
  );
}
