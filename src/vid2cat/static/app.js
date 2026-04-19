document.addEventListener("DOMContentLoaded", () => {
    const taskStatusBar = document.getElementById("task-status-bar");
    const interactionForm = document.getElementById("interaction-form");
    const interactionInput = document.getElementById("interaction-input");
    const interactionSubmitButton = document.getElementById("interaction-submit-btn");
    const interactionHint = document.getElementById("interaction-hint");
    const chatMessages = document.getElementById("chatMessages");
    const starRatings = document.querySelectorAll("[data-star-rating]");
    const shareCardButtons = document.querySelectorAll("[data-share-card-id]");
    const adoptionDialog = document.getElementById("adoption-dialog");
    const adoptionOpenButtons = document.querySelectorAll("[data-open-adoption]");
    const adoptionCloseButtons = document.querySelectorAll("[data-close-adoption]");
    const growthGuideDialog = document.getElementById("growth-guide-dialog");
    const growthGuideCloseButtons = document.querySelectorAll("[data-close-growth-guide]");
    const authDialog = document.getElementById("auth-dialog");
    const authOpenButtons = document.querySelectorAll("[data-open-auth]");
    const authCloseButtons = document.querySelectorAll("[data-close-auth]");
    const authTabButtons = document.querySelectorAll("[data-auth-tab]");
    const authPanels = document.querySelectorAll("[data-auth-panel]");
    const previewCardButtons = document.querySelectorAll("[data-preview-image]");
    const imagePreviewDialog = document.getElementById("image-preview-dialog");
    const imagePreviewTarget = document.getElementById("image-preview-target");
    const imagePreviewTitle = document.getElementById("image-preview-title");
    const imagePreviewDesc = document.getElementById("image-preview-desc");
    const previewCloseButtons = document.querySelectorAll("[data-close-preview]");
    const loadingOverlay = document.getElementById("loading-overlay");
    const loadingOverlayTitle = document.getElementById("loading-overlay-title");
    const loadingOverlayText = document.getElementById("loading-overlay-text");
    const adoptionForm = document.querySelector("[data-adoption-form]");
    const adoptionLoadingGrid = document.getElementById("adoption-loading-grid");
    const ownedCatsGrid = document.getElementById("owned-cats-grid");
    const emptyOwnedCats = document.getElementById("empty-owned-cats");
    const trainingButtons = document.querySelectorAll(".training-action-btn");
    const douyinPattern = /(douyin\.com|iesdouyin\.com|v\.douyin\.com)/i;

    let activeTaskId = null;
    let activeAdoptionTaskId = null;
    let typewriterTimer = null;
    let typewriterQueue = "";
    let typewriterStreamDone = false;
    let lastGrowthLogKey = "";

    const setTaskStatus = (text, variant = "progress") => {
        if (!taskStatusBar) return;
        taskStatusBar.textContent = text;
        taskStatusBar.className = `task-status-bar ${variant}`;
    };

    const clearTaskStatus = () => {
        if (!taskStatusBar) return;
        taskStatusBar.textContent = "";
        taskStatusBar.className = "task-status-bar hidden";
    };

    const clearAdoptionLoadingSlots = () => {
        document.querySelectorAll("[data-adoption-loading-slot]").forEach((el) => {
            el.remove();
        });
    };

    const scrollChatToBottom = () => {
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    };

    scrollChatToBottom();

    const updateDialogBodyState = () => {
        const hasVisibleDialog = [authDialog, adoptionDialog, growthGuideDialog, imagePreviewDialog, loadingOverlay].some(
            (dialog) => dialog && !dialog.classList.contains("hidden"),
        );
        document.body.classList.toggle("dialog-open", hasVisibleDialog);
    };

    const showLoadingOverlay = (title, text) => {
        if (!loadingOverlay) return;
        if (loadingOverlayTitle) loadingOverlayTitle.textContent = title || "处理中...";
        if (loadingOverlayText) loadingOverlayText.textContent = text || "请稍等，正在准备你的猫咪。";
        loadingOverlay.classList.remove("hidden");
        loadingOverlay.setAttribute("aria-hidden", "false");
        updateDialogBodyState();
    };

    const hideLoadingOverlay = () => {
        if (!loadingOverlay) return;
        loadingOverlay.classList.add("hidden");
        loadingOverlay.setAttribute("aria-hidden", "true");
        updateDialogBodyState();
    };

    const setAuthTab = (tabName) => {
        if (!authDialog) return;
        authTabButtons.forEach((button) => {
            button.classList.toggle("active", button.dataset.authTab === tabName);
        });
        authPanels.forEach((panel) => {
            panel.classList.toggle("active", panel.dataset.authPanel === tabName);
        });
    };

    const openAuthDialog = (tabName = "login") => {
        if (!authDialog) return;
        setAuthTab(tabName);
        authDialog.classList.remove("hidden");
        authDialog.setAttribute("aria-hidden", "false");
        updateDialogBodyState();
    };

    const closeAuthDialog = () => {
        if (!authDialog) return;
        authDialog.classList.add("hidden");
        authDialog.setAttribute("aria-hidden", "true");
        updateDialogBodyState();
    };

    const openAdoptionDialog = () => {
        if (!adoptionDialog) return;
        closeAuthDialog();
        if (growthGuideDialog) {
            growthGuideDialog.classList.add("hidden");
            growthGuideDialog.setAttribute("aria-hidden", "true");
        }
        adoptionDialog.classList.remove("hidden");
        adoptionDialog.setAttribute("aria-hidden", "false");
        updateDialogBodyState();
    };

    const closeAdoptionDialog = () => {
        if (!adoptionDialog) return;
        adoptionDialog.classList.add("hidden");
        adoptionDialog.setAttribute("aria-hidden", "true");
        updateDialogBodyState();
    };

    const openGrowthGuideDialog = () => {
        if (!growthGuideDialog) return;
        closeAuthDialog();
        if (adoptionDialog) {
            adoptionDialog.classList.add("hidden");
            adoptionDialog.setAttribute("aria-hidden", "true");
        }
        growthGuideDialog.classList.remove("hidden");
        growthGuideDialog.setAttribute("aria-hidden", "false");
        updateDialogBodyState();
    };

    const closeGrowthGuideDialog = () => {
        if (!growthGuideDialog) return;
        growthGuideDialog.classList.add("hidden");
        growthGuideDialog.setAttribute("aria-hidden", "true");
        updateDialogBodyState();
    };

    const openImagePreview = (url, title = "分享卡预览", desc = "预览图文字与技能区分开展示，不会出现重叠。") => {
        if (!imagePreviewDialog || !imagePreviewTarget || !url) return;
        imagePreviewTarget.src = url;
        if (imagePreviewTitle) imagePreviewTitle.textContent = title;
        if (imagePreviewDesc) imagePreviewDesc.textContent = desc;
        imagePreviewDialog.classList.remove("hidden");
        imagePreviewDialog.setAttribute("aria-hidden", "false");
        updateDialogBodyState();
    };

    const closeImagePreview = () => {
        if (!imagePreviewDialog || !imagePreviewTarget) return;
        imagePreviewDialog.classList.add("hidden");
        imagePreviewDialog.setAttribute("aria-hidden", "true");
        imagePreviewTarget.src = "";
        if (imagePreviewTitle) imagePreviewTitle.textContent = "分享卡预览";
        if (imagePreviewDesc) imagePreviewDesc.textContent = "预览图文字与技能区分开展示，不会出现重叠。";
        updateDialogBodyState();
    };

    authOpenButtons.forEach((button) => {
        button.addEventListener("click", () => {
            openAuthDialog(button.dataset.openAuth || "login");
        });
    });

    authCloseButtons.forEach((button) => {
        button.addEventListener("click", closeAuthDialog);
    });

    authTabButtons.forEach((button) => {
        button.addEventListener("click", () => {
            setAuthTab(button.dataset.authTab || "login");
        });
    });

    adoptionOpenButtons.forEach((button) => {
        button.addEventListener("click", openAdoptionDialog);
    });

    adoptionCloseButtons.forEach((button) => {
        button.addEventListener("click", closeAdoptionDialog);
    });

    growthGuideCloseButtons.forEach((button) => {
        button.addEventListener("click", closeGrowthGuideDialog);
    });

    const previewUploadedCard = async (button) => {
        const catId = button.dataset.previewCatId || button.dataset.shareCardId;
        const catName = button.dataset.previewCatName || button.dataset.shareCardName || "这只小猫";
        if (!catId) {
            openImagePreview(button.dataset.previewImage, `${catName} 的预览`, "未找到猫咪编号，展示本地预览。");
            return;
        }

        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = "准备预览中...";
        try {
            if (button.dataset.previewUploadedUrl) {
                openImagePreview(
                    button.dataset.previewUploadedUrl,
                    `${catName} 的分享卡预览`,
                    "该预览已走图床地址，介绍区单独展示，避免与技能文字重叠。",
                );
                return;
            }

            const response = await fetch(`/api/cats/${catId}/share-card/link`, { method: "POST" });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || "生成预览图失败");
            }
            button.dataset.previewUploadedUrl = payload.uploaded_url || "";
            openImagePreview(
                payload.uploaded_url,
                payload.share_title || `${catName} 的分享卡预览`,
                payload.share_text || `这是 ${catName} 的图床预览图，介绍区已和技能展示分开。`,
            );
        } catch (error) {
            appendEventMessage(error.message || "预览图生成失败", "error");
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    };

    const bindPreviewButton = (button) => {
        if (!button || button.dataset.previewBound === "true") return;
        button.dataset.previewBound = "true";
        button.addEventListener("click", async () => {
            await previewUploadedCard(button);
        });
    };

    previewCardButtons.forEach((button) => {
        bindPreviewButton(button);
    });

    previewCloseButtons.forEach((button) => {
        button.addEventListener("click", closeImagePreview);
    });

    const buildGrowthLogText = (log) => {
        if (!log) return "";
        const title = log.title ? `[${log.title}] ` : "";
        const timeSuffix = log.time ? `（${log.time}）` : "";
        return `${title}${log.summary || "本次已完成进化。"}${timeSuffix}`;
    };

    if (adoptionForm) {
        adoptionForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (activeAdoptionTaskId) {
                appendEventMessage("已有一只猫正在生成中，稍等它完成后再领养下一只。", "progress");
                return;
            }

            const formData = new FormData(adoptionForm);
            const breed = String(formData.get("breed") || "").trim();
            const color = String(formData.get("color") || "").trim();
            if (!breed || !color) {
                appendEventMessage("请先选择品种和颜色。", "error");
                return;
            }

            if (adoptionLoadingGrid) {
                if (ownedCatsGrid) {
                    clearAdoptionLoadingSlots();
                    ownedCatsGrid.insertAdjacentHTML(
                        "beforeend",
                        `<article class="cat-switch-card cat-switch-card-loading" data-adoption-loading-slot aria-label="新猫咪正在生成中">
                            <div class="cat-switch-thumb skeleton-box"></div>
                            <div class="cat-switch-body">
                                <div class="cat-switch-top">
                                    <h3>新猫咪生成中...</h3>
                                    <span class="pill muted">准备中</span>
                                </div>
                                <div class="pill-row compact">
                                    <span class="pill muted">正在匹配品种</span>
                                    <span class="pill muted">正在生成形象</span>
                                </div>
                            </div>
                        </article>`,
                    );
                    adoptionLoadingGrid.classList.add("hidden");
                } else {
                    adoptionLoadingGrid.classList.remove("hidden");
                }
            }
            if (emptyOwnedCats) {
                emptyOwnedCats.classList.add("hidden");
            }
            if (adoptionDialog) {
                adoptionDialog.classList.add("hidden");
                adoptionDialog.setAttribute("aria-hidden", "true");
            }
            updateDialogBodyState();
            appendEventMessage(`已开始领养 ${color}${breed}，生成中...`, "progress");

            try {
                const response = await fetch("/api/my-cat/adopt", {
                    method: "POST",
                    body: formData,
                });
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.detail || "领养任务提交失败");
                }
                activeAdoptionTaskId = payload.task_id;

                const pollAdoption = async () => {
                    if (!activeAdoptionTaskId) {
                        return;
                    }
                    const taskResponse = await fetch(`/api/tasks/${activeAdoptionTaskId}`);
                    const task = await taskResponse.json();
                    if (!taskResponse.ok) {
                        throw new Error(task.detail || "领养状态获取失败");
                    }
                    if (task.status === "pending" || task.status === "running") {
                        const progressText = `领养中：${task.message || "请稍候"}`;
                        setTaskStatus(progressText, "progress");
                        window.setTimeout(pollAdoption, 1400);
                        return;
                    }
                    activeAdoptionTaskId = null;
                    if (task.status === "done") {
                        if (!interactionForm) {
                            window.location.href = "/my-cat?message=" + encodeURIComponent(task.message || "领养完成");
                            return;
                        }
                        await refreshCatPanel();
                        clearAdoptionLoadingSlots();
                        if (adoptionLoadingGrid) {
                            adoptionLoadingGrid.classList.add("hidden");
                        }
                        setTaskStatus(task.message || "领养完成", "done");
                        appendEventMessage(task.message || "领养完成，可以开始互动啦。", "done");
                        return;
                    }
                    throw new Error(task.error || task.message || "领养失败");
                };

                void pollAdoption();
            } catch (error) {
                activeAdoptionTaskId = null;
                clearAdoptionLoadingSlots();
                if (adoptionLoadingGrid) {
                    adoptionLoadingGrid.classList.add("hidden");
                }
                setTaskStatus(error.message || "领养失败", "error");
                appendEventMessage(error.message || "领养失败", "error");
            }
        });
    }

    if (authDialog?.dataset.autoOpen === "true") {
        openAuthDialog(authDialog.dataset.initialAuthTab || "login");
    } else if (adoptionDialog?.dataset.autoOpen === "true") {
        openAdoptionDialog();
    } else if (growthGuideDialog?.dataset.autoOpen === "true") {
        openGrowthGuideDialog();
    }

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeAuthDialog();
            closeAdoptionDialog();
            closeGrowthGuideDialog();
            closeImagePreview();
        }
    });

    const showShareNotice = (text) => {
        window.alert(text);
    };

    const copyToClipboard = async (text) => {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
            return true;
        }
        const helper = document.createElement("textarea");
        helper.value = text;
        helper.setAttribute("readonly", "");
        helper.style.position = "absolute";
        helper.style.left = "-9999px";
        document.body.appendChild(helper);
        helper.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(helper);
        return copied;
    };

    const buildShareFallbackMessage = (payload) => [
        "分享卡图床链接已生成。",
        `链接：${payload.uploaded_url}`,
        "已为你复制到剪贴板。",
        "如果要发微信，直接把这个链接粘贴到聊天窗口即可。",
        "如果要发 QQ，可继续打开 QQ 空间或微博分享页。",
    ].join("\n");

    const shareUploadedCard = async (button) => {
        const catId = button.dataset.shareCardId;
        const catName = button.dataset.shareCardName || "这只小猫";
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = "生成分享链接中...";
        try {
            const response = await fetch(`/api/cats/${catId}/share-card/link`, { method: "POST" });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || "生成分享链接失败");
            }

            const copied = await copyToClipboard(payload.uploaded_url);
            if (navigator.share) {
                try {
                    await navigator.share({
                        title: payload.share_title || `${catName} 的分享卡`,
                        text: payload.share_text || `来看看 ${catName} 的分享卡`,
                        url: payload.uploaded_url,
                    });
                    showShareNotice(`分享卡链接已生成${copied ? "并复制到剪贴板" : ""}，可直接发到微信、QQ等主流 App。`);
                    return;
                } catch (error) {
                    // User cancelled the native share sheet or the browser rejected the call.
                }
            }

            const openQzone = window.confirm(
                `${buildShareFallbackMessage(payload)}\n\n点击“确定”打开 QQ 空间分享页，点击“取消”保持当前页面。`,
            );
            if (openQzone && payload.qzone_url) {
                window.open(payload.qzone_url, "_blank", "noopener,noreferrer");
            } else if (!openQzone && payload.weibo_url) {
                const openWeibo = window.confirm("要不要改为打开微博分享页？");
                if (openWeibo) {
                    window.open(payload.weibo_url, "_blank", "noopener,noreferrer");
                }
            }
        } catch (error) {
            showShareNotice(error.message || "分享分享卡失败");
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    };

    const bindShareButton = (button) => {
        if (!button || button.dataset.shareBound === "true") return;
        button.dataset.shareBound = "true";
        button.addEventListener("click", async () => {
            await shareUploadedCard(button);
        });
    };

    const appendMessage = (role, content) => {
        if (!chatMessages) return null;
        const wrapper = document.createElement("div");
        wrapper.className = `message ${role}`;
        const bubble = document.createElement("div");
        bubble.className = "message-content";
        bubble.textContent = content;
        wrapper.appendChild(bubble);
        chatMessages.appendChild(wrapper);
        scrollChatToBottom();
        return bubble;
    };

    const appendEventMessage = (content, variant = "progress") => {
        if (!chatMessages) return null;
        const wrapper = document.createElement("div");
        wrapper.className = "message assistant timeline-event-msg";
        const bubble = document.createElement("div");
        bubble.className = `message-content timeline-style task-${variant}`;
        bubble.textContent = content;
        wrapper.appendChild(bubble);
        chatMessages.appendChild(wrapper);
        scrollChatToBottom();
        return bubble;
    };

    const flushTypewriter = (bubble) => {
        if (!bubble || !typewriterQueue) return;
        const chunkSize = Math.min(3, typewriterQueue.length);
        bubble.textContent += typewriterQueue.slice(0, chunkSize);
        typewriterQueue = typewriterQueue.slice(chunkSize);
        scrollChatToBottom();
        if (!typewriterQueue) {
            typewriterTimer = null;
            return;
        }
        typewriterTimer = window.setTimeout(() => flushTypewriter(bubble), 18);
    };

    const queueTypewriterToken = (bubble, token) => {
        if (!bubble || !token) return;
        typewriterQueue += token;
        if (typewriterTimer === null) {
            flushTypewriter(bubble);
        }
    };

    const finishTypewriter = (bubble) => {
        if (!bubble || !typewriterQueue) return;
        if (typewriterTimer !== null) {
            window.clearTimeout(typewriterTimer);
            typewriterTimer = null;
        }
        bubble.textContent += typewriterQueue;
        typewriterQueue = "";
        scrollChatToBottom();
    };

    const waitForTypewriterToDrain = () =>
        new Promise((resolve) => {
            const poll = () => {
                if (typewriterStreamDone && typewriterQueue === "" && typewriterTimer === null) {
                    resolve();
                    return;
                }
                window.setTimeout(poll, 16);
            };
            poll();
        });

    const renderSkillBadges = (skillBadges) => {
        if (!Array.isArray(skillBadges) || skillBadges.length === 0) {
            return "还没有学会技能，先把经验练满后喂第一个视频。";
        }
        return skillBadges
            .map(
                (badge) =>
                    `<span class="skill-badge ${badge.class}"><span class="skill-rarity">${badge.rarity}</span>${badge.name}</span>`,
            )
            .join("");
    };

    const refreshOwnedCards = (ownedCats) => {
        if (!Array.isArray(ownedCats) || ownedCats.length === 0) {
            return;
        }
        ownedCats.forEach((owned) => {
            let card = document.querySelector(`[data-owned-cat-id="${owned.id}"]`);
            if (!card && ownedCatsGrid) {
                const activeTag = owned.is_active
                    ? '<span class="pill active">当前陪伴中</span>'
                    : `<form action="/my-cat/switch" method="POST"><input type="hidden" name="cat_id" value="${owned.id}"><button type="submit" class="ghost-btn">切换到这只</button></form>`;
                const firstChar = (owned.cat_name || "猫").slice(0, 1);
                const thumbContent = owned.image_url
                    ? `<img class="owned-cat-image" src="${owned.image_url}" alt="${owned.cat_name || "猫咪"}">`
                    : `<div class="cat-switch-placeholder owned-cat-placeholder">${firstChar}</div>`;
                ownedCatsGrid.insertAdjacentHTML(
                    "beforeend",
                    `<article class="cat-switch-card${owned.is_active ? " active" : ""}" data-owned-cat-id="${owned.id}">
                        <div class="cat-switch-thumb">${thumbContent}</div>
                        <div class="cat-switch-body">
                            <div class="cat-switch-top">
                                <h3 class="owned-cat-name">${owned.cat_name || "未命名猫咪"}</h3>
                                <span class="pill muted owned-cat-stage">${owned.stage || "初始态"}</span>
                            </div>
                            <div class="pill-row compact">
                                <span class="pill muted owned-cat-level">Lv.${owned.level || 0}</span>
                                <span class="pill muted owned-cat-feed">喂养 ${owned.feed_count || 0}/${owned.max_feed_count || 6}</span>
                                <span class="pill muted owned-cat-power">总属性 ${owned.overall_power || 0}</span>
                            </div>
                        </div>
                        <div class="cat-switch-actions">
                            ${activeTag}
                            <button type="button" class="ghost-btn" data-preview-image="/cats/${owned.id}/share-card.png" data-preview-cat-id="${owned.id}" data-preview-cat-name="${owned.cat_name || "猫咪"}" aria-label="预览 ${owned.cat_name || "猫咪"} 的分享卡">预览卡</button>
                            <button type="button" class="ghost-btn share-card-btn" data-share-card-id="${owned.id}" data-share-card-name="${owned.cat_name || "这只小猫"}">分享卡</button>
                        </div>
                    </article>`,
                );
                card = document.querySelector(`[data-owned-cat-id="${owned.id}"]`);
                if (!card) {
                    return;
                }
            }

            const thumb = card.querySelector(".cat-switch-thumb");
            const image = card.querySelector(".owned-cat-image");
            const placeholder = card.querySelector(".owned-cat-placeholder");
            if (thumb) {
                if (owned.image_url) {
                    if (image) {
                        image.src = owned.image_url;
                        image.alt = owned.cat_name;
                    } else {
                        thumb.innerHTML = `<img class="owned-cat-image" src="${owned.image_url}" alt="${owned.cat_name}">`;
                    }
                } else {
                    const firstChar = (owned.cat_name || "猫").slice(0, 1);
                    if (placeholder) {
                        placeholder.textContent = firstChar;
                    } else {
                        thumb.innerHTML = `<div class="cat-switch-placeholder owned-cat-placeholder">${firstChar}</div>`;
                    }
                }
            }

            const setCardText = (selector, text) => {
                const el = card.querySelector(selector);
                if (el) el.textContent = text;
            };
            setCardText(".owned-cat-name", owned.cat_name || "未命名猫咪");
            setCardText(".owned-cat-stage", owned.stage || "初始态");
            setCardText(".owned-cat-level", `Lv.${owned.level || 0}`);
            setCardText(".owned-cat-feed", `喂养 ${owned.feed_count || 0}/${owned.max_feed_count || 6}`);
            setCardText(".owned-cat-power", `总属性 ${owned.overall_power || 0}`);

            const previewButton = card.querySelector("[data-preview-image]");
            if (previewButton) {
                previewButton.dataset.previewImage = `/cats/${owned.id}/share-card.png`;
                previewButton.dataset.previewCatId = String(owned.id);
                previewButton.dataset.previewCatName = owned.cat_name || "猫咪";
                previewButton.setAttribute("aria-label", `预览 ${owned.cat_name || "猫咪"} 的分享卡`);
                bindPreviewButton(previewButton);
            }

            const shareButton = card.querySelector("[data-share-card-id]");
            if (shareButton) {
                shareButton.dataset.shareCardId = String(owned.id);
                shareButton.dataset.shareCardName = owned.cat_name || "这只小猫";
                bindShareButton(shareButton);
            }
        });
    };

    const refreshCatPanel = async (incomingCat = null) => {
        if (!interactionForm) return;
        let cat = incomingCat;
        if (!cat) {
            const refreshEndpoint = interactionForm.dataset.refreshEndpoint || "/api/my-cat/current";
            const response = await fetch(refreshEndpoint);
            cat = await response.json();
            if (!response.ok) {
                throw new Error(cat.detail || "刷新猫咪状态失败");
            }
        }

        const avatarCard = document.getElementById("cat-avatar-card");
        if (avatarCard) {
            avatarCard.innerHTML = cat.image_url
                ? `<img id="cat-avatar-image" src="${cat.image_url}" alt="${cat.name}">`
                : `<div id="cat-avatar-placeholder" class="cat-avatar-placeholder"><span>${cat.name.slice(0, 1)}</span></div>`;
            avatarCard.dataset.catName = cat.name;
        }

        const setText = (id, text) => {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
        };
        setText("cat-level-pill", `等级：${cat.level}/6`);
        setText("cat-stage-pill", `阶段：${cat.stage}`);
        setText("cat-remaining-feed-pill", `剩余喂养 ${cat.remaining_feeds} 次`);
        setText("cat-level-value", `${cat.level}/6`);
        setText("cat-feed-count-value", `${cat.feed_count}/${cat.max_feed_count}`);
        setText("cat-overall-power", `${cat.overall_power}`);
        setText("cat-stat-wisdom", `${cat.wisdom ?? 0}`);
        setText("cat-stat-grit", `${cat.grit ?? 0}`);
        setText("cat-stat-creativity", `${cat.creativity ?? 0}`);
        setText("cat-stat-agility", `${cat.agility ?? 0}`);
        setText("cat-stat-cooperation", `${cat.cooperation ?? 0}`);
        setText("cat-exp-text", cat.exp_progress.exp_to_next > 0 ? `${cat.exp_progress.exp}/${cat.exp_progress.exp_to_next}` : "已满级");
        setText("cat-feed-gate-hint", cat.feed_gate_hint);
        setText(
            "cat-owner-text",
            `@${cat.highest_level_owner_name || "未知主人"} 把它带到了 ${cat.highest_level_reached || cat.level} 级。后续若等级没有再突破，这个名字就不会被改写。`,
        );
        setText("cat-personality", cat.personality || "");
        setText("cat-story-summary", cat.story_summary || "");
        setText("cat-latest-summary", cat.latest_summary || "还没有新的成长记录。");

        const expFill = document.getElementById("cat-exp-fill");
        if (expFill) {
            expFill.style.width = `${cat.exp_progress.percent}%`;
        }
        const levelValue = document.getElementById("cat-level-value");
        if (levelValue) {
            levelValue.classList.toggle("limit-reached", cat.level >= 6);
        }
        const feedCountValue = document.getElementById("cat-feed-count-value");
        if (feedCountValue) {
            feedCountValue.classList.toggle("limit-reached", cat.feed_count >= cat.max_feed_count);
        }
        const expPill = document.getElementById("cat-exp-pill");
        if (expPill) {
            expPill.className = `pill${cat.exp_progress.exp_to_next <= 0 || cat.can_feed ? " active" : " muted"}`;
            expPill.textContent =
                cat.exp_progress.exp_to_next <= 0
                    ? "满级完成"
                    : cat.can_feed
                      ? "已充满"
                      : `还差 ${cat.exp_progress.remaining}`;
        }

        const skillContainer = document.getElementById("cat-skill-badges");
        if (skillContainer) {
            if (Array.isArray(cat.skill_badges) && cat.skill_badges.length > 0) {
                skillContainer.className = "pill-row compact";
                skillContainer.innerHTML = renderSkillBadges(cat.skill_badges);
            } else {
                skillContainer.className = "";
                skillContainer.textContent = "还没有学会技能，先把经验练满后喂第一个视频。";
            }
        }

        if (interactionInput) {
            if (cat.can_feed) {
                interactionInput.removeAttribute("data-feed-locked");
            } else {
                interactionInput.dataset.feedLocked = "true";
            }
            interactionInput.dataset.feedLockedMessage = cat.feed_gate_hint || "当前暂时不能喂养。";
        }

        const publishInput = document.getElementById("publish-toggle-input");
        const publishButton = document.getElementById("publish-toggle-button");
        if (publishInput) {
            publishInput.value = String(cat.is_public ? 0 : 1);
        }
        if (publishButton) {
            publishButton.textContent = cat.is_public ? "隐藏" : "发布";
            publishButton.classList.toggle("published", !!cat.is_public);
            publishButton.classList.toggle("hidden-state", !cat.is_public);
        }

        refreshOwnedCards(cat.owned_cats);
        updateInteractionUi();
        return cat;
    };

    const submitTraining = async (actionKey, triggerButton) => {
        if (!actionKey) return;
        const originalText = triggerButton.textContent;
        trainingButtons.forEach((button) => {
            button.disabled = true;
        });
        triggerButton.textContent = "进行中...";
        try {
            const formData = new FormData();
            formData.append("action_key", actionKey);
            const response = await fetch("/api/my-cat/train", {
                method: "POST",
                body: formData,
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || "修炼失败");
            }
            await refreshCatPanel(payload.cat || null);
            appendEventMessage(payload.message || "修炼完成", "done");
            setTaskStatus(payload.message || "修炼完成", "done");
        } catch (error) {
            appendEventMessage(error.message || "修炼失败", "error");
            setTaskStatus(error.message || "修炼失败", "error");
        } finally {
            trainingButtons.forEach((button) => {
                button.disabled = false;
            });
            triggerButton.textContent = originalText;
        }
    };

    const containsDouyinUrl = (text) => douyinPattern.test(text || "");

    const updateInteractionUi = () => {
        if (!interactionInput || !interactionSubmitButton || !interactionHint) {
            return;
        }
        const value = interactionInput.value.trim();
        const feedLocked = interactionInput.dataset.feedLocked === "true";
        const lockedMessage = interactionInput.dataset.feedLockedMessage || "当前暂时不能喂养。";
        const isFeed = containsDouyinUrl(value);
        if (isFeed && !feedLocked) {
            interactionSubmitButton.textContent = "开始喂养";
            interactionHint.textContent = "检测到抖音链接，提交后会进入喂养和形象更新流程（仅支持不超过 1 分钟的视频）。";
            return;
        }
        if (isFeed && feedLocked) {
            interactionSubmitButton.textContent = "暂不能喂养";
            interactionHint.textContent = lockedMessage;
            return;
        }
        interactionSubmitButton.textContent = "发送";
        interactionHint.textContent = feedLocked
            ? lockedMessage
            : "输入普通文字会直接进入聊天。";
    };

    if (interactionForm && interactionInput && interactionSubmitButton && chatMessages) {
        const submitFeed = async (rawInput) => {
            const formData = new FormData();
            formData.append("raw_input", rawInput);
            const response = await fetch(interactionForm.dataset.feedEndpoint || "/api/my-cat/feed", {
                method: "POST",
                body: formData,
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.detail || payload.message || "喂养任务提交失败");
            }

            const taskId = payload.task_id;
            activeTaskId = taskId;
            const statusBubble = appendEventMessage("进化中：正在分析抖音内容并准备刷新猫咪形象。", "progress");
            setTaskStatus("进化中：正在分析抖音内容并准备刷新猫咪形象。", "progress");
            interactionInput.value = "";
            updateInteractionUi();

            const poll = async () => {
                const taskResponse = await fetch(`/api/tasks/${taskId}`);
                const task = await taskResponse.json();
                if (!taskResponse.ok) {
                    throw new Error(task.detail || "任务状态获取失败");
                }
                if (task.status === "running" || task.status === "pending") {
                    const text = `进化中：${task.message || "请稍候"}`;
                    setTaskStatus(text, "progress");
                    if (statusBubble) {
                        statusBubble.textContent = text;
                    }
                    window.setTimeout(poll, 1500);
                    return;
                }
                if (task.status === "done") {
                    const refreshedCat = await refreshCatPanel();
                    const text = `${task.message || "进化完成"}，新形象已自动刷新。`;
                    setTaskStatus(text, "done");
                    if (statusBubble) {
                        statusBubble.textContent = text;
                        statusBubble.className = "message-content timeline-style task-done";
                    }
                    const logText = buildGrowthLogText(refreshedCat?.growth_log);
                    if (logText) {
                        const logKey = `${refreshedCat?.id || "cat"}-${logText}`;
                        if (lastGrowthLogKey !== logKey) {
                            appendEventMessage(logText, "done");
                            lastGrowthLogKey = logKey;
                        }
                    }
                    activeTaskId = null;
                    return;
                }
                const errorText = task.error || task.message || "任务执行失败";
                clearTaskStatus();
                if (statusBubble) {
                    statusBubble.textContent = errorText;
                    statusBubble.className = "message-content timeline-style task-error";
                }
                activeTaskId = null;
            };

            void poll();
        };

        const submitChat = async (content) => {
            interactionSubmitButton.disabled = true;
            appendMessage("user", content);
            interactionInput.value = "";
            updateInteractionUi();
            const assistantBubble = appendMessage("assistant", "");
            typewriterQueue = "";
            typewriterStreamDone = false;
            if (typewriterTimer !== null) {
                window.clearTimeout(typewriterTimer);
                typewriterTimer = null;
            }

            const formData = new FormData();
            formData.append("content", content);
            const response = await fetch(interactionForm.dataset.chatEndpoint || "/api/my-cat/chat/stream", {
                method: "POST",
                body: formData,
                headers: {
                    Accept: "text/event-stream",
                },
            });
            if (!response.ok || !response.body) {
                const fallback = await response.text();
                throw new Error(fallback || "对话失败");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const events = buffer.split("\n\n");
                buffer = events.pop() || "";
                for (const eventText of events) {
                    const line = eventText
                        .split("\n")
                        .find((item) => item.startsWith("data:"));
                    if (!line) continue;
                    const payload = JSON.parse(line.slice(5).trim());
                    if (payload.type === "token") {
                        queueTypewriterToken(assistantBubble, payload.token);
                    } else if (payload.type === "error" && assistantBubble) {
                        typewriterStreamDone = true;
                        finishTypewriter(assistantBubble);
                        assistantBubble.textContent = payload.message;
                    } else if (payload.type === "done") {
                        typewriterStreamDone = true;
                    }
                }
            }

            if (assistantBubble && typewriterStreamDone) {
                await waitForTypewriterToDrain();
            }
        };

        interactionInput.addEventListener("input", updateInteractionUi);
        updateInteractionUi();

        interactionForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const content = interactionInput.value.trim();
            if (!content) return;
            const feedLocked = interactionInput.dataset.feedLocked === "true";
            const isFeed = containsDouyinUrl(content);

            interactionSubmitButton.disabled = true;

            try {
                if (isFeed) {
                    if (activeTaskId) {
                        throw new Error("当前已有一次进化在进行中，先等待这次完成。");
                    }
                    if (feedLocked) {
                        throw new Error(interactionInput.dataset.feedLockedMessage || "当前暂时不能喂养，只能聊天。");
                    }
                    await submitFeed(content);
                } else {
                    await submitChat(content);
                }
            } catch (error) {
                clearTaskStatus();
                appendEventMessage(error.message || "处理失败", "error");
            } finally {
                interactionSubmitButton.disabled = false;
                interactionInput.focus();
                updateInteractionUi();
            }
        });

        window.addEventListener("pageshow", () => {
            interactionSubmitButton.disabled = false;
            clearTaskStatus();
            updateInteractionUi();
        });
    }

    starRatings.forEach((ratingRoot) => {
        const track = ratingRoot.querySelector("[data-star-track]");
        const hiddenInput = ratingRoot.querySelector("input[type='hidden']");
        const valueText = ratingRoot.querySelector("[data-star-value-text]");

        if (!track || !hiddenInput || !valueText) {
            return;
        }

        const stars = Array.from(track.querySelectorAll("[data-star-value]"));
        let dragging = false;
        const maxScore = Number(ratingRoot.dataset.max || track.getAttribute("aria-valuemax") || stars.length || 5);

        const clampValue = (value) => Math.max(1, Math.min(maxScore, value));

        const paint = (value) => {
            const normalized = clampValue(value);
            hiddenInput.value = String(normalized);
            valueText.textContent = `${normalized}/${maxScore}`;
            track.setAttribute("aria-valuenow", String(normalized));
            stars.forEach((star, index) => {
                star.classList.toggle("active", index < normalized);
            });
        };

        const valueFromEvent = (event) => {
            const rect = track.getBoundingClientRect();
            const offset = Math.min(Math.max(event.clientX - rect.left, 0), rect.width);
            const raw = Math.ceil((offset / rect.width) * maxScore);
            return clampValue(raw || 1);
        };

        paint(Number(hiddenInput.value || ratingRoot.dataset.value || 5));

        track.addEventListener("pointerdown", (event) => {
            dragging = true;
            track.setPointerCapture(event.pointerId);
            paint(valueFromEvent(event));
        });

        track.addEventListener("pointermove", (event) => {
            if (!dragging) {
                return;
            }
            paint(valueFromEvent(event));
        });

        const stopDragging = (event) => {
            if (!dragging) {
                return;
            }
            dragging = false;
            if (track.hasPointerCapture(event.pointerId)) {
                track.releasePointerCapture(event.pointerId);
            }
        };

        track.addEventListener("pointerup", stopDragging);
        track.addEventListener("pointercancel", stopDragging);

        track.addEventListener("click", (event) => {
            const target = event.target.closest("[data-star-value]");
            if (!target) {
                return;
            }
            paint(Number(target.dataset.starValue || 1));
        });

        track.addEventListener("keydown", (event) => {
            const currentValue = Number(hiddenInput.value || 5);
            if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
                event.preventDefault();
                paint(currentValue - 1);
            }
            if (event.key === "ArrowRight" || event.key === "ArrowUp") {
                event.preventDefault();
                paint(currentValue + 1);
            }
        });
    });

    shareCardButtons.forEach((button) => {
        bindShareButton(button);
    });

    trainingButtons.forEach((button) => {
        button.addEventListener("click", async (event) => {
            event.preventDefault();
            await submitTraining(button.dataset.actionKey, button);
        });
    });

    updateDialogBodyState();
});

