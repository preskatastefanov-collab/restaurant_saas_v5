const chatLauncher = document.getElementById("chatLauncher");
const chatWidget = document.getElementById("chatWidget");
const minimizeBtn = document.getElementById("minimizeBtn");
const chatLog = document.getElementById("chatLog");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("send-btn");
const chatQuickActions = document.getElementById("chatQuickActions");
const chatHeader = document.getElementById("chatHeader");
const langBgBtn = document.getElementById("langBgBtn");
const langEnBtn = document.getElementById("langEnBtn");

const CHATBOT_CONFIG = window.CHATBOT_CONFIG || {};
const CHAT_ENDPOINT = CHATBOT_CONFIG.chatEndpoint || "/chat";

let welcomeShown = false;
let currentLanguage = "bg";
let isSending = false;
let typingEl = null;

if (chatLauncher && chatWidget) {
    chatLauncher.addEventListener("click", openWidget);
}

if (minimizeBtn && chatWidget) {
    minimizeBtn.addEventListener("click", closeWidget);
}

if (sendBtn) {
    sendBtn.addEventListener("click", () => sendMessage(userInput ? userInput.value : ""));
}

if (userInput) {
    userInput.addEventListener("keypress", function (e) {
        if (e.key === "Enter") {
            sendMessage(userInput.value);
        }
    });
}

if (langBgBtn) {
    langBgBtn.addEventListener("click", () => {
        setLanguage("bg");
        sendMessage("Български", true);
    });
}

if (langEnBtn) {
    langEnBtn.addEventListener("click", () => {
        setLanguage("en");
        sendMessage("English", true);
    });
}

applyWidgetStyles();
setLanguage("bg");

function setLanguage(lang) {
    currentLanguage = lang === "en" ? "en" : "bg";
    updateLanguageButtons();
}

function updateLanguageButtons() {
    if (langBgBtn) {
        langBgBtn.classList.toggle("active", currentLanguage === "bg");
    }

    if (langEnBtn) {
        langEnBtn.classList.toggle("active", currentLanguage === "en");
    }

    if (userInput) {
        userInput.placeholder = currentLanguage === "en"
            ? "Write a message..."
            : "Напишете съобщение...";
    }
}

function getDefaultButtons() {
    const type = CHATBOT_CONFIG.businessType || "restaurant";

    if (currentLanguage === "en") {
        if (["restaurant", "cafe", "bar", "pub", "pizzeria"].includes(type)) {
            return ["New reservation", "Menu", "Contact", "🇧🇬 Български"];
        }

        if (type === "food_truck") {
            return ["Menu", "Location", "Contact", "🇧🇬 Български"];
        }

        return ["Menu", "Contact", "🇧🇬 Български"];
    }

    if (["restaurant", "cafe", "bar", "pub", "pizzeria"].includes(type)) {
        return ["Нова резервация", "Меню", "Контакти", "🇬🇧 English"];
    }

    if (type === "food_truck") {
        return ["Меню", "Локация", "Контакти", "🇬🇧 English"];
    }

    return ["Меню", "Контакти", "🇬🇧 English"];
}

function getWelcomeFallback() {
    const type = CHATBOT_CONFIG.businessType || "restaurant";

    const bgMessages = {
        restaurant: "👋 Здравейте! Мога да помогна с меню, препоръки, контакти или резервация.",
        cafe: "👋 Здравейте! Мога да помогна с кафе, десерти, работно време или резервация.",
        bar: "👋 Здравейте! Мога да помогна с напитки, коктейли, меню, контакти или резервация.",
        pub: "👋 Здравейте! Мога да помогна с бира, мезета, меню, контакти или резервация.",
        pizzeria: "👋 Здравейте! Мога да помогна с пици, меню, контакти или резервация.",
        fast_food: "👋 Здравейте! Мога да помогна с меню, цени и информация за поръчка.",
        bakery: "👋 Здравейте! Мога да помогна с продукти, наличности, поръчки и работно време.",
        sweet_shop: "👋 Здравейте! Мога да помогна с торти, десерти, заявки и работно време.",
        food_truck: "👋 Здравейте! Мога да помогна с меню, локация и работно време.",
        other: "👋 Здравейте! С какво мога да помогна?"
    };

    const enMessages = {
        restaurant: "👋 Hello! I can help with the menu, recommendations, contact details or reservations.",
        cafe: "👋 Hello! I can help with coffee, desserts, opening hours or reservations.",
        bar: "👋 Hello! I can help with drinks, cocktails, menu, contact details or reservations.",
        pub: "👋 Hello! I can help with beer, appetizers, menu, contact details or reservations.",
        pizzeria: "👋 Hello! I can help with pizzas, menu, contact details or reservations.",
        fast_food: "👋 Hello! I can help with the menu, prices and order information.",
        bakery: "👋 Hello! I can help with products, availability, orders and opening hours.",
        sweet_shop: "👋 Hello! I can help with cakes, desserts, requests and opening hours.",
        food_truck: "👋 Hello! I can help with the menu, location and opening hours.",
        other: "👋 Hello! How can I help?"
    };

    return currentLanguage === "en"
        ? (enMessages[type] || enMessages.other)
        : (bgMessages[type] || bgMessages.other);
}

function applyWidgetStyles() {
    if (chatLauncher && CHATBOT_CONFIG.primaryColor) {
        chatLauncher.style.background = CHATBOT_CONFIG.primaryColor;
    }

    // Premium widget дизайнът вече се управлява от CSS.
    // Не сменяме header background тук, за да не разваля dark premium стила.
}

function openWidget() {
    if (!chatWidget) return;

    chatWidget.classList.remove("hidden");

    if (chatLauncher) {
        chatLauncher.style.display = "none";
    }

    if (!welcomeShown) {
        showWelcomeMessage();
        welcomeShown = true;
    }

    setTimeout(() => {
        if (userInput) userInput.focus();
    }, 100);
}

function closeWidget() {
    if (!chatWidget) return;

    chatWidget.classList.add("hidden");

    if (chatLauncher) {
        chatLauncher.style.display = "flex";
    }
}

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function addMessage(text, type = "bot", imageUrl = "") {
    if (!chatLog) return;

    const msg = document.createElement("div");
    msg.className = `message ${type}`;

    const textEl = document.createElement("div");
    textEl.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
    msg.appendChild(textEl);

    if (imageUrl) {
        const imgWrap = document.createElement("div");
        imgWrap.className = "chat-image-wrap";

        const img = document.createElement("img");
        img.className = "chat-image";
        img.src = imageUrl;
        img.alt = currentLanguage === "en" ? "Item photo" : "Снимка на артикул";
        img.loading = "lazy";

        imgWrap.appendChild(img);
        msg.appendChild(imgWrap);
    }

    chatLog.appendChild(msg);
    scrollChatToBottom();
}

function showTyping() {
    if (!chatLog || typingEl) return;

    typingEl = document.createElement("div");
    typingEl.className = "message bot typing-message";
    typingEl.innerHTML = `
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
    `;

    chatLog.appendChild(typingEl);
    scrollChatToBottom();
}

function removeTyping() {
    if (typingEl) {
        typingEl.remove();
        typingEl = null;
    }
}

function scrollChatToBottom() {
    if (!chatLog) return;
    chatLog.scrollTop = chatLog.scrollHeight;
}

function setSendingState(state) {
    isSending = state;

    if (sendBtn) {
        sendBtn.disabled = state;
        sendBtn.classList.toggle("disabled", state);
    }

    if (userInput) {
        userInput.disabled = state;
    }
}

function setQuickActions(buttons = []) {
    if (!chatQuickActions) return;

    chatQuickActions.innerHTML = "";

    if (!Array.isArray(buttons)) return;

    buttons.forEach(label => {
        const btn = document.createElement("button");
        btn.className = "quick-btn";
        btn.type = "button";
        btn.innerText = label;

        btn.addEventListener("click", () => {
            if (isSending) return;

            const labelText = String(label || "");

            if (labelText.includes("English")) {
                setLanguage("en");
            }

            if (labelText.includes("Български")) {
                setLanguage("bg");
            }

            sendMessage(labelText);
        });

        chatQuickActions.appendChild(btn);
    });
}

function showWelcomeMessage() {
    const customWelcome = currentLanguage === "bg"
        ? (CHATBOT_CONFIG.welcomeMessage || getWelcomeFallback())
        : getWelcomeFallback();

    addMessage(customWelcome, "bot");
    setQuickActions(getDefaultButtons());
}

async function sendMessage(message, silentUserMessage = false) {
    const cleanMessage = (message || "").trim();
    if (!cleanMessage || isSending) return;

    if (!silentUserMessage) {
        addMessage(cleanMessage, "user");
    }

    if (userInput) {
        userInput.value = "";
    }

    setQuickActions([]);
    setSendingState(true);
    showTyping();

    try {
        const res = await fetch(CHAT_ENDPOINT, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: cleanMessage,
                language: currentLanguage
            })
        });

        const data = await res.json();

        const lower = cleanMessage.toLowerCase();

        if (lower.includes("english")) {
            setLanguage("en");
        }

        if (lower.includes("български")) {
            setLanguage("bg");
        }

        removeTyping();

        addMessage(
            data.text || (currentLanguage === "en" ? "No response." : "Няма отговор."),
            "bot",
            data.image_url || ""
        );

        setQuickActions(data.buttons || getDefaultButtons());

    } catch (error) {
        removeTyping();

        addMessage(
            currentLanguage === "en"
                ? "⚠️ A connection error occurred."
                : "⚠️ Възникна грешка при връзката със сървъра.",
            "bot"
        );

        setQuickActions(getDefaultButtons());

    } finally {
        setSendingState(false);

        if (userInput) {
            userInput.focus();
        }
    }
}