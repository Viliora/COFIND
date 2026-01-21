// ==============================================
// COPY-PASTE THIS DIRECTLY TO CONSOLE
// ==============================================

// Simple check without imports
function checkSession() {
  console.group('🔍 SESSION CHECK');
  
  // 1. Check localStorage for session
  const sbKey = Object.keys(localStorage).find(k => k.includes('sb-') && k.includes('auth'));
  
  console.log('📦 Session key:', sbKey ? '✅ EXISTS' : '❌ NOT FOUND');
  if (sbKey) {
    try {
      const sessionData = JSON.parse(localStorage.getItem(sbKey));
      console.log('   User ID:', sessionData?.user?.id || 'N/A');
      console.log('   Email:', sessionData?.user?.email || 'N/A');
      console.log('   Valid:', '✅ YES');
    } catch (e) {
      console.error('   Error parsing:', e.message);
    }
  }
  
  // 2. Check Supabase client
  console.log('\n🔌 Supabase Client:', window.__supabaseClient ? '✅ EXISTS' : '❌ NOT FOUND');
  
  // 3. Check all localStorage keys
  console.log('\n📋 All localStorage keys:');
  Object.keys(localStorage).slice(0, 15).forEach(k => {
    const size = localStorage.getItem(k).length;
    console.log(`   ${k}: ${size}b`);
  });
  
  console.groupEnd();
  
  return {
    hasSession: !!sbKey,
    hasClient: !!window.__supabaseClient
  };
}

// Run it
checkSession();
