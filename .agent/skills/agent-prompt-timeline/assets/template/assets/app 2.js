/**
 * Runs the Prompt Timeline browser UI.
 * It merges append-only prompt and summary events, then renders searchable
 * timeline cards and a detail panel without requiring a build step.
 */
(function () {
  const state = {
    events: Array.isArray(window.PROMPT_TIMELINE_EVENTS) ? window.PROMPT_TIMELINE_EVENTS : [],
    filter: "all",
    query: "",
    selectedId: "",
  };

  const nodes = {
    searchInput: document.querySelector("#searchInput"),
    fileInput: document.querySelector("#fileInput"),
    filters: Array.from(document.querySelectorAll("[data-filter]")),
    timelineList: document.querySelector("#timelineList"),
    resultCount: document.querySelector("#resultCount"),
    statTotal: document.querySelector("#statTotal"),
    statSummarized: document.querySelector("#statSummarized"),
    statLatest: document.querySelector("#statLatest"),
    detailStatus: document.querySelector("#detailStatus"),
    detailContent: document.querySelector("#detailContent"),
  };

  function normalizeEvents(events) {
    const prompts = [];
    const byId = new Map();

    events
      .filter((event) => event && event.kind === "prompt")
      .forEach((event) => {
        const normalized = {
          id: String(event.id || ""),
          timestamp: event.timestamp || "",
          timestampJst: event.timestamp_jst || event.timestamp || "",
          source: event.source || "agent",
          prompt: event.prompt_original || event.prompt_preview || "",
          promptPreview: event.prompt_preview || event.prompt_original || "",
          summary: event.summary || "",
          actions: Array.isArray(event.actions) ? event.actions.slice() : [],
          tags: Array.isArray(event.tags) ? event.tags.slice() : [],
          meta: event.meta || {},
        };
        if (normalized.id) {
          prompts.push(normalized);
          byId.set(normalized.id, normalized);
        }
      });

    events
      .filter((event) => event && event.kind === "summary" && event.parent_id)
      .forEach((event) => {
        const target = byId.get(String(event.parent_id));
        if (!target) return;
        if (event.summary) target.summary = event.summary;
        if (Array.isArray(event.actions)) target.actions.push(...event.actions);
        if (Array.isArray(event.tags)) target.tags.push(...event.tags);
      });

    return prompts.sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)));
  }

  function formatDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("ja-JP", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  function clip(value, length) {
    const normalized = String(value || "").replace(/\s+/g, " ").trim();
    if (normalized.length <= length) return normalized;
    return `${normalized.slice(0, length - 1)}…`;
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function getFilteredPrompts() {
    const query = state.query.trim().toLowerCase();
    return normalizeEvents(state.events).filter((item) => {
      const hasSummary = Boolean(item.summary || item.actions.length);
      if (state.filter === "summarized" && !hasSummary) return false;
      if (state.filter === "open" && hasSummary) return false;
      if (!query) return true;
      const haystack = [item.prompt, item.summary, item.actions.join(" "), item.source, item.tags.join(" ")]
        .join("\n")
        .toLowerCase();
      return haystack.includes(query);
    });
  }

  function renderStats(prompts) {
    const allPrompts = normalizeEvents(state.events);
    const summarized = allPrompts.filter((item) => item.summary || item.actions.length);
    nodes.statTotal.textContent = String(allPrompts.length);
    nodes.statSummarized.textContent = String(summarized.length);
    nodes.statLatest.textContent = allPrompts[0] ? formatDate(allPrompts[0].timestamp) : "-";
    nodes.resultCount.textContent = `${prompts.length}件`;
  }

  function renderTimeline(prompts) {
    if (!prompts.length) {
      nodes.timelineList.innerHTML = '<li class="empty-state">条件に合う記録がありません。</li>';
      return;
    }

    if (!state.selectedId || !prompts.some((item) => item.id === state.selectedId)) {
      state.selectedId = prompts[0].id;
    }

    nodes.timelineList.innerHTML = prompts
      .map((item) => {
        const hasSummary = Boolean(item.summary || item.actions.length);
        const title = clip(item.promptPreview || item.prompt, 92) || "Untitled prompt";
        const excerpt = clip(item.summary || item.promptPreview || item.prompt, 150);
        return `
          <li class="timeline-item">
            <button class="timeline-button ${item.id === state.selectedId ? "is-active" : ""}" type="button" data-id="${escapeHtml(item.id)}">
              <span class="timeline-meta">
                <span>${escapeHtml(formatDate(item.timestamp))}</span>
                <span>${escapeHtml(item.source)}</span>
                <span class="badge ${hasSummary ? "summary" : "open"}">${hasSummary ? "要約あり" : "要約待ち"}</span>
              </span>
              <span class="timeline-title">${escapeHtml(title)}</span>
              <span class="timeline-excerpt">${escapeHtml(excerpt)}</span>
            </button>
          </li>
        `;
      })
      .join("");

    nodes.timelineList.querySelectorAll("[data-id]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedId = button.getAttribute("data-id") || "";
        render();
      });
    });
  }

  function renderDetail(prompts) {
    const item = prompts.find((entry) => entry.id === state.selectedId);
    if (!item) {
      nodes.detailStatus.textContent = "未選択";
      nodes.detailContent.innerHTML = '<p class="empty-state">左のタイムラインから記録を選んでください。</p>';
      return;
    }

    const hasSummary = Boolean(item.summary || item.actions.length);
    nodes.detailStatus.textContent = hasSummary ? "要約あり" : "要約待ち";
    nodes.detailContent.innerHTML = `
      <div class="detail-block">
        <h3>日時</h3>
        <p class="detail-text">${escapeHtml(item.timestampJst || item.timestamp)}</p>
      </div>
      <div class="detail-block">
        <h3>原文プロンプト</h3>
        <p class="prompt-text">${escapeHtml(item.prompt)}</p>
      </div>
      <div class="detail-block">
        <h3>作業要約</h3>
        <p class="detail-text">${escapeHtml(item.summary || "まだ要約がありません。作業後に agent-prompt-timeline skill で追記します。")}</p>
      </div>
      <div class="detail-block">
        <h3>アクション / 検証</h3>
        ${
          item.actions.length
            ? `<ul class="actions-list">${item.actions.map((action) => `<li>${escapeHtml(action)}</li>`).join("")}</ul>`
            : '<p class="detail-text">未記録</p>'
        }
      </div>
      <div class="detail-block">
        <h3>メタ情報</h3>
        <p class="prompt-text">${escapeHtml(JSON.stringify({ id: item.id, source: item.source, tags: item.tags, meta: item.meta }, null, 2))}</p>
      </div>
    `;
  }

  function render() {
    const prompts = getFilteredPrompts();
    renderStats(prompts);
    renderTimeline(prompts);
    renderDetail(prompts);
  }

  function parseJsonl(text) {
    const trimmed = text.trim();
    if (!trimmed) return [];
    if (trimmed.startsWith("[")) return JSON.parse(trimmed);
    return trimmed
      .split(/\r?\n/)
      .filter(Boolean)
      .map((line) => JSON.parse(line));
  }

  nodes.searchInput.addEventListener("input", (event) => {
    state.query = event.target.value;
    render();
  });

  nodes.filters.forEach((button) => {
    button.addEventListener("click", () => {
      state.filter = button.getAttribute("data-filter") || "all";
      nodes.filters.forEach((item) => item.classList.toggle("is-active", item === button));
      render();
    });
  });

  nodes.fileInput.addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    const text = await file.text();
    state.events = parseJsonl(text);
    state.selectedId = "";
    render();
  });

  render();
})();
