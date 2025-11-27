# 📚 Koleksi Feature - Favorit & Want to Visit

## 🎯 Overview

Fitur **Koleksi** menggantikan button Favorit tunggal dengan sistem koleksi yang lebih lengkap:
- **Favorit** - Coffee shops yang sudah dikunjungi dan disukai
- **Want to Visit** - Coffee shops yang ingin dikunjungi

---

## ✨ Fitur yang Ditambahkan

### **1. Navbar - Koleksi Dropdown**

**Before:**
```
[Beranda] [Favorit] [Rekomendasi] [Tentang]
```

**After:**
```
[Beranda] [Koleksi ▼] [Rekomendasi] [Tentang]
         ↓
    [Favorit]
    [Want to Visit]
```

**Features:**
- ✅ Dropdown menu dengan 2 opsi
- ✅ Hover state & active state
- ✅ Click outside to close
- ✅ Mobile responsive

### **2. Page Want to Visit**

**Route:** `/want-to-visit`

**Features:**
- ✅ Display coffee shops dari localStorage
- ✅ Fetch detail dari API
- ✅ Grid layout (responsive)
- ✅ Empty state dengan CTA
- ✅ Loading state

### **3. Shop Detail - Dual Buttons**

**Before:**
```
[❤️ Favorit] (single button, bottom-right)
```

**After:**
```
[🔖 Want to Visit] (top button)
[❤️ Favorit]       (bottom button)
```

**Features:**
- ✅ 2 floating buttons (stacked vertically)
- ✅ Independent toggle (bisa keduanya aktif)
- ✅ Visual feedback (filled/outlined)
- ✅ Notification toast
- ✅ localStorage persistence

---

## 🏗️ Technical Implementation

### **Data Storage (localStorage):**

```javascript
// Favorit
localStorage.setItem('favoriteShops', JSON.stringify([
  'ChIJpVctpWBZ4S4RUbSIT-pD18',
  'ChIJXx6ZdWBZ4S4RgXTjD...'
]));

// Want to Visit
localStorage.setItem('wantToVisitShops', JSON.stringify([
  'ChIJmWdZdWBZ4S4RgXTjD...',
  'ChIJabcdZdWBZ4S4RgXTjD...'
]));
```

### **Files Created/Modified:**

**New Files:**
1. `frontend-cofind/src/pages/WantToVisit.jsx` - Want to Visit page

**Modified Files:**
1. `frontend-cofind/src/components/Navbar.jsx` - Dropdown menu
2. `frontend-cofind/src/pages/ShopDetail.jsx` - Dual buttons
3. `frontend-cofind/src/App.jsx` - Routing

---

## 🎨 UI/UX Design

### **Navbar Dropdown:**

```
┌─────────────────┐
│ 📚 Koleksi ▼   │ ← Button
└─────────────────┘
        ↓
┌─────────────────┐
│ ❤️  Favorit    │
│ 🔖  Want to    │
│     Visit      │
└─────────────────┘
```

**Colors:**
- Active: Pink gradient (from-pink-500 to-rose-500)
- Hover: Gray background
- Dropdown: White/Dark background with shadow

### **Shop Detail Buttons:**

```
        ┌──────┐
        │  🔖  │ ← Want to Visit (Blue)
        └──────┘
           ↓ 16px gap
        ┌──────┐
        │  ❤️  │ ← Favorit (Pink)
        └──────┘
```

**Position:** Fixed bottom-right (8px from edges)

**States:**
- Default: Colored circle + white icon
- Active: White circle + colored border + colored icon
- Hover: Scale 1.1 + color change

---

## 📱 Responsive Behavior

### **Desktop:**
- Dropdown menu on hover/click
- Both buttons visible
- Smooth animations

### **Mobile:**
- Dropdown in mobile menu (expanded list)
- Buttons slightly smaller
- Touch-friendly sizes (48x48px)

---

## 🔄 User Flow

### **Add to Want to Visit:**

```
1. User browse coffee shops
2. Click coffee shop → Detail page
3. Click 🔖 Want to Visit button
4. Toast: "Ditambahkan ke want to visit!"
5. Button state: Blue filled
6. Saved to localStorage
```

### **View Want to Visit:**

```
1. Click "Koleksi" in navbar
2. Click "Want to Visit"
3. Navigate to /want-to-visit
4. See list of coffee shops
5. Click shop → Detail page
```

### **Move from Want to Visit to Favorit:**

```
1. Visit coffee shop (in real life)
2. Open detail page
3. Click ❤️ Favorit button
4. Optionally: Remove from Want to Visit
   (manual, or keep both)
```

---

## 💾 Data Management

### **localStorage Keys:**

| Key | Type | Description |
|-----|------|-------------|
| `favoriteShops` | Array<string> | Place IDs of favorite shops |
| `wantToVisitShops` | Array<string> | Place IDs of want-to-visit shops |

### **Data Flow:**

```
User Action
    ↓
Toggle Function
    ↓
Update localStorage
    ↓
Update State
    ↓
Show Notification
    ↓
Re-render UI
```

### **API Integration:**

```javascript
// When viewing collection page
1. Get place_ids from localStorage
2. For each place_id:
   - Fetch detail from API
   - Parse photos (HD quality)
   - Build shop object
3. Display in grid
```

---

## 🎯 Use Cases

### **Use Case 1: Planning Coffee Tour**

```
User wants to visit 5 coffee shops this weekend:

1. Browse homepage
2. Find interesting shops
3. Add to "Want to Visit" (5 shops)
4. View "Want to Visit" page
5. Plan route based on locations
6. Visit shops one by one
7. After visiting, move to "Favorit"
```

### **Use Case 2: Building Favorite List**

```
User has visited many coffee shops:

1. Visit coffee shop
2. If liked → Add to "Favorit"
3. If not liked → Skip
4. Build personal collection
5. Share with friends
```

### **Use Case 3: Recommendation Basis**

```
For future LLaMA integration:

1. User has Favorit + Want to Visit
2. LLaMA analyzes preferences
3. Generate personalized recommendations
4. Based on:
   - Favorite shops (liked)
   - Want to visit (interested)
   - Ratings & reviews
```

---

## 🚀 Future Enhancements

### **Phase 2: Social Features**

```
- Share collections
- Export to PDF/image
- Collaborative lists
- Friend recommendations
```

### **Phase 3: Smart Features**

```
- Auto-suggest based on favorites
- Route optimization
- Visit reminders
- Check-in feature
```

### **Phase 4: Analytics**

```
- Most favorited shops
- Trending want-to-visit
- User preferences analysis
- LLaMA-powered insights
```

---

## 📊 Comparison

### **Before (Single Favorit):**

| Feature | Status |
|---------|--------|
| Save favorites | ✅ |
| View favorites | ✅ |
| Plan visits | ❌ |
| Organize collections | ❌ |
| Multiple lists | ❌ |

### **After (Koleksi System):**

| Feature | Status |
|---------|--------|
| Save favorites | ✅ |
| View favorites | ✅ |
| Plan visits | ✅ (Want to Visit) |
| Organize collections | ✅ (2 categories) |
| Multiple lists | ✅ (Favorit + Want to Visit) |

---

## 🐛 Troubleshooting

### **Problem 1: Dropdown tidak muncul**

**Solution:**
```javascript
// Check state
console.log(collectionDropdownOpen);

// Check z-index
className="... z-50"
```

### **Problem 2: Data tidak persist**

**Solution:**
```javascript
// Check localStorage
console.log(localStorage.getItem('wantToVisitShops'));

// Clear and retry
localStorage.removeItem('wantToVisitShops');
```

### **Problem 3: Buttons overlap**

**Solution:**
```css
/* Adjust gap */
.flex-col {
  gap: 1rem; /* 16px */
}
```

---

## ✅ Testing Checklist

### **Navbar:**
- [ ] Dropdown opens on click
- [ ] Dropdown closes on click outside
- [ ] Links navigate correctly
- [ ] Active state shows correctly
- [ ] Mobile menu works

### **Want to Visit Page:**
- [ ] Empty state shows when no data
- [ ] Loading state shows
- [ ] Coffee shops display correctly
- [ ] Photos load (HD quality)
- [ ] Click navigates to detail

### **Shop Detail:**
- [ ] Both buttons visible
- [ ] Want to Visit toggle works
- [ ] Favorit toggle works
- [ ] Notifications show
- [ ] State persists after refresh

### **Data Persistence:**
- [ ] localStorage saves correctly
- [ ] Data persists after refresh
- [ ] Multiple shops can be added
- [ ] Shops can be removed
- [ ] No duplicates

---

## 📝 Summary

**Koleksi feature successfully implemented!**

**Changes:**
- ✅ Navbar: Favorit → Koleksi (dropdown)
- ✅ New page: Want to Visit
- ✅ Shop Detail: Dual buttons (Want to Visit + Favorit)
- ✅ localStorage: 2 separate collections
- ✅ Routing: /want-to-visit added

**Benefits:**
- 📚 Better organization (2 categories)
- 🎯 Clear user intent (visited vs planning)
- 💡 Foundation for LLaMA recommendations
- 🚀 Scalable for future features

**Ready to use! 🎉**

