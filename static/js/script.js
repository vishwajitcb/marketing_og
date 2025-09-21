/**
 * Bulletproof JavaScript - Zero-failure video processing interface
 * Handles all user interactions with comprehensive error handling
 */

class VideoProcessor {
    constructor() {
        this.form = document.getElementById('videoForm');
        this.nameInput = document.getElementById('name');
        this.birthdayInput = document.getElementById('birthday');
        this.submitBtn = document.getElementById('submitBtn');
        this.btnText = this.submitBtn.querySelector('.btn-text');
        this.btnLoading = this.submitBtn.querySelector('.btn-loading');
        
        // Session management
        this.sessionId = this.getOrCreateSessionId();
        
        this.previewSection = document.getElementById('previewSection');
        this.previewContent = document.getElementById('previewContent');
        
        this.resultSection = document.getElementById('resultSection');
        this.resultContent = document.getElementById('resultContent');
        this.downloadBtn = document.getElementById('downloadBtn');
        
        // Message elements
        this.generatingMessage = document.getElementById('generatingMessage');
        this.successMessage = document.getElementById('successMessage');
        
        // Sharing elements
        this.sharingSection = document.getElementById('sharingSection');
        this.nativeShareBtn = document.getElementById('nativeShareBtn');
        this.sharingInstructions = document.getElementById('sharingInstructions');
        
        // Video player elements
        this.videoPlayerSection = document.getElementById('videoPlayerSection');
        this.generatedVideo = document.getElementById('generatedVideo');
        this.videoSource = document.getElementById('videoSource');
        this.videoLoading = document.getElementById('videoLoading');
        this.videoError = document.getElementById('videoError');
        this.fallbackDownload = document.getElementById('fallbackDownload');
        
        this.errorSection = document.getElementById('errorSection');
        this.errorText = document.getElementById('errorText');
        this.retryBtn = document.getElementById('retryBtn');
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.setupInputValidation();
        this.setupDateInput();
        this.setupVideoPlayer();
        this.setupCleanupHandlers();
    }
    
    setupEventListeners() {
        // Form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });
        
        // Remove real-time preview - OG code will only show with video
        // this.nameInput.addEventListener('input', this.debounce(() => {
        //     this.handlePreview();
        // }, 300));
        
        // this.birthdayInput.addEventListener('change', () => {
        //     this.handlePreview();
        // });
        
        // New video button removed - no longer needed
        
        // Retry button
        this.retryBtn.addEventListener('click', () => {
            this.hideAllSections();
            this.resetForm();
        });
        
        // Sharing button
        this.nativeShareBtn.addEventListener('click', () => {
            this.nativeShare();
        });
    }
    
    setupCleanupHandlers() {
        // Disabled aggressive cleanup to allow video preview
        // Auto-cleanup scheduler handles old files (15 minutes)

        // Note: Removed beforeunload and visibilitychange cleanup
        // to prevent videos from being deleted while user is watching

        console.log('Cleanup handlers disabled - relying on server-side auto-cleanup');
    }
    
    setupInputValidation() {
        // Clear errors when user starts typing (but don't validate yet)
        this.nameInput.addEventListener('input', () => {
            this.hideError('nameError');
        });
        
        this.birthdayInput.addEventListener('change', () => {
            this.hideError('birthdayError');
        });
    }
    
    setupDateInput() {
        // Set reasonable default date range
        const today = new Date();
        const maxDate = today.toISOString().split('T')[0];
        const minDate = new Date(today.getFullYear() - 120, 0, 1).toISOString().split('T')[0];
        
        this.birthdayInput.setAttribute('max', maxDate);
        this.birthdayInput.setAttribute('min', minDate);
    }
    
    setupVideoPlayer() {
        // Video loading event
        this.generatedVideo.addEventListener('loadstart', () => {
            console.log('Video load started');
            this.showVideoLoading();
        });
        
        // Video loaded metadata
        this.generatedVideo.addEventListener('loadedmetadata', () => {
            console.log('Video metadata loaded');
        });
        
        // Video can play event
        this.generatedVideo.addEventListener('canplay', () => {
            console.log('Video can play');
            this.hideVideoLoading();
            this.hideVideoError();
        });
        
        // Video can play through event
        this.generatedVideo.addEventListener('canplaythrough', () => {
            console.log('Video can play through');
            this.hideVideoLoading();
            this.hideVideoError();
        });
        
        // Video error event
        this.generatedVideo.addEventListener('error', (e) => {
            console.error('Video error:', e);
            console.error('Video error details:', this.generatedVideo.error);
            this.hideVideoLoading();
            this.showVideoError();
        });
        
        // Video stalled event (network issues)
        this.generatedVideo.addEventListener('stalled', () => {
            console.warn('Video stalled - network issues');
        });
        
        // Video waiting event (buffering)
        this.generatedVideo.addEventListener('waiting', () => {
            console.log('Video waiting/buffering');
            this.showVideoLoading();
        });
        
        // Video playing event
        this.generatedVideo.addEventListener('playing', () => {
            console.log('Video playing');
            this.hideVideoLoading();
        });
        
        // Video ended event
        this.generatedVideo.addEventListener('ended', () => {
            console.log('Video ended');
        });
        
        // Video progress event
        this.generatedVideo.addEventListener('progress', () => {
            console.log('Video progress:', this.generatedVideo.buffered);
        });
    }
    
    loadVideo(videoUrl, retryCount = 0) {
        try {
            console.log(`Loading video: ${videoUrl} (attempt ${retryCount + 1})`);
            
            // Reset video state
            this.hideVideoError();
            this.showVideoLoading();
            
            // Clear previous source
            this.videoSource.src = '';
            this.generatedVideo.load();
            
            // Set new video source with timestamp to prevent caching issues
            const urlWithTimestamp = `${videoUrl}?t=${Date.now()}`;
            this.videoSource.src = urlWithTimestamp;
            
            // Force reload with new source
            this.generatedVideo.load();
            
            // Add timeout for video loading
            const loadTimeout = setTimeout(() => {
                if (this.generatedVideo.readyState < 2) { // HAVE_CURRENT_DATA
                    console.warn('Video loading timeout');
                    this.hideVideoLoading();
                    this.showVideoError();
                }
            }, 30000); // 30 second timeout
            
            // Clear timeout when video can play
            const clearTimeout = () => {
                clearTimeout(loadTimeout);
            };
            
            this.generatedVideo.addEventListener('canplay', clearTimeout, { once: true });
            this.generatedVideo.addEventListener('error', clearTimeout, { once: true });
            
            // Add error handling for source loading with retry
            this.videoSource.addEventListener('error', () => {
                console.error('Video source error');
                clearTimeout(loadTimeout);
                
                if (retryCount < 2) {
                    console.log(`Retrying video load (attempt ${retryCount + 2})`);
                    setTimeout(() => {
                        this.loadVideo(videoUrl, retryCount + 1);
                    }, 2000); // Wait 2 seconds before retry
                } else {
                    this.hideVideoLoading();
                    this.showVideoError();
                }
            }, { once: true });
            
        } catch (error) {
            console.error('Error loading video:', error);
            this.hideVideoLoading();
            this.showVideoError();
        }
    }
    
    validateName() {
        const name = this.nameInput.value.trim();
        
        if (!name) {
            this.showError('nameError', 'Name is missing');
            return false;
        }
        
        if (name.length < 2) {
            this.showError('nameError', 'Name must be at least 2 characters long');
            return false;
        }
        
        if (name.length > 50) {
            this.showError('nameError', 'Name must be less than 50 characters');
            return false;
        }
        
        if (!/^[a-zA-Z\s\-']+$/.test(name)) {
            this.showError('nameError', 'Name can only contain letters, spaces, hyphens, and apostrophes');
            return false;
        }
        
        this.hideError('nameError');
        return true;
    }
    
    validateBirthday() {
        const birthday = this.birthdayInput.value;
        
        if (!birthday) {
            this.showError('birthdayError', 'Date of birth is missing');
            return false;
        }
        
        const birthDate = new Date(birthday);
        const today = new Date();
        const minDate = new Date(today.getFullYear() - 120, 0, 1);
        
        if (birthDate > today) {
            this.showError('birthdayError', 'Birthday cannot be in the future');
            return false;
        }
        
        if (birthDate < minDate) {
            this.showError('birthdayError', 'Please enter a valid birthday');
            return false;
        }
        
        this.hideError('birthdayError');
        return true;
    }
    
    showError(elementId, message) {
        const errorElement = document.getElementById(elementId);
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.add('show');
        }
    }
    
    hideError(elementId) {
        const errorElement = document.getElementById(elementId);
        if (errorElement) {
            errorElement.classList.remove('show');
        }
    }
    
    handlePreview() {
        const name = this.nameInput.value.trim();
        const birthday = this.birthdayInput.value;
        
        // Only show preview if both fields have some content (but don't validate yet)
        if (!name || !birthday) {
            this.hidePreview();
            return;
        }
        
        this.makeRequest('/preview', { name, birthday })
            .then(data => {
                if (data.success) {
                    this.showPreview(data.data);
                }
            })
            .catch(error => {
                console.error('Preview error:', error);
                // Preview errors are not critical, just hide preview
                this.hidePreview();
            });
    }
    
    showPreview(data) {
        this.previewContent.innerHTML = `
            <div class="preview-item">
                <div class="preview-label">Name (${data.extracted[0]})</div>
                <div class="preview-value">${data.extracted[0]}</div>
                <div class="preview-japanese">${data.japanese[0]}</div>
            </div>
            <div class="preview-item">
                <div class="preview-label">Birthday (${data.extracted[1]})</div>
                <div class="preview-value">${data.extracted[1]}</div>
                <div class="preview-japanese">${data.japanese[1]}</div>
            </div>
            <div class="preview-item">
                <div class="preview-label">Star Sign (${data.extracted[2]})</div>
                <div class="preview-value">${data.extracted[2]}</div>
                <div class="preview-japanese">${data.japanese[2]}</div>
            </div>
        `;
        
        this.previewSection.style.display = 'block';
    }
    
    hidePreview() {
        this.previewSection.style.display = 'none';
    }
    
    async handleSubmit() {
        // Validate inputs and show specific error messages
        const nameValid = this.validateName();
        const birthdayValid = this.validateBirthday();
        
        if (!nameValid || !birthdayValid) {
            // Show error section if validation fails
            this.showErrorSection();
            return;
        }
        
        const name = this.nameInput.value.trim();
        const birthday = this.birthdayInput.value;
        
        this.setLoading(true);
        this.hideAllSections();
        
        try {
            const data = await this.makeRequest('/generate', { name, birthday });
            
            if (data.success) {
                // Show preview data immediately
                this.showPreviewData(data.data);
                
                // Start polling for video completion
                if (data.job_id) {
                    this.pollVideoStatus(data.job_id);
                }
            } else {
                this.showError(data.error || 'Generation failed');
            }
        } catch (error) {
            console.error('Generation error:', error);
            this.showError('Network error. Please check your connection and try again.');
        } finally {
            this.setLoading(false);
        }
    }
    
    async makeRequest(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Session-ID': this.sessionId
            },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Network error' }));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        return await response.json();
    }
    
    getOrCreateSessionId() {
        // Try to get existing session ID from localStorage
        let sessionId = localStorage.getItem('video_session_id');
        
        // If no session ID exists, create a new one
        if (!sessionId) {
            sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('video_session_id', sessionId);
        }
        
        return sessionId;
    }
    
    async cleanupSessionFiles() {
        try {
            const response = await fetch('/cleanup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('Session cleanup completed:', data.message);
            }
        } catch (error) {
            console.warn('Session cleanup failed:', error);
        }
    }
    
    showPreviewData(data) {
        // Store the preview data for later use when video is ready
        this.previewData = data;
        
        // Show generating message (not success yet)
        this.generatingMessage.style.display = 'block';
        this.successMessage.style.display = 'none';
        
        // Show loading state for video
        this.showVideoLoading();
        
        // Disable download button initially
        this.downloadBtn.style.display = 'none';
        
        // Hide sharing section initially
        this.sharingSection.style.display = 'none';
        
        // Hide the preview content initially - it will show when video is ready
        this.resultContent.innerHTML = '';
        
        // Hide the result section initially - only show generating message
        this.resultSection.style.display = 'block';
        this.resultContent.style.display = 'none'; // Hide the black box with code
    }
    
    showResult(data) {
        // Use stored preview data or fallback to data parameter
        const previewData = this.previewData || data;
        
        // Now show the OG code with the video - make the black box visible
        this.resultContent.style.display = 'block';
        this.resultContent.innerHTML = `
            <div class="preview-item">
                <div class="preview-label">Name</div>
                <div class="preview-value">${previewData.extracted[0]} → ${previewData.japanese[0]}</div>
            </div>
            <div class="preview-item">
                <div class="preview-label">Birthday</div>
                <div class="preview-value">${previewData.extracted[1]} → ${previewData.japanese[1]}</div>
            </div>
            <div class="preview-item">
                <div class="preview-label">Star Sign (${previewData.star_sign})</div>
                <div class="preview-value">${previewData.extracted[2]} → ${previewData.japanese[2]}</div>
            </div>
        `;
        
        // Set up video player
        if (data.video_url && data.video_url !== 'undefined') {
            this.loadVideo(data.video_url);
        } else {
            console.warn('No video URL provided, skipping video player setup');
            this.hideVideoLoading();
            this.showVideoError();
        }
        
        // Set up download button
        this.downloadBtn.href = data.download_url;
        this.downloadBtn.download = data.filename || 'personalized_video.mp4';
        
        // Set up fallback download link
        this.fallbackDownload.href = data.download_url;
        this.fallbackDownload.download = data.filename || 'personalized_video.mp4';
        
        // Show download button
        this.downloadBtn.style.display = 'inline-block';
        
        // Show sharing section
        this.sharingSection.style.display = 'block';
        this.sharingInstructions.style.display = 'block';
        
        // Show success message (video is ready)
        this.generatingMessage.style.display = 'none';
        this.successMessage.style.display = 'block';
        
        this.resultSection.style.display = 'block';
        
        // Add banner after video generation is complete
        this.addBanner();
    }
    
    showError(message) {
        this.errorText.textContent = message;
        this.errorSection.style.display = 'block';
    }
    
    showErrorSection() {
        // Show the error section when validation fails
        this.errorSection.style.display = 'block';
    }
    
    hideAllSections() {
        this.previewSection.style.display = 'none';
        this.resultSection.style.display = 'none';
        this.errorSection.style.display = 'none';
    }
    
    showVideoLoading() {
        this.videoLoading.style.display = 'flex';
        this.videoError.style.display = 'none';
    }
    
    hideVideoLoading() {
        this.videoLoading.style.display = 'none';
    }
    
    showVideoError() {
        this.videoError.style.display = 'flex';
        this.videoLoading.style.display = 'none';
    }
    
    hideVideoError() {
        this.videoError.style.display = 'none';
    }
    
    async pollVideoStatus(jobId) {
        const maxAttempts = 60; // 5 minutes max (5 second intervals)
        let attempts = 0;
        
        const poll = async () => {
            try {
                attempts++;
                const response = await fetch(`/status/${jobId}`);
                const data = await response.json();
                
                if (data.status === 'completed') {
                    // Video is ready - show the result with OG code
                    this.hideVideoLoading();
                    
                    // Use stored preview data if available, otherwise extract from data
                    let previewData = this.previewData;
                    if (!previewData) {
                        // Fallback: try to extract from data parameter
                        previewData = {
                            extracted: data.extracted || ['XX', '10', 'XX'],
                            japanese: data.japanese || ['XX', '十', 'XX'],
                            star_sign: data.star_sign || 'Capricorn'
                        };
                    }
                    
                    this.showResult({
                        ...data,
                        extracted: previewData.extracted,
                        japanese: previewData.japanese,
                        star_sign: previewData.star_sign
                    });
                    return;
                } else if (data.status === 'failed') {
                    // Video generation failed
                    this.hideVideoLoading();
                    this.showVideoError();
                    this.showError(data.error || 'Video generation failed');
                    return;
                } else if (data.status === 'processing' || data.status === 'queued') {
                    // Still processing, continue polling
                    if (attempts < maxAttempts) {
                        setTimeout(poll, 5000); // Poll every 5 seconds
                    } else {
                        // Timeout
                        this.hideVideoLoading();
                        this.showVideoError();
                        this.showError('Video generation is taking longer than expected. Please try again.');
                    }
                }
            } catch (error) {
                console.error('Status polling error:', error);
                if (attempts < maxAttempts) {
                    setTimeout(poll, 5000);
                } else {
                    this.hideVideoLoading();
                    this.showVideoError();
                    this.showError('Unable to check video generation status. Please try again.');
                }
            }
        };
        
        // Start polling
        poll();
    }
    
    setLoading(loading) {
        this.submitBtn.disabled = loading;
        
        if (loading) {
            this.btnText.style.display = 'none';
            this.btnLoading.style.display = 'flex';
        } else {
            this.btnText.style.display = 'block';
            this.btnLoading.style.display = 'none';
        }
    }
    
    resetForm() {
        this.form.reset();
        this.hideAllSections();
        this.hideError('nameError');
        this.hideError('birthdayError');
        
        // Clear stored preview data
        this.previewData = null;
        
        // Remove banner if it exists
        const existingBanner = document.querySelector('.banner-section');
        if (existingBanner) {
            existingBanner.remove();
        }
        
        // Hide sharing section
        this.sharingSection.style.display = 'none';
        this.sharingInstructions.style.display = 'none';
        
        // Reset message states
        this.generatingMessage.style.display = 'block';
        this.successMessage.style.display = 'none';
        
        // Hide the black box with code
        this.resultContent.style.display = 'none';
        this.resultContent.innerHTML = '';
        
        // Reset video player
        this.generatedVideo.pause();
        this.generatedVideo.currentTime = 0;
        this.videoSource.src = '';
        this.hideVideoLoading();
        this.hideVideoError();
        
        this.nameInput.focus();
    }
    
    async nativeShare() {
        try {
            // Check if Web Share API is supported
            if (navigator.share) {
                const videoUrl = this.downloadBtn.href;
                const shareData = {
                    title: 'My Personalized Japanese Character Video',
                    text: 'Check out my personalized Japanese character video! 🎌✨',
                    url: videoUrl
                };
                
                // Try to share with files if supported
                if (navigator.canShare && navigator.canShare({ files: [] })) {
                    try {
                        // Fetch the video file
                        const response = await fetch(videoUrl);
                        const blob = await response.blob();
                        const file = new File([blob], 'personalized_video.mp4', { type: 'video/mp4' });
                        
                        const shareDataWithFile = {
                            ...shareData,
                            files: [file]
                        };
                        
                        await navigator.share(shareDataWithFile);
                        return;
                    } catch (fileError) {
                        console.log('File sharing not supported, falling back to URL sharing');
                    }
                }
                
                // Fallback to URL sharing
                await navigator.share(shareData);
            } else {
                // Fallback for browsers without Web Share API
                this.showFallbackSharing();
            }
        } catch (error) {
            console.error('Native sharing error:', error);
            if (error.name === 'AbortError') {
                // User cancelled sharing
                return;
            }
            this.showFallbackSharing();
        }
    }
    
    
    async copyToClipboard(text, platform) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                this.showCopySuccess(platform);
            } else {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                
                try {
                    document.execCommand('copy');
                    this.showCopySuccess(platform);
                } catch (err) {
                    console.error('Fallback copy failed:', err);
                    this.showSharingError(platform);
                }
                
                document.body.removeChild(textArea);
            }
        } catch (error) {
            console.error('Clipboard error:', error);
            this.showSharingError(platform);
        }
    }
    
    showCopySuccess(platform) {
        // Create a temporary success message
        const successMsg = document.createElement('div');
        successMsg.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--success-color);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            z-index: 1000;
            font-weight: 500;
        `;
        successMsg.textContent = `Link copied for ${platform}!`;
        
        document.body.appendChild(successMsg);
        
        // Remove after 3 seconds
        setTimeout(() => {
            if (document.body.contains(successMsg)) {
                document.body.removeChild(successMsg);
            }
        }, 3000);
    }
    
    showSharingError(platform) {
        alert(`Unable to share to ${platform}. Please try copying the video link manually.`);
    }
    
    showFallbackSharing() {
        const videoUrl = this.downloadBtn.href;
        const message = "Check out my personalized Japanese character video! 🎌✨";
        
        // Show a modal with sharing options
        const modal = document.createElement('div');
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        `;
        
        modal.innerHTML = `
            <div style="
                background: white;
                padding: 2rem;
                border-radius: var(--radius-lg);
                max-width: 400px;
                width: 90%;
                text-align: center;
            ">
                <h3 style="margin-bottom: 1rem; color: var(--text-primary);">Share Your Video</h3>
                <p style="margin-bottom: 1.5rem; color: var(--text-secondary);">
                    Choose how you'd like to share your video:
                </p>
                <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                    <button onclick="navigator.clipboard.writeText('${videoUrl}').then(() => alert('Link copied!'))" 
                            style="padding: 0.75rem; background: var(--primary-color); color: white; border: none; border-radius: var(--radius-md); cursor: pointer;">
                        📋 Copy Link
                    </button>
                    <button onclick="window.open('https://wa.me/?text=${encodeURIComponent(message + ' ' + videoUrl)}', '_blank')" 
                            style="padding: 0.75rem; background: #25d366; color: white; border: none; border-radius: var(--radius-md); cursor: pointer;">
                        💬 Share to WhatsApp
                    </button>
                    <button onclick="window.open('https://twitter.com/intent/tweet?text=${encodeURIComponent(message)}&url=${encodeURIComponent(videoUrl)}', '_blank')" 
                            style="padding: 0.75rem; background: #1da1f2; color: white; border: none; border-radius: var(--radius-md); cursor: pointer;">
                        🐦 Share to Twitter
                    </button>
                    <button onclick="this.closest('.modal').remove()" 
                            style="padding: 0.75rem; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: var(--radius-md); cursor: pointer;">
                        Cancel
                    </button>
                </div>
            </div>
        `;
        
        modal.className = 'modal';
        document.body.appendChild(modal);
        
        // Close modal when clicking outside
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }
    
    
    addBanner() {
        // Check if banner already exists
        if (document.querySelector('.banner-section')) {
            return;
        }
        
        // Create banner section
        const bannerSection = document.createElement('div');
        bannerSection.className = 'banner-section';
        
        const bannerImage = document.createElement('img');
        bannerImage.src = '/static/b_2.jpg';
        bannerImage.alt = 'Banner';
        bannerImage.className = 'banner-image';
        
        bannerSection.appendChild(bannerImage);
        
        // Insert banner inside the main container, before the footer
        const main = document.querySelector('.main');
        const footer = document.querySelector('.footer');
        main.parentNode.insertBefore(bannerSection, footer);
    }
    
    // Utility function for debouncing
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    try {
        new VideoProcessor();
    } catch (error) {
        console.error('Failed to initialize video processor:', error);
        // Show fallback error message
        document.body.innerHTML = `
            <div style="padding: 2rem; text-align: center; font-family: system-ui;">
                <h1>Service Temporarily Unavailable</h1>
                <p>Please refresh the page and try again.</p>
                <button onclick="location.reload()" style="padding: 0.5rem 1rem; margin-top: 1rem;">
                    Refresh Page
                </button>
            </div>
        `;
    }
});

// Handle page visibility changes to pause/resume processing
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Page is hidden, could pause any ongoing operations
    } else {
        // Page is visible again
    }
});

// Handle offline/online events
window.addEventListener('online', () => {
    console.log('Connection restored');
});

window.addEventListener('offline', () => {
    console.log('Connection lost');
});
