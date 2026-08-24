// Universal Voice-to-Expense Controller (Supports Chrome, Edge, Safari, Firefox, Opera, and Mobile)

let recognition = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let mediaStream = null;

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
    const naturalInput = document.getElementById('voiceNaturalInput');

    if (status) status.innerText = 'Click "Start Speaking" and speak your expense naturally...';
    if (transcript) {
        transcript.innerText = '';
        transcript.style.display = 'none';
    }
    if (naturalInput) naturalInput.value = '';
    if (btn) btn.innerHTML = '<i class="fas fa-microphone"></i> Start Speaking';
    if (pulse) pulse.classList.remove('pulse-active');
}

function toggleVoiceRecording() {
    if (!isRecording) {
        startUniversalVoiceRecording();
    } else {
        stopVoiceRecording();
    }
}

function startUniversalVoiceRecording() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    // Mode 1: Web Speech API (Chrome, Edge, Safari, Android)
    if (SpeechRecognition) {
        startWebSpeechRecognition(SpeechRecognition);
    } 
    // Mode 2: HTML5 MediaRecorder (Firefox, Desktop Linux, Custom Browsers)
    else if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        startMediaRecorderAudio();
    } 
    else {
        // Mode 3: Universal Fallback
        const status = document.getElementById('voiceStatus');
        if (status) status.innerHTML = '⚠️ Microphone access is not supported. Please type your expense below:';
        const naturalInput = document.getElementById('voiceNaturalInput');
        if (naturalInput) naturalInput.focus();
    }
}

// 1. Web Speech API Handler (Chrome / Edge / Safari)
function startWebSpeechRecognition(SpeechRecognition) {
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
        if (status) status.innerText = '🎙️ Listening... Speak naturally (e.g. "Spent 1200 on petrol")';
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

        if (event.results[0].isFinal) {
            processVoiceText(text);
        }
    };

    recognition.onerror = function(event) {
        console.warn('Speech recognition warning/fallback:', event.error);
        if (event.error === 'not-allowed') {
            if (status) status.innerText = '⚠️ Microphone permission denied. Please allow microphone access.';
        } else {
            // Fallback to MediaRecorder on error
            startMediaRecorderAudio();
        }
    };

    recognition.onend = function() {
        if (isRecording) {
            stopVoiceRecording();
        }
    };

    recognition.start();
}

// 2. MediaRecorder Audio Stream Handler (Firefox Desktop & Universal Fallback)
async function startMediaRecorderAudio() {
    const status = document.getElementById('voiceStatus');
    const btn = document.getElementById('startVoiceBtn');
    const pulse = document.getElementById('micPulse');

    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];

        const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 
                         (MediaRecorder.isTypeSupported('audio/ogg') ? 'audio/ogg' : 'audio/wav');

        mediaRecorder = new MediaRecorder(mediaStream, { mimeType: mimeType });

        mediaRecorder.ondataavailable = function(e) {
            if (e.data.size > 0) {
                audioChunks.push(e.data);
            }
        };

        mediaRecorder.onstop = async function() {
            if (audioChunks.length > 0) {
                const audioBlob = new Blob(audioChunks, { type: mimeType });
                await sendAudioBlobForTranscription(audioBlob);
            }
        };

        mediaRecorder.start(250);
        isRecording = true;

        if (status) status.innerText = '🎙️ Recording voice... Speak clearly, then click "Stop & Process"';
        if (btn) btn.innerHTML = '<i class="fas fa-stop"></i> Stop & Process';
        if (pulse) pulse.classList.add('pulse-active');

    } catch (err) {
        console.error('MediaRecorder error:', err);
        if (status) status.innerText = '⚠️ Microphone permission required. Please allow access or type below:';
        isRecording = false;
        if (btn) btn.innerHTML = '<i class="fas fa-microphone"></i> Start Speaking';
        if (pulse) pulse.classList.remove('pulse-active');
    }
}

function stopVoiceRecording() {
    isRecording = false;

    if (recognition) {
        try { recognition.stop(); } catch(e) {}
    }

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        try { mediaRecorder.stop(); } catch(e) {}
    }

    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }

    const btn = document.getElementById('startVoiceBtn');
    const pulse = document.getElementById('micPulse');
    if (btn) btn.innerHTML = '<i class="fas fa-microphone"></i> Start Speaking';
    if (pulse) pulse.classList.remove('pulse-active');
}

// Send Firefox MediaRecorder Audio to Backend Gemini Engine
async function sendAudioBlobForTranscription(audioBlob) {
    const status = document.getElementById('voiceStatus');
    const transcript = document.getElementById('voiceTranscript');
    if (status) status.innerHTML = '<i class="fas fa-spinner fa-spin text-primary"></i> Transcribing voice with AI...';

    const formData = new FormData();
    formData.append('audio', audioBlob, 'voice_recording.webm');

    try {
        const response = await fetch('/api/transcribe-voice-audio', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            if (transcript && data.transcript) {
                transcript.style.display = 'block';
                transcript.innerText = `"${data.transcript}"`;
            }
            applyExtractedExpense(data);
        } else {
            if (status) status.innerText = '⚠️ Could not parse audio. Please try again or type below.';
        }
    } catch (e) {
        console.error('Audio upload error:', e);
        if (status) status.innerText = '⚠️ Network error processing audio.';
    }
}

// Process Text (Heuristic & AI NLP)
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
            applyExtractedExpense(data);
        } else {
            if (status) status.innerText = '⚠️ Could not parse expense details. Please try again.';
        }
    } catch (e) {
        console.error('Voice parse error:', e);
        if (status) status.innerText = '⚠️ Network error processing speech.';
    }
}

// Parse text typed manually in the modal
function parseTypedVoiceText() {
    const input = document.getElementById('voiceNaturalInput');
    if (input && input.value.trim()) {
        processVoiceText(input.value.trim());
    }
}

// Apply extracted expense to form or redirect to Add Expense page
function applyExtractedExpense(data) {
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
    } else {
        window.location.href = `/add?amount=${data.amount || 0}&category=${encodeURIComponent(data.category || 'Other')}&note=${encodeURIComponent(data.note || '')}`;
    }
}
