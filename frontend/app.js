(function () {
    "use strict";

    const editor = document.getElementById("editor");
    const preview = document.getElementById("preview");
    const themeSelect = document.getElementById("theme");
    const titleInput = document.getElementById("title");
    const tocCheckbox = document.getElementById("toc");
    const hifiCheckbox = document.getElementById("hifi");
    const uploadInput = document.getElementById("upload");
    const downloadButton = document.getElementById("download");
    const statusEl = document.getElementById("status");
    const customCssPanel = document.getElementById("custom-css-panel");
    const customCssEditor = document.getElementById("custom-css-editor");
    const cssHelpBtn = document.getElementById("css-help-btn");
    const cssExpandBtn = document.getElementById("css-expand-btn");
    const cssMaximizeBtn = document.getElementById("css-maximize-btn");
    const cssHelpDialog = document.getElementById("css-help-dialog");
    const cssHelpClose = document.getElementById("css-help-close");

    const STORAGE_KEY = "md2pdf:last";
    const CUSTOM_CSS_KEY = "md2pdf:custom-css";
    const DEFAULT_MARKDOWN = [
        "# Welcome to md2pdf",
        "",
        "Write Markdown on the left; preview updates live on the right.",
        "",
        "## Features",
        "",
        "- GitHub-flavored tables, lists and task lists",
        "- [x] Syntax-highlighted code blocks",
        "- Math with KaTeX, inline $E=mc^2$ or display:",
        "",
        "$$",
        "\\int_0^\\infty e^{-x^2}\\,dx = \\frac{\\sqrt{\\pi}}{2}",
        "$$",
        "",
        "- Mermaid diagrams:",
        "",
        "```mermaid",
        "graph LR",
        "  A[Markdown] --> B{Renderer}",
        "  B -->|simple| C[WeasyPrint]",
        "  B -->|math/mermaid| D[Chromium]",
        "```",
        "",
        "- Emoji support: check, rocket, sparkles (native Unicode)",
        "",
        "Enjoy!",
    ].join("\n");

    marked.setOptions({
        gfm: true,
        breaks: false,
        headerIds: true,
        mangle: false,
        highlight: function (code, lang) {
            if (lang === "mermaid") return code;
            try {
                if (lang && hljs.getLanguage(lang)) {
                    return hljs.highlight(code, { language: lang }).value;
                }
                return hljs.highlightAuto(code).value;
            } catch (_e) {
                return code;
            }
        },
    });

    // Preserve fenced mermaid blocks as <pre class="mermaid"> so we can run
    // mermaid on them after rendering.
    const renderer = new marked.Renderer();
    const originalCode = renderer.code.bind(renderer);
    renderer.code = function (code, infostring) {
        if ((infostring || "").trim().toLowerCase() === "mermaid") {
            return '<pre class="mermaid">' + escapeHtml(code) + "</pre>";
        }
        return originalCode(code, infostring);
    };
    marked.use({ renderer });

    function escapeHtml(s) {
        return s.replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    function showStatus(message, isError) {
        statusEl.textContent = message;
        statusEl.hidden = false;
        statusEl.classList.toggle("error", Boolean(isError));
        clearTimeout(showStatus._t);
        showStatus._t = setTimeout(function () { statusEl.hidden = true; }, 3500);
    }

    let mermaidCounter = 0;
    let renderToken = 0;

    async function updatePreview() {
        const token = ++renderToken;
        const md = editor.value;
        localStorage.setItem(STORAGE_KEY, md);
        const rawHtml = marked.parse(md);
        const clean = DOMPurify.sanitize(rawHtml, { ADD_TAGS: ["pre"], ADD_ATTR: ["class"] });
        if (token !== renderToken) return;
        preview.innerHTML = clean;

        try {
            if (window.renderMathInElement) {
                renderMathInElement(preview, {
                    delimiters: [
                        { left: "$$", right: "$$", display: true },
                        { left: "$", right: "$", display: false },
                    ],
                    throwOnError: false,
                });
            }
        } catch (_e) { /* ignore math errors in preview */ }

        const mermaidBlocks = preview.querySelectorAll("pre.mermaid");
        if (mermaidBlocks.length && window.mermaid) {
            for (const block of mermaidBlocks) {
                const code = block.textContent;
                const id = "mmd-" + (++mermaidCounter);
                try {
                    const { svg } = await window.mermaid.render(id, code);
                    if (token !== renderToken) return;
                    const container = document.createElement("div");
                    container.className = "mermaid";
                    container.innerHTML = svg;
                    block.replaceWith(container);
                } catch (err) {
                    const pre = document.createElement("pre");
                    pre.textContent = "Mermaid error: " + (err && err.message ? err.message : err);
                    block.replaceWith(pre);
                }
            }
        }
    }

    async function applyTheme(slug) {
        if (slug === "custom") {
            customCssPanel.classList.add("is-open");
            const css = customCssEditor.value;
            applyPreviewCss(css ? scopeCustomCss(css) : "");
            return;
        }
        customCssPanel.classList.remove("is-open");
        try {
            const res = await fetch("/api/themes/" + encodeURIComponent(slug) + "/css");
            if (!res.ok) return;
            applyPreviewCss(await res.text());
        } catch (_e) { /* preview still works without theme CSS */ }
    }

    function applyPreviewCss(css) {
        let style = document.getElementById("preview-theme");
        if (!style) {
            style = document.createElement("style");
            style.id = "preview-theme";
            document.head.appendChild(style);
        }
        style.textContent = css;
    }

    function scopeCustomCss(css) {
        // Minimal client-side scoping: prefix each selector block with #preview.
        // Strips @page rules and wraps the rest so it only affects the preview pane.
        const stripped = css.replace(/@page\s*\{[^}]*\}/g, "");
        return stripped.replace(/([^{}@][^{}]*)\{([^{}]*)\}/g, function (_, sel, decl) {
            const scoped = sel.split(",").map(function (s) {
                s = s.trim();
                if (!s) return "";
                s = s.replace(/^(html\s*,?\s*)?(body)\b/, "#preview");
                if (!s.startsWith("#preview")) s = "#preview " + s;
                return s;
            }).filter(Boolean).join(", ");
            return scoped ? scoped + " {" + decl + "}" : "";
        });
    }

    async function loadThemes() {
        try {
            const res = await fetch("/api/themes");
            const themes = await res.json();
            themeSelect.innerHTML = "";
            themes.forEach(function (t) {
                const opt = document.createElement("option");
                opt.value = t.slug;
                opt.textContent = t.name;
                opt.title = t.description;
                themeSelect.appendChild(opt);
            });
        } catch (_e) {
            showStatus("Failed to load themes", true);
        }
    }

    async function downloadPdf() {
        const body = {
            markdown: editor.value,
            theme: themeSelect.value,
            title: titleInput.value || "document",
            include_toc: tocCheckbox.checked,
            force_high_fidelity: hifiCheckbox.checked,
            custom_css: themeSelect.value === "custom" ? customCssEditor.value : "",
        };
        downloadButton.disabled = true;
        showStatus("Rendering...");
        try {
            const res = await fetch("/api/render", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const text = await res.text();
                throw new Error(text || ("HTTP " + res.status));
            }
            const blob = await res.blob();
            const engine = res.headers.get("X-Render-Engine") || "";
            triggerDownload(blob, (body.title || "document") + ".pdf");
            showStatus("Done" + (engine ? " (" + engine + ")" : ""));
        } catch (err) {
            showStatus("Error: " + err.message, true);
        } finally {
            downloadButton.disabled = false;
        }
    }

    function triggerDownload(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    async function handleUpload(file) {
        try {
            const text = await file.text();
            editor.value = text;
            if (!titleInput.value || titleInput.value === "document") {
                titleInput.value = file.name.replace(/\.(md|markdown|txt)$/i, "") || "document";
            }
            updatePreview();
            showStatus("Loaded " + file.name);
        } catch (err) {
            showStatus("Failed to read file", true);
        }
    }

    function debounce(fn, wait) {
        let t;
        return function () {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, arguments), wait);
        };
    }

    // Wire up
    editor.addEventListener("input", debounce(updatePreview, 180));
    downloadButton.addEventListener("click", downloadPdf);
    uploadInput.addEventListener("change", function () {
        const f = uploadInput.files && uploadInput.files[0];
        if (f) handleUpload(f);
        uploadInput.value = "";
    });
    themeSelect.addEventListener("change", function () { applyTheme(themeSelect.value); });

    // Help dialog — open / close
    cssHelpBtn.addEventListener("click", function () { cssHelpDialog.showModal(); });
    cssHelpClose.addEventListener("click", function () { cssHelpDialog.close(); });
    cssHelpDialog.addEventListener("click", function (e) {
        if (e.target === cssHelpDialog) cssHelpDialog.close();
    });

    if (cssExpandBtn) {
        cssExpandBtn.addEventListener("click", function () {
            customCssPanel.classList.toggle("is-collapsed");
        });
    }

    if (cssMaximizeBtn) {
        cssMaximizeBtn.addEventListener("click", function () {
            customCssPanel.classList.toggle("is-maximized");
        });
    }

    customCssEditor.addEventListener("input", debounce(function () {
        localStorage.setItem(CUSTOM_CSS_KEY, customCssEditor.value);
        applyTheme("custom");
    }, 300));

    // Ctrl/Cmd-S to download
    document.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            downloadPdf();
        }
    });

    // Initial state
    (async function init() {
        await loadThemes();
        const savedCss = localStorage.getItem(CUSTOM_CSS_KEY);
        if (savedCss) customCssEditor.value = savedCss;
        await applyTheme(themeSelect.value);
        const saved = localStorage.getItem(STORAGE_KEY);
        editor.value = saved && saved.trim() ? saved : DEFAULT_MARKDOWN;
        updatePreview();
    })();
})();
