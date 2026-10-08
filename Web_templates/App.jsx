import React, { useState } from 'react';
import { 
  Menu, X, Cpu, Settings, BookOpen, Brain, 
  PlusCircle, BookMarked, Camera, HelpCircle, 
  MessageSquare, Phone, LogOut, Search, Crown, 
  Trash2, Eye, ShieldCheck, ChevronRight, XCircle
} from 'lucide-react';

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('devices');

  // State quản lý thiết bị
  const [devices, setDevices] = useState([
    {
      id: 'endpoint-1788747076580-giosy',
      name: '330730',
      url: 'wss://memory.gmbot.name.vn/ws',
      status: 'connected',
      isVip: true,
      vipTimer: '335d 18h 4m 51s'
    }
  ]);

  const [newDeviceName, setNewDeviceName] = useState('');
  const [newDeviceUrl, setNewDeviceUrl] = useState('');
  const [deviceSearch, setDeviceSearch] = useState('');
  const [selectedImageModal, setSelectedImageModal] = useState(null);

  // Thêm thiết bị
  const handleAddDevice = (e) => {
    e.preventDefault();
    if (!newDeviceName.trim()) return alert('Vui lòng nhập tên thiết bị');
    const newDev = {
      id: 'dev-' + Date.now(),
      name: newDeviceName.trim(),
      url: newDeviceUrl.trim() || 'wss://memory.gmbot.name.vn/ws',
      status: 'connected',
      isVip: false,
      vipTimer: ''
    };
    setDevices([newDev, ...devices]);
    setNewDeviceName('');
    setNewDeviceUrl('');
  };

  // Xóa thiết bị
  const handleDeleteDevice = (id) => {
    if (window.confirm('Bạn có chắc chắn muốn xóa thiết bị này?')) {
      setDevices(devices.filter(d => d.id !== id));
    }
  };

  const menuList = [
    { id: 'devices', label: 'Thiết bị', icon: '📡' },
    { id: 'config', label: 'Cấu hình Megabot AI', icon: '⚙️' },
    { id: 'english', label: 'HỌC TIẾNG ANH', icon: '📚' },
    { id: 'memory', label: 'Bộ nhớ', icon: '🧠' },
    { id: 'tasks', label: 'Tạo nhiệm vụ', icon: '📗' },
    { id: 'lessons', label: 'Chọn Bài học', icon: '📖' },
    { id: 'custom_lessons', label: 'Tự tạo bài học', icon: '🏕️' },
    { id: 'photo_lesson', label: 'Chụp ảnh tạo bài học', icon: '📷' },
    { id: 'photo_homework', label: 'Chụp ảnh giải bài tập', icon: '🎒' },
    { id: 'knowledge', label: 'Cơ sở tri thức', icon: '📗' },
  ];

  const secondaryMenuList = [
    { id: 'guide', label: 'Hướng dẫn sử dụng', icon: '⚙️' },
    { id: 'ha_guide', label: 'Hướng dẫn kết nối Home Assistant', icon: '🏕️' },
    { id: 'ha_request', label: 'Yêu cầu kết nối Home Assistant', icon: '🔗' },
    { id: 'feedback', label: 'Góp ý - Báo lỗi', icon: '💬' },
  ];

  const filteredDevices = devices.filter(d => 
    d.name.toLowerCase().includes(deviceSearch.toLowerCase()) ||
    d.id.toLowerCase().includes(deviceSearch.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-[#0b1f3d] text-white font-['Segoe_UI',sans-serif] flex">
      
      {/* ================= 1. OVERLAY MOBILE ================= */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/60 z-40 md:hidden backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ================= 2. SIDEBAR CỐ ĐỊNH BÊN TRÁI ================= */}
      <aside 
        className={`fixed top-0 bottom-0 left-0 z-50 w-[240px] bg-[#0b1220] flex flex-col 
        transition-transform duration-200 ease-in-out md:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* User profile box */}
        <div className="p-4">
          <div className="flex items-center justify-between md:hidden mb-2">
            <span className="text-xs font-bold text-gray-400 uppercase">Menu điều khiển</span>
            <button onClick={() => setSidebarOpen(false)} className="text-gray-400 hover:text-white">
              <X size={20} />
            </button>
          </div>

          <div className="flex flex-col gap-1.5 mb-4">
            <div className="text-[15px] font-bold text-white">Xin chào, 330730</div>
            <div className="text-xs text-gray-300">330730</div>
            
            <div className="flex items-center gap-1.5 text-xs">
              <span className="w-2.5 h-2.5 rounded-full bg-[#16a34a] inline-block"></span>
              <span className="text-[#16a34a] font-medium">connected</span>
            </div>

            <div className="flex items-center gap-1.5 mt-1">
              <span className="bg-[#fbbf24] text-black text-[11px] font-bold px-2 py-0.5 rounded-[20px]">
                👑 VIP
              </span>
              <span className="text-[#facc15] text-[11px] font-mono">
                335d 18h 4m 51s
              </span>
            </div>
          </div>
        </div>

        {/* Danh sách Menu dọc */}
        <nav className="flex-1 overflow-y-auto px-3 space-y-1 text-sm custom-scrollbar">
          {menuList.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setSidebarOpen(false);
                }}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[10px] text-left transition-all
                  ${isActive 
                    ? 'bg-[#13294b] text-white font-semibold shadow-inner' 
                    : 'text-gray-300 hover:bg-[#13294b]/60 hover:text-white'}`}
              >
                <span className="text-base">{item.icon}</span>
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}

          <div className="py-2">
            <div className="border-t border-gray-800" />
          </div>

          {secondaryMenuList.map((item) => (
            <button
              key={item.id}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[10px] text-xs text-gray-400 hover:bg-[#13294b]/60 hover:text-white transition-colors text-left"
            >
              <span className="text-sm">{item.icon}</span>
              <span className="truncate">{item.label}</span>
            </button>
          ))}
        </nav>

        {/* Chân Sidebar */}
        <div className="p-3 border-t border-gray-800 bg-[#070d18] text-xs space-y-2">
          <div className="text-gray-300 px-2">
            Zalo: <strong className="text-amber-400">0938.396.290</strong>
          </div>
          <button className="w-full flex items-center gap-2 px-2 py-1.5 text-red-400 hover:bg-red-500/10 rounded transition-colors font-semibold">
            <span>🚪</span>
            <span>Đăng xuất</span>
          </button>
        </div>
      </aside>

      {/* ================= 3. KHU VỰC NỘI DUNG CHÍNH ================= */}
      <div className="flex-1 flex flex-col min-w-0 md:ml-[240px]">
        
        {/* Topbar điều hướng */}
        <div className="px-4 py-3 flex items-center justify-between border-b border-[#13294b] text-xs md:text-sm">
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setSidebarOpen(true)}
              className="md:hidden bg-[#13294b] p-2 rounded-lg text-white"
            >
              <Menu size={18} />
            </button>
            <span className="text-gray-300">
              &lt;=== Bấm nút bên trái mở MENU điều khiển (<strong className="text-white">330730</strong>)
              <span className="text-gray-400 ml-1">(user)</span>
            </span>
          </div>
        </div>

        {/* Main Content Container */}
        <main className="p-4 md:p-6 w-full max-w-5xl mx-auto space-y-4">
          
          {/* CARD 1: THÊM THIẾT BỊ */}
          <section className="bg-[#13294b] rounded-[14px] p-4 md:p-5 shadow-lg">
            <h3 className="text-lg font-bold text-white mb-3">Thêm thiết bị</h3>
            <form onSubmit={handleAddDevice} className="space-y-2.5">
              <input
                type="text"
                placeholder="Tên thiết bị (đặt tùy ý)"
                value={newDeviceName}
                onChange={(e) => setNewDeviceName(e.target.value)}
                className="w-full bg-white text-black text-sm px-3.5 py-2.5 rounded-[8px] border-none outline-none focus:ring-2 focus:ring-blue-500"
              />
              <input
                type="text"
                placeholder="Nhập link wss://example.com/ws"
                value={newDeviceUrl}
                onChange={(e) => setNewDeviceUrl(e.target.value)}
                className="w-full bg-white text-black text-sm px-3.5 py-2.5 rounded-[8px] border-none outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="submit"
                className="w-full bg-[#2563eb] hover:bg-[#1d4ed8] active:scale-[0.99] text-white font-bold py-2.5 px-4 rounded-[8px] text-sm transition-all shadow-md shadow-blue-500/20"
              >
                Thêm thiết bị
              </button>
            </form>
          </section>

          {/* CARD 2: DANH SÁCH THIẾT BỊ */}
          <section className="bg-[#13294b] rounded-[14px] p-4 md:p-5 shadow-lg">
            <h3 className="text-lg font-bold text-white mb-3">Danh sách thiết bị</h3>
            
            {/* Search Input */}
            <div className="mb-4">
              <input
                type="text"
                placeholder="🔍 Tìm theo tên thiết bị (hoặc mã thiết bị)..."
                value={deviceSearch}
                onChange={(e) => setDeviceSearch(e.target.value)}
                className="w-full bg-white text-black text-sm px-3.5 py-2.5 rounded-[8px] border-none outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Danh sách các item thiết bị */}
            <div className="space-y-2.5 max-h-[55vh] overflow-y-auto pr-1 custom-scrollbar">
              {filteredDevices.length === 0 ? (
                <div className="text-center py-6 text-gray-400 text-sm">Không tìm thấy thiết bị nào</div>
              ) : (
                filteredDevices.map((dev) => (
                  <div
                    key={dev.id}
                    className="bg-[#0f2140] rounded-[8px] p-3 md:p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border border-blue-900/20 hover:border-blue-500/40 transition-colors"
                  >
                    <div>
                      <div className="text-base font-bold text-white tracking-wide">{dev.name}</div>
                      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                        <span className="bg-[#16a34a] text-white text-[11px] font-bold px-2 py-0.5 rounded-[20px]">
                          {dev.status}
                        </span>
                        {dev.isVip && (
                          <>
                            <span className="bg-[#fbbf24] text-black text-[11px] font-bold px-2 py-0.5 rounded-[20px]">
                              👑 VIP
                            </span>
                            <span className="text-[#facc15] text-[11px] font-mono">
                              {dev.vipTimer}
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                      <button
                        onClick={() => alert(`Xem Memory cho thiết bị: ${dev.name}`)}
                        className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-xs font-bold px-3 py-1.5 rounded-[8px] transition-colors"
                      >
                        Xem Memory
                      </button>
                      <button
                        onClick={() => alert(`Nâng cấp thiết bị: ${dev.name}`)}
                        className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-xs font-bold px-3 py-1.5 rounded-[8px] transition-colors"
                      >
                        Nâng cấp
                      </button>
                      <button
                        onClick={() => handleDeleteDevice(dev.id)}
                        className="bg-[#ef4444] hover:bg-[#dc2626] text-white text-xs font-bold px-3 py-1.5 rounded-[8px] transition-colors"
                      >
                        Xóa
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>

        </main>
      </div>

      {/* ================= 4. MODAL XEM CHI TIẾT ẢNH ================= */}
      {selectedImageModal && (
        <div 
          className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4 backdrop-blur-sm"
          onClick={() => setSelectedImageModal(null)}
        >
          <div className="relative max-w-2xl w-full bg-[#13294b] p-4 rounded-[14px] shadow-2xl border border-blue-900/50">
            <button 
              onClick={() => setSelectedImageModal(null)}
              className="absolute top-3 right-3 text-gray-400 hover:text-white"
            >
              <XCircle size={24} />
            </button>
            <img 
              src={selectedImageModal} 
              alt="Chi tiết" 
              className="w-full h-auto max-h-[80vh] object-contain rounded-lg mt-4" 
            />
          </div>
        </div>
      )}

    </div>
  );
}

