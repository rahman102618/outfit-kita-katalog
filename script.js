let allProducts = [];

function parsePrice(priceText) {
  if (!priceText) return 0;
  const clean = String(priceText).replace(/[^\d]/g, "");
  return Number(clean || 0);
}

function textIncludes(value, query) {
  return String(value || "").toLowerCase().includes(query);
}

function getValue(id) {
  const el = document.getElementById(id);
  return el ? el.value : "";
}

function productMatches(product) {
  const q = getValue("searchInput").trim().toLowerCase();
  const category = getValue("filterCategory");
  const minPrice = parsePrice(getValue("filterPriceMin"));
  const maxPrice = parsePrice(getValue("filterPriceMax"));
  const style = getValue("filterStyle");
  const haystack = [
    product.id, product.name, product.subtitle, product.desc, product.type,
    ...(product.tags || []), ...(product.colors || [])
  ].join(" ").toLowerCase();

  if (q && !haystack.includes(q)) return false;

  if (category) {
    const cat = category.toLowerCase();
    const tags = (product.tags || []).join(" ").toLowerCase();
    if (!textIncludes(product.type, cat) && !tags.includes(cat)) return false;
  }

  const p = parsePrice(product.price);

  if (minPrice && p < minPrice) return false;
  if (maxPrice && p > maxPrice) return false;
  
  if (style) {
    const tags = (product.tags || []).join(" ").toLowerCase();
    if (!tags.includes(style.toLowerCase())) return false;
  }

  return true;
}

function sortProducts(products) {
  const sortBy = getValue("sortBy");
  const items = [...products];

  if (sortBy === "low") items.sort((a, b) => parsePrice(a.price) - parsePrice(b.price));
  if (sortBy === "high") items.sort((a, b) => parsePrice(b.price) - parsePrice(a.price));
  if (sortBy === "new") items.reverse();

  return items;
}

function renderProducts() {
  const grid = document.getElementById("productGrid");
  const filtered = sortProducts(allProducts.filter(productMatches));

  if (!filtered.length) {
    grid.innerHTML = `<div class="empty">Produk tidak ditemukan. Coba ubah pencarian atau filter.</div>`;
    return;
  }

  grid.innerHTML = filtered.map((p) => {
    const tags = (p.tags || []).slice(0, 2).map(t => `<span class="chip">${escapeHtml(t)}</span>`).join("");
    const image = p.image || "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?q=80&w=1200&auto=format&fit=crop";
    const link = p.tiktokLink || "#";

    return `
      <article class="card">
        <div class="photo">
          <img src="${escapeAttr(image)}" alt="${escapeAttr(p.name || p.id)}" onerror="this.src='https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?q=80&w=1200&auto=format&fit=crop'">
          <div class="code">No. ${escapeHtml(p.id || "-")}</div>
          <div class="price">${escapeHtml(p.price || "Cek harga")}</div>
        </div>
        <div class="content">
          <div class="chips">
          <span class="chip">${escapeHtml(p.type || "Produk")}</span>
        </div>
        <h3>${escapeHtml(p.name || "Produk Outfit")}</h3/>
        <a class="buy" href="${escapeAttr(link)}" target="_blank" rel="noreferrer">Lihat Produk ↗</a>        </div>
      </article>
    `;
  }).join("");
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

async function loadProducts() {
  try {
    const res = await fetch("public/products.json?ts=" + Date.now());
    allProducts = await res.json();
  } catch (err) {
    console.error(err);
    allProducts = [];
  }
  renderProducts();
}

document.addEventListener("DOMContentLoaded", () => {
  loadProducts();

 ["searchInput", "filterCategory", "filterPriceMin", "filterPriceMax", "filterStyle", "sortBy"].forEach((id) => {    if (!el) return;
    el.addEventListener("input", renderProducts);
    el.addEventListener("change", renderProducts);
  });

  const applyBtn = document.getElementById("applyBtn");
  if (applyBtn) {
    applyBtn.addEventListener("click", () => {
      renderProducts();
      const details = document.querySelector("details.filter-box");
      if (details) details.open = false;
    });
  }

  const resetBtn = document.getElementById("resetBtn");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
     ["filterCategory", "filterPriceMin", "filterPriceMax", "filterStyle"].forEach(id => {
       if (el) el.value = "";
      });
      const sort = document.getElementById("sortBy");
      if (sort) sort.value = "new";
      renderProducts();
    });
  }
});
