import os
import json
import base64

def generate_widget(db87_path, db86_path, out_html_path):
    db87 = json.load(open(db87_path)) if os.path.exists(db87_path) else []
    db86 = json.load(open(db86_path)) if os.path.exists(db86_path) else []
    
    # Calculate stats for db87
    stats87 = {'voice_nguoi_that': 0, 'voice_ai': 0, 'khong_am_thanh': 0, 'co_am_thanh_sfx': 0, 'chi_co_nhac': 0, 'hon_hop': 0}
    for c in db87:
        at = c.get('audio_context', {}).get('audio_type', 'co_am_thanh_sfx')
        stats87[at] = stats87.get(at, 0) + 1
        
    # Helper to prepare clips data for JS
    def serialize_clips(db):
        serialized = []
        for c in db:
            thumb = c.get('thumb_path', '')
            thumb_b64 = ""
            if thumb and os.path.exists(thumb):
                try:
                    with open(thumb, 'rb') as f:
                        thumb_b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode('utf-8')
                except Exception:
                    pass
            ac = c.get('audio_context', {})
            serialized.append({
                'id': c.get('order_id', c.get('scene_id', 0)),
                'name': c.get('file_name', ''),
                'dur': round(c.get('duration', 0), 2),
                'shots': c.get('shots_count', c.get('shots_merged', 1)),
                'promoted': c.get('is_promoted', False),
                'thumb': thumb_b64,
                'audio_type': ac.get('audio_type', 'unknown'),
                'sound_class': ac.get('sound_class', 'unknown'),
                'impact_t': ac.get('peak_impact_time_sec', 0.0),
                'impact_f': ac.get('peak_impact_frame_relative', 0),
                'peak_db': ac.get('loudness_peak_db', 0.0),
                'dyn_range': ac.get('dynamic_range', 1.0),
                'speech': ac.get('speech_text', '')
            })
        return serialized

    clips87_js = json.dumps(serialize_clips(db87))
    clips86_js = json.dumps(serialize_clips(db86))

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Preview Widget — Ngữ Cảnh Âm Thanh & Bóc Tách 6 Nhóm (Split Scenes)</title>
<style>
  :root {{
    --bg-dark: #0b0f17;
    --card-bg: #151c28;
    --border: #232e42;
    --accent: #38bdf8;
    --text-main: #f1f5f9;
    --text-muted: #94a3b8;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg-dark);
    color: var(--text-main);
    margin: 0;
    padding: 24px;
  }}
  .header {{
    background: linear-gradient(135deg, #182234 0%, #0f172a 100%);
    padding: 24px;
    border-radius: 14px;
    margin-bottom: 24px;
    border: 1px solid var(--border);
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }}
  .title {{
    font-size: 26px;
    font-weight: 800;
    color: #fbbf24;
    margin: 0 0 6px 0;
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .subtitle {{
    color: var(--text-muted);
    font-size: 14px;
    line-height: 1.5;
  }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 12px;
    margin-top: 20px;
  }}
  .stat-card {{
    background: rgba(30, 41, 59, 0.7);
    padding: 12px 16px;
    border-radius: 10px;
    border-left: 4px solid var(--accent);
  }}
  .stat-val {{
    font-size: 20px;
    font-weight: 700;
  }}
  .stat-lbl {{
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
  }}
  .controls-bar {{
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 14px;
    margin-bottom: 20px;
  }}
  .tab-group {{
    display: flex;
    gap: 8px;
  }}
  .tab-btn {{
    padding: 9px 18px;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    color: var(--text-muted);
    cursor: pointer;
    font-weight: 600;
    font-size: 13px;
    transition: all 0.2s;
  }}
  .tab-btn.active {{
    background: #0284c7;
    color: #fff;
    border-color: #38bdf8;
  }}
  .filter-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 20px;
    background: #111827;
    padding: 12px;
    border-radius: 10px;
    border: 1px solid #1f2937;
  }}
  .filter-chip {{
    padding: 6px 14px;
    background: #1f2937;
    border: 1px solid #374151;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    color: #cbd5e1;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .filter-chip:hover {{
    background: #374151;
  }}
  .filter-chip.active {{
    background: #38bdf8;
    color: #0f172a;
    border-color: #38bdf8;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
  }}
  .search-box {{
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid #334155;
    background: #1e293b;
    color: #f1f5f9;
    font-size: 13px;
    min-width: 240px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
    gap: 16px;
  }}
  .card {{
    background: var(--card-bg);
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border);
    transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
    display: flex;
    flex-direction: column;
  }}
  .card:hover {{
    transform: translateY(-4px);
    border-color: var(--accent);
    box-shadow: 0 8px 20px rgba(0,0,0,0.5);
  }}
  .thumb-wrap {{
    position: relative;
    width: 100%;
    height: 162px;
    background: #07090e;
  }}
  .thumb-wrap img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}
  .badge-dur {{
    position: absolute;
    bottom: 8px;
    right: 8px;
    background: rgba(0,0,0,0.85);
    color: #fbbf24;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 7px;
    border-radius: 5px;
    font-family: monospace;
  }}
  .badge-type {{
    position: absolute;
    top: 8px;
    left: 8px;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 5px;
    letter-spacing: 0.3px;
    display: flex;
    align-items: center;
    gap: 4px;
  }}
  .type-voice_nguoi_that {{ background: #059669; color: #fff; }}
  .type-voice_ai {{ background: #7c3aed; color: #fff; }}
  .type-khong_am_thanh {{ background: #475569; color: #cbd5e1; }}
  .type-co_am_thanh_sfx {{ background: #d97706; color: #fff; }}
  .type-chi_co_nhac {{ background: #2563eb; color: #fff; }}
  .type-hon_hop {{ background: #e11d48; color: #fff; }}

  .badge-impact {{
    position: absolute;
    bottom: 8px;
    left: 8px;
    background: rgba(220, 38, 38, 0.9);
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    padding: 3px 6px;
    border-radius: 4px;
  }}
  .card-body {{
    padding: 14px;
    display: flex;
    flex-direction: column;
    flex-grow: 1;
  }}
  .filename {{
    font-size: 14px;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 6px;
  }}
  .sound-desc {{
    font-size: 12px;
    color: #38bdf8;
    font-weight: 600;
    margin-bottom: 8px;
  }}
  .speech-box {{
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 8px;
    font-size: 12px;
    color: #e2e8f0;
    font-style: italic;
    margin-bottom: 8px;
    max-height: 52px;
    overflow-y: auto;
  }}
  .meta-row {{
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--text-muted);
    margin-top: auto;
    padding-top: 8px;
    border-top: 1px solid #1e293b;
  }}
</style>
</head>
<body>

<div class="header">
  <div class="title">🎧 Audio Context Intelligence — Bóc Tách 6 Nhóm & Zero-Cut Snapping</div>
  <div class="subtitle">
    Hệ thống phân tích sóng âm đa chiều: Nhận diện giọng nói thật/AI qua độ biến thiên cao độ $F_0$, bóc tách tiếng va chạm SFX, nhạc BGM và áp dụng Audio Zero-Cut Snapping để chuyển cảnh hoàn hảo không gây click/pop.
  </div>
  <div class="stats-grid">
    <div class="stat-card" style="border-color: #059669;">
      <div class="stat-val" style="color: #34d399;">{stats87['voice_nguoi_that']} clips</div>
      <div class="stat-lbl">🗣️ Voice Người Thật</div>
    </div>
    <div class="stat-card" style="border-color: #7c3aed;">
      <div class="stat-val" style="color: #a78bfa;">{stats87['voice_ai']} clips</div>
      <div class="stat-lbl">🤖 Voice AI / TTS</div>
    </div>
    <div class="stat-card" style="border-color: #64748b;">
      <div class="stat-val" style="color: #94a3b8;">{stats87['khong_am_thanh']} clip</div>
      <div class="stat-lbl">🔇 Mute / Không Âm Thanh</div>
    </div>
    <div class="stat-card" style="border-color: #d97706;">
      <div class="stat-val" style="color: #fbbf24;">{stats87['co_am_thanh_sfx']} clips</div>
      <div class="stat-lbl">💥 Có Âm Thanh SFX</div>
    </div>
    <div class="stat-card" style="border-color: #2563eb;">
      <div class="stat-val" style="color: #60a5fa;">{stats87['chi_co_nhac']} clips</div>
      <div class="stat-lbl">🎵 Chỉ Có Nhạc (BGM)</div>
    </div>
    <div class="stat-card" style="border-color: #e11d48;">
      <div class="stat-val" style="color: #f43f5e;">{stats87['hon_hop']} clips</div>
      <div class="stat-lbl">🎛️ Hỗn Hợp (Mixed)</div>
    </div>
  </div>
</div>

<div class="controls-bar">
  <div class="tab-group">
    <button id="tab87" class="tab-btn active" onclick="switchVideo('87')">Video #87 (355 Clips)</button>
    <button id="tab86" class="tab-btn" onclick="switchVideo('86')">Video #86 ({len(db86)} Clips)</button>
  </div>
  <input type="text" id="searchInput" class="search-box" placeholder="🔍 Tìm theo tên hoặc lời thoại..." oninput="applyFilters()">
</div>

<div class="filter-bar">
  <div class="filter-chip active" data-type="all" onclick="setFilter('all')">Tất cả ({len(db87)})</div>
  <div class="filter-chip" data-type="voice_nguoi_that" onclick="setFilter('voice_nguoi_that')">🗣️ Voice Người Thật ({stats87['voice_nguoi_that']})</div>
  <div class="filter-chip" data-type="voice_ai" onclick="setFilter('voice_ai')">🤖 Voice AI ({stats87['voice_ai']})</div>
  <div class="filter-chip" data-type="khong_am_thanh" onclick="setFilter('khong_am_thanh')">🔇 Không Âm Thanh ({stats87['khong_am_thanh']})</div>
  <div class="filter-chip" data-type="co_am_thanh_sfx" onclick="setFilter('co_am_thanh_sfx')">💥 Có Âm Thanh SFX ({stats87['co_am_thanh_sfx']})</div>
  <div class="filter-chip" data-type="chi_co_nhac" onclick="setFilter('chi_co_nhac')">🎵 Chỉ Có Nhạc ({stats87['chi_co_nhac']})</div>
  <div class="filter-chip" data-type="hon_hop" onclick="setFilter('hon_hop')">🎛️ Hỗn Hợp ({stats87['hon_hop']})</div>
</div>

<div id="clipsGrid" class="grid"></div>

<script>
  const data87 = {clips87_js};
  const data86 = {clips86_js};
  let currentVid = '87';
  let currentFilter = 'all';

  const typeLabels = {{
    'voice_nguoi_that': '🗣️ Voice Người Thật',
    'voice_ai': '🤖 Voice AI',
    'khong_am_thanh': '🔇 Mute / Silence',
    'co_am_thanh_sfx': '💥 SFX / Va Chạm',
    'chi_co_nhac': '🎵 Nhạc BGM',
    'hon_hop': '🎛️ Hỗn Hợp'
  }};

  function switchVideo(vid) {{
    currentVid = vid;
    document.getElementById('tab87').classList.toggle('active', vid === '87');
    document.getElementById('tab86').classList.toggle('active', vid === '86');
    applyFilters();
  }}

  function setFilter(type) {{
    currentFilter = type;
    document.querySelectorAll('.filter-chip').forEach(el => {{
      el.classList.toggle('active', el.getAttribute('data-type') === type);
    }});
    applyFilters();
  }}

  function applyFilters() {{
    const data = (currentVid === '87') ? data87 : data86;
    const search = document.getElementById('searchInput').value.toLowerCase();
    const container = document.getElementById('clipsGrid');
    container.innerHTML = '';

    const filtered = data.filter(c => {{
      const matchType = (currentFilter === 'all') || (c.audio_type === currentFilter);
      const matchSearch = (!search) || c.name.toLowerCase().includes(search) || (c.speech && c.speech.toLowerCase().includes(search));
      return matchType && matchSearch;
    }});

    filtered.forEach(c => {{
      const card = document.createElement('div');
      card.className = 'card';
      
      const typeClass = 'type-' + c.audio_type;
      const typeLbl = typeLabels[c.audio_type] || c.audio_type;
      const impactHtml = (c.impact_t > 0) ? `<div class="badge-impact">⚡ Impact: ${{c.impact_t}}s</div>` : '';
      const speechHtml = (c.speech) ? `<div class="speech-box">🗣️ "${{c.speech}}"</div>` : '';

      card.innerHTML = `
        <div class="thumb-wrap">
          ${{c.thumb ? `<img src="${{c.thumb}}" loading="lazy" />` : '<div style=\"display:flex;align-items:center;justify-content:center;height:100%;color:#475569;\">No Preview</div>'}}
          <div class="badge-type ${{typeClass}}">${{typeLbl}}</div>
          <div class="badge-dur">${{c.dur}}s</div>
          ${{impactHtml}}
        </div>
        <div class="card-body">
          <div class="filename">${{c.name}}</div>
          <div class="sound-desc">🏷️ ${{c.sound_class.replace(/_/g, ' ')}}</div>
          ${{speechHtml}}
          <div class="meta-row">
            <span>🔊 Peak: ${{c.peak_db}} dB</span>
            <span>📊 Dyn: ${{c.dyn_range}}x</span>
            <span>🎬 ${{c.shots}} shots</span>
          </div>
        </div>
      `;
      container.appendChild(card);
    }});
  }}

  // Initial render
  applyFilters();
</script>

</body>
</html>"""

    with open(out_html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Generated Interactive Audio Preview Widget at: {out_html_path}")

if __name__ == '__main__':
    generate_widget(
        '/Volumes/External/clips/work_87/scene_db.json',
        '/Volumes/External/clips/work_86/scene_db.json',
        '/Users/mmmnhat/.gemini/antigravity/brain/fcd38b33-087d-4ddf-b3c4-2d58cf8d5071/preview_widget.html'
    )
