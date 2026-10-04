import { useEffect, useState } from "react";
import type { HighlighterCore } from "shiki/core";

import { useDocumentTheme } from "../../lib/useDocumentTheme";

interface Props {
  code: string;
  language: string;
}

/**
 * Languages the documentation actually uses.
 *
 * shiki's `codeToHtml` resolves grammars dynamically, which makes a bundler
 * include every language it supports — that pulled in ~3 MB of chunks for
 * things like C++ and Emacs Lisp. Naming the languages keeps only these.
 */
const LANGUAGES = ["bash", "json", "yaml", "python", "typescript", "sql"] as const;
const THEMES = { dark: "github-dark-default", light: "github-light" } as const;

type SupportedLanguage = (typeof LANGUAGES)[number];

function isSupported(lang: string): lang is SupportedLanguage {
  return (LANGUAGES as readonly string[]).includes(lang);
}

let highlighterPromise: Promise<HighlighterCore> | null = null;

/**
 * Created once, on first use, and shared by every code block on the page.
 *
 * Built from `shiki/core` with each grammar imported by name. The convenience
 * `shiki` entry point resolves grammars dynamically, which makes the bundler
 * include all of them — that added ~3 MB of chunks for languages this project
 * never uses. The JavaScript regex engine is used rather than Oniguruma so no
 * WebAssembly is shipped either.
 */
function getHighlighter(): Promise<HighlighterCore> {
  highlighterPromise ??= Promise.all([
    import("shiki/core"),
    import("shiki/engine/javascript"),
    import("shiki/themes/github-dark-default.mjs"),
    import("shiki/themes/github-light.mjs"),
    import("shiki/langs/bash.mjs"),
    import("shiki/langs/json.mjs"),
    import("shiki/langs/yaml.mjs"),
    import("shiki/langs/python.mjs"),
    import("shiki/langs/typescript.mjs"),
    import("shiki/langs/sql.mjs"),
  ]).then(([core, engine, dark, light, ...langs]) =>
    core.createHighlighterCore({
      themes: [dark.default, light.default],
      langs: langs.map((m) => m.default),
      engine: engine.createJavaScriptRegexEngine(),
    }),
  );
  return highlighterPromise;
}

/**
 * Syntax-highlighted code with a copy button.
 *
 * Highlighting is asynchronous, so the plain code renders first and is
 * replaced once it resolves — no blank flash, and the text stays selectable
 * either way.
 */
export function CodeBlock({ code, language }: Props) {
  const [html, setHtml] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const theme = useDocumentTheme();

  useEffect(() => {
    if (!isSupported(language)) return; // unknown language: plain fallback

    let cancelled = false;
    getHighlighter()
      .then((highlighter) => {
        if (!cancelled) {
          setHtml(highlighter.codeToHtml(code, { lang: language, theme: THEMES[theme] }));
        }
      })
      .catch(() => {
        /* highlighting is decorative — the fallback below still renders */
      });
    return () => {
      cancelled = true;
    };
  }, [code, language, theme]);

  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1600);
    return () => clearTimeout(t);
  }, [copied]);

  const copy = () => {
    navigator.clipboard?.writeText(code).then(
      () => setCopied(true),
      () => {
        /* clipboard blocked (insecure context) — leave the button unchanged */
      },
    );
  };

  return (
    <div className="code-block">
      <div className="code-block-head">
        <span className="code-block-lang">{language || "text"}</span>
        <button type="button" className="code-block-copy" onClick={copy}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {html ? (
        <div className="code-block-body" dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <pre className="code-block-body code-block-plain">
          <code>{code}</code>
        </pre>
      )}
    </div>
  );
}
