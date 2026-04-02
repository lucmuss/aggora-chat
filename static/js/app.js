(() => {
  const statusNode = document.getElementById("shortcut-status");
  const installPromptNode = document.getElementById("pwa-install-prompt");
  let activeCardIndex = -1;
  let markdownPreviewTimer;
  let deferredInstallPrompt;

  const cards = () => Array.from(document.querySelectorAll("[data-post-card]"));
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

  document.addEventListener("keydown", (event) => {
    const tagName = document.activeElement?.tagName;
    const isTyping = tagName === "INPUT" || tagName === "TEXTAREA" || document.activeElement?.isContentEditable;
    if (event.key === "/" && !isTyping) {
      event.preventDefault();
      document.querySelector("[data-shortcut-search]")?.focus();
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
})();
