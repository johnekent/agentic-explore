const slots = ["top", "left", "right", "bottom"];
const tray = document.getElementById("tray");
const target = document.getElementById("target");
const mode = document.getElementById("mode");
const status = document.getElementById("status");

const prepared = {
  "prepared-1": { top: "assets/gallery_top.svg", left: "assets/gallery_left.svg", right: "assets/gallery_right.svg", bottom: "assets/gallery_bottom.svg" },
  "prepared-2": { top: "assets/metro_top.svg", left: "assets/metro_left.svg", right: "assets/metro_right.svg", bottom: "assets/metro_bottom.svg" }
};

function generatedPiece(position) {
  const lines = {
    top: "M10,80 L100,20 L190,80",
    left: "M170,10 L30,70 L170,130",
    right: "M30,10 L170,70 L30,130",
    bottom: "M10,20 L100,80 L190,20"
  };
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 140'>
    <rect width='200' height='140' fill='white' stroke='black'/>
    <path d='${lines[position]}' stroke='black' stroke-width='6' fill='none'/>
    <path d='M20,120 L100,60 L180,120' stroke='black' stroke-width='2' fill='none'/>
  </svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

let answerKey = {};

function createPiece(slotName, src) {
  const piece = document.createElement("div");
  piece.className = "piece";
  piece.draggable = true;
  piece.dataset.answer = slotName;
  piece.innerHTML = `<img alt='${slotName} hallway piece' src='${src}'/>`;
  piece.addEventListener("dragstart", (e) => e.dataTransfer.setData("text/plain", slotName));
  return piece;
}

function buildRound() {
  answerKey = {};
  tray.innerHTML = "";
  for (const slot of target.querySelectorAll(".slot")) {
    slot.classList.remove("correct", "wrong");
    slot.innerHTML = slot.dataset.slot.toUpperCase();
  }

  slots.forEach((s) => {
    answerKey[s] = mode.value === "generated" ? generatedPiece(s) : prepared[mode.value][s];
    tray.appendChild(createPiece(s, answerKey[s]));
  });

  [...tray.children]
    .sort(() => Math.random() - 0.5)
    .forEach((c) => tray.appendChild(c));

  status.textContent = "Drag pieces into their perspective slots.";
}

function checkWin() {
  const ok = [...target.querySelectorAll(".slot")].every((slot) => {
    const p = slot.querySelector(".piece");
    return p && p.dataset.answer === slot.dataset.slot;
  });
  status.textContent = ok ? "Correct perspective arrangement ✅" : "Keep training your perspective sense.";
}

tray.addEventListener("dragover", (e) => e.preventDefault());
tray.addEventListener("drop", (e) => {
  e.preventDefault();
  const key = e.dataTransfer.getData("text/plain");
  const piece = document.querySelector(`.piece[data-answer='${key}']`);
  if (piece) tray.appendChild(piece);
  checkWin();
});

for (const slot of target.querySelectorAll(".slot")) {
  slot.addEventListener("dragover", (e) => e.preventDefault());
  slot.addEventListener("drop", (e) => {
    e.preventDefault();
    const key = e.dataTransfer.getData("text/plain");
    const piece = document.querySelector(`.piece[data-answer='${key}']`);
    if (!piece) return;
    slot.appendChild(piece);
    const correct = key === slot.dataset.slot;
    slot.classList.toggle("correct", correct);
    slot.classList.toggle("wrong", !correct);
    checkWin();
  });
}

document.getElementById("new-round").addEventListener("click", buildRound);
mode.addEventListener("change", buildRound);

buildRound();
