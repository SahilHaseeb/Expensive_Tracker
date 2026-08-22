// Modern AI Receipt Scanner Client Handler

document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('receiptFileInput');
    const dropzone = document.getElementById('receiptDropzone');
    const formSubheader = document.getElementById('formSubheader');

    if (!fileInput) return;

    // File change handler
    fileInput.addEventListener('change', function(e) {
        if (this.files && this.files[0]) {
            handleReceiptUpload(this.files[0]);
        }
    });

    // Drag & Drop handlers
    if (dropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, function(e) {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, function(e) {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove('dragover');
            }, false);
        });

        dropzone.addEventListener('drop', function(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files[0]) {
                handleReceiptUpload(files[0]);
            }
        });
    }

    async function handleReceiptUpload(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select an image file (JPEG or PNG).');
            return;
        }

        const formData = new FormData();
        formData.append('image', file);

        // Update UI state
        if (formSubheader) {
            formSubheader.innerHTML = '<i class="fas fa-spinner fa-spin text-primary"></i> <strong>AI Vision is scanning your receipt...</strong>';
            formSubheader.style.color = 'var(--primary)';
        }

        if (dropzone) {
            dropzone.style.opacity = '0.7';
            dropzone.style.pointerEvents = 'none';
        }

        try {
            const response = await fetch('/api/scan-receipt', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                
                // Auto populate form
                const amountInput = document.getElementById('amount');
                const categorySelect = document.getElementById('category');
                const dateInput = document.getElementById('date');
                const noteInput = document.getElementById('note');

                if (amountInput && data.amount) amountInput.value = data.amount;
                if (categorySelect && data.category) categorySelect.value = data.category;
                if (dateInput && data.date) dateInput.value = data.date;
                if (noteInput && data.merchant) {
                    noteInput.value = `${data.merchant} - ${data.note || 'Receipt'}`;
                }

                if (formSubheader) {
                    formSubheader.innerHTML = `✨ <strong>Receipt scanned successfully (${data.source})!</strong> Verify details and click Save.`;
                    formSubheader.style.color = 'var(--success)';
                }

                // Highlight amount input
                if (amountInput) {
                    amountInput.focus();
                    amountInput.style.borderColor = 'var(--success)';
                    setTimeout(() => {
                        amountInput.style.borderColor = '';
                    }, 2000);
                }
            } else {
                if (formSubheader) {
                    formSubheader.innerHTML = '⚠️ Could not extract receipt details. Please enter manually.';
                    formSubheader.style.color = 'var(--danger)';
                }
            }
        } catch (error) {
            console.error('Scan error:', error);
            if (formSubheader) {
                formSubheader.innerHTML = '⚠️ Error scanning receipt. Please enter manually.';
                formSubheader.style.color = 'var(--danger)';
            }
        } finally {
            if (dropzone) {
                dropzone.style.opacity = '1';
                dropzone.style.pointerEvents = 'auto';
            }
        }
    }
});
