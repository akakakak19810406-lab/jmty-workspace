/**
 * このコードは、ジモティー営業のアカウント情報シートにある画像セルをダウンロード導線にする。
 * 画像セルのリンク化、PC向けアカウント選択モーダル、スマホ向けWeb確認ページを提供する。
 * 画像はzip化せず、各画像ファイルとして1枚ずつ順番に保存できるようにする。
 */
var CONFIG_ = {
  spreadsheetId: "1GKBTHwBS6W0D30X_yK7vqsaDRWw3p1tXM7lnFhyb0Uw",
  targetSheetName: "アカウント情報",
  headerRow: 6,
  imageHeaders: ["使用画像", "使用画像①", "使用画像②"],
  imageDisplayLabelByHeader: {
    "使用画像": "工場",
    "使用画像①": "在宅1",
    "使用画像②": "在宅2"
  },
  imageDisplayLabels: ["工場", "在宅1", "在宅2"],
  accountNoHeader: "アカウントNo",
  accountNameHeader: "アカウント情報",
  filenameHeader: "",
  filenameSourceHeaders: ["アカウントNo", "アカウント情報"],
  defaultFilenamePrefix: "image",
  maxImageBytes: 8 * 1024 * 1024,
  webAppUrl: "",
  enableSelectionDownload: false,
  dialogTitle: "画像をダウンロード",
  pickerTitle: "アカウント画像を選択"
};

var IMAGE_EXTENSIONS_BY_MIME_ = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/gif": "gif",
  "image/webp": "webp",
  "image/bmp": "bmp",
  "image/svg+xml": "svg"
};

function onOpen(e) {
  SpreadsheetApp.getUi()
    .createMenu("画像ダウンロード")
    .addItem("アカウントを選んでダウンロード", "showImagePicker")
    .addItem("選択セルの画像を確認", "downloadSelectedImage")
    .addSeparator()
    .addItem("画像セルをスマホ対応リンク化", "setupImageDownloadLinks")
    .addToUi();
}

function doGet(e) {
  var params = (e && e.parameter) || {};
  if (!params.row) {
    return HtmlService.createTemplateFromFile("ImagePickerDialog")
      .evaluate()
      .setTitle(CONFIG_.pickerTitle)
      .addMetaTag("viewport", "width=device-width, initial-scale=1, viewport-fit=cover")
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  }

  var context = {
    source: "web",
    row: parseInt(params.row, 10) || 0,
    imageKey: params.imageKey || params.key || resolveImageKeyFromKind_(params.kind || params.type || params.slot || ""),
    mode: params.mode === "all" ? "all" : "single"
  };

  return createDownloadHtml_(context, 760, 700)
    .setTitle(CONFIG_.dialogTitle)
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function onSelectionChange(e) {
  if (!CONFIG_.enableSelectionDownload || !e || !e.range) return;

  try {
    var context = buildDownloadContextFromRange_(e.range, true);
    if (!context) return;
    showDownloadDialog_(context);
  } catch (error) {
    Logger.log("image-cell-downloader selection error: " + formatError_(error));
  }
}

function showImagePicker() {
  var html = HtmlService.createTemplateFromFile("ImagePickerDialog")
    .evaluate()
    .setWidth(760)
    .setHeight(640);
  SpreadsheetApp.getUi().showModalDialog(html, CONFIG_.pickerTitle);
}

function downloadSelectedImage() {
  try {
    var range = SpreadsheetApp.getActiveRange();
    var context = buildDownloadContextFromRange_(range, false);
    showDownloadDialog_(context);
  } catch (error) {
    SpreadsheetApp.getUi().alert(CONFIG_.dialogTitle, error.message, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

function showDownloadDialogForSelection(row, imageKey, mode) {
  showDownloadDialog_({
    source: "picker",
    row: parseInt(row, 10) || 0,
    imageKey: imageKey || "",
    mode: mode === "all" ? "all" : "single"
  });
  return true;
}

function setupImageDownloadLinks() {
  var webAppUrl = getWebAppUrl_();
  var sheet = getTargetSheet_();
  var lastRow = sheet.getLastRow();
  if (lastRow <= CONFIG_.headerRow) {
    throw new Error("リンク化する画像行がありません。");
  }

  var imageDefinitions = getImageDefinitions_(sheet);
  if (imageDefinitions.length === 0) {
    throw new Error("対象画像列が見つかりません。");
  }

  var changed = 0;
  for (var d = 0; d < imageDefinitions.length; d++) {
    var definition = imageDefinitions[d];
    for (var row = CONFIG_.headerRow + 1; row <= lastRow; row++) {
      var range = sheet.getRange(row, definition.column);
      var formula = range.getFormula();
      var imageUrl = extractImageUrlFromFormula_(formula);
      if (!imageUrl) continue;

      var downloadUrl = buildDownloadUrl_(webAppUrl, row, definition.imageKey, "single");
      var linkedFormula = '=HYPERLINK("' +
        escapeFormulaString_(downloadUrl) +
        '", IMAGE("' +
        escapeFormulaString_(imageUrl) +
        '"))';

      if (formula !== linkedFormula) {
        range.setFormula(linkedFormula);
        changed++;
      }
    }
  }

  SpreadsheetApp.getUi().alert(
    "画像セルのリンク化が完了しました。",
    changed + " セルを更新しました。",
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

function getAccountImageOptions() {
  var sheet = getTargetSheet_();
  var headerMap = buildHeaderMap_(sheet);
  var imageDefinitions = getImageDefinitions_(sheet);
  var lastRow = sheet.getLastRow();
  var lastColumn = sheet.getLastColumn();
  if (lastRow <= CONFIG_.headerRow) {
    return { accounts: [], imageDefinitions: imageDefinitions };
  }

  var rowCount = lastRow - CONFIG_.headerRow;
  var displayValues = sheet
    .getRange(CONFIG_.headerRow + 1, 1, rowCount, lastColumn)
    .getDisplayValues();
  var formulas = sheet
    .getRange(CONFIG_.headerRow + 1, 1, rowCount, lastColumn)
    .getFormulas();

  var accountNoColumn = headerMap[CONFIG_.accountNoHeader] || 0;
  var accountNameColumn = headerMap[CONFIG_.accountNameHeader] || 0;
  var accounts = [];

  for (var r = 0; r < rowCount; r++) {
    var rowNumber = CONFIG_.headerRow + 1 + r;
    var accountNo = accountNoColumn ? String(displayValues[r][accountNoColumn - 1] || "").trim() : "";
    var accountName = accountNameColumn ? String(displayValues[r][accountNameColumn - 1] || "").trim() : "";
    if (!accountNo && !accountName) continue;

    var images = [];
    for (var d = 0; d < imageDefinitions.length; d++) {
      var definition = imageDefinitions[d];
      var formula = formulas[r][definition.column - 1] || "";
      var imageUrl = extractImageUrlFromFormula_(formula);
      if (!imageUrl) continue;
      images.push({
        imageKey: definition.imageKey,
        header: definition.header,
        label: definition.label,
        column: definition.column,
        url: imageUrl
      });
    }

    accounts.push({
      row: rowNumber,
      accountNo: accountNo,
      accountName: accountName,
      label: buildAccountLabel_(accountNo, accountName, rowNumber),
      imageCount: images.length,
      images: images
    });
  }

  return {
    accounts: accounts,
    imageDefinitions: imageDefinitions
  };
}

function getDownloadModel(context) {
  var normalized = normalizeContext_(context);
  var accountContext = buildAccountImageContexts_(normalized.row);
  var selectedImageKey = normalized.imageKey || (accountContext.images[0] || {}).imageKey || "";
  var selectedImage = null;

  for (var i = 0; i < accountContext.images.length; i++) {
    if (accountContext.images[i].imageKey === selectedImageKey) {
      selectedImage = accountContext.images[i];
      break;
    }
  }

  if (!selectedImage && accountContext.images.length > 0) {
    selectedImage = accountContext.images[0];
    selectedImageKey = selectedImage.imageKey;
  }

  return {
    row: accountContext.row,
    mode: normalized.mode,
    selectedImageKey: selectedImageKey,
    accountNo: accountContext.accountNo,
    accountName: accountContext.accountName,
    accountLabel: buildAccountLabel_(accountContext.accountNo, accountContext.accountName, accountContext.row),
    images: accountContext.images,
    selectedImage: selectedImage
  };
}

function getSingleImagePayload(row, imageKey) {
  var context = buildImageContextByRowAndKey_(parseInt(row, 10), imageKey);
  var payload = getDownloadPayload(context.url, context.filename);
  payload.imageKey = context.imageKey;
  payload.label = context.label;
  payload.originalUrl = context.url;
  payload.row = context.row;
  return payload;
}

function getAccountImagePayloads(row) {
  var accountContext = buildAccountImageContexts_(parseInt(row, 10));
  if (accountContext.images.length === 0) {
    throw new Error("このアカウントにはダウンロードできる画像がありません。");
  }

  var payloads = [];
  for (var i = 0; i < accountContext.images.length; i++) {
    var image = accountContext.images[i];
    var payload = getDownloadPayload(image.url, image.filename);
    payload.imageKey = image.imageKey;
    payload.label = image.label;
    payload.originalUrl = image.url;
    payload.row = image.row;
    payloads.push(payload);
  }
  return payloads;
}

function getAccountImagePreviewPayloads(row) {
  var accountContext = buildAccountImageContexts_(parseInt(row, 10));
  var previews = [];
  for (var i = 0; i < accountContext.images.length; i++) {
    var image = accountContext.images[i];
    try {
      var payload = getDownloadPayload(image.url, image.filename);
      previews.push({
        imageKey: image.imageKey,
        label: image.label,
        filename: payload.filename,
        byteSize: payload.byteSize,
        dataUrl: payload.dataUrl,
        originalUrl: image.url
      });
    } catch (error) {
      previews.push({
        imageKey: image.imageKey,
        label: image.label,
        error: error && error.message ? error.message : String(error),
        originalUrl: image.url
      });
    }
  }
  return previews;
}

function getDownloadPayload(url, filename) {
  var normalizedUrl = normalizeUrl_(url);
  var source = fetchImageSource_(normalizedUrl);
  var bytes = source.blob.getBytes();

  if (bytes.length > CONFIG_.maxImageBytes) {
    throw new Error(
      "画像サイズが上限を超えています。上限: " +
      formatBytes_(CONFIG_.maxImageBytes) +
      " / 実サイズ: " +
      formatBytes_(bytes.length)
    );
  }

  var detectedMimeType = detectImageMimeType_(bytes, source.mimeType);
  if (!detectedMimeType) {
    throw new Error("画像として扱えるファイルではありません。Content-Type: " + (source.mimeType || "不明"));
  }

  var resolvedFilename = sanitizeFilename_(
    filename || source.filename || extractFilenameFromUrl_(normalizedUrl) || buildDefaultFilename_(detectedMimeType)
  );
  resolvedFilename = ensureImageExtension_(resolvedFilename, detectedMimeType);

  return {
    filename: resolvedFilename,
    mimeType: detectedMimeType,
    byteSize: bytes.length,
    dataUrl: "data:" + detectedMimeType + ";base64," + Utilities.base64Encode(bytes)
  };
}

function buildDownloadContextFromRange_(range, silent) {
  if (!range) {
    return failOrNull_("セルを選択してください。", silent);
  }
  if (range.getNumRows() !== 1 || range.getNumColumns() !== 1) {
    return failOrNull_("画像セルを1つだけ選択してください。", silent);
  }

  var sheet = range.getSheet();
  if (CONFIG_.targetSheetName && sheet.getName() !== CONFIG_.targetSheetName) {
    return failOrNull_("対象シートではありません: " + sheet.getName(), silent);
  }
  if (range.getRow() <= CONFIG_.headerRow) {
    return failOrNull_("ヘッダー行ではなく、画像が入っている行を選択してください。", silent);
  }

  var selectedImage = findSelectedImageColumn_(buildHeaderColumnsMap_(sheet), range.getColumn());
  if (!selectedImage) return null;

  var url = extractImageUrlFromFormula_(range.getFormula());
  if (!url) {
    return failOrNull_(
      "`" + selectedImage.header + "` セルの IMAGE 関数から画像URLを取得できません。",
      silent
    );
  }

  return {
    source: "selection",
    row: range.getRow(),
    imageKey: selectedImage.imageKey,
    mode: "single"
  };
}

function showDownloadDialog_(context) {
  SpreadsheetApp.getUi().showModalDialog(
    createDownloadHtml_(context, 760, 700),
    CONFIG_.dialogTitle
  );
}

function createDownloadHtml_(context, width, height) {
  var template = HtmlService.createTemplateFromFile("DownloadDialog");
  template.contextJson = JSON.stringify(context || {}).replace(/</g, "\\u003c");
  return template.evaluate()
    .setWidth(width)
    .setHeight(height);
}

function buildAccountImageContexts_(row) {
  var sheet = getTargetSheet_();
  if (!row || row <= CONFIG_.headerRow || row > sheet.getLastRow()) {
    throw new Error("対象アカウント行が正しくありません。");
  }

  var headerMap = buildHeaderMap_(sheet);
  var imageDefinitions = getImageDefinitions_(sheet);
  var rowValues = sheet.getRange(row, 1, 1, sheet.getLastColumn()).getDisplayValues()[0];
  var rowFormulas = sheet.getRange(row, 1, 1, sheet.getLastColumn()).getFormulas()[0];
  var accountNo = headerMap[CONFIG_.accountNoHeader]
    ? String(rowValues[headerMap[CONFIG_.accountNoHeader] - 1] || "").trim()
    : "";
  var accountName = headerMap[CONFIG_.accountNameHeader]
    ? String(rowValues[headerMap[CONFIG_.accountNameHeader] - 1] || "").trim()
    : "";

  var images = [];
  for (var i = 0; i < imageDefinitions.length; i++) {
    var definition = imageDefinitions[i];
    var formula = rowFormulas[definition.column - 1] || "";
    var imageUrl = extractImageUrlFromFormula_(formula);
    if (!imageUrl) continue;
    images.push({
      row: row,
      imageKey: definition.imageKey,
      header: definition.header,
      label: definition.label,
      column: definition.column,
      url: imageUrl,
      filename: buildFilenameFromParts_(sheet, headerMap, row, definition.label)
    });
  }

  return {
    row: row,
    accountNo: accountNo,
    accountName: accountName,
    images: images
  };
}

function buildImageContextByRowAndKey_(row, imageKey) {
  var accountContext = buildAccountImageContexts_(row);
  for (var i = 0; i < accountContext.images.length; i++) {
    if (accountContext.images[i].imageKey === imageKey) {
      return accountContext.images[i];
    }
  }
  throw new Error("指定された画像が見つかりません。");
}

function getImageDefinitions_(sheet) {
  return buildImageDefinitionsFromHeaderColumnsMap_(buildHeaderColumnsMap_(sheet));
}

function buildImageDefinitionsFromHeaderColumnsMap_(headerColumnsMap) {
  var definitions = [];
  for (var h = 0; h < CONFIG_.imageHeaders.length; h++) {
    var header = CONFIG_.imageHeaders[h];
    var columns = headerColumnsMap[header] || [];
    for (var c = 0; c < columns.length; c++) {
      var column = columns[c];
      definitions.push({
        imageKey: "col" + column,
        header: header,
        label: buildImageLabel_(header, column, columns.length),
        column: column,
        columnLetter: columnToLetter_(column)
      });
    }
  }

  definitions.sort(function(a, b) {
    return a.column - b.column;
  });
  return applyImageDisplayLabels_(definitions);
}

function findSelectedImageColumn_(headerColumnsMap, column) {
  var definitions = buildImageDefinitionsFromHeaderColumnsMap_(headerColumnsMap);
  for (var i = 0; i < definitions.length; i++) {
    if (definitions[i].column === column) {
      return definitions[i];
    }
  }
  return null;
}

function getTargetSheet_() {
  var spreadsheet = getTargetSpreadsheet_();
  if (!spreadsheet) {
    throw new Error("スプレッドシートに紐づいた状態で実行してください。");
  }
  var sheet = spreadsheet.getSheetByName(CONFIG_.targetSheetName);
  if (!sheet) {
    throw new Error("対象シート `" + CONFIG_.targetSheetName + "` が見つかりません。");
  }
  return sheet;
}

function getTargetSpreadsheet_() {
  if (CONFIG_.spreadsheetId) {
    return SpreadsheetApp.openById(CONFIG_.spreadsheetId);
  }
  return SpreadsheetApp.getActiveSpreadsheet();
}

function buildHeaderMap_(sheet) {
  var lastColumn = sheet.getLastColumn();
  if (lastColumn < 1) return {};

  var values = sheet.getRange(CONFIG_.headerRow, 1, 1, lastColumn).getDisplayValues()[0];
  var map = {};
  values.forEach(function(value, index) {
    var key = String(value || "").trim();
    if (key && !map[key]) {
      map[key] = index + 1;
    }
  });
  return map;
}

function buildHeaderColumnsMap_(sheet) {
  var lastColumn = sheet.getLastColumn();
  if (lastColumn < 1) return {};

  var values = sheet.getRange(CONFIG_.headerRow, 1, 1, lastColumn).getDisplayValues()[0];
  var map = {};
  values.forEach(function(value, index) {
    var key = String(value || "").trim();
    if (!key) return;
    if (!map[key]) {
      map[key] = [];
    }
    map[key].push(index + 1);
  });
  return map;
}

function buildFilenameFromParts_(sheet, headerMap, row, imageLabel) {
  if (CONFIG_.filenameHeader && headerMap[CONFIG_.filenameHeader]) {
    return String(sheet.getRange(row, headerMap[CONFIG_.filenameHeader]).getDisplayValue() || "").trim();
  }

  var parts = [];
  var sourceHeaders = CONFIG_.filenameSourceHeaders || [];
  for (var i = 0; i < sourceHeaders.length; i++) {
    var column = headerMap[sourceHeaders[i]];
    if (!column) continue;
    var value = String(sheet.getRange(row, column).getDisplayValue() || "").trim();
    if (value) parts.push(value);
  }

  if (imageLabel) parts.push(imageLabel);
  return parts.join("_");
}

function buildAccountLabel_(accountNo, accountName, row) {
  var parts = [];
  if (accountNo) parts.push(accountNo);
  if (accountName) parts.push(accountName);
  return parts.length > 0 ? parts.join(" / ") : "行 " + row;
}

function buildImageLabel_(header, column, duplicateCount) {
  if (duplicateCount > 1) {
    return header + "（" + columnToLetter_(column) + "列）";
  }
  return header;
}

function applyImageDisplayLabels_(definitions) {
  var labelsByHeader = CONFIG_.imageDisplayLabelByHeader || {};
  var labels = CONFIG_.imageDisplayLabels || [];
  for (var i = 0; i < definitions.length; i++) {
    if (labelsByHeader[definitions[i].header]) {
      definitions[i].label = labelsByHeader[definitions[i].header];
    } else if (labels[i]) {
      definitions[i].label = labels[i];
    }
  }
  return definitions;
}

function getWebAppUrl_() {
  var url = String(CONFIG_.webAppUrl || "").trim();
  if (!url) {
    url = ScriptApp.getService().getUrl();
  }
  if (!url) {
    throw new Error("WebアプリURLを取得できません。先にWebアプリとしてデプロイするか、CONFIG_.webAppUrl にURLを設定してください。");
  }
  return url;
}

function buildDownloadUrl_(webAppUrl, row, imageKey, mode) {
  return webAppUrl +
    "?row=" + encodeURIComponent(String(row)) +
    "&imageKey=" + encodeURIComponent(imageKey || "") +
    "&mode=" + encodeURIComponent(mode || "single");
}

function resolveImageKeyFromKind_(kind) {
  var normalized = String(kind || "").trim().toLowerCase();
  if (!normalized) return "";

  var label = "";
  if (normalized === "factory" || normalized === "工場") label = "工場";
  if (normalized === "remote1" || normalized === "remote_1" || normalized === "remote-1" || normalized === "在宅1") label = "在宅1";
  if (normalized === "remote2" || normalized === "remote_2" || normalized === "remote-2" || normalized === "在宅2") label = "在宅2";
  if (!label) return "";

  var definitions = getImageDefinitions_(getTargetSheet_());
  for (var i = 0; i < definitions.length; i++) {
    if (definitions[i].label === label) {
      return definitions[i].imageKey;
    }
  }
  return "";
}

function normalizeContext_(context) {
  var value = context || {};
  var row = parseInt(value.row, 10) || 0;
  if (!row) {
    throw new Error("対象アカウント行が指定されていません。");
  }
  return {
    row: row,
    imageKey: value.imageKey || "",
    mode: value.mode === "all" ? "all" : "single"
  };
}

function fetchImageSource_(url) {
  var driveTarget = extractDriveFileTarget_(url);
  if (driveTarget) {
    return fetchDriveImageSource_(driveTarget);
  }
  return fetchUrlImageSource_(url);
}

function fetchDriveImageSource_(driveTarget) {
  var file = driveTarget.resourceKey
    ? DriveApp.getFileByIdAndResourceKey(driveTarget.fileId, driveTarget.resourceKey)
    : DriveApp.getFileById(driveTarget.fileId);
  var blob = file.getBlob();

  return {
    blob: blob,
    mimeType: normalizeMimeType_(blob.getContentType() || file.getMimeType()),
    filename: file.getName()
  };
}

function fetchUrlImageSource_(url) {
  var response = UrlFetchApp.fetch(url, {
    followRedirects: true,
    muteHttpExceptions: true,
    validateHttpsCertificates: true,
    headers: {
      "User-Agent": "Mozilla/5.0 image-cell-downloader"
    }
  });
  var code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error("画像URLの取得に失敗しました。HTTP " + code);
  }

  var blob = response.getBlob();
  var mimeType = normalizeMimeType_(
    getHeaderCaseInsensitive_(response.getHeaders(), "Content-Type") || blob.getContentType()
  );

  return {
    blob: blob,
    mimeType: mimeType,
    filename: extractFilenameFromContentDisposition_(
      getHeaderCaseInsensitive_(response.getHeaders(), "Content-Disposition")
    )
  };
}

function normalizeUrl_(url) {
  var value = String(url || "").trim();
  if (!/^https?:\/\/\S+$/i.test(value)) {
    throw new Error("http または https の画像URLを指定してください。");
  }
  return value;
}

function extractImageUrlFromFormula_(formula) {
  var value = String(formula || "").trim();
  var match = value.match(/IMAGE\(\s*["']([^"']+)["']/i);
  return match ? match[1].trim() : "";
}

function extractDriveFileTarget_(url) {
  if (!/^https?:\/\/(?:drive|docs)\.google\.com\//i.test(url)) return null;

  var fileId = "";
  var pathMatch = url.match(/\/d\/([a-zA-Z0-9_-]{10,})/);
  if (pathMatch) {
    fileId = pathMatch[1];
  } else {
    fileId = getQueryParam_(url, "id") || getQueryParam_(url, "fileId");
  }

  if (!fileId) return null;
  return {
    fileId: fileId,
    resourceKey: getQueryParam_(url, "resourcekey") || getQueryParam_(url, "resourceKey")
  };
}

function getQueryParam_(url, name) {
  var pattern = new RegExp("[?&]" + name + "=([^&#]+)", "i");
  var match = String(url || "").match(pattern);
  return match ? decodeURIComponent(match[1].replace(/\+/g, " ")) : "";
}

function getHeaderCaseInsensitive_(headers, name) {
  if (!headers) return "";
  var target = String(name).toLowerCase();
  for (var key in headers) {
    if (Object.prototype.hasOwnProperty.call(headers, key) && String(key).toLowerCase() === target) {
      return String(headers[key] || "");
    }
  }
  return "";
}

function normalizeMimeType_(mimeType) {
  return String(mimeType || "").split(";")[0].trim().toLowerCase();
}

function detectImageMimeType_(bytes, mimeType) {
  var normalized = normalizeMimeType_(mimeType);
  if (IMAGE_EXTENSIONS_BY_MIME_[normalized]) return normalized;

  if (hasBytes_(bytes, [0x89, 0x50, 0x4e, 0x47], 0)) return "image/png";
  if (hasBytes_(bytes, [0xff, 0xd8, 0xff], 0)) return "image/jpeg";
  if (hasAscii_(bytes, "GIF87a", 0) || hasAscii_(bytes, "GIF89a", 0)) return "image/gif";
  if (hasAscii_(bytes, "RIFF", 0) && hasAscii_(bytes, "WEBP", 8)) return "image/webp";
  if (hasAscii_(bytes, "BM", 0)) return "image/bmp";

  var head = bytesToAsciiPrefix_(bytes, 1024).toLowerCase();
  if (head.indexOf("<svg") !== -1 || (head.indexOf("<?xml") !== -1 && head.indexOf("<svg") !== -1)) {
    return "image/svg+xml";
  }
  return "";
}

function hasBytes_(bytes, expected, offset) {
  if (bytes.length < offset + expected.length) return false;
  for (var i = 0; i < expected.length; i++) {
    if ((bytes[offset + i] & 0xff) !== expected[i]) return false;
  }
  return true;
}

function hasAscii_(bytes, text, offset) {
  if (bytes.length < offset + text.length) return false;
  for (var i = 0; i < text.length; i++) {
    if ((bytes[offset + i] & 0xff) !== text.charCodeAt(i)) return false;
  }
  return true;
}

function bytesToAsciiPrefix_(bytes, maxLength) {
  var chars = [];
  var length = Math.min(bytes.length, maxLength);
  for (var i = 0; i < length; i++) {
    var code = bytes[i] & 0xff;
    chars.push(code >= 9 && code <= 126 ? String.fromCharCode(code) : " ");
  }
  return chars.join("");
}

function extractFilenameFromUrl_(url) {
  var cleanUrl = String(url || "").split(/[?#]/)[0];
  var match = cleanUrl.match(/\/([^\/]+)$/);
  if (!match) return "";
  return decodeURIComponent(match[1]).trim();
}

function extractFilenameFromContentDisposition_(header) {
  var value = String(header || "");
  var utfMatch = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utfMatch) return decodeURIComponent(utfMatch[1].trim().replace(/^"|"$/g, ""));

  var plainMatch = value.match(/filename="?([^";]+)"?/i);
  return plainMatch ? plainMatch[1].trim() : "";
}

function sanitizeFilename_(filename) {
  var value = String(filename || "")
    .replace(/[\x00-\x1f\x7f]/g, "")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim();

  if (!value) {
    value = buildDefaultFilename_("");
  }
  if (value.length > 120) {
    value = value.slice(0, 120).trim();
  }
  return value;
}

function ensureImageExtension_(filename, mimeType) {
  if (/\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(filename)) return filename;
  var extension = IMAGE_EXTENSIONS_BY_MIME_[normalizeMimeType_(mimeType)] || "png";
  return filename + "." + extension;
}

function buildDefaultFilename_(mimeType) {
  var now = new Date();
  var timestamp = Utilities.formatDate(now, Session.getScriptTimeZone(), "yyyyMMdd-HHmmss");
  var extension = IMAGE_EXTENSIONS_BY_MIME_[normalizeMimeType_(mimeType)] || "png";
  return CONFIG_.defaultFilenamePrefix + "-" + timestamp + "." + extension;
}

function escapeFormulaString_(value) {
  return String(value || "").replace(/"/g, '""');
}

function columnToLetter_(column) {
  var value = "";
  var current = column;
  while (current > 0) {
    var remainder = (current - 1) % 26;
    value = String.fromCharCode(65 + remainder) + value;
    current = Math.floor((current - 1) / 26);
  }
  return value;
}

function formatBytes_(bytes) {
  if (bytes >= 1024 * 1024) {
    return (bytes / 1024 / 1024).toFixed(1) + "MB";
  }
  if (bytes >= 1024) {
    return (bytes / 1024).toFixed(1) + "KB";
  }
  return bytes + "B";
}

function failOrNull_(message, silent) {
  if (silent) return null;
  throw new Error(message);
}

function formatError_(error) {
  return error && error.stack ? error.stack : String(error);
}
