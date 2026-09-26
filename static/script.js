/**
 * AI Software Intelligence Copilot — Dual-Mode Workspace Architecture Script
 * Modern state-synchronized navigation & interactive graph/impact dashboards
 */

document.addEventListener("DOMContentLoaded", () => {
    // Global Workspace State
    const state = {
        activeView: "ask",
        activeRepoId: "default",
        activeGraphUrl: "",
        activeFunctionQuery: "",
        activeImpactData: null,
        sessionHistory: []
    };

    // DOM Elements — Header & Status
    const repoNameBadge = document.getElementById("repoNameBadge");
    const infoProjectName = document.getElementById("infoProjectName");
    const infoPythonFiles = document.getElementById("infoPythonFiles");
    const infoFolders = document.getElementById("infoFolders");
    const infoFunctions = document.getElementById("infoFunctions");
    const infoStatus = document.getElementById("infoStatus");
    const engineStatusBadge = document.getElementById("engineStatusBadge");

    // Summary Hero Stat Pills
    const statFiles = document.getElementById("statFiles");
    const statFunctions = document.getElementById("statFunctions");
    const statFolders = document.getElementById("statFolders");

    // Command Bar & Inputs (Ask Copilot)
    const queryInput = document.getElementById("queryInput");
    const sendBtn = document.getElementById("sendBtn");
    const clearBtn = document.getElementById("clearBtn");
    const charCountBadge = document.getElementById("charCountBadge");
    const loaderContainer = document.getElementById("loaderContainer");
    const loaderText = document.getElementById("loaderText");

    // Layout & Navigation
    const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");
    const appSidebar = document.getElementById("appSidebar");
    const emptyWorkspaceState = document.getElementById("emptyWorkspaceState");
    const toastContainer = document.getElementById("toastContainer");

    // Ask Copilot Split-View Drawer
    const askChatPane = document.getElementById("askChatPane");
    const sideCanvasDrawer = document.getElementById("sideCanvasDrawer");
    const toggleDrawerBtn = document.getElementById("toggleDrawerBtn");
    const drawerTitle = document.getElementById("drawerTitle");
    const drawerGraphIframe = document.getElementById("drawerGraphIframe");
    const drawerContent = document.getElementById("drawerContent");
    const drawerOpenDedicatedBtn = document.getElementById("drawerOpenDedicatedBtn");

    // Ask Copilot Results & Embedded Cards
    const resultsCard = document.getElementById("resultsCard");
    const queryTypeBadge = document.getElementById("queryTypeBadge");
    const subTypeBadge = document.getElementById("subTypeBadge");
    const riskBadge = document.getElementById("riskBadge");
    const impactPercBadge = document.getElementById("impactPercBadge");
    const answerContent = document.getElementById("answerContent");
    const citationsSection = document.getElementById("citationsSection");
    const citationsGrid = document.getElementById("citationsGrid");

    const graphSection = document.getElementById("graphSection");
    const graphIframe = document.getElementById("graphIframe");
    const openGraphBtn = document.getElementById("openGraphBtn");
    const openStandaloneViewBtn = document.getElementById("openStandaloneViewBtn");
    const toggleFullscreenBtn = document.getElementById("toggleFullscreenBtn");
    const fullscreenBtnText = document.getElementById("fullscreenBtnText");

    // Session Query History (Ask Copilot & Standalone Stream)
    const historySection = document.getElementById("historySection");
    const historyContainer = document.getElementById("historyContainer");
    const historyCountBadge = document.getElementById("historyCountBadge");
    const standaloneHistoryContainer = document.getElementById("standaloneHistoryContainer");

    // Standalone Views Elements
    const standaloneGraphIframe = document.getElementById("standaloneGraphIframe");
    const graphSelect = document.getElementById("graphSelect");
    const refreshGraphBtn = document.getElementById("refreshGraphBtn");
    const fullscreenGraphBtn = document.getElementById("fullscreenGraphBtn");
    const standaloneNodeSearch = document.getElementById("standaloneNodeSearch");

    const depSearchInput = document.getElementById("depSearchInput");
    const depSearchBtn = document.getElementById("depSearchBtn");
    const depResultsList = document.getElementById("depResultsList");

    const impactForm = document.getElementById("impactForm");
    const impactSearchInput = document.getElementById("impactSearchInput");
    const impactSearchBtn = document.getElementById("impactSearchBtn");
    const dashImpactFunc = document.getElementById("dashImpactFunc");
    const dashImpactRisk = document.getElementById("dashImpactRisk");
    const dashImpactPerc = document.getElementById("dashImpactPerc");
    const dashImpactSummary = document.getElementById("dashImpactSummary");
    const dashImpactCallers = document.getElementById("dashImpactCallers");

    // Repository Controls & Error Elements
    const errorCard = document.getElementById("errorCard");
    const errorMessage = document.getElementById("errorMessage");
    const repoZipInput = document.getElementById("repoZipInput");
    const repoSelect = document.getElementById("repoSelect");

    // ==========================================
    // 1. Dual-Mode View Switcher & URL Router
    // ==========================================
    function switchView(targetView, updateHash = true) {
        const validViews = ["overview", "ask", "dependencies", "impact", "graph", "history"];
        if (!validViews.includes(targetView)) targetView = "ask";

        state.activeView = targetView;

        // Update active class on view sections
        document.querySelectorAll(".workspace-view").forEach(el => {
            el.classList.remove("active");
        });

        const targetElemId = (targetView === "ask" || targetView === "askcopilot") 
            ? "viewAskCopilot" 
            : ("view" + targetView.charAt(0).toUpperCase() + targetView.slice(1));
        const activeElem = document.getElementById(targetElemId);
        if (activeElem) {
            activeElem.classList.add("active");
        }

        // Update active class on sidebar navigation links
        document.querySelectorAll(".sidebar-link").forEach(link => {
            if (link.dataset.view === targetView) {
                link.classList.add("active");
            } else {
                link.classList.remove("active");
            }
        });

        // Sync URL Hash
        if (updateHash) {
            window.location.hash = targetView;
        }

        // Trigger view-specific dynamic updates
        onViewActivated(targetView);
    }

    function onViewActivated(viewName) {
        if (viewName === "graph") {
            loadStandaloneGraph();
        } else if (viewName === "history") {
            renderStandaloneHistory();
        } else if (viewName === "dependencies" && !depResultsList.children.length) {
            fetchDependencyOverview();
        }
    }

    // Initialize View based on URL Hash
    function initViewFromHash() {
        const hash = window.location.hash.replace("#", "").toLowerCase();
        if (hash) {
            switchView(hash, false);
        } else {
            switchView("ask", false);
        }
    }

    window.addEventListener("hashchange", () => {
        const hash = window.location.hash.replace("#", "").toLowerCase();
        if (hash) switchView(hash, false);
    });

    // Sidebar navigation click delegates
    document.querySelectorAll(".sidebar-link[data-view]").forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const view = link.dataset.view;
            switchView(view);
        });
    });

    // Global Event Delegation for all view triggers (cards, buttons, links)
    document.addEventListener("click", (e) => {
        const trigger = e.target.closest("[data-view], [data-switch]");
        if (trigger) {
            const targetView = trigger.dataset.view || trigger.dataset.switch;
            if (targetView && !trigger.classList.contains("sidebar-link")) {
                e.preventDefault();
                switchView(targetView);
            }
        }
    });

    // Navigation helper to jump directly to standalone graph with node/query state
    if (openStandaloneViewBtn) {
        openStandaloneViewBtn.addEventListener("click", (e) => {
            e.preventDefault();
            switchView("graph");
        });
    }

    if (drawerOpenDedicatedBtn) {
        drawerOpenDedicatedBtn.addEventListener("click", (e) => {
            e.preventDefault();
            switchView("graph");
        });
    }

    const navToDedicatedGraphBtn = document.getElementById("navToDedicatedGraphBtn");
    if (navToDedicatedGraphBtn) {
        navToDedicatedGraphBtn.addEventListener("click", (e) => {
            e.preventDefault();
            switchView("graph");
        });
    }

    // ==========================================
    // 2. Ask Copilot Split-Pane Side Drawer Controls
    // ==========================================
    if (toggleDrawerBtn && sideCanvasDrawer) {
        toggleDrawerBtn.addEventListener("click", () => {
            toggleSideCanvasDrawer();
        });
    }

    function toggleSideCanvasDrawer(forceOpen = null) {
        if (!sideCanvasDrawer) return;
        const isCurrentlyOpen = sideCanvasDrawer.classList.contains("open");
        const shouldOpen = forceOpen !== null ? forceOpen : !isCurrentlyOpen;

        if (shouldOpen) {
            sideCanvasDrawer.classList.add("open");
            if (toggleDrawerBtn) {
                toggleDrawerBtn.classList.add("active");
                toggleDrawerBtn.title = "Collapse Side Canvas";
            }
        } else {
            sideCanvasDrawer.classList.remove("open");
            if (toggleDrawerBtn) {
                toggleDrawerBtn.classList.remove("active");
                toggleDrawerBtn.title = "Toggle Side Canvas Drawer";
            }
        }
    }

    function populateDrawerVisuals(data) {
        if (!sideCanvasDrawer) return;

        if (data.graph_url) {
            const bustUrl = data.graph_url + (data.graph_url.includes('?') ? '&' : '?') + '_t=' + Date.now();
            if (drawerGraphIframe) drawerGraphIframe.src = bustUrl;
            if (drawerTitle) drawerTitle.innerText = "Interactive Code Graph";

            if (drawerContent) {
                drawerContent.innerHTML = `
                    <div style="padding: 1rem;">
                        <h4 style="color: var(--text-main); margin-bottom: 0.5rem;">Visualization Summary</h4>
                        <p style="color: var(--text-muted); font-size: 0.85rem;">
                            Graph generated for query type <strong>${escapeHtml(data.query_type || "AST")}</strong>.
                            ${data.risk ? `<br><span class="risk-chip risk-${escapeHtml(data.risk.toLowerCase())}">Risk: ${escapeHtml(data.risk)}</span>` : ""}
                        </p>
                    </div>
                `;
            }
            toggleSideCanvasDrawer(true);
        } else if (data.risk || typeof data.impact_percentage === "number") {
            if (drawerTitle) drawerTitle.innerText = "Impact Context Drawer";
            if (drawerGraphIframe) drawerGraphIframe.src = "about:blank";

            if (drawerContent) {
                drawerContent.innerHTML = `
                    <div style="padding: 1.25rem;">
                        <h4 style="color: var(--text-main); margin-bottom: 0.75rem;">Impact & Risk Summary</h4>
                        <div style="margin-bottom: 0.75rem;">
                            ${data.risk ? `<span class="risk-chip risk-${escapeHtml(data.risk.toLowerCase())}">RISK: ${escapeHtml(data.risk)}</span> ` : ""}
                            ${typeof data.impact_percentage === "number" ? `<span class="impact-perc-chip">IMPACT: ${data.impact_percentage.toFixed(2)}%</span>` : ""}
                        </div>
                        <p style="color: var(--text-muted); font-size: 0.875rem; line-height: 1.5;">
                            ${data.answer ? escapeHtml(data.answer.substring(0, 300)) + "..." : "No additional impact details."}
                        </p>
                    </div>
                `;
            }
            toggleSideCanvasDrawer(true);
        }
    }

    // ==========================================
    // 3. Initial Status & Repo Management
    // ==========================================
    fetchRepoStatus();
    initViewFromHash();

    if (sidebarToggleBtn && appSidebar) {
        sidebarToggleBtn.addEventListener("click", () => {
            appSidebar.classList.toggle("collapsed");
        });
    }

    if (queryInput && charCountBadge) {
        queryInput.addEventListener("input", updateCharCount);
    }

    function updateCharCount() {
        const len = queryInput.value.length;
        charCountBadge.innerText = `${len} / 2000`;
        if (len > 1900) {
            charCountBadge.style.color = "var(--accent-rose)";
        } else {
            charCountBadge.style.color = "var(--text-muted)";
        }
    }

    if (sendBtn) sendBtn.addEventListener("click", handleQuerySubmit);

    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            queryInput.value = "";
            updateCharCount();
            hideError();
            showToast("Query cleared.", "info");
        });
    }

    if (repoZipInput) repoZipInput.addEventListener("change", handleRepoUpload);

    if (repoSelect) {
        repoSelect.addEventListener("change", async (e) => {
            const selectedRepoId = e.target.value;
            if (!selectedRepoId) return;
            await switchRepository(selectedRepoId);
        });
    }

    queryInput.addEventListener("keydown", (e) => {
        if ((e.key === "Enter" && !e.shiftKey) || (e.key === "Enter" && (e.ctrlKey || e.metaKey))) {
            e.preventDefault();
            handleQuerySubmit();
        }
    });

    // Fullscreen Graph Modal Handler (Ask Copilot)
    if (toggleFullscreenBtn && graphSection) {
        toggleFullscreenBtn.addEventListener("click", () => {
            const isFullscreen = graphSection.classList.toggle("fullscreen");
            if (isFullscreen) {
                if (fullscreenBtnText) fullscreenBtnText.innerText = "Exit Fullscreen";
                document.body.style.overflow = "hidden";
            } else {
                if (fullscreenBtnText) fullscreenBtnText.innerText = "Expand";
                document.body.style.overflow = "auto";
            }
        });

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && graphSection.classList.contains("fullscreen")) {
                graphSection.classList.remove("fullscreen");
                if (fullscreenBtnText) fullscreenBtnText.innerText = "Expand";
                document.body.style.overflow = "auto";
            }
        });
    }

    // Suggested Chips Handlers
    document.querySelectorAll(".suggestion-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            queryInput.value = chip.dataset.query || chip.innerText.trim();
            updateCharCount();
            handleQuerySubmit();
        });
    });

    async function fetchRepoStatus() {
        try {
            const response = await fetch("/api/status");
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();

            if (data.success || data.status === "active") {
                const projName = data.project_name || "Repository";
                if (data.active_repo_id) state.activeRepoId = data.active_repo_id;

                if (repoNameBadge) repoNameBadge.innerText = projName;
                if (infoProjectName) {
                    infoProjectName.innerText = projName;
                    infoProjectName.title = projName;
                }

                const filesCount = data.total_files ?? "-";
                const foldersCount = data.total_folders ?? "-";
                const funcsCount = data.total_functions ?? "-";

                if (infoPythonFiles) infoPythonFiles.innerText = filesCount;
                if (infoFolders) infoFolders.innerText = foldersCount;
                if (infoFunctions) infoFunctions.innerText = funcsCount;
                if (infoStatus) infoStatus.innerText = "Active";
                if (engineStatusBadge) engineStatusBadge.innerText = "Ready";

                if (statFiles) statFiles.innerText = filesCount;
                if (statFunctions) statFunctions.innerText = funcsCount;
                if (statFolders) statFolders.innerText = foldersCount;

                if (data.suggested_questions) {
                    renderSuggestedQuestions(data.suggested_questions);
                }

                if (data.repositories) {
                    renderRepoDropdown(data.repositories, data.active_repo_id);
                }
            } else {
                if (infoStatus) infoStatus.innerText = "Error";
                if (engineStatusBadge) engineStatusBadge.innerText = "Error";
            }
        } catch (err) {
            console.warn("Failed to fetch repository status:", err);
            if (repoNameBadge) repoNameBadge.innerText = "Copilot Active";
            if (infoStatus) infoStatus.innerText = "Offline";
            if (engineStatusBadge) engineStatusBadge.innerText = "Offline";
        }
    }

    async function switchRepository(repoId) {
        try {
            setLoading(true, "Switching repository context...");
            hideError();
            if (resultsCard) resultsCard.style.display = "none";
            if (graphSection) graphSection.style.display = "none";
            if (graphIframe) graphIframe.src = "about:blank";

            const response = await fetch("/api/switch_repo", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ repo_id: repoId })
            });

            const data = await response.json();

            if (!response.ok || data.success === false) {
                showError(data.error || "Failed to switch repository.");
                showToast("Failed to switch repository.", "error");
                return;
            }

            if (data.active_repo_id) state.activeRepoId = data.active_repo_id;

            if (data.repository) {
                const rName = data.repository.name;
                if (repoNameBadge) repoNameBadge.innerText = rName;
                if (infoProjectName) {
                    infoProjectName.innerText = rName;
                    infoProjectName.title = rName;
                }
                if (infoPythonFiles) infoPythonFiles.innerText = data.repository.python_files;
                if (infoFolders) infoFolders.innerText = data.repository.folders;
                if (infoFunctions) infoFunctions.innerText = data.repository.functions;
                if (infoStatus) infoStatus.innerText = "Active";

                if (statFiles) statFiles.innerText = data.repository.python_files;
                if (statFunctions) statFunctions.innerText = data.repository.functions;
                if (statFolders) statFolders.innerText = data.repository.folders;

                showToast(`Switched active repository to '${rName}'`, "success");
            }

            if (data.suggested_questions) {
                renderSuggestedQuestions(data.suggested_questions);
            }

            if (data.repositories) {
                renderRepoDropdown(data.repositories, data.active_repo_id || repoId);
            }

            // Refresh graph dashboard if active
            if (state.activeView === "graph") loadStandaloneGraph();

        } catch (err) {
            console.error("Repository Switch Error:", err);
            showError(`Failed to switch repository: ${err.message}`);
            showToast("Repository switch failed.", "error");
        } finally {
            setLoading(false);
        }
    }

    function renderRepoDropdown(repos, activeRepoId) {
        if (!repoSelect || !repos || !Array.isArray(repos) || repos.length === 0) return;
        repoSelect.innerHTML = "";
        repos.forEach(repo => {
            const option = document.createElement("option");
            option.value = repo.id;
            option.innerText = `${repo.name}${repo.loaded ? " (Loaded)" : ""}`;
            if (repo.id === activeRepoId || repo.is_active) {
                option.selected = true;
            }
            repoSelect.appendChild(option);
        });
        repoSelect.style.display = repos.length > 1 ? "inline-block" : "none";
    }

    async function handleRepoUpload(e) {
        const file = e.target.files[0];
        if (!file) return;

        if (!file.name.toLowerCase().endsWith(".zip")) {
            showError("Only .zip repository archives are supported.");
            showToast("Upload rejected: Must be a .zip file", "error");
            if (repoZipInput) repoZipInput.value = "";
            return;
        }

        setLoading(true, "Uploading, extracting, and indexing repository... Please wait.");
        hideError();
        if (resultsCard) resultsCard.style.display = "none";
        if (graphSection) graphSection.style.display = "none";

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch("/api/upload_repo", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (!response.ok || data.success === false) {
                const errMsg = data.error || data.message || `Upload failed with status ${response.status}`;
                showError(errMsg);
                showToast(`Upload failed: ${errMsg}`, "error");
                return;
            }

            if (data.active_repo_id) state.activeRepoId = data.active_repo_id;

            if (data.repository) {
                const rName = data.repository.name;
                if (repoNameBadge) repoNameBadge.innerText = rName;
                if (infoProjectName) {
                    infoProjectName.innerText = rName;
                    infoProjectName.title = rName;
                }
                if (infoPythonFiles) infoPythonFiles.innerText = data.repository.python_files;
                if (infoFolders) infoFolders.innerText = data.repository.folders;
                if (infoFunctions) infoFunctions.innerText = data.repository.functions;
                if (infoStatus) infoStatus.innerText = "Active";

                if (statFiles) statFiles.innerText = data.repository.python_files;
                if (statFunctions) statFunctions.innerText = data.repository.functions;
                if (statFolders) statFolders.innerText = data.repository.folders;

                showToast(`Repository '${rName}' uploaded and indexed successfully!`, "success");
            }

            if (data.suggested_questions) {
                renderSuggestedQuestions(data.suggested_questions);
            }

            if (data.repositories) {
                renderRepoDropdown(data.repositories, data.active_repo_id);
            }

        } catch (err) {
            console.error("Repository Upload Error:", err);
            showError(`Network / Connection Error during upload: ${err.message}`);
            showToast("Repository upload failed.", "error");
        } finally {
            setLoading(false);
            if (repoZipInput) repoZipInput.value = "";
        }
    }

    // ==========================================
    // 4. Ask Copilot Query Handler
    // ==========================================
    async function handleQuerySubmit() {
        const queryText = queryInput.value.trim();

        if (!queryText) {
            showError("Please enter a question or select a suggested query.");
            return;
        }

        if (queryText.length > 2000) {
            showError("Query length exceeds maximum allowed length of 2000 characters.");
            showToast("Query exceeds 2000 characters limit", "error");
            return;
        }

        try {
            setLoading(true, "Thinking through your codebase...");
            hideError();
            if (emptyWorkspaceState) emptyWorkspaceState.style.display = "none";
            if (resultsCard) resultsCard.style.display = "none";
            if (graphIframe) graphIframe.src = "about:blank";
            if (graphSection) graphSection.style.display = "none";

            const targetRepoId = (repoSelect && repoSelect.value) ? repoSelect.value : state.activeRepoId;

            const response = await fetch("/api/query", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    query: queryText,
                    repo_id: targetRepoId
                })
            });

            const data = await response.json();

            if (!response.ok || data.success === false) {
                const errMsg = data.error || data.message || `Server returned status ${response.status}`;
                showError(errMsg);
                showToast("Query failed", "error");
                return;
            }

            // Sync state for standalone views
            state.activeFunctionQuery = queryText;
            if (data.graph_url) state.activeGraphUrl = data.graph_url;
            state.activeImpactData = data;

            renderResults(data);
            populateDrawerVisuals(data);
            syncToImpactDashboard(queryText, data);

            queryInput.value = "";
            updateCharCount();
            addToHistory(queryText, data);

        } catch (err) {
            console.error("API Query Error:", err);
            showError(`Network / Connection Error: ${err.message}`);
            showToast("Network error executing query", "error");
        } finally {
            setLoading(false);
        }
    }

    function renderResults(data) {
        if (data.query_type) {
            queryTypeBadge.innerText = data.query_type;
            queryTypeBadge.style.display = "inline-block";
        } else {
            queryTypeBadge.style.display = "none";
        }

        if (data.sub_type) {
            subTypeBadge.innerText = data.sub_type;
            subTypeBadge.style.display = "inline-block";
        } else {
            subTypeBadge.style.display = "none";
        }

        if (data.risk) {
            riskBadge.innerText = `RISK: ${data.risk}`;
            riskBadge.className = `risk-chip risk-${data.risk.toLowerCase()}`;
            riskBadge.style.display = "inline-block";
        } else {
            riskBadge.style.display = "none";
        }

        if (typeof data.impact_percentage === "number") {
            impactPercBadge.innerText = `IMPACT: ${data.impact_percentage.toFixed(2)}%`;
            impactPercBadge.style.display = "inline-block";
        } else {
            impactPercBadge.style.display = "none";
        }

        answerContent.innerHTML = renderMarkdown(data.answer || "No response text available.");

        if (window.hljs && typeof window.hljs.highlightElement === "function") {
            try {
                answerContent.querySelectorAll("pre code").forEach((block) => {
                    window.hljs.highlightElement(block);
                });
            } catch (err) {
                console.warn("Syntax highlighting failed:", err);
            }
        }

        if (data.citations && Array.isArray(data.citations) && data.citations.length > 0) {
            renderCitations(data.citations);
            citationsSection.style.display = "flex";
        } else {
            citationsSection.style.display = "none";
        }

        if (data.graph_url) {
            const bustUrl = data.graph_url + (data.graph_url.includes('?') ? '&' : '?') + '_t=' + Date.now();
            graphIframe.src = bustUrl;
            if (openGraphBtn) openGraphBtn.href = data.graph_url;
            graphSection.style.display = "flex";

            // Also update standalone graph iframe
            if (standaloneGraphIframe) standaloneGraphIframe.src = bustUrl;
        } else {
            graphIframe.src = "about:blank";
            graphSection.style.display = "none";
        }

        resultsCard.style.display = "flex";
        resultsCard.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function renderCitations(citations) {
        citationsGrid.innerHTML = "";
        citations.forEach(cit => {
            const card = document.createElement("div");
            card.className = "citation-card";

            const headerRow = document.createElement("div");
            headerRow.className = "citation-header-row";

            const fileEl = document.createElement("div");
            fileEl.className = "citation-file";
            fileEl.innerText = cit.file || "Unknown File";

            const copyBtn = document.createElement("button");
            copyBtn.className = "copy-citation-btn";
            copyBtn.title = "Copy citation reference";
            copyBtn.innerHTML = `
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg> Copy
            `;

            const parts = [];
            if (cit.file) parts.push(cit.file);
            if (cit.name) parts.push(cit.name);
            if (cit.start_line) {
                const lineStr = cit.end_line && cit.end_line !== cit.start_line ? `L${cit.start_line}-L${cit.end_line}` : `L${cit.start_line}`;
                parts.push(lineStr);
            }
            const copyText = parts.join(" → ");

            copyBtn.addEventListener("click", () => {
                copyToClipboard(copyText, copyBtn);
            });

            headerRow.appendChild(fileEl);
            headerRow.appendChild(copyBtn);

            const metaEl = document.createElement("div");
            metaEl.className = "citation-meta";

            const nameLines = [];
            if (cit.name) nameLines.push(`Function: ${cit.name}`);
            if (cit.start_line) nameLines.push(`Lines ${cit.start_line}-${cit.end_line || cit.start_line}`);
            
            metaEl.innerHTML = `<span>${nameLines.join(" | ")}</span>`;

            if (cit.type) {
                const typeTag = document.createElement("span");
                typeTag.className = "citation-type-tag";
                typeTag.innerText = cit.type;
                metaEl.appendChild(typeTag);
            }

            card.appendChild(headerRow);
            card.appendChild(metaEl);
            citationsGrid.appendChild(card);
        });
    }

    // ==========================================
    // 5. Standalone Dedicated Dashboards Logic
    // ==========================================

    // A. Standalone Graph View
    async function loadStandaloneGraph() {
        if (!standaloneGraphIframe) return;

        const graphLoadingState = document.getElementById("graphLoadingState");
        const graphEmptyState = document.getElementById("graphEmptyState");

        let graphUrl = state.activeGraphUrl;
        if (!graphUrl) {
            const selectedGraph = (graphSelect && graphSelect.value) ? graphSelect.value : "call_graph";
            graphUrl = `/api/graph/${selectedGraph}`;
        }

        // Show dark-themed loading skeleton spinner
        if (graphLoadingState) graphLoadingState.style.display = "flex";
        if (graphEmptyState) graphEmptyState.style.display = "none";
        standaloneGraphIframe.style.display = "none";

        try {
            const bustUrl = graphUrl + (graphUrl.includes('?') ? '&' : '?') + '_t=' + Date.now();
            const res = await fetch(bustUrl);
            const contentType = res.headers.get("content-type") || "";

            if (!res.ok || contentType.includes("application/json")) {
                const data = await res.json().catch(() => ({}));
                if (data.error || !res.ok) {
                    showGraphEmptyState(data.error);
                    return;
                }
            }

            // Valid HTML pyvis graph output
            standaloneGraphIframe.src = bustUrl;
            standaloneGraphIframe.style.display = "block";
            if (graphLoadingState) graphLoadingState.style.display = "none";
            if (graphEmptyState) graphEmptyState.style.display = "none";

        } catch (err) {
            console.warn("Failed to load graph:", err);
            showGraphEmptyState();
        }
    }

    function showGraphEmptyState() {
        const graphLoadingState = document.getElementById("graphLoadingState");
        const graphEmptyState = document.getElementById("graphEmptyState");
        if (graphLoadingState) graphLoadingState.style.display = "none";
        if (standaloneGraphIframe) standaloneGraphIframe.style.display = "none";
        if (graphEmptyState) graphEmptyState.style.display = "flex";
    }

    // CTA Handler: Generate Dependency Graph
    const generateGraphBtn = document.getElementById("generateGraphBtn");
    if (generateGraphBtn) {
        generateGraphBtn.addEventListener("click", async () => {
            const graphLoadingState = document.getElementById("graphLoadingState");
            const graphEmptyState = document.getElementById("graphEmptyState");

            if (graphEmptyState) graphEmptyState.style.display = "none";
            if (graphLoadingState) graphLoadingState.style.display = "flex";

            try {
                showToast("Analyzing codebase & generating graph...", "info");
                const targetRepoId = (repoSelect && repoSelect.value) ? repoSelect.value : state.activeRepoId;

                const response = await fetch("/api/query", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        query: "Show the dependency graph.",
                        repo_id: targetRepoId
                    })
                });

                const data = await response.json();
                if (data.graph_url) {
                    state.activeGraphUrl = data.graph_url;
                }
                loadStandaloneGraph();
            } catch (err) {
                console.error("Generate Graph Error:", err);
                showToast("Failed to generate graph.", "error");
                showGraphEmptyState();
            }
        });
    }

    if (graphSelect) {
        graphSelect.addEventListener("change", () => {
            state.activeGraphUrl = `/api/graph/${graphSelect.value}`;
            loadStandaloneGraph();
        });
    }

    if (refreshGraphBtn) {
        refreshGraphBtn.addEventListener("click", () => {
            loadStandaloneGraph();
            showToast("Graph view refreshed", "info");
        });
    }

    if (fullscreenGraphBtn && standaloneGraphIframe) {
        fullscreenGraphBtn.addEventListener("click", () => {
            if (standaloneGraphIframe.requestFullscreen) {
                standaloneGraphIframe.requestFullscreen();
            } else if (standaloneGraphIframe.webkitRequestFullscreen) {
                standaloneGraphIframe.webkitRequestFullscreen();
            }
        });
    }

    if (standaloneNodeSearch) {
        standaloneNodeSearch.addEventListener("input", (e) => {
            const query = e.target.value.toLowerCase().trim();
            try {
                const iframeDoc = standaloneGraphIframe.contentDocument || standaloneGraphIframe.contentWindow.document;
                if (iframeDoc && iframeDoc.querySelector("canvas")) {
                    // Filter or search canvas nodes if network instance exists
                    if (standaloneGraphIframe.contentWindow.network) {
                        const net = standaloneGraphIframe.contentWindow.network;
                        const nodes = standaloneGraphIframe.contentWindow.nodes;
                        if (nodes) {
                            const matchingNode = nodes.get().find(n => (n.label || "").toLowerCase().includes(query));
                            if (matchingNode) {
                                net.focus(matchingNode.id, { scale: 1.2, animation: true });
                            }
                        }
                    }
                }
            } catch (err) {
                // Cross-origin or uninitialized iframe catch
            }
        });
    }

    // B. Standalone Dependencies Dashboard
    async function fetchDependencyOverview(searchQuery = "") {
        if (!depResultsList) return;
        depResultsList.innerHTML = `<div class="dash-empty-state"><div class="dash-empty-icon">⏳</div><div>Loading dependency graph...</div></div>`;

        try {
            const response = await fetch("/api/status");
            const data = await response.json();

            if (data.success || data.status === "active") {
                const pyFiles = data.total_files || 0;
                const funcs = data.total_functions || 0;

                depResultsList.innerHTML = `
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
                        <div class="dash-card">
                            <div class="dash-card-title">Indexed Modules</div>
                            <div class="dash-card-value">${pyFiles}</div>
                        </div>
                        <div class="dash-card">
                            <div class="dash-card-title">Parsed Functions</div>
                            <div class="dash-card-value">${funcs}</div>
                        </div>
                        <div class="dash-card">
                            <div class="dash-card-title">Active Repository</div>
                            <div class="dash-card-value" style="font-size: 1.1rem; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(data.project_name || "Loaded")}</div>
                        </div>
                    </div>
                    <div class="dash-card">
                        <div class="dash-card-title">Dependency Quick Actions</div>
                        <p style="color: var(--text-muted); font-size: 0.875rem; margin-bottom: 1rem;">
                            Search function dependencies or view full caller call graph in standalone interactive canvas.
                        </p>
                        <div style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
                            <button class="dash-action-btn" id="depOpenFullGraphBtn">⚡ Launch Standalone Call Graph</button>
                        </div>
                    </div>
                `;

                const btn = document.getElementById("depOpenFullGraphBtn");
                if (btn) {
                    btn.addEventListener("click", () => {
                        state.activeGraphUrl = "/api/graph/call_graph";
                        switchView("graph");
                    });
                }
            }
        } catch (err) {
            depResultsList.innerHTML = `<div class="dash-empty-state"><div class="dash-empty-icon">⚠️</div><div>Failed to load dependencies data.</div></div>`;
        }
    }

    if (depSearchBtn && depSearchInput) {
        depSearchBtn.addEventListener("click", () => {
            const q = depSearchInput.value.trim();
            if (q) {
                // Switch to Ask Copilot to execute dependency query
                queryInput.value = `Show dependencies of ${q}`;
                switchView("ask");
                handleQuerySubmit();
            } else {
                fetchDependencyOverview();
            }
        });
    }

    // C. Standalone Impact Analysis Dashboard
    if (impactForm) {
        impactForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const funcName = impactSearchInput ? impactSearchInput.value.trim() : "";
            if (!funcName) return;

            // Route impact analysis query
            queryInput.value = `What is the impact of modifying function ${funcName}?`;
            switchView("ask");
            handleQuerySubmit();
        });
    }

    function syncToImpactDashboard(query, data) {
        if (!dashImpactFunc) return;

        dashImpactFunc.innerText = query ? `Target: ${query.substring(0, 40)}` : "No Active Target";

        if (data.risk) {
            dashImpactRisk.innerText = `RISK: ${data.risk}`;
            dashImpactRisk.className = `risk-chip risk-${data.risk.toLowerCase()}`;
            dashImpactRisk.style.display = "inline-block";
        } else {
            dashImpactRisk.style.display = "none";
        }

        if (typeof data.impact_percentage === "number") {
            dashImpactPerc.innerText = `IMPACT: ${data.impact_percentage.toFixed(2)}%`;
            dashImpactPerc.style.display = "inline-block";
        } else {
            dashImpactPerc.style.display = "none";
        }

        if (dashImpactSummary) {
            dashImpactSummary.innerHTML = renderMarkdown(data.answer || "Execute an impact analysis query to populate impact stats.");
        }

        if (dashImpactCallers && data.citations) {
            dashImpactCallers.innerHTML = "";
            data.citations.forEach(c => {
                const div = document.createElement("div");
                div.className = "history-item-card";
                div.style.marginBottom = "0.5rem";
                div.innerHTML = `<strong>${escapeHtml(c.name || c.file)}</strong> <span style="color: var(--text-muted); font-size: 0.8rem;">(${escapeHtml(c.file)})</span>`;
                dashImpactCallers.appendChild(div);
            });
        }
    }

    // D. Standalone History Stream Dashboard
    function renderStandaloneHistory() {
        if (!standaloneHistoryContainer) return;
        standaloneHistoryContainer.innerHTML = "";

        if (state.sessionHistory.length === 0) {
            standaloneHistoryContainer.innerHTML = `
                <div class="dash-empty-state">
                    <div class="dash-empty-icon">📜</div>
                    <div style="font-size: 1.1rem; color: var(--text-main); margin-bottom: 0.5rem;">No Session Queries Yet</div>
                    <p style="color: var(--text-muted); font-size: 0.875rem; margin-bottom: 1rem;">Ask questions in Ask Copilot to build your interactive session history stream.</p>
                    <button class="dash-action-btn" data-view="ask">Go to Ask Copilot</button>
                </div>
            `;

            const goBtn = standaloneHistoryContainer.querySelector("[data-view='ask']");
            if (goBtn) goBtn.addEventListener("click", () => switchView("ask"));
            return;
        }

        state.sessionHistory.forEach(item => {
            const card = document.createElement("div");
            card.className = "history-item-card";

            const header = document.createElement("div");
            header.className = "history-item-header";

            const qSpan = document.createElement("div");
            qSpan.className = "history-item-query";
            qSpan.innerHTML = `<span class="query-icon">Q:</span> <strong>${escapeHtml(item.query)}</strong>`;

            const repoTag = document.createElement("span");
            repoTag.className = "repo-history-tag";
            repoTag.innerText = `Repo: ${escapeHtml(item.repoName)}`;

            header.appendChild(qSpan);
            header.appendChild(repoTag);

            const metaRow = document.createElement("div");
            metaRow.className = "history-item-badges";
            if (item.data.query_type) metaRow.innerHTML += `<span class="type-chip">${escapeHtml(item.data.query_type)}</span> `;
            if (item.data.sub_type) metaRow.innerHTML += `<span class="subtype-chip">${escapeHtml(item.data.sub_type)}</span> `;
            if (item.data.risk) metaRow.innerHTML += `<span class="risk-chip risk-${escapeHtml(item.data.risk.toLowerCase())}">RISK: ${escapeHtml(item.data.risk)}</span> `;
            if (typeof item.data.impact_percentage === "number") metaRow.innerHTML += `<span class="impact-perc-chip">IMPACT: ${item.data.impact_percentage.toFixed(2)}%</span> `;

            const ansDiv = document.createElement("div");
            ansDiv.className = "history-item-answer";
            ansDiv.innerHTML = renderMarkdown(item.data.answer || "");

            card.appendChild(header);
            if (metaRow.children.length > 0) card.appendChild(metaRow);
            card.appendChild(ansDiv);

            standaloneHistoryContainer.appendChild(card);
        });
    }

    // ==========================================
    // 6. Session History Stream Sync
    // ==========================================
    function addToHistory(query, data) {
        const currentRepoName = (repoNameBadge && repoNameBadge.innerText !== "Loading repo...") 
            ? repoNameBadge.innerText 
            : state.activeRepoId;

        const historyItem = {
            query: query,
            repoName: currentRepoName,
            data: data,
            timestamp: new Date().toLocaleTimeString()
        };

        state.sessionHistory.unshift(historyItem);

        if (historyCountBadge) {
            const count = state.sessionHistory.length;
            historyCountBadge.innerText = `${count} ${count === 1 ? 'query' : 'queries'}`;
        }

        if (historySection && historyContainer) {
            historySection.style.display = "flex";

            const card = document.createElement("div");
            card.className = "history-item-card";

            const header = document.createElement("div");
            header.className = "history-item-header";

            const qSpan = document.createElement("div");
            qSpan.className = "history-item-query";
            qSpan.innerHTML = `<span class="query-icon">Q:</span> <strong>${escapeHtml(query)}</strong>`;

            const repoTag = document.createElement("span");
            repoTag.className = "repo-history-tag";
            repoTag.innerText = `Repo: ${currentRepoName}`;

            header.appendChild(qSpan);
            header.appendChild(repoTag);

            const metaRow = document.createElement("div");
            metaRow.className = "history-item-badges";
            if (data.query_type) metaRow.innerHTML += `<span class="type-chip">${escapeHtml(data.query_type)}</span> `;
            if (data.sub_type) metaRow.innerHTML += `<span class="subtype-chip">${escapeHtml(data.sub_type)}</span> `;
            if (data.risk) metaRow.innerHTML += `<span class="risk-chip risk-${escapeHtml(data.risk.toLowerCase())}">RISK: ${escapeHtml(data.risk)}</span> `;
            if (typeof data.impact_percentage === "number") metaRow.innerHTML += `<span class="impact-perc-chip">IMPACT: ${data.impact_percentage.toFixed(2)}%</span> `;

            const ansDiv = document.createElement("div");
            ansDiv.className = "history-item-answer";
            ansDiv.innerHTML = renderMarkdown(data.answer || "");

            card.appendChild(header);
            if (metaRow.children.length > 0) card.appendChild(metaRow);
            card.appendChild(ansDiv);

            if (data.citations && Array.isArray(data.citations) && data.citations.length > 0) {
                const citSummary = document.createElement("div");
                citSummary.className = "history-item-citations";
                const files = data.citations.map(c => c.file).filter(Boolean);
                citSummary.innerHTML = `<strong>Citations (${data.citations.length}):</strong> ${escapeHtml(files.join(", "))}`;
                card.appendChild(citSummary);
            }

            historyContainer.insertBefore(card, historyContainer.firstChild);
        }

        if (state.activeView === "history") {
            renderStandaloneHistory();
        }
    }

    // ==========================================
    // 7. Clipboard & Notifications & Helpers
    // ==========================================
    function copyToClipboard(text, btnElement) {
        if (!navigator.clipboard || !navigator.clipboard.writeText) {
            const textarea = document.createElement("textarea");
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand("copy");
                showCopySuccess(btnElement);
            } catch (err) {
                console.warn("Fallback copy failed:", err);
            }
            document.body.removeChild(textarea);
            return;
        }

        navigator.clipboard.writeText(text)
            .then(() => showCopySuccess(btnElement))
            .catch(err => console.warn("Clipboard copy failed:", err));
    }

    function showCopySuccess(btnElement) {
        const origHTML = btnElement.innerHTML;
        btnElement.classList.add("copied");
        btnElement.innerText = "Copied!";
        showToast("Citation reference copied to clipboard.", "success");
        setTimeout(() => {
            btnElement.classList.remove("copied");
            btnElement.innerHTML = origHTML;
        }, 1800);
    }

    function showToast(message, type = "info") {
        if (!toastContainer) return;
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.innerText = message;
        toastContainer.appendChild(toast);

        setTimeout(() => toast.classList.add("show"), 10);
        setTimeout(() => {
            toast.classList.remove("show");
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    function setLoading(isLoading, text = "Thinking through your codebase...") {
        if (sendBtn) sendBtn.disabled = isLoading;
        if (queryInput) queryInput.disabled = isLoading;
        if (loaderText) loaderText.innerText = text;
        if (loaderContainer) loaderContainer.style.display = isLoading ? "flex" : "none";
    }

    function showError(msg) {
        if (errorMessage) errorMessage.innerText = msg;
        if (errorCard) {
            errorCard.style.display = "block";
            if (typeof errorCard.scrollIntoView === "function") {
                errorCard.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }
    }

    function hideError() {
        if (errorCard) errorCard.style.display = "none";
    }

    function renderSuggestedQuestions(questions) {
        if (!questions || !Array.isArray(questions) || questions.length === 0) return;
        const container = document.querySelector(".suggestions-list");
        if (!container) return;

        container.innerHTML = "";
        questions.forEach(q => {
            const chip = document.createElement("button");
            chip.className = "suggestion-chip";
            chip.dataset.query = q;
            chip.innerText = q;
            chip.addEventListener("click", () => {
                queryInput.value = q;
                updateCharCount();
                handleQuerySubmit();
            });
            container.appendChild(chip);
        });
    }

    function escapeHtml(text) {
        if (!text) return "";
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function renderMarkdown(text) {
        if (window.marked && typeof window.marked.parse === "function") {
            return window.marked.parse(text);
        }

        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
            return `<pre><code>${code.trim()}</code></pre>`;
        });

        html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
        html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
        html = html.replace(/^## (.*$)/gim, "## $1");
        html = html.replace(/^# (.*$)/gim, "<h1>$1</h1>");
        html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        html = html.replace(/^\s*-\s+(.*$)/gim, "<li>$1</li>");
        html = html.replace(/(<li>.*<\/li>)/sim, "<ul>$1</ul>");
        html = html.replace(/\n\n/g, "<br><br>");

        return html;
    }
});
