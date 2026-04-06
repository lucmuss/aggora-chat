(() => {
  const statusNode = document.getElementById("shortcut-status");
  const installPromptNode = document.getElementById("pwa-install-prompt");
  const commandPalette = document.getElementById("command-palette");
  const commandPaletteInput = document.getElementById("command-palette-input");
  const headerSearchInput = document.getElementById("search-input");
  const headerSearchResults = document.getElementById("header-search-results");
  const pushPreferenceCheckbox = document.getElementById("id_push_notifications_enabled");
  const browserNotificationsEnabled = document.body.dataset.browserNotificationsEnabled === "true";
  const browserNotificationsFeedUrl = document.body.dataset.browserNotificationsFeedUrl || "";
  const browserNotificationsOpenUrl = document.body.dataset.browserNotificationsUrl || "/accounts/notifications/";
  let activeCardIndex = -1;
  let markdownPreviewTimer;
  let deferredInstallPrompt;
  let activeQuickIndex = -1;
  let activeQuickSurface = null;
  let browserNotificationTimer = null;
  let browserNotificationsRuntimeEnabled = browserNotificationsEnabled;
  const installPromptSeenKey = "agora.installPromptSeen";
  const browserNotificationCursorKey = "agora.browserNotificationCursor";

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
    initializeRichTextareas(event.target);
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

  const getBrowserNotificationCursor = () => {
    try {
      return window.localStorage.getItem(browserNotificationCursorKey);
    } catch (_error) {
      return null;
    }
  };

  const setBrowserNotificationCursor = (value) => {
    if (!value) {
      return;
    }
    try {
      window.localStorage.setItem(browserNotificationCursorKey, value);
    } catch (_error) {
      // Ignore storage failures and keep browser notifications best-effort.
    }
  };

  const showBrowserNotification = async (item) => {
    if (!("Notification" in window) || Notification.permission !== "granted") {
      return;
    }
    try {
      const registration = await navigator.serviceWorker.ready;
      if (registration?.showNotification) {
        await registration.showNotification(item.title || "Agora notification", {
          body: item.message || "",
          icon: "/static/icons/agora-icon.svg",
          badge: "/static/icons/agora-icon.svg",
          data: { url: item.url || browserNotificationsOpenUrl },
        });
        return;
      }
    } catch (_error) {
      // Fall back to the window API below.
    }
    const notification = new Notification(item.title || "Agora notification", {
      body: item.message || "",
      icon: "/static/icons/agora-icon.svg",
    });
    notification.onclick = () => {
      window.location.href = item.url || browserNotificationsOpenUrl;
    };
  };

  const pollBrowserNotifications = async () => {
    if (!browserNotificationsFeedUrl || Notification.permission !== "granted") {
      return;
    }
    const url = new URL(browserNotificationsFeedUrl, window.location.origin);
    const since = getBrowserNotificationCursor();
    if (since) {
      url.searchParams.set("since", since);
    }
    try {
      const response = await fetch(url.toString(), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      const notifications = Array.isArray(payload.notifications) ? payload.notifications : [];
      if (!notifications.length) {
        return;
      }
      for (const item of notifications) {
        await showBrowserNotification(item);
      }
      const latestCreatedAt = notifications[notifications.length - 1]?.created_at;
      if (latestCreatedAt) {
        setBrowserNotificationCursor(latestCreatedAt);
      }
    } catch (_error) {
      // Polling failures should not break the rest of the app.
    }
  };

  const stopBrowserNotificationPolling = () => {
    if (browserNotificationTimer) {
      window.clearInterval(browserNotificationTimer);
      browserNotificationTimer = null;
    }
  };

  const startBrowserNotificationPolling = () => {
    if (!browserNotificationsRuntimeEnabled || !browserNotificationsFeedUrl || !("Notification" in window)) {
      return;
    }
    if (Notification.permission !== "granted") {
      return;
    }
    stopBrowserNotificationPolling();
    if (!getBrowserNotificationCursor()) {
      setBrowserNotificationCursor(new Date().toISOString());
    }
    pollBrowserNotifications();
    browserNotificationTimer = window.setInterval(pollBrowserNotifications, 30000);
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

  const hideMentionDropdown = (controller) => {
    if (!controller?.dropdown) {
      return;
    }
    controller.dropdown.classList.add("hidden");
    controller.dropdown.replaceChildren();
    controller.items = [];
    controller.activeIndex = -1;
    controller.currentRange = null;
  };

  const insertMentionAtCursor = (textarea, mentionRange, handle) => {
    const before = textarea.value.slice(0, mentionRange.start);
    const after = textarea.value.slice(mentionRange.end);
    textarea.value = `${before}@${handle} ${after}`;
    const nextCursor = before.length + handle.length + 2;
    setTextareaSelection(textarea, nextCursor, nextCursor);
  };

  const attachMentionAutocomplete = (textarea) => {
    if (!textarea?.dataset.mentionsUrl || textarea.dataset.mentionsMounted === "true") {
      return;
    }
    textarea.dataset.mentionsMounted = "true";
    const dropdown = document.createElement("div");
    dropdown.className = "hidden mt-2 overflow-hidden rounded-g border border-gray-200 bg-white shadow-glow";
    textarea.insertAdjacentElement("afterend", dropdown);
    const controller = {
      dropdown,
      items: [],
      activeIndex: -1,
      currentRange: null,
      abortController: null,
    };

    const updateActiveItem = (nextIndex) => {
      if (!controller.items.length) {
        controller.activeIndex = -1;
        return;
      }
      controller.activeIndex = Math.max(0, Math.min(nextIndex, controller.items.length - 1));
      Array.from(dropdown.children).forEach((node, index) => {
        node.classList.toggle("bg-opal-light", index === controller.activeIndex);
        node.classList.toggle("text-opal", index === controller.activeIndex);
      });
    };

    const renderItems = (results) => {
      controller.items = results;
      controller.activeIndex = results.length ? 0 : -1;
      dropdown.replaceChildren();
      if (!results.length) {
        hideMentionDropdown(controller);
        return;
      }
      results.forEach((item, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm ${index === 0 ? "bg-opal-light text-opal" : "text-gray-700 hover:bg-gray-50"}`;
        button.innerHTML = `<span class="font-medium">@${item.handle}</span><span class="truncate text-xs text-gray-500">${item.display_name || item.handle}</span>`;
        button.addEventListener("click", () => {
          if (!controller.currentRange) {
            return;
          }
          insertMentionAtCursor(textarea, controller.currentRange, item.handle);
          hideMentionDropdown(controller);
          announce(`Mentioned @${item.handle}`);
        });
        dropdown.appendChild(button);
      });
      dropdown.classList.remove("hidden");
    };

    const refreshSuggestions = async () => {
      const cursor = textarea.selectionStart ?? textarea.value.length;
      const beforeCursor = textarea.value.slice(0, cursor);
      const match = beforeCursor.match(/(?:^|\s)@([a-z0-9_]{1,30})$/i);
      if (!match) {
        hideMentionDropdown(controller);
        return;
      }
      const query = match[1];
      controller.currentRange = {
        start: cursor - query.length - 1,
        end: cursor,
      };
      const url = new URL(textarea.dataset.mentionsUrl, window.location.origin);
      url.searchParams.set("q", query);
      if (textarea.dataset.communitySlug) {
        url.searchParams.set("community_slug", textarea.dataset.communitySlug);
      }
      controller.abortController?.abort();
      controller.abortController = new AbortController();
      try {
        const response = await fetch(url.toString(), {
          signal: controller.abortController.signal,
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (!response.ok) {
          hideMentionDropdown(controller);
          return;
        }
        const payload = await response.json();
        renderItems(Array.isArray(payload.results) ? payload.results : []);
      } catch (_error) {
        hideMentionDropdown(controller);
      }
    };

    textarea.addEventListener("input", refreshSuggestions);
    textarea.addEventListener("blur", () => {
      window.setTimeout(() => hideMentionDropdown(controller), 100);
    });
    textarea.addEventListener("keydown", (event) => {
      if (dropdown.classList.contains("hidden") || !controller.items.length) {
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        updateActiveItem(controller.activeIndex + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        updateActiveItem(controller.activeIndex - 1);
      } else if (event.key === "Enter" || event.key === "Tab") {
        event.preventDefault();
        const item = controller.items[controller.activeIndex];
        if (item && controller.currentRange) {
          insertMentionAtCursor(textarea, controller.currentRange, item.handle);
          hideMentionDropdown(controller);
          announce(`Mentioned @${item.handle}`);
        }
      } else if (event.key === "Escape") {
        hideMentionDropdown(controller);
      }
    });
  };

  const attachMarkdownPreview = (textarea) => {
    if (!textarea || textarea.dataset.previewMounted === "true") {
      return;
    }
    textarea.dataset.previewMounted = "true";
    textarea.addEventListener("input", () => requestMarkdownPreview(textarea));
    if (textarea.value.trim()) {
      requestMarkdownPreview(textarea);
    }
  };

  const initializeRichTextareas = (root = document) => {
    root.querySelectorAll?.("textarea[data-rich-markdown], textarea[data-markdown-preview-target]").forEach((textarea) => {
      attachMarkdownToolbar(textarea);
    });
    root.querySelectorAll?.("textarea[data-markdown-preview-target]").forEach((textarea) => {
      attachMarkdownPreview(textarea);
    });
    root.querySelectorAll?.("textarea[data-mentions-url]").forEach((textarea) => {
      attachMentionAutocomplete(textarea);
    });
  };

  initializeRichTextareas(document);

  const dismissInstallPrompt = () => {
    installPromptNode?.classList.add("hidden");
    try {
      window.localStorage.setItem(installPromptSeenKey, "1");
    } catch (_error) {
      // Ignore storage failures and still hide the prompt for this page view.
    }
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
    try {
      if (window.localStorage.getItem(installPromptSeenKey) === "1") {
        return;
      }
      window.localStorage.setItem(installPromptSeenKey, "1");
    } catch (_error) {
      // If storage is unavailable, we still show the prompt for this page view.
    }
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
        if (button.dataset.shareRecordUrl) {
          recordShare(button.dataset.shareRecordUrl);
        }
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
      if (button.hasAttribute("data-share-sheet-open")) {
        return;
      }
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

  const shareSheet = document.getElementById("share-sheet");
  const shareSheetTitle = document.getElementById("share-sheet-title");
  const shareSheetCopy = document.getElementById("share-sheet-copy");
  const shareSheetNative = document.getElementById("share-sheet-native");
  const shareSheetWhatsapp = document.getElementById("share-sheet-whatsapp");
  const shareSheetTelegram = document.getElementById("share-sheet-telegram");
  const shareSheetEmail = document.getElementById("share-sheet-email");
  const shareSheetX = document.getElementById("share-sheet-x");

  const openShareSheet = (payload) => {
    if (!shareSheet) {
      return;
    }
    const title = payload.title || document.title;
    const text = payload.text || "";
    const url = payload.url || window.location.href;
    const recordUrl = payload.recordUrl || "";
    if (shareSheetTitle) {
      shareSheetTitle.textContent = title;
    }
    if (shareSheetCopy) {
      shareSheetCopy.dataset.copyText = url;
      shareSheetCopy.dataset.copyLabel = "Invite link copied";
      shareSheetCopy.dataset.shareRecordUrl = recordUrl;
    }
    if (shareSheetNative) {
      shareSheetNative.dataset.shareTitle = title;
      shareSheetNative.dataset.shareText = text;
      shareSheetNative.dataset.shareUrl = url;
      shareSheetNative.dataset.shareRecordUrl = recordUrl;
    }
    if (shareSheetWhatsapp) {
      shareSheetWhatsapp.href = `https://wa.me/?text=${encodeURIComponent(`${text} ${url}`.trim())}`;
      shareSheetWhatsapp.dataset.shareRecordUrl = recordUrl;
    }
    if (shareSheetTelegram) {
      shareSheetTelegram.href = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
      shareSheetTelegram.dataset.shareRecordUrl = recordUrl;
    }
    if (shareSheetEmail) {
      shareSheetEmail.href = `mailto:?subject=${encodeURIComponent("Join me on Agora")}&body=${encodeURIComponent(`${text}\n\n${url}`)}`;
      shareSheetEmail.dataset.shareRecordUrl = recordUrl;
    }
    if (shareSheetX) {
      shareSheetX.href = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
      shareSheetX.dataset.shareRecordUrl = recordUrl;
    }
    shareSheet.classList.remove("hidden");
    shareSheet.setAttribute("aria-hidden", "false");
  };

  const closeShareSheet = () => {
    if (!shareSheet) {
      return;
    }
    shareSheet.classList.add("hidden");
    shareSheet.setAttribute("aria-hidden", "true");
  };

  document.querySelectorAll("[data-share-sheet-open]").forEach((button) => {
    button.addEventListener("click", () => {
      openShareSheet({
        title: button.dataset.shareTitle,
        text: button.dataset.shareText,
        url: button.dataset.shareUrl,
        recordUrl: button.dataset.shareRecordUrl,
      });
    });
  });

  document.querySelectorAll("[data-share-sheet-close]").forEach((button) => {
    button.addEventListener("click", closeShareSheet);
  });

  pushPreferenceCheckbox?.addEventListener("change", async () => {
    if (!pushPreferenceCheckbox.checked) {
      browserNotificationsRuntimeEnabled = false;
      stopBrowserNotificationPolling();
      return;
    }
    if (!("Notification" in window)) {
      pushPreferenceCheckbox.checked = false;
      announce("Browser notifications are not supported here");
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      pushPreferenceCheckbox.checked = false;
      browserNotificationsRuntimeEnabled = false;
      announce("Allow browser notifications to turn this on");
      return;
    }
    browserNotificationsRuntimeEnabled = true;
    setBrowserNotificationCursor(new Date().toISOString());
    startBrowserNotificationPolling();
    announce("Browser notifications enabled");
  });

  startBrowserNotificationPolling();

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
