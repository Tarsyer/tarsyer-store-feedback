import React, { useState, useEffect, useMemo } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'https://store-feedback.tarsyer.com';

// Simple bar chart component
const BarChart = ({ data, labelKey, valueKey, maxBars = 10, color = '#1a73e8' }) => {
  const maxValue = Math.max(...data.map(d => d[valueKey]), 1);
  
  return (
    <div className="bar-chart">
      {data.slice(0, maxBars).map((item, i) => (
        <div key={i} className="bar-row">
          <span className="bar-label">{item[labelKey]}</span>
          <div className="bar-container">
            <div 
              className="bar-fill" 
              style={{ 
                width: `${(item[valueKey] / maxValue) * 100}%`,
                backgroundColor: color
              }}
            />
          </div>
          <span className="bar-value">{item[valueKey]}</span>
        </div>
      ))}
    </div>
  );
};

// Pie/Donut chart for tone distribution
const ToneChart = ({ data }) => {
  const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
  const colors = {
    positive: '#34a853',
    neutral: '#fbbc04',
    negative: '#ea4335'
  };
  
  let cumulative = 0;
  const segments = Object.entries(data).map(([tone, count]) => {
    const start = cumulative;
    const percent = (count / total) * 100;
    cumulative += percent;
    return { tone, count, percent, start };
  });

  return (
    <div className="tone-chart">
      <div className="donut-container">
        <svg viewBox="0 0 100 100">
          {segments.map(({ tone, percent, start }) => {
            const radius = 40;
            const circumference = 2 * Math.PI * radius;
            const offset = (start / 100) * circumference;
            const length = (percent / 100) * circumference;
            
            return (
              <circle
                key={tone}
                cx="50"
                cy="50"
                r={radius}
                fill="none"
                stroke={colors[tone] || '#ccc'}
                strokeWidth="12"
                strokeDasharray={`${length} ${circumference - length}`}
                strokeDashoffset={-offset + circumference / 4}
              />
            );
          })}
        </svg>
        <div className="donut-center">
          <span className="donut-total">{total}</span>
          <span className="donut-label">Total</span>
        </div>
      </div>
      <div className="tone-legend">
        {segments.map(({ tone, count, percent }) => (
          <div key={tone} className="legend-item">
            <span className="legend-color" style={{ background: colors[tone] }} />
            <span className="legend-label">{tone}</span>
            <span className="legend-value">{count} ({percent.toFixed(0)}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// Daily trend chart
const TrendChart = ({ data }) => {
  if (!data.length) return <div className="no-data">No data available</div>;
  
  const maxCount = Math.max(...data.map(d => d.count), 1);
  const height = 150;
  const width = 100;
  
  return (
    <div className="trend-chart">
      <div className="trend-bars">
        {data.map((day, i) => (
          <div key={i} className="trend-bar-wrapper">
            <div 
              className="trend-bar"
              style={{ height: `${(day.count / maxCount) * 100}%` }}
              title={`${day.date}: ${day.count} feedbacks`}
            >
              <span className="trend-count">{day.count}</span>
            </div>
            <span className="trend-date">{day.date.slice(5)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [stores, setStores] = useState([]);
  const [feedbacks, setFeedbacks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedStore, setSelectedStore] = useState('');
  const [days, setDays] = useState(15);
  const [detailView, setDetailView] = useState(null);

  useEffect(() => {
    fetchData();
  }, [selectedStore, days]);

  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch dashboard stats
      const statsUrl = new URL(`${API_BASE}/api/v1/dashboard/stats`);
      statsUrl.searchParams.set('days', days);
      if (selectedStore) statsUrl.searchParams.set('store_code', selectedStore);
      
      const statsRes = await fetch(statsUrl);
      const statsData = await statsRes.json();
      setStats(statsData);

      // Fetch stores list
      const storesRes = await fetch(`${API_BASE}/api/v1/stores`);
      const storesData = await storesRes.json();
      setStores(storesData);

      // Fetch recent feedbacks
      const feedbacksUrl = new URL(`${API_BASE}/api/v1/feedbacks`);
      feedbacksUrl.searchParams.set('limit', 20);
      if (selectedStore) feedbacksUrl.searchParams.set('store_code', selectedStore);
      
      const feedbacksRes = await fetch(feedbacksUrl);
      const feedbacksData = await feedbacksRes.json();
      setFeedbacks(feedbacksData);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    // Simple CSV export
    const headers = ['Date', 'Store', 'Tone', 'Summary', 'Products', 'Issues', 'Actions'];
    const rows = feedbacks.map(fb => [
      fb.recorded_date,
      fb.store_code,
      fb.analysis?.tone || '',
      fb.analysis?.summary || '',
      (fb.analysis?.products || []).join('; '),
      (fb.analysis?.issues || []).join('; '),
      (fb.analysis?.actions || []).join('; ')
    ]);
    
    const csv = [headers, ...rows].map(row => 
      row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
    ).join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `feedback-export-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  if (loading && !stats) {
    return <div className="loading">Loading dashboard...</div>;
  }

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <h1>Store Feedback Dashboard</h1>
        <div className="header-actions">
          <select 
            value={selectedStore} 
            onChange={e => setSelectedStore(e.target.value)}
          >
            <option value="">All Stores</option>
            {stores.map(s => (
              <option key={s.store_code} value={s.store_code}>
                {s.store_code} ({s.feedback_count})
              </option>
            ))}
          </select>
          <select value={days} onChange={e => setDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option>
            <option value={15}>Last 15 days</option>
            <option value={30}>Last 30 days</option>
            <option value={60}>Last 60 days</option>
          </select>
          <button onClick={handleExport} className="export-btn">
            📥 Export CSV
          </button>
        </div>
      </header>

      {/* Stats Overview */}
      <div className="stats-grid">
        <div className="stat-card total">
          <span className="stat-value">{stats?.total_feedbacks || 0}</span>
          <span className="stat-label">Total Feedbacks</span>
        </div>
        <div className="stat-card stores">
          <span className="stat-value">{stores.length}</span>
          <span className="stat-label">Active Stores</span>
        </div>
        <div className="stat-card positive">
          <span className="stat-value">{stats?.tone_distribution?.positive || 0}</span>
          <span className="stat-label">Positive</span>
        </div>
        <div className="stat-card negative">
          <span className="stat-value">{stats?.tone_distribution?.negative || 0}</span>
          <span className="stat-label">Negative</span>
        </div>
      </div>

      {/* Charts Row */}
      <div className="charts-row">
        {/* Daily Trend */}
        <div className="chart-card wide">
          <h3>📊 Daily Submissions (Last {days} Days)</h3>
          <TrendChart data={stats?.feedbacks_by_day || []} />
        </div>
        
        {/* Tone Distribution */}
        <div className="chart-card">
          <h3>😊 Tone Distribution</h3>
          <ToneChart data={stats?.tone_distribution || {}} />
        </div>
      </div>

      {/* Insights Row */}
      <div className="insights-row">
        {/* Top Products */}
        <div className="insight-card">
          <h3>🏷️ Top 5 Products</h3>
          {stats?.top_products?.length ? (
            <BarChart 
              data={stats.top_products} 
              labelKey="name" 
              valueKey="count"
              maxBars={5}
              color="#4285f4"
            />
          ) : (
            <div className="no-data">No product data yet</div>
          )}
        </div>

        {/* Top Issues */}
        <div className="insight-card">
          <h3>⚠️ Top 5 Issues</h3>
          {stats?.top_issues?.length ? (
            <BarChart 
              data={stats.top_issues} 
              labelKey="name" 
              valueKey="count"
              maxBars={5}
              color="#ea4335"
            />
          ) : (
            <div className="no-data">No issues reported</div>
          )}
        </div>

        {/* Top Actions */}
        <div className="insight-card">
          <h3>✅ Top 5 Actions</h3>
          {stats?.top_actions?.length ? (
            <BarChart 
              data={stats.top_actions} 
              labelKey="name" 
              valueKey="count"
              maxBars={5}
              color="#34a853"
            />
          ) : (
            <div className="no-data">No actions identified</div>
          )}
        </div>
      </div>

      {/* Store-wise Breakdown */}
      <div className="store-breakdown">
        <h3>🏪 Feedbacks by Store</h3>
        <BarChart 
          data={stats?.feedbacks_by_store || []} 
          labelKey="store" 
          valueKey="count"
          maxBars={15}
          color="#1a73e8"
        />
      </div>

      {/* Recent Feedbacks Table */}
      <div className="feedbacks-table-container">
        <h3>📝 Recent Feedbacks</h3>
        <table className="feedbacks-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Store</th>
              <th>Status</th>
              <th>Tone</th>
              <th>Summary</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {feedbacks.map(fb => (
              <tr key={fb.id}>
                <td>{fb.recorded_date}</td>
                <td><strong>{fb.store_code}</strong></td>
                <td>
                  <span className={`status-pill ${fb.status}`}>{fb.status}</span>
                </td>
                <td>
                  {fb.analysis?.tone && (
                    <span className={`tone-pill ${fb.analysis.tone}`}>
                      {fb.analysis.tone}
                    </span>
                  )}
                </td>
                <td className="summary-cell">
                  {fb.analysis?.summary?.slice(0, 100)}
                  {fb.analysis?.summary?.length > 100 && '...'}
                </td>
                <td>
                  <button 
                    className="view-btn"
                    onClick={() => setDetailView(fb)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Detail Modal */}
      {detailView && (
        <div className="modal-overlay" onClick={() => setDetailView(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setDetailView(null)}>×</button>
            
            <h2>Feedback Details</h2>
            
            <div className="detail-header">
              <span className="detail-store">{detailView.store_code}</span>
              <span className="detail-date">{detailView.recorded_date}</span>
              <span className={`status-pill ${detailView.status}`}>{detailView.status}</span>
            </div>

            {detailView.media_url && (
              <div className="detail-section">
                <h4>🎵 Audio Recording</h4>
                <audio controls src={detailView.media_url} style={{ width: '100%' }} />
              </div>
            )}

            {detailView.transcription && (
              <div className="detail-section">
                <h4>📄 Transcription</h4>
                <p className="transcription-text">{detailView.transcription}</p>
              </div>
            )}

            {detailView.analysis && (
              <>
                <div className="detail-section">
                  <h4>📊 Analysis</h4>
                  <div className="analysis-grid">
                    <div>
                      <strong>Tone:</strong>
                      <span className={`tone-pill ${detailView.analysis.tone}`}>
                        {detailView.analysis.tone} ({(detailView.analysis.tone_score * 100).toFixed(0)}%)
                      </span>
                    </div>
                  </div>
                  <p><strong>Summary:</strong> {detailView.analysis.summary}</p>
                </div>

                {detailView.analysis.products?.length > 0 && (
                  <div className="detail-section">
                    <h4>🏷️ Products Mentioned</h4>
                    <div className="tag-list">
                      {detailView.analysis.products.map((p, i) => (
                        <span key={i} className="tag product">{p}</span>
                      ))}
                    </div>
                  </div>
                )}

                {detailView.analysis.issues?.length > 0 && (
                  <div className="detail-section">
                    <h4>⚠️ Issues</h4>
                    <div className="tag-list">
                      {detailView.analysis.issues.map((p, i) => (
                        <span key={i} className="tag issue">{p}</span>
                      ))}
                    </div>
                  </div>
                )}

                {detailView.analysis.actions?.length > 0 && (
                  <div className="detail-section">
                    <h4>✅ Suggested Actions</h4>
                    <div className="tag-list">
                      {detailView.analysis.actions.map((p, i) => (
                        <span key={i} className="tag action">{p}</span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
