const traitButtons = document.querySelectorAll(".trait");

traitButtons.forEach((trait) => {
  trait.addEventListener("click", () => {
    trait.classList.toggle("on");
  });
});

const segmentedControls = document.querySelectorAll(".seg");

segmentedControls.forEach((seg) => {
  const items = seg.querySelectorAll(".seg-item");

  items.forEach((item) => {
    item.addEventListener("click", () => {
      items.forEach((x) => x.classList.remove("on"));
      item.classList.add("on");
    });
  });
});

const difficultyButtons = document.querySelectorAll(
  ".difficulty .seg-item"
);

const difficultyMap = {
  Gentle: 0.25,
  Balanced: 0.5,
  Hard: 0.75,
  Brutal: 1.0,
};

let difficultyValue = 0.5;
let materialText = "";

difficultyButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    difficultyButtons.forEach((b) => b.classList.remove("on"));

    btn.classList.add("on");

    difficultyValue = difficultyMap[
      btn.textContent.trim()
    ] || 0.5;
  });
});

function updateCount(textarea) {
  document.getElementById("char-count").textContent =
    textarea.value.length.toLocaleString() + " / 2,000";
}

const fileInput = document.getElementById("file-input");
const fileList = document.getElementById("file-list");

fileInput.addEventListener("change", async () => {
  const files = [...fileInput.files];

  const chunks = [];

  fileList.innerHTML = "";

  for (const file of files) {
    const ext = file.name.split(".").pop().toLowerCase();

    const canRead =
      ["txt", "md", "csv"].includes(ext) ||
      file.type.startsWith("text/");

    const item = document.createElement("div");

    item.className = "file-item";

    item.innerHTML = `
      <span>${file.name}</span>
      <small>${canRead ? "included" : "name only"}</small>
    `;

    fileList.appendChild(item);

    if (canRead) {
      chunks.push(
        `--- ${file.name} ---\n${await file.text()}`
      );
    } else {
      chunks.push(
        `Uploaded file: ${file.name} (${file.type || "unknown type"}).`
      );
    }
  }

  materialText = chunks.join("\n\n");
});

async function send() {
  const btn = document.querySelector(".btn-primary");

  btn.disabled = true;
  btn.textContent = "Generating...";

  try {
    const payload = {
      teacher: {
        name: document
          .getElementById("teacher-name")
          .value
          .trim(),

        role: document
          .getElementById("teacher-role")
          .value
          .trim(),

        personality: document
          .getElementById("teacher-personality")
          .value
          .trim(),

        traits: [...document.querySelectorAll(".trait.on")]
          .map((t) => t.textContent.trim()),
      },

      lesson: {
        topic: document
          .getElementById("topic-ta")
          .value
          .trim(),

        mode: document
          .querySelector(".seg-item.on")
          ?.textContent
          .trim() ?? "",

        language: document
          .getElementById("lesson-language")
          .value,

        length: document
          .getElementById("lesson-length")
          .value,

        difficulty: difficultyValue,

        school_type: document
          .getElementById("lesson-school")
          .value
          .trim(),

        grade: document
          .getElementById("lesson-grade")
          .value
          .trim(),
      },

      material: materialText,
    };

    const response = await fetch("/api/work", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error("Failed to generate case");
    }

    const blueprint = await response.json();

    sessionStorage.setItem(
      "mindheist_blueprint",
      JSON.stringify(blueprint)
    );

    window.location.href = "/chat.html";
  }
  catch (err) {
    console.error(err);

    alert("Failed to generate case.");
  }
  finally {
    btn.disabled = false;
    btn.textContent = "Generate Case";
  }
}
