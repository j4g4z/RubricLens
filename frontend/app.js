/* RubricLens — Frontend Application Logic */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
    currentRubricId: null,
    currentSubmissionId: null,
    editingRubricId: null,
    criteria: [],
};

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

const API = '/api';

async function apiFetch(path, options = {}) {
    try {
        const res = await fetch(`${API}${path}`, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Request failed');
        }
        // Handle non-JSON responses (e.g., file downloads)
        const contentType = res.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return res.json();
        }
        return res;
    } catch (err) {
        showAlert(err.message, 'error');
        throw err;
    }
}

function showAlert(message, type = 'info') {
    const area = document.getElementById('alert-area');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    area.prepend(alert);
    setTimeout(() => alert.remove(), 5000);
}

function showLoading(message = 'Processing...') {
    document.getElementById('loading-message').textContent = message;
    document.getElementById('loading-overlay').classList.add('active');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.remove('active');
}

function statusBadge(status) {
    const cls = status === 'Missing' ? 'status-missing' :
                status === 'Partial' ? 'status-partial' : 'status-strong';
    return `<span class="status-badge ${cls}">${status}</span>`;
}

function strengthBar(value) {
    const pct = Math.round(value * 100);
    const color = value > 0.25 ? 'var(--green)' : value > 0.1 ? 'var(--amber)' : 'var(--accent-red)';
    return `<span class="strength-bar"><span class="strength-fill" style="width:${pct}%; background:${color};"></span></span> ${pct}%`;
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.nav-tab').forEach(t => {
            t.classList.remove('active');
            t.setAttribute('aria-selected', 'false');
        });
        tab.classList.add('active');
        tab.setAttribute('aria-selected', 'true');

        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById(`view-${tab.dataset.view}`).classList.add('active');

        // Refresh data when switching views
        if (tab.dataset.view === 'rubrics') loadRubrics();
        if (tab.dataset.view === 'draft') { loadRubricSelect(); loadSubmissions(); }
    });
});

function switchToView(viewName) {
    document.querySelectorAll('.nav-tab').forEach(t => {
        const isTarget = t.dataset.view === viewName;
        t.classList.toggle('active', isTarget);
        t.setAttribute('aria-selected', isTarget.toString());
    });
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`view-${viewName}`).classList.add('active');
}

// ---------------------------------------------------------------------------
// Rubric List
// ---------------------------------------------------------------------------

async function loadRubrics() {
    const rubrics = await apiFetch('/rubrics');
    const list = document.getElementById('rubric-list');

    if (!rubrics.length) {
        list.innerHTML = `
            <div class="empty-state">
                <h3>No Rubrics Yet</h3>
                <p>Create a new rubric or load the demo rubric to get started.</p>
            </div>`;
        return;
    }

    list.innerHTML = rubrics.map(r => `
        <div class="rubric-item" data-id="${r.rubric_id}">
            <div class="rubric-info">
                <h3>${escapeHtml(r.title)}</h3>
                <span>${r.total_marks} marks</span>
            </div>
            <div class="btn-group">
                <button class="btn btn-outline btn-sm" onclick="editRubric(${r.rubric_id}); event.stopPropagation();">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteRubricConfirm(${r.rubric_id}); event.stopPropagation();">Delete</button>
            </div>
        </div>
    `).join('');

    // Click to select rubric for analysis
    list.querySelectorAll('.rubric-item').forEach(item => {
        item.addEventListener('click', () => {
            state.currentRubricId = parseInt(item.dataset.id);
            showAlert(`Rubric selected. Go to Draft Input to submit your draft.`, 'success');
            // Auto-switch to draft view
            switchToView('draft');
            loadRubricSelect();
            document.getElementById('draft-rubric-select').value = state.currentRubricId;
        });
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ---------------------------------------------------------------------------
// Rubric CRUD
// ---------------------------------------------------------------------------

document.getElementById('btn-new-rubric').addEventListener('click', () => {
    state.editingRubricId = null;
    state.criteria = [];
    document.getElementById('rubric-editor-title').textContent = 'New Rubric';
    document.getElementById('rubric-title').value = '';
    document.getElementById('rubric-marks').value = 0;
    document.getElementById('criteria-list').innerHTML = '';
    document.getElementById('rubric-editor').style.display = 'block';
});

document.getElementById('btn-cancel-rubric').addEventListener('click', () => {
    document.getElementById('rubric-editor').style.display = 'none';
});

document.getElementById('btn-add-criterion').addEventListener('click', () => {
    addCriterionEditor();
});

function addCriterionEditor(criterion = null) {
    const list = document.getElementById('criteria-list');
    const idx = list.children.length;
    const div = document.createElement('div');
    div.className = 'criterion-item';
    div.innerHTML = `
        <div class="criterion-header" onclick="this.nextElementSibling.classList.toggle('expanded')">
            <h4>${criterion ? escapeHtml(criterion.name) : 'New Criterion'}</h4>
            <button class="btn btn-danger btn-sm" onclick="this.closest('.criterion-item').remove(); event.stopPropagation();">Remove</button>
        </div>
        <div class="criterion-details ${criterion ? 'expanded' : 'expanded'}">
            <div class="form-group">
                <label class="form-label">Criterion Name</label>
                <input type="text" class="form-input crit-name" value="${criterion ? escapeHtml(criterion.name) : ''}" placeholder="e.g., Code quality">
            </div>
            <div class="form-group">
                <label class="form-label">Max Marks</label>
                <input type="number" class="form-input crit-marks" value="${criterion ? criterion.max_marks : 0}" min="0" step="0.5">
            </div>
            <div class="form-group">
                <label class="form-label">Descriptors</label>
                <div class="descriptors-list">
                    ${criterion && criterion.descriptors ? criterion.descriptors.map(d => `
                        <div class="descriptor-item">
                            <span class="level-num">L${d.level_num || d.level}</span>
                            <input type="text" class="form-input desc-text" value="${escapeHtml(d.descriptor_text || d.text || '')}" style="flex:1;">
                            <button class="btn btn-danger btn-sm" onclick="this.closest('.descriptor-item').remove()">X</button>
                        </div>
                    `).join('') : ''}
                </div>
                <button class="btn btn-outline btn-sm" onclick="addDescriptorRow(this.previousElementSibling)">+ Add Descriptor</button>
            </div>
        </div>
    `;
    list.appendChild(div);
}

function addDescriptorRow(container) {
    const count = container.children.length + 1;
    const div = document.createElement('div');
    div.className = 'descriptor-item';
    div.innerHTML = `
        <span class="level-num">L${count}</span>
        <input type="text" class="form-input desc-text" placeholder="Descriptor text" style="flex:1;">
        <button class="btn btn-danger btn-sm" onclick="this.closest('.descriptor-item').remove()">X</button>
    `;
    container.appendChild(div);
}

document.getElementById('btn-save-rubric').addEventListener('click', async () => {
    const title = document.getElementById('rubric-title').value.trim();
    const totalMarks = parseFloat(document.getElementById('rubric-marks').value) || 0;

    if (!title) {
        showAlert('Please enter a rubric title.', 'error');
        return;
    }

    try {
        showLoading('Saving rubric...');
        let rubricId;

        if (state.editingRubricId) {
            // Delete old criteria before re-adding
            const oldRubric = await apiFetch(`/rubrics/${state.editingRubricId}`);
            for (const c of oldRubric.criteria) {
                await apiFetch(`/criteria/${c.criterion_id}`, { method: 'DELETE' });
            }
            await apiFetch(`/rubrics/${state.editingRubricId}`, {
                method: 'PUT',
                body: JSON.stringify({ title, total_marks: totalMarks }),
            });
            rubricId = state.editingRubricId;
        } else {
            const res = await apiFetch('/rubrics', {
                method: 'POST',
                body: JSON.stringify({ title, total_marks: totalMarks }),
            });
            rubricId = res.rubric_id;
        }

        // Save criteria
        const criteriaItems = document.querySelectorAll('#criteria-list .criterion-item');
        for (let i = 0; i < criteriaItems.length; i++) {
            const item = criteriaItems[i];
            const name = item.querySelector('.crit-name').value.trim();
            const maxMarks = parseFloat(item.querySelector('.crit-marks').value) || 0;

            if (!name) continue;

            const descItems = item.querySelectorAll('.descriptor-item');
            const descriptors = [];
            descItems.forEach((d, j) => {
                const text = d.querySelector('.desc-text').value.trim();
                if (text) descriptors.push({ level: j + 1, text });
            });

            await apiFetch(`/rubrics/${rubricId}/criteria`, {
                method: 'POST',
                body: JSON.stringify({
                    name,
                    max_marks: maxMarks,
                    order_index: i,
                    descriptors,
                }),
            });
        }

        hideLoading();
        showAlert('Rubric saved successfully!', 'success');
        document.getElementById('rubric-editor').style.display = 'none';
        loadRubrics();
    } catch (err) {
        hideLoading();
    }
});

async function editRubric(id) {
    try {
        showLoading('Loading rubric...');
        const rubric = await apiFetch(`/rubrics/${id}`);
        state.editingRubricId = id;

        document.getElementById('rubric-editor-title').textContent = 'Edit Rubric';
        document.getElementById('rubric-title').value = rubric.title;
        document.getElementById('rubric-marks').value = rubric.total_marks;

        const list = document.getElementById('criteria-list');
        list.innerHTML = '';
        rubric.criteria.forEach(c => addCriterionEditor(c));

        document.getElementById('rubric-editor').style.display = 'block';
        hideLoading();
    } catch (err) {
        hideLoading();
    }
}

async function deleteRubricConfirm(id) {
    if (!confirm('Are you sure you want to delete this rubric? This cannot be undone.')) return;
    try {
        await apiFetch(`/rubrics/${id}`, { method: 'DELETE' });
        showAlert('Rubric deleted.', 'success');
        loadRubrics();
    } catch (err) {
        // Error already shown by apiFetch
    }
}

// Demo rubric
document.getElementById('btn-demo-rubric').addEventListener('click', async () => {
    try {
        showLoading('Loading demo rubric...');
        const res = await apiFetch('/rubrics/seed-demo', { method: 'POST' });
        hideLoading();
        showAlert('CM2020 demo rubric loaded!', 'success');
        loadRubrics();
    } catch (err) {
        hideLoading();
    }
});

// Import rubric
document.getElementById('import-rubric-file').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
        showLoading('Importing rubric...');
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch(`${API}/rubrics/import`, { method: 'POST', body: formData });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Import failed' }));
            throw new Error(err.detail);
        }

        hideLoading();
        showAlert('Rubric imported successfully!', 'success');
        loadRubrics();
    } catch (err) {
        hideLoading();
        showAlert(err.message, 'error');
    }

    e.target.value = '';
});

// ---------------------------------------------------------------------------
// Draft Input
// ---------------------------------------------------------------------------

async function loadRubricSelect() {
    const rubrics = await apiFetch('/rubrics');
    const select = document.getElementById('draft-rubric-select');
    const currentVal = select.value;

    select.innerHTML = '<option value="">-- Select a rubric --</option>';
    rubrics.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.rubric_id;
        opt.textContent = `${r.title} (${r.total_marks} marks)`;
        select.appendChild(opt);
    });

    if (state.currentRubricId) {
        select.value = state.currentRubricId;
    } else if (currentVal) {
        select.value = currentVal;
    }

    updateAnalyseButton();
}

function updateAnalyseButton() {
    const btn = document.getElementById('btn-analyse');
    const hasRubric = document.getElementById('draft-rubric-select').value;
    const hasText = document.getElementById('draft-text').value.trim().length > 0;
    const hasFile = document.getElementById('draft-file').files.length > 0;
    btn.disabled = !hasRubric || (!hasText && !hasFile);
}

// Live word count
document.getElementById('draft-text').addEventListener('input', (e) => {
    const text = e.target.value.trim();
    const words = text ? text.split(/\s+/).length : 0;
    document.getElementById('word-count').textContent = `${words} words`;
    updateAnalyseButton();
});

document.getElementById('draft-rubric-select').addEventListener('change', (e) => {
    state.currentRubricId = parseInt(e.target.value) || null;
    updateAnalyseButton();
});

// File upload display
document.getElementById('draft-file').addEventListener('change', (e) => {
    const file = e.target.files[0];
    document.getElementById('file-name').textContent = file ? file.name : '';
    updateAnalyseButton();
});

// Analyse button
document.getElementById('btn-analyse').addEventListener('click', async () => {
    const rubricId = parseInt(document.getElementById('draft-rubric-select').value);
    const title = document.getElementById('draft-title').value.trim() || 'Untitled Draft';
    const textArea = document.getElementById('draft-text');
    const fileInput = document.getElementById('draft-file');

    if (!rubricId) {
        showAlert('Please select a rubric.', 'error');
        return;
    }

    try {
        showLoading('Submitting draft...');
        let submissionId;

        if (fileInput.files.length > 0) {
            // Upload .docx
            const formData = new FormData();
            formData.append('rubric_id', rubricId);
            formData.append('title', title);
            formData.append('file', fileInput.files[0]);

            const res = await fetch(`${API}/submissions/upload`, { method: 'POST', body: formData });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
                throw new Error(err.detail);
            }
            const data = await res.json();
            submissionId = data.submission_id;
        } else {
            // Paste text
            const res = await apiFetch('/submissions', {
                method: 'POST',
                body: JSON.stringify({ rubric_id: rubricId, title, raw_text: textArea.value }),
            });
            submissionId = res.submission_id;
        }

        // Run analysis
        document.getElementById('loading-message').textContent = 'Analysing draft against rubric...';
        const report = await apiFetch(`/analyse/${submissionId}`, { method: 'POST' });

        state.currentSubmissionId = submissionId;
        hideLoading();
        showAlert('Analysis complete!', 'success');

        // Show report
        renderReport(report);
        switchToView('report');

        // Clear inputs
        textArea.value = '';
        fileInput.value = '';
        document.getElementById('file-name').textContent = '';
        document.getElementById('word-count').textContent = '0 words';

    } catch (err) {
        hideLoading();
    }
});

// Submissions list
async function loadSubmissions() {
    const subs = await apiFetch('/submissions');
    const list = document.getElementById('submissions-list');

    if (!subs.length) {
        list.innerHTML = `<div class="empty-state"><p>No previous submissions.</p></div>`;
        return;
    }

    list.innerHTML = subs.map(s => `
        <div class="rubric-item" data-id="${s.submission_id}">
            <div class="rubric-info">
                <h3>${escapeHtml(s.title)}</h3>
                <span>${s.created_at}</span>
            </div>
            <div class="btn-group">
                <button class="btn btn-primary btn-sm" onclick="viewSubmissionReport(${s.submission_id}); event.stopPropagation();">View Report</button>
                <button class="btn btn-danger btn-sm" onclick="deleteSubmissionConfirm(${s.submission_id}); event.stopPropagation();">Delete</button>
            </div>
        </div>
    `).join('');
}

async function viewSubmissionReport(submissionId) {
    try {
        showLoading('Loading report...');
        state.currentSubmissionId = submissionId;
        const report = await apiFetch(`/report/${submissionId}`);
        hideLoading();
        renderReport(report);
        switchToView('report');
    } catch (err) {
        hideLoading();
    }
}

async function deleteSubmissionConfirm(id) {
    if (!confirm('Delete this submission?')) return;
    try {
        await apiFetch(`/submissions/${id}`, { method: 'DELETE' });
        showAlert('Submission deleted.', 'success');
        loadSubmissions();
    } catch (err) {
        // Error already shown
    }
}

// ---------------------------------------------------------------------------
// Report View
// ---------------------------------------------------------------------------

function renderReport(report) {
    document.getElementById('report-empty').style.display = 'none';
    document.getElementById('report-content').style.display = 'block';

    const summary = report.summary;

    // Summary bar
    document.getElementById('summary-bar').innerHTML = `
        <div class="summary-stat">
            <div class="stat-value">${summary.total_criteria}</div>
            <div class="stat-label">Criteria</div>
        </div>
        <div class="summary-stat">
            <div class="stat-value" style="color: var(--green);">${summary.strong}</div>
            <div class="stat-label">Strong</div>
        </div>
        <div class="summary-stat">
            <div class="stat-value" style="color: var(--amber);">${summary.partial}</div>
            <div class="stat-label">Partial</div>
        </div>
        <div class="summary-stat">
            <div class="stat-value" style="color: var(--accent-red);">${summary.missing}</div>
            <div class="stat-label">Missing</div>
        </div>
        <div class="summary-stat">
            <div class="stat-value">${summary.coverage_pct}%</div>
            <div class="stat-label">Coverage</div>
        </div>
    `;

    // Top priorities
    const prioBox = document.getElementById('priorities-box');
    if (summary.top_priorities && summary.top_priorities.length > 0) {
        prioBox.style.display = 'block';
        document.getElementById('priorities-list').innerHTML = summary.top_priorities.map((p, i) => `
            <div class="priority-item">
                <strong>${i + 1}. ${escapeHtml(p.criterion_name)}</strong>
                ${statusBadge(p.status)}
                <span style="color: var(--mid-grey); font-size:0.85rem;">(${p.max_marks} marks)</span>
                <p style="font-size: 0.9rem; margin-top: 0.3rem;">${escapeHtml(p.next_action)}</p>
            </div>
        `).join('');
    } else {
        prioBox.style.display = 'none';
    }

    // Criterion cards
    document.getElementById('report-criteria').innerHTML = report.items.map(item => `
        <div class="report-criterion" id="criterion-${item.criterion_id}">
            <div class="report-criterion-header" onclick="toggleEvidence(${item.criterion_id})">
                <div class="criterion-info">
                    ${statusBadge(item.status)}
                    <strong>${escapeHtml(item.criterion_name)}</strong>
                    <span class="marks">(${item.max_marks} marks)</span>
                </div>
                <div style="display:flex; align-items:center; gap:0.75rem;">
                    ${strengthBar(item.evidence_strength)}
                    <span style="font-size:0.85rem; color: var(--mid-grey);">View Evidence</span>
                </div>
            </div>
            <div class="evidence-panel" id="evidence-${item.criterion_id}">
                <div class="rationale-box">
                    <h4>Why this status?</h4>
                    <p>${escapeHtml(item.rationale)}</p>
                </div>
                <div class="next-action-box">
                    <h4>Next Action</h4>
                    <p>${escapeHtml(item.next_action)}</p>
                </div>
                <div id="evidence-excerpts-${item.criterion_id}">
                    <p style="color: var(--mid-grey); font-size: 0.85rem;">Click to load evidence excerpts...</p>
                </div>
            </div>
        </div>
    `).join('');
}

async function toggleEvidence(criterionId) {
    const panel = document.getElementById(`evidence-${criterionId}`);
    const isExpanded = panel.classList.contains('expanded');

    if (isExpanded) {
        panel.classList.remove('expanded');
        return;
    }

    panel.classList.add('expanded');

    // Load evidence if not already loaded
    const excerpts = document.getElementById(`evidence-excerpts-${criterionId}`);
    if (excerpts.dataset.loaded) return;

    try {
        const data = await apiFetch(`/evidence/${state.currentSubmissionId}/${criterionId}`);
        excerpts.dataset.loaded = 'true';

        if (data.criterion && data.criterion.descriptors && data.criterion.descriptors.length > 0) {
            excerpts.innerHTML = `
                <h4 style="font-size:0.85rem; text-transform:uppercase; color:var(--mid-grey); margin-bottom:0.5rem;">Rubric Descriptors</h4>
                <div style="margin-bottom:0.75rem;">
                    ${data.criterion.descriptors.map((d, i) => `
                        <div class="descriptor-item"><span class="level-num">L${i + 1}</span> ${escapeHtml(d)}</div>
                    `).join('')}
                </div>
            `;
        } else {
            excerpts.innerHTML = '';
        }

        if (data.evidence && data.evidence.length > 0) {
            excerpts.innerHTML += `
                <h4 style="font-size:0.85rem; text-transform:uppercase; color:var(--mid-grey); margin-bottom:0.5rem;">Evidence Excerpts</h4>
                ${data.evidence.map(e => `
                    <div class="evidence-excerpt">
                        <p>${escapeHtml(e.snippet)}</p>
                        <div class="evidence-score">Relevance: ${(e.score * 100).toFixed(1)}%</div>
                    </div>
                `).join('')}
            `;
        } else {
            excerpts.innerHTML += `
                <div class="no-evidence">
                    No evidence found in your draft for this criterion.
                    ${data.criterion ? `The rubric expects content related to: ${escapeHtml(data.criterion.descriptors.join('; '))}` : ''}
                </div>
            `;
        }
    } catch (err) {
        excerpts.innerHTML = `<p class="no-evidence">Failed to load evidence.</p>`;
    }
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

document.getElementById('btn-export-md').addEventListener('click', async () => {
    if (!state.currentSubmissionId) return;
    try {
        const res = await fetch(`${API}/export/${state.currentSubmissionId}/markdown`);
        const blob = await res.blob();
        downloadBlob(blob, `report_${state.currentSubmissionId}.md`);
    } catch (err) {
        showAlert('Export failed.', 'error');
    }
});

document.getElementById('btn-export-pdf').addEventListener('click', async () => {
    if (!state.currentSubmissionId) return;
    try {
        const res = await fetch(`${API}/export/${state.currentSubmissionId}/pdf`);
        const blob = await res.blob();
        downloadBlob(blob, `report_${state.currentSubmissionId}.pdf`);
    } catch (err) {
        showAlert('Export failed.', 'error');
    }
});

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

loadRubrics();
