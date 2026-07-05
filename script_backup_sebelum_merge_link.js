let allProducts = [];
let allCategories = [];
let activeCategory = "";
let categoryOpen = false;

const defaultCategories = ["Atasan", "Bawahan", "Hijab", "Gamis", "Tas", "Sepatu"];
const fallbackImage = "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?q=80&w=1200&auto=format&fit=crop";

function parsePrice(priceText) {
  if (!priceText) return 0;
  const clean = String(priceText).replace(/[^\d]/g, "");
  return Number(clean || 0);
}

function formatPrice(priceText) {
  const raw = String(priceText || "").trim();
  if (!raw) return "Cek harga";
  if (raw.toLowerCase().startsWith("rp")) return raw;
  const number = parsePrice(raw);
  if (!number) return raw;
  return "Rp" + number.toLocaleString("id-ID");
}

function getValue(id) {
  const el = document.getElementById(id);
  return el ? el.value : "";
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(text) {
  return escapeHtml(text).replaceAll("\n", " ");
}

function normalizeTextKey(text) {
  return String(text || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&amp;/g, "&")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function normalizeProductNumber(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/^no\.?\s*/i, "")
    .replace(/\s+/g, "")
    .trim();
}

function numericIdValue(id) {
  const match = String(id || "").match(/\d+/);
  return match ? Number(match[0]) : -1;
}

function normalizeLinkKey(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const url = new URL(raw, window.location.href);
    let host = url.hostname.toLowerCase().replace(/^www\./, "");
    let path = decodeURIComponent(url.pathname || "").replace(/\/+$/, "");
    if (/shopee|tokopedia|tiktok/.test(host)) return `${host}${path}`.toLowerCase();
    return `${host}${path}${url.search || ""}`.toLowerCase();
  } catch (err) {
    return normalizeTextKey(raw);
  }
}

function uniqueTextValues(values) {
  const out = [];
  const seen = new Set();
  values.forEach((value) => {
    const text = String(value || "").trim();
    if (!text) return;
    const key = text.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    out.push(text);
  });
  return out;
}

function getStoredVariants(product) {
  const list = [];
  if (Array.isArray(product && product._variants)) list.push(...product._variants);
  if (Array.isArray(product && product.variants)) list.push(...product.variants);
  if (!list.length) list.push(product || {});

  return list.map((item) => {
    const clean = { ...(item || {}) };
    delete clean._variants;
    delete clean.variants;
    return clean;
  });
}

function collectProductIds(product, variants) {
  return uniqueTextValues([
    product && product.id,
    ...((product && product._aliases) || []),
    ...((product && product._allIds) || []),
    ...((product && product.searchIds) || []),
    ...(variants || []).map((item) => item && item.id),
  ]);
}

function variantSortValue(item) {
  return numericIdValue(item && item.id);
}

function getLatestVariant(variants) {
  const list = [...(variants || [])].filter(Boolean);
  if (!list.length) return {};
  list.sort((a, b) => {
    const numA = variantSortValue(a);
    const numB = variantSortValue(b);
    if (numA !== numB) return numB - numA;
    return String(b.id || "").localeCompare(String(a.id || ""));
  });
  return list[0];
}

function duplicateKey(product) {
  const nameKey = normalizeTextKey(product.name || product.subtitle || "");
  const priceKey = normalizeTextKey(formatPrice(product.price));
  const categoryKey = normalizeTextKey(product.category || product.badge || product.type || inferCategory(product));

  // Produk marketplace yang sama biasanya punya nama + harga + kategori yang sama,
  // walaupun nomor/link/gambar berbeda. Ini yang dipakai untuk menggabungkan kartu.
  if (nameKey && priceKey && priceKey !== "cek harga") {
    return `produk:${nameKey}|${priceKey}|${categoryKey}`;
  }

  const linkKey = normalizeLinkKey(product.link || product.tiktokLink || product.productLink || "");
  if (linkKey) return `link:${linkKey}`;

  return `id:${normalizeProductNumber(product.id) || Math.random()}`;
}

function groupSimilarProducts(products) {
  const groups = new Map();
  const result = [];

  (Array.isArray(products) ? products : []).forEach((rawProduct, index) => {
    const product = { ...(rawProduct || {}) };
    const key = duplicateKey(product);
    const storedVariants = getStoredVariants(product);
    const variants = storedVariants.map((variant) => ({
      ...product,
      ...variant,
      _variantOrder: index,
    }));
    const ids = collectProductIds(product, variants);

    if (!groups.has(key)) {
      const group = {
        ...product,
        _duplicateKey: key,
        _variants: [],
        _allIds: [],
        _sortNumber: -1,
      };
      groups.set(key, group);
      result.push(group);
    }

    const group = groups.get(key);
    group._variants.push(...variants);
    group._allIds = uniqueTextValues([...group._allIds, ...ids]);
    group._sortNumber = Math.max(group._sortNumber || -1, ...ids.map(numericIdValue));
  });

  result.forEach((group) => {
    group._variants = uniqueVariants(group._variants);
    group._variants.sort((a, b) => {
      const numA = numericIdValue(a.id);
      const numB = numericIdValue(b.id);
      if (numA !== numB) return numA - numB;
      return String(a.id || "").localeCompare(String(b.id || ""));
    });

    const representative = getLatestVariant(group._variants);
    ["id", "name", "price", "category", "type", "badge", "image", "link", "tiktokLink", "platform", "tags", "subtitle", "desc", "colors", "size"].forEach((field) => {
      if (representative[field] !== undefined && representative[field] !== "") {
        group[field] = representative[field];
      }
    });
    group._allIds = collectProductIds(group, group._variants);
    group._sortNumber = Math.max(group._sortNumber || -1, ...group._allIds.map(numericIdValue));
  });

  return result;
}

function uniqueVariants(variants) {
  const out = [];
  const seen = new Set();
  (variants || []).forEach((variant) => {
    const key = [
      normalizeProductNumber(variant && variant.id),
      normalizeTextKey(variant && variant.name),
      normalizeTextKey(formatPrice(variant && variant.price)),
      normalizeTextKey(variant && variant.link),
      normalizeTextKey(variant && variant.image),
    ].join("|");
    if (seen.has(key)) return;
    seen.add(key);
    out.push(variant);
  });
  return out;
}

function displayVariantForSearch(product) {
  const q = normalizeProductNumber(getValue("searchInput"));
  const variants = product._variants && product._variants.length ? product._variants : getStoredVariants(product);

  if (q) {
    const exact = variants.find((variant) => normalizeProductNumber(variant.id) === q);
    if (exact) return exact;

    const alias = (product._allIds || product._aliases || []).find((id) => normalizeProductNumber(id) === q);
    if (alias) return { ...product, id: alias };
  }

  return getLatestVariant(variants) || product;
}

function cleanCategoryName(value) {
  let text = String(value || "").trim().replace(/\s+/g, " ");
  text = text.replace(/^[\-_/+\s]+|[\-_/+\s]+$/g, "");
  return text;
}

function uniqueCategories(values) {
  const out = [];
  const seen = new Set();
  values.forEach((value) => {
    const cat = cleanCategoryName(value);
    if (!cat) return;
    const key = cat.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    out.push(cat);
  });
  return out;
}

function inferCategory(product) {
  // Prioritaskan kategori yang ditulis oleh manager Python.
  const manual = cleanCategoryName(product.category || product.badge || product.type || "");
  if (manual) {
    const found = allCategories.find((cat) => cat.toLowerCase() === manual.toLowerCase());
    return found || manual;
  }

  const text = [
    product.name,
    product.subtitle,
    product.desc,
    ...(product.tags || [])
  ].join(" ").toLowerCase();

  if (/(hijab|jilbab|kerudung|khimar|pashmina|segiempat)/.test(text)) return "Hijab";
  if (/(oneset|one set|setelan|stelan|gamis|dress|abaya)/.test(text)) return "Gamis";
  if (/(tas|bag|slingbag|handbag|totebag|shoulder)/.test(text)) return "Tas";
  if (/(sepatu|sandal|heels|sneakers|flatshoes|flat shoes)/.test(text)) return "Sepatu";
  if (/(rok|celana|kulot|jeans|pants|skirt)/.test(text)) return "Bawahan";
  if (/(baju|kaos|kemeja|blouse|tunik|cardigan|jaket|outer|top|atasan|jersey)/.test(text)) return "Atasan";
  if (/(tumbler|botol minum|botol|cup|mug)/.test(text)) return "Tumbler";

  const firstWord = String(product.name || "Produk").trim().split(/\s+/).find((w) => w.length >= 3);
  return firstWord ? firstWord.charAt(0).toUpperCase() + firstWord.slice(1).toLowerCase() : "Produk";
}

function buildCategories() {
  const productCategories = allProducts.map(inferCategory);
  allCategories = uniqueCategories([...defaultCategories, ...allCategories, ...productCategories]);
}

function renderCategoryMenu() {
  const menu = document.getElementById("categoryPills");
  const toggle = document.getElementById("categoryToggle");
  if (!menu) return;

  const currentLabel = activeCategory || "Semua Kategori";
  if (toggle) {
    toggle.innerHTML = `<span>☰</span><strong>${escapeHtml(currentLabel)}</strong><em>${categoryOpen ? "▴" : "▾"}</em>`;
    toggle.classList.toggle("active", Boolean(activeCategory));
  }

  menu.classList.toggle("show", categoryOpen);
  menu.innerHTML = ["", ...allCategories].map((category) => {
    const label = category || "Semua";
    const active = (category || "").toLowerCase() === activeCategory.toLowerCase();
    return `<button class="pill ${active ? "active" : ""}" type="button" data-category="${escapeAttr(category)}">${escapeHtml(label)}</button>`;
  }).join("");

  menu.querySelectorAll(".pill").forEach((button) => {
    button.addEventListener("click", () => {
      setActiveCategory(button.dataset.category || "");
      categoryOpen = false;
      renderCategoryMenu();
    });
  });
}

function productMatches(product) {
  const qRaw = getValue("searchInput").trim().toLowerCase();
  const qText = normalizeTextKey(qRaw);
  const qNumber = normalizeProductNumber(qRaw);
  const minPrice = parsePrice(getValue("filterPriceMin"));
  const maxPrice = parsePrice(getValue("filterPriceMax"));
  const variants = product._variants && product._variants.length ? product._variants : getStoredVariants(product);
  const allIds = collectProductIds(product, variants);

  const categories = variants.map(inferCategory);
  const prices = variants.map((variant) => parsePrice(variant.price)).filter(Boolean);

  const haystackParts = [
    ...allIds.flatMap((id) => [id, `no ${id}`, `no. ${id}`, `produk ${id}`, `nomor ${id}`]),
    ...variants.flatMap((variant) => {
      const category = inferCategory(variant);
      return [
        variant.name,
        variant.type,
        variant.subtitle,
        variant.desc,
        category,
        ...(variant.tags || []),
        ...(variant.colors || [])
      ];
    })
  ];

  const haystackRaw = haystackParts.join(" ").toLowerCase();
  const haystackText = normalizeTextKey(haystackRaw);
  const idMatch = qNumber && allIds.some((id) => normalizeProductNumber(id) === qNumber);

  if (qRaw && !idMatch && !haystackRaw.includes(qRaw) && !haystackText.includes(qText)) return false;
  if (activeCategory && !categories.some((category) => category.toLowerCase() === activeCategory.toLowerCase())) return false;
  if (minPrice && !prices.some((price) => price >= minPrice)) return false;
  if (maxPrice && !prices.some((price) => price <= maxPrice)) return false;

  return true;
}

function sortProducts(products) {
  const sortBy = getValue("sortBy");
  const items = [...products];

  if (sortBy === "low") items.sort((a, b) => parsePrice(a.price) - parsePrice(b.price));
  if (sortBy === "high") items.sort((a, b) => parsePrice(b.price) - parsePrice(a.price));
  if (sortBy === "name") items.sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")));
  if (sortBy === "new") items.sort((a, b) => (b._sortNumber || numericIdValue(b.id)) - (a._sortNumber || numericIdValue(a.id)));

  return items;
}

function renderProducts() {
  const grid = document.getElementById("productGrid");
  const count = document.getElementById("productCount");
  const filtered = sortProducts(allProducts.filter(productMatches));

  if (count) count.textContent = `${filtered.length} produk unik`;
  renderCategoryMenu();

  if (!grid) return;

  if (!filtered.length) {
    grid.innerHTML = `<div class="empty">Produk tidak ditemukan. Coba ganti kata pencarian atau reset filter.</div>`;
    return;
  }

  grid.innerHTML = filtered.map((product) => {
    const displayProduct = displayVariantForSearch(product);
    const category = inferCategory(displayProduct);
    const image = displayProduct.image || product.image || fallbackImage;
    const link = displayProduct.tiktokLink || displayProduct.link || product.tiktokLink || product.link || "#";
    const displayId = displayProduct.id || product.id || "-";
    return `
      <article class="card">
        <div class="photo">
          <img src="${escapeAttr(image)}" alt="${escapeAttr(displayProduct.name || product.name || displayId)}" onerror="this.src='${fallbackImage}'">
          <div class="badge">${escapeHtml(category)}</div>
          <div class="code">No. ${escapeHtml(displayId)}</div>
          <div class="price">${escapeHtml(formatPrice(displayProduct.price || product.price))}</div>
        </div>
        <div class="content">
          <h3>${escapeHtml(displayProduct.name || product.name || "Produk Outfit")}</h3>
          <a class="buy" href="${escapeAttr(link)}" target="_blank" rel="noreferrer">Lihat Produk ↗</a>
        </div>
      </article>
    `;
  }).join("");
}

async function loadProducts() {
  let loadedProducts = [];

  try {
    const [productRes, categoryRes] = await Promise.allSettled([
      fetch("public/products.json?ts=" + Date.now()),
      fetch("public/categories.json?ts=" + Date.now())
    ]);

    if (productRes.status === "fulfilled" && productRes.value.ok) {
      const data = await productRes.value.json();
      loadedProducts = Array.isArray(data) ? data : [];
    } else {
      loadedProducts = [];
    }

    if (categoryRes.status === "fulfilled" && categoryRes.value.ok) {
      const data = await categoryRes.value.json();
      allCategories = Array.isArray(data) ? data : (data.categories || []);
    } else {
      allCategories = [];
    }
  } catch (err) {
    console.error(err);
    loadedProducts = [];
    allCategories = [];
  }

  allProducts = groupSimilarProducts(loadedProducts);
  buildCategories();
  renderProducts();
}

function setActiveCategory(category) {
  activeCategory = category || "";
  renderProducts();
}

document.addEventListener("DOMContentLoaded", () => {
  loadProducts();

  ["searchInput", "filterPriceMin", "filterPriceMax", "sortBy"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", renderProducts);
    el.addEventListener("change", renderProducts);
  });

  const categoryToggle = document.getElementById("categoryToggle");
  if (categoryToggle) {
    categoryToggle.addEventListener("click", () => {
      categoryOpen = !categoryOpen;
      renderCategoryMenu();
    });
  }

  const filterToggle = document.getElementById("filterToggle");
  const filterPanel = document.getElementById("filterPanel");
  if (filterToggle && filterPanel) {
    filterToggle.addEventListener("click", () => {
      filterPanel.classList.toggle("show");
    });
  }

  const resetBtn = document.getElementById("resetBtn");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      ["searchInput", "filterPriceMin", "filterPriceMax"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = "";
      });
      const sort = document.getElementById("sortBy");
      if (sort) sort.value = "new";
      activeCategory = "";
      categoryOpen = false;
      renderProducts();
    });
  }
});
