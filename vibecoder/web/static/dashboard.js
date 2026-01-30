// VibeCoder Dashboard JavaScript

const API_BASE = '/api';
let ws = null;
let logs = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initModals();
    initForms();
    loadTasks();
    loadApprovals();
    connectWebSocket();
});

// Tab switching
function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            tab.classList.add('active');
            document.getElementById(`${tab.dataset.tab}-tab`).classList.add('active');
        });
    });

    // Refresh buttons
    document.getElementById('refresh-tasks-btn').addEventListener('click', loadTasks);
    document.getElementById('refresh-approvals-btn').addEventListener('click', loadApprovals);
    document.getElementById('clear-logs-btn').addEventListener('click', clearLogs);

    // Filters
    document.getElementById('task-filter').addEventListener('change', loadTasks);
    document.getElementById('log-filter').addEventListener('change', filterLogs);
}

// Modal handling
function initModals() {
    // Create task modal
    const createBtn = document.getElementById('create-task-btn');
    const taskModal = document.getElementById('task-modal');
    const detailModal = document.getElementById('task-detail-modal');

    createBtn.addEventListener('click', () => {
        taskModal.style.display = 'block';
    });

    document.querySelectorAll('.close').forEach(btn => {
        btn.addEventListener('click', () => {
            taskModal.style.display = 'none';
            detailModal.style.display = 'none';
        });
    });

    window.addEventListener('click', (e) => {
        if (e.target === taskModal) taskModal.style.display = 'none';
        if (e.target === detailModal) detailModal.style.display = 'none';
    });
}

// Form handling
function initForms() {
    document.getElementById('task-form').addEventListener('submit', async (e) => {
        e.preventDefault();

        const requirements = document.getElementById('task-requirements').value
            .split('\n')
            .filter(r => r.trim());

        const verification = document.getElementById('task-verification').value
            .split('\n')
            .filter(c => c.trim());

        const taskData = {
            name: document.getElementById('task-name').value,
            description: document.getElementById('task-description').value,
            requirements: requirements,
            verification_commands: verification,
            working_directory: document.getElementById('task-workdir').value,
            max_iterations: parseInt(document.getElementById('task-iterations').value),
            timeout_per_iteration: parseInt(document.getElementById('task-timeout').value),
            auto_queue: true
        };

        try {
            const response = await fetch(`${API_BASE}/tasks/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });

            if (response.ok) {
                document.getElementById('task-modal').style.display = 'none';
                document.getElementById('task-form').reset();
                loadTasks();
            } else {
                const error = await response.json();
                alert(`Error: ${error.detail}`);
            }
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    });
}

// Load tasks
async function loadTasks() {
    const filter = document.getElementById('task-filter').value;
    const url = filter ? `${API_BASE}/tasks/?status=${filter}` : `${API_BASE}/tasks/`;

    try {
        const response = await fetch(url);
        const tasks = await response.json();

        const container = document.getElementById('tasks-list');

        if (tasks.length === 0) {
            container.innerHTML = '<div class="empty-state">No tasks found</div>';
            return;
        }

        container.innerHTML = tasks.map(task => `
            <div class="task-card" onclick="showTaskDetail('${task.id}')">
                <div class="task-card-header">
                    <div>
                        <div class="task-name">${escapeHtml(task.name)}</div>
                        <div class="task-id">${task.id}</div>
                    </div>
                    <span class="task-status ${task.status}">${task.status}</span>
                </div>
                ${task.description ? `<div class="task-description">${escapeHtml(task.description.substring(0, 150))}${task.description.length > 150 ? '...' : ''}</div>` : ''}
                <div class="task-meta">
                    <span>Iterations: ${task.current_iteration}/${task.max_iterations}</span>
                    <span>Files: ${task.artifacts.length}</span>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading tasks:', err);
    }
}

// Show task detail
async function showTaskDetail(taskId) {
    try {
        const [taskRes, iterationsRes] = await Promise.all([
            fetch(`${API_BASE}/tasks/${taskId}`),
            fetch(`${API_BASE}/tasks/${taskId}/iterations`)
        ]);

        const task = await taskRes.json();
        const iterations = await iterationsRes.json();

        document.getElementById('detail-task-name').textContent = task.name;

        const content = document.getElementById('task-detail-content');
        content.innerHTML = `
            <div class="detail-section">
                <h3>Status</h3>
                <div class="detail-content">
                    <span class="task-status ${task.status}">${task.status}</span>
                    <span style="margin-left: 16px;">Progress: ${task.current_iteration}/${task.max_iterations} iterations</span>
                </div>
            </div>

            <div class="detail-section">
                <h3>Description</h3>
                <div class="detail-content">${escapeHtml(task.description) || '(none)'}</div>
            </div>

            <div class="detail-section">
                <h3>Requirements</h3>
                <div class="detail-content">
                    <ul class="detail-list">
                        ${task.requirements.map(r => `<li>- ${escapeHtml(r)}</li>`).join('') || '<li>(none)</li>'}
                    </ul>
                </div>
            </div>

            <div class="detail-section">
                <h3>Verification Commands</h3>
                <div class="detail-content">
                    <ul class="detail-list">
                        ${task.verification_commands.map(c => `<li>$ ${escapeHtml(c)}</li>`).join('') || '<li>(none)</li>'}
                    </ul>
                </div>
            </div>

            <div class="detail-section">
                <h3>Artifacts</h3>
                <div class="detail-content">
                    <ul class="detail-list">
                        ${task.artifacts.map(a => `<li>${escapeHtml(a)}</li>`).join('') || '<li>(none)</li>'}
                    </ul>
                </div>
            </div>

            <div class="detail-section">
                <h3>Iterations</h3>
                <div class="detail-content">
                    ${iterations.length === 0 ? '<p>No iterations yet</p>' : iterations.map(it => `
                        <div class="iteration-item ${it.verification_passed ? 'iteration-passed' : 'iteration-failed'}">
                            <div class="iteration-header">
                                <strong>Iteration ${it.iteration_number}</strong>
                                <span>${it.verification_passed ? 'PASSED' : 'FAILED'}</span>
                            </div>
                            <div>Files modified: ${it.files_modified.length}</div>
                            ${it.feedback_generated ? `<details><summary>Feedback</summary><pre>${escapeHtml(it.feedback_generated)}</pre></details>` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>

            <div class="detail-section">
                <h3>Actions</h3>
                <div style="display: flex; gap: 8px;">
                    ${task.status === 'pending' ? `<button class="btn btn-primary" onclick="queueTask('${task.id}')">Add to Queue</button>` : ''}
                    ${['pending', 'running', 'needs_approval'].includes(task.status) ? `<button class="btn btn-danger" onclick="cancelTask('${task.id}')">Cancel</button>` : ''}
                    <button class="btn btn-danger" onclick="deleteTask('${task.id}')">Delete</button>
                </div>
            </div>
        `;

        document.getElementById('task-detail-modal').style.display = 'block';
    } catch (err) {
        console.error('Error loading task detail:', err);
    }
}

// Task actions
async function cancelTask(taskId) {
    if (!confirm('Are you sure you want to cancel this task?')) return;

    try {
        await fetch(`${API_BASE}/tasks/${taskId}/cancel`, { method: 'POST' });
        document.getElementById('task-detail-modal').style.display = 'none';
        loadTasks();
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task? This cannot be undone.')) return;

    try {
        await fetch(`${API_BASE}/tasks/${taskId}`, { method: 'DELETE' });
        document.getElementById('task-detail-modal').style.display = 'none';
        loadTasks();
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

async function queueTask(taskId) {
    try {
        await fetch(`${API_BASE}/tasks/${taskId}/queue`, { method: 'POST' });
        loadTasks();
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

// Load approvals
async function loadApprovals() {
    try {
        const response = await fetch(`${API_BASE}/approvals/`);
        const approvals = await response.json();

        const container = document.getElementById('approvals-list');

        if (approvals.length === 0) {
            container.innerHTML = '<div class="empty-state">No pending approvals</div>';
            return;
        }

        container.innerHTML = approvals.map(approval => `
            <div class="approval-card">
                <div class="approval-header">
                    <span class="approval-type">${approval.action_type}</span>
                    <span>Task: ${approval.task_id.substring(0, 8)}</span>
                </div>
                <div class="approval-description">${escapeHtml(approval.description)}</div>
                <div class="approval-details">${JSON.stringify(approval.details, null, 2)}</div>
                <div class="approval-actions">
                    <button class="btn btn-success" onclick="approveAction(${approval.id})">Approve</button>
                    <button class="btn btn-danger" onclick="denyAction(${approval.id})">Deny</button>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading approvals:', err);
    }
}

async function approveAction(approvalId) {
    try {
        await fetch(`${API_BASE}/approvals/${approvalId}/approve`, { method: 'POST' });
        loadApprovals();
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

async function denyAction(approvalId) {
    try {
        await fetch(`${API_BASE}/approvals/${approvalId}/deny`, { method: 'POST' });
        loadApprovals();
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

// WebSocket connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);

        if (message.type === 'status') {
            updateStatus(message.data);
        } else if (message.type === 'log') {
            addLog(message.data);
        }
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function updateStatus(status) {
    const badge = document.getElementById('queue-status');
    badge.textContent = status.status;
    badge.className = `status-badge ${status.status}`;

    document.getElementById('pending-count').textContent = status.pending_count;
    document.getElementById('running-count').textContent = status.running_count;
    document.getElementById('completed-count').textContent = status.completed_count;
    document.getElementById('failed-count').textContent = status.failed_count;
}

function addLog(log) {
    logs.unshift(log);
    if (logs.length > 500) logs.pop();
    renderLogs();
}

function renderLogs() {
    const filter = document.getElementById('log-filter').value;
    const filtered = filter ? logs.filter(l => l.level === filter) : logs;

    const container = document.getElementById('logs-container');
    container.innerHTML = filtered.map(log => `
        <div class="log-entry">
            <span class="log-timestamp">${formatTime(log.created_at)}</span>
            <span class="log-level ${log.level}">${log.level}</span>
            <span class="log-message">${escapeHtml(log.message)}</span>
            ${log.task_id ? `<span class="log-task">[${log.task_id.substring(0, 8)}]</span>` : ''}
        </div>
    `).join('');
}

function filterLogs() {
    renderLogs();
}

function clearLogs() {
    logs = [];
    renderLogs();
}

// Utilities
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString();
}
