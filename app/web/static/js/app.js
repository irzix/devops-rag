document.addEventListener('alpine:init', () => {
    // Check local storage for theme
    if (localStorage.getItem('theme') === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    }

    Alpine.data('app', () => ({
        token: localStorage.getItem('token'),
        theme: localStorage.getItem('theme') || 'dark',
        sidebarOpen: false,

        init() {
            if (!this.token && window.location.pathname !== '/login') {
                window.location.href = '/login';
            }
        },

        logout() {
            localStorage.removeItem('token');
            window.location.href = '/login';
        },

        toggleTheme() {
            this.theme = this.theme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('theme', this.theme);
            if (this.theme === 'light') {
                document.documentElement.setAttribute('data-theme', 'light');
            } else {
                document.documentElement.removeAttribute('data-theme');
            }
        },

        async apiFetch(url, options = {}) {
            const headers = {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.token}`,
                ...options.headers
            };
            const response = await fetch(url, { ...options, headers });
            if (response.status === 401) {
                this.logout();
            }
            return response;
        }
    }));

    Alpine.data('dashboard', () => ({
        servers: [],
        loading: true,
        showAddModal: false,
        submitting: false,
        error: '',
        newServer: {
            name: '',
            ip_address: '',
            ssh_port: 22,
            ssh_username: '',
            ssh_auth_type: 'password',
            credential: '',
            tags: ''
        },
        
        // Summary Widget state
        summary: { total: 0, healthy: 0, degraded: 0, offline: 0 },
        
        // History Modal state
        showHistoryModal: false,
        activeServer: null,
        historyLoading: false,
        historyData: [],
        chartInstance: null,

        async init() {
            await this.fetchServers();
        },

        calculateSummary() {
            this.summary = {
                total: this.servers.length,
                healthy: this.servers.filter(s => s.status === 'healthy').length,
                degraded: this.servers.filter(s => s.status === 'degraded').length,
                offline: this.servers.filter(s => s.status === 'unreachable' || s.status === 'unknown').length,
            };
        },

        async fetchServers() {
            this.loading = true;
            try {
                const res = await this.apiFetch('/api/v1/monitoring/status');
                if (res.ok) {
                    this.servers = await res.json();
                    this.calculateSummary();
                }
            } catch (e) {
                console.error("Failed to load dashboard data", e);
            } finally {
                this.loading = false;
            }
        },

        async addServer() {
            this.error = '';
            this.submitting = true;
            try {
                const payload = { ...this.newServer };
                const res = await this.apiFetch('/api/v1/servers/', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    this.showAddModal = false;
                    // Reset form
                    this.newServer = {
                        name: '', ip_address: '', ssh_port: 22, ssh_username: '',
                        ssh_auth_type: 'password', credential: '', tags: ''
                    };
                    await this.fetchServers();
                } else {
                    const data = await res.json();
                    this.error = data.detail || 'Failed to add server';
                }
            } catch (e) {
                this.error = 'Network error occurred';
            } finally {
                this.submitting = false;
            }
        },

        async deleteServer(id) {
            if (!confirm('Are you sure you want to remove this server?')) return;
            try {
                const res = await this.apiFetch(`/api/v1/servers/${id}`, { method: 'DELETE' });
                if (res.ok) {
                    await this.fetchServers();
                }
            } catch (e) {
                console.error("Failed to delete server", e);
            }
        },

        async openHistory(server) {
            this.activeServer = server;
            this.showHistoryModal = true;
            this.historyLoading = true;
            this.historyData = [];
            
            try {
                const res = await this.apiFetch(`/api/v1/monitoring/${server.server_id}/history?limit=30`);
                if (res.ok) {
                    this.historyData = await res.json();
                    // The API returns desc order. Let's reverse it for the chart so time goes left to right.
                    this.historyData.reverse();
                    this.renderChart();
                }
            } catch(e) {
                console.error("Failed to fetch history", e);
            } finally {
                this.historyLoading = false;
            }
        },

        closeHistory() {
            this.showHistoryModal = false;
            this.activeServer = null;
            if (this.chartInstance) {
                this.chartInstance.destroy();
                this.chartInstance = null;
            }
        },

        renderChart() {
            if (this.chartInstance) {
                this.chartInstance.destroy();
            }

            // Wait for alpine to show canvas
            setTimeout(() => {
                const ctx = document.getElementById('historyChart');
                if (!ctx) return;

                const labels = this.historyData.map(d => {
                    const dt = new Date(d.checked_at);
                    return dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                });

                const cpuData = this.historyData.map(d => d.cpu_percent || 0);
                const memData = this.historyData.map(d => d.memory_percent || 0);

                this.chartInstance = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: 'CPU Usage (%)',
                                data: cpuData,
                                borderColor: 'rgba(54, 162, 235, 1)',
                                backgroundColor: 'rgba(54, 162, 235, 0.1)',
                                fill: true,
                                tension: 0.4
                            },
                            {
                                label: 'Memory Usage (%)',
                                data: memData,
                                borderColor: 'rgba(255, 99, 132, 1)',
                                backgroundColor: 'rgba(255, 99, 132, 0.1)',
                                fill: true,
                                tension: 0.4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100
                            }
                        },
                        interaction: {
                            mode: 'index',
                            intersect: false,
                        }
                    }
                });
            }, 100);
        }
    }));

    Alpine.data('chat', () => ({
        sessions: [],
        messages: [],
        input: '',
        ws: null,
        session_id: null,
        isProcessing: false,
        pendingAction: null,

        async init() {
            await this.loadSessions();
            let sid = localStorage.getItem('chat_session_id');
            if (sid && !isNaN(parseInt(sid))) {
                if (!this.sessions.find(s => s.id === parseInt(sid))) {
                    sid = null;
                }
            }

            if (!sid || isNaN(parseInt(sid))) {
                if (this.sessions.length > 0) {
                    sid = this.sessions[0].id;
                } else {
                    await this.createNewSession();
                    return;
                }
            }
            this.session_id = parseInt(sid);
            localStorage.setItem('chat_session_id', this.session_id);
            await this.loadMessages(this.session_id);
            this.connectWs();
        },

        async loadSessions() {
            try {
                const res = await this.apiFetch('/api/v1/chat/sessions');
                if (res.ok) {
                    this.sessions = await res.json();
                }
            } catch (e) {
                console.error("Failed to load sessions", e);
            }
        },

        async createNewSession() {
            try {
                const res = await this.apiFetch('/api/v1/chat/sessions', {
                    method: 'POST',
                    body: JSON.stringify({ title: 'New Chat Session' })
                });
                if (res.ok) {
                    const data = await res.json();
                    this.sessions.unshift(data);
                    await this.selectSession(data.id);
                }
            } catch (e) {
                console.error("Failed to create session", e);
            }
        },

        async loadMessages(id) {
            this.messages = [];
            try {
                const res = await this.apiFetch(`/api/v1/chat/sessions/${id}/messages`);
                if (res.ok) {
                    const msgs = await res.json();
                    this.messages = msgs.map(m => ({
                        role: m.sender === 'user' ? 'user' : 'agent',
                        content: m.content,
                        isAction: false
                    }));
                    this.scrollToBottom();
                }
            } catch(e) {
                console.error("Failed to load messages", e);
            }
        },

        async selectSession(id) {
            this.session_id = parseInt(id);
            localStorage.setItem('chat_session_id', this.session_id);
            if (this.ws) {
                this.ws.close(1000);
            }
            await this.loadMessages(this.session_id);
            this.connectWs();
        },

        connectWs() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/chat/ws?token=${this.token}`);
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'token' || data.type === 'stdout' || data.type === 'stderr') {
                    let lastMsg = this.messages.length > 0 ? this.messages[this.messages.length - 1] : null;
                    if (!lastMsg || lastMsg.role !== 'agent' || lastMsg.isAction) {
                        this.messages.push({ role: 'agent', content: '', isAction: false });
                        lastMsg = this.messages[this.messages.length - 1];
                    }
                    lastMsg.content += data.data;
                    this.scrollToBottom();
                } 
                else if (data.type === 'approval_required') {
                    this.pendingAction = data;
                    this.messages.push({
                        role: 'agent',
                        content: `⚠️ Action Requires Approval:\nServer: ${data.server_name}\nCommand: ${data.command}`,
                        isAction: true,
                        actionId: data.action_id
                    });
                    this.scrollToBottom();
                }
            };

            this.ws.onclose = (event) => {
                if (!event.wasClean && event.code !== 1000) {
                    console.log("WebSocket disconnected. Reconnecting in 3s...");
                    setTimeout(() => this.connectWs(), 3000);
                }
            };
        },

        sendMessage() {
            if (!this.input.trim() || !this.ws) return;
            
            this.messages.push({ role: 'user', content: this.input });
            this.ws.send(JSON.stringify({ 
                type: 'message', 
                content: this.input,
                session_id: this.session_id
            }));
            this.input = '';
            this.scrollToBottom();
        },

        async submitApproval(actionId, approved) {
            this.pendingAction = null;
            this.messages.push({ role: 'user', content: approved ? 'Approved ✅' : 'Rejected ❌' });
            
            // Note: Use WebSocket for approvals per router logic!
            this.ws.send(JSON.stringify({
                type: approved ? 'approve' : 'reject',
                action_id: actionId
            }));
            
            this.scrollToBottom();
        },

        scrollToBottom() {
            setTimeout(() => {
                const container = document.getElementById('chat-messages');
                if (container) container.scrollTop = container.scrollHeight;
            }, 50);
        }
    }));
});
