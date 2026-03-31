(() => {
  const statusNode = document.getElementById("shortcut-status");
  let activeCardIndex = -1;

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
})();
