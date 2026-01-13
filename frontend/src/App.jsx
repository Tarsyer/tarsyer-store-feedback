import React, { useState, useRef, useEffect } from 'react';
import Auth from './components/Auth';

const API_BASE = import.meta.env.VITE_API_URL || 'https://store-feedback.tarsyer.com';

// Simple store list - can be expanded or fetched from API
const STORES = [
  { code: 'W001', name: 'Bata - MG Road' },
  { code: 'W002', name: 'Bata - Brigade Road' },
  { code: 'W003', name: 'Bata - Koramangala' },
  { code: 'W004', name: 'Bata - Indiranagar' },
  { code: 'W005', name: 'Bata - Whitefield' },
  // Add more stores as needed
];

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [store, setStore] = useState(null);
  const [view, setView] = useState('record'); // record, history
  const [recording, setRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [feedbacks, setFeedbacks] = useState([]);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const fileInputRef = useRef(null);

  // Check stored authentication and login
  useEffect(() => {
    const staffAuth = localStorage.getItem('staff_auth');
    if (staffAuth === 'true') {
      setIsAuthenticated(true);
    }

    const savedStore = localStorage.getItem('store');
    if (savedStore) {
      setStore(JSON.parse(savedStore));
      setIsLoggedIn(true);
    }
  }, []);

  // Fetch history when switching to history view
  useEffect(() => {
    if (view === 'history' && store) {
      fetchHistory();
    }
  }, [view, store]);

  const handleLogin = (storeCode) => {
    const selectedStore = STORES.find(s => s.code === storeCode) || { code: storeCode, name: storeCode };
    setStore(selectedStore);
    localStorage.setItem('store', JSON.stringify(selectedStore));
    setIsLoggedIn(true);
  };

  const handleLogout = () => {
    setStore(null);
    localStorage.removeItem('store');
    localStorage.removeItem('staff_auth');
    setIsLoggedIn(false);
    setIsAuthenticated(false);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      chunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorderRef.current.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current.start();
      setRecording(true);
      setUploadStatus(null);
    } catch (err) {
      alert('Unable to access microphone. Please grant permission.');
      console.error(err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setAudioBlob(file);
      setAudioUrl(URL.createObjectURL(file));
      setUploadStatus(null);
    }
  };

  const clearRecording = () => {
    setAudioBlob(null);
    setAudioUrl(null);
    setUploadStatus(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const uploadFeedback = async () => {
    if (!audioBlob || !store) return;

    setUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    formData.append('store_code', store.code);
    formData.append('recorded_date', selectedDate);
    
    // Determine filename based on source
    const ext = audioBlob.type.includes('webm') ? 'webm' : 'mp3';
    const filename = `${store.code}_${selectedDate}_feedback.${ext}`;
    formData.append('media', audioBlob, filename);

    try {
      const response = await fetch(`${API_BASE}/api/v1/feedback`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        setUploadStatus({ success: true, message: 'Feedback uploaded successfully!' });
        clearRecording();
      } else {
        const error = await response.json();
        setUploadStatus({ success: false, message: error.detail || 'Upload failed' });
      }
    } catch (err) {
      setUploadStatus({ success: false, message: 'Network error. Please try again.' });
      console.error(err);
    } finally {
      setUploading(false);
    }
  };

  const fetchHistory = async () => {
    if (!store) return;
    
    try {
      const response = await fetch(
        `${API_BASE}/api/v1/feedbacks?store_code=${store.code}&limit=20`
      );
      if (response.ok) {
        const data = await response.json();
        setFeedbacks(data);
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  };

  // Authentication Screen
  if (!isAuthenticated) {
    return <Auth onLogin={setIsAuthenticated} userType="staff" />;
  }

  // Login Screen (Store Selection)
  if (!isLoggedIn) {
    return (
      <div className="login-container">
        <div className="login-card">
          <div className="logo">
            <img src="/Tarsyer_Logo.png" alt="Tarsyer Store Sentiment" style={{ height: '80px', marginBottom: '16px' }} />
            <h1>Tarsyer Store Sentiment</h1>
          </div>
          <p className="subtitle">Select your store to continue</p>
          
          <select 
            className="store-select"
            onChange={(e) => e.target.value && handleLogin(e.target.value)}
            defaultValue=""
          >
            <option value="" disabled>Choose your store...</option>
            {STORES.map(s => (
              <option key={s.code} value={s.code}>{s.code} - {s.name}</option>
            ))}
          </select>
          
          <div className="manual-entry">
            <p>Or enter store code manually:</p>
            <input
              type="text"
              placeholder="W001"
              pattern="W\d{3}"
              maxLength={4}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && /^W\d{3}$/i.test(e.target.value)) {
                  handleLogin(e.target.value.toUpperCase());
                }
              }}
            />
          </div>
        </div>
      </div>
    );
  }

  // Main App
  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="store-info">
          <span className="store-code">{store.code}</span>
        </div>
        <button className="logout-btn" onClick={handleLogout}>Logout</button>
      </header>

      {/* Navigation */}
      <nav className="app-nav">
        <button 
          className={`nav-btn ${view === 'record' ? 'active' : ''}`}
          onClick={() => setView('record')}
        >
          Record
        </button>
        <button 
          className={`nav-btn ${view === 'history' ? 'active' : ''}`}
          onClick={() => setView('history')}
        >
          History
        </button>
      </nav>

      {/* Content */}
      <main className="app-content">
        {view === 'record' ? (
          <div className="record-view">
            {/* Date Selection */}
            <div className="date-section">
              <label>Feedback Date</label>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                max={new Date().toISOString().split('T')[0]}
              />
            </div>

            {/* Recording Section */}
            <div className="recording-section">
              {!audioBlob ? (
                <>
                  <button
                    className={`record-btn ${recording ? 'recording' : ''}`}
                    onClick={recording ? stopRecording : startRecording}
                  >
                    <span className="record-icon">{recording ? '⬛' : '🎤'}</span>
                    <span>{recording ? 'Stop Recording' : 'Start Recording'}</span>
                  </button>
                  
                  {recording && (
                    <div className="recording-indicator">
                      <span className="pulse"></span>
                      Recording...
                    </div>
                  )}

                  <div className="divider">
                    <span>OR</span>
                  </div>

                  <button 
                    className="upload-btn"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    📁 Upload Audio/Video File
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="audio/*,video/*"
                    onChange={handleFileSelect}
                    style={{ display: 'none' }}
                  />
                </>
              ) : (
                <div className="preview-section">
                  <h3>Preview</h3>
                  <audio controls src={audioUrl} />
                  
                  <div className="preview-actions">
                    <button className="clear-btn" onClick={clearRecording}>
                      ❌ Clear
                    </button>
                    <button 
                      className="submit-btn"
                      onClick={uploadFeedback}
                      disabled={uploading}
                    >
                      {uploading ? '⏳ Uploading...' : '✅ Submit Feedback'}
                    </button>
                  </div>
                </div>
              )}

              {uploadStatus && (
                <div className={`status-message ${uploadStatus.success ? 'success' : 'error'}`}>
                  {uploadStatus.message}
                </div>
              )}
            </div>

            {/* Instructions */}
            <div className="instructions">
              <h4>Tips for good feedback</h4>
              <ul>
                <li>Speak clearly about customer interactions</li>
                <li>Mention specific products by name</li>
                <li>Note any issues or complaints</li>
                <li>Share suggestions for improvement</li>
              </ul>
            </div>
          </div>
        ) : (
          <div className="history-view">
            <h2>Your Submissions</h2>
            {feedbacks.length === 0 ? (
              <p className="no-data">No feedback submissions yet</p>
            ) : (
              <div className="feedback-list">
                {feedbacks.map((fb) => (
                  <div key={fb.id} className="feedback-card">
                    <div className="feedback-header">
                      <span className="feedback-date">{fb.recorded_date}</span>
                      <span className={`status-badge ${fb.status}`}>{fb.status}</span>
                    </div>
                    
                    {fb.media_url && (
                      <audio controls src={fb.media_url} className="feedback-audio" />
                    )}
                    
                    {fb.transcription && (
                      <div className="transcription">
                        <strong>Transcription:</strong>
                        <p>{fb.transcription}</p>
                      </div>
                    )}
                    
                    {fb.analysis && (
                      <div className="analysis">
                        <div className={`tone-badge ${fb.analysis.tone}`}>
                          {fb.analysis.tone}
                        </div>
                        {fb.analysis.summary && (
                          <p className="summary">{fb.analysis.summary}</p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            <button className="refresh-btn" onClick={fetchHistory}>
              🔄 Refresh
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
