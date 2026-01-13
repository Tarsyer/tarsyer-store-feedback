import React, { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, Link } from 'react-router-dom';
import { 
  Mic, Upload, BarChart3, LogOut, Play, Pause, 
  CheckCircle, Clock, AlertCircle, ChevronRight,
  Calendar, Store, TrendingUp, TrendingDown, Minus
} from 'lucide-react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line
} from 'recharts';

// ============ API Configuration ============

const API_BASE = import.meta.env.VITE_API_URL || 'https://store-feedback.tarsyer.com';

// ============ Types ============

interface User {
  username: string;
  name: string;
  role: 'staff' | 'manager' | 'admin';
  store_ids: string[];
}

interface Feedback {
  id: string;
  store_code: string;
  store_name?: string;
  recorded_date: string;
  recorded_time: string;
  media_url?: string;
  transcription?: string;
  analysis?: {
    summary: string;
    tone: 'positive' | 'negative' | 'neutral';
    tone_score: number;
    products: string[];
    issues: string[];
    actions: string[];
  };
  status: string;
  created_at: string;
}

interface DashboardStats {
  total_feedbacks: number;
  feedbacks_by_day: { date: string; count: number }[];
  feedbacks_by_store: { store: string; count: number }[];
  tone_distribution: { positive?: number; negative?: number; neutral?: number };
  top_products: { name: string; count: number }[];
  top_issues: { name: string; count: number }[];
  top_actions: { name: string; count: number }[];
}

// ============ Auth Context ============

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

// ============ API Helpers ============

const api = {
  async fetch(endpoint: string, options: RequestInit = {}) {
    const token = localStorage.getItem('token');
    const headers: HeadersInit = {
      ...options.headers,
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }
    
    const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    
    if (res.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
    
    return res;
  },
  
  async get(endpoint: string) {
    const res = await this.fetch(endpoint);
    return res.json();
  },
  
  async post(endpoint: string, data: any) {
    const res = await this.fetch(endpoint, {
      method: 'POST',
      body: data instanceof FormData ? data : JSON.stringify(data),
    });
    return res.json();
  }
};

// ============ Components ============

// Login Page
const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      await login(username, password);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Store className="w-8 h-8 text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-800">Store Feedback</h1>
          <p className="text-gray-500 mt-1">Sign in to continue</p>
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter username"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter password"
              required
            />
          </div>
          
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
};

// Recording Page (Staff)
const RecordingPage: React.FC = () => {
  const { user, logout } = useAuth();
  const [storeCode, setStoreCode] = useState(user?.store_ids[0] || '');
  const [recordedDate, setRecordedDate] = useState(new Date().toISOString().split('T')[0]);
  const [file, setFile] = useState<File | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [audioChunks, setAudioChunks] = useState<Blob[]>([]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [recentUploads, setRecentUploads] = useState<Feedback[]>([]);

  useEffect(() => {
    loadRecentUploads();
  }, []);

  const loadRecentUploads = async () => {
    try {
      const data = await api.get('/api/v1/feedbacks?limit=5');
      setRecentUploads(data);
    } catch (e) {
      console.error('Failed to load recent uploads');
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        const file = new File([blob], `recording_${Date.now()}.webm`, { type: 'audio/webm' });
        setFile(file);
        stream.getTracks().forEach(t => t.stop());
      };
      
      recorder.start();
      setMediaRecorder(recorder);
      setAudioChunks(chunks);
      setIsRecording(true);
    } catch (err) {
      setMessage({ type: 'error', text: 'Could not access microphone' });
    }
  };

  const stopRecording = () => {
    if (mediaRecorder) {
      mediaRecorder.stop();
      setIsRecording(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !storeCode) return;
    
    setUploading(true);
    setMessage(null);
    
    try {
      const formData = new FormData();
      formData.append('media', file);
      formData.append('store_code', storeCode.toUpperCase());
      formData.append('recorded_date', recordedDate);
      
      await api.post('/api/v1/feedback', formData);
      
      setMessage({ type: 'success', text: 'Feedback uploaded successfully!' });
      setFile(null);
      loadRecentUploads();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Upload failed' });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-800">Record Feedback</h1>
            <p className="text-sm text-gray-500">Hi, {user?.name}</p>
          </div>
          <div className="flex items-center gap-2">
            {user?.role !== 'staff' && (
              <Link to="/dashboard" className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg">
                <BarChart3 className="w-5 h-5" />
              </Link>
            )}
            <button onClick={logout} className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg">
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="max-w-lg mx-auto p-4 space-y-6">
        {/* Upload Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm p-6 space-y-4">
          {message && (
            <div className={`px-4 py-3 rounded-lg text-sm ${
              message.type === 'success' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'
            }`}>
              {message.text}
            </div>
          )}
          
          {/* Store Code */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Store Code</label>
            <input
              type="text"
              value={storeCode}
              onChange={(e) => setStoreCode(e.target.value.toUpperCase())}
              pattern="W\d{3}"
              placeholder="W001"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          
          {/* Date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Date</label>
            <input
              type="date"
              value={recordedDate}
              onChange={(e) => setRecordedDate(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          
          {/* Recording */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Recording</label>
            
            {/* Record Button */}
            <div className="flex justify-center mb-4">
              <button
                type="button"
                onClick={isRecording ? stopRecording : startRecording}
                className={`w-24 h-24 rounded-full flex items-center justify-center transition-all ${
                  isRecording 
                    ? 'bg-red-500 hover:bg-red-600 animate-pulse' 
                    : 'bg-blue-500 hover:bg-blue-600'
                }`}
              >
                {isRecording ? (
                  <Pause className="w-10 h-10 text-white" />
                ) : (
                  <Mic className="w-10 h-10 text-white" />
                )}
              </button>
            </div>
            <p className="text-center text-sm text-gray-500 mb-4">
              {isRecording ? 'Recording... Tap to stop' : 'Tap to record'}
            </p>
            
            {/* Or Upload */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">or upload file</span>
              </div>
            </div>
            
            <input
              type="file"
              accept="audio/*,video/*"
              onChange={handleFileChange}
              className="mt-4 w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-600 hover:file:bg-blue-100"
            />
          </div>
          
          {/* Selected File */}
          {file && (
            <div className="bg-blue-50 px-4 py-3 rounded-lg flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-blue-600" />
              <span className="text-sm text-blue-800 truncate">{file.name}</span>
            </div>
          )}
          
          {/* Submit */}
          <button
            type="submit"
            disabled={!file || uploading}
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {uploading ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="w-5 h-5" />
                Upload Feedback
              </>
            )}
          </button>
        </form>
        
        {/* Recent Uploads */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Recent Uploads</h2>
          <div className="space-y-3">
            {recentUploads.map((fb) => (
              <div key={fb.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  fb.status === 'completed' ? 'bg-green-100' :
                  fb.status === 'error' ? 'bg-red-100' : 'bg-yellow-100'
                }`}>
                  {fb.status === 'completed' ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : fb.status === 'error' ? (
                    <AlertCircle className="w-5 h-5 text-red-600" />
                  ) : (
                    <Clock className="w-5 h-5 text-yellow-600" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-800">{fb.store_code}</p>
                  <p className="text-sm text-gray-500 truncate">{fb.recorded_date}</p>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400" />
              </div>
            ))}
            {recentUploads.length === 0 && (
              <p className="text-center text-gray-500 py-4">No uploads yet</p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

// Dashboard Page (Manager)
const DashboardPage: React.FC = () => {
  const { user, logout } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(15);
  const [selectedFeedback, setSelectedFeedback] = useState<Feedback | null>(null);
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([]);

  useEffect(() => {
    loadData();
  }, [days]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsData, feedbacksData] = await Promise.all([
        api.get(`/api/v1/dashboard/stats?days=${days}`),
        api.get('/api/v1/feedbacks?limit=20')
      ]);
      setStats(statsData);
      setFeedbacks(feedbacksData);
    } catch (e) {
      console.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const TONE_COLORS = {
    positive: '#22c55e',
    negative: '#ef4444',
    neutral: '#94a3b8'
  };

  const getToneIcon = (tone: string) => {
    switch (tone) {
      case 'positive': return <TrendingUp className="w-4 h-4 text-green-500" />;
      case 'negative': return <TrendingDown className="w-4 h-4 text-red-500" />;
      default: return <Minus className="w-4 h-4 text-gray-400" />;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const toneData = stats ? [
    { name: 'Positive', value: stats.tone_distribution.positive || 0, color: TONE_COLORS.positive },
    { name: 'Negative', value: stats.tone_distribution.negative || 0, color: TONE_COLORS.negative },
    { name: 'Neutral', value: stats.tone_distribution.neutral || 0, color: TONE_COLORS.neutral },
  ] : [];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-800">Manager Dashboard</h1>
            <p className="text-sm text-gray-500">Store Feedback Analytics</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value={7}>Last 7 days</option>
              <option value={15}>Last 15 days</option>
              <option value={30}>Last 30 days</option>
            </select>
            <Link to="/" className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg">
              <Mic className="w-5 h-5" />
            </Link>
            <button onClick={logout} className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg">
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-4 space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl shadow-sm p-5">
            <p className="text-sm text-gray-500">Total Feedbacks</p>
            <p className="text-3xl font-bold text-gray-800 mt-1">{stats?.total_feedbacks || 0}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-5">
            <p className="text-sm text-gray-500">Active Stores</p>
            <p className="text-3xl font-bold text-gray-800 mt-1">{stats?.feedbacks_by_store.length || 0}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-5">
            <p className="text-sm text-gray-500">Positive</p>
            <p className="text-3xl font-bold text-green-600 mt-1">{stats?.tone_distribution.positive || 0}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-5">
            <p className="text-sm text-gray-500">Negative</p>
            <p className="text-3xl font-bold text-red-600 mt-1">{stats?.tone_distribution.negative || 0}</p>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Daily Trend */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-semibold text-gray-800 mb-4">Daily Feedback Count</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats?.feedbacks_by_day || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Tone Distribution */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-semibold text-gray-800 mb-4">Tone Distribution</h3>
            <div className="h-64 flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={toneData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {toneData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Top 5s */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Top Products */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-semibold text-gray-800 mb-4">Top 5 Products</h3>
            <div className="space-y-3">
              {stats?.top_products.map((item, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-medium">
                      {i + 1}
                    </span>
                    <span className="text-gray-700">{item.name}</span>
                  </div>
                  <span className="font-semibold text-gray-800">{item.count}</span>
                </div>
              ))}
              {(!stats?.top_products || stats.top_products.length === 0) && (
                <p className="text-gray-500 text-center py-4">No data yet</p>
              )}
            </div>
          </div>

          {/* Top Issues */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-semibold text-gray-800 mb-4">Top 5 Issues</h3>
            <div className="space-y-3">
              {stats?.top_issues.map((item, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 bg-red-100 text-red-600 rounded-full flex items-center justify-center text-sm font-medium">
                      {i + 1}
                    </span>
                    <span className="text-gray-700">{item.name}</span>
                  </div>
                  <span className="font-semibold text-gray-800">{item.count}</span>
                </div>
              ))}
              {(!stats?.top_issues || stats.top_issues.length === 0) && (
                <p className="text-gray-500 text-center py-4">No data yet</p>
              )}
            </div>
          </div>

          {/* Top Actions */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="font-semibold text-gray-800 mb-4">Top 5 Actions</h3>
            <div className="space-y-3">
              {stats?.top_actions.map((item, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-sm font-medium">
                      {i + 1}
                    </span>
                    <span className="text-gray-700">{item.name}</span>
                  </div>
                  <span className="font-semibold text-gray-800">{item.count}</span>
                </div>
              ))}
              {(!stats?.top_actions || stats.top_actions.length === 0) && (
                <p className="text-gray-500 text-center py-4">No data yet</p>
              )}
            </div>
          </div>
        </div>

        {/* Store Breakdown */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="font-semibold text-gray-800 mb-4">Feedback by Store</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats?.feedbacks_by_store.slice(0, 10) || []} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis dataKey="store" type="category" tick={{ fontSize: 12 }} width={80} />
                <Tooltip />
                <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Feedbacks Table */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="p-6 border-b border-gray-100">
            <h3 className="font-semibold text-gray-800">Recent Feedbacks</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Store</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tone</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Summary</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Audio</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {feedbacks.map((fb) => (
                  <tr key={fb.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setSelectedFeedback(fb)}>
                    <td className="px-6 py-4 font-medium text-gray-800">{fb.store_code}</td>
                    <td className="px-6 py-4 text-gray-600">{fb.recorded_date}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1">
                        {fb.analysis?.tone && getToneIcon(fb.analysis.tone)}
                        <span className="capitalize">{fb.analysis?.tone || '-'}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-gray-600 max-w-xs truncate">
                      {fb.analysis?.summary || '-'}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                        fb.status === 'completed' ? 'bg-green-100 text-green-700' :
                        fb.status === 'error' ? 'bg-red-100 text-red-700' :
                        'bg-yellow-100 text-yellow-700'
                      }`}>
                        {fb.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {fb.media_url && (
                        <button
                          onClick={(e) => { e.stopPropagation(); }}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          <Play className="w-5 h-5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Feedback Detail Modal */}
        {selectedFeedback && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6 border-b border-gray-100 flex items-center justify-between">
                <h3 className="font-semibold text-lg text-gray-800">
                  Feedback Detail - {selectedFeedback.store_code}
                </h3>
                <button
                  onClick={() => setSelectedFeedback(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ×
                </button>
              </div>
              <div className="p-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">Date</p>
                    <p className="font-medium">{selectedFeedback.recorded_date}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Time</p>
                    <p className="font-medium">{selectedFeedback.recorded_time}</p>
                  </div>
                </div>
                
                {selectedFeedback.media_url && (
                  <div>
                    <p className="text-sm text-gray-500 mb-2">Audio</p>
                    <audio controls className="w-full">
                      <source src={selectedFeedback.media_url} />
                    </audio>
                  </div>
                )}
                
                {selectedFeedback.transcription && (
                  <div>
                    <p className="text-sm text-gray-500 mb-2">Transcription</p>
                    <div className="bg-gray-50 rounded-lg p-4 text-gray-700 max-h-48 overflow-y-auto">
                      {selectedFeedback.transcription}
                    </div>
                  </div>
                )}
                
                {selectedFeedback.analysis && (
                  <>
                    <div>
                      <p className="text-sm text-gray-500 mb-2">Summary</p>
                      <p className="text-gray-700">{selectedFeedback.analysis.summary}</p>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <p className="text-sm text-gray-500 mb-2">Products</p>
                        <div className="flex flex-wrap gap-1">
                          {selectedFeedback.analysis.products.map((p, i) => (
                            <span key={i} className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">
                              {p}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500 mb-2">Issues</p>
                        <div className="flex flex-wrap gap-1">
                          {selectedFeedback.analysis.issues.map((p, i) => (
                            <span key={i} className="px-2 py-1 bg-red-100 text-red-700 text-xs rounded-full">
                              {p}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500 mb-2">Actions</p>
                        <div className="flex flex-wrap gap-1">
                          {selectedFeedback.analysis.actions.map((p, i) => (
                            <span key={i} className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">
                              {p}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

// ============ App Component ============

const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      if (token) {
        try {
          // For demo, we'll just decode the token or set a mock user
          // In production, call /api/v1/auth/me to get user info
          setUser({
            username: 'demo',
            name: 'Demo User',
            role: 'manager',
            store_ids: ['W001', 'W002']
          });
        } catch (e) {
          localStorage.removeItem('token');
          setToken(null);
        }
      }
      setLoading(false);
    };
    initAuth();
  }, [token]);

  const login = async (username: string, password: string) => {
    // For demo, accept any credentials
    // In production, call /api/v1/auth/login
    const demoToken = 'demo-token-' + Date.now();
    localStorage.setItem('token', demoToken);
    setToken(demoToken);
    setUser({
      username,
      name: username.charAt(0).toUpperCase() + username.slice(1),
      role: username.includes('manager') ? 'manager' : 'staff',
      store_ids: ['W001', 'W002']
    });
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={user ? <Navigate to="/" /> : <LoginPage />} />
          <Route path="/" element={user ? <RecordingPage /> : <Navigate to="/login" />} />
          <Route path="/dashboard" element={
            user?.role !== 'staff' ? <DashboardPage /> : <Navigate to="/" />
          } />
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  );
};

export default App;
