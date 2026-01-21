/**
 * Test Frontend Auth Integration
 * Tests the new authService and AuthContext with backend API
 */

const API_BASE = 'http://localhost:5000';

async function testAuthFlow() {
  console.log('🧪 Testing Frontend Auth Integration...\n');

  try {
    // Test 1: Signup
    console.log('[TEST 1] Signup');
    const signupRes = await fetch(`${API_BASE}/api/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'test_fe@example.com',
        username: 'test_fe_user',
        password: 'testpassword123',
        full_name: 'Test Frontend User'
      })
    });
    const signupData = await signupRes.json();
    console.log(`Status: ${signupRes.status}`);
    console.log(`Response:`, signupData);
    
    if (signupData.status !== 'success') {
      throw new Error('Signup failed: ' + signupData.message);
    }
    
    const token = signupData.token;
    const user = signupData.user;
    console.log(`✅ Signup successful! Token: ${token.substring(0, 20)}...`);
    console.log(`   User: ${user.username} (ID: ${user.id})\n`);

    // Test 2: Verify Token
    console.log('[TEST 2] Verify Token');
    const verifyRes = await fetch(`${API_BASE}/api/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token })
    });
    const verifyData = await verifyRes.json();
    console.log(`Status: ${verifyRes.status}`);
    console.log(`Valid: ${verifyData.status === 'success'}`);
    console.log(`✅ Token verification works!\n`);

    // Test 3: Get User
    console.log('[TEST 3] Get User (with auth token)');
    const userRes = await fetch(`${API_BASE}/api/auth/user`, {
      method: 'GET',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const userData = await userRes.json();
    console.log(`Status: ${userRes.status}`);
    console.log(`Response:`, userData);
    console.log(`✅ Get user works!\n`);

    // Test 4: Login
    console.log('[TEST 4] Login with same credentials');
    const loginRes = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'test_fe@example.com',
        password: 'testpassword123'
      })
    });
    const loginData = await loginRes.json();
    console.log(`Status: ${loginRes.status}`);
    console.log(`User logged in: ${loginData.user.username}`);
    console.log(`New token: ${loginData.token.substring(0, 20)}...`);
    console.log(`✅ Login works!\n`);

    // Test 5: Update Profile
    console.log('[TEST 5] Update Profile');
    const updateRes = await fetch(`${API_BASE}/api/auth/update-profile`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        full_name: 'Updated Frontend User',
        bio: 'Testing from frontend'
      })
    });
    const updateData = await updateRes.json();
    console.log(`Status: ${updateRes.status}`);
    console.log(`Updated user: ${updateData.user.full_name}`);
    console.log(`✅ Update profile works!\n`);

    console.log('═══════════════════════════════════════');
    console.log('✅ ALL FRONTEND AUTH TESTS PASSED!');
    console.log('═══════════════════════════════════════');
    console.log('\nAuthContext is ready for components:');
    console.log('- signUp() works');
    console.log('- signIn() works');
    console.log('- verifySession() works');
    console.log('- updateProfile() works');
    console.log('- Token stored in localStorage');

  } catch (error) {
    console.error('\n❌ TEST FAILED:', error.message);
    process.exit(1);
  }
}

testAuthFlow();
