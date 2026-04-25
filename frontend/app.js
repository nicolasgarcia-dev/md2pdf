(function () {
    "use strict";

    // ─── DOM references ────────────────────────────────────────────────
    const editor = document.getElementById("editor");
    const preview = document.getElementById("preview");
    const themeSelect = document.getElementById("theme");
    const titleInput = document.getElementById("title");
    const scaleInput = document.getElementById("scale");
    const tocCheckbox = document.getElementById("toc");
    const uploadInput = document.getElementById("upload");
    const downloadButton = document.getElementById("download");
    const statusEl = document.getElementById("status");
    const saveStateEl = document.getElementById("save-state");
    const editorStatsEl = document.getElementById("editor-stats");
    const customCssPanel = document.getElementById("custom-css-panel");
    const customCssEditor = document.getElementById("custom-css-editor");
    const customCssOverlay = document.getElementById("custom-css-overlay");
    const colorPopover = document.getElementById("color-popover");
    const cpNative = document.getElementById("cp-native");
    const cpR = document.getElementById("cp-r");
    const cpG = document.getElementById("cp-g");
    const cpB = document.getElementById("cp-b");
    const cpHex = document.getElementById("cp-hex");
    const cpApply = document.getElementById("cp-apply");
    const cpCancel = document.getElementById("cp-cancel");
    const cssHelpBtn = document.getElementById("css-help-btn");
    const cssExpandBtn = document.getElementById("css-expand-btn");
    const cssMaximizeBtn = document.getElementById("css-maximize-btn");
    const cssHelpDialog = document.getElementById("css-help-dialog");
    const cssHelpClose = document.getElementById("css-help-close");
    const syncScrollBtn = document.getElementById("sync-scroll-btn");
    const brandMark = document.querySelector(".brand-mark");
    const shortcutsBtn = document.getElementById("shortcuts-btn");
    const shortcutsDialog = document.getElementById("shortcuts-dialog");
    const shortcutsClose = document.getElementById("shortcuts-close");
    const docsSidebar = document.getElementById("docs-sidebar");
    const docsToggle = document.getElementById("docs-toggle");
    const docsBackdrop = document.getElementById("docs-backdrop");
    const docsList = document.getElementById("docs-list");
    const docsNewBtn = document.getElementById("docs-new");

    // ─── Storage keys ──────────────────────────────────────────────────
    const LEGACY_KEY = "md2pdf:last";
    const CUSTOM_CSS_KEY = "md2pdf:custom-css";
    const SCALE_KEY = "md2pdf:scale";
    const DOCS_KEY = "md2pdf:docs";
    const ACTIVE_DOC_KEY = "md2pdf:active-doc";
    const SIDEBAR_KEY = "md2pdf:sidebar-open";
    const SYNC_SCROLL_KEY = "md2pdf:sync-scroll";

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
        "  B -->|primary| C[Chromium]",
        "  B -->|fallback| D[WeasyPrint]",
        "```",
        "",
        "- Emoji support: check, rocket, sparkles (native Unicode)",
        "",
        "Enjoy!",
    ].join("\n");

    // ─── Helpers ───────────────────────────────────────────────────────
    function escapeHtml(s) {
        return s.replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    function debounce(fn, wait) {
        let t;
        return function () {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, arguments), wait);
        };
    }

    function readScale() {
        let n = parseInt(scaleInput.value, 10);
        if (!Number.isFinite(n)) n = 100;
        if (n < 60) n = 60;
        if (n > 140) n = 140;
        return n;
    }

    function showStatus(message, isError) {
        statusEl.textContent = message;
        statusEl.hidden = false;
        statusEl.classList.toggle("error", Boolean(isError));
        clearTimeout(showStatus._t);
        showStatus._t = setTimeout(function () { statusEl.hidden = true; }, 3500);
    }

    function uid() {
        return "d-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 7);
    }

    // ─── Documents store ───────────────────────────────────────────────
    let docs = [];
    let activeId = null;

    function loadDocs() {
        try {
            const raw = localStorage.getItem(DOCS_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) docs = parsed;
            }
        } catch (_e) { /* corrupt JSON — ignore */ }
        // Migrate legacy single-document storage on first run.
        if (!docs.length) {
            const legacy = localStorage.getItem(LEGACY_KEY);
            const content = legacy && legacy.trim() ? legacy : DEFAULT_MARKDOWN;
            docs = [{ id: uid(), name: "document", content, updatedAt: Date.now() }];
        }
        const savedActive = localStorage.getItem(ACTIVE_DOC_KEY);
        if (savedActive && docs.some(d => d.id === savedActive)) {
            activeId = savedActive;
        } else {
            activeId = docs[0].id;
        }
    }

    function saveDocs() {
        localStorage.setItem(DOCS_KEY, JSON.stringify(docs));
        localStorage.setItem(ACTIVE_DOC_KEY, activeId);
    }

    function activeDoc() {
        return docs.find(d => d.id === activeId);
    }

    function renderDocsList() {
        docsList.innerHTML = "";
        docs.forEach(function (d) {
            const li = document.createElement("li");
            li.className = "docs-item" + (d.id === activeId ? " is-active" : "");
            li.dataset.id = d.id;

            const name = document.createElement("span");
            name.className = "docs-item-name";
            name.textContent = d.name || "Untitled";
            name.title = d.name;

            const actions = document.createElement("span");
            actions.className = "docs-item-actions";

            const renameBtn = document.createElement("button");
            renameBtn.type = "button";
            renameBtn.className = "docs-item-btn";
            renameBtn.title = "Rename";
            renameBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>';

            const deleteBtn = document.createElement("button");
            deleteBtn.type = "button";
            deleteBtn.className = "docs-item-btn is-danger";
            deleteBtn.title = "Delete";
            deleteBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>';

            actions.appendChild(renameBtn);
            actions.appendChild(deleteBtn);

            li.appendChild(name);
            li.appendChild(actions);

            li.addEventListener("click", function (e) {
                if (e.target.closest(".docs-item-btn")) return;
                if (name.isContentEditable) return;
                if (d.id !== activeId) switchDoc(d.id);
                if (window.matchMedia("(max-width: 920px)").matches) setSidebar(false);
            });

            renameBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                startRename(name, d);
            });

            deleteBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                deleteDoc(d.id);
            });

            docsList.appendChild(li);
        });
    }

    function startRename(nameEl, doc) {
        nameEl.contentEditable = "true";
        nameEl.focus();
        const range = document.createRange();
        range.selectNodeContents(nameEl);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);

        function finish(commit) {
            nameEl.contentEditable = "false";
            const newName = (nameEl.textContent || "").trim() || "Untitled";
            if (commit) {
                doc.name = newName;
                if (doc.id === activeId) titleInput.value = newName;
                saveDocs();
            }
            nameEl.textContent = doc.name;
            nameEl.removeEventListener("keydown", onKey);
            nameEl.removeEventListener("blur", onBlur);
        }
        function onKey(e) {
            if (e.key === "Enter") { e.preventDefault(); finish(true); }
            else if (e.key === "Escape") { e.preventDefault(); finish(false); }
        }
        function onBlur() { finish(true); }
        nameEl.addEventListener("keydown", onKey);
        nameEl.addEventListener("blur", onBlur);
    }

    function switchDoc(id) {
        commitActive();
        activeId = id;
        const doc = activeDoc();
        if (!doc) return;
        editor.value = doc.content;
        titleInput.value = doc.name;
        saveDocs();
        renderDocsList();
        updatePreview();
        updateStats();
        markSaved();
    }

    function newDoc() {
        commitActive();
        const doc = { id: uid(), name: "Untitled", content: "", updatedAt: Date.now() };
        docs.unshift(doc);
        activeId = doc.id;
        editor.value = "";
        titleInput.value = doc.name;
        saveDocs();
        renderDocsList();
        updatePreview();
        updateStats();
        markSaved();
        editor.focus();
    }

    function deleteDoc(id) {
        const idx = docs.findIndex(d => d.id === id);
        if (idx < 0) return;
        const isActive = id === activeId;
        if (docs.length === 1) {
            // Don't leave the user with zero docs — reset the only one.
            docs[0] = { id: uid(), name: "Untitled", content: "", updatedAt: Date.now() };
            activeId = docs[0].id;
        } else {
            docs.splice(idx, 1);
            if (isActive) activeId = docs[Math.max(0, idx - 1)].id;
        }
        const doc = activeDoc();
        editor.value = doc.content;
        titleInput.value = doc.name;
        saveDocs();
        renderDocsList();
        updatePreview();
        updateStats();
        markSaved();
    }

    function commitActive() {
        const doc = activeDoc();
        if (!doc) return;
        doc.content = editor.value;
        doc.updatedAt = Date.now();
    }

    // Persist editor contents into the active doc, debounced.
    const persistEditor = debounce(function () {
        commitActive();
        saveDocs();
        renderDocsList();
        markSaved();
    }, 350);

    // ─── Save-state indicator ──────────────────────────────────────────
    function markDirty() {
        if (!saveStateEl) return;
        saveStateEl.textContent = "Saving…";
        saveStateEl.classList.remove("is-saved");
        saveStateEl.classList.add("is-dirty");
    }
    function markSaved() {
        if (!saveStateEl) return;
        saveStateEl.textContent = "Saved";
        saveStateEl.classList.remove("is-dirty");
        saveStateEl.classList.add("is-saved");
    }

    // ─── Marked configuration ──────────────────────────────────────────
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

    const renderer = new marked.Renderer();
    const originalCode = renderer.code.bind(renderer);
    renderer.code = function (code, infostring) {
        if ((infostring || "").trim().toLowerCase() === "mermaid") {
            return '<pre class="mermaid">' + escapeHtml(code) + "</pre>";
        }
        return originalCode(code, infostring);
    };
    marked.use({ renderer });

    // ─── Math extension for marked ─────────────────────────────────────
    // Without this, marked's escape rules collapse `\\` to `\` inside math,
    // which breaks LaTeX row separators in matrices (e.g. \begin{matrix}).
    // The extension tokenises $$…$$ and $…$ as opaque blocks and re-emits
    // their contents verbatim so KaTeX can render them downstream.
    marked.use({
        extensions: [
            {
                name: "mathBlock",
                level: "block",
                start(src) {
                    const idx = src.indexOf("$$");
                    return idx >= 0 ? idx : undefined;
                },
                tokenizer(src) {
                    const m = /^\$\$([\s\S]+?)\$\$/.exec(src);
                    if (m) return { type: "mathBlock", raw: m[0], text: m[1] };
                },
                renderer(token) {
                    return "<p>$$" + escapeHtml(token.text) + "$$</p>";
                },
            },
            {
                name: "mathInline",
                level: "inline",
                start(src) {
                    const m = src.match(/(?<!\\)\$(?!\$)/);
                    return m ? m.index : undefined;
                },
                tokenizer(src) {
                    const m = /^\$((?:\\\$|[^\$\n])+?)\$(?!\$)/.exec(src);
                    if (m) return { type: "mathInline", raw: m[0], text: m[1] };
                },
                renderer(token) {
                    return "$" + escapeHtml(token.text) + "$";
                },
            },
        ],
    });

    // ─── Preview rendering ─────────────────────────────────────────────
    let mermaidCounter = 0;
    let renderToken = 0;

    async function updatePreview() {
        const token = ++renderToken;
        const md = editor.value;
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

    // ─── Editor stats (word count + estimated pages) ───────────────────
    function updateStats() {
        if (!editorStatsEl) return;
        const text = editor.value;
        const words = (text.match(/\S+/g) || []).length;
        // Rough estimate: ~3000 chars per A4 page at 100% scale; scale aware.
        const scale = readScale() / 100;
        const charsPerPage = 3000 * scale * scale; // rough — denser pages at smaller scale
        const pages = Math.max(1, Math.ceil(text.length / charsPerPage));
        editorStatsEl.textContent = words + " word" + (words === 1 ? "" : "s") + " · ~" + pages + " page" + (pages === 1 ? "" : "s");
    }

    // ─── Theme handling ────────────────────────────────────────────────
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

    // ─── PDF download ──────────────────────────────────────────────────
    async function downloadPdf() {
        const body = {
            markdown: editor.value,
            theme: themeSelect.value,
            title: titleInput.value || "document",
            include_toc: tocCheckbox.checked,
            custom_css: themeSelect.value === "custom" ? customCssEditor.value : "",
            scale: readScale() / 100,
        };
        downloadButton.disabled = true;
        if (brandMark) brandMark.classList.add("is-rendering");
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
            if (brandMark) brandMark.classList.remove("is-rendering");
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
            const baseName = (file.name || "").replace(/\.(md|markdown|txt)$/i, "") || "document";
            // Load into the active document so it stays in the sidebar list.
            editor.value = text;
            titleInput.value = baseName;
            const doc = activeDoc();
            if (doc) {
                doc.name = baseName;
                doc.content = text;
                doc.updatedAt = Date.now();
            }
            saveDocs();
            renderDocsList();
            updatePreview();
            updateStats();
            markSaved();
            showStatus("Loaded " + file.name);
        } catch (_err) {
            showStatus("Failed to read file", true);
        }
    }

    // ─── Sync scroll between editor and preview ────────────────────────
    let syncEnabled = true;
    let syncSource = null;
    function syncFrom(source, target) {
        if (!syncEnabled) return;
        if (syncSource && syncSource !== source) return;
        syncSource = source;
        const sMax = source.scrollHeight - source.clientHeight;
        const tMax = target.scrollHeight - target.clientHeight;
        if (sMax > 0 && tMax > 0) {
            target.scrollTop = (source.scrollTop / sMax) * tMax;
        }
        clearTimeout(syncFrom._t);
        syncFrom._t = setTimeout(() => { syncSource = null; }, 80);
    }
    editor.addEventListener("scroll", function () { syncFrom(editor, preview); });
    preview.addEventListener("scroll", function () { syncFrom(preview, editor); });

    function setSyncScroll(on) {
        syncEnabled = on;
        syncScrollBtn.classList.toggle("is-on", on);
        syncScrollBtn.setAttribute("aria-pressed", on ? "true" : "false");
        syncScrollBtn.title = on
            ? "Sync scroll: ON (click to unlink)"
            : "Sync scroll: OFF (click to link)";
        localStorage.setItem(SYNC_SCROLL_KEY, on ? "1" : "0");
    }
    syncScrollBtn.addEventListener("click", function () { setSyncScroll(!syncEnabled); });

    // ─── Drag & drop .md onto editor ───────────────────────────────────
    function isMdFile(f) {
        if (!f) return false;
        const n = (f.name || "").toLowerCase();
        return /\.(md|markdown|txt)$/.test(n) || f.type === "text/markdown" || f.type === "text/plain";
    }
    ["dragenter", "dragover"].forEach(function (ev) {
        editor.addEventListener(ev, function (e) {
            if (e.dataTransfer && Array.from(e.dataTransfer.items || []).some(it => it.kind === "file")) {
                e.preventDefault();
                e.dataTransfer.dropEffect = "copy";
            }
        });
    });
    editor.addEventListener("drop", function (e) {
        const files = e.dataTransfer && e.dataTransfer.files;
        if (!files || !files.length) return;
        e.preventDefault();
        const f = files[0];
        if (isMdFile(f)) handleUpload(f);
        else showStatus("Drop a .md / .markdown / .txt file", true);
    });

    // ─── Markdown shortcuts in editor ──────────────────────────────────
    function wrapSelection(before, after, placeholder) {
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        const value = editor.value;
        const sel = value.slice(start, end) || (placeholder || "");
        const next = value.slice(0, start) + before + sel + after + value.slice(end);
        editor.value = next;
        const newStart = start + before.length;
        const newEnd = newStart + sel.length;
        editor.setSelectionRange(newStart, newEnd);
        editor.dispatchEvent(new Event("input", { bubbles: true }));
    }

    function indentSelection(outdent, target) {
        const ta = target || editor;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const value = ta.value;
        const lineStart = value.lastIndexOf("\n", start - 1) + 1;
        const block = value.slice(lineStart, end);
        const lines = block.split("\n");
        const transformed = lines.map(function (ln) {
            if (outdent) {
                if (ln.startsWith("    ")) return ln.slice(4);
                if (ln.startsWith("\t")) return ln.slice(1);
                return ln.replace(/^ {1,3}/, "");
            }
            return "    " + ln;
        }).join("\n");
        ta.value = value.slice(0, lineStart) + transformed + value.slice(end);
        const delta = transformed.length - block.length;
        ta.setSelectionRange(lineStart, end + delta);
        ta.dispatchEvent(new Event("input", { bubbles: true }));
    }

    editor.addEventListener("keydown", function (e) {
        // Tab / Shift+Tab handled inside the textarea
        if (e.key === "Tab") {
            e.preventDefault();
            indentSelection(e.shiftKey);
            return;
        }
        if (!(e.ctrlKey || e.metaKey)) return;
        const k = e.key.toLowerCase();
        if (k === "b") { e.preventDefault(); wrapSelection("**", "**", "bold"); }
        else if (k === "i") { e.preventDefault(); wrapSelection("_", "_", "italic"); }
        else if (k === "k") { e.preventDefault(); wrapSelection("[", "](url)", "link text"); }
    });

    // ─── Sidebar collapse/expand ───────────────────────────────────────
    function setSidebar(open) {
        docsSidebar.classList.toggle("is-collapsed", !open);
        if (docsBackdrop) docsBackdrop.classList.toggle("is-visible", open);
        localStorage.setItem(SIDEBAR_KEY, open ? "1" : "0");
    }
    if (docsBackdrop) {
        docsBackdrop.addEventListener("click", function () { setSidebar(false); });
    }
    docsToggle.addEventListener("click", function () {
        setSidebar(docsSidebar.classList.contains("is-collapsed"));
    });
    docsNewBtn.addEventListener("click", function (e) { e.stopPropagation(); newDoc(); });

    // ─── Wire up: editor and toolbar ───────────────────────────────────
    editor.addEventListener("input", function () {
        markDirty();
        updatePreview();
        updateStats();
        persistEditor();
    });

    titleInput.addEventListener("input", function () {
        const doc = activeDoc();
        if (!doc) return;
        doc.name = titleInput.value || "Untitled";
        markDirty();
        persistEditor();
    });

    downloadButton.addEventListener("click", downloadPdf);
    uploadInput.addEventListener("change", function () {
        const f = uploadInput.files && uploadInput.files[0];
        if (f) handleUpload(f);
        uploadInput.value = "";
    });
    themeSelect.addEventListener("change", function () { applyTheme(themeSelect.value); });
    scaleInput.addEventListener("change", function () {
        const n = readScale();
        scaleInput.value = String(n);
        localStorage.setItem(SCALE_KEY, String(n));
        updateStats();
    });

    // Help dialogs
    cssHelpBtn.addEventListener("click", function () { cssHelpDialog.showModal(); });
    cssHelpClose.addEventListener("click", function () { cssHelpDialog.close(); });
    cssHelpDialog.addEventListener("click", function (e) {
        if (e.target === cssHelpDialog) cssHelpDialog.close();
    });

    shortcutsBtn.addEventListener("click", function () { shortcutsDialog.showModal(); });
    shortcutsClose.addEventListener("click", function () { shortcutsDialog.close(); });
    shortcutsDialog.addEventListener("click", function (e) {
        if (e.target === shortcutsDialog) shortcutsDialog.close();
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

    customCssEditor.addEventListener("keydown", function (e) {
        if (e.key === "Tab") {
            e.preventDefault();
            indentSelection(e.shiftKey, customCssEditor);
        }
    });

    customCssEditor.addEventListener("input", debounce(function () {
        localStorage.setItem(CUSTOM_CSS_KEY, customCssEditor.value);
        applyTheme("custom");
    }, 300));

    // ─── CSS color swatches + picker ───────────────────────────────────
    // Tokens are kept simple on purpose: 6-digit hex, 3-digit hex, and
    // rgb(r,g,b). 6-digit listed first so it wins over the 3-digit prefix.
    const COLOR_RE = /#[0-9a-fA-F]{6}(?![0-9a-fA-F])|#[0-9a-fA-F]{3}(?![0-9a-fA-F])|rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)/g;

    function escapeHtml(s) {
        return s.replace(/[&<>]/g, function (c) {
            return c === "&" ? "&amp;" : c === "<" ? "&lt;" : "&gt;";
        });
    }

    function clamp255(n) { return Math.max(0, Math.min(255, n | 0)); }

    function parseColor(s) {
        if (s[0] === "#") {
            let h = s.slice(1);
            if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
            return {
                r: parseInt(h.slice(0, 2), 16),
                g: parseInt(h.slice(2, 4), 16),
                b: parseInt(h.slice(4, 6), 16),
            };
        }
        const m = s.match(/\d+/g) || [0, 0, 0];
        return { r: clamp255(+m[0]), g: clamp255(+m[1]), b: clamp255(+m[2]) };
    }

    function toHex(c) {
        const h = function (n) { return clamp255(n).toString(16).padStart(2, "0"); };
        return "#" + h(c.r) + h(c.g) + h(c.b);
    }

    // Format the new color string in the same shape as the original token,
    // so a hex stays hex and rgb() stays rgb().
    function formatLikeOriginal(original, c) {
        if (original[0] === "#") {
            if (original.length === 4) {
                // Only collapse to 3-digit if each channel is a duplicated nibble.
                const hex = toHex(c);
                if (hex[1] === hex[2] && hex[3] === hex[4] && hex[5] === hex[6]) {
                    return "#" + hex[1] + hex[3] + hex[5];
                }
                return hex;
            }
            return toHex(c);
        }
        return "rgb(" + c.r + ", " + c.g + ", " + c.b + ")";
    }

    function renderOverlay() {
        const text = customCssEditor.value;
        let html = "";
        let last = 0;
        let m;
        COLOR_RE.lastIndex = 0;
        while ((m = COLOR_RE.exec(text)) !== null) {
            const start = m.index;
            const end = start + m[0].length;
            html += escapeHtml(text.slice(last, start));
            const swatchColor = toHex(parseColor(m[0]));
            html += '<span class="swatch" style="--swatch-color:' + swatchColor +
                '" data-start="' + start + '" data-end="' + end + '">' +
                escapeHtml(m[0]) + "</span>";
            last = end;
        }
        // Trailing newline mirrors textarea behavior so the last line aligns.
        html += escapeHtml(text.slice(last)) + "\n";
        customCssOverlay.innerHTML = html;
        syncOverlayScroll();
    }

    function syncOverlayScroll() {
        customCssOverlay.scrollTop = customCssEditor.scrollTop;
        customCssOverlay.scrollLeft = customCssEditor.scrollLeft;
    }

    customCssEditor.addEventListener("input", renderOverlay);
    customCssEditor.addEventListener("scroll", syncOverlayScroll);
    window.addEventListener("resize", syncOverlayScroll);

    // ─── Color picker popover ──────────────────────────────────────────
    let pickerCtx = null; // { start, end, original }
    let updatingPicker = false;

    function setPickerColor(c, sourceField) {
        updatingPicker = true;
        const hex = toHex(c);
        if (sourceField !== cpR) cpR.value = c.r;
        if (sourceField !== cpG) cpG.value = c.g;
        if (sourceField !== cpB) cpB.value = c.b;
        if (sourceField !== cpHex) cpHex.value = hex;
        if (sourceField !== cpNative) cpNative.value = hex;
        updatingPicker = false;
    }

    function getPickerColor() {
        return { r: clamp255(+cpR.value), g: clamp255(+cpG.value), b: clamp255(+cpB.value) };
    }

    function positionPopover(rect) {
        // Make sure dimensions are measured before clamping.
        colorPopover.style.left = "0px";
        colorPopover.style.top = "0px";
        const pw = colorPopover.offsetWidth;
        const ph = colorPopover.offsetHeight;
        const margin = 8;
        let left = rect.left;
        let top = rect.bottom + 6;
        if (left + pw + margin > window.innerWidth) left = window.innerWidth - pw - margin;
        if (top + ph + margin > window.innerHeight) top = rect.top - ph - 6;
        if (left < margin) left = margin;
        if (top < margin) top = margin;
        colorPopover.style.left = left + "px";
        colorPopover.style.top = top + "px";
    }

    function openPicker(swatchEl) {
        const start = +swatchEl.dataset.start;
        const end = +swatchEl.dataset.end;
        const original = customCssEditor.value.slice(start, end);
        if (!COLOR_RE.test(original)) { COLOR_RE.lastIndex = 0; return; }
        COLOR_RE.lastIndex = 0;
        pickerCtx = { start: start, end: end, original: original };
        setPickerColor(parseColor(original), null);
        colorPopover.hidden = false;
        positionPopover(swatchEl.getBoundingClientRect());
        cpHex.focus();
        cpHex.select();
    }

    function closePicker() {
        colorPopover.hidden = true;
        pickerCtx = null;
    }

    function applyPicker() {
        if (!pickerCtx) { closePicker(); return; }
        // Re-validate the range still matches the original token (user may
        // have typed elsewhere, shifting indices). If not, abort silently.
        const cur = customCssEditor.value.slice(pickerCtx.start, pickerCtx.end);
        if (cur !== pickerCtx.original) { closePicker(); return; }
        const c = getPickerColor();
        const next = formatLikeOriginal(pickerCtx.original, c);
        const v = customCssEditor.value;
        customCssEditor.value = v.slice(0, pickerCtx.start) + next + v.slice(pickerCtx.end);
        closePicker();
        // Trigger save + theme reapply + overlay re-render.
        customCssEditor.dispatchEvent(new Event("input", { bubbles: true }));
    }

    customCssOverlay.addEventListener("click", function (e) {
        const sw = e.target.closest(".swatch");
        if (!sw) return;
        e.preventDefault();
        openPicker(sw);
    });

    cpNative.addEventListener("input", function () {
        setPickerColor(parseColor(cpNative.value), cpNative);
    });
    [cpR, cpG, cpB].forEach(function (inp) {
        inp.addEventListener("input", function () {
            if (updatingPicker) return;
            setPickerColor(getPickerColor(), inp);
        });
    });
    cpHex.addEventListener("input", function () {
        if (updatingPicker) return;
        const v = cpHex.value.trim();
        if (/^#?[0-9a-fA-F]{6}$/.test(v) || /^#?[0-9a-fA-F]{3}$/.test(v)) {
            setPickerColor(parseColor(v[0] === "#" ? v : "#" + v), cpHex);
        }
    });
    cpApply.addEventListener("click", applyPicker);
    cpCancel.addEventListener("click", closePicker);

    // Close the picker if the user edits the textarea (indices may shift)
    // or clicks outside the popover. Escape also closes.
    document.addEventListener("mousedown", function (e) {
        if (colorPopover.hidden) return;
        if (colorPopover.contains(e.target)) return;
        if (e.target.closest(".swatch")) return;
        closePicker();
    });
    document.addEventListener("keydown", function (e) {
        if (!colorPopover.hidden && e.key === "Escape") {
            e.preventDefault();
            closePicker();
        }
    });
    customCssEditor.addEventListener("keydown", function () {
        if (!colorPopover.hidden) closePicker();
    });

    // ─── Global keyboard shortcuts ─────────────────────────────────────
    document.addEventListener("keydown", function (e) {
        const inField = e.target instanceof HTMLInputElement
            || e.target instanceof HTMLTextAreaElement
            || (e.target && e.target.isContentEditable);

        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            downloadPdf();
            return;
        }
        if ((e.ctrlKey || e.metaKey) && e.key === "`") {
            e.preventDefault();
            setSidebar(docsSidebar.classList.contains("is-collapsed"));
            return;
        }
        if (!inField && e.key === "?") {
            e.preventDefault();
            shortcutsDialog.showModal();
        }
    });

    // ─── Initial load ──────────────────────────────────────────────────
    (async function init() {
        await loadThemes();

        const savedCss = localStorage.getItem(CUSTOM_CSS_KEY);
        if (savedCss) customCssEditor.value = savedCss;
        renderOverlay();

        const savedScale = parseInt(localStorage.getItem(SCALE_KEY) || "", 10);
        if (Number.isFinite(savedScale) && savedScale >= 60 && savedScale <= 140) {
            scaleInput.value = String(savedScale);
        }

        loadDocs();
        const doc = activeDoc();
        editor.value = doc.content;
        titleInput.value = doc.name;
        renderDocsList();

        // Sidebar: collapsed by default, restore previous choice.
        setSidebar(localStorage.getItem(SIDEBAR_KEY) === "1");

        // Sync-scroll: on by default, restore previous choice.
        setSyncScroll(localStorage.getItem(SYNC_SCROLL_KEY) !== "0");

        await applyTheme(themeSelect.value);
        updatePreview();
        updateStats();
        markSaved();
    })();
})();
