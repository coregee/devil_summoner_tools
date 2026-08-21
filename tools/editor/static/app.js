const state = {
  rows: [],
  selected: null,
  evaluation: null,
  queryTimer: null,
  evaluationTimer: null,
  evaluationRequest: null,
};

const $ = (id) => document.getElementById(id);
const elements = {
  corpusState: $("corpus-state"),
  search: $("search"),
  resultCount: $("result-count"),
  resultNote: $("result-note"),
  entryList: $("entry-list"),
  emptyState: $("empty-state"),
  editorContent: $("editor-content"),
  assetPath: $("asset-path"),
  recordName: $("record-name"),
  reviewState: $("review-state"),
  consumerCount: $("consumer-count"),
  reference: $("reference"),
  translation: $("translation"),
  characterCount: $("character-count"),
  saveState: $("save-state"),
  discard: $("discard"),
  save: $("save"),
  surfaceSelect: $("surface-select"),
  previewImage: $("preview-image"),
  previewEmpty: $("preview-empty"),
  fontFact: $("font-fact"),
  geometryFact: $("geometry-fact"),
  fidelityFact: $("fidelity-fact"),
  validationSummary: $("validation-summary"),
  diagnostics: $("diagnostics"),
  consumerList: $("consumer-list"),
  toast: $("toast"),
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try { data = await response.json(); } catch { data = {}; }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function showToast(message, error = false) {
  elements.toast.textContent = message;
  elements.toast.className = `toast show${error ? " error" : ""}`;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => { elements.toast.className = "toast"; }, 2600);
}

function excerpt(value, length = 72) {
  const single = value.replaceAll("\n", " ").replaceAll("{n}", " ↵ ").trim();
  return single.length > length ? `${single.slice(0, length - 1)}…` : single;
}

async function loadEntries() {
  const query = encodeURIComponent(elements.search.value.trim());
  try {
    const data = await requestJson(`/api/entries?q=${query}&limit=300`);
    state.rows = data.entries;
    elements.corpusState.textContent = "Corpus ready";
    elements.resultCount.textContent = `${data.total.toLocaleString()} fields`;
    elements.resultNote.textContent = data.limited ? "showing first 300" : "";
    renderEntries();
  } catch (error) {
    elements.corpusState.textContent = "Corpus unavailable";
    showToast(error.message, true);
  }
}

function renderEntries() {
  const fragment = document.createDocumentFragment();
  for (const row of state.rows) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `entry-button${state.selected?.id === row.id ? " active" : ""}`;
    button.dataset.id = row.id;
    const title = document.createElement("strong");
    title.textContent = excerpt(row.translation) || "Untranslated";
    const source = document.createElement("span");
    source.textContent = excerpt(row.reference);
    const context = document.createElement("small");
    context.textContent = `${row.asset} · ${row.entry}.${row.field}`;
    button.append(title, source, context);
    button.addEventListener("click", () => selectEntry(row.id));
    fragment.append(button);
  }
  elements.entryList.replaceChildren(fragment);
}

async function selectEntry(id) {
  try {
    state.selected = await requestJson(`/api/entry?id=${encodeURIComponent(id)}`);
    state.evaluation = null;
    elements.emptyState.hidden = true;
    elements.editorContent.hidden = false;
    elements.assetPath.textContent = state.selected.asset;
    elements.recordName.textContent = `${state.selected.entry}.${state.selected.field}`;
    elements.reviewState.textContent = state.selected.reviewed ? "Reviewed" : "Needs review";
    elements.consumerCount.textContent = `${state.selected.consumers.length} consumer${state.selected.consumers.length === 1 ? "" : "s"}`;
    elements.reference.value = state.selected.reference;
    elements.translation.value = state.selected.translation;
    elements.consumerList.replaceChildren(...state.selected.consumers.map((consumer) => {
      const item = document.createElement("li");
      item.textContent = `${consumer.record_id}${consumer.surface ? ` · ${consumer.surface}` : " · unmapped"}`;
      return item;
    }));
    renderEntries();
    updateDirtyState();
    await evaluateDraft(true);
  } catch (error) {
    showToast(error.message, true);
  }
}

function isDirty() {
  return Boolean(state.selected && elements.translation.value !== state.selected.translation);
}

function updateDirtyState() {
  const dirty = isDirty();
  elements.characterCount.textContent = `${elements.translation.value.length} characters`;
  elements.discard.disabled = !dirty;
  elements.save.disabled = !dirty || !state.evaluation?.valid;
  elements.saveState.textContent = dirty ? "Unsaved draft" : "No unsaved changes";
}

function scheduleEvaluation() {
  updateDirtyState();
  window.clearTimeout(state.evaluationTimer);
  state.evaluationTimer = window.setTimeout(() => evaluateDraft(false), 180);
}

async function evaluateDraft(immediate) {
  if (!state.selected) return;
  if (!immediate) elements.validationSummary.textContent = "Checking draft…";
  state.evaluationRequest?.abort();
  state.evaluationRequest = new AbortController();
  try {
    const result = await requestJson("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: state.selected.id, translation: elements.translation.value }),
      signal: state.evaluationRequest.signal,
    });
    state.evaluation = result;
    renderEvaluation();
    updateDirtyState();
  } catch (error) {
    if (error.name !== "AbortError") showToast(error.message, true);
  }
}

function renderEvaluation() {
  const evaluation = state.evaluation;
  const errors = evaluation.diagnostics.filter((row) => row.severity === "error").length;
  const warnings = evaluation.diagnostics.filter((row) => row.severity === "warning").length;
  const unknown = evaluation.diagnostics.filter((row) => row.severity === "unknown").length;
  elements.validationSummary.className = `validation-summary ${errors ? "error" : "valid"}`;
  elements.validationSummary.textContent = errors
    ? `${errors} blocking error${errors === 1 ? "" : "s"}`
    : warnings || unknown
      ? `Valid · ${warnings} warning${warnings === 1 ? "" : "s"} · ${unknown} unknown`
      : "All known constraints pass";

  const diagnostics = evaluation.diagnostics.length ? evaluation.diagnostics : [{
    severity: "valid", message: "All known constraints pass for every mapped consumer.", surface: null,
  }];
  elements.diagnostics.replaceChildren(...diagnostics.map((row) => {
    const card = document.createElement("article");
    card.className = `diagnostic ${row.severity}`;
    const label = document.createElement("strong");
    label.textContent = row.severity;
    const message = document.createElement("p");
    message.textContent = `${row.surface ? `${row.surface} · ` : ""}${row.message}`;
    card.append(label, message);
    return card;
  }));

  const selectedSurface = elements.surfaceSelect.value;
  elements.surfaceSelect.replaceChildren(...evaluation.surfaces.map((surface) => {
    const option = document.createElement("option");
    option.value = surface.name;
    option.textContent = surface.name;
    return option;
  }));
  if (evaluation.surfaces.some((surface) => surface.name === selectedSurface)) {
    elements.surfaceSelect.value = selectedSurface;
  }
  renderSurface();
}

function renderSurface() {
  const surface = state.evaluation?.surfaces.find((row) => row.name === elements.surfaceSelect.value)
    || state.evaluation?.surfaces[0];
  const preview = state.evaluation?.preview;
  if (!surface) {
    elements.previewImage.hidden = true;
    elements.previewEmpty.hidden = false;
    elements.fontFact.textContent = "Font —";
    elements.geometryFact.textContent = "Geometry unknown";
    elements.fidelityFact.textContent = "Fidelity —";
    return;
  }
  elements.previewTitle = surface.name;
  elements.fontFact.textContent = `Font ${surface.font?.toUpperCase() || "unknown"}`;
  const width = surface.width.value ? `${surface.width.value} ${surface.width.unit === "pixels" ? "px" : "cells"}` : "unknown width";
  elements.geometryFact.textContent = `${surface.rows || "?"} rows · ${width}`;
  elements.fidelityFact.textContent = surface.exact ? "Exact wrapping" : "Measured surface";
  if (preview && preview.surface === surface.name) {
    elements.previewImage.src = preview.data_url;
    elements.previewImage.hidden = false;
    elements.previewEmpty.hidden = true;
  } else {
    elements.previewImage.hidden = true;
    elements.previewEmpty.hidden = false;
  }
}

async function saveTranslation() {
  if (!state.selected || !isDirty() || !state.evaluation?.valid) return;
  elements.save.disabled = true;
  elements.saveState.textContent = "Saving…";
  try {
    const data = await requestJson("/api/entry", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: state.selected.id,
        translation: elements.translation.value,
        base_hash: state.selected.file_hash,
      }),
    });
    state.selected = data.entry;
    state.evaluation = data.evaluation;
    const row = state.rows.find((item) => item.id === state.selected.id);
    if (row) row.translation = state.selected.translation;
    renderEntries();
    renderEvaluation();
    updateDirtyState();
    showToast("Translation saved.");
  } catch (error) {
    showToast(error.message, true);
    updateDirtyState();
  }
}

elements.search.addEventListener("input", () => {
  window.clearTimeout(state.queryTimer);
  state.queryTimer = window.setTimeout(loadEntries, 180);
});
elements.translation.addEventListener("input", scheduleEvaluation);
elements.surfaceSelect.addEventListener("change", renderSurface);
elements.discard.addEventListener("click", () => {
  if (!state.selected) return;
  elements.translation.value = state.selected.translation;
  evaluateDraft(true);
});
elements.save.addEventListener("click", saveTranslation);
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    saveTranslation();
  }
});

loadEntries();

