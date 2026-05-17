// Trait toggles
document.querySelectorAll('.trait').forEach(t =>
    t.addEventListener('click', () => t.classList.toggle('on'))
);

// Segmented control (mode picker, length picker, …)
document.querySelectorAll('.seg').forEach(seg =>
  seg.querySelectorAll('.seg-item').forEach(item =>
    item.addEventListener('click', () => {
      seg.querySelectorAll('.seg-item').forEach(x => x.classList.remove('on'));
      item.classList.add('on');
    })
  )
);

// Difficulty slider
const track = document.getElementById('diff-track');
const fill  = document.getElementById('diff-fill');
const knob  = document.getElementById('diff-knob');
const label = document.getElementById('diff-label');
const labels = ['Gentle', 'Balanced', 'Challenging', 'Brutal'];
let difficultyPct = 60;

function setDifficulty(pct) {
  difficultyPct = Math.max(0, Math.min(100, pct));
  fill.style.width = difficultyPct + '%';
  knob.style.left  = difficultyPct + '%';
  label.textContent = labels[Math.min(3, Math.floor(difficultyPct / 25))];
}

track.addEventListener('click', e => {
  const r = track.getBoundingClientRect();
  setDifficulty(((e.clientX - r.left) / r.width) * 100);
});

// Character count
function updateCount(ta) {
  document.getElementById('char-count').textContent =
    ta.value.length.toLocaleString() + ' / 2,000';
}

// ── File uploads ─────────────────────────────────────────────────
let materialText = '';
let materialImages = [];     // base64 images for vision
let materialDocuments = [];  // [{name, data:base64}] for server-side extraction
const fileInput = document.getElementById('file-input');
const fileListEl = document.getElementById('file-list');

const DOC_EXTS = ['pdf', 'docx', 'pptx', 'xlsx'];
const IMAGE_EXTS = ['jpg', 'jpeg', 'png', 'webp', 'gif'];
const TEXT_EXTS = ['txt', 'md', 'csv'];

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      // Strip "data:.../...;base64," prefix — backend wants raw base64
      const comma = result.indexOf(',');
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

if (fileInput && fileListEl) {
  fileInput.addEventListener('change', async () => {
    const files = [...fileInput.files];
    fileListEl.innerHTML = '';
    const chunks = [];
    const images = [];
    const documents = [];
    for (const file of files) {
      const ext = file.name.split('.').pop().toLowerCase();
      const isImage = file.type.startsWith('image/') || IMAGE_EXTS.includes(ext);
      const isDoc   = DOC_EXTS.includes(ext);
      const isText  = TEXT_EXTS.includes(ext) || file.type.startsWith('text/');

      const item = document.createElement('div');
      item.className = 'file-item';
      const label = isImage ? 'vision'
                  : isDoc   ? 'extracted'
                  : isText  ? 'included'
                  : 'name only';
      item.innerHTML = `<span>${file.name}</span><small>${label}</small>`;
      fileListEl.appendChild(item);

      try {
        if (isImage) {
          images.push(await fileToBase64(file));
        } else if (isDoc) {
          documents.push({ name: file.name, data: await fileToBase64(file) });
        } else if (isText) {
          chunks.push(`--- ${file.name} ---\n${await file.text()}`);
        } else {
          chunks.push(`Uploaded file: ${file.name} (${file.type || 'unknown type'}).`);
        }
      } catch (e) {
        console.error('Encode failed for', file.name, e);
      }
    }
    materialText = chunks.join('\n\n');
    materialImages = images;
    materialDocuments = documents;
  });
}

// ── Loading overlay ──────────────────────────────────────────────

let _loadTimer = null;
let _loadStartTime = 0;

function showLoadingOverlay() {
  const overlay = document.getElementById('loading-overlay');
  overlay.classList.add('lo-open');
  // Double rAF: first frame applies display:flex, second triggers the opacity transition
  requestAnimationFrame(() => requestAnimationFrame(() => {
    overlay.classList.add('active');
  }));
  _loadStartTime = Date.now();
  _loadTimer = setInterval(() => {
    const el = document.getElementById('lo-timer');
    if (el) el.textContent = Math.floor((Date.now() - _loadStartTime) / 1000) + 's';
  }, 1000);
}

function hideLoadingOverlay() {
  clearInterval(_loadTimer);
  _loadTimer = null;
  const overlay = document.getElementById('loading-overlay');
  overlay.classList.remove('active');
  overlay.classList.add('fade-out');
  setTimeout(() => overlay.classList.remove('lo-open', 'fade-out'), 700);
}

const _STAGE_ICONS = [
  '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  '<path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="2"/><path d="M9 12h6M9 16h4"/>',
  '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
];

function resetLoadingOverlay() {
  clearInterval(_loadTimer);
  _loadTimer = null;
  const overlay = document.getElementById('loading-overlay');
  overlay.classList.remove('lo-open', 'active', 'fade-out');
  [1, 2, 3].forEach((n, i) => {
    const el = document.getElementById(`lo-stage-${n}`);
    if (!el) return;
    el.classList.remove('active', 'done');
    const svg = el.querySelector('.lo-stage-icon svg');
    if (svg) svg.innerHTML = _STAGE_ICONS[i];
  });
  const fill = document.getElementById('lo-progress-fill');
  if (fill) fill.style.width = '0';
  const sub = document.getElementById('lo-subtitle');
  if (sub) sub.textContent = 'Preparing your investigation…';
}

function setLoadStageActive(n) {
  const el = document.getElementById(`lo-stage-${n}`);
  if (el) {
    el.classList.remove('done');
    el.classList.add('active');
  }
}

function setLoadStageDone(n) {
  const el = document.getElementById(`lo-stage-${n}`);
  if (!el) return;
  el.classList.remove('active');
  el.classList.add('done');
  // Swap icon to checkmark
  const svg = el.querySelector('.lo-stage-icon svg');
  if (svg) {
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.innerHTML = '<polyline points="20 6 9 17 4 12" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>';
  }
}

function setLoadProgress(pct) {
  const el = document.getElementById('lo-progress-fill');
  if (el) el.style.width = Math.min(100, pct) + '%';
}

function setLoadSubtitle(text) {
  const el = document.getElementById('lo-subtitle');
  if (el) el.textContent = text;
}

// ── Main send function ───────────────────────────────────────────

async function send() {
  const topic = document.getElementById('topic-ta').value.trim();
  if (!topic) {
    document.getElementById('topic-ta').focus();
    return;
  }

  resetLoadingOverlay();
  showLoadingOverlay();

  const payload = {
    teacher: {
      name:        document.getElementById('teacher-name').value.trim(),
      role:        document.getElementById('teacher-role').value.trim(),
      personality: document.getElementById('teacher-personality').value.trim(),
      traits:      [...document.querySelectorAll('.trait.on')].map(t => t.textContent.trim()),
    },
    lesson: {
      topic,
      mode:        'auto',  // backend picks Cold Case / Murder / Conspiracy / Heist
      language:    document.getElementById('lesson-language').value,
      length:      document.getElementById('lesson-length').value,
      difficulty:  difficultyPct / 100,
      school_type: document.getElementById('lesson-school-type').value,
      grade:       document.getElementById('lesson-grade').value,
    },
    material:  materialText,
    images:    materialImages,
    documents: materialDocuments,
  };

  try {
    const response = await fetch('/api/work/stream', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail ?? response.statusText);
    }

    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let sseBuffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      sseBuffer += decoder.decode(value, { stream: true });
      const events = sseBuffer.split('\n\n');
      sseBuffer = events.pop() ?? '';

      for (const event of events) {
        const line = event.trim();
        if (!line.startsWith('data: ')) continue;
        let data;
        try { data = JSON.parse(line.slice(6)); } catch { continue; }

        if (data.type === 'progress') {
          setLoadStageActive(data.stage);
          setLoadSubtitle(data.label);
          setLoadProgress((data.stage - 1) * 30 + 5);

        } else if (data.type === 'stage_done') {
          setLoadStageDone(data.stage);
          setLoadProgress(data.stage * 33);
          await new Promise(r => setTimeout(r, 900));

        } else if (data.type === 'complete') {
          setLoadProgress(100);
          setLoadSubtitle('Case file compiled — entering the investigation…');
          sessionStorage.setItem('mindheist_blueprint', JSON.stringify(data.blueprint));
          await new Promise(r => setTimeout(r, 2000));
          hideLoadingOverlay();
          await new Promise(r => setTimeout(r, 750));
          window.location.href = '/chat.html';
          return;

        } else if (data.type === 'error') {
          throw new Error(data.message);
        }
      }
    }

  } catch (e) {
    resetLoadingOverlay();
    alert('Error opening the case: ' + e.message);
  }
}
