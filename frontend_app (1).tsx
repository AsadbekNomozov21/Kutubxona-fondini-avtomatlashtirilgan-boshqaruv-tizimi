import React, { useState, useEffect } from 'react';
import { BookOpen, Users, FileText, DollarSign, TrendingUp, AlertCircle, Search, Plus, LogOut, Menu, X } from 'lucide-react';

// API Base URL
const API_URL = 'http://localhost:8000/api';

// API Service
const api = {
  login: async (email, password) => {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);
    const res = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      body: formData
    });
    return res.json();
  },
  
  getBooks: async (token, search = '') => {
    const res = await fetch(`${API_URL}/books?search=${search}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
  },
  
  createBook: async (token, bookData) => {
    const res = await fetch(`${API_URL}/books`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(bookData)
    });
    return res.json();
  },
  
  getMembers: async (token, search = '') => {
    const res = await fetch(`${API_URL}/members?search=${search}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
  },
  
  getBorrowings: async (token) => {
    const res = await fetch(`${API_URL}/borrowings`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
  },
  
  returnBook: async (token, borrowId) => {
    const res = await fetch(`${API_URL}/borrowings/${borrowId}/return`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({})
    });
    return res.json();
  },
  
  getPenalties: async (token) => {
    const res = await fetch(`${API_URL}/penalties`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
  },
  
  payPenalty: async (token, penaltyId, amount) => {
    const res = await fetch(`${API_URL}/penalties/${penaltyId}/pay`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ paid_amount: amount })
    });
    return res.json();
  },
  
  getStats: async (token) => {
    const res = await fetch(`${API_URL}/stats`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
  },
  
  getPopularBooks: async (token) => {
    const res = await fetch(`${API_URL}/stats/popular-books`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
  }
};

// Login Component
const Login = ({ onLogin }) => {
  const [email, setEmail] = useState('admin@library.uz');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    
    try {
      const data = await api.login(email, password);
      if (data.access_token) {
        onLogin(data.access_token, data.user);
      } else {
        setError('Login xatosi');
      }
    } catch (err) {
      setError('Email yoki parol noto\'g\'ri');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-600 rounded-full mb-4">
            <BookOpen className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-800">Kutubxona tizimi</h1>
          <p className="text-gray-600 mt-2">Tizimga kirish</p>
        </div>
        
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="admin@library.uz"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Parol
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="••••••••"
            />
          </div>
          
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          )}
          
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full bg-indigo-600 text-white py-3 rounded-lg font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50"
          >
            {loading ? 'Yuklanmoqda...' : 'Kirish'}
          </button>
        </div>
        
        <div className="mt-6 text-center text-sm text-gray-600">
          <p>Test login: admin@library.uz</p>
          <p>Parol: admin123</p>
        </div>
      </div>
    </div>
  );
};

// Dashboard Component
const Dashboard = ({ token, user, onLogout }) => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [stats, setStats] = useState(null);
  const [books, setBooks] = useState([]);
  const [members, setMembers] = useState([]);
  const [borrowings, setBorrowings] = useState([]);
  const [penalties, setPenalties] = useState([]);
  const [popularBooks, setPopularBooks] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    try {
      if (activeTab === 'dashboard') {
        const [statsData, popularData] = await Promise.all([
          api.getStats(token),
          api.getPopularBooks(token)
        ]);
        setStats(statsData);
        setPopularBooks(popularData);
      } else if (activeTab === 'books') {
        const data = await api.getBooks(token, searchTerm);
        setBooks(data);
      } else if (activeTab === 'members') {
        const data = await api.getMembers(token, searchTerm);
        setMembers(data);
      } else if (activeTab === 'borrowings') {
        const data = await api.getBorrowings(token);
        setBorrowings(data);
      } else if (activeTab === 'penalties') {
        const data = await api.getPenalties(token);
        setPenalties(data);
      }
    } catch (error) {
      console.error('Ma\'lumot yuklashda xato:', error);
    }
  };

  const handleReturnBook = async (borrowId) => {
    if (confirm('Kitobni qaytarish tasdiqlaysizmi?')) {
      try {
        await api.returnBook(token, borrowId);
        loadData();
        alert('Kitob muvaffaqiyatli qaytarildi');
      } catch (error) {
        alert('Xatolik yuz berdi');
      }
    }
  };

  const handlePayPenalty = async (penaltyId, amount) => {
    if (confirm(`${amount} so'm jarimani to'lash tasdiqlaysizmi?`)) {
      try {
        await api.payPenalty(token, penaltyId, amount);
        loadData();
        alert('Jarima muvaffaqiyatli to\'landi');
      } catch (error) {
        alert('Xatolik yuz berdi');
      }
    }
  };

  const StatCard = ({ icon: Icon, title, value, color, subtitle }) => (
    <div className="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-shadow">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-600 text-sm font-medium">{title}</p>
          <p className={`text-3xl font-bold ${color} mt-2`}>{value}</p>
          {subtitle && <p className="text-gray-500 text-xs mt-1">{subtitle}</p>}
        </div>
        <div className={`p-4 rounded-full ${color.replace('text', 'bg').replace('600', '100')}`}>
          <Icon className={`w-8 h-8 ${color}`} />
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <div className={`bg-indigo-900 text-white transition-all duration-300 ${sidebarOpen ? 'w-64' : 'w-20'}`}>
        <div className="p-6">
          <div className="flex items-center justify-between mb-8">
            {sidebarOpen && (
              <div className="flex items-center gap-3">
                <BookOpen className="w-8 h-8" />
                <span className="font-bold text-xl">Kutubxona</span>
              </div>
            )}
            <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 hover:bg-indigo-800 rounded">
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>

          <nav className="space-y-2">
            {[
              { id: 'dashboard', icon: TrendingUp, label: 'Dashboard' },
              { id: 'books', icon: BookOpen, label: 'Kitoblar' },
              { id: 'members', icon: Users, label: 'A\'zolar' },
              { id: 'borrowings', icon: FileText, label: 'Ijaralar' },
              { id: 'penalties', icon: DollarSign, label: 'Jarimalar' }
            ].map(item => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  activeTab === item.id ? 'bg-indigo-700' : 'hover:bg-indigo-800'
                }`}
              >
                <item.icon className="w-5 h-5" />
                {sidebarOpen && <span>{item.label}</span>}
              </button>
            ))}
          </nav>
        </div>

        <div className="absolute bottom-0 left-0 right-0 p-6 border-t border-indigo-800">
          <div className={`flex items-center ${sidebarOpen ? 'gap-3' : 'justify-center'}`}>
            <div className="w-10 h-10 bg-indigo-700 rounded-full flex items-center justify-center">
              {user.full_name.charAt(0)}
            </div>
            {sidebarOpen && (
              <div className="flex-1">
                <p className="font-medium text-sm">{user.full_name}</p>
                <p className="text-xs text-indigo-300">{user.role}</p>
              </div>
            )}
          </div>
          <button
            onClick={onLogout}
            className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4" />
            {sidebarOpen && <span>Chiqish</span>}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        <div className="p-8">
          {/* Dashboard View */}
          {activeTab === 'dashboard' && stats && (
            <div>
              <h1 className="text-3xl font-bold text-gray-800 mb-8">Dashboard</h1>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <StatCard icon={BookOpen} title="Jami kitoblar" value={stats.total_books} color="text-blue-600" />
                <StatCard icon={Users} title="Jami a'zolar" value={stats.total_members} color="text-green-600" />
                <StatCard icon={FileText} title="Aktiv ijaralar" value={stats.active_borrowings} color="text-purple-600" />
                <StatCard 
                  icon={AlertCircle} 
                  title="Kechikkanlar" 
                  value={stats.late_borrowings} 
                  color="text-red-600"
                  subtitle={`${stats.unpaid_penalties.toLocaleString()} so'm jarima`}
                />
              </div>

              <div className="bg-white rounded-xl shadow-md p-6">
                <h2 className="text-xl font-bold text-gray-800 mb-4">Eng mashhur kitoblar</h2>
                <div className="space-y-3">
                  {popularBooks.map((book, index) => (
                    <div key={book.book_id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-4">
                        <div className="w-8 h-8 bg-indigo-600 text-white rounded-full flex items-center justify-center font-bold">
                          {index + 1}
                        </div>
                        <div>
                          <p className="font-semibold text-gray-800">{book.title}</p>
                          <p className="text-sm text-gray-600">{book.author}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-600">Ijaralar soni</p>
                        <p className="text-xl font-bold text-indigo-600">{book.borrow_count}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Books View */}
          {activeTab === 'books' && (
            <div>
              <div className="flex justify-between items-center mb-6">
                <h1 className="text-3xl font-bold text-gray-800">Kitoblar</h1>
              </div>

              <div className="mb-6">
                <div className="relative">
                  <Search className="absolute left-3 top-3 w-5 h-5 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Kitob qidirish..."
                    value={searchTerm}
                    onChange={(e) => {
                      setSearchTerm(e.target.value);
                      setTimeout(loadData, 300);
                    }}
                    className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {books.map(book => (
                  <div key={book.book_id} className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-lg transition-shadow">
                    <div className="h-48 bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center">
                      <BookOpen className="w-20 h-20 text-white opacity-50" />
                    </div>
                    <div className="p-6">
                      <h3 className="font-bold text-lg text-gray-800 mb-2">{book.title}</h3>
                      <p className="text-gray-600 mb-4">{book.author}</p>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500">{book.genre}</span>
                        <span className={`px-3 py-1 rounded-full ${
                          book.available_copies > 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                          {book.available_copies} / {book.total_copies}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Members View */}
          {activeTab === 'members' && (
            <div>
              <h1 className="text-3xl font-bold text-gray-800 mb-6">A'zolar</h1>

              <div className="bg-white rounded-xl shadow-md overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Ism</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Email</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Telefon</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Olingan</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Hozirgi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {members.map(member => (
                      <tr key={member.member_id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-gray-800">{member.full_name}</td>
                        <td className="px-6 py-4 text-gray-600">{member.email}</td>
                        <td className="px-6 py-4 text-gray-600">{member.phone}</td>
                        <td className="px-6 py-4 text-gray-800 font-semibold">{member.total_borrowed}</td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-sm ${
                            member.current_borrowed > 0 ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
                          }`}>
                            {member.current_borrowed}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Borrowings View */}
          {activeTab === 'borrowings' && (
            <div>
              <h1 className="text-3xl font-bold text-gray-800 mb-6">Ijaralar</h1>

              <div className="bg-white rounded-xl shadow-md overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">A'zo</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Kitob</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Sana</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Muddat</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Status</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Amallar</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {borrowings.map(borrow => (
                      <tr key={borrow.borrow_id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-gray-800">{borrow.member_name}</td>
                        <td className="px-6 py-4 text-gray-800">{borrow.book_title}</td>
                        <td className="px-6 py-4 text-gray-600">{borrow.borrow_date}</td>
                        <td className="px-6 py-4 text-gray-600">{borrow.due_date}</td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-sm ${
                            borrow.status === 'returned' ? 'bg-green-100 text-green-700' :
                            borrow.status === 'late' ? 'bg-red-100 text-red-700' :
                            'bg-blue-100 text-blue-700'
                          }`}>
                            {borrow.status === 'returned' ? 'Qaytarilgan' :
                             borrow.status === 'late' ? `Kechikkan (${borrow.days_late} kun)` :
                             'Olingan'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          {borrow.status !== 'returned' && (
                            <button
                              onClick={() => handleReturnBook(borrow.borrow_id)}
                              className="text-indigo-600 hover:text-indigo-800 font-medium"
                            >
                              Qaytarish
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Penalties View */}
          {activeTab === 'penalties' && (
            <div>
              <h1 className="text-3xl font-bold text-gray-800 mb-6">Jarimalar</h1>

              <div className="bg-white rounded-xl shadow-md overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">A'zo</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Sabab</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Summa</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Sana</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Status</th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">Amallar</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {penalties.map(penalty => (
                      <tr key={penalty.penalty_id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-gray-800">{penalty.member_name}</td>
                        <td className="px-6 py-4 text-gray-600 text-sm">{penalty.reason}</td>
                        <td className="px-6 py-4 text-gray-800 font-semibold">{penalty.amount.toLocaleString()} so'm</td>
                        <td className="px-6 py-4 text-gray-600">{penalty.issued_date}</td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-sm ${
                            penalty.status === 'paid' ? 'bg-green-100 text-green-700' :
                            penalty.status === 'waived' ? 'bg-gray-100 text-gray-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {penalty.status === 'paid' ? 'To\'langan' :
                             penalty.status === 'waived' ? 'Bekor qilingan' :
                             'To\'lanmagan'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          {penalty.status === 'unpaid' && (
                            <button
                              onClick={() => handlePayPenalty(penalty.penalty_id, penalty.amount)}
                              className="text-green-600 hover:text-green-800 font-medium"
                            >
                              To'lash
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Main App
export default function App() {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);

  const handleLogin = (accessToken, userData) => {
    setToken(accessToken);
    setUser(userData);
  };

  const handleLogout = () => {
    setToken(null);
    setUser(null);
  };

  if (!token) {
    return <Login onLogin={handleLogin} />;
  }

  return <Dashboard token={token} user={user} onLogout={handleLogout} />;
}