"use strict";

// ---- 공통 헬퍼 ---------------------------------------------------------
const $ = (id) => document.getElementById(id);

async function post(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return { status: r.status, data: await r.json().catch(() => ({})) };
}
async function get(url) {
  const r = await fetch(url);
  return { status: r.status, data: await r.json().catch(() => ({})) };
}

function setMsg(el, text, kind) {
  el.textContent = text || "";
  el.className = "msg" + (kind ? " " + kind : "");
}
function busy(btn, on, label) {
  btn.disabled = on;
  if (on) { btn.dataset._t = btn.textContent; btn.textContent = label || "처리 중…"; }
  else if (btn.dataset._t) { btn.textContent = btn.dataset._t; }
}

function goStep(n) {
  $("card1").classList.toggle("hidden", n !== 1);
  $("card2").classList.toggle("hidden", n !== 2);
  $("card3").classList.toggle("hidden", n !== 3);
  [1, 2, 3].forEach((i) => {
    const el = $("s" + i);
    el.className = i === n ? "on" : i < n ? "done" : "";
  });
}

let LOT = "";

// ---- ① 주차장 코드 ------------------------------------------------------
$("btnLot").onclick = async () => {
  const lot = $("lot").value.trim();
  if (!lot) return setMsg($("msgLot"), "주차장 코드를 입력해 주세요.", "err");
  busy($("btnLot"), true, "확인 중…");
  setMsg($("msgLot"), "");
  const { status, data } = await post("/api/check-lot", { parkingLotId: lot });
  busy($("btnLot"), false);
  if (status === 200 && data.ok) {
    LOT = lot;
    const d = data.detail || {};
    const name = d.parkingLotName || d.name || d.lotName || "(이름 정보 없음)";
    $("lotName").textContent = name + " (" + lot + ")";
    goStep(2);
    $("acc").focus();
  } else {
    setMsg($("msgLot"), data.error || "주차장 조회에 실패했습니다.", "err");
  }
};

// ---- ② 스토어 로그인 ----------------------------------------------------
$("btnBack1").onclick = () => goStep(1);

$("btnLogin").onclick = async () => {
  const acc = $("acc").value.trim();
  const pw = $("pw").value;
  if (!acc || !pw) return setMsg($("msgLogin"), "아이디와 비밀번호를 입력해 주세요.", "err");
  busy($("btnLogin"), true, "로그인 중…");
  setMsg($("msgLogin"), "");
  const { status, data } = await post("/api/login", {
    parkingLotId: LOT, storeAccountId: acc, password: pw,
  });
  busy($("btnLogin"), false);
  if (status === 200 && data.ok) {
    $("pw").value = "";
    $("who").textContent = data.accountName || data.storeAccountId;
    $("lotBadge").textContent = data.parkingLotId;
    goStep(3);
    loadTickets();
  } else {
    setMsg($("msgLogin"), data.error || "로그인에 실패했습니다.", "err");
  }
};
$("pw").addEventListener("keydown", (e) => { if (e.key === "Enter") $("btnLogin").click(); });

// ---- ③ 할인권 조회 ------------------------------------------------------
$("btnTickets").onclick = loadTickets;

async function loadTickets() {
  busy($("btnTickets"), true, "불러오는 중…");
  setMsg($("msgTickets"), "");
  const { status, data } = await get("/api/tickets");
  busy($("btnTickets"), false);
  if (status === 200 && data.ok) {
    renderTickets(data.tickets);
    setMsg($("msgTickets"), "", "ok");
  } else {
    $("ticketBox").innerHTML = "";
    if (status === 401) { setMsg($("msgTickets"), "세션이 만료되었습니다. 다시 로그인해 주세요.", "err"); goStep(2); }
    else setMsg($("msgTickets"), data.error || "할인권 조회에 실패했습니다.", "err");
  }
}

// 응답 형태를 모르는 상태라 흔한 위치에서 목록을 최대한 유연하게 찾아 표로 그린다.
function extractList(payload) {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== "object") return [];
  for (const key of ["tickets", "list", "content", "items", "data", "result"]) {
    const v = payload[key];
    if (Array.isArray(v)) return v;
    if (v && typeof v === "object") {
      const inner = extractList(v);
      if (inner.length) return inner;
    }
  }
  return [];
}

function renderTickets(payload) {
  const list = extractList(payload);
  const box = $("ticketBox");
  if (!list.length) {
    box.innerHTML =
      '<div class="empty">표시할 할인권이 없거나 응답 형식이 예상과 다릅니다. 아래 원본 응답을 확인해 주세요.</div>' +
      rawBlock(payload);
    return;
  }
  const cols = Object.keys(list[0]).slice(0, 6);
  const head = cols.map((c) => `<th>${esc(c)}</th>`).join("");
  const rows = list
    .map((row) => "<tr>" + cols.map((c) => `<td>${esc(fmt(row[c]))}</td>`).join("") + "</tr>")
    .join("");
  box.innerHTML =
    `<table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>` +
    `<div class="kv" style="margin-top:8px">총 ${list.length}건</div>` +
    rawBlock(payload);
}

function rawBlock(payload) {
  return (
    "<details><summary>원본 응답(JSON) 보기</summary><pre>" +
    esc(JSON.stringify(payload, null, 2)) +
    "</pre></details>"
  );
}

function fmt(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---- 로그아웃 ----------------------------------------------------------
$("btnLogout").onclick = async () => {
  await post("/api/logout", {});
  LOT = "";
  $("lot").value = ""; $("acc").value = ""; $("pw").value = "";
  $("ticketBox").innerHTML = "";
  setMsg($("msgLogin"), ""); setMsg($("msgTickets"), "");
  goStep(1);
};
