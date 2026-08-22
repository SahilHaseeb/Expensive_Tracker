// Voice-to-Expense Web Speech API Controller

let recognition = null;
let isRecording = false;

document.addEventListener('DOMContentLoaded', function() {
    const dashboardVoiceBtn = document.getElementById('dashboardVoiceBtn');
    if (dashboardVoiceBtn) {
        dashboardVoiceBtn.addEventListener('click', openVoiceModalDirect);
    }
});

function openVoiceModalDirect() {
    const modal = document.getElementById('voiceModal');
    if (modal) {
        modal.style.display = 'flex';
        resetVoiceUI();
    }
}

function closeVoiceModal() {
    const modal = document.getElementById('voiceModal');
    if (modal) {
        modal.style.display = 'none';
        if (isRecording) stopVoiceRecording();
    }
}

function resetVoiceUI() {
    const status = document.getElementById('voiceStatus');
    const transcript = document.getElementById('voiceTranscript');
    const btn = document.getElementById('startVoiceBtn');
    const pulse = document.getElementById('micPulse');

    if (status) status.innerText = 'Click "Start Speaking" and speak your expense naturally...';
    if (transcript) {
        transcript.innerText = '';
        transcript.style.display = 'none';
    }
    if (btn) btn.innerHTML = '<i class="fas fa-play"></i> Start Speaking';
    if (pulse) pulse.classList.remove('pulse-active');
}

function toggleVoiceRecording() {
    if (!isRecording) {
        startVoiceRecording();
    } else {
        stopVoiceRecording();
    }
}

function startVoiceRecording() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert('Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.');
        return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    const status = document.getElementById('voiceStatus');
    const transcript = document.getElementById('voiceTranscript');
    const btn = document.getElementById('startVoiceBtn');
    const pulse = document.getElementById('micPulse');

    recognition.onstart = function() {
        isRecording = true;
        if (status) status.innerText = '🎙️ Listening... Speak your expense (e.g. "Spent 1200 on petrol")';
        if (btn) btn.innerHTML = '<i class="fas fa-stop"></i> Stop & Process';
        if (pulse) pulse.classList.add('pulse-active');
    };

    recognition.onresult = function(event) {
        const text = Array.from(event.results)
            .map(result => result[0].transcript)
            .join('');

        if (transcript) {
            transcript.style.display = 'block';
            transcript.innerText = `"${text}"`;
        }

        // If final result
        if (event.results[0].isFinal) {
            processVoiceText(text);
        }
    };

    recognition.onerror = function(event) {
        console.error('Speech error:', event.error);
        if (status) status.innerText = `⚠️ Microphone error: ${event.error}. Please try again.`;
        stopVoiceRecording();
    };

    recognition.onend = function() {
        if (isRecording) {
            stopVoiceRecording();
        }
    };

    recognition.start();
}

function stopVoiceRecording() {
    isRecording = false;
    if (recognition) {
        try { recognition.stop(); } catch(e) {}
    }
    const btn = document.getElementById('startVoiceBtn');
    const pulse = document.getElementById('micPulse');
    if (btn) btn.innerHTML = '<i class="fas fa-play"></i> Start Speaking';
    if (pulse) pulse.classList.remove('pulse-active');
}

async function processVoiceText(spokenText) {
    const status = document.getElementById('voiceStatus');
    if (status) status.innerHTML = '<i class="fas fa-spinner fa-spin text-primary"></i> Analyzing speech with AI...';

    try {
        const response = await fetch('/api/parse-voice-expense', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: spokenText })
        });

        if (response.ok) {
            const data = await response.json();
            
            // If on Add Expense page, auto-fill form directly
            const amountInput = document.getElementById('amount');
            const categorySelect = document.getElementById('category');
            const dateInput = document.getElementById('date');
            const noteInput = document.getElementById('note');

            if (amountInput && categorySelect) {
                if (data.amount) amountInput.value = data.amount;
                if (data.category) categorySelect.value = data.category;
                if (data.date && dateInput) dateInput.value = data.date;
                if (data.note && noteInput) noteInput.value = data.note;

                closeVoiceModal();
                amountInput.focus();
                alert(`✨ Extracted:\nAmount: ${data.amount}\nCategory: ${data.category}\nNote: ${data.note}`);
            } else {
                // On dashboard page: redirect to Add Expense with query parameters
                window.location.href = `/add?amount=${data.amount}&category=${data.category}&note=${encodeURIComponent(data.note)}`;
            }
        } else {
            if (status) status.innerText = '⚠️ Could not parse expense details. Please try again.';
        }
    } catch (e) {
        console.error('Voice parse error:', e);
        if (status) status.innerText = '⚠️ Network error processing speech.';
    }
}
