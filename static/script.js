const chatLauncher = document.getElementById("chatLauncher");
const chatWidget = document.getElementById("chatWidget");
const minimizeBtn = document.getElementById("minimizeBtn");
const chatLog = document.getElementById("chatLog");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("send-btn");
const chatQuickActions = document.getElementById("chatQuickActions");
const chatHeader = document.getElementById("chatHeader");

const CHATBOT_CONFIG = window.CHATBOT_CONFIG || {};
const CHAT_ENDPOINT = CHATBOT_CONFIG.chatEndpoint || "/chat";

let welcomeShown = false;

if (chatLauncher && chatWidget) {
    chatLauncher.addEventListener("click", toggleWidget);
}

if (minimizeBtn && chatWidget) {
    minimizeBtn.addEventListener("click", toggleWidget);
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

applyWidgetStyles();

function applyWidgetStyles() {
    if (chatLauncher && CHATBOT_CONFIG.primaryColor) {
        chatLauncher.style.background = CHATBOT_CONFIG.primaryColor;
    }

    if (chatHeader && CHATBOT_CONFIG.primaryColor) {
        chatHeader.style.background = CHATBOT_CONFIG.primaryColor;
    }
}

function toggleWidget() {
    if (!chatWidget) return;

    chatWidget.classList.toggle("hidden");

    if (!chatWidget.classList.contains("hidden") && !welcomeShown) {
        showWelcomeMessage();
        welcomeShown = true;
    }
}

function addMessage(text, type = "bot") {
    if (!chatLog) return;

    const msg = document.createElement("div");
    msg.className = `message ${type}`;
    msg.innerHTML = String(text || "").replace(/\n/g, "<br>");
    chatLog.appendChild(msg);
    chatLog.scrollTop = chatLog.scrollHeight;
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
        btn.addEventListener("click", () => sendMessage(label));
        chatQuickActions.appendChild(btn);
    });
}

function showWelcomeMessage() {
    const customWelcome =
        CHATBOT_CONFIG.welcomeMessage ||
        "👋 Здравейте! С какво мога да помогна?";

    addMessage(customWelcome, "bot");
    setQuickActions(["Нова резервация", "Меню", "Контакти"]);
}

async function sendMessage(message) {
    const cleanMessage = (message || "").trim();
    if (!cleanMessage) return;

    addMessage(cleanMessage, "user");

    if (userInput) {
        userInput.value = "";
    }

    setQuickActions([]);

    try {
        const res = await fetch(CHAT_ENDPOINT, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message: cleanMessage })
        });

        const data = await res.json();

        addMessage(data.text || "Няма отговор.", "bot");
        setQuickActions(data.buttons || []);
    } catch (error) {
        addMessage("⚠️ Възникна грешка при връзката със сървъра.", "bot");
        setQuickActions(["Нова резервация", "Меню", "Контакти"]);
    }
}