document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Elementlerini Seçme ---
    const chatBubble = document.getElementById('chat-bubble');
    const chatPopup = document.getElementById('chat-popup');
    const chatHeader = document.querySelector('.chat-header');
    const chatHeaderTitle = chatHeader ? chatHeader.querySelector('h5') : null;
    const closeChatBtn = document.getElementById('close-chat');
    const messagesContainer = document.getElementById('chat-messages');
    const mainChatFormContainer = document.getElementById('customer-chat-form');

    // --- Değişkenler ---
    const socket = io('/chat');
    let myTicketId = sessionStorage.getItem('chat_ticket_id');
    let myName = sessionStorage.getItem('chat_customer_name');
    let myToken = sessionStorage.getItem('chat_token');

    // --- HTML Şablonları ---
    const supportFormHTML = `
        <div id="support-form-container" class="p-3">
            <p class="text-muted small">Lütfen sorununuzu ve bilgilerinizi girin. En kısa sürede bir yetkili size yardımcı olacaktır.</p>
            <form id="support-ticket-form" autocomplete="off">
                <div class="mb-2">
                    <input type="text" name="name" class="form-control form-control-sm" placeholder="Adınız Soyadınız" required>
                </div>
                <div class="mb-2">
                    <input type="email" name="email" class="form-control form-control-sm" placeholder="E-posta Adresiniz" required>
                </div>
                <div class="mb-2">
                    <textarea name="subject" class="form-control form-control-sm" placeholder="Sorununuz..." rows="4" required></textarea>
                </div>
                <button type="submit" class="btn btn-primary w-100">Destek Talebi Gönder</button>
            </form>
        </div>`;

    const waitingHTML = `<div class="p-3 text-center text-muted m-auto">Talebiniz alındı. Sıradasınız...<br><br>Lütfen bekleyin, bir yetkili sohbete katılacak.</div>`;

    const chatInputHTML = `<input id="customer-message-input" type="text" class="form-control" placeholder="Mesajınızı yazın..." autocomplete="off"><button type="submit"><i class="bi bi-send-fill"></i></button>`;

    // --- Arayüz Yönetim Fonksiyonları ---
    function showForm() {
        myTicketId = null;
        myName = '';
        myToken = null;
        sessionStorage.removeItem('chat_ticket_id');
        sessionStorage.removeItem('chat_customer_name');
        sessionStorage.removeItem('chat_token');

        if(chatHeaderTitle) chatHeaderTitle.textContent = 'Canlı Destek';

        const existingEndBtn = document.getElementById('end-chat-btn');
        if(existingEndBtn) existingEndBtn.remove();

        if(messagesContainer) messagesContainer.innerHTML = supportFormHTML;
        if(mainChatFormContainer) mainChatFormContainer.style.display = 'none';

        const supportForm = document.getElementById('support-ticket-form');
        if(supportForm) {
            supportForm.addEventListener('submit', handleTicketSubmit);
        }
    }

    function handleTicketSubmit(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData.entries());
        myName = data.name;
        sessionStorage.setItem('chat_customer_name', myName);
        socket.emit('new_support_ticket', data);
        messagesContainer.innerHTML = waitingHTML;
    }

    function showChatInterface() {
        if(chatHeaderTitle) chatHeaderTitle.textContent = `Destek Sohbeti (Talep #${myTicketId})`;

        if (chatHeader && !document.getElementById('end-chat-btn')) {
            const endChatButton = document.createElement('button');
            endChatButton.id = 'end-chat-btn';
            endChatButton.className = 'btn btn-danger btn-sm';
            endChatButton.textContent = 'Sohbeti Bitir';
            chatHeader.appendChild(endChatButton);
            endChatButton.addEventListener('click', handleEndChat);
        }

        if(messagesContainer) messagesContainer.innerHTML = '<div id="chat-messages-display" class="d-flex flex-column gap-2 p-3" style="overflow-y: auto; flex-grow: 1;"></div>';
        if(mainChatFormContainer) {
            mainChatFormContainer.innerHTML = chatInputHTML;
            mainChatFormContainer.style.display = 'flex';
            mainChatFormContainer.addEventListener('submit', handleMessageSubmit);
            document.getElementById('customer-message-input').focus();
        }

        socket.emit('join_chat_room', { ticket_id: parseInt(myTicketId) });
    }

    function handleMessageSubmit(e) {
        e.preventDefault();
        const messageInput = document.getElementById('customer-message-input');
        const message = messageInput.value.trim();
        if (message && myTicketId) {
            appendMessage({ sender: myName || 'Siz', message: message, role: 'customer' });
            socket.emit('send_message', { ticket_id: parseInt(myTicketId), message: message });
            messageInput.value = '';
        }
    }

    function handleEndChat() {
        if (myTicketId && myToken && confirm("Bu sohbeti sonlandırmak istediğinizden emin misiniz?")) {
            socket.emit('close_chat', { ticket_id: parseInt(myTicketId), token: myToken });
        }
    }

    function appendMessage(data) {
        const display = document.getElementById('chat-messages-display');
        if (!display) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message';
        const senderDisplay = `<strong>${data.sender}:</strong> `;

        if (data.role === 'system') {
            messageDiv.className = 'system-message';
            messageDiv.textContent = data.message;
        } else {
            messageDiv.innerHTML = `${senderDisplay}${data.message.replace(/</g, "&lt;").replace(/>/g, "&gt;")}`;
            if (data.role === 'customer') {
                messageDiv.classList.add('user-message');
            } else {
                messageDiv.classList.add('support-message');
            }
        }
        display.appendChild(messageDiv);
        display.scrollTop = display.scrollHeight;
    }

    // --- DOM Olayları ---
    if(chatBubble) {
        chatBubble.addEventListener('click', () => {
            chatPopup.style.display = 'flex';
            chatBubble.style.display = 'none';
        });
    }

    if(closeChatBtn) {
        closeChatBtn.addEventListener('click', () => {
            chatPopup.style.display = 'none';
            chatBubble.style.display = 'block';
        });
    }

    // --- SOCKET.IO OLAYLARI ---
    socket.on('ticket_received', function(data) {
        myTicketId = data.ticket_id;
        myToken = data.token;
        sessionStorage.setItem('chat_ticket_id', myTicketId);
        sessionStorage.setItem('chat_token', myToken);
    });

    socket.on('form_error', function(data) {
        alert("Form hatası: " + JSON.stringify(data.errors));
        showForm();
    });

    socket.on('chat_approved', function(data) {
        if (myTicketId && parseInt(myTicketId) === data.ticket_id) {
            showChatInterface();
        }
    });

    socket.on('load_history', function(data){
        const display = document.getElementById('chat-messages-display');
        if(display) {
            display.innerHTML = '';
            data.messages.forEach(msg => appendMessage(msg));
        }
    });

    socket.on('new_message', function(data){
        appendMessage(data);
    });

    socket.on('status', function(data){
        appendMessage({ sender: 'Sistem', message: data.msg, role: 'system' });
    });

    socket.on('chat_closed', function(data) {
        if(myTicketId && parseInt(myTicketId) === data.ticket_id) {
            if(mainChatFormContainer) mainChatFormContainer.style.display = 'none';
            appendMessage({ sender: 'Sistem', message: 'Bu sohbet sonlandırıldı. Yeni bir talep için pencereyi kapatıp tekrar açabilirsiniz.', role: 'system' });

            const endChatBtn = document.getElementById('end-chat-btn');
            if(endChatBtn) endChatBtn.remove();

            sessionStorage.removeItem('chat_ticket_id');
            sessionStorage.removeItem('chat_customer_name');
            sessionStorage.removeItem('chat_token');
            myTicketId = null;
        }
    });

    // --- BAŞLANGIÇ KONTROLÜ ---
    if (myTicketId && myToken) {
        showChatInterface();
    } else {
        showForm();
    }
});