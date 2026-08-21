const state = {
  rows: [],
  selected: null,
  evaluation: null,
  queryTimer: null,
  evaluationTimer: null,
  evaluationRequest: null,
  mode: "translations",
  fonts: [],
  font: null,
  fontPlan: null,
  selectedGlyph: null,
  languages: [],
  language: null,
  editingLanguage: false,
  fontQueryTimer: null,
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
  font8Alphabet: $("font8-alphabet"),
  font8AlphabetField: $("font8-alphabet-field"),
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
  translationsTab: $("translations-tab"),
  fontsTab: $("fonts-tab"),
  translationsWorkspace: $("translations-workspace"),
  fontsWorkspace: $("fonts-workspace"),
  languageSelect: $("language-select"),
  editLanguage: $("edit-language"),
  newLanguage: $("new-language"),
  languageDialog: $("language-dialog"),
  languageForm: $("language-form"),
  languageDialogTitle: $("language-dialog-title"),
  languageLabel: $("language-label"),
  languageId: $("language-id"),
  languageLocale: $("language-locale"),
  languageCharacters: $("language-characters"),
  closeLanguage: $("close-language"),
  cancelLanguage: $("cancel-language"),
  saveLanguage: $("save-language"),
  fontList: $("font-list"),
  fontEmptyState: $("font-empty-state"),
  fontContent: $("font-content"),
  fontDisc: $("font-disc"),
  fontName: $("font-name"),
  fontDescription: $("font-description"),
  fontCell: $("font-cell"),
  fontSource: $("font-source"),
  importFont: $("import-font"),
  fontFile: $("font-file"),
  planFontUpdate: $("plan-font-update"),
  fontUpdateEmpty: $("font-update-empty"),
  fontUpdateResult: $("font-update-result"),
  fontUpdateStats: $("font-update-stats"),
  fontUpdateWarnings: $("font-update-warnings"),
  fontUpdateChanges: $("font-update-changes"),
  fontUpdateSummary: $("font-update-summary"),
  applyFontUpdate: $("apply-font-update"),
  originalAtlas: $("original-atlas"),
  modifiedAtlas: $("modified-atlas"),
  glyphCount: $("glyph-count"),
  glyphFilter: $("glyph-filter"),
  glyphPageSummary: $("glyph-page-summary"),
  previousGlyphPage: $("previous-glyph-page"),
  nextGlyphPage: $("next-glyph-page"),
  glyphGrid: $("glyph-grid"),
  glyphEmpty: $("glyph-empty"),
  glyphContent: $("glyph-content"),
  selectedOriginalImage: $("selected-original-image"),
  selectedGlyphPair: $("selected-glyph-pair"),
  selectedGlyphDivider: $("selected-glyph-divider"),
  selectedCurrentGlyph: $("selected-current-glyph"),
  selectedGlyphImage: $("selected-glyph-image"),
  selectedGlyphCode: $("selected-glyph-code"),
  selectedGlyphOriginal: $("selected-glyph-original"),
  selectedGlyphMapping: $("selected-glyph-mapping"),
  sourceValue: $("source-value"),
  sourceValueHelp: $("source-value-help"),
  saveSourceValue: $("save-source-value"),
  replacementEditor: $("replacement-editor"),
  glyphReplacement: $("glyph-replacement"),
  glyphUsage: $("glyph-usage"),
  saveGlyph: $("save-glyph"),
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

function glyphValueLabel(value) {
  if (value === " ") return "Blank";
  return value || "?";
}

function glyphMappingLabel(slot) {
  const source = glyphValueLabel(slot.source_value);
  if (slot.replacement === null || slot.replacement === slot.source_value) {
    return source;
  }
  return `${source} / ${glyphValueLabel(slot.replacement)}`;
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
    elements.font8Alphabet.value = state.selected.font8_alphabet;
    elements.font8AlphabetField.hidden = !state.selected.font8_configurable;
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
  return Boolean(state.selected && (
    elements.translation.value !== state.selected.translation
    || elements.font8Alphabet.value !== state.selected.font8_alphabet
  ));
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
      body: JSON.stringify({
        id: state.selected.id,
        translation: elements.translation.value,
        font8_alphabet: elements.font8Alphabet.value,
      }),
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
        font8_alphabet: elements.font8Alphabet.value,
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

function switchWorkspace(mode) {
  state.mode = mode;
  const translations = mode === "translations";
  elements.translationsWorkspace.hidden = !translations;
  elements.fontsWorkspace.hidden = translations;
  elements.translationsTab.classList.toggle("active", translations);
  elements.fontsTab.classList.toggle("active", !translations);
  if (!translations && !state.languages.length) loadLanguages();
}

async function loadLanguages(selectedId = state.language?.id || "en") {
  try {
    const data = await requestJson("/api/languages");
    state.languages = data.languages;
    elements.languageSelect.replaceChildren(...state.languages.map((language) => {
      const option = document.createElement("option");
      option.value = language.id;
      option.textContent = language.built_in
        ? `${language.label} · built in`
        : language.label;
      return option;
    }));
    const selected = state.languages.find((row) => row.id === selectedId)
      || state.languages[0];
    elements.languageSelect.value = selected.id;
    await selectLanguage(selected.id);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function selectLanguage(id) {
  try {
    state.language = await requestJson(`/api/language?id=${encodeURIComponent(id)}`);
    state.font = null;
    state.fontPlan = null;
    state.selectedGlyph = null;
    elements.languageSelect.value = id;
    elements.editLanguage.disabled = state.language.built_in;
    elements.glyphFilter.value = "";
    elements.fontContent.hidden = true;
    elements.fontEmptyState.hidden = false;
    await loadFonts();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function loadFonts() {
  if (!state.language) return;
  try {
    const data = await requestJson(
      `/api/fonts?language=${encodeURIComponent(state.language.id)}`,
    );
    state.fonts = data.fonts;
    renderFontList();
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderFontList() {
  elements.fontList.replaceChildren(...state.fonts.map((font) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `font-button${state.font?.id === font.id ? " active" : ""}`;
    const copy = document.createElement("span");
    const name = document.createElement("strong");
    name.textContent = font.name;
    const detail = document.createElement("span");
    detail.textContent = `${font.platform === "psp" ? "PSP" : "Saturn"} · ${font.known_slots.toLocaleString()}/${font.physical_slots.toLocaleString()} mapped`;
    copy.append(name, detail);
    const count = document.createElement("small");
    count.textContent = font.customized
      ? "custom"
      : font.unknown_slots
        ? `${font.unknown_slots.toLocaleString()} unknown`
        : font.suggested_slots
          ? `${font.suggested_slots.toLocaleString()} to review`
          : "complete";
    button.append(copy, count);
    button.addEventListener("click", () => {
      elements.glyphFilter.value = "";
      selectFont(font.id);
    });
    return button;
  }));
}

async function selectFont(id, offset = 0) {
  try {
    const query = new URLSearchParams({
      id,
      language: state.language.id,
      offset: String(offset),
      limit: "200",
      q: elements.glyphFilter.value.trim(),
    });
    state.font = await requestJson(
      `/api/font?${query}`,
    );
    state.fontPlan = null;
    state.selectedGlyph = null;
    elements.fontEmptyState.hidden = true;
    elements.fontContent.hidden = false;
    elements.fontDisc.textContent = state.font.context || `${state.font.disc} disc font`;
    elements.fontName.textContent = state.font.name;
    elements.fontDescription.textContent = state.font.description || "Game font resource";
    elements.fontCell.textContent = `${state.font.cell.width}×${state.font.cell.height} · ${state.font.cell.bpp}bpp`;
    elements.fontSource.textContent = state.font.source ? `Typeface · ${state.font.source}` : "Source-preserved font";
    elements.importFont.hidden = !state.font.can_import;
    elements.importFont.textContent = state.font.customized
      ? "Change replacement typeface…"
      : state.font.source
        ? "Change replacement typeface…"
        : "Choose replacement typeface…";
    elements.fontUpdateEmpty.hidden = false;
    elements.fontUpdateResult.hidden = true;
    elements.planFontUpdate.disabled = !state.font.can_import;
    elements.planFontUpdate.textContent = state.font.can_import
      ? "Audit font"
      : "No replacement profile";
    elements.originalAtlas.src = state.font.atlases.original || "";
    elements.originalAtlas.hidden = !state.font.atlases.original;
    elements.modifiedAtlas.src = state.font.atlases.modified || "";
    elements.modifiedAtlas.hidden = !state.font.atlases.modified;
    const counts = state.font.slot_counts;
    elements.glyphCount.textContent = `${state.font.slot_page.physical.toLocaleString()} physical slots · ${counts.defined.toLocaleString()} defined`;
    const start = state.font.slot_page.total ? state.font.slot_page.offset + 1 : 0;
    const end = Math.min(
      state.font.slot_page.offset + state.font.slots.length,
      state.font.slot_page.total,
    );
    elements.glyphPageSummary.textContent = `${start.toLocaleString()}–${end.toLocaleString()} of ${state.font.slot_page.total.toLocaleString()} shown · ${counts.suggested} suggested · ${counts.unknown} unknown · ${counts.replaceable} replaceable`;
    elements.previousGlyphPage.disabled = state.font.slot_page.offset === 0;
    elements.nextGlyphPage.disabled = end >= state.font.slot_page.total;
    elements.glyphEmpty.hidden = false;
    elements.glyphContent.hidden = true;
    renderFontList();
    renderGlyphs();
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderFontPlan() {
  const plan = state.fontPlan;
  if (!plan) return;
  elements.fontUpdateEmpty.hidden = true;
  elements.fontUpdateResult.hidden = false;
  const audit = plan.audit;
  const facts = [
    `${audit.fields.toLocaleString()} corpus fields`,
    `${audit.required_glyphs.toLocaleString()} required glyphs`,
    `${audit.required_uses.toLocaleString()} translated uses`,
    `${audit.preferred_glyphs.toLocaleString()} original glyphs`,
    `${audit.protected_slots.toLocaleString()} protected slots`,
    `${audit.replacement_slots.toLocaleString()} replacement slots`,
  ];
  elements.fontUpdateStats.replaceChildren(...facts.map((value) => {
    const fact = document.createElement("span");
    fact.className = "pill";
    fact.textContent = value;
    return fact;
  }));
  elements.fontUpdateWarnings.replaceChildren(...plan.warnings.map((value) => {
    const warning = document.createElement("p");
    warning.className = "font-update-warning";
    warning.textContent = value;
    return warning;
  }));
  const displacedCodes = new Set(plan.required_displaced.map((row) => row.code));
  elements.fontUpdateChanges.replaceChildren(...plan.changes.map((change) => {
    const row = document.createElement("tr");
    row.classList.toggle("required-displaced", displacedCodes.has(change.code));
    for (const value of [
      change.code_label,
      glyphValueLabel(change.source),
      glyphValueLabel(change.before),
      glyphValueLabel(change.after),
      change.original_frequency.toLocaleString(),
      change.required_frequency.toLocaleString(),
    ]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    return row;
  }));
  elements.fontUpdateSummary.textContent = plan.changes.length
    ? `${plan.changes.length.toLocaleString()} slot changes proposed. Rows in amber currently hold a glyph required by the translated corpus.`
    : "The current font already matches the corpus audit; no slot changes are needed.";
  elements.applyFontUpdate.disabled = !plan.can_apply || !plan.changes.length;
}

async function planFontUpdate() {
  if (!state.font || !state.language) return;
  elements.planFontUpdate.disabled = true;
  elements.planFontUpdate.textContent = "Auditing…";
  try {
    const query = new URLSearchParams({
      id: state.font.id,
      language: state.language.id,
    });
    state.fontPlan = await requestJson(`/api/font/update-plan?${query}`);
    renderFontPlan();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    elements.planFontUpdate.disabled = !state.font?.can_import;
    elements.planFontUpdate.textContent = "Audit again";
  }
}

async function applyFontUpdate() {
  if (!state.fontPlan || !state.font || !state.language) return;
  const displaced = state.fontPlan.required_displaced.length;
  if (displaced && !window.confirm(
    `${displaced} required glyphs are in slots this plan will replace. Apply the reviewed plan anyway?`,
  )) return;
  elements.applyFontUpdate.disabled = true;
  elements.applyFontUpdate.textContent = "Updating and rebuilding…";
  try {
    const fontId = state.font.id;
    await requestJson("/api/font/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: fontId,
        language: state.language.id,
        base_hash: state.fontPlan.base_hash,
        confirm_required: displaced > 0,
      }),
    });
    state.language = await requestJson(
      `/api/language?id=${encodeURIComponent(state.language.id)}`,
    );
    await loadFonts();
    await selectFont(fontId);
    showToast(`${state.font.name} updated from the current corpus audit.`);
  } catch (error) {
    showToast(error.message, true);
    elements.applyFontUpdate.disabled = false;
    elements.applyFontUpdate.textContent = "Apply Update Font pipeline";
  }
}

function renderGlyphs() {
  if (!state.font) return;
  elements.glyphGrid.replaceChildren(...state.font.slots.map((slot) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `glyph-card ${slot.source_status}${slot.usage ? " used" : ""}${state.selectedGlyph?.code === slot.code ? " active" : ""}`;
    const pair = document.createElement("div");
    const replaced = slot.replacement !== null;
    pair.className = `glyph-card-pair${replaced ? "" : " single"}`;
    const images = replaced
      ? [
        ["original", slot.original_image],
        ["current", slot.modified_image],
      ]
      : [["original", slot.original_image || slot.modified_image]];
    for (const [side, source] of images) {
      const frame = document.createElement("span");
      frame.className = `glyph-card-image ${side}`;
      if (source) {
        const image = document.createElement("img");
        image.src = source;
        image.alt = "";
        frame.append(image);
      } else {
        frame.textContent = "?";
      }
      pair.append(frame);
    }
    const mapping = document.createElement("strong");
    mapping.className = "glyph-card-mapping";
    mapping.textContent = glyphMappingLabel(slot);
    const code = document.createElement("small");
    code.textContent = `${slot.code_label} · ${slot.source_status}${slot.can_edit_render ? " · replaceable" : ""}`;
    button.append(pair, mapping, code);
    button.addEventListener("click", () => selectGlyph(slot.code));
    return button;
  }));
}

function selectGlyph(code) {
  state.selectedGlyph = state.font?.slots.find((slot) => slot.code === code) || null;
  if (!state.selectedGlyph) return;
  const slot = state.selectedGlyph;
  elements.glyphEmpty.hidden = true;
  elements.glyphContent.hidden = false;
  const replaced = slot.replacement !== null;
  const originalImage = slot.original_image || slot.modified_image;
  elements.selectedOriginalImage.src = originalImage || "";
  elements.selectedOriginalImage.hidden = !originalImage;
  elements.selectedGlyphPair.classList.toggle("single", !replaced);
  elements.selectedGlyphDivider.hidden = !replaced;
  elements.selectedCurrentGlyph.hidden = !replaced;
  elements.selectedGlyphImage.src = slot.image || "";
  elements.selectedGlyphImage.hidden = !replaced || !slot.image;
  elements.selectedGlyphCode.textContent = slot.code_label;
  elements.selectedGlyphOriginal.textContent = `Source mapping: ${slot.source_status}`;
  elements.selectedGlyphMapping.textContent = glyphMappingLabel(slot);
  elements.sourceValue.value = slot.source_value || "";
  elements.sourceValue.disabled = !slot.can_edit_source;
  elements.saveSourceValue.disabled = !slot.can_edit_source;
  const sourceMessages = {
    defined: "Stored in the checked font definition. Edit and save here if the mapping is wrong.",
    suggested: "Suggested automatically from an identical known bitmap or an empty cell. Review it before saving.",
    unknown: "No source value is known yet. Enter your best reading of the bitmap.",
  };
  elements.sourceValueHelp.textContent = sourceMessages[slot.source_status];
  elements.replacementEditor.hidden = !slot.can_edit_render;
  elements.glyphReplacement.value = slot.replacement || "";
  elements.glyphUsage.className = `glyph-usage${slot.usage ? " warn" : ""}`;
  elements.glyphUsage.textContent = slot.usage
    ? `This character appears ${slot.usage} times in the current translation. Replacing it can make those lines invalid.`
    : "This character is not currently used by an indexed translation field.";
  elements.saveGlyph.disabled = !slot.can_edit_render || !state.font.can_rebuild;
  renderGlyphs();
}

async function saveGlyph() {
  if (!state.font || !state.selectedGlyph) return;
  const replacement = elements.glyphReplacement.value;
  if (!replacement) {
    showToast("Enter the character this slot should render.", true);
    return;
  }
  const changed = replacement !== state.selectedGlyph.replacement;
  let confirmUsed = false;
  if (changed && state.selectedGlyph.usage) {
    confirmUsed = window.confirm(
      `${JSON.stringify(state.selectedGlyph.replacement)} is used ${state.selectedGlyph.usage} times. Replace and rebuild it anyway?`,
    );
    if (!confirmUsed) return;
  }
  elements.saveGlyph.disabled = true;
  try {
    await requestJson("/api/font", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: state.font.id,
        code: state.selectedGlyph.code,
        replacement,
        base_hash: state.font.config_hash,
        language: state.language.id,
        confirm_used: confirmUsed,
      }),
    });
    const selectedCode = state.selectedGlyph.code;
    const offset = state.font.slot_page.offset;
    const fontId = state.font.id;
    state.selectedGlyph = null;
    await selectFont(fontId, offset);
    selectGlyph(selectedCode);
    showToast(`${state.font.name} rebuilt with ${JSON.stringify(replacement)}.`);
  } catch (error) {
    showToast(error.message, true);
    elements.saveGlyph.disabled = false;
  }
}

async function saveSourceValue() {
  if (!state.font || !state.selectedGlyph?.can_edit_source) return;
  const sourceValue = elements.sourceValue.value;
  if (!sourceValue) {
    showToast("Enter the original value represented by this bitmap.", true);
    return;
  }
  elements.saveSourceValue.disabled = true;
  try {
    await requestJson("/api/font/source", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: state.font.id,
        code: state.selectedGlyph.code,
        source_value: sourceValue,
        base_hash: state.font.source_hash,
      }),
    });
    const selectedCode = state.selectedGlyph.code;
    const selectedLabel = state.selectedGlyph.code_label;
    const offset = state.font.slot_page.offset;
    const fontId = state.font.id;
    await loadFonts();
    await selectFont(fontId, offset);
    selectGlyph(selectedCode);
    showToast(`Source value saved for ${state.font.file} ${selectedLabel}.`);
  } catch (error) {
    showToast(error.message, true);
    elements.saveSourceValue.disabled = false;
  }
}

function openLanguageDialog(editing) {
  state.editingLanguage = editing;
  const language = editing ? state.language : null;
  elements.languageDialogTitle.textContent = editing ? "Edit language" : "New language";
  elements.languageLabel.value = language?.label || "";
  elements.languageId.value = language?.id || "";
  elements.languageId.disabled = editing;
  elements.languageLocale.value = language?.locale || "";
  elements.languageCharacters.value = language?.characters || "";
  elements.saveLanguage.textContent = editing ? "Save language" : "Create language";
  elements.languageDialog.showModal();
}

async function saveLanguage(event) {
  event.preventDefault();
  const payload = {
    id: elements.languageId.value.trim(),
    label: elements.languageLabel.value.trim(),
    locale: elements.languageLocale.value.trim(),
    characters: elements.languageCharacters.value,
  };
  if (state.editingLanguage) payload.base_hash = state.language.file_hash;
  elements.saveLanguage.disabled = true;
  try {
    const language = await requestJson(
      state.editingLanguage ? "/api/language" : "/api/languages",
      {
        method: state.editingLanguage ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    elements.languageDialog.close();
    await loadLanguages(language.id);
    showToast(state.editingLanguage ? "Language saved." : "Language created.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    elements.saveLanguage.disabled = false;
  }
}

async function importFontFile() {
  const file = elements.fontFile.files[0];
  if (!file || !state.font || !state.language) return;
  if (!window.confirm(
    `Import ${file.name} for ${state.language.label}? You are responsible for permission to redistribute this typeface.`,
  )) {
    elements.fontFile.value = "";
    return;
  }
  elements.importFont.disabled = true;
  elements.importFont.textContent = "Importing and rebuilding…";
  try {
    const query = new URLSearchParams({
      language: state.language.id,
      font: state.font.id,
      filename: file.name,
    });
    state.font = await requestJson(`/api/font/import?${query}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    });
    state.language = await requestJson(
      `/api/language?id=${encodeURIComponent(state.language.id)}`,
    );
    const selectedId = state.font.id;
    await loadFonts();
    await selectFont(selectedId);
    showToast(`${file.name} selected as the replacement typeface. Run Update Font to recalculate mappings.`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    elements.fontFile.value = "";
    elements.importFont.disabled = false;
  }
}

elements.search.addEventListener("input", () => {
  window.clearTimeout(state.queryTimer);
  state.queryTimer = window.setTimeout(loadEntries, 180);
});
elements.translation.addEventListener("input", scheduleEvaluation);
elements.font8Alphabet.addEventListener("change", scheduleEvaluation);
elements.surfaceSelect.addEventListener("change", renderSurface);
elements.discard.addEventListener("click", () => {
  if (!state.selected) return;
  elements.translation.value = state.selected.translation;
  elements.font8Alphabet.value = state.selected.font8_alphabet;
  evaluateDraft(true);
});
elements.save.addEventListener("click", saveTranslation);
elements.translationsTab.addEventListener("click", () => switchWorkspace("translations"));
elements.fontsTab.addEventListener("click", () => switchWorkspace("fonts"));
elements.languageSelect.addEventListener("change", () => selectLanguage(elements.languageSelect.value));
elements.newLanguage.addEventListener("click", () => openLanguageDialog(false));
elements.editLanguage.addEventListener("click", () => openLanguageDialog(true));
elements.closeLanguage.addEventListener("click", () => elements.languageDialog.close());
elements.cancelLanguage.addEventListener("click", () => elements.languageDialog.close());
elements.languageForm.addEventListener("submit", saveLanguage);
elements.importFont.addEventListener("click", () => elements.fontFile.click());
elements.fontFile.addEventListener("change", importFontFile);
elements.planFontUpdate.addEventListener("click", planFontUpdate);
elements.applyFontUpdate.addEventListener("click", applyFontUpdate);
elements.glyphFilter.addEventListener("input", () => {
  window.clearTimeout(state.fontQueryTimer);
  state.fontQueryTimer = window.setTimeout(() => {
    if (state.font) selectFont(state.font.id, 0);
  }, 180);
});
elements.previousGlyphPage.addEventListener("click", () => {
  if (!state.font) return;
  selectFont(
    state.font.id,
    Math.max(0, state.font.slot_page.offset - state.font.slot_page.limit),
  );
});
elements.nextGlyphPage.addEventListener("click", () => {
  if (!state.font) return;
  selectFont(
    state.font.id,
    state.font.slot_page.offset + state.font.slot_page.limit,
  );
});
elements.saveGlyph.addEventListener("click", saveGlyph);
elements.saveSourceValue.addEventListener("click", saveSourceValue);
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    saveTranslation();
  }
});

loadEntries();
