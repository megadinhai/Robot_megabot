import React, { useState } from 'react';
import { 
  ArrowLeft, Home, Map, BookOpen, PenTool, 
  BarChart2, Flame, Layers, Clock, Star, 
  RotateCw, PowerOff, Sparkles, User, ChevronDown
} from 'lucide-react';

export default function EnglishTutorDashboard({ onBack }) {
  const [activeNav, setActiveNav] = useState('today');
  const [selectedDevice, setSelectedDevice] = useState('330730');

  const navItems = [
    { id: 'today', label: 'Hôm nay', icon: Home },
    { id: 'roadmap', label: 'Lộ trình', icon: Map },
    { id: 'curriculum', label: 'Giáo trình', icon: BookOpen },
    { id: 'create', label: 'Tự tạo bài', icon: PenTool },
    { id: 'report', label: 'Báo cáo', icon: BarChart2 },
  ];

  const stats = [
    { label: 'Chuỗi học', value: '0 ngày', icon: '🔥', color: 'text-amber-500' },
    { label: 'Tổng buổi học', value: '0', icon: '📚', color: 'text-emerald-500' },
    { label: 'Thời gian học', value: '0 phút', icon: '⏱️', color: 'text-blue-500' },
    { label: 'Điểm trung bình', value: '0/100', icon: '⭐', color: 'text-yellow-400' },
  ];

  return (
    <div className="min-h-screen bg-[#071326] text-white font-['Segoe_UI',sans-serif] flex flex-col">
      
      {/* ================= 1. HEADER ================= */}
      <header className="h-16 bg-[#0b1b36] border-b border-blue-900/30 px-6 flex items-center justify-between sticky top-0 z-40 backdrop-blur">
        <div className="flex items-center gap-3">
          <button 
            onClick={onBack}
            className="w-9 h-9 rounded-lg bg-[#13294b] hover:bg-[#1a3866] flex items-center justify-center text-gray-300 hover:text-white transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className="font-bold text-base tracking-wide text-white">GMBOT English</div>
            <div className="text-xs text-gray-400">Gia sư tiếng Anh cá nhân hóa</div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-gray-300">
            <span>Thiết bị</span>
            <div className="relative">
              <select 
                value={selectedDevice}
                onChange={(e) => setSelectedDevice(e.target.value)}
                className="appearance-none bg-[#13294b] text-white text-xs font-semibold pl-3 pr-7 py-1.5 rounded-lg border border-blue-800/40 outline-none cursor-pointer"
              >
                <option value="330730">330730</option>
              </select>
              <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
            </div>
          </div>

          <div className="flex items-center gap-2 bg-[#13294b] px-3 py-1.5 rounded-lg border border-blue-800/40 text-xs">
            <span className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center">
              <User size={13} />
            </span>
            <span className="font-semibold text-white">330730</span>
          </div>
        </div>
      </header>

      {/* ================= 2. MAIN LAYOUT ================= */}
      <div className="flex-1 flex">
        
        {/* SIDEBAR NAVIGATION */}
        <aside className="w-56 bg-[#09172f] border-r border-blue-900/20 p-4 flex flex-col justify-between">
          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeNav === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveNav(item.id)}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-semibold transition-all
                    ${isActive 
                      ? 'bg-[#183664] text-white shadow-md shadow-blue-900/20 border border-blue-600/30' 
                      : 'text-gray-400 hover:text-white hover:bg-[#102544]'}`}
                >
                  <Icon size={17} className={isActive ? 'text-blue-400' : 'text-gray-400'} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          <button 
            onClick={onBack}
            className="flex items-center gap-2 text-xs text-gray-400 hover:text-white px-3 py-2 rounded-lg hover:bg-[#102544] transition-colors"
          >
            <ArrowLeft size={14} />
            <span>Về GMBOT</span>
          </button>
        </aside>

        {/* CONTENT AREA */}
        <main className="flex-1 p-6 md:p-8 max-w-7xl mx-auto space-y-6">
          
          {/* HERO BANNER GRADIENT */}
          <section className="relative overflow-hidden rounded-3xl p-8 bg-gradient-to-br from-[#4338ca] via-[#3730a3] to-[#1e1b4b] border border-indigo-400/20 shadow-2xl flex flex-col md:flex-row items-center justify-between gap-8">
            <div className="space-y-3.5 max-w-2xl z-10">
              <div className="text-[11px] font-black uppercase tracking-widest text-indigo-200">
                BÀI HỌC HÔM NAY
              </div>
              <h1 className="text-3xl md:text-4xl font-extrabold text-white tracking-tight">
                Xin chào 330730 👋
              </h1>
              <p className="text-sm md:text-base text-indigo-100/90 leading-relaxed">
                Trình độ hiện tại: <strong className="text-white">STARTER</strong>. Hãy dành một buổi học ngắn để duy trì thói quen mỗi ngày. Sau khi học xong hãy nói "học xong rồi" để hệ thống đánh giá và lưu lại báo cáo học tập.
              </p>
              
              <div className="pt-2 flex flex-wrap items-center gap-3">
                <button className="bg-white hover:bg-slate-100 active:scale-95 text-slate-900 text-sm font-bold px-5 py-2.5 rounded-xl shadow-lg transition-all flex items-center gap-2">
                  <span>▶</span> Bắt đầu bài đề xuất
                </button>
                <button className="bg-white/10 hover:bg-white/15 text-indigo-200 text-sm font-semibold px-4 py-2.5 rounded-xl border border-white/10 transition-colors flex items-center gap-1.5">
                  <span>✔</span> Chưa có nội dung cần ôn
                </button>
              </div>
            </div>

            {/* Mascot Visual */}
            <div className="flex flex-col items-center gap-3 shrink-0">
              <div className="w-36 h-36 rounded-full bg-white/10 border border-white/20 flex items-center justify-center shadow-inner relative">
                {/* Robot Illustration */}
                <div className="text-7xl select-none">🤖</div>
              </div>
              <div className="bg-white text-indigo-950 font-bold text-xs px-3.5 py-1.5 rounded-full shadow-lg">
                Ready to learn something new?
              </div>
            </div>
          </section>

          {/* 4 STATS CARDS */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {stats.map((s, i) => (
              <div key={i} className="bg-[#0f2446] border border-blue-900/30 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                <div className="text-2xl mb-1">{s.icon}</div>
                <div>
                  <div className="text-xs text-gray-400">{s.label}</div>
                  <div className="text-2xl font-black text-white mt-0.5 tracking-tight">{s.value}</div>
                </div>
              </div>
            ))}
          </div>

          {/* 2 MAIN CARDS: ĐỀ XUẤT & BÀI ĐANG ÁP DỤNG */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Card 1: Đề xuất cho bạn */}
            <div className="bg-[#0f2446] border border-blue-900/30 rounded-2xl p-6 shadow-lg flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-blue-400">ĐỀ XUẤT CHO BẠN</span>
                  <span className="bg-blue-900/50 text-blue-300 border border-blue-700/50 text-[10px] font-black px-2 py-0.5 rounded-full">
                    STARTER
                  </span>
                </div>
                <h3 className="text-xl font-bold text-white mb-1.5">Greeting - Bài 1: Hello</h3>
                <p className="text-xs text-gray-400 mb-4">Bài phù hợp trình độ STARTER hiện tại.</p>

                {/* Pills */}
                <div className="flex flex-wrap gap-2 mb-6">
                  <span className="bg-[#09172f] text-gray-300 text-xs px-2.5 py-1 rounded-lg border border-blue-900/30">🎯 Greeting</span>
                  <span className="bg-[#09172f] text-blue-400 text-xs px-2.5 py-1 rounded-lg border border-blue-900/30">📘 Bài học mới</span>
                  <span className="bg-[#09172f] text-sky-400 text-xs px-2.5 py-1 rounded-lg border border-blue-900/30">🔤 3 từ</span>
                  <span className="bg-[#09172f] text-gray-300 text-xs px-2.5 py-1 rounded-lg border border-blue-900/30">💬 3 câu</span>
                  <span className="bg-[#09172f] text-gray-300 text-xs px-2.5 py-1 rounded-lg border border-blue-900/30">⏱️ 10 phút</span>
                </div>
              </div>

              {/* Progress */}
              <div>
                <div className="flex justify-between text-xs text-gray-400 mb-1.5 font-medium">
                  <span>Tiến độ học</span>
                  <span>0%</span>
                </div>
                <div className="h-1.5 w-full bg-[#09172f] rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 w-0"></div>
                </div>
              </div>
            </div>

            {/* Card 2: Bài đang áp dụng */}
            <div className="bg-[#0f2446] border border-blue-900/30 rounded-2xl p-6 shadow-lg flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-blue-400">BÀI ĐANG ÁP DỤNG</span>
                  <span className="bg-gray-800 text-gray-400 text-[10px] font-black px-2 py-0.5 rounded-full">
                    CHƯA BẬT
                  </span>
                </div>
                <h3 className="text-lg font-bold text-white mb-3">Chưa có bài đang học</h3>
                
                <div className="bg-[#071326] border border-blue-900/30 rounded-xl p-4 text-xs text-gray-400 mb-6">
                  Chọn một bài học hoặc tạo bài riêng để bắt đầu.
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button className="bg-[#183664] hover:bg-[#1e427b] text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-colors flex items-center gap-1.5">
                  <RotateCw size={14} /> Tải lại
                </button>
                <button className="bg-red-500/10 text-red-400/60 border border-red-500/20 text-xs font-bold px-4 py-2.5 rounded-xl cursor-not-allowed flex items-center gap-1.5">
                  <PowerOff size={14} /> Tắt bài đang học
                </button>
              </div>
            </div>

          </div>

          {/* BOTTOM CARD: CẦN ÔN LẠI */}
          <div className="bg-[#0f2446] border border-blue-900/30 rounded-2xl p-6 shadow-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-blue-400">CẦN ÔN LẠI</span>
              <button className="text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors">
                Xem báo cáo →
              </button>
            </div>
            <h3 className="text-lg font-bold text-white mb-1">Từ và câu còn yếu</h3>
            <p className="text-xs text-gray-400">
              Chưa có dữ liệu điểm yếu. Hãy hoàn thành ít nhất một buổi học để hệ thống bắt đầu theo dõi.
            </p>
          </div>

        </main>
      </div>

      {/* FLOATING TOAST */}
      <div className="fixed bottom-4 right-4 bg-[#09172f]/95 border border-blue-600/40 text-white text-xs font-medium px-4 py-2.5 rounded-xl shadow-2xl backdrop-blur flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
        <span>Đã tải dữ liệu mới nhất.</span>
      </div>

    </div>
  );
}

