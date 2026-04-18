document.addEventListener("DOMContentLoaded", () => {
    const loadingOverlay = document.getElementById("parse-loading");
    const interactionForm = document.getElementById("interaction-form");
    const interactionInput = document.getElementById("interaction-input");
    const interactionSubmitButton = document.getElementById("interaction-submit-btn");
    const interactionHint = document.getElementById("interaction-hint");
    const chatMessages = document.getElementById("chatMessages");
    const starRatings = document.querySelectorAll("[data-star-rating]");
    const douyinPattern = /(douyin\.com|iesdouyin\.com|v\.douyin\.com)/i;

    const setOverlay = (title, text) => {
        if (!loadingOverlay) return;
        const loadingTitle = loadingOverlay.querySelector("h3");
        const loadingTextEl = loadingOverlay.querySelector("p");
        if (loadingTitle) loadingTitle.textContent = title;
        if (loadingTextEl) loadingTextEl.textContent = text;
        loadingOverlay.classList.remove("hidden");
        loadingOverlay.setAttribute("aria-hidden", "false");
    };

    const hideOverlay = () => {
        if (!loadingOverlay) return;
        loadingOverlay.classList.add("hidden");
        loadingOverlay.setAttribute("aria-hidden", "true");
    };

    const scrollChatToBottom = () => {
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    };

    scrollChatToBottom();

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
            interactionHint.textContent = "检测到抖音链接，提交后会进入喂养和形象更新流程。";
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
            setOverlay("正在分析抖音内容", "系统正在解析抖音内容并准备刷新猫咪形象。");
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
            const poll = async () => {
                const taskResponse = await fetch(`/api/tasks/${taskId}`);
                const task = await taskResponse.json();
                if (!taskResponse.ok) {
                    throw new Error(task.detail || "任务状态获取失败");
                }
                if (task.status === "running" || task.status === "pending") {
                    setOverlay("正在处理中", task.message || "请稍候");
                    window.setTimeout(poll, 1500);
                    return;
                }
                if (task.status === "done") {
                    setOverlay("处理完成", task.message || "猫咪成长完成");
                    window.setTimeout(() => {
                        window.location.href = `/my-cat?message=${encodeURIComponent(task.message || "处理完成")}`;
                    }, 600);
                    return;
                }
                throw new Error(task.error || task.message || "任务执行失败");
            };

            poll();
        };

        const submitChat = async (content) => {
            interactionSubmitButton.disabled = true;
            appendMessage("user", content);
            interactionInput.value = "";
            updateInteractionUi();
            const assistantBubble = appendMessage("assistant", "");

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
                        .find((item) => item.startsWith("data: "));
                    if (!line) continue;
                    const payload = JSON.parse(line.slice(6));
                    if (payload.type === "token") {
                        if (assistantBubble) {
                            assistantBubble.textContent += payload.token;
                        }
                        scrollChatToBottom();
                    } else if (payload.type === "error" && assistantBubble) {
                        assistantBubble.textContent = payload.message;
                    }
                }
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
                    if (feedLocked) {
                        throw new Error(interactionInput.dataset.feedLockedMessage || "当前暂时不能喂养，只能聊天。");
                    }
                    await submitFeed(content);
                } else {
                    await submitChat(content);
                }
            } catch (error) {
                hideOverlay();
                window.location.href = `/my-cat?error=${encodeURIComponent(error.message || "处理失败")}`;
            } finally {
                interactionSubmitButton.disabled = false;
                interactionInput.focus();
                updateInteractionUi();
            }
        });

        window.addEventListener("pageshow", () => {
            interactionSubmitButton.disabled = false;
            hideOverlay();
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

});
