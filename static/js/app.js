(() => {
  const statusNode = document.getElementById("shortcut-status");
  const installPromptNode = document.getElementById("pwa-install-prompt");
  const commandPalette = document.getElementById("command-palette");
  const commandPaletteInput = document.getElementById("command-palette-input");
  const headerSearchInput = document.getElementById("search-input");
  const headerSearchResults = document.getElementById("header-search-results");
  let activeCardIndex = -1;
  let markdownPreviewTimer;
  let deferredInstallPrompt;
  let activeQuickIndex = -1;
  let activeQuickSurface = null;

  const cards = () => Array.from(document.querySelectorAll("[data-post-card]"));
  const quickItems = () =>
    activeQuickSurface ? Array.from(activeQuickSurface.querySelectorAll("[data-quick-item]")) : [];
  const focusCard = (index) => {
    const items = cards();
    if (!items.length) {
      return;
    }
    activeCardIndex = Math.max(0, Math.min(index, items.length - 1));
    items[activeCardIndex].focus();
    items[activeCardIndex].scrollIntoView({ block: "nearest", behavior: "smooth" });
  };

  const announce = (message) => {
    if (!statusNode) {
      return;
    }
    statusNode.textContent = message;
    window.clearTimeout(announce._timer);
    announce._timer = window.setTimeout(() => {
      statusNode.textContent = "";
    }, 1200);
  };

  const closeQuickSurfaces = () => {
    headerSearchResults?.replaceChildren();
    if (commandPalette) {
      commandPalette.classList.add("hidden");
      commandPalette.setAttribute("aria-hidden", "true");
    }
    activeQuickIndex = -1;
    activeQuickSurface = null;
  };

  const openCommandPalette = () => {
    if (!commandPalette || !commandPaletteInput) {
      return;
    }
    commandPalette.classList.remove("hidden");
    commandPalette.setAttribute("aria-hidden", "false");
    commandPaletteInput.focus();
    commandPaletteInput.dispatchEvent(new Event("search", { bubbles: true }));
  };

  const updateQuickSelection = (index) => {
    const items = quickItems();
    if (!items.length) {
      activeQuickIndex = -1;
      return;
    }
    activeQuickIndex = Math.max(0, Math.min(index, items.length - 1));
    items.forEach((item, itemIndex) => {
      item.classList.toggle("bg-opal-light", itemIndex === activeQuickIndex);
      item.classList.toggle("text-opal", itemIndex === activeQuickIndex);
    });
    items[activeQuickIndex].scrollIntoView({ block: "nearest" });
  };

  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (
      event.target?.id === "header-search-results" ||
      event.target?.id === "command-palette-results"
    ) {
      activeQuickSurface = event.target.querySelector("[data-quick-surface]");
      activeQuickIndex = -1;
      const items = quickItems();
      if (items.length) {
        updateQuickSelection(0);
      }
    }
  });

  document.addEventListener("keydown", (event) => {
    const tagName = document.activeElement?.tagName;
    const isTyping = tagName === "INPUT" || tagName === "TEXTAREA" || document.activeElement?.isContentEditable;
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openCommandPalette();
      announce("Command palette opened");
      return;
    }
    if (event.key === "Escape") {
      closeQuickSurfaces();
      return;
    }
    if (activeQuickSurface && ["ArrowDown", "ArrowUp", "Enter"].includes(event.key)) {
      const items = quickItems();
      if (!items.length) {
        return;
      }
      event.preventDefault();
      if (event.key === "ArrowDown") {
        updateQuickSelection(activeQuickIndex + 1);
        return;
      }
      if (event.key === "ArrowUp") {
        updateQuickSelection(activeQuickIndex <= 0 ? 0 : activeQuickIndex - 1);
        return;
      }
      items[activeQuickIndex]?.click();
      return;
    }
    if (event.key === "/" && !isTyping) {
      event.preventDefault();
      headerSearchInput?.focus();
      announce("Search focused");
      return;
    }
    if (isTyping) {
      return;
    }

    if (event.key === "j") {
      event.preventDefault();
      focusCard(activeCardIndex + 1);
      announce("Next post");
    } else if (event.key === "k") {
      event.preventDefault();
      focusCard(activeCardIndex <= 0 ? 0 : activeCardIndex - 1);
      announce("Previous post");
    } else if (event.key === "a") {
      const card = cards()[activeCardIndex];
      card?.querySelector("[data-vote-up]")?.click();
      if (card) {
        announce("Upvoted");
      }
    } else if (event.key === "z") {
      const card = cards()[activeCardIndex];
      card?.querySelector("[data-vote-down]")?.click();
      if (card) {
        announce("Downvoted");
      }
    } else if (event.key === "Enter") {
      const card = cards()[activeCardIndex];
      card?.querySelector('a[href*="/post/"]')?.click();
    }
  });

  const csrfToken = () => {
    const match = document.cookie.match(new RegExp("(^| )csrftoken=([^;]+)"));
    return match ? match[2] : "";
  };

  const requestMarkdownPreview = (textarea) => {
    const targetId = textarea.dataset.markdownPreviewTarget;
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target) {
      return;
    }

    window.clearTimeout(markdownPreviewTimer);
    markdownPreviewTimer = window.setTimeout(async () => {
      try {
        const response = await fetch("/markdown/preview/", {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrfToken(),
          },
          body: new URLSearchParams({ markdown: textarea.value }),
        });
        if (!response.ok) {
          return;
        }
        target.innerHTML = await response.text();
      } catch (_error) {
        // Preview failures should never block the editor itself.
      }
    }, 180);
  };

  const setTextareaSelection = (textarea, start, end) => {
    textarea.focus();
    textarea.setSelectionRange(start, end);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  };

  const replaceSelection = (textarea, replacement, selectStart, selectEnd) => {
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? textarea.value.length;
    const before = textarea.value.slice(0, start);
    const after = textarea.value.slice(end);
    textarea.value = `${before}${replacement}${after}`;
    setTextareaSelection(textarea, before.length + selectStart, before.length + selectEnd);
  };

  const wrapSelection = (textarea, prefix, suffix, fallbackText) => {
    const start = textarea.selectionStart ?? 0;
    const end = textarea.selectionEnd ?? 0;
    const selected = textarea.value.slice(start, end) || fallbackText;
    const replacement = `${prefix}${selected}${suffix}`;
    replaceSelection(textarea, replacement, prefix.length, prefix.length + selected.length);
  };

  const prefixLines = (textarea, prefix) => {
    const start = textarea.selectionStart ?? 0;
    const end = textarea.selectionEnd ?? 0;
    const selected = textarea.value.slice(start, end) || "Your text";
    const replacement = selected
      .split("\n")
      .map((line) => `${prefix}${line || ""}`.trimEnd())
      .join("\n");
    replaceSelection(textarea, replacement, 0, replacement.length);
  };

  const prefixOrderedList = (textarea) => {
    const start = textarea.selectionStart ?? 0;
    const end = textarea.selectionEnd ?? 0;
    const selected = textarea.value.slice(start, end) || "First item\nSecond item";
    const replacement = selected
      .split("\n")
      .map((line, index) => `${index + 1}. ${line || "List item"}`)
      .join("\n");
    replaceSelection(textarea, replacement, 0, replacement.length);
  };

  const insertCode = (textarea) => {
    const start = textarea.selectionStart ?? 0;
    const end = textarea.selectionEnd ?? 0;
    const selected = textarea.value.slice(start, end);
    if (selected.includes("\n")) {
      const replacement = `\`\`\`\n${selected || "code block"}\n\`\`\``;
      replaceSelection(textarea, replacement, 4, replacement.length - 4);
      return;
    }
    wrapSelection(textarea, "`", "`", "code");
  };

  const insertLink = (textarea) => {
    const start = textarea.selectionStart ?? 0;
    const end = textarea.selectionEnd ?? 0;
    const selected = textarea.value.slice(start, end) || "link text";
    const href = window.prompt("Link URL", "https://");
    if (!href) {
      return;
    }
    const replacement = `[${selected}](${href})`;
    replaceSelection(textarea, replacement, 1, 1 + selected.length);
  };

  const markdownToolHandlers = {
    bold: (textarea) => wrapSelection(textarea, "**", "**", "bold text"),
    italic: (textarea) => wrapSelection(textarea, "*", "*", "italic text"),
    link: (textarea) => insertLink(textarea),
    heading: (textarea) => prefixLines(textarea, "## "),
    quote: (textarea) => prefixLines(textarea, "> "),
    bullet: (textarea) => prefixLines(textarea, "- "),
    ordered: (textarea) => prefixOrderedList(textarea),
    code: (textarea) => insertCode(textarea),
  };

  const toolbarButtons = [
    { action: "bold", label: "Bold", icon: "B" },
    { action: "italic", label: "Italic", icon: "I" },
    { action: "link", label: "Link", icon: "Link" },
    { action: "heading", label: "Heading", icon: "H2" },
    { action: "quote", label: "Quote", icon: "Quote" },
    { action: "bullet", label: "Bullets", icon: "List" },
    { action: "ordered", label: "Numbered list", icon: "1." },
    { action: "code", label: "Code", icon: "</>" },
  ];

  const attachMarkdownToolbar = (textarea) => {
    if (!textarea || textarea.dataset.toolbarMounted === "true") {
      return;
    }
    textarea.dataset.toolbarMounted = "true";
    const toolbar = document.createElement("div");
    toolbar.className = "markdown-toolbar";
    toolbar.setAttribute("role", "toolbar");
    toolbar.setAttribute("aria-label", textarea.dataset.markdownPreviewLabel || "Markdown formatting");
    toolbarButtons.forEach((buttonConfig) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "markdown-toolbar__button";
      button.dataset.markdownAction = buttonConfig.action;
      button.setAttribute("aria-label", buttonConfig.label);
      button.title = buttonConfig.label;
      button.textContent = buttonConfig.icon;
      button.addEventListener("click", () => {
        markdownToolHandlers[buttonConfig.action]?.(textarea);
        announce(`${buttonConfig.label} inserted`);
      });
      toolbar.appendChild(button);
    });
    textarea.parentNode.insertBefore(toolbar, textarea);
  };

  document.querySelectorAll("textarea[data-rich-markdown], textarea[data-markdown-preview-target]").forEach((textarea) => {
    attachMarkdownToolbar(textarea);
  });

  document.querySelectorAll("textarea[data-markdown-preview-target]").forEach((textarea) => {
    textarea.addEventListener("input", () => requestMarkdownPreview(textarea));
    if (textarea.value.trim()) {
      requestMarkdownPreview(textarea);
    }
  });

  const dismissInstallPrompt = () => {
    installPromptNode?.classList.add("hidden");
  };

  document.querySelector("[data-install-dismiss]")?.addEventListener("click", dismissInstallPrompt);
  document.querySelector("[data-install-trigger]")?.addEventListener("click", async () => {
    if (!deferredInstallPrompt) {
      dismissInstallPrompt();
      return;
    }
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice.catch(() => null);
    deferredInstallPrompt = null;
    dismissInstallPrompt();
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    installPromptNode?.classList.remove("hidden");
  });

  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    dismissInstallPrompt();
    announce("Agora installed");
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/service-worker.js").catch(() => {
        // Registration failures should not break the rest of the app.
      });
    });
  }

  document.querySelectorAll("[data-auto-submit]").forEach((node) => {
    node.addEventListener("change", () => {
      node.closest("form")?.submit();
    });
  });

  document.querySelectorAll("[data-copy-text]").forEach((button) => {
    button.addEventListener("click", async () => {
      const text = button.dataset.copyText || "";
      if (!text) {
        return;
      }
      try {
        await navigator.clipboard.writeText(text);
        announce(button.dataset.copyLabel || "Copied");
      } catch (_error) {
        // Clipboard failures should not block the rest of the page.
      }
    });
  });

  document.querySelectorAll("[data-insert-into]").forEach((button) => {
    button.addEventListener("click", () => {
      const field = document.getElementById(button.dataset.insertInto);
      if (!field) {
        return;
      }
      const text = button.dataset.insertText || "";
      field.value = field.value.trim() ? `${field.value}\n\n${text}` : text;
      field.dispatchEvent(new Event("input", { bubbles: true }));
      field.focus();
      announce("Reply snippet inserted");
    });
  });

  const recordShare = (url) => {
    if (!url) {
      return;
    }
    if (navigator.sendBeacon) {
      const formData = new FormData();
      formData.append("csrfmiddlewaretoken", csrfToken());
      navigator.sendBeacon(url, formData);
      return;
    }
    fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken(),
      },
    }).catch(() => {
      // Share tracking should never break outbound sharing.
    });
  };

  document.querySelectorAll("[data-share-record-url]").forEach((link) => {
    link.addEventListener("click", () => {
      recordShare(link.dataset.shareRecordUrl);
    });
  });

  document.querySelectorAll("[data-share-title]").forEach((button) => {
    button.addEventListener("click", async () => {
      const title = button.dataset.shareTitle || document.title;
      const text = button.dataset.shareText || "";
      const url = button.dataset.shareUrl || window.location.href;
      const recordUrl = button.dataset.shareRecordUrl;
      if (navigator.share) {
        try {
          await navigator.share({ title, text, url });
          recordShare(recordUrl);
          announce("Shared");
          return;
        } catch (_error) {
          // Fall back to clipboard on cancelled or unsupported flows.
        }
      }
      if (url) {
        try {
          await navigator.clipboard.writeText(url);
          recordShare(recordUrl);
          announce(button.dataset.copyLabel || "Link copied");
        } catch (_error) {
          // Clipboard failures should not break the rest of the page.
        }
      }
    });
  });

  document.querySelectorAll("[data-command-open]").forEach((button) => {
    button.addEventListener("click", openCommandPalette);
  });

  document.addEventListener("click", (event) => {
    if (commandPalette && !commandPalette.classList.contains("hidden")) {
      const withinPalette = event.target.closest("#command-palette > div");
      if (!withinPalette) {
        closeQuickSurfaces();
      }
    }
    if (headerSearchResults && !event.target.closest('form[action="/search/"]')) {
      headerSearchResults.replaceChildren();
      activeQuickSurface = null;
      activeQuickIndex = -1;
    }
  });
})();
