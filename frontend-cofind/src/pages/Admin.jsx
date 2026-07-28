import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/authContext';
import { adminService } from '../services/adminService';
import AdminSidebar from '../components/admin/AdminSidebar';
import AdminTopbar from '../components/admin/AdminTopbar';
import AdminStatCard from '../components/admin/AdminStatCard';
import AdminTable from '../components/admin/AdminTable';
import AdminModal from '../components/admin/AdminModal';
import CoordinatePickerMap from '../components/admin/CoordinatePickerMap';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', description: 'Ringkasan statistik dan aktivitas terbaru.' },
  { id: 'users', label: 'Users', description: 'Kelola akun, role admin, dan status user.' },
  { id: 'facilities', label: 'Coffee Shop', description: 'Kelola coffee shop, fasilitas, dan koordinat lokasi.' },
  { id: 'reviews', label: 'Reviews', description: 'Moderasi ulasan dan pantau engagement.' },
  { id: 'reports', label: 'Reports', description: 'Moderasi laporan review dari user.' },
  { id: 'ai', label: 'AI', description: 'Trigger analisis sentimen dan lihat cache AI.' },
  { id: 'settings', label: 'Settings', description: 'Informasi sistem admin dan konfigurasi LLM.' },
];

const DEFAULT_USER_FORM = {
  id: null,
  email: '',
  username: '',
  password: '',
  full_name: '',
  phone: '',
  bio: '',
  is_admin: false,
  is_active: true,
};

const DEFAULT_SHOP_FORM = {
  place_id: '',
  name: '',
  address: '',
  rating: '',
  total_reviews: '',
  latitude: '',
  longitude: '',
  map_embed_url: '',
  opening_hours_display: '',
};

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('id-ID', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function formatTimestamp(value) {
  if (!value) return '-';
  const date = new Date(Number(value) * 1000);
  if (Number.isNaN(date.getTime())) return '-';
  return formatDate(date.toISOString());
}

function formatJson(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
}

function SectionHeader({ title, description, actions }) {
  return (
    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
      <div>
        <h3 className="text-2xl font-bold text-stone-800">{title}</h3>
        <p className="text-sm text-stone-500 mt-1">{description}</p>
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

function Toolbar({ search, onSearchChange, filters }) {
  return (
    <div className="rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-4 flex flex-col lg:flex-row gap-3 lg:items-center lg:justify-between">
      <input
        type="text"
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        placeholder="Cari data..."
        className="w-full lg:max-w-md rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 transition-all duration-300 ease-out"
      />
      {filters ? <div className="flex flex-wrap gap-2">{filters}</div> : null}
    </div>
  );
}

export default function Admin() {
  const navigate = useNavigate();
  const { profile, isAdmin, signOut } = useAuth();

  const [activeSection, setActiveSection] = useState('dashboard');
  const [feedback, setFeedback] = useState(null);

  const [dashboard, setDashboard] = useState({ stats: null, recent_activity: [] });
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState('');

  const [users, setUsers] = useState([]);
  const [usersPagination, setUsersPagination] = useState(null);
  const [usersSearch, setUsersSearch] = useState('');
  const [userRoleFilter, setUserRoleFilter] = useState('');
  const [userStatusFilter, setUserStatusFilter] = useState('');
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState('');

  const [shops, setShops] = useState([]);
  const [shopsPagination, setShopsPagination] = useState(null);
  const [shopsSearch, setShopsSearch] = useState('');
  const [shopsLoading, setShopsLoading] = useState(false);
  const [shopsError, setShopsError] = useState('');

  const [reviews, setReviews] = useState([]);
  const [reviewsPagination, setReviewsPagination] = useState(null);
  const [reviewsSearch, setReviewsSearch] = useState('');
  const [reviewShopFilter, setReviewShopFilter] = useState('');
  const [reviewShopOptions, setReviewShopOptions] = useState([]);
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const [reviewsError, setReviewsError] = useState('');

  const [reviewReports, setReviewReports] = useState([]);
  const [reviewReportsPagination, setReviewReportsPagination] = useState(null);
  const [reviewReportsSearch, setReviewReportsSearch] = useState('');
  const [reviewReportsStatusFilter, setReviewReportsStatusFilter] = useState('');
  const [reviewReportsLoading, setReviewReportsLoading] = useState(false);
  const [reviewReportsError, setReviewReportsError] = useState('');

  const [aiCache, setAiCache] = useState([]);
  const [aiCacheLoading, setAiCacheLoading] = useState(false);
  const [aiCacheError, setAiCacheError] = useState('');
  const [aiRunningPlaceId, setAiRunningPlaceId] = useState('');
  const [aiShops, setAiShops] = useState([]);
  const [settings, setSettings] = useState(null);
  const [settingsLoading, setSettingsLoading] = useState(false);

  const [userModalOpen, setUserModalOpen] = useState(false);
  const [userModalMode, setUserModalMode] = useState('edit');
  const [userForm, setUserForm] = useState(DEFAULT_USER_FORM);
  const [userSubmitting, setUserSubmitting] = useState(false);

  const [shopModalOpen, setShopModalOpen] = useState(false);
  const [shopModalMode, setShopModalMode] = useState('create');
  const [shopForm, setShopForm] = useState(DEFAULT_SHOP_FORM);
  const [shopSubmitting, setShopSubmitting] = useState(false);

  const [facilityEditorOpen, setFacilityEditorOpen] = useState(false);
  const [facilityEditorShop, setFacilityEditorShop] = useState(null);
  const [facilityJsonText, setFacilityJsonText] = useState('');
  const [facilityEditorLoading, setFacilityEditorLoading] = useState(false);
  const [facilityEditorSubmitting, setFacilityEditorSubmitting] = useState(false);

  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [reportSubmitting, setReportSubmitting] = useState(false);
  const [reportForm, setReportForm] = useState({
    id: null,
    review_id: null,
    report_reason: '',
    report_text: '',
    status: 'pending',
    admin_notes: '',
    reported_by_username: '',
    review_text: '',
    shop_name: '',
    created_at: '',
  });

  useEffect(() => {
    document.title = 'Admin - Cofind';
    return () => {
      document.title = 'Cofind';
    };
  }, []);

  useEffect(() => {
    const { body, documentElement } = document;
    const hadDarkClass = documentElement.classList.contains('dark');
    const previousHtmlBackground = documentElement.style.backgroundColor;
    const previousBodyBackground = body.style.backgroundColor;
    const previousBodyColor = body.style.color;
    const previousColorScheme = documentElement.style.colorScheme;

    documentElement.classList.remove('dark');
    documentElement.style.backgroundColor = '#f8fafc';
    documentElement.style.colorScheme = 'light';
    body.style.backgroundColor = '#f8fafc';
    body.style.color = '#111827';

    return () => {
      if (hadDarkClass) {
        documentElement.classList.add('dark');
      }
      documentElement.style.backgroundColor = previousHtmlBackground;
      documentElement.style.colorScheme = previousColorScheme;
      body.style.backgroundColor = previousBodyBackground;
      body.style.color = previousBodyColor;
    };
  }, []);

  const showFeedback = useCallback((type, message) => {
    setFeedback({ type, message });
    window.clearTimeout(window.__cofindAdminToast);
    window.__cofindAdminToast = window.setTimeout(() => {
      setFeedback(null);
    }, 3500);
  }, []);

  const handleLogout = useCallback(async () => {
    await signOut();
    navigate('/login', { replace: true });
  }, [navigate, signOut]);

  const loadDashboard = useCallback(async () => {
    setDashboardLoading(true);
    setDashboardError('');
    try {
      const result = await adminService.getDashboard();
      setDashboard(result);
    } catch (error) {
      setDashboardError(error.message);
    } finally {
      setDashboardLoading(false);
    }
  }, []);

  const loadUsers = useCallback(async (page = 1, search = '', role = '', status = '') => {
    setUsersLoading(true);
    setUsersError('');
    try {
      const result = await adminService.getUsers({ page, per_page: 8, search, role, status });
      setUsers(result.items || []);
      setUsersPagination(result.pagination || null);
    } catch (error) {
      setUsersError(error.message);
    } finally {
      setUsersLoading(false);
    }
  }, []);

  const loadShops = useCallback(async (page = 1, search = '') => {
    setShopsLoading(true);
    setShopsError('');
    try {
      const result = await adminService.getShops({ page, per_page: 8, search });
      setShops(result.items || []);
      setShopsPagination(result.pagination || null);
    } catch (error) {
      setShopsError(error.message);
    } finally {
      setShopsLoading(false);
    }
  }, []);

  const loadReviews = useCallback(async (page = 1, search = '', placeId = '') => {
    setReviewsLoading(true);
    setReviewsError('');
    try {
      const result = await adminService.getReviews({ page, per_page: 8, search, place_id: placeId });
      setReviews(result.items || []);
      setReviewsPagination(result.pagination || null);
    } catch (error) {
      setReviewsError(error.message);
    } finally {
      setReviewsLoading(false);
    }
  }, []);

  const loadReviewShopOptions = useCallback(async () => {
    try {
      const result = await adminService.getShops({
        page: 1,
        per_page: 100,
      });
      setReviewShopOptions(result.items || []);
    } catch {
      setReviewShopOptions([]);
    }
  }, []);

  const loadReviewReports = useCallback(async (page = 1, search = '', status = '') => {
    setReviewReportsLoading(true);
    setReviewReportsError('');
    try {
      const result = await adminService.getReviewReports({ page, per_page: 8, search, status });
      setReviewReports(result.items || []);
      setReviewReportsPagination(result.pagination || null);
    } catch (error) {
      setReviewReportsError(error.message);
    } finally {
      setReviewReportsLoading(false);
    }
  }, []);

  const loadAICache = useCallback(async () => {
    setAiCacheLoading(true);
    setAiCacheError('');
    try {
      const [cacheResult, shopResult, settingsResult] = await Promise.all([
        adminService.getAICache(),
        adminService.getShops({ page: 1, per_page: 100 }),
        adminService.getSettings(),
      ]);
      setAiCache(cacheResult.items || []);
      setAiShops(shopResult.items || []);
      setSettings(settingsResult.settings || null);
    } catch (error) {
      setAiCacheError(error.message);
    } finally {
      setAiCacheLoading(false);
    }
  }, []);

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    try {
      const result = await adminService.getSettings();
      setSettings(result.settings || null);
    } finally {
      setSettingsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    loadDashboard();
    loadSettings();
  }, [isAdmin, loadDashboard, loadSettings]);

  useEffect(() => {
    if (!isAdmin || activeSection !== 'users') return;
    loadUsers(1, usersSearch, userRoleFilter, userStatusFilter);
  }, [isAdmin, activeSection, usersSearch, userRoleFilter, userStatusFilter, loadUsers]);

  useEffect(() => {
    if (!isAdmin || activeSection !== 'facilities') return;
    loadShops(1, shopsSearch);
  }, [isAdmin, activeSection, shopsSearch, loadShops]);

  useEffect(() => {
    if (!isAdmin || activeSection !== 'reviews') return;
    loadReviews(1, reviewsSearch, reviewShopFilter);
    loadReviewShopOptions();
  }, [isAdmin, activeSection, reviewsSearch, reviewShopFilter, loadReviews, loadReviewShopOptions]);

  useEffect(() => {
    if (!isAdmin || activeSection !== 'reports') return;
    loadReviewReports(1, reviewReportsSearch, reviewReportsStatusFilter);
  }, [isAdmin, activeSection, reviewReportsSearch, reviewReportsStatusFilter, loadReviewReports]);

  useEffect(() => {
    if (!isAdmin || activeSection !== 'ai') return;
    loadAICache();
  }, [isAdmin, activeSection, loadAICache]);

  const openUserCreateModal = () => {
    setUserModalMode('create');
    setUserForm(DEFAULT_USER_FORM);
    setUserModalOpen(true);
  };

  const openUserModal = (user) => {
    setUserModalMode('edit');
    setUserForm({
      id: user.id,
      email: user.email || '',
      username: user.username || '',
      password: '',
      full_name: user.full_name || '',
      phone: user.phone || '',
      bio: user.bio || '',
      is_admin: !!user.is_admin,
      is_active: !!user.is_active,
    });
    setUserModalOpen(true);
  };

  const closeUserModal = () => {
    setUserForm(DEFAULT_USER_FORM);
    setUserModalOpen(false);
  };

  const handleUserSubmit = async (event) => {
    event.preventDefault();
    setUserSubmitting(true);
    try {
      if (userModalMode === 'create') {
        await adminService.createUser(userForm);
        showFeedback('success', 'User baru berhasil dibuat.');
      } else {
        await adminService.updateUser(userForm.id, userForm);
        showFeedback('success', 'User berhasil diperbarui.');
      }
      closeUserModal();
      await Promise.all([loadUsers(usersPagination?.page || 1), loadDashboard()]);
    } catch (error) {
      showFeedback('error', error.message);
    } finally {
      setUserSubmitting(false);
    }
  };

  const handleDeleteUser = async (userId, username) => {
    if (!window.confirm(`Hapus user "${username}"? Semua data terkait (review, favorit, sesi) akan ikut dihapus.`)) return;
    try {
      await adminService.deleteUser(userId);
      showFeedback('success', `User "${username}" berhasil dihapus.`);
      await Promise.all([loadUsers(usersPagination?.page || 1), loadDashboard()]);
    } catch (error) {
      showFeedback('error', error.message);
    }
  };

  const openShopCreateModal = () => {
    setShopModalMode('create');
    setShopForm(DEFAULT_SHOP_FORM);
    setShopModalOpen(true);
  };

  const openShopEditModal = (shop) => {
    setShopModalMode('edit');
    setShopForm({
      place_id: shop.place_id || '',
      name: shop.name || '',
      address: shop.address || '',
      rating: shop.rating ?? '',
      total_reviews: shop.total_reviews ?? '',
      latitude: shop.latitude ?? '',
      longitude: shop.longitude ?? '',
      map_embed_url: shop.map_embed_url || '',
      opening_hours_display: shop.opening_hours_display || '',
    });
    setShopModalOpen(true);
  };

  const closeShopModal = () => {
    setShopForm(DEFAULT_SHOP_FORM);
    setShopModalOpen(false);
  };

  const openFacilityEditor = async (shop) => {
    setFacilityEditorOpen(true);
    setFacilityEditorShop(shop);
    setFacilityJsonText('');
    setFacilityEditorLoading(true);
    try {
      const result = await adminService.getFacilityEntry(shop.place_id);
      setFacilityJsonText(formatJson(result.item || {}));
    } catch (error) {
      showFeedback('error', error.message);
      setFacilityEditorOpen(false);
    } finally {
      setFacilityEditorLoading(false);
    }
  };

  const closeFacilityEditor = () => {
    setFacilityEditorOpen(false);
    setFacilityEditorShop(null);
    setFacilityJsonText('');
  };

  const handleShopSubmit = async (event) => {
    event.preventDefault();
    setShopSubmitting(true);
    try {
      const payload = {
        ...shopForm,
        rating: shopForm.rating === '' ? 0 : Number(shopForm.rating),
        total_reviews: shopForm.total_reviews === '' ? 0 : Number(shopForm.total_reviews),
        latitude: shopForm.latitude === '' ? null : Number(shopForm.latitude),
        longitude: shopForm.longitude === '' ? null : Number(shopForm.longitude),
      };

      if (shopModalMode === 'create') {
        await adminService.createShop(payload);
        showFeedback('success', 'Coffee shop berhasil ditambahkan.');
      } else {
        await adminService.updateShop(shopForm.place_id, payload);
        showFeedback('success', 'Coffee shop berhasil diperbarui.');
      }
      closeShopModal();
      await Promise.all([loadShops(shopsPagination?.page || 1), loadDashboard()]);
    } catch (error) {
      showFeedback('error', error.message);
    } finally {
      setShopSubmitting(false);
    }
  };

  const handleDeleteShop = async (placeId, name) => {
    if (!window.confirm(`Hapus coffee shop "${name}"? Data review terkait juga akan dihapus.`)) return;
    try {
      await adminService.deleteShop(placeId);
      showFeedback('success', 'Coffee shop berhasil dihapus.');
      await Promise.all([loadShops(shopsPagination?.page || 1), loadDashboard(), loadAICache()]);
    } catch (error) {
      showFeedback('error', error.message);
    }
  };

  const handleDeleteReview = async (reviewId) => {
    if (!window.confirm('Hapus review ini?')) return;
    try {
      await adminService.deleteReview(reviewId);
      showFeedback('success', 'Review berhasil dihapus.');
      await Promise.all([loadReviews(reviewsPagination?.page || 1), loadDashboard(), loadAICache()]);
    } catch (error) {
      showFeedback('error', error.message);
    }
  };

  const handleSaveFacilityEditor = async (event) => {
    event.preventDefault();
    if (!facilityEditorShop?.place_id) return;
    setFacilityEditorSubmitting(true);
    try {
      const parsed = JSON.parse(facilityJsonText);
      await adminService.updateFacilityEntry(facilityEditorShop.place_id, { item: parsed });
      showFeedback('success', 'Facilities JSON berhasil diperbarui.');
      closeFacilityEditor();
      await loadShops(shopsPagination?.page || 1);
    } catch (error) {
      showFeedback('error', error.message || 'JSON tidak valid.');
    } finally {
      setFacilityEditorSubmitting(false);
    }
  };

  const openReportModal = (report) => {
    setReportForm({
      id: report.id,
      review_id: report.review_id,
      report_reason: report.report_reason || '',
      report_text: report.report_text || '',
      status: report.status || 'pending',
      admin_notes: report.admin_notes || '',
      reported_by_username: report.reported_by_username || '',
      review_text: report.review_text || '',
      shop_name: report.shop_name || '',
      created_at: report.created_at || '',
    });
    setReportModalOpen(true);
  };

  const closeReportModal = () => {
    setReportModalOpen(false);
    setReportForm({
      id: null,
      review_id: null,
      report_reason: '',
      report_text: '',
      status: 'pending',
      admin_notes: '',
      reported_by_username: '',
      review_text: '',
      shop_name: '',
      created_at: '',
    });
  };

  const handleSaveReport = async (event) => {
    event.preventDefault();
    setReportSubmitting(true);
    try {
      await adminService.updateReviewReport(reportForm.id, {
        status: reportForm.status,
        admin_notes: reportForm.admin_notes,
      });
      showFeedback('success', 'Review report berhasil diperbarui.');
      closeReportModal();
      await Promise.all([loadReviewReports(reviewReportsPagination?.page || 1), loadDashboard()]);
    } catch (error) {
      showFeedback('error', error.message);
    } finally {
      setReportSubmitting(false);
    }
  };

  const handleRunSentiment = async (shop) => {
    setAiRunningPlaceId(shop.place_id);
    try {
      const result = await adminService.triggerSentimentAnalysis({
        place_id: shop.place_id,
        shop_name: shop.name,
      });
      showFeedback('success', result.from_cache ? 'Analisis AI diambil dari cache.' : 'Analisis AI berhasil dijalankan.');
      await loadAICache();
    } catch (error) {
      showFeedback('error', error.message);
    } finally {
      setAiRunningPlaceId('');
    }
  };

  const handleDeleteCache = async (placeId) => {
    if (!window.confirm('Hapus cache AI untuk coffee shop ini?')) return;
    try {
      await adminService.deleteAICache(placeId);
      showFeedback('success', 'Cache AI berhasil dihapus.');
      await loadAICache();
    } catch (error) {
      showFeedback('error', error.message);
    }
  };

  const userColumns = [
    {
      key: 'identity',
      label: 'User',
      render: (row) => (
        <div>
          <p className="font-semibold text-stone-800">{row.full_name || row.username}</p>
          <p className="text-xs text-stone-500">@{row.username} • {row.email}</p>
        </div>
      ),
    },
    {
      key: 'role',
      label: 'Role',
      render: (row) => (
        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
          row.is_admin
            ? 'bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800/60'
            : 'bg-slate-100 dark:bg-slate-700/70 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-600/70'
        }`}>
          {row.is_admin ? 'Admin' : 'User'}
        </span>
      ),
    },
    {
      key: 'stats',
      label: 'Aktivitas',
      render: (row) => (
        <div className="text-xs text-stone-600 space-y-1">
          <p>{row.review_count} review</p>
          <p>{row.favorite_count} favorit</p>
          <p>{row.want_to_visit_count} want-to-visit</p>
        </div>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (row) => (
        <div className="text-xs">
          <p className={row.is_active ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
            {row.is_active ? 'Aktif' : 'Nonaktif'}
          </p>
          <p className="text-stone-500 mt-1">{formatDate(row.created_at)}</p>
        </div>
      ),
    },
    {
      key: 'actions',
      label: 'Aksi',
      render: (row) => (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => openUserModal(row)}
            className="rounded-lg bg-amber-700 px-3 py-2 text-xs font-medium text-stone-50 hover:bg-amber-800 transition-all duration-300 ease-out cursor-pointer"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={() => handleDeleteUser(row.id, row.username)}
            className="rounded-lg bg-red-600 px-3 py-2 text-xs font-medium text-stone-50 hover:bg-red-700 transition-all duration-300 ease-out cursor-pointer"
          >
            Hapus
          </button>
        </div>
      ),
    },
  ];

  const shopColumns = [
    {
      key: 'name',
      label: 'Coffee Shop',
      render: (row) => (
        <div>
          <p className="font-semibold text-stone-800">{row.name}</p>
          <p className="text-xs text-stone-500">{row.place_id}</p>
        </div>
      ),
    },
    {
      key: 'address',
      label: 'Alamat & Lokasi',
      render: (row) => (
        <div className="space-y-1">
          <p>{row.address}</p>
          <p className="text-xs text-stone-500">
            Lat: {row.latitude ?? '-'} • Lng: {row.longitude ?? '-'}
          </p>
        </div>
      ),
    },
    {
      key: 'facilities',
      label: 'Fasilitas',
      render: (row) => (
        <div className="space-y-1">
          <p className="text-xs text-stone-500">
            {row.has_facilities ? `${row.facility_count} indikator fasilitas` : 'Belum ada data facilities.json'}
          </p>
          <p className="text-xs line-clamp-3">{row.facilities_text || '-'}</p>
        </div>
      ),
    },
    {
      key: 'rating',
      label: 'Rating',
      render: (row) => (
        <div className="text-xs">
          <p>{row.rating || 0} / 5</p>
          <p className="text-stone-500">{row.total_reviews || 0} review</p>
        </div>
      ),
    },
    {
      key: 'actions',
      label: 'Aksi',
      render: (row) => (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => openFacilityEditor(row)}
            className="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-medium text-stone-50 hover:bg-emerald-800 transition-all duration-300 ease-out cursor-pointer"
          >
            Edit JSON
          </button>
          <button
            type="button"
            onClick={() => openShopEditModal(row)}
            className="rounded-lg bg-amber-700 px-3 py-2 text-xs font-medium text-stone-50 hover:bg-amber-800 transition-all duration-300 ease-out cursor-pointer"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={() => handleDeleteShop(row.place_id, row.name)}
            className="rounded-lg bg-red-600 px-3 py-2 text-xs font-medium text-stone-50 hover:bg-red-700 transition-all duration-300 ease-out cursor-pointer"
          >
            Hapus
          </button>
        </div>
      ),
    },
  ];

  const reviewColumns = [
    {
      key: 'review',
      label: 'Review',
      render: (row) => (
        <div className="space-y-1">
          <p className="font-semibold text-stone-800">{row.shop_name || row.place_id}</p>
          <p className="text-xs text-stone-500">oleh {row.username || 'Anonim'}</p>
          <p className="text-xs line-clamp-3">{row.text || '(Tanpa teks)'}</p>
        </div>
      ),
    },
    {
      key: 'scores',
      label: 'Skor',
      render: (row) => (
        <div className="text-xs space-y-1">
          <p>Rating: {row.rating}</p>
        </div>
      ),
    },
    {
      key: 'meta',
      label: 'Meta',
      render: (row) => (
        <div className="text-xs space-y-1">
          <p>{row.photo_count} foto</p>
          <p>{row.like_count} like</p>
          <p className="text-stone-500">{formatDate(row.created_at)}</p>
        </div>
      ),
    },
    {
      key: 'actions',
      label: 'Aksi',
      render: (row) => (
        <button
          type="button"
          onClick={() => handleDeleteReview(row.id)}
          className="rounded-lg bg-red-600 px-3 py-2 text-xs font-medium text-stone-50 hover:bg-red-700 transition-all duration-300 ease-out cursor-pointer"
        >
          Hapus
        </button>
      ),
    },
  ];

  const reviewReportColumns = [
    {
      key: 'report',
      label: 'Report',
      render: (row) => (
        <div className="space-y-1">
          <p className="font-semibold text-stone-800">{row.report_reason || 'Tanpa alasan'}</p>
          <p className="text-xs text-stone-500">
            {row.shop_name || row.place_id || 'Coffee Shop'} • pelapor {row.reported_by_username || 'User'}
          </p>
          <p className="text-xs line-clamp-3">{row.report_text || '(Tanpa detail laporan)'}</p>
        </div>
      ),
    },
    {
      key: 'review_text',
      label: 'Review Terkait',
      render: (row) => (
        <div className="space-y-1">
          <p className="text-xs line-clamp-3">{row.review_text || '(Review sudah tidak ada)'}</p>
          <p className="text-xs text-stone-500">{formatDate(row.created_at)}</p>
        </div>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (row) => (
        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
          row.status === 'resolved'
            ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800/60'
            : row.status === 'dismissed'
            ? 'bg-slate-100 dark:bg-slate-700/70 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-600/70'
            : row.status === 'reviewed'
            ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800/60'
            : 'bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800/60'
        }`}>
          {row.status || 'pending'}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Aksi',
      render: (row) => (
        <button
          type="button"
          onClick={() => openReportModal(row)}
          className="rounded-lg bg-amber-700 px-3 py-2 text-xs font-medium text-stone-50 hover:bg-amber-800 transition-all duration-300 ease-out cursor-pointer"
        >
          Moderasi
        </button>
      ),
    },
  ];

  const aiCacheColumns = [
    {
      key: 'shop_name',
      label: 'Coffee Shop',
      render: (row) => (
        <div>
          <p className="font-semibold text-stone-800">{row.shop_name}</p>
          <p className="text-xs text-stone-500">{row.place_id}</p>
        </div>
      ),
    },
    {
      key: 'summary',
      label: 'Ringkasan Cache',
      render: (row) => (
        <div className="space-y-1">
          <p className="text-xs line-clamp-3">{row.data?.ringkasan || '-'}</p>
          <p className="text-xs text-stone-500">
            {row.review_count} review • {formatTimestamp(row.timestamp)}
          </p>
        </div>
      ),
    },
    {
      key: 'actions',
      label: 'Aksi',
      render: (row) => (
        <button
          type="button"
          onClick={() => handleDeleteCache(row.place_id)}
          className="rounded-lg bg-red-600 px-3 py-2 text-xs font-medium text-stone-50 hover:bg-red-700 transition-all duration-300 ease-out cursor-pointer"
        >
          Hapus cache
        </button>
      ),
    },
  ];

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-[#FAF9F6] via-stone-50 to-amber-50/30 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-[#FAF9F6]/95 border border-stone-200/50 rounded-2xl shadow-[0_12px_40px_rgb(0,0,0,0.08)] p-8 text-center">
          <div className="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-stone-800 mb-2">Akses Ditolak</h2>
          <p className="text-stone-600 mb-6">
            Halaman ini hanya dapat diakses oleh administrator.
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-4 py-2 bg-amber-700 text-stone-50 rounded-lg hover:bg-amber-800 transition-all duration-300 ease-out cursor-pointer"
          >
            Kembali ke Beranda
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#FAF9F6] via-stone-50 to-amber-50/30 px-3 py-6 sm:px-4 md:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <AdminTopbar profile={profile} onLogout={handleLogout} />

        {feedback ? (
          <div className={`rounded-2xl px-4 py-3 text-sm font-medium ${
            feedback.type === 'success'
              ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
              : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
          }`}>
            {feedback.message}
          </div>
        ) : null}

        <div className="flex flex-col lg:flex-row gap-6">
          <AdminSidebar items={NAV_ITEMS} activeSection={activeSection} onChangeSection={setActiveSection} />

          <main className="flex-1 space-y-6">
            {activeSection === 'dashboard' ? (
              <>
                <SectionHeader
                  title="Dashboard"
                  description="Ringkasan data utama, aktivitas terbaru, dan status aplikasi admin."
                  actions={
                    <button
                      type="button"
                      onClick={loadDashboard}
                      className="rounded-xl bg-amber-700 px-4 py-2 text-sm font-medium text-stone-50 hover:bg-amber-800 transition-all duration-300 ease-out cursor-pointer"
                    >
                      Refresh
                    </button>
                  }
                />

                {dashboardError ? (
                  <div className="rounded-2xl bg-red-100 dark:bg-red-900/30 px-4 py-3 text-sm text-red-700 dark:text-red-400">
                    {dashboardError}
                  </div>
                ) : null}

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                  <AdminStatCard label="Total Users" value={dashboardLoading ? '...' : dashboard.stats?.total_users ?? 0} helper="Termasuk admin dan user biasa." />
                  <AdminStatCard label="Total Facilities / Shops" value={dashboardLoading ? '...' : dashboard.stats?.total_facilities ?? 0} helper="Jumlah coffee shop di database." />
                  <AdminStatCard label="Total Reviews" value={dashboardLoading ? '...' : dashboard.stats?.total_reviews ?? 0} helper="Review user yang tersimpan." />
                  <AdminStatCard label="Total Review Reports" value={dashboardLoading ? '...' : dashboard.stats?.total_review_reports ?? 0} helper="Laporan review yang perlu dimoderasi." />
                </div>

                <div className="rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-5">
                  <h4 className="text-lg font-semibold text-stone-800 mb-4">Aktivitas terbaru</h4>
                  <div className="space-y-3">
                    {(dashboard.recent_activity || []).length === 0 ? (
                      <p className="text-sm text-stone-500">Belum ada aktivitas terbaru.</p>
                    ) : (
                      dashboard.recent_activity.map((item, index) => (
                        <div key={`${item.type}-${index}`} className="rounded-xl border border-stone-200/60 bg-stone-100/40 p-4">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="font-medium text-stone-800">{item.title}</p>
                              <p className="text-sm text-stone-500">{item.description}</p>
                            </div>
                            <span className="text-xs text-stone-500">{formatDate(item.created_at)}</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </>
            ) : null}

            {activeSection === 'users' ? (
              <>
                <SectionHeader
                  title="Users"
                  description="Kelola akun, role admin, dan status aktif user."
                  actions={
                    <button
                      type="button"
                      onClick={openUserCreateModal}
                      className="rounded-xl bg-amber-700 px-4 py-2 text-sm font-medium text-stone-50 hover:bg-amber-800 transition-all duration-300 ease-out cursor-pointer"
                    >
                      Tambah user
                    </button>
                  }
                />
                <Toolbar
                  search={usersSearch}
                  onSearchChange={setUsersSearch}
                  filters={
                    <>
                      <select
                        value={userRoleFilter}
                        onChange={(event) => setUserRoleFilter(event.target.value)}
                        className="rounded-xl border border-stone-300/70 bg-stone-50 px-3 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
                      >
                        <option value="">Semua role</option>
                        <option value="admin">Admin</option>
                        <option value="user">User</option>
                      </select>
                      <select
                        value={userStatusFilter}
                        onChange={(event) => setUserStatusFilter(event.target.value)}
                        className="rounded-xl border border-stone-300/70 bg-stone-50 px-3 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
                      >
                        <option value="">Semua status</option>
                        <option value="active">Aktif</option>
                        <option value="inactive">Nonaktif</option>
                      </select>
                    </>
                  }
                />
                <AdminTable
                  columns={userColumns}
                  rows={users}
                  loading={usersLoading}
                  error={usersError}
                  pagination={usersPagination}
                  onPageChange={(p) => loadUsers(p, usersSearch, userRoleFilter, userStatusFilter)}
                  emptyMessage="Belum ada user yang cocok dengan filter."
                />
              </>
            ) : null}

            {activeSection === 'facilities' ? (
              <>
                <SectionHeader
                  title="Coffee Shop"
                  description="Kelola data coffee shop, lokasi, rating, dan edit penuh entry facilities.json per coffee shop."
                  actions={
                    <button
                      type="button"
                      onClick={openShopCreateModal}
                      className="rounded-xl bg-amber-700 px-4 py-2 text-sm font-medium text-stone-50 hover:bg-amber-800 transition-all duration-300 ease-out cursor-pointer"
                    >
                      Tambah coffee shop
                    </button>
                  }
                />
                <Toolbar search={shopsSearch} onSearchChange={setShopsSearch} />
                <AdminTable
                  columns={shopColumns}
                  rows={shops}
                  loading={shopsLoading}
                  error={shopsError}
                  pagination={shopsPagination}
                  onPageChange={(p) => loadShops(p, shopsSearch)}
                  emptyMessage="Belum ada coffee shop yang cocok."
                />
              </>
            ) : null}

            {activeSection === 'reviews' ? (
              <>
                <SectionHeader title="Reviews" description="Moderasi review user, cek skor, foto, dan engagement." />
                <Toolbar
                  search={reviewsSearch}
                  onSearchChange={setReviewsSearch}
                  filters={
                    <select
                      value={reviewShopFilter}
                      onChange={(event) => setReviewShopFilter(event.target.value)}
                      className="rounded-xl border border-stone-300/70 bg-stone-50 px-3 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 transition-all duration-300 ease-out"
                    >
                      <option value="">Semua coffee shop</option>
                      {reviewShopOptions.map((shop) => (
                        <option key={shop.place_id} value={shop.place_id}>
                          {shop.name}
                        </option>
                      ))}
                    </select>
                  }
                />
                <AdminTable
                  columns={reviewColumns}
                  rows={reviews}
                  loading={reviewsLoading}
                  error={reviewsError}
                  pagination={reviewsPagination}
                  onPageChange={(p) => loadReviews(p, reviewsSearch, reviewShopFilter)}
                  emptyMessage="Belum ada review yang cocok."
                />
              </>
            ) : null}

            {activeSection === 'reports' ? (
              <>
                <SectionHeader title="Review Reports" description="Moderasi laporan review: cek alasan, review terkait, dan beri status tindak lanjut." />
                <Toolbar
                  search={reviewReportsSearch}
                  onSearchChange={setReviewReportsSearch}
                  filters={
                    <select
                      value={reviewReportsStatusFilter}
                      onChange={(event) => setReviewReportsStatusFilter(event.target.value)}
                      className="rounded-xl border border-stone-300/70 bg-stone-50 px-3 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
                    >
                      <option value="">Semua status</option>
                      <option value="pending">pending</option>
                      <option value="reviewed">reviewed</option>
                      <option value="resolved">resolved</option>
                      <option value="dismissed">dismissed</option>
                    </select>
                  }
                />
                <AdminTable
                  columns={reviewReportColumns}
                  rows={reviewReports}
                  loading={reviewReportsLoading}
                  error={reviewReportsError}
                  pagination={reviewReportsPagination}
                  onPageChange={(p) => loadReviewReports(p, reviewReportsSearch, reviewReportsStatusFilter)}
                  emptyMessage="Belum ada review report."
                />
              </>
            ) : null}

            {activeSection === 'ai' ? (
              <>
                <SectionHeader title="AI Management" description="Jalankan analisis sentimen per coffee shop dan pantau hasil cache yang tersimpan." />
                {aiCacheError ? (
                  <div className="rounded-2xl bg-red-100 dark:bg-red-900/30 px-4 py-3 text-sm text-red-700 dark:text-red-400">
                    {aiCacheError}
                  </div>
                ) : null}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-5">
                    <h4 className="font-semibold text-stone-800 mb-4">Trigger analisis sentimen</h4>
                    <div className="space-y-3 max-h-[420px] overflow-y-auto">
                      {aiShops.map((shop) => (
                        <div key={shop.place_id} className="rounded-xl border border-stone-200/60 p-4 flex items-center justify-between gap-3">
                          <div>
                            <p className="font-medium text-stone-800">{shop.name}</p>
                            <p className="text-xs text-stone-500">{shop.place_id}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleRunSentiment(shop)}
                            disabled={aiRunningPlaceId === shop.place_id}
                            className="rounded-lg bg-amber-700 px-3 py-2 text-xs font-medium text-stone-50 hover:bg-amber-800 transition-all duration-300 ease-out cursor-pointer disabled:opacity-60"
                          >
                            {aiRunningPlaceId === shop.place_id ? 'Menganalisis...' : 'Analisis'}
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-5">
                    <h4 className="font-semibold text-stone-800 mb-4">Status AI</h4>
                    <div className="space-y-3 text-sm">
                      <div className="rounded-xl bg-stone-100/40 border border-stone-200/60 p-4">
                        <p className="text-stone-500">LLM tersedia</p>
                        <p className="font-semibold text-stone-800">{settings?.llm_available ? 'Ya' : 'Tidak'}</p>
                      </div>
                      <div className="rounded-xl bg-stone-100/40 border border-stone-200/60 p-4">
                        <p className="text-stone-500">Model</p>
                        <p className="font-semibold text-stone-800 break-all">{settings?.llm_model || '-'}</p>
                      </div>
                      <div className="rounded-xl bg-stone-100/40 border border-stone-200/60 p-4">
                        <p className="text-stone-500">Total cache</p>
                        <p className="font-semibold text-stone-800">{aiCache.length}</p>
                      </div>
                    </div>
                  </div>
                </div>

                <AdminTable
                  columns={aiCacheColumns}
                  rows={aiCache}
                  loading={aiCacheLoading}
                  error={aiCacheError}
                  emptyMessage="Belum ada cache analisis sentimen."
                />
              </>
            ) : null}

            {activeSection === 'settings' ? (
              <>
                <SectionHeader title="Settings" description="Ringkasan konfigurasi admin, LLM, dan integrasi frontend-backend." />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-5">
                    <h4 className="font-semibold text-stone-800 mb-3">Konfigurasi sistem</h4>
                    {settingsLoading ? (
                      <p className="text-sm text-stone-500">Memuat settings...</p>
                    ) : (
                      <div className="space-y-3 text-sm">
                        <p><span className="font-medium">LLM tersedia:</span> {settings?.llm_available ? 'Ya' : 'Tidak'}</p>
                        <p><span className="font-medium">Model LLM:</span> {settings?.llm_model || '-'}</p>
                        <p><span className="font-medium">Cache sentiment:</span> {settings?.cache_expiry_days ?? '-'} hari</p>
                        <p><span className="font-medium">Catatan:</span> {settings?.api_base_note || '-'}</p>
                      </div>
                    )}
                  </div>

                  <div className="rounded-2xl border border-stone-200/50 bg-[#FAF9F6]/95 shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-5">
                    <h4 className="font-semibold text-stone-800 mb-3">Saran operasional</h4>
                    <div className="space-y-3 text-sm text-stone-600">
                      <p>Gunakan tab Facilities untuk memperbarui latitude dan longitude dengan klik langsung di peta.</p>
                      <p>Setelah menghapus review besar-besaran, jalankan ulang analisis AI pada coffee shop terkait agar cache tetap relevan.</p>
                      <p>Saran preferensi dari user dapat menjadi dasar menambah pill preferensi baru di halaman utama.</p>
                    </div>
                  </div>
                </div>
              </>
            ) : null}
          </main>
        </div>
      </div>

      <AdminModal
        isOpen={userModalOpen}
        title={userModalMode === 'create' ? 'Tambah User Baru' : 'Edit User'}
        onClose={closeUserModal}
        maxWidth="max-w-2xl"
      >
        <form onSubmit={handleUserSubmit} className="space-y-4">
          {userModalMode === 'create' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">
                  Email <span className="text-red-500 dark:text-red-400">*</span>
                </label>
                <input
                  type="email"
                  required
                  value={userForm.email}
                  onChange={(event) => setUserForm((prev) => ({ ...prev, email: event.target.value }))}
                  placeholder="user@example.com"
                  className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">
                  Password <span className="text-red-500 dark:text-red-400">*</span>
                </label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={userForm.password}
                  onChange={(event) => setUserForm((prev) => ({ ...prev, password: event.target.value }))}
                  placeholder="Min. 6 karakter"
                  className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>
            </div>
          ) : null}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">
                Username {userModalMode === 'create' ? <span className="text-red-500 dark:text-red-400">*</span> : null}
              </label>
              <input
                type="text"
                required={userModalMode === 'create'}
                value={userForm.username}
                onChange={(event) => setUserForm((prev) => ({ ...prev, username: event.target.value }))}
                className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Nama lengkap</label>
              <input
                type="text"
                value={userForm.full_name}
                onChange={(event) => setUserForm((prev) => ({ ...prev, full_name: event.target.value }))}
                className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Nomor telepon</label>
            <input
              type="text"
              value={userForm.phone}
              onChange={(event) => setUserForm((prev) => ({ ...prev, phone: event.target.value }))}
              className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Bio</label>
            <textarea
              rows={3}
              value={userForm.bio}
              onChange={(event) => setUserForm((prev) => ({ ...prev, bio: event.target.value }))}
              className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="flex items-center gap-3 rounded-xl border border-stone-200/60 p-4 cursor-pointer">
              <input
                type="checkbox"
                checked={userForm.is_admin}
                onChange={(event) => setUserForm((prev) => ({ ...prev, is_admin: event.target.checked }))}
              />
              <div>
                <p className="text-sm font-medium text-stone-700">Role admin</p>
                <p className="text-xs text-stone-500">Akses ke dashboard admin</p>
              </div>
            </label>
            <label className="flex items-center gap-3 rounded-xl border border-stone-200/60 p-4 cursor-pointer">
              <input
                type="checkbox"
                checked={userForm.is_active}
                onChange={(event) => setUserForm((prev) => ({ ...prev, is_active: event.target.checked }))}
              />
              <div>
                <p className="text-sm font-medium text-stone-700">Akun aktif</p>
                <p className="text-xs text-stone-500">User bisa login jika aktif</p>
              </div>
            </label>
          </div>

          <div className="flex justify-end gap-3">
            <button type="button" onClick={closeUserModal} className="rounded-xl border border-stone-300/70 px-4 py-2 text-sm text-stone-700 hover:bg-stone-100 transition-all duration-300 ease-out cursor-pointer">
              Batal
            </button>
            <button type="submit" disabled={userSubmitting} className="rounded-xl bg-amber-700 px-4 py-2 text-sm font-medium text-stone-50 hover:bg-amber-800 disabled:opacity-60 transition-all duration-300 ease-out cursor-pointer">
              {userSubmitting ? 'Menyimpan...' : userModalMode === 'create' ? 'Buat user' : 'Simpan perubahan'}
            </button>
          </div>
        </form>
      </AdminModal>

      <AdminModal
        isOpen={shopModalOpen}
        title={shopModalMode === 'create' ? 'Tambah Coffee Shop' : 'Edit Coffee Shop'}
        onClose={closeShopModal}
        maxWidth="max-w-5xl"
      >
        <form onSubmit={handleShopSubmit} className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Place ID</label>
              <input
                type="text"
                value={shopForm.place_id}
                disabled={shopModalMode === 'edit'}
                onChange={(event) => setShopForm((prev) => ({ ...prev, place_id: event.target.value }))}
                placeholder="Kosongkan untuk generate otomatis"
                className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:opacity-60"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Nama coffee shop</label>
              <input
                type="text"
                value={shopForm.name}
                onChange={(event) => setShopForm((prev) => ({ ...prev, name: event.target.value }))}
                required
                className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Alamat</label>
            <textarea
              rows={3}
              value={shopForm.address}
              onChange={(event) => setShopForm((prev) => ({ ...prev, address: event.target.value }))}
              required
              className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Rating</label>
              <input
                type="number"
                min="0"
                max="5"
                step="0.1"
                value={shopForm.rating}
                onChange={(event) => setShopForm((prev) => ({ ...prev, rating: event.target.value }))}
                className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Total review</label>
              <input
                type="number"
                min="0"
                value={shopForm.total_reviews}
                onChange={(event) => setShopForm((prev) => ({ ...prev, total_reviews: event.target.value }))}
                className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Latitude</label>
              <input
                type="number"
                step="0.000001"
                value={shopForm.latitude}
                onChange={(event) => setShopForm((prev) => ({ ...prev, latitude: event.target.value }))}
                className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Longitude</label>
              <input
                type="number"
                step="0.000001"
                value={shopForm.longitude}
                onChange={(event) => setShopForm((prev) => ({ ...prev, longitude: event.target.value }))}
                className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 mb-2">Pilih koordinat di peta</label>
            <CoordinatePickerMap
              latitude={shopForm.latitude === '' ? null : Number(shopForm.latitude)}
              longitude={shopForm.longitude === '' ? null : Number(shopForm.longitude)}
              onChange={(lat, lng) => setShopForm((prev) => ({ ...prev, latitude: lat, longitude: lng }))}
            />
            <p className="mt-2 text-xs text-stone-500">
              Klik pada peta untuk mengisi latitude dan longitude otomatis.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Map embed URL</label>
              <input
                type="text"
                value={shopForm.map_embed_url}
                onChange={(event) => setShopForm((prev) => ({ ...prev, map_embed_url: event.target.value }))}
                className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Jam operasional</label>
              <input
                type="text"
                value={shopForm.opening_hours_display}
                onChange={(event) => setShopForm((prev) => ({ ...prev, opening_hours_display: event.target.value }))}
                placeholder="Contoh: Senin-Minggu, 08.00-22.00"
                className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button type="button" onClick={closeShopModal} className="rounded-xl border border-stone-300/70 px-4 py-2 text-sm text-stone-700 hover:bg-stone-100 transition-all duration-300 ease-out cursor-pointer">
              Batal
            </button>
            <button type="submit" disabled={shopSubmitting} className="rounded-xl bg-amber-700 px-4 py-2 text-sm font-medium text-stone-50 hover:bg-amber-800 disabled:opacity-60 transition-all duration-300 ease-out cursor-pointer">
              {shopSubmitting ? 'Menyimpan...' : shopModalMode === 'create' ? 'Tambah coffee shop' : 'Simpan perubahan'}
            </button>
          </div>
        </form>
      </AdminModal>

      <AdminModal
        isOpen={facilityEditorOpen}
        title={`Edit Facilities JSON${facilityEditorShop?.name ? ` - ${facilityEditorShop.name}` : ''}`}
        onClose={closeFacilityEditor}
        maxWidth="max-w-5xl"
      >
        {facilityEditorLoading ? (
          <div className="py-12 text-center text-sm text-stone-500">Memuat data facilities...</div>
        ) : (
          <form onSubmit={handleSaveFacilityEditor} className="space-y-4">
            <div className="rounded-xl bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 p-4 text-sm text-amber-800 dark:text-amber-300">
              Editor ini bersifat penuh: Anda dapat mengubah seluruh struktur entry `facilities.json` untuk coffee shop ini. Pastikan JSON tetap valid.
            </div>
            <textarea
              value={facilityJsonText}
              onChange={(event) => setFacilityJsonText(event.target.value)}
              rows={24}
              spellCheck={false}
              className="w-full rounded-xl border border-stone-300/70 bg-stone-50 text-stone-800 font-mono text-xs px-4 py-3 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
            <div className="flex justify-end gap-3">
              <button type="button" onClick={closeFacilityEditor} className="rounded-xl border border-stone-300/70 px-4 py-2 text-sm text-stone-700 hover:bg-stone-100 transition-all duration-300 ease-out cursor-pointer">
                Batal
              </button>
              <button type="submit" disabled={facilityEditorSubmitting} className="rounded-xl bg-emerald-700 px-4 py-2 text-sm font-medium text-stone-50 hover:bg-emerald-800 disabled:opacity-60 transition-all duration-300 ease-out cursor-pointer">
                {facilityEditorSubmitting ? 'Menyimpan...' : 'Simpan JSON'}
              </button>
            </div>
          </form>
        )}
      </AdminModal>

      <AdminModal
        isOpen={reportModalOpen}
        title="Moderasi Review Report"
        onClose={closeReportModal}
        maxWidth="max-w-3xl"
      >
        <form onSubmit={handleSaveReport} className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-stone-200/60 p-4">
              <p className="text-xs text-stone-500">Coffee shop</p>
              <p className="mt-1 font-medium text-stone-800">{reportForm.shop_name || '-'}</p>
            </div>
            <div className="rounded-xl border border-stone-200/60 p-4">
              <p className="text-xs text-stone-500">Pelapor</p>
              <p className="mt-1 font-medium text-stone-800">{reportForm.reported_by_username || '-'}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-stone-200/60 p-4">
              <p className="text-xs text-stone-500">Alasan laporan</p>
              <p className="mt-1 font-medium text-stone-800">{reportForm.report_reason || '-'}</p>
            </div>
            <div className="rounded-xl border border-stone-200/60 p-4">
              <p className="text-xs text-stone-500">Tanggal laporan</p>
              <p className="mt-1 font-medium text-stone-800">{formatDate(reportForm.created_at)}</p>
            </div>
          </div>

          <div className="rounded-xl border border-stone-200/60 p-4">
            <p className="text-xs text-stone-500">Detail laporan</p>
            <p className="mt-1 text-sm text-stone-800 whitespace-pre-wrap">{reportForm.report_text || '(Tidak ada detail tambahan)'}</p>
          </div>

          <div className="rounded-xl border border-stone-200/60 p-4">
            <p className="text-xs text-stone-500">Review yang dilaporkan</p>
            <p className="mt-1 text-sm text-stone-800 whitespace-pre-wrap">{reportForm.review_text || '(Review sudah tidak tersedia)'}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Status moderasi</label>
            <select
              value={reportForm.status}
              onChange={(event) => setReportForm((prev) => ({ ...prev, status: event.target.value }))}
              className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
            >
              <option value="pending">pending</option>
              <option value="reviewed">reviewed</option>
              <option value="resolved">resolved</option>
              <option value="dismissed">dismissed</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Catatan admin</label>
            <textarea
              rows={4}
              value={reportForm.admin_notes}
              onChange={(event) => setReportForm((prev) => ({ ...prev, admin_notes: event.target.value }))}
              className="w-full rounded-xl border border-stone-300/70 bg-stone-50 px-4 py-2.5 text-sm text-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="Contoh: Review melanggar aturan spam, sudah dihapus."
            />
          </div>

          <div className="flex justify-end gap-3">
            <button type="button" onClick={closeReportModal} className="rounded-xl border border-stone-300/70 px-4 py-2 text-sm text-stone-700 hover:bg-stone-100 transition-all duration-300 ease-out cursor-pointer">
              Batal
            </button>
            <button type="submit" disabled={reportSubmitting} className="rounded-xl bg-amber-700 px-4 py-2 text-sm font-medium text-stone-50 hover:bg-amber-800 disabled:opacity-60 transition-all duration-300 ease-out cursor-pointer">
              {reportSubmitting ? 'Menyimpan...' : 'Simpan moderasi'}
            </button>
          </div>
        </form>
      </AdminModal>
    </div>
  );
}
