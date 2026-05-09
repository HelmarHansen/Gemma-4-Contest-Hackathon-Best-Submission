// Trait toggles
document.querySelectorAll('.trait').forEach(t =>
    t.addEventListener('click', () => t.classList.toggle('on'))
);

// Segmented control
document.querySelectorAll('.seg').forEach(seg =>
seg.querySelectorAll('.seg-item').forEach(item =>
    item.addEventListener('click', () => {
    seg.querySelectorAll('.seg-item').forEach(x => x.classList.remove('on'));
    item.classList.add('on');
    })
)
);

// Project selection
document.querySelectorAll('.project').forEach(p =>
p.addEventListener('click', () => {
    document.querySelectorAll('.project').forEach(x => x.classList.remove('active'));
    p.classList.add('active');
})
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

async function send() {
    const btn = document.querySelector('.btn-primary');
    btn.disabled = true;
    btn.textContent = 'Generating…';

    const payload = {
        teacher: {
            name:        document.getElementById('teacher-name').value.trim(),
            role:        document.getElementById('teacher-role').value.trim(),
            personality: document.getElementById('teacher-personality').value.trim(),
            traits:      [...document.querySelectorAll('.trait.on')].map(t => t.textContent.trim()),
        },
        lesson: {
            topic:      document.getElementById('topic-ta').value.trim(),
            mode:       document.querySelector('.seg-item.on')?.textContent.trim() ?? '',
            language:   document.getElementById('lesson-language').value,
            length:     document.getElementById('lesson-length').value,
            difficulty: difficultyPct / 100,
        },
        material: '',
    };

    try {
        const res = await fetch('/api/work', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload),
        });

        if (!res.ok) {
            const err = await res.json();
            alert('Error: ' + (err.detail ?? res.statusText));
            return;
        }

        const data = await res.json();
        console.log('Blueprint:', data);
        // TODO: navigate to game page with session data
        alert('Blueprint ready! Session ID: ' + data.session_id);
    } catch (e) {
        alert('Network error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4l14 8-14 8z" fill="currentColor"/></svg> Begin roleplay <span class="kbd">⏎</span>';
    }
}
