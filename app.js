(function () {
  "use strict";
  var CATEGORY_ORDER = ["AI subscriptions", "Cloud", "Domains", "Tools"];
  var SVGNS = "http://www.w3.org/2000/svg";

  function parseCSV(text) {
    var rows = [], row = [], field = "", q = false, i, c;
    for (i = 0; i < text.length; i++) {
      c = text[i];
      if (q) {
        if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else { q = false; } }
        else field += c;
      } else if (c === '"') q = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(field); field = "";
        if (row.length > 1 || row[0] !== "") rows.push(row);
        row = [];
      } else field += c;
    }
    if (field !== "" || row.length) { row.push(field); rows.push(row); }
    var head = rows.shift();
    return rows.map(function (r) {
      var o = {}; head.forEach(function (h, k) { o[h] = (r[k] || "").trim(); }); return o;
    });
  }

  function money(n) {
    return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function isPlaceholder(r) { return r.list_price_usd === "PLACEHOLDER"; }
  function isVaries(r) { return r.list_price_usd === "VARIES"; }
  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (text != null) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }
  function svg(tag, attrs, text) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function hostOf(url) { try { return new URL(url).hostname.replace(/^www\./, ""); } catch (e) { return url; } }

  function render(all) {
    var months = all.map(function (r) { return r.month; }).sort();
    var month = months[months.length - 1];
    var rows = all.filter(function (r) { return r.month === month; });
    rows.sort(function (a, b) { return CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category); });

    var total = 0, pending = 0, varies = 0, byCat = {}, pendCat = {}, varCat = {}, asOf = [];
    rows.forEach(function (r) {
      if (isVaries(r)) { varies++; varCat[r.category] = (varCat[r.category] || 0) + 1; return; }
      if (isPlaceholder(r)) { pending++; pendCat[r.category] = (pendCat[r.category] || 0) + 1; return; }
      var v = parseFloat(r.list_price_usd) || 0;
      total += v; byCat[r.category] = (byCat[r.category] || 0) + v;
      if (r.as_of) asOf.push(r.as_of);
    });
    asOf.sort();

    var d = new Date(month + "-01T12:00:00");
    document.getElementById("month-label").textContent = "· " + d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
    document.getElementById("total").textContent = money(total) + "/mo";
    var notes = [];
    if (pending) notes.push(pending + " placeholder" + (pending > 1 ? "s are" : " is") + " excluded until confirmed.");
    if (varies) notes.push(varies + " usage-based line" + (varies > 1 ? "s vary" : " varies") + " monthly and " + (varies > 1 ? "are" : "is") + " not counted.");
    document.getElementById("total-note").textContent = notes.length
      ? "Counts fixed list prices only. " + notes.join(" ")
      : "All line items confirmed.";
    if (asOf.length) {
      var last = new Date(asOf[asOf.length - 1] + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
      document.getElementById("asof-note").textContent = "List prices from vendors' public pricing pages, as of " + last + "; not actual bills.";
    }

    // table
    var tb = document.querySelector("#costs tbody");
    rows.forEach(function (r) {
      var tr = document.createElement("tr");
      var labels = ["Category", "Item", "List price", "Billing", "Source", "As of"];
      var tdCat = el("td", null, "nowrap"); tdCat.appendChild(el("span", r.category));
      var tdItem = el("td"); var wrap = el("span"); wrap.appendChild(el("span", r.item));
      if (r.note) wrap.appendChild(el("span", r.note, "note")); tdItem.appendChild(wrap);
      var tdPrice = el("td", null, "num");
      if (isVaries(r)) tdPrice.appendChild(el("span", "Varies monthly", "tbc"));
      else if (isPlaceholder(r)) tdPrice.appendChild(el("span", "To be confirmed", "tbc"));
      else tdPrice.appendChild(el("span", money(parseFloat(r.list_price_usd)) + (r.billing === "free" ? "" : "/mo")));
      var tdBill = el("td"); tdBill.appendChild(el("span", r.billing));
      var tdSrc = el("td");
      if (r.source_url) {
        var a = el("a", hostOf(r.source_url)); a.href = r.source_url; a.rel = "noopener"; tdSrc.appendChild(a);
      } else tdSrc.appendChild(el("span", "–"));
      var tdAs = el("td", null, "nowrap"); tdAs.appendChild(el("span", r.as_of || "–"));
      [tdCat, tdItem, tdPrice, tdBill, tdSrc, tdAs].forEach(function (td, k) { td.setAttribute("data-label", labels[k]); tr.appendChild(td); });
      tb.appendChild(tr);
    });

    // bar chart by category (drawn at the container's pixel width so text stays readable)
    function drawChart() {
    var cats = CATEGORY_ORDER.filter(function (c) { return c in byCat || c in pendCat || c in varCat; });
    var max = 0; cats.forEach(function (c) { max = Math.max(max, byCat[c] || 0); });
    var box = document.getElementById("chart");
    var W = Math.max(280, Math.round(box.clientWidth || 640)), rowH = 40, top = 6;
    var narrow = W < 520, labelW = narrow ? 118 : 160, valW = narrow ? 132 : 150;
    var H = top + cats.length * rowH;
    var s = svg("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img", "aria-label": "Confirmed monthly list price by category" });
    var barMax = W - labelW - valW - 10;
    cats.forEach(function (c, i) {
      var y = top + i * rowH, v = byCat[c] || 0;
      s.appendChild(svg("text", { x: 0, y: y + 21 }, c));
      var w = max > 0 ? Math.max(v > 0 ? 3 : 0, (v / max) * barMax) : 0;
      s.appendChild(svg("rect", { x: labelW, y: y + 6, width: barMax, height: 22, rx: 3, fill: "#eef1f4" }));
      if (w) s.appendChild(svg("rect", { x: labelW, y: y + 6, width: w, height: 22, rx: 3, fill: "#4a5568" }));
      var txt = money(v) + (pendCat[c] ? " + TBC" : "") + (varCat[c] ? " + varies" : "");
      var empty = !v && (pendCat[c] || varCat[c]);
      var emptyTxt = varCat[c] ? "varies, not counted" : "to be confirmed";
      s.appendChild(svg("text", { x: W, y: y + 21, "text-anchor": "end", "class": empty ? "muted" : "" }, empty ? emptyTxt : txt));
    });
    box.textContent = "";
    box.appendChild(s);
    }
    drawChart();
    var t; window.addEventListener("resize", function () { clearTimeout(t); t = setTimeout(drawChart, 150); });
  }

  fetch("data/costs.csv", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
    .then(function (t) { render(parseCSV(t)); })
    .catch(function () {
      document.getElementById("total").textContent = "Could not load data/costs.csv";
    });
})();
