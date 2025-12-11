#!/usr/bin/env python3
"""
Script untuk mengecek quota dan usage LLM dari log file
"""

import re
import os
import sys
from pathlib import Path

# Path ke log file
LOG_FILE = Path(__file__).parent.parent / "logs" / "flask_server.log"

def check_token_usage_from_log():
    """Cek token usage terakhir dari log"""
    if not LOG_FILE.exists():
        print("❌ Log file tidak ditemukan:", LOG_FILE)
        print("   Pastikan backend sudah pernah dijalankan dan menghasilkan log.")
        return False
    
    print("📊 Mengecek Token Usage dari Log...")
    print("=" * 60)
    
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Cari baris terakhir dengan token info
    token_info_found = False
    for line in reversed(lines):
        if "[LLM] TOTAL INPUT:" in line:
            token_info_found = True
            print("\n✅ Token Usage Terakhir:")
            print(line.strip())
            
            # Extract angka
            match = re.search(r'~(\d+) tokens', line)
            if match:
                tokens = int(match.group(1))
                limit = 8192
                percentage = (tokens / limit) * 100
                
                print(f"\n📈 Breakdown:")
                print(f"   Usage: {tokens:,} / {limit:,} tokens")
                print(f"   Persentase: {percentage:.1f}%")
                
                if percentage > 90:
                    print(f"   Status: ⚠️ KRITIS - Mendekati limit!")
                elif percentage > 75:
                    print(f"   Status: ⚠️ PERINGATAN - Di atas 75% limit")
                else:
                    print(f"   Status: ✅ AMAN")
            
            # Cari breakdown detail
            breakdown_started = False
            breakdown_lines = []
            for i, l in enumerate(reversed(lines)):
                if "[LLM] ========== TOKEN BREAKDOWN ==========" in l:
                    # Ambil 10 baris berikutnya (breakdown detail)
                    start_idx = len(lines) - i - 1
                    for j in range(start_idx, min(start_idx + 15, len(lines))):
                        if "[LLM]" in lines[j]:
                            breakdown_lines.append(lines[j].strip())
                    break
            
            if breakdown_lines:
                print(f"\n📋 Detail Breakdown:")
                for bl in reversed(breakdown_lines[:8]):  # Tampilkan 8 baris terakhir
                    # Hapus prefix [LLM] untuk readability
                    clean_line = bl.replace("[LLM] ", "").replace("[LLM]", "")
                    if clean_line.strip():
                        print(f"   {clean_line}")
            
            break
    
    if not token_info_found:
        print("⚠️ Token usage info tidak ditemukan di log.")
        print("   Pastikan endpoint /api/llm/analyze sudah pernah dipanggil.")
    
    return token_info_found

def check_quota_errors():
    """Cek error terkait quota dari log"""
    if not LOG_FILE.exists():
        return []
    
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    errors = []
    keywords = ['quota', 'exceeded', '402', '429', 'payment required', 'rate limit']
    
    # Cek 500 baris terakhir
    for i, line in enumerate(lines[-500:], len(lines) - 500):
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in keywords):
            # Skip jika hanya info biasa (bukan error)
            if 'estimated' not in line_lower and 'info' not in line_lower.lower():
                errors.append((i + 1, line.strip()))
    
    return errors

def check_hf_api_errors():
    """Cek error khusus dari Hugging Face API"""
    if not LOG_FILE.exists():
        return []
    
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    errors = []
    hf_keywords = ['hf api error', 'huggingface', 'inference api', 'hf_client']
    
    for i, line in enumerate(lines[-500:], len(lines) - 500):
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in hf_keywords):
            if 'error' in line_lower or 'failed' in line_lower or 'exception' in line_lower:
                errors.append((i + 1, line.strip()))
    
    return errors

def main():
    print("🔍 COFIND LLM Quota Checker")
    print("=" * 60)
    
    # 1. Cek token usage
    token_found = check_token_usage_from_log()
    
    # 2. Cek quota errors
    print("\n" + "=" * 60)
    print("🔍 Mengecek Error Quota...")
    print("=" * 60)
    
    quota_errors = check_quota_errors()
    hf_errors = check_hf_api_errors()
    
    all_errors = quota_errors + hf_errors
    # Remove duplicates
    all_errors = list(dict.fromkeys(all_errors))
    
    if all_errors:
        print(f"\n⚠️ Ditemukan {len(all_errors)} error terkait quota:")
        print("-" * 60)
        for line_num, error in all_errors[-10:]:  # Tampilkan 10 terakhir
            print(f"   Line {line_num}: {error[:80]}...")
        print("\n💡 Saran:")
        print("   1. Cek Hugging Face dashboard: https://huggingface.co/settings/billing")
        print("   2. Pastikan HF_API_TOKEN masih valid")
        print("   3. Cek apakah quota/credits masih tersedia")
    else:
        print("\n✅ Tidak ada error quota ditemukan di log terakhir")
    
    # 3. Summary
    print("\n" + "=" * 60)
    print("📝 Summary")
    print("=" * 60)
    print(f"   Log file: {LOG_FILE}")
    print(f"   Token info: {'✅ Ditemukan' if token_found else '❌ Tidak ditemukan'}")
    print(f"   Quota errors: {len(all_errors)} ditemukan")
    
    # 4. Quick tips
    print("\n💡 Quick Tips:")
    print("   - Cek Hugging Face quota: https://huggingface.co/settings/billing")
    print("   - Monitor token usage harus < 75% dari 8,192 tokens")
    print("   - Jika quota habis, pertimbangkan upgrade ke paid tier")
    print("   - Dokumentasi lengkap: docs/CARA_CEK_QUOTA_LLM.md")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Dibatalkan oleh user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

